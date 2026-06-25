from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from compare_hype_ema_v2_v4 import entry_signal
from research_hype_ema_cross_strategy import PERIODS_PER_YEAR, SLIPPAGE, TRADE_COST, build_features
from research_hype_ema_htf_rsi_exit_v9 import v8_clean_spec
from research_hype_ema_oscillator_top_exit_v10 import (
    add_oscillator_features,
)
from research_hype_ema_regime_hold_v5 import dynamic_allocation, load_hype_data_lake, run_variant_dynamic_3x
from research_hype_ema_volume_exhaustion_v7 import V7Spec, add_volume_features, exhaustion_masks
from research_hype_ema_volume_overlay_v8 import V8Spec, run_v8, v6_variant


REPORT_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12.json")
RANKING_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_ranking.csv")
TOP_TRADES_PATH = Path("research/hype/ema-crossover/artifacts/hype_state_machine_v12_top_trades.csv")


@dataclass(frozen=True, slots=True)
class V12Spec:
    name: str
    warning_source: str
    confirm_mode: str
    reentry_mode: str
    min_mfe_atr: float
    confirm_window: int
    trail_atr: float
    osc_min_score: int
    fallback_adx: float
    fallback_bars: int
    hard_exit_mode: str = "none"
    hard_exit_bars: int = 1
    volume_warning_mode: str = "all"
    warning_exit_min_capture: float = 0.0
    entry_max_regime_age: int = 0
    entry_min_rvol96: float = 0.0
    entry_max_dist_ema96: float = 0.0
    entry_max_move48: float = 0.0
    segment_exit_mode: str = "none"
    segment_min_mfe_atr: float = 0.0
    segment_exit_min_capture: float = 0.0
    segment_adx: float = 0.0
    segment_bars: int = 1
    stop_atr: float = 9.0
    exit_rvol: float = 2.0
    wick_min: float = 0.55


def build_v12_specs() -> list[V12Spec]:
    specs: list[V12Spec] = []
    for warning_source in ("volume", "osc", "either"):
        for confirm_mode in (
            "ema21",
            "ema55",
            "ema96",
            "donchian",
            "atr_trail",
            "ema21_or_donchian",
            "ema55_or_donchian",
            "ema55_and_donchian",
        ):
            for reentry_mode in ("none", "breakout48", "breakout96"):
                for min_mfe_atr in (2.0, 4.0):
                    for fallback_adx in (0.0, 18.0, 22.0):
                        for confirm_window in (24, 48, 96):
                            for trail_atr in (5.0, 7.5, 10.0):
                                if "donchian" not in confirm_mode and confirm_window != 24:
                                    continue
                                if confirm_mode != "atr_trail" and trail_atr != 5.0:
                                    continue
                                name = (
                                    f"V12_{warning_source}_{confirm_mode}_{reentry_mode}"
                                    f"_cw{confirm_window}_ta{trail_atr:g}"
                                    f"_mfe{min_mfe_atr:g}_adx{fallback_adx:g}"
                                )
                                specs.append(
                                    V12Spec(
                                        name=name,
                                        warning_source=warning_source,
                                        confirm_mode=confirm_mode,
                                        reentry_mode=reentry_mode,
                                        min_mfe_atr=min_mfe_atr,
                                        confirm_window=confirm_window,
                                        trail_atr=trail_atr,
                                        osc_min_score=3,
                                        fallback_adx=fallback_adx,
                                        fallback_bars=3,
                                    )
                                )
    return specs


def add_structure_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["ema21"] = result.close.ewm(span=21, adjust=False, min_periods=21).mean()
    result["ema55"] = result.close.ewm(span=55, adjust=False, min_periods=55).mean()
    result["ema96"] = result.close.ewm(span=96, adjust=False, min_periods=96).mean()
    spread = result.ema_spread.to_numpy("float64")
    previous = np.r_[np.nan, spread[:-1]]
    cross = ((spread > 0) & (previous <= 0)) | ((spread < 0) & (previous >= 0))
    age = np.full(len(result), np.nan)
    current_age = np.nan
    for i, is_cross in enumerate(cross):
        if is_cross:
            current_age = 0
        elif np.isfinite(current_age):
            current_age += 1
        age[i] = current_age
    result["regime_age"] = age
    for window in (24, 48, 96):
        result[f"low{window}"] = result.low.rolling(window, min_periods=window).min()
        result[f"high{window}"] = result.high.rolling(window, min_periods=window).max()
    return result


