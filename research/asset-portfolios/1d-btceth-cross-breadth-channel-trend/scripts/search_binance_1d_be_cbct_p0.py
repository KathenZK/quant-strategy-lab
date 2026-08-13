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
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATA_HELPER_PATH = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p0.py"
DATA_HELPER_SHA256 = "8fe4f043a3fdffb6aa74ec0860d51d13ec8539442fe28641233e30c8567c8d29"
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
SYMBOLS = ("BTCUSDT", "ETHUSDT")
CODE_TO_ASSET = {1: "BTCUSDT", -1: "BTCUSDT", 2: "ETHUSDT", -2: "ETHUSDT"}


@dataclass(frozen=True, order=True)
class Config:
    entry_n: int
    exit_n: int
    breadth_ema: int
    trail_atr: float
    confirm_days: int
    cooldown_days: int
    max_hold_days: int


@dataclass(frozen=True, order=True)
class ProfitProtection:
    activation_atr: float
    giveback: float
    confirm_days: int


@dataclass(frozen=True, order=True)
class PartialProtection:
    activation_atr: float
    giveback: float
    confirm_days: int
    fraction: float


@dataclass(frozen=True, order=True)
class Handoff:
    window_days: int
    confirm_days: int


@dataclass
class EntryBook:
    code: np.ndarray
    score: np.ndarray


@dataclass
class DailyMarket:
    ts: pd.DatetimeIndex
    open: dict[str, np.ndarray]
    high: dict[str, np.ndarray]
    low: dict[str, np.ndarray]
    close: dict[str, np.ndarray]
    atr14: dict[str, np.ndarray]


