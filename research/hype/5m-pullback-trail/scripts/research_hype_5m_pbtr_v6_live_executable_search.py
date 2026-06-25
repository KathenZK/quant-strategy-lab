from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade, add_features
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_live_executable_search.json")
PRESCREEN_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_live_executable_prescreen.csv")
CANDIDATE_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_live_executable_candidates.csv")
SLICE_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_live_executable_slices.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_live_executable_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v6-live-executable-search-2026-06-25.md"
)

IS_END = pd.Timestamp("2026-03-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")
MIN_FULL_TRADES = 80
MIN_TRAIN_EVENTS = 100
PRESCREEN_TOP = 80
ATOMIC_TOP = 28
PRESCREEN_RANK_KEYS = (
    "is_2025_05_30_to_2026_03_01_profit_factor",
    "is_2025_05_30_to_2026_03_01_avg_trade",
    "is_2025_05_30_to_2026_03_01_total_return",
    "profit_factor",
)


@dataclass(frozen=True, slots=True)
class SignalSpec:
    style: str
    ema_fast: int
    ema_slow: int
    pullback_buffer: float
    side_mode: str
    require_candle: bool
    htf_threshold: float | None

    @property
    def label(self) -> str:
        htf = "none" if self.htf_threshold is None else f"{self.htf_threshold:g}"
        candle = "candle" if self.require_candle else "nocandle"
        return (
            f"{self.style}_ema{self.ema_fast}_{self.ema_slow}"
            f"_pb{self.pullback_buffer:g}_{self.side_mode}_{candle}_htf{htf}"
        )


@dataclass(frozen=True, slots=True)
class ExitSpec:
    tp_atr: float
    sl_atr: float
    trail_atr: float
    time_exit_bars: int

    @property
    def label(self) -> str:
        return f"tp{self.tp_atr:g}_sl{self.sl_atr:g}_tr{self.trail_atr:g}_tx{self.time_exit_bars}"


@dataclass(frozen=True, slots=True)
class RuleSpec:
    label: str
    conditions: tuple[tuple[str, str, float], ...]


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def load_closed_frame() -> pd.DataFrame:
    frame = load_all_hype_5m()
    now = pd.Timestamp.now(tz="UTC")
    frame = frame.loc[pd.to_datetime(frame["ts"], utc=True) + pd.Timedelta(minutes=5) <= now].reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="5min")
    missing = expected.difference(pd.to_datetime(frame["ts"], utc=True))
    if len(missing):
        raise RuntimeError(f"HYPE 5m data has {len(missing)} missing bars, first={missing[0]}")
    return frame


def signal_specs() -> list[SignalSpec]:
    specs: list[SignalSpec] = []
    for ema_fast, ema_slow in ((9, 55), (9, 96), (13, 55), (13, 96), (21, 55), (21, 96)):
        for pullback_buffer in (0.005, 0.01, 0.015):
            for side_mode in ("both", "long", "short"):
                for require_candle in (True, False):
                    for htf_threshold in (None, 0.5):
                        specs.append(
                            SignalSpec(
                                style="pullback_reclaim",
                                ema_fast=ema_fast,
                                ema_slow=ema_slow,
                                pullback_buffer=pullback_buffer,
                                side_mode=side_mode,
                                require_candle=require_candle,
                                htf_threshold=htf_threshold,
                            )
                        )
    return specs


def exit_specs() -> list[ExitSpec]:
    fixed_pairs = (
        (1.0, 2.0),
        (1.5, 2.0),
        (2.0, 3.0),
        (2.5, 3.0),
        (3.0, 4.0),
        (5.0, 6.0),
    )
    specs: list[ExitSpec] = []
    for time_exit_bars in (6, 12, 24, 48):
        for tp_atr, sl_atr in fixed_pairs:
            specs.append(ExitSpec(tp_atr=tp_atr, sl_atr=sl_atr, trail_atr=0.0, time_exit_bars=time_exit_bars))
    for time_exit_bars in (12, 24, 48):
        for tp_atr in (2.0, 3.0, 5.0):
            for sl_atr in (2.0, 4.0):
                for trail_atr in (2.0, 4.0, 6.0):
                    specs.append(ExitSpec(tp_atr=tp_atr, sl_atr=sl_atr, trail_atr=trail_atr, time_exit_bars=time_exit_bars))
    return specs


def regime_age(direction: np.ndarray) -> np.ndarray:
    age = np.zeros(len(direction), dtype=np.int32)
    current = 0
    start = 0
    for idx, value in enumerate(direction):
        if value == 0 or value != current:
            current = int(value)
            start = idx
        age[idx] = idx - start
    return age