def oscillator_warning(frame: pd.DataFrame, spec: V12Spec) -> tuple[np.ndarray, np.ndarray]:
    rsi_values = frame.h1_rsi14_osc.to_numpy("float64")
    kdj_j = frame.h1_kdj_j.to_numpy("float64")
    macd_down = frame.h1_macd_down2.to_numpy("float64")
    macd_up = frame.h1_macd_up2.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    price_edge_long = high >= frame.price_high96.shift(1).to_numpy("float64")
    price_edge_short = low <= frame.price_low96.shift(1).to_numpy("float64")
    rsi_long = rsi_values >= 72
    rsi_short = rsi_values <= 28
    kdj_long = kdj_j >= 100
    kdj_short = kdj_j <= 0
    macd_long = macd_down >= 2
    macd_short = macd_up >= 2
    long_score = rsi_long.astype(int) + kdj_long.astype(int) + macd_long.astype(int)
    short_score = rsi_short.astype(int) + kdj_short.astype(int) + macd_short.astype(int)
    return (
        price_edge_long & (long_score >= spec.osc_min_score),
        price_edge_short & (short_score >= spec.osc_min_score),
    )


def volume_warning_masks(frame: pd.DataFrame, spec: V12Spec) -> tuple[np.ndarray, np.ndarray]:
    if spec.volume_warning_mode == "all":
        return exhaustion_masks(
            frame,
            V7Spec(
                name=spec.name,
                entry_window=0,
                entry_rvol=0.0,
                entry_mode="price",
                exit_rvol=spec.exit_rvol,
                wick_min=spec.wick_min,
                fail_bars=1,
                min_mfe_atr=spec.min_mfe_atr,
                invalid_bars=0,
            ),
        )

    rvol = frame.rvol96.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    atr = frame.atr_pct96.to_numpy("float64")
    upper_wick = frame.upper_wick.to_numpy("float64")
    lower_wick = frame.lower_wick.to_numpy("float64")
    candle_pos = frame.candle_pos.to_numpy("float64")
    new_high = high >= frame.price_high96.shift(1).to_numpy("float64")
    new_low = low <= frame.price_low96.shift(1).to_numpy("float64")
    mfi_lower_high = frame.mfi14.to_numpy("float64") <= (
        frame.mfi_high96.shift(1).to_numpy("float64") - 8
    )
    mfi_higher_low = frame.mfi14.to_numpy("float64") >= (
        frame.mfi_low96.shift(1).to_numpy("float64") + 8
    )
    blowoff_long = new_high & (rvol >= spec.exit_rvol) & (upper_wick >= spec.wick_min) & (candle_pos <= 0.58)
    blowoff_short = new_low & (rvol >= spec.exit_rvol) & (lower_wick >= spec.wick_min) & (candle_pos >= 0.42)
    effort_fail = (rvol >= spec.exit_rvol) & (frame.ret3_abs.to_numpy("float64") <= 0.45 * atr)
    effort_long = effort_fail & (candle_pos <= 0.55)
    effort_short = effort_fail & (candle_pos >= 0.45)

    if spec.volume_warning_mode == "blowoff_only":
        return blowoff_long, blowoff_short
    if spec.volume_warning_mode == "no_mfi_div":
        return blowoff_long | effort_long, blowoff_short | effort_short

    div_rvol = spec.exit_rvol if spec.volume_warning_mode in ("mfi_rvol_exit", "mfi_rvol_exit_wick35") else 1.0
    div_long = new_high & (rvol >= div_rvol) & mfi_lower_high & (close < high)
    div_short = new_low & (rvol >= div_rvol) & mfi_higher_low & (close > low)
    if spec.volume_warning_mode == "mfi_rvol_exit_wick35":
        div_long = div_long & (upper_wick >= 0.35)
        div_short = div_short & (lower_wick >= 0.35)
    if spec.volume_warning_mode in ("mfi_rvol_exit", "mfi_rvol_exit_wick35"):
        return blowoff_long | div_long | effort_long, blowoff_short | div_short | effort_short
    raise ValueError(f"unknown volume warning mode: {spec.volume_warning_mode}")


