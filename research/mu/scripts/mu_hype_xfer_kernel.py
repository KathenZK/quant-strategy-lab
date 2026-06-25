from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


# Frozen HYPE-EMA-X kernel snapshot for MU-HYPE-XFER research.
# Do not import evolving HYPE research scripts directly from MU scripts.
SLIPPAGE = 0.0005
TRADE_COST = 0.00085
PERIODS_PER_YEAR = 365 * 24 * 4


@dataclass(frozen=True, slots=True)
class Variant:
    name: str
    entry: str
    exit: str
    take_atr: float | None = None
    stop_atr: float | None = None
    adx_exit: float | None = None
    adx_exit_bars: int = 3
    disable_adx_after_mfe_atr: float | None = None
    ema384_break_bars: int = 2
    max_hold_bars: int | None = None


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def adx_di(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = (
        100
        * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    minus_di = (
        100
        * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100 - 100 / (1 + rs)


def trend_efficiency(close: pd.Series, window: int) -> pd.Series:
    direct = close.pct_change(window).abs()
    path = close.pct_change().abs().rolling(window, min_periods=window).sum()
    return direct / path.replace(0.0, np.nan)


def add_htf_features(frame: pd.DataFrame, rule: str, prefix: str) -> pd.DataFrame:
    ohlcv = (
        frame.set_index("ts")[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna()
    )
    htf = pd.DataFrame(index=ohlcv.index)
    htf[f"{prefix}_ema24"] = ohlcv.close.ewm(
        span=24, adjust=False, min_periods=24
    ).mean()
    htf[f"{prefix}_ema96"] = ohlcv.close.ewm(
        span=96, adjust=False, min_periods=96
    ).mean()
    htf[f"{prefix}_ema_spread"] = (
        htf[f"{prefix}_ema24"] / htf[f"{prefix}_ema96"].replace(0.0, np.nan) - 1
    )
    htf[f"{prefix}_ret12"] = ohlcv.close.pct_change(12)
    htf[f"{prefix}_rsi14"] = rsi(ohlcv.close, 14)
    htf[f"{prefix}_adx21"], htf[f"{prefix}_pdi21"], htf[f"{prefix}_mdi21"] = adx_di(
        ohlcv.high,
        ohlcv.low,
        ohlcv.close,
        21,
    )
    aligned = htf.shift(1).reindex(pd.DatetimeIndex(frame.ts), method="ffill")
    return aligned.reset_index(drop=True)


def build_features(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    close = frame.close
    high = frame.high
    low = frame.low
    volume = frame.volume

    frame["ema96"] = close.ewm(span=96, adjust=False, min_periods=96).mean()
    frame["ema384"] = close.ewm(span=384, adjust=False, min_periods=384).mean()
    frame["ema_spread"] = frame.ema96 / frame.ema384.replace(0.0, np.nan) - 1
    frame["ema96_slope16"] = frame.ema96.pct_change(16)
    frame["ema96_slope48"] = frame.ema96.pct_change(48)
    frame["ema384_slope96"] = frame.ema384.pct_change(96)

    for window in (4, 16, 48, 96):
        frame[f"ret{window}"] = close.pct_change(window)
    for window in (96, 192):
        frame[f"vol_surge{window}"] = (
            volume / volume.rolling(window, min_periods=window).mean().replace(0.0, np.nan)
            - 1
        )
    tr = true_range(high, low, close)
    for window in (96, 336, 672):
        frame[f"atr_pct{window}"] = (
            tr.rolling(window, min_periods=window).mean() / close.replace(0.0, np.nan)
        )
    frame["atr_ratio96_672"] = frame.atr_pct96 / frame.atr_pct672.replace(0.0, np.nan)

    for window in (14, 28):
        (
            frame[f"adx{window}"],
            frame[f"pdi{window}"],
            frame[f"mdi{window}"],
        ) = adx_di(high, low, close, window)

    frame["rsi14"] = rsi(close, 14)
    frame["eff48"] = trend_efficiency(close, 48)
    frame["eff96"] = trend_efficiency(close, 96)

    for window in (96, 192):
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        frame[f"donchian_pos{window}"] = (
            (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)
        )

    frame = pd.concat(
        [
            frame,
            add_htf_features(frame, "1h", "h1"),
            add_htf_features(frame, "4h", "h4"),
        ],
        axis=1,
    )
    return frame.reset_index(drop=True)


def entry_signal(frame: pd.DataFrame, variant: Variant) -> np.ndarray:
    spread = frame.ema_spread.to_numpy("float64")
    previous = np.r_[np.nan, spread[:-1]]
    cross_long = (spread > 0.0) & (previous <= 0.0)
    cross_short = (spread < 0.0) & (previous >= 0.0)
    regime_long = spread > 0.0
    regime_short = spread < 0.0

    if variant.entry.startswith("v2"):
        long_ok = (
            regime_long
            & (frame.adx28.to_numpy("float64") >= 28)
            & (frame.vol_surge192.to_numpy("float64") >= 0.25)
            & (frame.h1_adx21.to_numpy("float64") > 18)
            & (frame.h1_pdi21.to_numpy("float64") > frame.h1_mdi21.to_numpy("float64"))
        )
        short_ok = (
            regime_short
            & (frame.adx28.to_numpy("float64") >= 36)
            & (frame.vol_surge192.to_numpy("float64") >= 0.50)
            & (frame.h1_ema_spread.to_numpy("float64") < 0)
        )
        signal = np.zeros(len(frame), dtype=np.int8)
        signal[long_ok] = 1
        signal[short_ok] = -1
        return signal

    v4_long_filter = (
        (frame.ema96_slope48.to_numpy("float64") > 0)
        & (frame.pdi14.to_numpy("float64") > frame.mdi14.to_numpy("float64"))
        & (frame.rsi14.to_numpy("float64") >= 52)
        & (frame.h4_ema_spread.to_numpy("float64") > 0)
    )
    v4_short_filter = (
        (frame.ema96_slope48.to_numpy("float64") < 0)
        & (frame.mdi14.to_numpy("float64") > frame.pdi14.to_numpy("float64"))
        & (frame.rsi14.to_numpy("float64") <= 48)
        & (frame.h4_ema_spread.to_numpy("float64") < 0)
    )
    if "window" in variant.entry:
        window_bars = int(variant.entry.rsplit("_", maxsplit=1)[-1])
        regime_age = np.full(len(frame), np.inf)
        age = np.inf
        for i in range(len(frame)):
            if cross_long[i] or cross_short[i]:
                age = 0
            elif np.isfinite(age):
                age += 1
            regime_age[i] = age
        long_base = regime_long & (regime_age <= window_bars)
        short_base = regime_short & (regime_age <= window_bars)
    else:
        long_base = regime_long if "regime" in variant.entry else cross_long
        short_base = regime_short if "regime" in variant.entry else cross_short
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[long_base & v4_long_filter] = 1
    signal[short_base & v4_short_filter] = -1
    return signal


def v6_variant() -> Variant:
    return Variant(
        "V6_dynamic_3x",
        "v2_regime",
        "adx_exit",
        stop_atr=9.0,
        adx_exit=22,
        adx_exit_bars=3,
    )