def build_signal(frame: pd.DataFrame, spec: SignalSpec) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{spec.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{spec.ema_slow}"].to_numpy("float64")
    atr14 = frame["atr14"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    if spec.side_mode == "long":
        direction = np.where(direction > 0, 1, 0).astype(np.int8)
    elif spec.side_mode == "short":
        direction = np.where(direction < 0, -1, 0).astype(np.int8)

    touched = np.where(
        direction > 0,
        low <= ema_fast * (1.0 + spec.pullback_buffer),
        high >= ema_fast * (1.0 - spec.pullback_buffer),
    )
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    mask = (direction != 0) & touched & reclaimed & np.isfinite(atr14)
    if spec.require_candle:
        candle = np.where(direction > 0, close > open_, close < open_)
        mask &= candle
    if spec.htf_threshold is not None:
        htf = frame["htf_spread"].to_numpy("float64")
        mask &= np.isfinite(htf) & (direction * htf >= spec.htf_threshold)
    mask = np.nan_to_num(mask, nan=False).astype(bool)
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[mask] = direction[mask]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def add_search_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]
    high = result["high"]
    low = result["low"]
    open_ = result["open"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    for span in (13,):
        column = f"ema{span}"
        if column not in result.columns:
            result[column] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    result["atr_bps"] = result["atr14"] / close * 10000.0
    result["atr_ratio_14_96"] = result["atr14"] / result["atr14"].rolling(96, min_periods=96).mean()
    result["range_atr"] = (high - low) / result["atr14"]
    result["body_bps"] = (close / open_ - 1.0) * 10000.0
    result["abs_body_atr"] = (close - open_).abs() / result["atr14"]
    candle_top = pd.concat([open_, close], axis=1).max(axis=1)
    candle_bottom = pd.concat([open_, close], axis=1).min(axis=1)
    result["upper_wick_atr"] = (high - candle_top) / result["atr14"]
    result["lower_wick_atr"] = (candle_bottom - low) / result["atr14"]
    result["vol_ratio_96"] = result["volume"] / result["volume"].rolling(96, min_periods=96).mean()
    result["quote_vol_ratio_96"] = result["quote_volume"] / result["quote_volume"].rolling(96, min_periods=96).mean()
    result["trade_count_ratio_96"] = result["trade_count"] / result["trade_count"].rolling(96, min_periods=96).mean()
    sum_tr = tr.rolling(14, min_periods=14).sum()
    high_14 = high.rolling(14, min_periods=14).max()
    low_14 = low.rolling(14, min_periods=14).min()
    result["chop14_alt"] = 100.0 * np.log10(sum_tr / (high_14 - low_14).replace(0.0, np.nan)) / np.log10(14)
    for window in (3, 6, 12, 24, 48, 96, 192, 384):
        result[f"ret{window}"] = close / close.shift(window) - 1.0
    return result


def exit_price_with_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * EXIT_SLIPPAGE_RATE))


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return bool(open_price >= target_price if side > 0 else open_price <= target_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def touched_target(high_price: float, low_price: float, target_price: float, side: int) -> bool:
    return bool(high_price >= target_price if side > 0 else low_price <= target_price)


def simulate_live_orders(
    frame: pd.DataFrame,
    signal: np.ndarray,
    signal_spec: SignalSpec,
    exit_spec: ExitSpec,
    *,
    label: str,
) -> list[Trade]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if side == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        target_price = entry_price + side * exit_spec.tp_atr * signal_atr
        stop_price = entry_price - side * exit_spec.sl_atr * signal_atr
        active_stop = stop_price
        exit_i = min(n - 1, entry_i + exit_spec.time_exit_bars)
        raw_exit_price = float(open_[exit_i] if exit_i < n else close[-1])
        reason = "time_open"
        peak = entry_price
        trough = entry_price

        for bar_i in range(entry_i, min(n, entry_i + exit_spec.time_exit_bars + 1)):
            if crossed_stop(float(open_[bar_i]), active_stop, side):
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "stop_gap_open"
                break
            if crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target_gap_or_open"
                break
            if bar_i == entry_i + exit_spec.time_exit_bars:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "time_open"
                break

            stop_hit = touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side)
            target_hit = touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
            if stop_hit and target_hit:
                exit_i = bar_i
                raw_exit_price = float(active_stop)
                reason = "both_hit_stop_first"
                break
            if stop_hit:
                exit_i = bar_i
                raw_exit_price = float(active_stop)
                reason = "stop_market"
                break
            if target_hit:
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target"
                break

            if side > 0:
                peak = max(peak, float(high[bar_i]))
                if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = max(active_stop, peak - exit_spec.trail_atr * float(atr[bar_i]))
            else:
                trough = min(trough, float(low[bar_i]))
                if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = min(active_stop, trough + exit_spec.trail_atr * float(atr[bar_i]))

        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if len(path_high) == 0:
            continue
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))

        exit_price = exit_price_with_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        trades.append(
            Trade(
                config=label,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i
    return trades


def summarize_trades(label: str, trades: list[Trade], frame: pd.DataFrame, extra: dict[str, Any]) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    reasons: dict[str, int] = {}
    for trade in trades:
        reasons[trade.reason] = reasons.get(trade.reason, 0) + 1
    return {
        "label": label,
        "trade_count": len(trades),
        "trades_per_day": len(trades) / days,
        "reason_counts": json.dumps(reasons, ensure_ascii=False, sort_keys=True),
        **extra,
        **metric_with_sides(trades, LEVERAGE, start=start, end=end),
    }


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "is_2025_05_30_to_2026_03_01", "start": start, "end": IS_END},
        {"name": "val_2026_03_01_to_2026_06_01", "start": IS_END, "end": VAL_END},
        {"name": "oos_2026_06_01_to_latest", "start": VAL_END, "end": end},
        {"name": "slice_2025_05_30_to_2025_09_01", "start": start, "end": pd.Timestamp("2025-09-01T00:00:00Z")},
        {"name": "slice_2025_09_01_to_2025_12_01", "start": pd.Timestamp("2025-09-01T00:00:00Z"), "end": pd.Timestamp("2025-12-01T00:00:00Z")},
        {"name": "slice_2025_12_01_to_2026_03_01", "start": pd.Timestamp("2025-12-01T00:00:00Z"), "end": IS_END},
        {"name": "slice_2026_03_01_to_2026_06_01", "start": IS_END, "end": VAL_END},
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    periods = pd.period_range(start.tz_convert(None).to_period("M"), (end - pd.Timedelta(minutes=5)).tz_convert(None).to_period("M"), freq="M")
    rows: list[dict[str, Any]] = []
    for period in periods:
        raw_start = pd.Timestamp(period.start_time, tz="UTC")
        raw_end = pd.Timestamp((period + 1).start_time, tz="UTC")
        slice_start = max(start, raw_start)
        slice_end = min(end, raw_end)
        if slice_start < slice_end:
            rows.append({"name": str(period), "start": slice_start, "end": slice_end})
    return rows


def event_features(frame: pd.DataFrame, signal: np.ndarray, spec: SignalSpec) -> pd.DataFrame:
    sig_idx = np.flatnonzero(signal)
    side = signal[sig_idx].astype("float64")
    ts = pd.to_datetime(frame["ts"], utc=True)
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{spec.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{spec.ema_slow}"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    age = regime_age(direction)
    data: dict[str, np.ndarray] = {
        "idx": sig_idx,
        "signal_ts": frame["ts"].to_numpy()[sig_idx],
        "side": side,
        "is_long": (side > 0).astype("float64"),
        "hour": ts.dt.hour.to_numpy()[sig_idx].astype("float64"),
        "ema_spread_bps": side * spread[sig_idx] / close[sig_idx] * 10000.0,
        "abs_ema_spread_bps": np.abs(spread[sig_idx] / close[sig_idx] * 10000.0),
        "htf_spread_bps": side * frame["htf_spread"].to_numpy("float64")[sig_idx] / close[sig_idx] * 10000.0,
        "dist_fast_bps": side * (close[sig_idx] / ema_fast[sig_idx] - 1.0) * 10000.0,
        "abs_dist_fast_bps": np.abs(close[sig_idx] / ema_fast[sig_idx] - 1.0) * 10000.0,
        "rsi14_dir": np.where(side > 0, frame["rsi14"].to_numpy("float64")[sig_idx], 100.0 - frame["rsi14"].to_numpy("float64")[sig_idx]),
        "adx14": frame["adx14"].to_numpy("float64")[sig_idx],
        "chop14": frame["chop14"].to_numpy("float64")[sig_idx],
        "chop14_alt": frame["chop14_alt"].to_numpy("float64")[sig_idx],
        "atr_bps": frame["atr_bps"].to_numpy("float64")[sig_idx],
        "atr_ratio_14_96": frame["atr_ratio_14_96"].to_numpy("float64")[sig_idx],
        "range_atr": frame["range_atr"].to_numpy("float64")[sig_idx],
        "abs_body_atr": frame["abs_body_atr"].to_numpy("float64")[sig_idx],
        "dir_body_bps": side * frame["body_bps"].to_numpy("float64")[sig_idx],
        "dir_wick_atr": np.where(side > 0, frame["upper_wick_atr"].to_numpy("float64")[sig_idx], frame["lower_wick_atr"].to_numpy("float64")[sig_idx]),
        "opp_wick_atr": np.where(side > 0, frame["lower_wick_atr"].to_numpy("float64")[sig_idx], frame["upper_wick_atr"].to_numpy("float64")[sig_idx]),
        "vol_ratio_96": frame["vol_ratio_96"].to_numpy("float64")[sig_idx],
        "quote_vol_ratio_96": frame["quote_vol_ratio_96"].to_numpy("float64")[sig_idx],
        "trade_count_ratio_96": frame["trade_count_ratio_96"].to_numpy("float64")[sig_idx],
        "regime_age": age[sig_idx].astype("float64"),
    }
    for window in (3, 6, 12, 24, 48, 96, 192, 384):
        data[f"dir_ret{window}_bps"] = side * frame[f"ret{window}"].to_numpy("float64")[sig_idx] * 10000.0
    return pd.DataFrame(data)


def independent_event_outcomes(frame: pd.DataFrame, signal: np.ndarray, exit_spec: ExitSpec) -> pd.DataFrame:
    sig_idx = np.flatnonzero(signal)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    n = len(frame)
    rows: list[dict[str, Any]] = []
    for sig_i in sig_idx:
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if side == 0 or entry_i >= n:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        target_price = entry_price + side * exit_spec.tp_atr * signal_atr
        active_stop = entry_price - side * exit_spec.sl_atr * signal_atr
        exit_i = min(n - 1, entry_i + exit_spec.time_exit_bars)
        raw_exit_price = float(open_[exit_i])
        reason = "time_open"
        peak = entry_price
        trough = entry_price
        for bar_i in range(entry_i, min(n, entry_i + exit_spec.time_exit_bars + 1)):
            if crossed_stop(float(open_[bar_i]), active_stop, side):
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "stop_gap_open"
                break
            if crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target_gap_or_open"
                break
            if bar_i == entry_i + exit_spec.time_exit_bars:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "time_open"
                break
            stop_hit = touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side)
            target_hit = touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
            if stop_hit and target_hit:
                exit_i = bar_i
                raw_exit_price = float(active_stop)
                reason = "both_hit_stop_first"
                break
            if stop_hit:
                exit_i = bar_i
                raw_exit_price = float(active_stop)
                reason = "stop_market"
                break
            if target_hit:
                exit_i = bar_i
                raw_exit_price = float(target_price)
                reason = "target"
                break
            if side > 0:
                peak = max(peak, float(high[bar_i]))
                if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = max(active_stop, peak - exit_spec.trail_atr * float(atr[bar_i]))
            else:
                trough = min(trough, float(low[bar_i]))
                if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                    active_stop = min(active_stop, trough + exit_spec.trail_atr * float(atr[bar_i]))
        exit_price = exit_price_with_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        rows.append({"idx": int(sig_i), "event_net_ret_1x": float(gross - fee_cost), "event_reason": reason, "event_exit_i": int(exit_i)})
    return pd.DataFrame(rows)


def simple_metrics(rets: np.ndarray) -> dict[str, float | int]:
    rets = rets[np.isfinite(rets)]
    if len(rets) == 0:
        return {"events": 0, "event_pf": 0.0, "event_avg": 0.0, "event_win": 0.0, "event_payoff": 0.0}
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf") if len(wins) else 0.0
    payoff = float(wins.mean() / abs(losses.mean())) if len(wins) and len(losses) else 0.0
    return {"events": int(len(rets)), "event_pf": pf, "event_avg": float(rets.mean()), "event_win": float((rets > 0).mean()), "event_payoff": payoff}


def event_metrics(events: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | int]:
    if events.empty:
        return {
            "trades": 0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss_abs": 0.0,
            "payoff_ratio": 0.0,
            "worst_trade": 0.0,
            "best_trade": 0.0,
        }
    ts = pd.to_datetime(events["signal_ts"], utc=True)
    selected = events.loc[(ts >= start) & (ts < end)].copy()
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if selected.empty:
        return {
            "trades": 0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "avg_win": 0.0,
            "avg_loss_abs": 0.0,
            "payoff_ratio": 0.0,
            "worst_trade": 0.0,
            "best_trade": 0.0,
        }
    rets = selected["event_net_ret_1x"].to_numpy("float64")
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret in rets:
        equity *= max(0.001, 1.0 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
    payoff = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf") if len(wins) else 0.0
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    return {
        "trades": int(len(rets)),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((rets > 0).mean()),
        "profit_factor": pf,
        "avg_trade": float(rets.mean()),
        "avg_win": avg_win,
        "avg_loss_abs": avg_loss_abs,
        "payoff_ratio": payoff,
        "worst_trade": float(rets.min()),
        "best_trade": float(rets.max()),
    }


def attach_event_key_slices(row: dict[str, Any], events: pd.DataFrame, frame: pd.DataFrame) -> dict[str, Any]:
    result = dict(row)
    for item in validation_slices(frame):
        metrics = event_metrics(events, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            result[f"{item['name']}_{key}"] = value
    return result


def apply_rule(events: pd.DataFrame, rule: RuleSpec) -> np.ndarray:
    keep = np.ones(len(events), dtype=bool)
    for column, op, threshold in rule.conditions:
        values = events[column].to_numpy("float64")
        if op == "<=":
            keep &= np.isfinite(values) & (values <= threshold)
        elif op == ">=":
            keep &= np.isfinite(values) & (values >= threshold)
        else:
            raise ValueError(op)
    return keep


def build_atomic_rules(events: pd.DataFrame, train_mask: np.ndarray) -> list[tuple[RuleSpec, dict[str, Any]]]:
    rules: list[tuple[RuleSpec, dict[str, Any]]] = []
    excluded = {"idx", "signal_ts", "event_net_ret_1x", "event_reason", "event_exit_i"}
    for column in events.columns:
        if column in excluded:
            continue
        values = events[column].to_numpy("float64")
        finite_train = np.isfinite(values) & train_mask
        if int(finite_train.sum()) < MIN_TRAIN_EVENTS * 2:
            continue
        thresholds = sorted(set(float(np.quantile(values[finite_train], q)) for q in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)))
        for threshold in thresholds:
            for op in ("<=", ">="):
                rule = RuleSpec(label=f"{column}{op}{threshold:.6g}", conditions=((column, op, threshold),))
                keep = apply_rule(events, rule)
                train_count = int((keep & train_mask).sum())
                if train_count < MIN_TRAIN_EVENTS:
                    continue
                metrics = simple_metrics(events.loc[keep & train_mask, "event_net_ret_1x"].to_numpy("float64"))
                if float(metrics["event_pf"]) <= 1.0 or float(metrics["event_avg"]) <= 0:
                    continue
                rules.append((rule, {"train_" + key: value for key, value in metrics.items()}))
    rules.sort(key=lambda item: (float(item[1]["train_event_pf"]), float(item[1]["train_event_avg"])), reverse=True)
    return rules[:ATOMIC_TOP]


def build_pair_rules(events: pd.DataFrame, atomic: list[tuple[RuleSpec, dict[str, Any]]], train_mask: np.ndarray) -> list[tuple[RuleSpec, dict[str, Any]]]:
    pairs: list[tuple[RuleSpec, dict[str, Any]]] = []
    for i, (left, _left_meta) in enumerate(atomic):
        for right, _right_meta in atomic[i + 1 :]:
            columns = {cond[0] for cond in left.conditions + right.conditions}
            if len(columns) < 2:
                continue
            rule = RuleSpec(label=f"{left.label} & {right.label}", conditions=left.conditions + right.conditions)
            keep = apply_rule(events, rule)
            train_count = int((keep & train_mask).sum())
            if train_count < MIN_TRAIN_EVENTS:
                continue
            metrics = simple_metrics(events.loc[keep & train_mask, "event_net_ret_1x"].to_numpy("float64"))
            if float(metrics["event_pf"]) <= 1.1 or float(metrics["event_avg"]) <= 0:
                continue
            pairs.append((rule, {"train_" + key: value for key, value in metrics.items()}))
    pairs.sort(key=lambda item: (float(item[1]["train_event_pf"]), float(item[1]["train_event_avg"])), reverse=True)
    return pairs[:ATOMIC_TOP]


def filtered_signal(base_signal: np.ndarray, events: pd.DataFrame, keep: np.ndarray) -> np.ndarray:
    signal = np.zeros_like(base_signal)
    idx = events.loc[keep, "idx"].to_numpy("int64")
    signal[idx] = base_signal[idx]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def slice_rows(label: str, trades: list[Trade], frame: pd.DataFrame, slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in slices:
        rows.append({"label": label, "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    return rows


def candidate_gate(rows: pd.DataFrame) -> pd.Series:
    full = rows["trades"] >= MIN_FULL_TRADES
    return (
        full
        & (rows["profit_factor"] > 1.0)
        & (rows["avg_trade"] > 0.0)
        & (rows["max_dd"] > -0.50)
        & (rows["is_2025_05_30_to_2026_03_01_profit_factor"] > 1.0)
        & (rows["val_2026_03_01_to_2026_06_01_profit_factor"] > 0.9)
        & (rows["oos_2026_06_01_to_latest_profit_factor"] > 0.8)
    )


def attach_key_slices(row: dict[str, Any], trades: list[Trade], frame: pd.DataFrame) -> dict[str, Any]:
    result = dict(row)
    for item in validation_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            result[f"{item['name']}_{key}"] = value
    return result


def render_markdown(
    *,
    frame: pd.DataFrame,
    prescreen: pd.DataFrame,
    candidates: pd.DataFrame,
    slices: pd.DataFrame,
    monthly: pd.DataFrame,
) -> str:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    lines = [
        "# HYPE-5M-PBTR-V6 live-executable 搜索 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本轮不是提升版 live spec，而是一次重新搜索：保留 V3.3 的趋势内回踩恢复触发方式作为主要事件源，同时允许 EMA 周期、回踩幅度、单边/双边、HTF 过滤、K 线方向过滤、固定 bracket、实时 trailing 和时间退出变化。",
        "",
        "## 实盘边界",
        "",
        f"- 数据：Binance HYPE USDT 永续 `5m`，闭合 K 范围 `{start}` 到 `{end - pd.Timedelta(minutes=5)}`，共 `{len(frame)}` 根。",
        "- 信号：只使用已收盘 K。若第 `t` 根 K 触发，最早在第 `t+1` 根开盘入场。",
        "- 入场：按下一根 open 加观测实盘开仓滑点。",
        "- 出口：入场后立即存在可挂的 TP/SL；若 open 已穿越 stop，按 open 市价退出；同一根 K 同时触及 TP/SL 时保守按 stop 先触发；trailing 只能在 K 收盘后更新，下一根才生效；时间退出按到期下一根 open 市价退出。",
        f"- 成本：手续费 `{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`，开仓滑点 `{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`，平仓滑点 `{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        "",
        "## 搜索规模",
        "",
        f"- prescreen 行数：`{len(prescreen)}`。",
        "- prescreen 排名：只按 `2025-05-30 -> 2026-03-01` 样本内 PF、平均每笔和收益排序；`2026-03-01` 之后不参与 top 区域选择。",
        f"- 精筛候选行数：`{len(candidates)}`。",
        f"- 通过宽松 candidate gate 的行数：`{int(candidates['candidate_pass'].sum()) if 'candidate_pass' in candidates else 0}`。",
        "",
        "## Prescreen Top 15",
        "",
        "| 排名 | 信号 | 出口 | 规则 | 交易数 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | IS PF | VAL PF | OOS PF |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rank, row in enumerate(prescreen.head(15).to_dict(orient="records"), start=1):
        lines.append(
            f"| `{rank}` | `{row['signal_label']}` | `{row['exit_label']}` | `{row.get('rule_label', 'none')}` | "
            f"`{int(row['trades'])}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{num(float(row.get('is_2025_05_30_to_2026_03_01_profit_factor', 0.0)))}` | "
            f"`{num(float(row.get('val_2026_03_01_to_2026_06_01_profit_factor', 0.0)))}` | "
            f"`{num(float(row.get('oos_2026_06_01_to_latest_profit_factor', 0.0)))}` |"
        )

    lines.extend(["", "## Candidate Gate 通过项", ""])
    passed = candidates.loc[candidates.get("candidate_pass", False)].copy() if len(candidates) else pd.DataFrame()
    if passed.empty:
        lines.append("无。")
    else:
        lines.extend(
            [
                "| 排名 | 信号 | 出口 | 规则 | 交易数 | 总收益 | PF | 平均每笔 | 最大回撤 | IS PF | VAL PF | OOS PF |",
                "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for rank, row in enumerate(passed.head(20).to_dict(orient="records"), start=1):
            lines.append(
                f"| `{rank}` | `{row['signal_label']}` | `{row['exit_label']}` | `{row.get('rule_label', 'none')}` | "
                f"`{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{num(float(row['profit_factor']))}` | "
                f"`{pct(float(row['avg_trade']))}` | `{pct(float(row['max_dd']))}` | "
                f"`{num(float(row['is_2025_05_30_to_2026_03_01_profit_factor']))}` | "
                f"`{num(float(row['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
                f"`{num(float(row['oos_2026_06_01_to_latest_profit_factor']))}` |"
            )

    lines.extend(["", "## 最佳候选切片", ""])
    if candidates.empty:
        lines.append("无候选可切片。")
    else:
        best_label = str(candidates.iloc[0]["label"])
        best_slices = slices.loc[slices["label"].eq(best_label)]
        lines.extend(
            [
                f"最佳候选：`{best_label}`",
                "",
                "| 切片 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in best_slices.to_dict(orient="records"):
            lines.append(
                f"| `{row['slice']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
                f"`{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | "
                f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` |"
            )
        best_monthly = monthly.loc[monthly["label"].eq(best_label)]
        lines.extend(["", "### 月度", "", "| 月份 | 交易数 | 总收益 | PF | 平均每笔 | 最大回撤 |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for row in best_monthly.to_dict(orient="records"):
            lines.append(
                f"| `{row['slice']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
                f"`{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | `{pct(float(row['max_dd']))}` |"
            )

    if len(candidates) and bool(candidates.iloc[0].get("candidate_pass", False)):
        verdict = "找到宽松 candidate gate 通过项，但仍需下一轮做 walk-forward 固化和 paper audit。"
    elif len(candidates) and float(candidates.iloc[0]["profit_factor"]) > 1.0:
        verdict = "存在全样本 PF 大于 1 的研究线索，但没有同时通过 IS/VAL/OOS 的 live-ready gate。"
    else:
        verdict = "没有找到可实盘且稳健盈利的参数组合。"
    lines.extend(
        [
            "",
            "## 结论",
            "",
            verdict,
            "",
            "这轮搜索刻意没有接受旧 `min_hold_bars + stale stop price` 的成交假设。若候选不能在这个口径下赚钱，就不应交给实盘 runner。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_live_executable_search.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- prescreen CSV：`{PRESCREEN_PATH}`",
            f"- candidates CSV：`{CANDIDATE_PATH}`",
            f"- slices CSV：`{SLICE_PATH}`",
            f"- monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def main() -> None:
    raw = load_closed_frame()
    frame = add_search_features(add_features(raw))
    sig_specs = signal_specs()
    ex_specs = exit_specs()
    print(f"data {frame['ts'].iloc[0]} -> {frame['ts'].iloc[-1]} rows={len(frame)}")
    print(f"signal_specs={len(sig_specs)} exit_specs={len(ex_specs)}")

    signal_cache: dict[str, np.ndarray] = {}
    prescreen_rows: list[dict[str, Any]] = []
    for s_idx, sig_spec in enumerate(sig_specs, start=1):
        signal = build_signal(frame, sig_spec)
        signal_count = int(np.count_nonzero(signal))
        if signal_count < MIN_FULL_TRADES:
            continue
        signal_cache[sig_spec.label] = signal
        base_events = event_features(frame, signal, sig_spec)
        if len(base_events) < MIN_FULL_TRADES:
            continue
        for exit_spec in ex_specs:
            label = f"{sig_spec.label}__{exit_spec.label}__none"
            outcomes = independent_event_outcomes(frame, signal, exit_spec)
            if len(outcomes) < MIN_FULL_TRADES:
                continue
            events = base_events.merge(outcomes, on="idx", how="inner")
            if len(events) < MIN_FULL_TRADES:
                continue
            full_metrics = event_metrics(
                events,
                start=pd.Timestamp(frame["ts"].iloc[0]),
                end=pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5),
            )
            row = {
                "label": label,
                "signal_label": sig_spec.label,
                "exit_label": exit_spec.label,
                "rule_label": "none",
                "rule_conditions": "[]",
                "signal_count": signal_count,
                "prescreen_mode": "independent_events",
                **{f"signal_{key}": value for key, value in asdict(sig_spec).items()},
                **{f"exit_{key}": value for key, value in asdict(exit_spec).items()},
                **full_metrics,
            }
            row = attach_event_key_slices(row, events, frame)
            prescreen_rows.append(row)
        if s_idx % 12 == 0:
            print(f"prescreen signal {s_idx}/{len(sig_specs)} rows={len(prescreen_rows)}", flush=True)

    prescreen = pd.DataFrame(prescreen_rows)
    if prescreen.empty:
        raise RuntimeError("prescreen produced no rows")
    prescreen = prescreen.sort_values(list(PRESCREEN_RANK_KEYS), ascending=False).reset_index(drop=True)
    top_prescreen = prescreen.head(PRESCREEN_TOP).copy()

    candidate_rows: list[dict[str, Any]] = []
    trade_by_label: dict[str, list[Trade]] = {}
    slice_rows_all: list[dict[str, Any]] = []
    monthly_rows_all: list[dict[str, Any]] = []

    for row_idx, base_row in enumerate(top_prescreen.to_dict(orient="records"), start=1):
        sig_spec = SignalSpec(
            style=str(base_row["signal_style"]),
            ema_fast=int(base_row["signal_ema_fast"]),
            ema_slow=int(base_row["signal_ema_slow"]),
            pullback_buffer=float(base_row["signal_pullback_buffer"]),
            side_mode=str(base_row["signal_side_mode"]),
            require_candle=bool(base_row["signal_require_candle"]),
            htf_threshold=None if pd.isna(base_row["signal_htf_threshold"]) else float(base_row["signal_htf_threshold"]),
        )
        exit_spec = ExitSpec(
            tp_atr=float(base_row["exit_tp_atr"]),
            sl_atr=float(base_row["exit_sl_atr"]),
            trail_atr=float(base_row["exit_trail_atr"]),
            time_exit_bars=int(base_row["exit_time_exit_bars"]),
        )
        signal = signal_cache.get(sig_spec.label)
        if signal is None:
            signal = build_signal(frame, sig_spec)
        events = event_features(frame, signal, sig_spec)
        outcomes = independent_event_outcomes(frame, signal, exit_spec)
        events = events.merge(outcomes, on="idx", how="inner")
        if len(events) < MIN_TRAIN_EVENTS:
            continue
        ts = pd.to_datetime(events["signal_ts"], utc=True)
        train_mask = ts < IS_END
        atomic = build_atomic_rules(events, train_mask.to_numpy())
        rules = [(RuleSpec(label="none", conditions=()), {})] + atomic + build_pair_rules(events, atomic, train_mask.to_numpy())
        print(f"refine {row_idx}/{len(top_prescreen)} base_pf={base_row['profit_factor']:.3f} rules={len(rules)} {sig_spec.label} {exit_spec.label}")
        for rule, rule_meta in rules:
            keep = np.ones(len(events), dtype=bool) if not rule.conditions else apply_rule(events, rule)
            if int(keep.sum()) < MIN_FULL_TRADES:
                continue
            filt_signal = filtered_signal(signal, events, keep)
            label = f"{sig_spec.label}__{exit_spec.label}__{rule.label}"
            trades = simulate_live_orders(frame, filt_signal, sig_spec, exit_spec, label=label)
            if len(trades) < MIN_FULL_TRADES:
                continue
            result = summarize_trades(
                label,
                trades,
                frame,
                {
                    "signal_label": sig_spec.label,
                    "exit_label": exit_spec.label,
                    "rule_label": rule.label,
                    "rule_conditions": json.dumps(rule.conditions, ensure_ascii=False),
                    "signal_count": int(np.count_nonzero(filt_signal)),
                    **{f"signal_{key}": value for key, value in asdict(sig_spec).items()},
                    **{f"exit_{key}": value for key, value in asdict(exit_spec).items()},
                    **rule_meta,
                },
            )
            result = attach_key_slices(result, trades, frame)
            candidate_rows.append(result)
            trade_by_label[label] = trades

    candidates = pd.DataFrame(candidate_rows)
    if not candidates.empty:
        candidates = candidates.sort_values(["profit_factor", "avg_trade", "total_return"], ascending=False).reset_index(drop=True)
        candidates["candidate_pass"] = candidate_gate(candidates)
        keep_labels = list(candidates.head(20)["label"])
        passed_labels = list(candidates.loc[candidates["candidate_pass"], "label"].head(20))
        for label in dict.fromkeys(passed_labels + keep_labels):
            trades = trade_by_label.get(label)
            if trades is None:
                continue
            slice_rows_all.extend(slice_rows(label, trades, frame, validation_slices(frame)))
            monthly_rows_all.extend(slice_rows(label, trades, frame, month_slices(frame)))
    else:
        candidates = pd.DataFrame()

    slices = pd.DataFrame(slice_rows_all)
    monthly = pd.DataFrame(monthly_rows_all)

    PRESCREEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    prescreen.to_csv(PRESCREEN_PATH, index=False)
    candidates.to_csv(CANDIDATE_PATH, index=False)
    slices.to_csv(SLICE_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    report = {
        "family_id": "HYPE-5M-PBTR",
        "search_id": "V6-live-executable-search",
        "data_start": pd.Timestamp(frame["ts"].iloc[0]),
        "data_end": pd.Timestamp(frame["ts"].iloc[-1]),
        "bar_count": int(len(frame)),
        "signal_specs": [asdict(item) for item in sig_specs],
        "exit_specs": [asdict(item) for item in ex_specs],
        "costs": {
            "fee_rate_per_fill": FEE_RATE_PER_FILL,
            "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
            "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
            "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
        },
        "prescreen_top": prescreen.head(100).to_dict(orient="records"),
        "candidates_top": candidates.head(100).to_dict(orient="records") if not candidates.empty else [],
        "candidate_pass_count": int(candidates["candidate_pass"].sum()) if "candidate_pass" in candidates else 0,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(frame=frame, prescreen=prescreen, candidates=candidates, slices=slices, monthly=monthly), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {PRESCREEN_PATH}")
    print(f"wrote {CANDIDATE_PATH}")
    print(f"wrote {SLICE_PATH}")
    print(f"wrote {MONTHLY_PATH}")
    print(f"wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