def metric_result(
    spec: V12Spec,
    equity_curve: pd.Series,
    trades: list[dict[str, Any]],
    *,
    collect_trades: bool,
) -> dict[str, Any]:
    returns = equity_curve.pct_change().fillna(0.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    closed = [trade for trade in trades if trade["exit_reason"] != "open_at_end"]
    pnl_values = np.array([float(trade["pnl_pct"]) for trade in closed], dtype=float)
    hold_values = np.array([int(trade["hold_bars"]) for trade in closed], dtype=float)
    exit_reasons: dict[str, int] = {}
    for trade in closed:
        reason = str(trade["exit_reason"])
        exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
    std = returns.std(ddof=0)
    result: dict[str, Any] = {
        **asdict(spec),
        "return": float(equity_curve.iloc[-1] - 1.0),
        "max_dd": float(drawdown.min()),
        "sharpe": 0.0 if std == 0.0 else float(returns.mean() / std * np.sqrt(PERIODS_PER_YEAR)),
        "trades": len(closed),
        "win_rate": float((pnl_values > 0).mean()) if len(pnl_values) else 0.0,
        "avg_trade_pct": float(pnl_values.mean()) if len(pnl_values) else 0.0,
        "median_trade_pct": float(np.median(pnl_values)) if len(pnl_values) else 0.0,
        "best_trade_pct": float(pnl_values.max()) if len(pnl_values) else 0.0,
        "worst_trade_pct": float(pnl_values.min()) if len(pnl_values) else 0.0,
        "avg_hold_bars": float(hold_values.mean()) if len(hold_values) else 0.0,
        "exit_reasons": exit_reasons,
        "fitness": float((equity_curve.iloc[-1] - 1.0) + drawdown.min() * 1.5),
    }
    if collect_trades:
        result["trades_detail"] = closed
    return result


def reentry_allowed(
    frame: pd.DataFrame,
    i: int,
    direction: int,
    spec: V12Spec,
    last_exit_direction: int,
    last_exit_regime: int,
) -> bool:
    if spec.reentry_mode == "none":
        return True
    regime = 1 if frame.ema_spread.iloc[i] > 0 else -1 if frame.ema_spread.iloc[i] < 0 else 0
    if direction != last_exit_direction or regime != last_exit_regime:
        return True
    window = 48 if spec.reentry_mode == "breakout48" else 96
    if direction > 0:
        level = frame[f"high{window}"].shift(1).iloc[i]
        return bool(np.isfinite(level) and frame.close.iloc[i] >= level)
    level = frame[f"low{window}"].shift(1).iloc[i]
    return bool(np.isfinite(level) and frame.close.iloc[i] <= level)


def entry_filter_allowed(frame: pd.DataFrame, i: int, direction: int, spec: V12Spec) -> bool:
    if spec.entry_max_regime_age > 0:
        age = float(frame.regime_age.iloc[i])
        if np.isfinite(age) and age > spec.entry_max_regime_age:
            return False
    if spec.entry_min_rvol96 > 0:
        rvol = float(frame.rvol96.iloc[i])
        if not np.isfinite(rvol) or rvol < spec.entry_min_rvol96:
            return False
    if spec.entry_max_dist_ema96 > 0:
        ema96 = float(frame.ema96.iloc[i])
        if not np.isfinite(ema96) or ema96 <= 0:
            return False
        dist = direction * (float(frame.close.iloc[i]) / ema96 - 1)
        if dist > spec.entry_max_dist_ema96:
            return False
    if spec.entry_max_move48 > 0 and i >= 48:
        move = direction * (float(frame.close.iloc[i]) / float(frame.close.iloc[i - 48]) - 1)
        if move > spec.entry_max_move48:
            return False
    return True


def confirm_exit(frame: pd.DataFrame, i: int, direction: int, entry_px: float, entry_atr: float, high_water: float, low_water: float, spec: V12Spec) -> bool:
    close = float(frame.close.iloc[i])
    ema21 = float(frame.ema21.iloc[i])
    ema55 = float(frame.ema55.iloc[i])
    ema96 = float(frame.ema96.iloc[i])
    low_level = float(frame[f"low{spec.confirm_window}"].shift(1).iloc[i])
    high_level = float(frame[f"high{spec.confirm_window}"].shift(1).iloc[i])
    if direction > 0:
        ema_break = np.isfinite(ema21) and close < ema21
        ema55_break = np.isfinite(ema55) and close < ema55
        ema96_break = np.isfinite(ema96) and close < ema96
        donchian_break = np.isfinite(low_level) and close < low_level
        trail_break = close < high_water * (1 - spec.trail_atr * entry_atr)
    else:
        ema_break = np.isfinite(ema21) and close > ema21
        ema55_break = np.isfinite(ema55) and close > ema55
        ema96_break = np.isfinite(ema96) and close > ema96
        donchian_break = np.isfinite(high_level) and close > high_level
        trail_break = close > low_water * (1 + spec.trail_atr * entry_atr)
    if spec.confirm_mode == "ema21":
        return ema_break
    if spec.confirm_mode == "ema55":
        return ema55_break
    if spec.confirm_mode == "ema96":
        return ema96_break
    if spec.confirm_mode == "donchian":
        return donchian_break
    if spec.confirm_mode == "atr_trail":
        return trail_break
    if spec.confirm_mode == "ema21_or_donchian":
        return ema_break or donchian_break
    if spec.confirm_mode == "ema55_or_donchian":
        return ema55_break or donchian_break
    if spec.confirm_mode == "ema55_and_donchian":
        return ema55_break and donchian_break
    raise ValueError(f"unknown confirm mode: {spec.confirm_mode}")


def warning_capture_ok(close: float, direction: int, entry_px: float, high_water: float, low_water: float, spec: V12Spec) -> bool:
    return capture_ok(close, direction, entry_px, high_water, low_water, spec.warning_exit_min_capture)


def capture_ok(close: float, direction: int, entry_px: float, high_water: float, low_water: float, min_capture: float) -> bool:
    if min_capture <= 0:
        return True
    if direction > 0:
        mfe = high_water / entry_px - 1
        raw = close / entry_px - 1
    else:
        mfe = 1 - low_water / entry_px
        raw = 1 - close / entry_px
    if mfe <= 0:
        return False
    return raw / mfe >= min_capture


def segment_trend_weak(frame: pd.DataFrame, i: int, direction: int, spec: V12Spec) -> bool:
    mode = spec.segment_exit_mode
    if mode == "none":
        return False
    close = float(frame.close.iloc[i])
    ema21 = float(frame.ema21.iloc[i])
    ema55 = float(frame.ema55.iloc[i])
    ema96 = float(frame.ema96.iloc[i])
    adx = float(frame.adx28.iloc[i])

    def ema_break(level: float) -> bool:
        if not np.isfinite(level):
            return False
        return close < level if direction > 0 else close > level

    adx_weak = np.isfinite(adx) and spec.segment_adx > 0 and adx < spec.segment_adx
    if mode == "adx":
        return adx_weak
    if mode == "ema21":
        return ema_break(ema21)
    if mode == "ema55":
        return ema_break(ema55)
    if mode == "ema96":
        return ema_break(ema96)
    if mode == "ema21_adx":
        return ema_break(ema21) and adx_weak
    if mode == "ema55_adx":
        return ema_break(ema55) and adx_weak
    if mode == "ema96_adx":
        return ema_break(ema96) and adx_weak
    raise ValueError(f"unknown segment exit mode: {mode}")


def hard_trend_invalidated(frame: pd.DataFrame, i: int, direction: int, spec: V12Spec) -> bool:
    mode = spec.hard_exit_mode
    if mode == "none":
        return False
    close = float(frame.close.iloc[i])
    ema96 = float(frame.ema96.iloc[i])

    def ema96_break() -> bool:
        if direction > 0:
            return np.isfinite(ema96) and close < ema96
        return np.isfinite(ema96) and close > ema96

    def swing_break(window: int) -> bool:
        if direction > 0:
            level = float(frame[f"low{window}"].shift(1).iloc[i])
            return np.isfinite(level) and close < level
        level = float(frame[f"high{window}"].shift(1).iloc[i])
        return np.isfinite(level) and close > level

    if mode == "ema96":
        return ema96_break()
    if mode == "swing24":
        return swing_break(24)
    if mode == "swing48":
        return swing_break(48)
    if mode == "swing96":
        return swing_break(96)
    if mode == "ema96_or_swing24":
        return ema96_break() or swing_break(24)
    if mode == "ema96_or_swing48":
        return ema96_break() or swing_break(48)
    if mode == "ema96_or_swing96":
        return ema96_break() or swing_break(96)
    if mode == "ema96_and_swing24":
        return ema96_break() and swing_break(24)
    if mode == "ema96_and_swing48":
        return ema96_break() and swing_break(48)
    if mode == "ema96_and_swing96":
        return ema96_break() and swing_break(96)
    raise ValueError(f"unknown hard exit mode: {mode}")


def run_v12(
    frame: pd.DataFrame,
    spec: V12Spec,
    *,
    start_ts: pd.Timestamp | None = None,
    collect_trades: bool = False,
) -> dict[str, Any]:
    ts_series = pd.to_datetime(frame.ts, utc=True)
    if start_ts is None:
        start_i = 0
    else:
        candidates = np.flatnonzero(ts_series >= start_ts)
        start_i = int(candidates[0]) if len(candidates) else len(frame)
    ts = ts_series.to_numpy()
    open_ = frame.open.to_numpy("float64")
    high = frame.high.to_numpy("float64")
    low = frame.low.to_numpy("float64")
    close = frame.close.to_numpy("float64")
    spread = frame.ema_spread.to_numpy("float64")
    previous_spread = np.r_[np.nan, spread[:-1]]
    adx28 = frame.adx28.to_numpy("float64")
    atr672 = frame.atr_pct672.to_numpy("float64")
    signal = entry_signal(frame, v6_variant())
    volume_long, volume_short = volume_warning_masks(frame, spec)
    osc_long, osc_short = oscillator_warning(frame, spec)

    pos = 0
    allocation = 0.0
    entry_px = 0.0
    entry_ts: pd.Timestamp | None = None
    entry_atr = np.nan
    equity = 1.0
    last_mark = open_[start_i]
    pending_entry = 0
    hold_bars = 0
    bad_bars = 0
    hard_bad_bars = 0
    segment_bad_bars = 0
    mfe_atr = 0.0
    warning_active = False
    warning_reason = ""
    warning_ts: pd.Timestamp | None = None
    high_water = 0.0
    low_water = 0.0
    last_exit_direction = 0
    last_exit_regime = 0
    trades: list[dict[str, Any]] = []
    curve: list[float] = []

    def close_position(i: int, price: float, reason: str) -> None:
        nonlocal pos, allocation, entry_px, entry_ts, entry_atr, equity, last_mark
        nonlocal hold_bars, bad_bars, mfe_atr, warning_active, warning_reason, warning_ts
        nonlocal hard_bad_bars, segment_bad_bars, high_water, low_water, last_exit_direction, last_exit_regime
        equity *= 1 + allocation * pos * (price / last_mark - 1)
        equity *= 1 - TRADE_COST * allocation
        raw_pnl = pos * (price / entry_px - 1)
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[i])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(price),
                "allocation": float(allocation),
                "raw_pnl_pct": float(raw_pnl),
                "pnl_pct": float(allocation * raw_pnl),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "warning_reason": warning_reason,
                "warning_ts": str(warning_ts) if warning_ts is not None else "",
                "exit_reason": reason,
                "equity_after": float(equity),
            }
        )
        last_exit_direction = int(pos)
        last_exit_regime = 1 if spread[i] > 0 else -1 if spread[i] < 0 else 0
        pos = 0
        allocation = 0.0
        entry_px = 0.0
        entry_ts = None
        entry_atr = np.nan
        last_mark = price
        hold_bars = 0
        bad_bars = 0
        hard_bad_bars = 0
        segment_bad_bars = 0
        mfe_atr = 0.0
        warning_active = False
        warning_reason = ""
        warning_ts = None
        high_water = 0.0
        low_water = 0.0

    for i in range(start_i, len(frame)):
        if i > start_i:
            if pos:
                equity *= 1 + allocation * pos * (open_[i] / last_mark - 1)
            last_mark = open_[i]

        if pending_entry and not pos:
            entry_atr = atr672[i - 1] if i > 0 else atr672[i]
            next_allocation = dynamic_allocation(pending_entry, entry_atr)
            if next_allocation > 0:
                pos = pending_entry
                allocation = next_allocation
                entry_px = open_[i] * (1 + SLIPPAGE if pos > 0 else 1 - SLIPPAGE)
                entry_ts = pd.Timestamp(ts[i])
                high_water = high[i]
                low_water = low[i]
                equity *= 1 - TRADE_COST * allocation
                last_mark = entry_px
            pending_entry = 0

        if pos:
            hold_bars += 1
            high_water = max(high_water, high[i])
            low_water = min(low_water, low[i])
            if np.isfinite(entry_atr) and entry_atr > 0:
                if pos > 0:
                    mfe_atr = max(mfe_atr, (high[i] / entry_px - 1) / entry_atr)
                else:
                    mfe_atr = max(mfe_atr, (1 - low[i] / entry_px) / entry_atr)
                stop_px = entry_px * (1 - pos * spec.stop_atr * entry_atr)
                hit_stop = low[i] <= stop_px if pos > 0 else high[i] >= stop_px
                if hit_stop:
                    px = stop_px * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(i, px, "stop_loss")
                    curve.append(float(equity))
                    continue

            equity *= 1 + allocation * pos * (close[i] / last_mark - 1)
            last_mark = close[i]

            opposite_cross = (pos > 0 and spread[i] < 0 <= previous_spread[i]) or (
                pos < 0 and spread[i] > 0 >= previous_spread[i]
            )
            if opposite_cross:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, "opposite_cross")
                curve.append(float(equity))
                continue

            hard_bad = hard_trend_invalidated(frame, i, pos, spec)
            hard_bad_bars = hard_bad_bars + 1 if hard_bad else 0
            if hard_bad_bars >= spec.hard_exit_bars:
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, f"hard_{spec.hard_exit_mode}")
                curve.append(float(equity))
                continue

            volume_warning = (pos > 0 and volume_long[i]) or (pos < 0 and volume_short[i])
            osc_warning = (pos > 0 and osc_long[i]) or (pos < 0 and osc_short[i])
            if mfe_atr >= spec.min_mfe_atr and not warning_active:
                if spec.warning_source == "volume" and volume_warning:
                    warning_active = True
                    warning_reason = "volume"
                    warning_ts = pd.Timestamp(ts[i])
                elif spec.warning_source == "osc" and osc_warning:
                    warning_active = True
                    warning_reason = "osc"
                    warning_ts = pd.Timestamp(ts[i])
                elif spec.warning_source == "either" and (volume_warning or osc_warning):
                    warning_active = True
                    warning_reason = "volume" if volume_warning else "osc"
                    warning_ts = pd.Timestamp(ts[i])

            if (
                warning_active
                and confirm_exit(frame, i, pos, entry_px, entry_atr, high_water, low_water, spec)
                and warning_capture_ok(close[i], pos, entry_px, high_water, low_water, spec)
            ):
                exit_i = min(i + 1, len(frame) - 1)
                px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                close_position(exit_i, px, f"warning_confirm_{warning_reason}")
                curve.append(float(equity))
                continue

            if spec.segment_exit_mode != "none" and mfe_atr >= spec.segment_min_mfe_atr:
                segment_bad = segment_trend_weak(frame, i, pos, spec) and capture_ok(
                    close[i],
                    pos,
                    entry_px,
                    high_water,
                    low_water,
                    spec.segment_exit_min_capture,
                )
                segment_bad_bars = segment_bad_bars + 1 if segment_bad else 0
                if segment_bad_bars >= spec.segment_bars:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, f"segment_{spec.segment_exit_mode}")
                    curve.append(float(equity))
                    continue

            if spec.fallback_adx > 0:
                trend_bad = bool(adx28[i] < spec.fallback_adx)
                bad_bars = bad_bars + 1 if trend_bad else 0
                if bad_bars >= spec.fallback_bars:
                    exit_i = min(i + 1, len(frame) - 1)
                    px = open_[exit_i] * (1 - SLIPPAGE if pos > 0 else 1 + SLIPPAGE)
                    close_position(exit_i, px, "fallback_trend_break")
                    curve.append(float(equity))
                    continue

        if not pos and signal[i]:
            direction = int(signal[i])
            if reentry_allowed(frame, i, direction, spec, last_exit_direction, last_exit_regime) and entry_filter_allowed(frame, i, direction, spec):
                pending_entry = direction

        curve.append(float(equity))

    if pos:
        trades.append(
            {
                "spec": spec.name,
                "entry_ts": str(entry_ts),
                "exit_ts": str(pd.Timestamp(ts[-1])),
                "direction": int(pos),
                "side": "long" if pos > 0 else "short",
                "entry_price": float(entry_px),
                "exit_price": float(close[-1]),
                "allocation": float(allocation),
                "raw_pnl_pct": float(pos * (close[-1] / entry_px - 1)),
                "pnl_pct": float(allocation * pos * (close[-1] / entry_px - 1)),
                "hold_bars": int(hold_bars),
                "mfe_atr": float(mfe_atr),
                "warning_reason": warning_reason,
                "warning_ts": str(warning_ts) if warning_ts is not None else "",
                "exit_reason": "open_at_end",
                "equity_after": float(equity),
            }
        )

    equity_curve = pd.Series(curve, index=pd.DatetimeIndex(ts[start_i : start_i + len(curve)]))
    return metric_result(spec, equity_curve, trades, collect_trades=collect_trades)


