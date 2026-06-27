from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


FAMILY_ROOT = Path("research/hype/1m-ema-crossover")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"
RUN_DATE = "2026-06-27"

REPORT_PATH = ARTIFACT_ROOT / f"hype_1m_ema_v35_filter_overlay_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_1m_ema_v35_filter_overlay_summary_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_1m_ema_v35_filter_overlay_slices_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_1m_ema_v35_filter_overlay_monthly_{RUN_DATE}.csv"
TOP_TRADES_PATH = ARTIFACT_ROOT / f"hype_1m_ema_v35_filter_overlay_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-1m-ema-v35-filter-overlay-{RUN_DATE}.md"

MIN_PAPER_TRADES = 20
MIN_PAPER_PROFIT_FACTOR = 1.10
MIN_PAPER_WIN_RATE = 0.48
MAX_PAPER_DRAWDOWN = -0.20


@dataclass(frozen=True, slots=True)
class OverlayFilter:
    name: str
    require_m15_ema: bool
    require_m15_adx28: bool
    long_m15_adx_min: float
    short_m15_adx_min: float
    require_m15_volume: bool
    long_volume_surge_min: float
    short_volume_surge_min: float
    require_h1_confirm: bool
    h1_long_adx_min: float
    require_m15_di: bool
    require_early_adx14: bool
    early_adx14_min: float
    require_1m_adx: bool
    min_1m_adx14: float


@dataclass(frozen=True, slots=True)
class ExitSpec:
    name: str
    stop_atr: float
    arm_dev_atr: float
    trail_drawdown_atr: float
    partial_dev_atr: float | None
    partial_fraction: float
    use_two_closes_fast_break: bool
    use_weakening_fast_gap: bool
    max_hold_bars: int


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    name: str
    fast_ema: int
    slow_ema: int
    overlay: OverlayFilter
    exit_spec: ExitSpec


def load_deviation_module() -> Any:
    path = Path(__file__).with_name("research_hype_1m_ema_deviation_take_profit.py")
    spec = importlib.util.spec_from_file_location("hype_1m_deviation_tp", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import helper module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hype_1m_deviation_tp"] = module
    spec.loader.exec_module(module)
    return module


BASE = load_deviation_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test HYPE-1M-EMA-Crossover signals with HYPE-EMA-TB-V35-style strength filters."
    )
    parser.add_argument(
        "--ema-pairs",
        type=str,
        default="8:21,13:48,21:55,21:72,21:96,30:120",
        help="Comma-separated fast:slow EMA pairs.",
    )
    parser.add_argument("--exposures", type=str, default="1,2,3")
    parser.add_argument("--top-keep", type=int, default=80)
    parser.add_argument("--progress-every", type=int, default=25)
    return parser.parse_args()


def parse_ema_pairs(text: str) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        fast_text, slow_text = item.split(":", maxsplit=1)
        fast = int(fast_text)
        slow = int(slow_text)
        if fast <= 0 or slow <= fast:
            raise ValueError(f"invalid EMA pair: {item}")
        pairs.append((fast, slow))
    if not pairs:
        raise ValueError("no EMA pairs were provided")
    return pairs


