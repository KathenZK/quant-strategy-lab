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
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-btceth-cross-impulse-lead-lag"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATA_HELPER_PATH = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p0.py"
DATA_HELPER_SHA256 = "8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29"
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
SYMBOLS = ("BTCUSDT", "ETHUSDT")


@dataclass(frozen=True, order=True)
class Config:
    vol_h: int
    impulse_z: float
    gap_z: float
    follower_cap_z: float
    catchup_fraction: float
    max_hold_hours: int
    stop_sigma: float
    cooldown_hours: int


@dataclass
class SignalBook:
    follower: np.ndarray
    side: np.ndarray
    leader: np.ndarray
    leader_return_abs: np.ndarray
    follower_vol: np.ndarray


@dataclass
class Market:
    ts: pd.DatetimeIndex
    open: dict[str, np.ndarray]
    high: dict[str, np.ndarray]
    low: dict[str, np.ndarray]
    close: dict[str, np.ndarray]
    unit_funding: dict[str, np.ndarray]


@dataclass
class Result:
    equity_multiple: float
    max_drawdown_pct: float
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    counts: dict[str, int]
    trade_path_sha256: str


def load_data_helper() -> Any:
    digest = hashlib.sha256(DATA_HELPER_PATH.read_bytes()).hexdigest()
    if digest != DATA_HELPER_SHA256:
        raise RuntimeError(f"data helper drift: {digest}")
    spec = importlib.util.spec_from_file_location("binance_1h_be_cill_data", DATA_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {DATA_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configs() -> list[Config]:
    return [Config(*values) for values in itertools.product(
        (24, 72, 168), (2.0, 3.0, 4.0), (0.5, 1.0), (0.5, 1.0),
        (0.0, 0.5, 1.0), (3, 6, 12, 24, 48), (0.0, 2.0), (0, 6),
    )]


def prepare_market(data: Any, hourly: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]) -> tuple[Market, pd.DataFrame]:
    union = data.build_hourly_union(hourly, funding)
    market = Market(
        ts=pd.DatetimeIndex(union["ts"]),
        open={symbol: union[f"{symbol}_open"].to_numpy(float) for symbol in SYMBOLS},
        high={symbol: union[f"{symbol}_high"].to_numpy(float) for symbol in SYMBOLS},
        low={symbol: union[f"{symbol}_low"].to_numpy(float) for symbol in SYMBOLS},
        close={symbol: union[f"{symbol}_close"].to_numpy(float) for symbol in SYMBOLS},
        unit_funding={symbol: union[f"{symbol}_unit_funding"].to_numpy(float) for symbol in SYMBOLS},
    )
    full = hourly["BTCUSDT"][["ts", "close"]].rename(columns={"close": "BTCUSDT"}).merge(
        hourly["ETHUSDT"][["ts", "close"]].rename(columns={"close": "ETHUSDT"}),
        on="ts", how="inner", validate="one_to_one",
    ).sort_values("ts")
    return market, full


def build_signal_book(full: pd.DataFrame, market: Market, config: Config) -> SignalBook:
    feature = full.copy().set_index("ts")
    for symbol in SYMBOLS:
        returns = np.log(feature[symbol].astype(float)).diff()
        volatility = returns.shift(1).rolling(config.vol_h, min_periods=config.vol_h).std(ddof=1)
        feature[f"{symbol}_return"] = returns
        feature[f"{symbol}_vol"] = volatility
        feature[f"{symbol}_z"] = returns / volatility.replace(0.0, np.nan)
    aligned = feature.reindex(market.ts)
    btc_z, eth_z = aligned["BTCUSDT_z"].to_numpy(float), aligned["ETHUSDT_z"].to_numpy(float)
    btc_r, eth_r = aligned["BTCUSDT_return"].to_numpy(float), aligned["ETHUSDT_return"].to_numpy(float)
    btc_v, eth_v = aligned["BTCUSDT_vol"].to_numpy(float), aligned["ETHUSDT_vol"].to_numpy(float)
    btc_leads = np.abs(btc_z) > np.abs(eth_z)
    leader_z = np.where(btc_leads, btc_z, eth_z)
    follower_z = np.where(btc_leads, eth_z, btc_z)
    leader_return = np.where(btc_leads, btc_r, eth_r)
    side = np.where(np.isfinite(leader_return), np.sign(leader_return), 0).astype(np.int8)
    valid = (
        np.isfinite(leader_z) & np.isfinite(follower_z) & np.isfinite(leader_return)
        & (side != 0) & (np.abs(leader_z) >= config.impulse_z)
        & ((np.abs(leader_z) - np.abs(follower_z)) >= config.gap_z)
        & ((side * follower_z) <= config.follower_cap_z)
    )
    follower = np.where(valid, np.where(btc_leads, 2, 1), 0).astype(np.int8)
    leader = np.where(valid, np.where(btc_leads, 1, 2), 0).astype(np.int8)
    side = np.where(valid, side, 0).astype(np.int8)
    return SignalBook(
        follower=follower,
        side=side,
        leader=leader,
        leader_return_abs=np.where(valid, np.abs(leader_return), np.nan),
        follower_vol=np.where(valid, np.where(btc_leads, eth_v, btc_v), np.nan),
    )


def fill_price(mark: float, side: int, slippage: float, *, entry: bool) -> float:
    return mark * (1.0 + (side if entry else -side) * slippage)


def open_position(equity: float, side: int, mark: float, slippage: float) -> tuple[float, float, float]:
    fill = fill_price(mark, side, slippage, entry=True)
    quantity = equity / (fill * (1.0 + FEE))
    cash = equity - quantity * fill * FEE
    return float(cash), float(quantity), float(fill)


def close_position(cash: float, quantity: float, side: int, entry_fill: float, mark: float, slippage: float) -> tuple[float, float]:
    fill = fill_price(mark, side, slippage, entry=False)
    cash += side * quantity * (fill - entry_fill)
    cash -= quantity * fill * FEE
    return float(cash), float(fill)


def simulate(market: Market, signals: SignalBook, config: Config, *, slippage: float, delay_hours: int = 0, retain: bool = False) -> Result:
    signal_indices = np.flatnonzero(signals.follower)
    terminal = len(market.ts) - 1
    cash, peak, max_drawdown = 1.0, 1.0, 0.0
    trades: list[dict[str, Any]] = []
    path_values = np.full(len(market.ts), np.nan) if retain else None
    counts = {"trades": 0, "long": 0, "short": 0, "BTCUSDT_follower": 0, "ETHUSDT_follower": 0, "BTCUSDT_leader": 0, "ETHUSDT_leader": 0}
    minimum_signal = 0
    flat_cursor = 0
    identities = []
    while True:
        position = int(np.searchsorted(signal_indices, minimum_signal, side="left"))
        if position >= len(signal_indices):
            break
        signal_index = int(signal_indices[position])
        entry_index = signal_index + 1 + delay_hours
        if entry_index >= terminal:
            break
        if retain and path_values is not None:
            path_values[flat_cursor:entry_index] = cash
        follower = SYMBOLS[int(signals.follower[signal_index]) - 1]
        leader = SYMBOLS[int(signals.leader[signal_index]) - 1]
        side = int(signals.side[signal_index])
        entry_mark = float(market.open[follower][entry_index])
        entry_equity = cash
        cash, quantity, entry_fill = open_position(cash, side, entry_mark, slippage)
        target_return = config.catchup_fraction * float(signals.leader_return_abs[signal_index])
        stop_return = config.stop_sigma * float(signals.follower_vol[signal_index]) * math.sqrt(config.max_hold_hours)
        planned_exit: int | None = None
        exit_reason = "terminal"
        held_hours = 0
        hour = entry_index
        while hour < terminal:
            cash -= side * quantity * float(market.unit_funding[follower][hour])
            favorable = market.high[follower][hour] if side > 0 else market.low[follower][hour]
            adverse = market.low[follower][hour] if side > 0 else market.high[follower][hour]
            favorable_equity = cash + side * quantity * (favorable - entry_fill)
            peak = max(peak, favorable_equity)
            adverse_equity = cash + side * quantity * (adverse - entry_fill)
            max_drawdown = min(max_drawdown, adverse_equity / peak - 1.0)
            close_equity = cash + side * quantity * (market.close[follower][hour] - entry_fill)
            peak = max(peak, close_equity)
            max_drawdown = min(max_drawdown, close_equity / peak - 1.0)
            if retain and path_values is not None:
                path_values[hour] = close_equity
            held_hours += 1
            if planned_exit is None:
                follower_return = side * math.log(float(market.close[follower][hour]) / entry_mark)
                if config.catchup_fraction > 0 and follower_return >= target_return:
                    planned_exit, exit_reason = hour + 1 + delay_hours, "catchup"
                elif config.stop_sigma > 0 and follower_return <= -stop_return:
                    planned_exit, exit_reason = hour + 1 + delay_hours, "stop"
                elif held_hours >= config.max_hold_hours:
                    planned_exit, exit_reason = hour + 1 + delay_hours, "timeout"
            hour += 1
            if planned_exit is not None and hour >= planned_exit:
                break
        exit_index = min(hour, terminal)
        if exit_index == terminal and (planned_exit is None or planned_exit > terminal):
            exit_reason = "terminal"
        cash, exit_fill = close_position(cash, quantity, side, entry_fill, float(market.open[follower][exit_index]), slippage)
        peak = max(peak, cash)
        max_drawdown = min(max_drawdown, cash / peak - 1.0)
        if retain and path_values is not None:
            path_values[exit_index] = cash
        trade_log_growth = math.log(cash / entry_equity) if cash > 0 and entry_equity > 0 else None
        trades.append({
            "signal_ts": market.ts[signal_index], "entry_ts": market.ts[entry_index], "exit_ts": market.ts[exit_index],
            "leader": leader, "follower": follower, "side": side, "entry_mark": entry_mark,
            "entry_fill": entry_fill, "exit_fill": exit_fill, "entry_equity": entry_equity, "exit_equity": cash,
            "held_hours": held_hours, "exit_reason": exit_reason, "trade_log_growth": trade_log_growth,
        })
        identities.append((signal_index, entry_index, exit_index, leader, follower, side, exit_reason))
        counts["trades"] += 1
        counts["long" if side > 0 else "short"] += 1
        counts[f"{follower}_follower"] += 1
        counts[f"{leader}_leader"] += 1
        flat_cursor = exit_index
        minimum_signal = exit_index + config.cooldown_hours
        if exit_index >= terminal:
            break
    if retain and path_values is not None:
        path_values[flat_cursor:] = np.where(np.isnan(path_values[flat_cursor:]), cash, path_values[flat_cursor:])
        path = [{"ts": ts, "equity": float(equity)} for ts, equity in zip(market.ts, path_values, strict=True)]
    else:
        path = []
    path_hash = hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()
    return Result(float(cash), float(max_drawdown * 100.0), trades if retain else [], path, counts, path_hash)


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
    shifted = equity.shift(24 * 365)
    values = (equity / shifted - 1.0).dropna()
    return float((values > 0.0).mean()) if not values.empty else 0.0


def concentration(trades: list[dict[str, Any]]) -> float:
    values = [max(0.0, float(trade["trade_log_growth"])) for trade in trades if trade["trade_log_growth"] is not None]
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
    parser = argparse.ArgumentParser(description="Frozen P0 search for BIN-1H-BE-CILL.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 2160
        print("self-test: PASS")
        return
    data = load_data_helper()
    hourly, funding, quality = data.load_frozen_data()
    market, full = prepare_market(data, hourly, funding)
    signal_books = {}
    for vol_h, impulse_z, gap_z, cap_z in sorted({(c.vol_h, c.impulse_z, c.gap_z, c.follower_cap_z) for c in grid}):
        key = (vol_h, impulse_z, gap_z, cap_z)
        signal_books[key] = build_signal_book(full, market, Config(vol_h, impulse_z, gap_z, cap_z, 0.0, 3, 0.0, 0))
    rows, passing_base = [], []
    for config in grid:
        signals = signal_books[(config.vol_h, config.impulse_z, config.gap_z, config.follower_cap_z)]
        result = simulate(market, signals, config, slippage=BASE_SLIPPAGE)
        base_pass = result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0
        row = {**asdict(config), "equity_multiple": result.equity_multiple, "ordered_mdd_pct": result.max_drawdown_pct, **result.counts, "trade_path_sha256": result.trade_path_sha256, "base_screen_pass": base_pass, "all_gates_pass": False}
        rows.append(row)
        if base_pass:
            passing_base.append((config, signals))
    details, retained, seen = [], {}, set()
    for config, signals in sorted(passing_base):
        base = simulate(market, signals, config, slippage=BASE_SLIPPAGE, retain=True)
        if base.trade_path_sha256 in seen:
            continue
        seen.add(base.trade_path_sha256)
        stress = simulate(market, signals, config, slippage=STRESS_SLIPPAGE)
        delayed = simulate(market, signals, config, slippage=BASE_SLIPPAGE, delay_hours=1)
        base_log = math.log(base.equity_multiple)
        stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 else -math.inf
        delay_retention = math.log(delayed.equity_multiple) / base_log if delayed.equity_multiple > 0 else -math.inf
        capacity = base.counts["trades"] >= 40 and all(base.counts[key] >= 10 for key in ("long", "short", "BTCUSDT_follower", "ETHUSDT_follower", "BTCUSDT_leader", "ETHUSDT_leader"))
        gates = {
            "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
            "delay": delay_retention >= 0.70 and delayed.equity_multiple >= 8.0 and delayed.max_drawdown_pct >= -25.0,
            "calendar": complete_year_ratio(base.path) >= 0.70,
            "rolling": rolling_ratio(base.path) >= 0.70,
            "capacity": capacity, "concentration": concentration(base.trades) <= 0.25,
        }
        detail = {**asdict(config), "base_equity_multiple": base.equity_multiple, "base_ordered_mdd_pct": base.max_drawdown_pct, **base.counts, "trade_path_sha256": base.trade_path_sha256, "stress_equity_multiple": stress.equity_multiple, "stress_ordered_mdd_pct": stress.max_drawdown_pct, "stress_log_growth_retention": stress_retention, "delay_equity_multiple": delayed.equity_multiple, "delay_ordered_mdd_pct": delayed.max_drawdown_pct, "delay_log_growth_retention": delay_retention, "complete_year_positive_ratio": complete_year_ratio(base.path), "rolling_365d_positive_ratio": rolling_ratio(base.path), "max_trade_positive_log_share": concentration(base.trades), **{f"gate_{k}": v for k, v in gates.items()}, "all_gates_pass": all(gates.values())}
        details.append(detail)
        retained[config] = base
    frame, detail_frame = pd.DataFrame(rows), pd.DataFrame(details)
    passing = detail_frame.loc[detail_frame["all_gates_pass"]].copy() if not detail_frame.empty else detail_frame
    if not passing.empty:
        passing = passing.sort_values(["base_ordered_mdd_pct", "stress_log_growth_retention", "base_equity_multiple", "trades", "vol_h", "impulse_z", "gap_z", "follower_cap_z", "catchup_fraction", "max_hold_hours", "stop_sigma", "cooldown_hours"], ascending=[False, False, False, True, True, True, True, True, True, True, True, True])
    unique = passing.iloc[0].to_dict() if not passing.empty else None
    best_growth = frame.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1H-BTCETH-Cross-Impulse-Lead-Lag", "campaign": "P0 frozen development search",
        "status": "development candidate; audit sealed" if unique else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read", "data_quality": quality,
        "contract": {"configs": len(grid), "fee_per_fill": FEE, "base_slippage": BASE_SLIPPAGE, "stress_slippage": STRESS_SLIPPAGE, "initial_leverage": 1.0},
        "counts": {"configs": len(frame), "base_screen_pass": int(frame["base_screen_pass"].sum()), "unique_base_paths": len(detail_frame), "all_gates_pass": int(detail_frame["all_gates_pass"].sum()) if not detail_frame.empty else 0},
        "best_growth": best_growth, "best_risk": best_risk, "unique_candidate": unique, "audit_revealed": False, "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1h_be_cill_p0_search_{args.run_date}"
    (ARTIFACT_DIR / f"{stem}.json").write_text(json.dumps(clean(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    frame.to_csv(ARTIFACT_DIR / f"{stem}_grid.csv", index=False)
    detail_frame.to_csv(ARTIFACT_DIR / f"{stem}_candidates.csv", index=False)
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