def main() -> None:
    raw = load_hype_data_lake()
    frame = add_structure_features(add_oscillator_features(add_volume_features(build_features(raw))))
    specs = build_v12_specs()
    rankings = [run_v12(frame, spec) for spec in specs]
    ranking_frame = pd.DataFrame(rankings).sort_values(["fitness", "return", "sharpe"], ascending=False)
    top_spec = next(spec for spec in specs if spec.name == str(ranking_frame.iloc[0]["name"]))
    top_result = run_v12(frame, top_spec, collect_trades=True)
    top_trades = pd.DataFrame(top_result.pop("trades_detail"))

    v6 = run_variant_dynamic_3x(frame, v6_variant())
    v8_clean = run_v8(frame, v8_clean_spec())
    report = {
        "data": {
            "start": str(pd.Timestamp(frame.ts.iloc[0])),
            "end": str(pd.Timestamp(frame.ts.iloc[-1])),
            "bars": int(len(frame)),
        },
        "v6_baseline": v6,
        "v8_clean_wick055": v8_clean,
        "top_v12": top_result,
        "ranking_top20": ranking_frame.head(20).to_dict(orient="records"),
        "notes": [
            "V12 tests warning/confirm exits instead of immediate volume or oscillator exits.",
            "Reentry modes optionally require a fresh 48/96-bar structural breakout inside the same EMA regime.",
            "Confirm modes are EMA21 break, Donchian break, ATR trail, or EMA21/Donchian union.",
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    ranking_frame.to_csv(RANKING_PATH, index=False)
    top_trades.to_csv(TOP_TRADES_PATH, index=False)
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"top_trades={TOP_TRADES_PATH}")
    print(
        "top="
        f"{top_result['name']} return={top_result['return']:.4f} "
        f"dd={top_result['max_dd']:.4f} trades={top_result['trades']} "
        f"win={top_result['win_rate']:.4f}"
    )
    print(
        "v8_clean="
        f"return={v8_clean['return']:.4f} dd={v8_clean['max_dd']:.4f} "
        f"trades={v8_clean['trades']} win={v8_clean['win_rate']:.4f}"
    )


if __name__ == "__main__":
    main()
