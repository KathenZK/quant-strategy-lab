from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-crisis-override-shadow-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CBCT_PATH = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend/scripts/search_binance_1d_be_cbct_p0.py"
EXPECTED_CONTROL = (21.270651982678306, -37.19612846945293)


@dataclass(frozen=True, order=True)
class Config:
    crisis_ema: int
    slope_days: int
    confirm_days: int


@dataclass
class RouterResult:
    equity_multiple: float
    ordered_mdd_pct: float
    path: pd.DataFrame
    trades: list[dict[str, Any]]
    crisis_legs: list[dict[str, Any]]
    counts: dict[str, int]


def load_cbct() -> Any:
    spec = importlib.util.spec_from_file_location("binance_1d_be_cost_cbct", CBCT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {CBCT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configs() -> list[Config]:
    return [Config(*values) for values in itertools.product((100, 200, 300), (20, 60), (1, 3))]


def confirmed_binary(raw: np.ndarray, days: int) -> np.ndarray:
    output = np.zeros(len(raw), dtype=np.int8)
    state, candidate, streak = 0, 0, 0
    for index, value in enumerate(raw):
        target = int(value)
        if target == state:
            candidate, streak = state, 0
        elif target == candidate:
            streak += 1
        else:
            candidate, streak = target, 1
        if target != state and streak >= days:
            state, candidate, streak = target, target, 0
        output[index] = state
    return output


def crisis_execution(daily_frame: pd.DataFrame, config: Config, delay_days: int = 0) -> np.ndarray:
    raw = np.ones(len(daily_frame), dtype=bool)
    for symbol in ("BTCUSDT", "ETHUSDT"):
        close = daily_frame[f"{symbol}_close"]
        ema = close.ewm(span=config.crisis_ema, adjust=False, min_periods=config.crisis_ema).mean()
        raw &= ((close < ema) & (ema < ema.shift(config.slope_days))).to_numpy(bool)
    decisions = confirmed_binary(raw.astype(np.int8), config.confirm_days)
    lag = 1 + delay_days
    execution = np.zeros(len(decisions), dtype=np.int8)
    execution[lag:] = decisions[:-lag]
    return execution


def shadow_replay(
    cbct: Any,
    data: Any,
    daily: Any,
    hourly: Any,
    daily_frame: pd.DataFrame,
    *,
    slippage: float,
    delay_days: int,
) -> Any:
    config = cbct.Config(20, 10, 50, 5.0, 2, 7, 120)
    return cbct.simulate(
        data,
        daily,
        hourly,
        cbct.build_entry_book(daily_frame, daily, 20, 50, 2),
        cbct.exit_channels(daily_frame, 10),
        config,
        slippage=slippage,
        delay_days=delay_days,
        retain=True,
        profit_protection=cbct.ProfitProtection(1.0, 0.35, 2),
    )


def open_short_basket(cbct: Any, equity: float, hourly: Any, hour: int, slippage: float) -> tuple[float, dict[str, float], dict[str, float]]:
    cash, quantities, fills = equity, {}, {}
    for symbol in cbct.SYMBOLS:
        mark = float(hourly.open[symbol][hour])
        fill = cbct.fill_price(mark, -1, slippage, entry=True)
        quantity = (equity * 0.5) / (fill * (1.0 + cbct.FEE))
        cash -= quantity * fill * cbct.FEE
        quantities[symbol], fills[symbol] = float(quantity), float(fill)
    return float(cash), quantities, fills


def close_short_basket(
    cbct: Any,
    cash: float,
    quantities: dict[str, float],
    fills: dict[str, float],
    hourly: Any,
    hour: int,
    slippage: float,
) -> tuple[float, dict[str, float]]:
    exits = {}
    for symbol in cbct.SYMBOLS:
        fill = cbct.fill_price(float(hourly.open[symbol][hour]), -1, slippage, entry=False)
        cash -= quantities[symbol] * (fill - fills[symbol])
        cash -= quantities[symbol] * fill * cbct.FEE
        exits[symbol] = float(fill)
    return float(cash), exits


def route_replay(
    cbct: Any,
    data: Any,
    daily: Any,
    hourly: Any,
    daily_frame: pd.DataFrame,
    shadow: Any,
    crisis: np.ndarray,
    *,
    slippage: float,
    retain: bool,
) -> RouterResult:
    entries = {pd.Timestamp(trade["entry_ts"]): trade for trade in shadow.trades}
    exits = {pd.Timestamp(trade["exit_ts"]): trade for trade in shadow.trades}
    partials = {
        pd.Timestamp(event["ts"]): event
        for trade in shadow.trades
        for event in trade.get("partial_events", [])
    }
    day_index = {pd.Timestamp(ts): index for index, ts in enumerate(daily.ts)}
    cash, peak, worst = 1.0, 1.0, 0.0
    mode = "flat"
    base_asset, base_side, base_quantity, base_entry_fill, base_entry_equity = "", 0, 0.0, 0.0, 0.0
    base_entry_ts: pd.Timestamp | None = None
    base_partial_events: list[dict[str, Any]] = []
    base_entry_source = "regular"
    pair_quantities: dict[str, float] = {}
    pair_fills: dict[str, float] = {}
    pair_entry_equity = 0.0
    pair_entry_ts: pd.Timestamp | None = None
    trades: list[dict[str, Any]] = []
    crisis_legs: list[dict[str, Any]] = []
    path_rows: list[dict[str, Any]] = []
    counts = {
        "base_trades": 0,
        "crisis_episodes": 0,
        "crisis_legs": 0,
        "override_base_exits": 0,
        "partial_profit_events": 0,
        "handoff_entries": 0,
    }

    def close_base(hour: int, timestamp: pd.Timestamp, mark: float, reason: str) -> None:
        nonlocal cash, mode, base_asset, base_side, base_quantity, base_entry_fill
        cash, exit_fill = cbct.close_position(
            cash, base_quantity, base_side, base_entry_fill, mark, slippage
        )
        trades.append(
            {
                "mode": "base",
                "entry_ts": base_entry_ts,
                "exit_ts": timestamp,
                "asset": base_asset,
                "side": base_side,
                "entry_price": base_entry_fill,
                "exit_price": exit_fill,
                "entry_equity": base_entry_equity,
                "exit_equity": cash,
                "exit_reason": reason,
                "trade_log_growth": math.log(cash / base_entry_equity),
                "partial_events": list(base_partial_events),
                "entry_source": base_entry_source,
            }
        )
        counts["base_trades"] += 1
        counts["override_base_exits"] += int(reason == "crisis_override")
        mode, base_asset, base_side, base_quantity, base_entry_fill = "flat", "", 0, 0.0, 0.0

    for hour, timestamp in enumerate(hourly.ts):
        timestamp = pd.Timestamp(timestamp)
        terminal = timestamp == data.DEVELOPMENT_END
        just_exited_crisis = False
        desired_crisis = 0
        if timestamp.hour == 0:
            desired_crisis = 0 if terminal else int(crisis[day_index[timestamp]])
            if desired_crisis and mode != "crisis":
                if mode == "base":
                    close_base(hour, timestamp, float(hourly.open[base_asset][hour]), "crisis_override")
                pair_entry_equity, pair_entry_ts = cash, timestamp
                cash, pair_quantities, pair_fills = open_short_basket(cbct, cash, hourly, hour, slippage)
                mode = "crisis"
            elif not desired_crisis and mode == "crisis":
                cash, pair_exits = close_short_basket(
                    cbct, cash, pair_quantities, pair_fills, hourly, hour, slippage
                )
                trade_growth = math.log(cash / pair_entry_equity)
                trades.append(
                    {
                        "mode": "crisis",
                        "entry_ts": pair_entry_ts,
                        "exit_ts": timestamp,
                        "asset": "BTCUSDT+ETHUSDT",
                        "side": -1,
                        "entry_price": None,
                        "exit_price": None,
                        "entry_equity": pair_entry_equity,
                        "exit_equity": cash,
                        "exit_reason": "crisis_state_exit" if not terminal else "terminal",
                        "trade_log_growth": trade_growth,
                    }
                )
                for symbol in cbct.SYMBOLS:
                    crisis_legs.append(
                        {
                            "entry_ts": pair_entry_ts,
                            "exit_ts": timestamp,
                            "asset": symbol,
                            "side": -1,
                            "entry_price": pair_fills[symbol],
                            "exit_price": pair_exits[symbol],
                            "episode_entry_equity": pair_entry_equity,
                            "episode_exit_equity": cash,
                        }
                    )
                counts["crisis_episodes"] += 1
                counts["crisis_legs"] += 2
                mode, pair_quantities, pair_fills = "flat", {}, {}
                just_exited_crisis = True
            if mode == "base" and timestamp in exits and exits[timestamp]["exit_reason"] != "stop":
                trade = exits[timestamp]
                close_base(hour, timestamp, float(trade["exit_mark"]), str(trade["exit_reason"]))
            if mode == "base" and timestamp in partials:
                event = partials[timestamp]
                cash_before, quantity_before = cash, base_quantity
                cash, base_quantity, fill, quantity_closed = cbct.reduce_position(
                    cash,
                    base_quantity,
                    base_side,
                    base_entry_fill,
                    float(event["mark"]),
                    slippage,
                    float(event["fraction"]),
                )
                base_partial_events.append(
                    {
                        "ts": timestamp,
                        "mark": float(event["mark"]),
                        "fill": fill,
                        "fraction": float(event["fraction"]),
                        "quantity_before": quantity_before,
                        "quantity_closed": quantity_closed,
                        "quantity_remaining": base_quantity,
                        "cash_before": cash_before,
                        "cash_after": cash,
                    }
                )
                counts["partial_profit_events"] += 1
            if (
                mode == "flat"
                and not desired_crisis
                and not just_exited_crisis
                and timestamp in entries
                and not terminal
            ):
                trade = entries[timestamp]
                base_asset, base_side = str(trade["asset"]), int(trade["side"])
                base_entry_equity, base_entry_ts = cash, timestamp
                base_partial_events = []
                base_entry_source = str(trade.get("entry_source", "regular"))
                counts["handoff_entries"] += int(base_entry_source == "handoff")
                cash, base_quantity, base_entry_fill = cbct.open_position(
                    cash, base_side, float(trade["entry_mark"]), slippage
                )
                mode = "base"
        if terminal:
            favorable = adverse = close_equity = cash
        else:
            if mode == "base":
                cash -= base_side * base_quantity * float(hourly.unit_funding[base_asset][hour])
                stop_trade = exits.get(timestamp)
                if stop_trade is not None and stop_trade["exit_reason"] == "stop":
                    close_base(hour, timestamp, float(stop_trade["exit_mark"]), "stop")
                    favorable = adverse = close_equity = cash
                else:
                    favorable_mark = hourly.high[base_asset][hour] if base_side > 0 else hourly.low[base_asset][hour]
                    adverse_mark = hourly.low[base_asset][hour] if base_side > 0 else hourly.high[base_asset][hour]
                    favorable = cash + base_side * base_quantity * (float(favorable_mark) - base_entry_fill)
                    adverse = cash + base_side * base_quantity * (float(adverse_mark) - base_entry_fill)
                    close_equity = cash + base_side * base_quantity * (
                        float(hourly.close[base_asset][hour]) - base_entry_fill
                    )
            elif mode == "crisis":
                for symbol in cbct.SYMBOLS:
                    cash += pair_quantities[symbol] * float(hourly.unit_funding[symbol][hour])
                favorable = cash + sum(
                    -pair_quantities[symbol] * (float(hourly.low[symbol][hour]) - pair_fills[symbol])
                    for symbol in cbct.SYMBOLS
                )
                adverse = cash + sum(
                    -pair_quantities[symbol] * (float(hourly.high[symbol][hour]) - pair_fills[symbol])
                    for symbol in cbct.SYMBOLS
                )
                close_equity = cash + sum(
                    -pair_quantities[symbol] * (float(hourly.close[symbol][hour]) - pair_fills[symbol])
                    for symbol in cbct.SYMBOLS
                )
            else:
                favorable = adverse = close_equity = cash
        peak = max(peak, favorable)
        worst = min(worst, adverse / peak - 1.0)
        peak = max(peak, close_equity)
        worst = min(worst, close_equity / peak - 1.0)
        if retain:
            path_rows.append(
                {
                    "ts": timestamp,
                    "equity": float(close_equity),
                    "favorable_equity": float(favorable),
                    "adverse_equity": float(adverse),
                    "mode": mode,
                    "crisis_state": desired_crisis if timestamp.hour == 0 else None,
                }
            )
        if terminal:
            break
    return RouterResult(float(cash), float(worst * 100.0), pd.DataFrame(path_rows), trades, crisis_legs, counts)


def calendar_ratio(path: pd.DataFrame) -> float:
    equity = pd.Series(path["equity"].to_numpy(float), index=pd.DatetimeIndex(path["ts"]))
    values = []
    for year in range(2020, 2025):
        prior = equity.loc[equity.index < pd.Timestamp(f"{year}-01-01", tz="UTC")]
        current = equity.loc[(equity.index >= pd.Timestamp(f"{year}-01-01", tz="UTC")) & (equity.index < pd.Timestamp(f"{year + 1}-01-01", tz="UTC"))]
        if not prior.empty and not current.empty:
            values.append(current.iloc[-1] / prior.iloc[-1] - 1.0)
    return float(np.mean(np.asarray(values) > 0.0)) if values else 0.0


def rolling_ratio(path: pd.DataFrame) -> float:
    equity = pd.Series(path["equity"].to_numpy(float), index=pd.DatetimeIndex(path["ts"]))
    values = (equity / equity.shift(24 * 365) - 1.0).dropna()
    return float((values > 0.0).mean()) if not values.empty else 0.0


def concentration(trades: list[dict[str, Any]]) -> float:
    positive = [max(0.0, float(trade["trade_log_growth"])) for trade in trades]
    return max(positive, default=0.0) / sum(positive) if sum(positive) > 0 else 1.0


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Frozen P0 research for BIN-1D-BE-COST.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 12 and len(set(grid)) == 12
        print("self-test: PASS")
        return
    cbct = load_cbct()
    data = cbct.load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    daily, hourly, daily_frame = cbct.prepare_markets(data, hourly_source, funding)
    shadows = {
        "base": shadow_replay(cbct, data, daily, hourly, daily_frame, slippage=cbct.BASE_SLIPPAGE, delay_days=0),
        "stress": shadow_replay(cbct, data, daily, hourly, daily_frame, slippage=cbct.STRESS_SLIPPAGE, delay_days=0),
        "delay": shadow_replay(cbct, data, daily, hourly, daily_frame, slippage=cbct.BASE_SLIPPAGE, delay_days=1),
    }
    neutral = np.zeros(len(daily.ts), dtype=np.int8)
    control = route_replay(
        cbct, data, daily, hourly, daily_frame, shadows["base"], neutral,
        slippage=cbct.BASE_SLIPPAGE, retain=False
    )
    if not math.isclose(control.equity_multiple, EXPECTED_CONTROL[0], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"control terminal parity failed: {control.equity_multiple}")
    if not math.isclose(control.ordered_mdd_pct, EXPECTED_CONTROL[1], rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"control MDD parity failed: {control.ordered_mdd_pct}")
    rows, retained = [], {}
    for config in grid:
        mode_results = {}
        for mode, (slippage, delay) in {
            "base": (cbct.BASE_SLIPPAGE, 0),
            "stress": (cbct.STRESS_SLIPPAGE, 0),
            "delay": (cbct.BASE_SLIPPAGE, 1),
        }.items():
            mode_results[mode] = route_replay(
                cbct,
                data,
                daily,
                hourly,
                daily_frame,
                shadows[mode],
                crisis_execution(daily_frame, config, delay),
                slippage=slippage,
                retain=mode == "base",
            )
        base, stress, delay = mode_results["base"], mode_results["stress"], mode_results["delay"]
        base_log = math.log(base.equity_multiple) if base.equity_multiple > 0 else -math.inf
        stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 and base_log > 0 else -math.inf
        delay_retention = math.log(delay.equity_multiple) / base_log if delay.equity_multiple > 0 and base_log > 0 else -math.inf
        hard_base = base.equity_multiple >= 20.0 and base.ordered_mdd_pct >= -20.0
        gates = {
            "stress": stress.equity_multiple >= 16.0 and stress.ordered_mdd_pct >= -22.0,
            "delay": delay.equity_multiple >= 8.0 and delay.ordered_mdd_pct >= -25.0 and delay_retention >= 0.70,
            "calendar": calendar_ratio(base.path) >= 0.70,
            "rolling": rolling_ratio(base.path) >= 0.70,
            "capacity": len(base.trades) >= 20 and base.counts["crisis_episodes"] >= 2,
            "concentration": concentration(base.trades) <= 0.30,
        }
        rows.append(
            {
                **asdict(config),
                "equity_multiple": base.equity_multiple,
                "ordered_mdd_pct": base.ordered_mdd_pct,
                **base.counts,
                "trades": len(base.trades),
                "complete_year_positive_ratio": calendar_ratio(base.path),
                "rolling_365d_positive_ratio": rolling_ratio(base.path),
                "max_trade_positive_log_share": concentration(base.trades),
                "hard_base_pass": hard_base,
                "stress_equity_multiple": stress.equity_multiple,
                "stress_ordered_mdd_pct": stress.ordered_mdd_pct,
                "stress_log_growth_retention": stress_retention,
                "delay_equity_multiple": delay.equity_multiple,
                "delay_ordered_mdd_pct": delay.ordered_mdd_pct,
                "delay_log_growth_retention": delay_retention,
                **{f"gate_{key}": value for key, value in gates.items()},
                "all_gates_pass": hard_base and all(gates.values()),
            }
        )
        retained[config] = base
    frame = pd.DataFrame(rows)
    best_growth = frame.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    passing = frame.loc[frame["all_gates_pass"]].sort_values(
        ["ordered_mdd_pct", "stress_log_growth_retention", "equity_multiple", "trades", "crisis_ema", "slope_days", "confirm_days"],
        ascending=[False, False, False, True, True, True, True],
    )
    selected = passing.iloc[0].to_dict() if not passing.empty else None
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": "Binance-1D-BTCETH-Crisis-Override-Shadow-Trend",
        "campaign": "P0 frozen development search",
        "status": "development candidate; audit sealed" if selected else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read",
        "data_quality": quality,
        "control_parity": {"equity_multiple": control.equity_multiple, "ordered_mdd_pct": control.ordered_mdd_pct},
        "counts": {
            "configs": len(frame),
            "hard_base_pass": int(frame["hard_base_pass"].sum()),
            "all_gates_pass": int(frame["all_gates_pass"].sum()),
        },
        "best_growth": best_growth,
        "best_risk": best_risk,
        "unique_candidate": selected,
        "audit_revealed": False,
        "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_cost_p0_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    path_rows, trade_rows, leg_rows = [], [], []
    keys = tuple(asdict(grid[0]))
    for frontier, row in (("growth_frontier", best_growth), ("risk_frontier", best_risk)):
        config = Config(**{key: row[key] for key in keys})
        result = retained[config]
        path_rows.extend({"frontier": frontier, **item} for item in result.path.to_dict("records"))
        trade_rows.extend({"frontier": frontier, **item} for item in result.trades)
        leg_rows.extend({"frontier": frontier, **item} for item in result.crisis_legs)
    pd.DataFrame(path_rows).to_csv(ARTIFACT_DIR / f"{stem}_paths.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(ARTIFACT_DIR / f"{stem}_trades.csv", index=False)
    pd.DataFrame(leg_rows).to_csv(ARTIFACT_DIR / f"{stem}_crisis_legs.csv", index=False)
    print(json.dumps(clean(payload["counts"]), ensure_ascii=False))
    print(json.dumps(clean(best_growth), ensure_ascii=False))
    print(json.dumps(clean(best_risk), ensure_ascii=False))
    print(json.dumps(clean(selected), ensure_ascii=False))


if __name__ == "__main__":
    main()
