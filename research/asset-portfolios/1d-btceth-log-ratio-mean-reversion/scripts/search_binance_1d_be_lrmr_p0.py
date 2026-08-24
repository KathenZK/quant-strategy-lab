from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-log-ratio-mean-reversion"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATA_HELPER_PATH = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p0.py"
DATA_HELPER_SHA256 = "8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29"
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008


@dataclass(frozen=True, order=True)
class Config:
    lookback: int
    entry_z: float
    exit_z: float
    stop_z: float
    max_hold_days: int
    cooldown_days: int


@dataclass
class Result:
    equity_multiple: float
    max_drawdown_pct: float
    states: np.ndarray
    path: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    positive_pair_count: int
    negative_pair_count: int


def load_data_helper() -> Any:
    digest = hashlib.sha256(DATA_HELPER_PATH.read_bytes()).hexdigest()
    if digest != DATA_HELPER_SHA256:
        raise RuntimeError(f"data helper drift: {digest}")
    spec = importlib.util.spec_from_file_location("binance_1d_be_lrmr_data", DATA_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {DATA_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configs() -> list[Config]:
    output = []
    for values in itertools.product(
        (20, 30, 45, 60, 90, 120, 180),
        (1.0, 1.5, 2.0, 2.5, 3.0),
        (0.0, 0.25, 0.5, 0.75, 1.0),
        (0.0, 3.0, 4.0, 5.0),
        (0, 3, 7, 14, 30, 60),
        (0, 1, 3, 7),
    ):
        config = Config(*values)
        if config.exit_z >= config.entry_z:
            continue
        if config.stop_z > 0 and config.stop_z <= config.entry_z:
            continue
        output.append(config)
    return output


def ratio_z(daily: pd.DataFrame, lookback: int) -> np.ndarray:
    ratio = np.log(daily["BTCUSDT_close"].astype(float) / daily["ETHUSDT_close"].astype(float))
    mean = ratio.rolling(lookback, min_periods=lookback).mean()
    std = ratio.rolling(lookback, min_periods=lookback).std(ddof=1)
    return ((ratio - mean) / std.replace(0.0, np.nan)).to_numpy(float)


def pair_states(z: np.ndarray, config: Config, *, extra_delay_days: int = 0) -> np.ndarray:
    lag = 1 + extra_delay_days
    output = np.zeros(len(z), dtype=np.int8)
    state = 0
    entry_index = -1
    next_entry_index = 0
    for index in range(len(z)):
        signal_index = index - lag
        if signal_index < 0 or not np.isfinite(z[signal_index]):
            output[index] = state
            continue
        signal = float(z[signal_index])
        previous_signal = float(z[signal_index - 1]) if signal_index > 0 else float("nan")
        if state:
            crossed = (state > 0 and signal >= 0.0) or (state < 0 and signal <= 0.0)
            reverted = abs(signal) <= config.exit_z
            stopped = (
                config.stop_z > 0
                and abs(signal) >= config.stop_z
                and np.isfinite(previous_signal)
                and abs(signal) > abs(previous_signal)
            )
            timed_out = config.max_hold_days > 0 and index - entry_index >= config.max_hold_days
            if crossed or reverted or stopped or timed_out:
                state = 0
                next_entry_index = index + config.cooldown_days + 1
        elif index >= next_entry_index:
            if signal >= config.entry_z:
                state = -1
                entry_index = index
            elif signal <= -config.entry_z:
                state = 1
                entry_index = index
        output[index] = state
    return output


def fill_price(mark: float, side: int, slippage: float, *, entry: bool) -> float:
    direction = side if entry else -side
    return mark * (1.0 + direction * slippage)


def open_pair(equity: float, state: int, btc_mark: float, eth_mark: float, slippage: float) -> tuple[float, dict[str, Any]]:
    sides = {"BTCUSDT": state, "ETHUSDT": -state}
    marks = {"BTCUSDT": btc_mark, "ETHUSDT": eth_mark}
    legs = {}
    cash = equity
    for symbol in ("BTCUSDT", "ETHUSDT"):
        side = sides[symbol]
        fill = fill_price(marks[symbol], side, slippage, entry=True)
        quantity = 0.5 * equity / fill
        fee = quantity * fill * FEE
        cash -= fee
        legs[symbol] = {"side": side, "quantity": quantity, "entry_price": fill, "entry_fee": fee}
    return cash, legs


def mark_equity(cash: float, legs: dict[str, Any], marks: dict[str, float]) -> float:
    return float(cash + sum(leg["side"] * leg["quantity"] * (marks[symbol] - leg["entry_price"]) for symbol, leg in legs.items()))


def close_pair(cash: float, legs: dict[str, Any], marks: dict[str, float], slippage: float) -> tuple[float, dict[str, float]]:
    fills = {}
    for symbol, leg in legs.items():
        fill = fill_price(marks[symbol], leg["side"], slippage, entry=False)
        cash += leg["side"] * leg["quantity"] * (fill - leg["entry_price"])
        cash -= leg["quantity"] * fill * FEE
        fills[symbol] = fill
    return float(cash), fills


def apply_funding(cash: float, legs: dict[str, Any], unit_funding: dict[str, float]) -> float:
    return float(cash - sum(leg["side"] * leg["quantity"] * unit_funding[symbol] for symbol, leg in legs.items()))


def daily_replay(
    data: Any,
    daily: pd.DataFrame,
    states: np.ndarray,
    *,
    slippage: float,
    retain: bool = False,
) -> Result:
    start = int(daily["ts"].searchsorted(data.COMMON_START))
    end = int(daily["ts"].searchsorted(data.DEVELOPMENT_END))
    cash = 1.0
    legs: dict[str, Any] = {}
    state = 0
    entry_ts: pd.Timestamp | None = None
    entry_equity = 0.0
    peak = 1.0
    max_drawdown = 0.0
    path, trades = [], []
    positive_pairs = 0
    negative_pairs = 0
    for index in range(start, end + 1):
        row = daily.iloc[index]
        timestamp = pd.Timestamp(row["ts"])
        target = 0 if index == end else int(states[index])
        if target != state:
            if state:
                cash, exit_fills = close_pair(
                    cash,
                    legs,
                    {symbol: float(row[f"{symbol}_open"]) for symbol in data.ASSETS},
                    slippage,
                )
                if retain:
                    trades.append(
                        {
                            "entry_ts": entry_ts,
                            "exit_ts": timestamp,
                            "state": state,
                            "entry_equity": entry_equity,
                            "exit_equity": cash,
                            "pair_log_growth": math.log(cash / entry_equity) if cash > 0 and entry_equity > 0 else None,
                            **{f"{symbol}_entry_price": leg["entry_price"] for symbol, leg in legs.items()},
                            **{f"{symbol}_exit_price": fill for symbol, fill in exit_fills.items()},
                        }
                    )
                legs = {}
                state = 0
            if target and index < end and cash > 0:
                entry_equity = cash
                entry_ts = timestamp
                cash, legs = open_pair(
                    cash,
                    target,
                    float(row["BTCUSDT_open"]),
                    float(row["ETHUSDT_open"]),
                    slippage,
                )
                state = target
                positive_pairs += int(state > 0)
                negative_pairs += int(state < 0)
        if index == end:
            equity = cash
        elif state:
            cash = apply_funding(
                cash,
                legs,
                {symbol: float(row[f"{symbol}_unit_funding"]) for symbol in data.ASSETS},
            )
            equity = mark_equity(
                cash,
                legs,
                {symbol: float(row[f"{symbol}_close"]) for symbol in data.ASSETS},
            )
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if retain:
            path.append({"ts": timestamp, "equity": equity, "state": state})
    return Result(float(cash), float(max_drawdown * 100.0), states, path, trades, positive_pairs, negative_pairs)


def build_daily_arrays(data: Any, daily: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        f"{symbol}_{field}": daily[f"{symbol}_{field}"].to_numpy(float)
        for symbol in data.ASSETS
        for field in ("open", "close", "unit_funding")
    }


def fast_daily_replay(
    data: Any,
    daily: pd.DataFrame,
    values: dict[str, np.ndarray],
    states: np.ndarray,
    *,
    slippage: float,
) -> Result:
    start = int(daily["ts"].searchsorted(data.COMMON_START))
    end = int(daily["ts"].searchsorted(data.DEVELOPMENT_END))
    cash, state, peak, max_drawdown = 1.0, 0, 1.0, 0.0
    legs: dict[str, Any] = {}
    positive_pairs = 0
    negative_pairs = 0
    for index in range(start, end + 1):
        target = 0 if index == end else int(states[index])
        if target != state:
            if state:
                cash, _ = close_pair(
                    cash,
                    legs,
                    {symbol: values[f"{symbol}_open"][index] for symbol in data.ASSETS},
                    slippage,
                )
                legs = {}
                state = 0
            if target and index < end and cash > 0:
                cash, legs = open_pair(
                    cash,
                    target,
                    values["BTCUSDT_open"][index],
                    values["ETHUSDT_open"][index],
                    slippage,
                )
                state = target
                positive_pairs += int(state > 0)
                negative_pairs += int(state < 0)
        if index == end:
            equity = cash
        elif state:
            cash = apply_funding(
                cash,
                legs,
                {symbol: values[f"{symbol}_unit_funding"][index] for symbol in data.ASSETS},
            )
            equity = mark_equity(
                cash,
                legs,
                {symbol: values[f"{symbol}_close"][index] for symbol in data.ASSETS},
            )
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    return Result(float(cash), float(max_drawdown * 100.0), states, [], [], positive_pairs, negative_pairs)


def hourly_replay(
    data: Any,
    union: pd.DataFrame,
    daily: pd.DataFrame,
    states: np.ndarray,
    *,
    slippage: float,
    retain: bool = False,
) -> Result:
    target_by_day = dict(zip(daily["ts"], states, strict=True))
    cash = 1.0
    legs: dict[str, Any] = {}
    state = 0
    entry_ts: pd.Timestamp | None = None
    entry_equity = 0.0
    peak = 1.0
    max_drawdown = 0.0
    path, trades = [], []
    positive_pairs = 0
    negative_pairs = 0
    for row in union.itertuples(index=False):
        timestamp = pd.Timestamp(row.ts)
        if timestamp.hour == 0:
            target = 0 if timestamp == data.DEVELOPMENT_END else int(target_by_day[timestamp])
            if target != state:
                if state:
                    cash, exit_fills = close_pair(
                        cash,
                        legs,
                        {symbol: float(getattr(row, f"{symbol}_open")) for symbol in data.ASSETS},
                        slippage,
                    )
                    if retain:
                        trades.append(
                            {
                                "entry_ts": entry_ts,
                                "exit_ts": timestamp,
                                "state": state,
                                "entry_equity": entry_equity,
                                "exit_equity": cash,
                                "pair_log_growth": math.log(cash / entry_equity) if cash > 0 and entry_equity > 0 else None,
                                **{f"{symbol}_entry_price": leg["entry_price"] for symbol, leg in legs.items()},
                                **{f"{symbol}_exit_price": fill for symbol, fill in exit_fills.items()},
                            }
                        )
                    legs = {}
                    state = 0
                if target and timestamp < data.DEVELOPMENT_END and cash > 0:
                    entry_equity = cash
                    entry_ts = timestamp
                    cash, legs = open_pair(
                        cash,
                        target,
                        float(row.BTCUSDT_open),
                        float(row.ETHUSDT_open),
                        slippage,
                    )
                    state = target
                    positive_pairs += int(state > 0)
                    negative_pairs += int(state < 0)
        if timestamp == data.DEVELOPMENT_END:
            equity = cash
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity / peak - 1.0)
            if retain:
                path.append({"ts": timestamp, "equity": equity, "state": 0})
            break
        if state:
            cash = apply_funding(
                cash,
                legs,
                {symbol: float(getattr(row, f"{symbol}_unit_funding")) for symbol in data.ASSETS},
            )
            favorable_marks, adverse_marks, close_marks = {}, {}, {}
            for symbol, leg in legs.items():
                favorable_marks[symbol] = float(getattr(row, f"{symbol}_{'high' if leg['side'] > 0 else 'low'}"))
                adverse_marks[symbol] = float(getattr(row, f"{symbol}_{'low' if leg['side'] > 0 else 'high'}"))
                close_marks[symbol] = float(getattr(row, f"{symbol}_close"))
            favorable_equity = mark_equity(cash, legs, favorable_marks)
            peak = max(peak, favorable_equity)
            adverse_equity = mark_equity(cash, legs, adverse_marks)
            max_drawdown = min(max_drawdown, adverse_equity / peak - 1.0)
            equity = mark_equity(cash, legs, close_marks)
        else:
            equity = cash
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
        if retain and timestamp.hour == 23:
            path.append({"ts": timestamp, "equity": equity, "state": state})
    return Result(float(cash), float(max_drawdown * 100.0), states, path, trades, positive_pairs, negative_pairs)


def complete_year_ratio(path: list[dict[str, Any]]) -> float:
    equity = pd.Series([row["equity"] for row in path], index=pd.DatetimeIndex([row["ts"] for row in path])).sort_index()
    results = []
    for year in range(2020, 2025):
        prior = equity.loc[equity.index < pd.Timestamp(f"{year}-01-01", tz="UTC")]
        current = equity.loc[(equity.index >= pd.Timestamp(f"{year}-01-01", tz="UTC")) & (equity.index < pd.Timestamp(f"{year + 1}-01-01", tz="UTC"))]
        if not prior.empty and not current.empty:
            results.append(current.iloc[-1] / prior.iloc[-1] - 1.0)
    return float(np.mean(np.asarray(results) > 0.0)) if results else 0.0


def rolling_ratio(path: list[dict[str, Any]]) -> float:
    equity = pd.Series([row["equity"] for row in path], index=pd.DatetimeIndex([row["ts"] for row in path])).sort_index()
    values = (equity / equity.shift(365) - 1.0).dropna()
    return float((values > 0.0).mean()) if not values.empty else 0.0


def concentration(trades: list[dict[str, Any]]) -> float:
    values = [max(0.0, float(trade["pair_log_growth"])) for trade in trades if trade["pair_log_growth"] is not None]
    return max(values, default=0.0) / sum(values) if sum(values) > 0 else 1.0


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, np.generic):
        return clean(value.item())
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Frozen P0 search for BIN-1D-BE-LRMR.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 15288
        print("self-test: PASS")
        return
    data = load_data_helper()
    hourly, funding, quality = data.load_frozen_data()
    daily = data.build_daily(hourly, funding)
    union = data.build_hourly_union(hourly, funding)
    z_by_lookback = {lookback: ratio_z(daily, lookback) for lookback in sorted({config.lookback for config in grid})}
    daily_values = build_daily_arrays(data, daily)
    control_config = Config(60, 1.5, 0.5, 4.0, 14, 1)
    control_states = pair_states(z_by_lookback[control_config.lookback], control_config)
    control_daily = daily_replay(data, daily, control_states, slippage=BASE_SLIPPAGE, retain=True)
    control_fast = fast_daily_replay(data, daily, daily_values, control_states, slippage=BASE_SLIPPAGE)
    control_hourly = hourly_replay(data, union, daily, control_states, slippage=BASE_SLIPPAGE, retain=True)
    if not math.isclose(control_daily.equity_multiple, control_fast.equity_multiple, abs_tol=1e-12):
        raise RuntimeError("fast/detailed daily final-equity reconciliation failed")
    if not math.isclose(control_daily.max_drawdown_pct, control_fast.max_drawdown_pct, abs_tol=1e-12):
        raise RuntimeError("fast/detailed daily MDD reconciliation failed")
    if not math.isclose(control_daily.equity_multiple, control_hourly.equity_multiple, abs_tol=1e-12):
        raise RuntimeError("daily/hourly final-equity reconciliation failed")
    if len(control_daily.trades) != len(control_hourly.trades):
        raise RuntimeError("daily/hourly trade-count reconciliation failed")
    ledger_control = {
        "config": asdict(control_config),
        "daily_equity": control_daily.equity_multiple,
        "fast_daily_equity": control_fast.equity_multiple,
        "hourly_equity": control_hourly.equity_multiple,
        "absolute_difference": abs(control_daily.equity_multiple - control_hourly.equity_multiple),
        "daily_mdd_pct": control_daily.max_drawdown_pct,
        "conservative_ordered_mdd_pct": control_hourly.max_drawdown_pct,
        "trades": len(control_daily.trades),
        "parity": "PASS",
    }
    rows = []
    daily_candidates = []
    for config in grid:
        states = pair_states(z_by_lookback[config.lookback], config)
        result = fast_daily_replay(data, daily, daily_values, states, slippage=BASE_SLIPPAGE)
        passed = result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0
        rows.append({
            **asdict(config), "equity_multiple": result.equity_multiple,
            "daily_close_mdd_pct": result.max_drawdown_pct, "daily_screen_pass": passed,
            "state_path_sha256": hashlib.sha256(states.tobytes()).hexdigest(),
            "positive_pair_count": result.positive_pair_count, "negative_pair_count": result.negative_pair_count,
        })
        if passed:
            daily_candidates.append((config, states))
    details, retained, seen = [], {}, set()
    for config, states in sorted(daily_candidates):
        path_hash = hashlib.sha256(states.tobytes()).hexdigest()
        if path_hash in seen:
            continue
        seen.add(path_hash)
        base = hourly_replay(data, union, daily, states, slippage=BASE_SLIPPAGE, retain=True)
        row = {**asdict(config), "state_path_sha256": path_hash, "base_equity_multiple": base.equity_multiple, "base_ordered_mdd_pct": base.max_drawdown_pct, "pairs": len(base.trades), "base_screen_pass": base.equity_multiple >= 20.0 and base.max_drawdown_pct >= -20.0, "all_gates_pass": False}
        if row["base_screen_pass"]:
            stress = hourly_replay(data, union, daily, states, slippage=STRESS_SLIPPAGE)
            delayed_states = pair_states(z_by_lookback[config.lookback], config, extra_delay_days=1)
            delayed = hourly_replay(data, union, daily, delayed_states, slippage=BASE_SLIPPAGE)
            base_log = math.log(base.equity_multiple)
            stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 else -math.inf
            delay_retention = math.log(delayed.equity_multiple) / base_log if delayed.equity_multiple > 0 else -math.inf
            gates = {
                "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
                "delay": delay_retention >= 0.70 and delayed.equity_multiple >= 8.0 and delayed.max_drawdown_pct >= -25.0,
                "calendar": complete_year_ratio(base.path) >= 0.70,
                "rolling": rolling_ratio(base.path) >= 0.70,
                "capacity": len(base.trades) >= 20 and base.positive_pair_count >= 8 and base.negative_pair_count >= 8,
                "concentration": concentration(base.trades) <= 0.35,
            }
            row.update({
                "stress_equity_multiple": stress.equity_multiple, "stress_ordered_mdd_pct": stress.max_drawdown_pct,
                "stress_log_growth_retention": stress_retention, "delay_equity_multiple": delayed.equity_multiple,
                "delay_ordered_mdd_pct": delayed.max_drawdown_pct, "delay_log_growth_retention": delay_retention,
                "complete_year_positive_ratio": complete_year_ratio(base.path), "rolling_365d_positive_ratio": rolling_ratio(base.path),
                "positive_pair_count": base.positive_pair_count, "negative_pair_count": base.negative_pair_count,
                "max_pair_positive_log_share": concentration(base.trades),
                **{f"gate_{key}": value for key, value in gates.items()}, "all_gates_pass": all(gates.values()),
            })
            retained[config] = base
        details.append(row)
    frame, detail_frame = pd.DataFrame(rows), pd.DataFrame(details)
    passing = detail_frame.loc[detail_frame["all_gates_pass"]].copy() if not detail_frame.empty else detail_frame
    if not passing.empty:
        passing = passing.sort_values(["base_ordered_mdd_pct", "stress_log_growth_retention", "base_equity_multiple", "pairs", "lookback", "entry_z", "exit_z", "stop_z", "max_hold_days", "cooldown_days"], ascending=[False, False, False, True, True, True, True, True, True, True])
    unique = passing.iloc[0].to_dict() if not passing.empty else None
    best_growth = frame.sort_values(["equity_multiple", "daily_close_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["daily_close_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Log-Ratio-Mean-Reversion",
        "campaign": "P0 frozen development search", "status": "development candidate; audit sealed" if unique else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read", "data_quality": quality,
        "ledger_control": ledger_control,
        "contract": {"configs": len(grid), "fee_per_leg_fill": FEE, "base_slippage": BASE_SLIPPAGE, "stress_slippage": STRESS_SLIPPAGE, "initial_leg_notional": 0.5, "gross_leverage": 1.0},
        "counts": {"configs": len(frame), "daily_screen_pass": int(frame["daily_screen_pass"].sum()), "unique_ordered_paths": len(detail_frame), "all_gates_pass": int(detail_frame["all_gates_pass"].sum()) if not detail_frame.empty else 0},
        "best_growth": best_growth, "best_risk": best_risk, "unique_candidate": unique,
        "audit_revealed": False, "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_lrmr_p0_search_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    detail_frame.to_csv(ARTIFACT_DIR / f"{stem}_ordered_candidates.csv", index=False)
    if unique:
        config = Config(**{key: unique[key] for key in asdict(grid[0])})
        result = retained[config]
        pd.DataFrame(result.path).to_csv(ARTIFACT_DIR / f"{stem}_candidate_path.csv", index=False)
        pd.DataFrame(result.trades).to_csv(ARTIFACT_DIR / f"{stem}_candidate_trades.csv", index=False)
    print(json.dumps(clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean(best_growth), ensure_ascii=False))
    print(json.dumps(clean(best_risk), ensure_ascii=False))
    print(json.dumps(clean(unique), ensure_ascii=False))


if __name__ == "__main__":
    main()