@dataclass
class HourlyMarket:
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
    spec = importlib.util.spec_from_file_location("binance_1d_be_cbct_data", DATA_HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {DATA_HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configs() -> list[Config]:
    return [
        Config(*values)
        for values in itertools.product(
            (20, 40, 60, 90),
            (5, 10, 20, 40),
            (20, 50, 100),
            (2.0, 3.0, 4.0, 5.0),
            (1, 2, 3),
            (0, 3, 7),
            (0, 120),
        )
        if values[1] < values[0]
    ]


def atr14(frame: pd.DataFrame, symbol: str) -> np.ndarray:
    high, low, close = frame[f"{symbol}_high"], frame[f"{symbol}_low"], frame[f"{symbol}_close"]
    previous = close.shift(1)
    true_range = pd.concat([high - low, (high - previous).abs(), (low - previous).abs()], axis=1).max(axis=1)
    return true_range.rolling(14, min_periods=14).mean().to_numpy(float)


def prepare_markets(data: Any, hourly: dict[str, pd.DataFrame], funding: dict[str, pd.DataFrame]) -> tuple[DailyMarket, HourlyMarket, pd.DataFrame]:
    daily_frame = data.build_daily(hourly, funding)
    union = data.build_hourly_union(hourly, funding)
    daily = DailyMarket(
        ts=pd.DatetimeIndex(daily_frame["ts"]),
        open={symbol: daily_frame[f"{symbol}_open"].to_numpy(float) for symbol in SYMBOLS},
        high={symbol: daily_frame[f"{symbol}_high"].to_numpy(float) for symbol in SYMBOLS},
        low={symbol: daily_frame[f"{symbol}_low"].to_numpy(float) for symbol in SYMBOLS},
        close={symbol: daily_frame[f"{symbol}_close"].to_numpy(float) for symbol in SYMBOLS},
        atr14={symbol: atr14(daily_frame, symbol) for symbol in SYMBOLS},
    )
    hourly_market = HourlyMarket(
        ts=pd.DatetimeIndex(union["ts"]),
        open={symbol: union[f"{symbol}_open"].to_numpy(float) for symbol in SYMBOLS},
        high={symbol: union[f"{symbol}_high"].to_numpy(float) for symbol in SYMBOLS},
        low={symbol: union[f"{symbol}_low"].to_numpy(float) for symbol in SYMBOLS},
        close={symbol: union[f"{symbol}_close"].to_numpy(float) for symbol in SYMBOLS},
        unit_funding={symbol: union[f"{symbol}_unit_funding"].to_numpy(float) for symbol in SYMBOLS},
    )
    return daily, hourly_market, daily_frame


def confirm_codes(raw: np.ndarray, days: int) -> np.ndarray:
    output = np.zeros(len(raw), dtype=np.int8)
    candidate, streak = 0, 0
    for index, value in enumerate(raw):
        code = int(value)
        if code and code == candidate:
            streak += 1
        elif code:
            candidate, streak = code, 1
        else:
            candidate, streak = 0, 0
        if streak >= days:
            output[index] = candidate
    return output


def find_handoff_signal(
    close: np.ndarray,
    side: int,
    level: float,
    start_day: int,
    end_day: int,
    window_days: int,
    confirm_days: int,
) -> int | None:
    streak = 0
    for day in range(start_day, min(end_day, start_day + window_days)):
        continued = close[day] > level if side > 0 else close[day] < level
        streak = streak + 1 if continued else 0
        if streak >= confirm_days:
            return day
    return None


def build_entry_book(daily_frame: pd.DataFrame, daily: DailyMarket, entry_n: int, breadth_ema: int, confirm_days: int) -> EntryBook:
    raw = np.zeros(len(daily.ts), dtype=np.int8)
    selected_score = np.full(len(daily.ts), np.nan)
    candidates: dict[int, np.ndarray] = {}
    scores: dict[int, np.ndarray] = {}
    ema = {
        symbol: daily_frame[f"{symbol}_close"].ewm(span=breadth_ema, adjust=False, min_periods=breadth_ema).mean().to_numpy(float)
        for symbol in SYMBOLS
    }
    for asset_index, symbol in enumerate(SYMBOLS, start=1):
        peer = SYMBOLS[1] if symbol == SYMBOLS[0] else SYMBOLS[0]
        prior_high = daily_frame[f"{symbol}_high"].shift(1).rolling(entry_n, min_periods=entry_n).max().to_numpy(float)
        prior_low = daily_frame[f"{symbol}_low"].shift(1).rolling(entry_n, min_periods=entry_n).min().to_numpy(float)
        long_score = (daily.close[symbol] - prior_high) / daily.atr14[symbol]
        short_score = (prior_low - daily.close[symbol]) / daily.atr14[symbol]
        long_ok = (long_score > 0) & (daily.close[symbol] > ema[symbol]) & (daily.close[peer] > ema[peer])
        short_ok = (short_score > 0) & (daily.close[symbol] < ema[symbol]) & (daily.close[peer] < ema[peer])
        code = np.where(long_ok, asset_index, np.where(short_ok, -asset_index, 0)).astype(np.int8)
        score = np.where(long_ok, long_score, np.where(short_ok, short_score, np.nan))
        candidates[asset_index] = code
        scores[asset_index] = score
    for index in range(len(raw)):
        options = [(scores[asset][index], int(candidates[asset][index]), asset) for asset in (1, 2) if candidates[asset][index] != 0 and np.isfinite(scores[asset][index])]
        if options:
            options.sort(key=lambda item: (-item[0], item[2]))
            selected_score[index], raw[index] = options[0][0], options[0][1]
    return EntryBook(confirm_codes(raw, confirm_days), selected_score)


def exit_channels(daily_frame: pd.DataFrame, exit_n: int) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    prior_low = {symbol: daily_frame[f"{symbol}_low"].shift(1).rolling(exit_n, min_periods=exit_n).min().to_numpy(float) for symbol in SYMBOLS}
    prior_high = {symbol: daily_frame[f"{symbol}_high"].shift(1).rolling(exit_n, min_periods=exit_n).max().to_numpy(float) for symbol in SYMBOLS}
    return prior_low, prior_high


def fill_price(mark: float, side: int, slippage: float, *, entry: bool) -> float:
    return mark * (1.0 + (side if entry else -side) * slippage)


def open_position(equity: float, side: int, mark: float, slippage: float) -> tuple[float, float, float]:
    fill = fill_price(mark, side, slippage, entry=True)
    quantity = equity / (fill * (1.0 + FEE))
    return float(equity - quantity * fill * FEE), float(quantity), float(fill)


def close_position(cash: float, quantity: float, side: int, entry_fill: float, mark: float, slippage: float) -> tuple[float, float]:
    fill = fill_price(mark, side, slippage, entry=False)
    cash += side * quantity * (fill - entry_fill)
    cash -= quantity * fill * FEE
    return float(cash), float(fill)


def reduce_position(
    cash: float,
    quantity: float,
    side: int,
    entry_fill: float,
    mark: float,
    slippage: float,
    fraction: float,
) -> tuple[float, float, float, float]:
    fill = fill_price(mark, side, slippage, entry=False)
    closed = quantity * fraction
    cash += side * closed * (fill - entry_fill)
    cash -= closed * fill * FEE
    return float(cash), float(quantity - closed), float(fill), float(closed)


def simulate(
    data: Any,
    daily: DailyMarket,
    hourly: HourlyMarket,
    book: EntryBook,
    channels: tuple[dict[str, np.ndarray], dict[str, np.ndarray]],
    config: Config,
    *,
    slippage: float,
    delay_days: int = 0,
    retain: bool = False,
    profit_protection: ProfitProtection | None = None,
    campaign_state: np.ndarray | None = None,
    partial_protection: PartialProtection | None = None,
    handoff: Handoff | None = None,
) -> Result:
    start_day = int(daily.ts.searchsorted(data.COMMON_START))
    end_day = int(daily.ts.searchsorted(data.DEVELOPMENT_END))
    day_to_hour = {timestamp: index for index, timestamp in enumerate(hourly.ts) if timestamp.hour == 0}
    signal_indices = np.flatnonzero(book.code)
    cash, peak, max_drawdown = 1.0, 1.0, 0.0
    counts = {"trades": 0, "long": 0, "short": 0, "BTCUSDT": 0, "ETHUSDT": 0, "channel_exit": 0, "stop_exit": 0, "timeout_exit": 0, "terminal_exit": 0}
    if profit_protection is not None:
        counts["profit_protection_exit"] = 0
    if campaign_state is not None:
        counts["regime_exit"] = 0
    if partial_protection is not None:
        counts["partial_profit_events"] = 0
    if handoff is not None:
        counts["handoff_entries"] = 0
        counts["handoff_armed"] = 0
        counts["handoff_expired"] = 0
        counts["handoff_regular_preemptions"] = 0
    trades: list[dict[str, Any]] = []
    path_values = np.full(len(hourly.ts), np.nan) if retain else None
    favorable_values = np.full(len(hourly.ts), np.nan) if retain else None
    adverse_values = np.full(len(hourly.ts), np.nan) if retain else None
    identities = []
    flat_hour_cursor = 0
    minimum_signal_day = start_day - 1
    armed_handoff: dict[str, Any] | None = None
    prior_low, prior_high = channels
    while True:
        position = int(np.searchsorted(signal_indices, minimum_signal_day, side="left"))
        regular_signal_day = int(signal_indices[position]) if position < len(signal_indices) else None
        handoff_signal_day = None
        if handoff is not None and armed_handoff is not None:
            handoff_signal_day = find_handoff_signal(
                daily.close[armed_handoff["asset"]],
                armed_handoff["side"],
                armed_handoff["level"],
                armed_handoff["start_day"],
                end_day,
                handoff.window_days,
                handoff.confirm_days,
            )
        candidates = []
        if regular_signal_day is not None:
            candidates.append((regular_signal_day + 1 + delay_days, 1, "regular", regular_signal_day))
        if handoff_signal_day is not None:
            candidates.append((handoff_signal_day + 1 + delay_days, 0, "handoff", handoff_signal_day))
        if not candidates:
            if handoff is not None and armed_handoff is not None:
                counts["handoff_expired"] += 1
            break
        entry_day, _, entry_source, signal_day = min(candidates)
        if entry_day >= end_day:
            break
        entry_hour = day_to_hour[daily.ts[entry_day]]
        if retain and path_values is not None:
            path_values[flat_hour_cursor:entry_hour] = cash
            favorable_values[flat_hour_cursor:entry_hour] = cash
            adverse_values[flat_hour_cursor:entry_hour] = cash
        if entry_source == "handoff":
            asset = str(armed_handoff["asset"])
            side = int(armed_handoff["side"])
            asset_code = 1 if asset == "BTCUSDT" else 2
            code = asset_code if side > 0 else -asset_code
            counts["handoff_entries"] += 1
        else:
            if handoff is not None and armed_handoff is not None:
                if handoff_signal_day is None:
                    counts["handoff_expired"] += 1
                else:
                    counts["handoff_regular_preemptions"] += 1
            code = int(book.code[signal_day])
        asset, side = CODE_TO_ASSET[code], 1 if code > 0 else -1
        armed_handoff = None
        entry_mark = float(daily.open[asset][entry_day])
        entry_equity = cash
        cash, quantity, entry_fill = open_position(cash, side, entry_mark, slippage)
        entry_ts = daily.ts[entry_day]
        entry_atr = float(daily.atr14[asset][entry_day])
        active_stop: float | None = None
        extreme = -math.inf if side > 0 else math.inf
        profit_streak = 0
        partial_streak = 0
        partial_done = False
        partial_events: list[dict[str, Any]] = []
        pending_exit_day: int | None = None
        pending_partial_day: int | None = None
        exit_reason = "terminal"
        exit_hour = day_to_hour[data.DEVELOPMENT_END]
        exit_mark = float(hourly.open[asset][exit_hour])
        day = entry_day
        stopped = False
        while day < end_day:
            day_start = day_to_hour[daily.ts[day]]
            if pending_exit_day is not None and day >= pending_exit_day:
                exit_hour, exit_mark = day_start, float(hourly.open[asset][day_start])
                break
            if pending_partial_day is not None and day >= pending_partial_day:
                mark = float(hourly.open[asset][day_start])
                cash_before, quantity_before = cash, quantity
                cash, quantity, partial_fill, quantity_closed = reduce_position(
                    cash,
                    quantity,
                    side,
                    entry_fill,
                    mark,
                    slippage,
                    partial_protection.fraction,
                )
                partial_events.append(
                    {
                        "ts": daily.ts[day],
                        "mark": mark,
                        "fill": partial_fill,
                        "fraction": partial_protection.fraction,
                        "quantity_before": quantity_before,
                        "quantity_closed": quantity_closed,
                        "quantity_remaining": quantity,
                        "cash_before": cash_before,
                        "cash_after": cash,
                    }
                )
                counts["partial_profit_events"] += 1
                partial_done = True
                pending_partial_day = None
            next_day_start = day_to_hour[daily.ts[day + 1]]
            for hour in range(day_start, next_day_start):
                cash -= side * quantity * float(hourly.unit_funding[asset][hour])
                stop_mark: float | None = None
                if active_stop is not None:
                    open_mark = float(hourly.open[asset][hour])
                    gap = (side > 0 and open_mark <= active_stop) or (side < 0 and open_mark >= active_stop)
                    touched = (side > 0 and hourly.low[asset][hour] <= active_stop) or (side < 0 and hourly.high[asset][hour] >= active_stop)
                    if gap:
                        stop_mark = open_mark
                    elif touched:
                        stop_mark = active_stop
                if stop_mark is not None:
                    cash, exit_fill = close_position(cash, quantity, side, entry_fill, stop_mark, slippage)
                    peak = max(peak, cash)
                    max_drawdown = min(max_drawdown, cash / peak - 1.0)
                    exit_hour, exit_mark, exit_reason, stopped = hour, stop_mark, "stop", True
                    if retain and path_values is not None:
                        path_values[hour] = cash
                        favorable_values[hour] = cash
                        adverse_values[hour] = cash
                    break
                favorable = hourly.high[asset][hour] if side > 0 else hourly.low[asset][hour]
                adverse = hourly.low[asset][hour] if side > 0 else hourly.high[asset][hour]
                favorable_equity = cash + side * quantity * (favorable - entry_fill)
                peak = max(peak, favorable_equity)
                adverse_equity = cash + side * quantity * (adverse - entry_fill)
                max_drawdown = min(max_drawdown, adverse_equity / peak - 1.0)
                close_equity = cash + side * quantity * (hourly.close[asset][hour] - entry_fill)
                peak = max(peak, close_equity)
                max_drawdown = min(max_drawdown, close_equity / peak - 1.0)
                if retain and path_values is not None:
                    path_values[hour] = close_equity
                    favorable_values[hour] = favorable_equity
                    adverse_values[hour] = adverse_equity
            if stopped:
                break
            extreme = max(extreme, daily.high[asset][day]) if side > 0 else min(extreme, daily.low[asset][day])
            candidate_stop = extreme - config.trail_atr * daily.atr14[asset][day] if side > 0 else extreme + config.trail_atr * daily.atr14[asset][day]
            if np.isfinite(candidate_stop):
                active_stop = candidate_stop if active_stop is None else (max(active_stop, candidate_stop) if side > 0 else min(active_stop, candidate_stop))
            profit_exit = False
            if profit_protection is not None and np.isfinite(entry_atr):
                mfe = side * (extreme - entry_fill)
                armed = mfe >= profit_protection.activation_atr * entry_atr
                threshold = entry_fill + side * (1.0 - profit_protection.giveback) * mfe
                beyond = daily.close[asset][day] <= threshold if side > 0 else daily.close[asset][day] >= threshold
                profit_streak = profit_streak + 1 if armed and beyond else 0
                profit_exit = profit_streak >= profit_protection.confirm_days
            partial_exit = False
            if partial_protection is not None and not partial_done and np.isfinite(entry_atr):
                partial_mfe = side * (extreme - entry_fill)
                partial_armed = partial_mfe >= partial_protection.activation_atr * entry_atr
                partial_threshold = entry_fill + side * (1.0 - partial_protection.giveback) * partial_mfe
                partial_beyond = (
                    daily.close[asset][day] <= partial_threshold
                    if side > 0
                    else daily.close[asset][day] >= partial_threshold
                )
                partial_streak = partial_streak + 1 if partial_armed and partial_beyond else 0
                partial_exit = partial_streak >= partial_protection.confirm_days
            channel = daily.close[asset][day] < prior_low[asset][day] if side > 0 else daily.close[asset][day] > prior_high[asset][day]
            regime_exit = campaign_state is not None and int(campaign_state[day]) != side
            held_days = day - entry_day + 1
            timeout = config.max_hold_days > 0 and held_days >= config.max_hold_days
            if pending_exit_day is None and (profit_exit or regime_exit or channel or timeout):
                pending_exit_day = day + 1 + delay_days
                if profit_exit:
                    exit_reason = "profit_protection"
                elif regime_exit:
                    exit_reason = "regime"
                else:
                    exit_reason = "channel" if channel else "timeout"
            elif pending_partial_day is None and partial_exit:
                pending_partial_day = day + 1 + delay_days
            day += 1
        if not stopped:
            cash, exit_fill = close_position(cash, quantity, side, entry_fill, exit_mark, slippage)
            peak = max(peak, cash)
            max_drawdown = min(max_drawdown, cash / peak - 1.0)
            if exit_hour == day_to_hour[data.DEVELOPMENT_END]:
                exit_reason = "terminal"
        if retain and path_values is not None:
            path_values[exit_hour] = cash
            favorable_values[exit_hour] = cash
            adverse_values[exit_hour] = cash
        exit_day = int(daily.ts.searchsorted(hourly.ts[exit_hour].floor("1D")))
        trade_log_growth = math.log(cash / entry_equity) if cash > 0 and entry_equity > 0 else None
        trades.append({
            "signal_ts": daily.ts[signal_day], "entry_ts": entry_ts, "exit_ts": hourly.ts[exit_hour],
            "asset": asset, "side": side, "entry_mark": entry_mark, "entry_fill": entry_fill,
            "exit_mark": exit_mark, "exit_fill": exit_fill, "entry_equity": entry_equity,
            "exit_equity": cash, "exit_reason": exit_reason, "trade_log_growth": trade_log_growth,
            "partial_events": partial_events,
            "entry_source": entry_source,
        })
        identity: tuple[Any, ...] = (signal_day, entry_day, exit_hour, asset, side, exit_reason)
        if partial_protection is not None:
            identity += (tuple((event["ts"].isoformat(), event["fraction"]) for event in partial_events),)
        identities.append(identity)
        counts["trades"] += 1
        counts["long" if side > 0 else "short"] += 1
        counts[asset] += 1
        counts[f"{exit_reason}_exit"] += 1
        flat_hour_cursor = exit_hour
        minimum_signal_day = exit_day + config.cooldown_days
        if (
            handoff is not None
            and entry_source == "regular"
            and exit_reason == "profit_protection"
            and exit_day < end_day
        ):
            armed_handoff = {
                "asset": asset,
                "side": side,
                "level": float(extreme),
                "start_day": exit_day,
            }
            counts["handoff_armed"] += 1
        if exit_day >= end_day:
            break
    if retain and path_values is not None:
        path_values[flat_hour_cursor:] = np.where(np.isnan(path_values[flat_hour_cursor:]), cash, path_values[flat_hour_cursor:])
        favorable_values[flat_hour_cursor:] = np.where(
            np.isnan(favorable_values[flat_hour_cursor:]), cash, favorable_values[flat_hour_cursor:]
        )
        adverse_values[flat_hour_cursor:] = np.where(
            np.isnan(adverse_values[flat_hour_cursor:]), cash, adverse_values[flat_hour_cursor:]
        )
        path = [
            {
                "ts": ts,
                "equity": float(equity),
                "favorable_equity": float(favorable),
                "adverse_equity": float(adverse),
            }
            for ts, equity, favorable, adverse in zip(
                hourly.ts, path_values, favorable_values, adverse_values, strict=True
            )
        ]
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
    values = (equity / equity.shift(24 * 365) - 1.0).dropna()
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
    parser = argparse.ArgumentParser(description="Frozen P0 search for BIN-1D-BE-CBCT.")
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    grid = configs()
    if args.self_test:
        assert len(grid) == 2808
        print("self-test: PASS")
        return
    data = load_data_helper()
    hourly_source, funding, quality = data.load_frozen_data()
    daily, hourly, daily_frame = prepare_markets(data, hourly_source, funding)
    books = {(entry_n, ema, confirm): build_entry_book(daily_frame, daily, entry_n, ema, confirm) for entry_n, ema, confirm in sorted({(c.entry_n, c.breadth_ema, c.confirm_days) for c in grid})}
    channels = {exit_n: exit_channels(daily_frame, exit_n) for exit_n in sorted({c.exit_n for c in grid})}
    rows, passing_base = [], []
    for config in grid:
        book = books[(config.entry_n, config.breadth_ema, config.confirm_days)]
        result = simulate(data, daily, hourly, book, channels[config.exit_n], config, slippage=BASE_SLIPPAGE)
        base_pass = result.equity_multiple >= 20.0 and result.max_drawdown_pct >= -20.0
        row = {**asdict(config), "equity_multiple": result.equity_multiple, "ordered_mdd_pct": result.max_drawdown_pct, **result.counts, "trade_path_sha256": result.trade_path_sha256, "base_screen_pass": base_pass, "all_gates_pass": False}
        rows.append(row)
        if base_pass:
            passing_base.append((config, book))
    details, retained, seen = [], {}, set()
    for config, book in sorted(passing_base):
        base = simulate(data, daily, hourly, book, channels[config.exit_n], config, slippage=BASE_SLIPPAGE, retain=True)
        if base.trade_path_sha256 in seen:
            continue
        seen.add(base.trade_path_sha256)
        stress = simulate(data, daily, hourly, book, channels[config.exit_n], config, slippage=STRESS_SLIPPAGE)
        delayed = simulate(data, daily, hourly, book, channels[config.exit_n], config, slippage=BASE_SLIPPAGE, delay_days=1)
        base_log = math.log(base.equity_multiple)
        stress_retention = math.log(stress.equity_multiple) / base_log if stress.equity_multiple > 0 else -math.inf
        delay_retention = math.log(delayed.equity_multiple) / base_log if delayed.equity_multiple > 0 else -math.inf
        gates = {
            "stress": stress.equity_multiple >= 16.0 and stress.max_drawdown_pct >= -22.0,
            "delay": delay_retention >= 0.70 and delayed.equity_multiple >= 8.0 and delayed.max_drawdown_pct >= -25.0,
            "calendar": complete_year_ratio(base.path) >= 0.70,
            "rolling": rolling_ratio(base.path) >= 0.70,
            "capacity": base.counts["trades"] >= 20 and all(base.counts[key] >= 5 for key in ("long", "short", "BTCUSDT", "ETHUSDT")),
            "concentration": concentration(base.trades) <= 0.30,
        }
        detail = {**asdict(config), "base_equity_multiple": base.equity_multiple, "base_ordered_mdd_pct": base.max_drawdown_pct, **base.counts, "trade_path_sha256": base.trade_path_sha256, "stress_equity_multiple": stress.equity_multiple, "stress_ordered_mdd_pct": stress.max_drawdown_pct, "stress_log_growth_retention": stress_retention, "delay_equity_multiple": delayed.equity_multiple, "delay_ordered_mdd_pct": delayed.max_drawdown_pct, "delay_log_growth_retention": delay_retention, "complete_year_positive_ratio": complete_year_ratio(base.path), "rolling_365d_positive_ratio": rolling_ratio(base.path), "max_trade_positive_log_share": concentration(base.trades), **{f"gate_{key}": value for key, value in gates.items()}, "all_gates_pass": all(gates.values())}
        details.append(detail)
        retained[config] = base
    frame, detail_frame = pd.DataFrame(rows), pd.DataFrame(details)
    passing = detail_frame.loc[detail_frame["all_gates_pass"]].copy() if not detail_frame.empty else detail_frame
    if not passing.empty:
        passing = passing.sort_values(["base_ordered_mdd_pct", "stress_log_growth_retention", "base_equity_multiple", "trades", "entry_n", "exit_n", "breadth_ema", "trail_atr", "confirm_days", "cooldown_days", "max_hold_days"], ascending=[False, False, False, True, True, True, True, True, True, True, True])
    unique = passing.iloc[0].to_dict() if not passing.empty else None
    best_growth = frame.sort_values(["equity_multiple", "ordered_mdd_pct"], ascending=[False, False]).iloc[0].to_dict()
    best_risk = frame.sort_values(["ordered_mdd_pct", "equity_multiple"], ascending=[False, False]).iloc[0].to_dict()
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(), "family": "Binance-1D-BTCETH-Cross-Breadth-Channel-Trend", "campaign": "P0 frozen development search",
        "status": "development candidate; audit sealed" if unique else "HARD-GATE-FAILED / explore / not promoted / not live-ready",
        "evidence_role": "development only; audit/prospective not read", "data_quality": quality,
        "contract": {"configs": len(grid), "fee_per_fill": FEE, "base_slippage": BASE_SLIPPAGE, "stress_slippage": STRESS_SLIPPAGE, "initial_leverage": 1.0},
        "counts": {"configs": len(frame), "base_screen_pass": int(frame["base_screen_pass"].sum()), "unique_base_paths": len(detail_frame), "all_gates_pass": int(detail_frame["all_gates_pass"].sum()) if not detail_frame.empty else 0},
        "best_growth": best_growth, "best_risk": best_risk, "unique_candidate": unique, "audit_revealed": False, "prospective_revealed": False,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"binance_1d_be_cbct_p0_search_{args.run_date}"
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