def parse_float_list(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("empty float list")
    return values


def resample_ohlcv(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    indexed = frame.set_index("ts")[["open", "high", "low", "close", "volume"]]
    out = indexed.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    return out.dropna(subset=["open", "high", "low", "close"])


def align_known_to_1m(source: pd.DataFrame, one_minute_ts: pd.Series, known_delay: pd.Timedelta) -> pd.DataFrame:
    known = source.copy()
    known.index = known.index + known_delay
    target = pd.DatetimeIndex(one_minute_ts)
    aligned = known.reindex(target, method="ffill")
    aligned.index = one_minute_ts.index
    return aligned


def build_v35_overlay_features(frame_1m: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=frame_1m.index)
    m15 = resample_ohlcv(frame_1m, "15min")
    h1 = resample_ohlcv(frame_1m, "1h")

    m15_close = m15["close"].astype("float64")
    m15_high = m15["high"].astype("float64")
    m15_low = m15["low"].astype("float64")
    m15_volume = m15["volume"].astype("float64")
    m15_feat = pd.DataFrame(index=m15.index)
    m15_feat["m15_ema96"] = m15_close.ewm(span=96, adjust=False, min_periods=96).mean()
    m15_feat["m15_ema384"] = m15_close.ewm(span=384, adjust=False, min_periods=384).mean()
    m15_feat["m15_ema_spread"] = m15_feat["m15_ema96"] / m15_feat["m15_ema384"].replace(0.0, np.nan) - 1.0
    m15_feat["m15_adx28"], m15_feat["m15_pdi28"], m15_feat["m15_mdi28"] = BASE.adx_di(
        m15_high, m15_low, m15_close, 28
    )
    m15_feat["m15_adx14"], m15_feat["m15_pdi14"], m15_feat["m15_mdi14"] = BASE.adx_di(
        m15_high, m15_low, m15_close, 14
    )
    m15_feat["m15_adx14_slope"] = m15_feat["m15_adx14"] - m15_feat["m15_adx14"].shift(1)
    m15_feat["m15_volume_surge"] = m15_volume / m15_volume.rolling(192, min_periods=192).mean().replace(0.0, np.nan) - 1.0
    aligned_m15 = align_known_to_1m(m15_feat, frame_1m["ts"], pd.Timedelta(minutes=15))

    h1_close = h1["close"].astype("float64")
    h1_high = h1["high"].astype("float64")
    h1_low = h1["low"].astype("float64")
    h1_feat = pd.DataFrame(index=h1.index)
    h1_feat["h1_adx21"], h1_feat["h1_pdi21"], h1_feat["h1_mdi21"] = BASE.adx_di(h1_high, h1_low, h1_close, 21)
    h1_feat["h1_ema24"] = h1_close.ewm(span=24, adjust=False, min_periods=24).mean()
    h1_feat["h1_ema36"] = h1_close.ewm(span=36, adjust=False, min_periods=36).mean()
    h1_feat["h1_ema96"] = h1_close.ewm(span=96, adjust=False, min_periods=96).mean()
    h1_feat["h1_ema_spread24"] = h1_feat["h1_ema24"] / h1_feat["h1_ema96"].replace(0.0, np.nan) - 1.0
    h1_feat["h1_ema_spread36"] = h1_feat["h1_ema36"] / h1_feat["h1_ema96"].replace(0.0, np.nan) - 1.0
    aligned_h1 = align_known_to_1m(h1_feat, frame_1m["ts"], pd.Timedelta(hours=1))

    for column in aligned_m15.columns:
        features[column] = aligned_m15[column].to_numpy("float64")
    for column in aligned_h1.columns:
        features[column] = aligned_h1[column].to_numpy("float64")
    return features


def overlay_filters() -> list[OverlayFilter]:
    return [
        OverlayFilter(
            name="none_reference",
            require_m15_ema=False,
            require_m15_adx28=False,
            long_m15_adx_min=0.0,
            short_m15_adx_min=0.0,
            require_m15_volume=False,
            long_volume_surge_min=-99.0,
            short_volume_surge_min=-99.0,
            require_h1_confirm=False,
            h1_long_adx_min=0.0,
            require_m15_di=False,
            require_early_adx14=False,
            early_adx14_min=0.0,
            require_1m_adx=False,
            min_1m_adx14=0.0,
        ),
        OverlayFilter(
            name="v35_full",
            require_m15_ema=True,
            require_m15_adx28=True,
            long_m15_adx_min=28.0,
            short_m15_adx_min=36.0,
            require_m15_volume=True,
            long_volume_surge_min=0.25,
            short_volume_surge_min=0.50,
            require_h1_confirm=True,
            h1_long_adx_min=18.0,
            require_m15_di=False,
            require_early_adx14=False,
            early_adx14_min=0.0,
            require_1m_adx=False,
            min_1m_adx14=0.0,
        ),
        OverlayFilter(
            name="v35_no_volume",
            require_m15_ema=True,
            require_m15_adx28=True,
            long_m15_adx_min=28.0,
            short_m15_adx_min=36.0,
            require_m15_volume=False,
            long_volume_surge_min=-99.0,
            short_volume_surge_min=-99.0,
            require_h1_confirm=True,
            h1_long_adx_min=18.0,
            require_m15_di=False,
            require_early_adx14=False,
            early_adx14_min=0.0,
            require_1m_adx=False,
            min_1m_adx14=0.0,
        ),
        OverlayFilter(
            name="v35_relaxed_adx_volume",
            require_m15_ema=True,
            require_m15_adx28=True,
            long_m15_adx_min=24.0,
            short_m15_adx_min=32.0,
            require_m15_volume=True,
            long_volume_surge_min=0.0,
            short_volume_surge_min=0.25,
            require_h1_confirm=True,
            h1_long_adx_min=16.0,
            require_m15_di=False,
            require_early_adx14=False,
            early_adx14_min=0.0,
            require_1m_adx=False,
            min_1m_adx14=0.0,
        ),
        OverlayFilter(
            name="v35_early_adx14_di",
            require_m15_ema=True,
            require_m15_adx28=False,
            long_m15_adx_min=0.0,
            short_m15_adx_min=0.0,
            require_m15_volume=True,
            long_volume_surge_min=0.0,
            short_volume_surge_min=0.25,
            require_h1_confirm=True,
            h1_long_adx_min=18.0,
            require_m15_di=True,
            require_early_adx14=True,
            early_adx14_min=35.0,
            require_1m_adx=False,
            min_1m_adx14=0.0,
        ),
        OverlayFilter(
            name="v35_full_plus_1m_adx20",
            require_m15_ema=True,
            require_m15_adx28=True,
            long_m15_adx_min=28.0,
            short_m15_adx_min=36.0,
            require_m15_volume=True,
            long_volume_surge_min=0.25,
            short_volume_surge_min=0.50,
            require_h1_confirm=True,
            h1_long_adx_min=18.0,
            require_m15_di=False,
            require_early_adx14=False,
            early_adx14_min=0.0,
            require_1m_adx=True,
            min_1m_adx14=20.0,
        ),
    ]


def exit_specs() -> list[ExitSpec]:
    return [
        ExitSpec(
            name="devtrail_arm2_dd1p5_sl1p5",
            stop_atr=1.5,
            arm_dev_atr=2.0,
            trail_drawdown_atr=1.5,
            partial_dev_atr=None,
            partial_fraction=0.0,
            use_two_closes_fast_break=False,
            use_weakening_fast_gap=False,
            max_hold_bars=1440,
        ),
        ExitSpec(
            name="devtrail_arm2p2_dd1p8_sl1p5",
            stop_atr=1.5,
            arm_dev_atr=2.2,
            trail_drawdown_atr=1.8,
            partial_dev_atr=None,
            partial_fraction=0.0,
            use_two_closes_fast_break=False,
            use_weakening_fast_gap=False,
            max_hold_bars=1440,
        ),
        ExitSpec(
            name="exhaust_arm2p2_dd1p8_sl1p5",
            stop_atr=1.5,
            arm_dev_atr=2.2,
            trail_drawdown_atr=1.8,
            partial_dev_atr=None,
            partial_fraction=0.0,
            use_two_closes_fast_break=True,
            use_weakening_fast_gap=True,
            max_hold_bars=1440,
        ),
        ExitSpec(
            name="staged_p2p2_dd1p5_sl1p5",
            stop_atr=1.5,
            arm_dev_atr=2.0,
            trail_drawdown_atr=1.5,
            partial_dev_atr=2.2,
            partial_fraction=0.5,
            use_two_closes_fast_break=False,
            use_weakening_fast_gap=False,
            max_hold_bars=1440,
        ),
    ]


def build_configs(ema_pairs: list[tuple[int, int]]) -> list[StrategyConfig]:
    configs: list[StrategyConfig] = []
    for fast, slow in ema_pairs:
        for overlay in overlay_filters():
            for exit_spec in exit_specs():
                name = f"HYPE_1M_EMA_V35_OVERLAY_FAST{fast}_SLOW{slow}_{overlay.name}_{exit_spec.name}"
                configs.append(StrategyConfig(name=name, fast_ema=fast, slow_ema=slow, overlay=overlay, exit_spec=exit_spec))
    return configs


def finite(value: float, default: float = 0.0) -> float:
    return float(value) if np.isfinite(value) else default


def passes_overlay(frame: pd.DataFrame, overlay_features: pd.DataFrame, cfg: StrategyConfig, signal_i: int, side: int) -> bool:
    overlay = cfg.overlay
    if overlay.require_1m_adx and finite(float(frame["adx14"].iloc[signal_i])) < overlay.min_1m_adx14:
        return False

    row = overlay_features.iloc[signal_i]
    if overlay.require_m15_ema:
        spread = finite(float(row["m15_ema_spread"]), default=np.nan)
        if not np.isfinite(spread) or side * spread <= 0:
            return False
    if overlay.require_m15_adx28:
        adx = finite(float(row["m15_adx28"]), default=np.nan)
        threshold = overlay.long_m15_adx_min if side > 0 else overlay.short_m15_adx_min
        if not np.isfinite(adx) or adx < threshold:
            return False
    if overlay.require_m15_di:
        pdi = finite(float(row["m15_pdi14"]), default=np.nan)
        mdi = finite(float(row["m15_mdi14"]), default=np.nan)
        if not np.isfinite(pdi) or not np.isfinite(mdi):
            return False
        if side > 0 and pdi <= mdi:
            return False
        if side < 0 and mdi <= pdi:
            return False
    if overlay.require_early_adx14:
        adx14 = finite(float(row["m15_adx14"]), default=np.nan)
        adx14_slope = finite(float(row["m15_adx14_slope"]), default=np.nan)
        if not np.isfinite(adx14) or not np.isfinite(adx14_slope):
            return False
        if adx14 < overlay.early_adx14_min or adx14_slope <= 0:
            return False
    if overlay.require_m15_volume:
        volume_surge = finite(float(row["m15_volume_surge"]), default=np.nan)
        threshold = overlay.long_volume_surge_min if side > 0 else overlay.short_volume_surge_min
        if not np.isfinite(volume_surge) or volume_surge < threshold:
            return False
    if overlay.require_h1_confirm:
        if side > 0:
            h1_adx = finite(float(row["h1_adx21"]), default=np.nan)
            h1_pdi = finite(float(row["h1_pdi21"]), default=np.nan)
            h1_mdi = finite(float(row["h1_mdi21"]), default=np.nan)
            if not np.isfinite(h1_adx) or h1_adx <= overlay.h1_long_adx_min or h1_pdi <= h1_mdi:
                return False
        else:
            h1_spread = finite(float(row["h1_ema_spread24"]), default=np.nan)
            if not np.isfinite(h1_spread) or h1_spread >= 0:
                return False
    return True


def simulate_trades(frame: pd.DataFrame, overlay_features: pd.DataFrame, cfg: StrategyConfig) -> list[Any]:
    signal = BASE.cross_signal(frame, cfg)
    signal_i = np.flatnonzero(signal)
    if len(signal_i) == 0:
        return []

    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    fast = frame[f"ema{cfg.fast_ema}"].to_numpy("float64")
    slow = frame[f"ema{cfg.slow_ema}"].to_numpy("float64")
    n = len(frame)
    trades: list[Any] = []
    exit_spec = cfg.exit_spec

    for pos, sig_i in enumerate(signal_i):
        side = int(signal[sig_i])
        entry_i = int(sig_i + 1)
        if side == 0 or entry_i >= n - 1:
            continue
        if not passes_overlay(frame, overlay_features, cfg, int(sig_i), side):
            continue

        next_signal_i = int(signal_i[pos + 1]) if pos + 1 < len(signal_i) else n - 2
        forced_exit_i = min(next_signal_i + 1, entry_i + exit_spec.max_hold_bars, n - 1)
        forced_reason = "opposite_cross" if forced_exit_i == next_signal_i + 1 else "max_hold"
        if forced_exit_i <= entry_i:
            continue

        entry_price = float(open_[entry_i])
        atr_at_signal = float(atr[sig_i])
        if not np.isfinite(atr_at_signal) or atr_at_signal <= 0:
            continue
        stop_price = entry_price - side * exit_spec.stop_atr * atr_at_signal

        remaining = 1.0
        legs: list[tuple[float, int, float, str]] = []
        armed = False
        partial_taken = False
        partial_i: int | None = None
        highest = entry_price
        lowest = entry_price
        mae = 0.0
        mfe = 0.0
        max_dev = -math.inf
        max_drawdown_after_arm = 0.0
        final_exit_i = forced_exit_i
        final_reason = forced_reason

        for bar_i in range(entry_i, forced_exit_i):
            stopped, stop_fill, stop_reason = BASE.touched_stop(
                float(open_[bar_i]), float(high[bar_i]), float(low[bar_i]), stop_price, side
            )
            if stopped:
                BASE.add_exit_leg(legs, remaining, int(bar_i), float(stop_fill), stop_reason)
                remaining = 0.0
                final_exit_i = int(bar_i)
                final_reason = stop_reason
                break

            if side > 0:
                highest = max(highest, float(high[bar_i]))
                mae = min(mae, float(low[bar_i]) / entry_price - 1.0)
                mfe = max(mfe, float(high[bar_i]) / entry_price - 1.0)
            else:
                lowest = min(lowest, float(low[bar_i]))
                mae = min(mae, entry_price / float(high[bar_i]) - 1.0)
                mfe = max(mfe, entry_price / float(low[bar_i]) - 1.0)

            atr_now = float(atr[bar_i])
            if not np.isfinite(atr_now) or atr_now <= 0 or not np.isfinite(fast[bar_i]):
                continue

            dev_atr = side * (float(close[bar_i]) - float(fast[bar_i])) / atr_now
            max_dev = max(max_dev, dev_atr)
            if dev_atr >= exit_spec.arm_dev_atr:
                armed = True

            if side > 0:
                drawdown_atr = (highest - float(close[bar_i])) / atr_now
                two_closes_break = (
                    bar_i > 0
                    and float(close[bar_i]) < float(fast[bar_i])
                    and float(close[bar_i - 1]) < float(fast[bar_i - 1])
                )
            else:
                drawdown_atr = (float(close[bar_i]) - lowest) / atr_now
                two_closes_break = (
                    bar_i > 0
                    and float(close[bar_i]) > float(fast[bar_i])
                    and float(close[bar_i - 1]) > float(fast[bar_i - 1])
                )
            if armed:
                max_drawdown_after_arm = max(max_drawdown_after_arm, drawdown_atr)

            weakening = False
            if bar_i > 0 and np.isfinite(fast[bar_i - 1]) and np.isfinite(slow[bar_i - 1]):
                fast_slope = side * (float(fast[bar_i]) - float(fast[bar_i - 1]))
                gap_now = float(fast[bar_i]) - float(slow[bar_i])
                gap_prev = float(fast[bar_i - 1]) - float(slow[bar_i - 1])
                weakening = fast_slope < 0 and side * (gap_now - gap_prev) < 0

            full_exit_reason: str | None = None
            if armed and drawdown_atr >= exit_spec.trail_drawdown_atr:
                full_exit_reason = "armed_peak_drawdown_next_open"
            elif armed and exit_spec.use_two_closes_fast_break and two_closes_break:
                full_exit_reason = "armed_two_closes_fast_break_next_open"
            elif armed and exit_spec.use_weakening_fast_gap and weakening:
                full_exit_reason = "armed_fast_gap_weakening_next_open"

            next_open_i = bar_i + 1
            if full_exit_reason is not None and next_open_i <= forced_exit_i and next_open_i < n:
                BASE.add_exit_leg(legs, remaining, int(next_open_i), float(open_[next_open_i]), full_exit_reason)
                remaining = 0.0
                final_exit_i = int(next_open_i)
                final_reason = full_exit_reason
                break

            can_take_partial = (
                exit_spec.partial_dev_atr is not None
                and not partial_taken
                and dev_atr >= exit_spec.partial_dev_atr
                and remaining > exit_spec.partial_fraction
                and next_open_i < forced_exit_i
                and next_open_i < n
            )
            if can_take_partial:
                BASE.add_exit_leg(
                    legs,
                    exit_spec.partial_fraction,
                    int(next_open_i),
                    float(open_[next_open_i]),
                    "extension_partial_next_open",
                )
                remaining -= exit_spec.partial_fraction
                partial_taken = True
                partial_i = int(next_open_i)

        if remaining > 0:
            BASE.add_exit_leg(legs, remaining, int(forced_exit_i), float(open_[forced_exit_i]), forced_reason)
            final_exit_i = int(forced_exit_i)
            final_reason = forced_reason

        raw_ret = 0.0
        net_ret = 0.0
        final_exit_price = float(open_[final_exit_i])
        for fraction, exit_i, exit_price, reason in legs:
            raw_leg = BASE.leg_raw_return(side, entry_price, exit_price)
            raw_ret += fraction * raw_leg
            net_ret += fraction * (raw_leg - BASE.ROUND_TRIP_COST)
            if exit_i == final_exit_i:
                final_exit_price = exit_price
                final_reason = reason

        trades.append(
            BASE.Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[final_exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                final_exit_price=float(final_exit_price),
                exit_reason=final_reason,
                bars_held=max(int(final_exit_i - entry_i), 0),
                raw_ret_1x=float(raw_ret),
                net_ret_1x=float(net_ret),
                mae_1x=float(mae - BASE.ROUND_TRIP_COST),
                mfe_1x=float(mfe),
                max_dev_atr=float(max_dev) if np.isfinite(max_dev) else 0.0,
                max_drawdown_atr_after_arm=float(max_drawdown_after_arm),
                armed=armed,
                partial_taken=partial_taken,
                partial_fraction=float(exit_spec.partial_fraction if partial_taken else 0.0),
                partial_ts=pd.Timestamp(ts_ns[partial_i], unit="ns", tz="UTC") if partial_i is not None else None,
                adx14=finite(float(frame["adx14"].iloc[sig_i])),
                atr_bps=finite(float(frame["atr_bps"].iloc[sig_i])),
                slow_slope_atr=0.0,
            )
        )
    return trades


def row_for_config(frame: pd.DataFrame, cfg: StrategyConfig, trades: list[Any], slices: list[dict[str, Any]], exposure: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    row: dict[str, Any] = {
        "name": cfg.name,
        "fast_ema": cfg.fast_ema,
        "slow_ema": cfg.slow_ema,
        "overlay_filter": cfg.overlay.name,
        "exit_model": cfg.exit_spec.name,
        "exposure": exposure,
        "cost_bps_round_trip": BASE.ROUND_TRIP_COST * 10_000.0,
    }
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        name = str(item["name"])
        start = pd.Timestamp(item["start"])
        end = pd.Timestamp(item["end"])
        window_trades = BASE.trades_in_window(trades, start, end)
        period_days = max((end - start).total_seconds() / 86_400.0, 1 / 1440.0)
        metrics = BASE.metrics_for_trades(window_trades, exposure=exposure, period_days=period_days)
        for key, value in metrics.items():
            row[f"{name}_{key}"] = value
        slice_rows.append(
            {
                "name": cfg.name,
                "fast_ema": cfg.fast_ema,
                "slow_ema": cfg.slow_ema,
                "overlay_filter": cfg.overlay.name,
                "exit_model": cfg.exit_spec.name,
                "exposure": exposure,
                "slice": name,
                "start": start,
                "end": end,
                **metrics,
            }
        )
    row["exit_reason_counts"] = json.dumps(BASE.exit_reason_counts(trades), ensure_ascii=False, sort_keys=True)
    row["score"] = score_row(row)
    row["paper_candidate_pass"] = paper_candidate_pass(row)
    return row, slice_rows


def score_row(row: dict[str, Any]) -> float:
    full_ann = max(float(row["full_annualized_multiple"]), 1e-9)
    full_pf = float(row["full_profit_factor"])
    if not np.isfinite(full_pf):
        full_pf = 10.0
    val_ret = float(row.get("val_next_20pct_total_return", 0.0))
    fwd_ret = float(row.get("fwd_last_20pct_total_return", 0.0))
    recent_ret = float(row.get("recent_30d_total_return", 0.0))
    dd_penalty = max(0.0, abs(float(row["full_max_dd"])) - abs(MAX_PAPER_DRAWDOWN)) * 8.0
    low_trade_penalty = max(0, MIN_PAPER_TRADES - int(row["full_trades"])) * 0.08
    return (
        math.log(full_ann)
        + min(full_pf, 5.0) * 0.7
        + float(row["full_win_rate"])
        + val_ret * 2.0
        + fwd_ret * 3.0
        + recent_ret
        - dd_penalty
        - low_trade_penalty
    )


def paper_candidate_pass(row: dict[str, Any]) -> bool:
    return (
        int(row["full_trades"]) >= MIN_PAPER_TRADES
        and float(row["full_total_return"]) > 0
        and float(row["full_profit_factor"]) >= MIN_PAPER_PROFIT_FACTOR
        and float(row["full_win_rate"]) >= MIN_PAPER_WIN_RATE
        and float(row["full_max_dd"]) >= MAX_PAPER_DRAWDOWN
        and int(row["val_next_20pct_trades"]) >= 2
        and int(row["fwd_last_20pct_trades"]) >= 2
        and float(row["val_next_20pct_total_return"]) >= 0
        and float(row["fwd_last_20pct_total_return"]) >= 0
        and float(row["recent_30d_total_return"]) >= 0
    )


def monthly_rows(trades_by_config: dict[str, list[Any]], top_rows: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in top_rows.to_dict(orient="records"):
        name = str(item["name"])
        exposure = float(item["exposure"])
        trades = trades_by_config.get(name, [])
        by_month: dict[str, list[Any]] = {}
        for trade in trades:
            by_month.setdefault(trade.entry_ts.strftime("%Y-%m"), []).append(trade)
        for month, month_trades in sorted(by_month.items()):
            start = min(trade.entry_ts for trade in month_trades)
            end = max(trade.exit_ts for trade in month_trades) + pd.Timedelta(minutes=1)
            period_days = max((end - start).total_seconds() / 86_400.0, 1 / 1440.0)
            rows.append(
                {
                    "name": name,
                    "fast_ema": int(item["fast_ema"]),
                    "slow_ema": int(item["slow_ema"]),
                    "overlay_filter": str(item["overlay_filter"]),
                    "exit_model": str(item["exit_model"]),
                    "exposure": exposure,
                    "month": month,
                    **BASE.metrics_for_trades(month_trades, exposure=exposure, period_days=period_days),
                }
            )
    return rows


def best_by_group(summary: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if summary.empty:
        return summary
    return (
        summary.sort_values(["paper_candidate_pass", "score"], ascending=[False, False])
        .groupby(group_columns, as_index=False)
        .head(1)
        .reset_index(drop=True)
    )


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 15) -> list[str]:
    if frame.empty:
        return ["_none_"]
    display = frame.head(limit).copy()
    rows = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, item in display.iterrows():
        values: list[str] = []
        for column in columns:
            value = item[column]
            if isinstance(value, (float, np.floating)):
                if column.endswith("return") or column.endswith("max_dd") or column.endswith("win_rate"):
                    values.append(f"`{BASE.pct(float(value))}`")
                elif "annualized" in column:
                    values.append(f"`{BASE.mult(float(value))}`")
                elif "profit_factor" in column:
                    values.append(f"`{BASE.num(float(value))}`")
                else:
                    values.append(f"`{BASE.num(float(value))}`")
            else:
                values.append(f"`{value}`")
        rows.append("| " + " | ".join(values) + " |")
    return rows


def render_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any], args: argparse.Namespace) -> str:
    paper = summary.loc[summary["paper_candidate_pass"].eq(True)].sort_values("score", ascending=False)
    top = paper.head(20) if not paper.empty else summary.sort_values("score", ascending=False).head(20)
    ema_21_96_focus = summary.loc[(summary["fast_ema"] == 21) & (summary["slow_ema"] == 96)].sort_values(
        "full_total_return", ascending=False
    )
    pair_surface = best_by_group(summary, ["fast_ema", "slow_ema"]).sort_values("score", ascending=False)
    filter_surface = best_by_group(summary, ["overlay_filter"]).sort_values("score", ascending=False)

    table_columns = [
        "name",
        "exposure",
        "full_trades",
        "full_total_return",
        "full_annualized_multiple",
        "full_max_dd",
        "full_win_rate",
        "full_profit_factor",
        "fwd_last_20pct_total_return",
        "recent_30d_total_return",
    ]
    surface_columns = [
        "fast_ema",
        "slow_ema",
        "overlay_filter",
        "exit_model",
        "exposure",
        "full_trades",
        "full_total_return",
        "full_max_dd",
        "full_profit_factor",
        "fwd_last_20pct_total_return",
    ]

    lines = [
        f"# HYPE 1m EMA V35 filter overlay diagnostic {RUN_DATE}",
        "",
        "Family id: `HYPE-1M-EMA-Crossover`",
        "",
        "Reference family: `HYPE-EMA-Trend-Breakout-V35` (`15m-ema-trend-breakout`). This is a transfer diagnostic, not a relabeling of V35.",
        "",
        "## 数据质量",
        "",
        f"- Normalized OHLCV: `{quality['normalized_file_count']}` 个日分区，`{quality['rows']}` 根 K。",
        f"- Raw OHLCV: `{quality['raw_ohlcv_file_count']}` 个日分区，`{quality['raw_rows']}` 根 K。",
        f"- 时间范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 连续性：expected `{quality['expected_bars']}`，missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`。",
        f"- OHLC/VWAP/volume hard violations：`{quality['ohlcv_violations']}`。",
        "",
        "## 迁移规则",
        "",
        "- 1m 入场仍然是快 EMA 上穿慢 EMA 下一根 open 做多、下穿下一根 open 做空。",
        "- V35 overlay 使用已闭合的 15m/1h 数据，不使用当前未收完的 15m 或 1h K。",
        "- `v35_full`：15m EMA96/384 同向、15m ADX28 多头 >= 28 / 空头 >= 36、15m volume_surge 多头 >= 0.25 / 空头 >= 0.50、1h 确认同向。",
        "- `v35_no_volume`、`v35_relaxed_adx_volume`、`v35_early_adx14_di` 用来检查是否是 V35 门槛过严导致样本不足。",
        "- 出场沿用上一轮偏离止盈状态机：fast-EMA 偏离 arm，然后用高低点回撤、快线失守或分批止盈退出。",
        "",
        "## 搜索规模",
        "",
        f"- EMA pairs: `{args.ema_pairs}`。",
        f"- Exposures: `{args.exposures}`。",
        f"- Config rows including overlay filters and exposure: `{len(summary)}`。",
        f"- Paper gate: trades >= `{MIN_PAPER_TRADES}`，PF >= `{MIN_PAPER_PROFIT_FACTOR}`，win >= `{MIN_PAPER_WIN_RATE:.0%}`，maxDD >= `{MAX_PAPER_DRAWDOWN:.0%}`，validation/forward/recent slices 不得亏损。",
        f"- 通过 paper gate：`{len(paper)}`。",
        "",
    ]
    if paper.empty:
        lines.append("没有配置通过完整 paper gate；下面列出的是最接近的诊断配置，不能升级为 paper-live 或 live。")
    else:
        lines.append("以下配置通过 paper gate，但仍然只能进入 paper audit；需要 forward window、实盘成本和 runner 审计后才能继续。")

    lines.extend(["", "## Top rows", "", *markdown_table(top, table_columns, limit=12), ""])
    lines.extend(["## EMA21/96 focus", "", *markdown_table(ema_21_96_focus, surface_columns, limit=12), ""])
    lines.extend(["## EMA pair surface", "", *markdown_table(pair_surface, surface_columns, limit=12), ""])
    lines.extend(["## Overlay filter surface", "", *markdown_table(filter_surface, surface_columns, limit=12), ""])

    if not top.empty and not monthly.empty:
        top_name = str(top.iloc[0]["name"])
        top_monthly = monthly.loc[monthly["name"].eq(top_name)].copy()
        negative_months = int((top_monthly["total_return"] < 0).sum()) if not top_monthly.empty else 0
        lines.extend(["## 月度提示", ""])
        lines.append(f"- top score `{top_name}` 的负收益月份数：`{negative_months}`。")
        if not top_monthly.empty:
            worst = top_monthly.sort_values("total_return").head(1).iloc[0]
            lines.append(
                f"- 最差月份 `{worst['month']}`：return `{BASE.pct(float(worst['total_return']))}`，PF `{BASE.num(float(worst['profit_factor']))}`，trades `{int(worst['trades'])}`。"
            )

    lines.extend(["", "## 结论", ""])
    if paper.empty:
        lines.append(
            "V35 的强趋势过滤确实能显著减少 1m EMA 交叉噪声，但本轮没有把短周期金叉/死叉追单变成可用候选。"
        )
    else:
        best = paper.iloc[0]
        lines.append(f"本轮存在 paper-audit 诊断行 `{best['name']}`，但它仍不是 live candidate。")
    lines.append(
        "核心差异仍然是机制：V35 原策略不是在交叉瞬间追单，而是用 15m 趋势突破 + 1h 确认 + ATR bracket 抓慢趋势段；把它当作 1m 交叉过滤器只是在过滤噪声，不能自动生成同等 edge。"
    )

    lines.extend(
        [
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/1m-ema-crossover/scripts/research_hype_1m_ema_v35_filter_overlay.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- Summary CSV：`{SUMMARY_PATH}`",
            f"- Slices CSV：`{SLICES_PATH}`",
            f"- Monthly CSV：`{MONTHLY_PATH}`",
            f"- Top trades CSV：`{TOP_TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)

    ema_pairs = parse_ema_pairs(args.ema_pairs)
    exposures = parse_float_list(args.exposures)
    configs = build_configs(ema_pairs)
    spans = sorted({span for fast, slow in ema_pairs for span in (fast, slow)})

    frame_raw, quality = BASE.validate_hype_1m()
    frame = BASE.add_features(frame_raw, spans)
    overlay_features = build_v35_overlay_features(frame_raw)
    slices = BASE.validation_slices(frame)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trades_by_config: dict[str, list[Any]] = {}

    for idx, cfg in enumerate(configs, start=1):
        trades = simulate_trades(frame, overlay_features, cfg)
        trades_by_config[cfg.name] = trades
        for exposure in exposures:
            row, per_slices = row_for_config(frame, cfg, trades, slices, exposure)
            summary_rows.append(row)
            slice_rows.extend(per_slices)
        if args.progress_every and idx % args.progress_every == 0:
            best_so_far = sorted(summary_rows, key=lambda item: float(item["score"]), reverse=True)[0]
            print(
                f"[{idx}/{len(configs)}] best={best_so_far['name']} "
                f"x={float(best_so_far['exposure']):.1f} "
                f"ret={float(best_so_far['full_total_return']):.3f} "
                f"pf={float(best_so_far['full_profit_factor']):.3f} "
                f"dd={float(best_so_far['full_max_dd']):.3f} "
                f"trades={int(best_so_far['full_trades'])}",
                flush=True,
            )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["paper_candidate_pass", "score"], ascending=[False, False]
    )
    slices_frame = pd.DataFrame(slice_rows)
    monthly = pd.DataFrame(monthly_rows(trades_by_config, summary.head(args.top_keep)))

    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)

    best_name = str(summary.iloc[0]["name"]) if not summary.empty else ""
    BASE.trades_to_frame(trades_by_config.get(best_name, [])).to_csv(TOP_TRADES_PATH, index=False)

    payload = {
        "family_id": "HYPE-1M-EMA-Crossover",
        "reference_family_id": "HYPE-EMA-Trend-Breakout-V35",
        "run_date": RUN_DATE,
        "quality": quality,
        "cost_model": {
            "fee_bps_per_fill": BASE.FEE_BPS_PER_FILL,
            "slippage_bps_per_fill": BASE.SLIPPAGE_BPS_PER_FILL,
            "round_trip_bps": BASE.ROUND_TRIP_COST * 10_000.0,
        },
        "args": vars(args),
        "config_count": int(len(configs)),
        "summary_rows": int(len(summary)),
        "paper_candidate_pass_count": int(summary["paper_candidate_pass"].sum()) if not summary.empty else 0,
        "top_rows": summary.head(40).to_dict(orient="records"),
        "paths": {
            "summary": str(SUMMARY_PATH),
            "slices": str(SLICES_PATH),
            "monthly": str(MONTHLY_PATH),
            "top_trades": str(TOP_TRADES_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=BASE.json_default))
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality, args))

    print(f"wrote {MARKDOWN_PATH}")
    print(f"paper_candidate_pass_count={payload['paper_candidate_pass_count']}")
    if not summary.empty:
        top = summary.iloc[0]
        print(
            "top="
            f"{top['name']} x={float(top['exposure']):.1f} "
            f"ann={float(top['full_annualized_multiple']):.3f} "
            f"ret={float(top['full_total_return']):.3f} "
            f"pf={float(top['full_profit_factor']):.3f} "
            f"win={float(top['full_win_rate']):.3f} "
            f"dd={float(top['full_max_dd']):.3f} "
            f"trades={int(top['full_trades'])}"
        )


if __name__ == "__main__":
    main()
