from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import random
from typing import Any, Iterable, Literal

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
FUNDING_ROOT = ROOT / "data/normalized/funding/exchange=binance/market_type=perp"
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "TRXUSDT", "HYPEUSDT")
SLUGS = {symbol: f"{symbol[:-4].lower()}_usdt_usdt" for symbol in SYMBOLS}
STARTS = {
    symbol: pd.Timestamp("2024-07-14T00:00:00Z") for symbol in SYMBOLS
}
STARTS["HYPEUSDT"] = pd.Timestamp("2025-05-30T10:30:00Z")
PREFIT_END = pd.Timestamp("2026-04-14T09:00:00Z")
REUSED_END = pd.Timestamp("2026-07-14T09:00:00Z")
FUTURE_OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")
FEE_PER_FILL = 0.001
BASE_SLIPPAGE = 0.0004

Mechanism = Literal["trend_state", "breakout", "reversal"]
MECHANISMS: tuple[Mechanism, ...] = ("trend_state", "breakout", "reversal")

EMA_WINDOWS = (8, 16, 21, 24, 32, 48, 64, 72, 96, 128, 192, 256, 384)
ADX_WINDOWS = (14, 21, 28, 42)
RSI_WINDOWS = (5, 7, 9, 14)
RVOL_WINDOWS = (48, 96, 192)
DONCHIAN_WINDOWS = (24, 48, 72, 96, 144, 192)
MACD_PAIRS = ((8, 21), (12, 26), (16, 40), (24, 52))


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    config_id: str
    symbol: str
    mechanism: Mechanism
    side_mode: str
    ema_fast: int
    ema_slow: int
    adx_window: int
    adx_min: float
    rvol_window: int
    rvol_min: float
    indicator_window: int
    threshold_long: float
    threshold_short: float
    aux_fast: int
    aux_slow: int
    min_atr_pct: float
    max_atr_pct: float
    max_atr_ratio: float
    max_dist_atr: float
    require_h1: bool
    require_body: bool
    tp_atr: float
    sl_atr: float
    trail_activate_atr: float
    trail_atr: float
    max_hold_bars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StrategyConfig:
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class Opportunity:
    symbol: str
    mechanism: Mechanism
    config_id: str
    side: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_fill: float
    exit_fill: float
    score: float
    price_return_1x: float
    funding_return_1x: float
    fee_return_1x: float
    net_return_1x: float
    mae_return_1x: float
    exit_reason: str


def _atr(frame: pd.DataFrame, window: int) -> pd.Series:
    previous = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0.0)).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss.replace(0.0, np.nan)
    return (100.0 - 100.0 / (1.0 + rs)).fillna(50.0)


def _adx(frame: pd.DataFrame, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = frame["high"].diff()
    down = -frame["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0.0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0.0), down, 0.0), index=frame.index)
    atr = _atr(frame, window).replace(0.0, np.nan)
    plus = 100.0 * plus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean() / atr
    minus = 100.0 * minus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean() / atr
    dx = 100.0 * (plus - minus).abs() / (plus + minus).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    return adx.fillna(0.0), plus.fillna(0.0), minus.fillna(0.0)


def load_symbol_frame(symbol: str, *, end: pd.Timestamp = REUSED_END) -> pd.DataFrame:
    slug = SLUGS[symbol]
    pieces: list[pd.DataFrame] = []
    for path in sorted(DATA_ROOT.glob(f"date=*/symbol={slug}.parquet")):
        date = pd.Timestamp(path.parent.name.removeprefix("date="), tz="UTC")
        if date > end.normalize():
            continue
        pieces.append(pd.read_parquet(path))
    if not pieces:
        raise FileNotFoundError(f"no normalized 15m data for {symbol}")
    frame = pd.concat(pieces, ignore_index=True, sort=False)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[
            (frame["ts"] >= STARTS[symbol])
            & (frame["ts"] < end)
            & frame["is_closed"].astype(bool)
        ]
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = pd.date_range(STARTS[symbol], end - pd.Timedelta(minutes=15), freq="15min")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
    if len(frame) != len(expected) or len(missing):
        raise RuntimeError(f"{symbol} incomplete 15m frame: rows={len(frame)} missing={len(missing)}")
    return add_features(frame)


def load_funding(symbol: str, *, end: pd.Timestamp = REUSED_END) -> pd.DataFrame:
    path = FUNDING_ROOT / f"symbol={SLUGS[symbol]}" / "funding.parquet"
    frame = pd.read_parquet(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame = (
        frame.loc[(frame["ts"] >= STARTS[symbol]) & (frame["ts"] < end)]
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if frame.empty or frame["funding_rate"].isna().any():
        raise RuntimeError(f"{symbol} funding missing or invalid")
    return frame


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"]
    result["atr14"] = _atr(result, 14)
    result["atr96"] = _atr(result, 96)
    result["atr_pct"] = result["atr96"] / close
    result["atr_ratio"] = result["atr14"] / result["atr96"].replace(0.0, np.nan)
    result["body_atr"] = (result["close"] - result["open"]).abs() / result["atr14"].replace(0.0, np.nan)
    for window in EMA_WINDOWS:
        result[f"ema_{window}"] = close.ewm(span=window, adjust=False, min_periods=window).mean()
    for window in ADX_WINDOWS:
        adx, plus, minus = _adx(result, window)
        result[f"adx_{window}"] = adx
        result[f"pdi_{window}"] = plus
        result[f"mdi_{window}"] = minus
    for window in RSI_WINDOWS:
        result[f"rsi_{window}"] = _rsi(close, window)
    for window in RVOL_WINDOWS:
        result[f"rvol_{window}"] = result["volume"] / result["volume"].rolling(window, min_periods=window).mean().replace(0.0, np.nan)
    for window in DONCHIAN_WINDOWS:
        result[f"don_high_{window}"] = result["high"].rolling(window, min_periods=window).max().shift(1)
        result[f"don_low_{window}"] = result["low"].rolling(window, min_periods=window).min().shift(1)
    for fast, slow in MACD_PAIRS:
        fast_ema = close.ewm(span=fast, adjust=False, min_periods=fast).mean()
        slow_ema = close.ewm(span=slow, adjust=False, min_periods=slow).mean()
        result[f"macd_{fast}_{slow}"] = fast_ema - slow_ema

    h1 = (
        result.set_index("ts")
        .resample("1h", label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    h1["h1_known_ts"] = h1["ts"] + pd.Timedelta(hours=1)
    h1["h1_ema_24"] = h1["close"].ewm(span=24, adjust=False, min_periods=24).mean()
    h1["h1_ema_96"] = h1["close"].ewm(span=96, adjust=False, min_periods=96).mean()
    h1_adx, h1_plus, h1_minus = _adx(h1, 21)
    h1["h1_adx_21"] = h1_adx
    h1["h1_pdi_21"] = h1_plus
    h1["h1_mdi_21"] = h1_minus
    result["known_ts"] = result["ts"] + pd.Timedelta(minutes=15)
    result = pd.merge_asof(
        result.sort_values("known_ts"),
        h1[["h1_known_ts", "h1_ema_24", "h1_ema_96", "h1_adx_21", "h1_pdi_21", "h1_mdi_21"]].sort_values("h1_known_ts"),
        left_on="known_ts",
        right_on="h1_known_ts",
        direction="backward",
    )
    return result.drop(columns=["known_ts", "h1_known_ts"]).reset_index(drop=True)


def random_config(symbol: str, mechanism: Mechanism, rng: random.Random, index: int, atr_values: np.ndarray) -> StrategyConfig:
    if mechanism == "trend_state":
        fast = rng.choice((21, 24, 32, 48, 64, 72, 96))
        slow = rng.choice(tuple(value for value in (96, 128, 192, 256, 384) if value > fast * 1.8))
        indicator = rng.choice((24, 48, 72, 96))
        tp = 0.0
        sl = rng.choice((4.0, 5.0, 6.0, 8.0, 10.0))
        activate = rng.choice((2.0, 3.0, 4.0, 5.0))
        trail = rng.choice((1.5, 2.0, 2.5, 3.0, 4.0))
        max_hold = rng.choice((192, 384, 576, 768))
        long_level = rng.choice((0.0, 0.5, 1.0))
        short_level = long_level
        aux_fast, aux_slow = 0, 0
    elif mechanism == "breakout":
        fast = rng.choice((16, 24, 32, 48, 64, 96))
        slow = rng.choice(tuple(value for value in (96, 128, 192, 256, 384) if value > fast * 1.5))
        indicator = rng.choice(DONCHIAN_WINDOWS)
        tp = rng.choice((2.0, 3.0, 4.0, 5.0, 6.0, 8.0))
        sl = rng.choice((3.0, 4.0, 5.0, 7.0, 9.0))
        activate = rng.choice((1.0, 1.5, 2.0, 3.0))
        trail = 0.0
        max_hold = rng.choice((48, 96, 192, 384))
        long_level = rng.choice((0.0, 0.25, 0.5, 0.75))
        short_level = rng.choice((0.0, 0.25, 0.5, 0.75))
        aux_fast, aux_slow = 0, 0
    else:
        fast, slow = 0, 0
        indicator = rng.choice(RSI_WINDOWS)
        long_level = rng.choice((20.0, 25.0, 30.0, 35.0, 40.0, 45.0))
        short_level = rng.choice((55.0, 60.0, 65.0, 70.0, 75.0, 80.0))
        aux_fast, aux_slow = rng.choice(MACD_PAIRS)
        tp = rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5))
        sl = rng.choice((2.0, 3.0, 4.0, 5.0, 6.0, 7.0))
        activate, trail = 0.0, 0.0
        max_hold = rng.choice((8, 12, 16, 24, 32, 48))
    q_low = rng.choice((0.05, 0.10, 0.20, 0.30, 0.40))
    q_high = rng.choice((0.70, 0.80, 0.90, 0.95, 1.0))
    min_atr = float(np.nanquantile(atr_values, q_low))
    max_atr = float(np.nanquantile(atr_values, q_high)) if q_high < 1.0 else float("inf")
    return StrategyConfig(
        config_id=f"{symbol}_{mechanism}_{index:06d}", symbol=symbol, mechanism=mechanism,
        side_mode=rng.choice(("both", "both", "both", "long", "short")),
        ema_fast=fast, ema_slow=slow, adx_window=rng.choice(ADX_WINDOWS),
        adx_min=rng.choice((0.0, 15.0, 18.0, 21.0, 24.0, 28.0, 32.0, 36.0)),
        rvol_window=rng.choice(RVOL_WINDOWS),
        rvol_min=rng.choice((0.0, 0.75, 0.85, 1.0, 1.15, 1.3, 1.5)),
        indicator_window=indicator, threshold_long=long_level, threshold_short=short_level,
        aux_fast=aux_fast, aux_slow=aux_slow, min_atr_pct=min_atr, max_atr_pct=max_atr,
        max_atr_ratio=rng.choice((1.0, 1.2, 1.5, 1.8, 2.5, 99.0)),
        max_dist_atr=rng.choice((1.0, 2.0, 3.0, 4.0, 6.0, 99.0)),
        require_h1=rng.choice((False, True)), require_body=rng.choice((False, True)),
        tp_atr=tp, sl_atr=sl, trail_activate_atr=activate, trail_atr=trail,
        max_hold_bars=max_hold,
    )


def build_signal(frame: pd.DataFrame, cfg: StrategyConfig) -> tuple[np.ndarray, np.ndarray]:
    close = frame["close"]
    open_ = frame["open"]
    atr = frame["atr14"]
    adx = frame[f"adx_{cfg.adx_window}"]
    plus = frame[f"pdi_{cfg.adx_window}"]
    minus = frame[f"mdi_{cfg.adx_window}"]
    rvol = frame[f"rvol_{cfg.rvol_window}"]
    common = (
        atr.notna() & (frame["atr_pct"] >= cfg.min_atr_pct)
        & (frame["atr_pct"] <= cfg.max_atr_pct)
        & (frame["atr_ratio"] <= cfg.max_atr_ratio)
        & (adx >= cfg.adx_min) & (rvol >= cfg.rvol_min)
    )
    if cfg.mechanism == "trend_state":
        fast = frame[f"ema_{cfg.ema_fast}"]
        slow = frame[f"ema_{cfg.ema_slow}"]
        distance = (close - fast) / atr.replace(0.0, np.nan)
        long_gate = (fast > slow) & (plus > minus) & (distance.abs() <= cfg.max_dist_atr)
        short_gate = (fast < slow) & (minus > plus) & (distance.abs() <= cfg.max_dist_atr)
        pullback_long = (frame["low"] <= fast) & (close > fast)
        pullback_short = (frame["high"] >= fast) & (close < fast)
        if cfg.threshold_long >= 0.5:
            long_gate &= pullback_long
            short_gate &= pullback_short
        if cfg.threshold_long >= 1.0:
            long_gate &= close > close.shift(1)
            short_gate &= close < close.shift(1)
        long = long_gate & ~long_gate.shift(1, fill_value=False)
        short = short_gate & ~short_gate.shift(1, fill_value=False)
        score = (
            0.35 * ((fast - slow).abs() / atr.replace(0.0, np.nan) / 6.0).clip(0.0, 1.0)
            + 0.30 * (adx / 45.0).clip(0.0, 1.0)
            + 0.20 * (rvol / 2.0).clip(0.0, 1.0)
            + 0.15 * (1.0 - (distance.abs() / max(cfg.max_dist_atr, 1.0)).clip(0.0, 1.0))
        )
    elif cfg.mechanism == "breakout":
        fast = frame[f"ema_{cfg.ema_fast}"]
        slow = frame[f"ema_{cfg.ema_slow}"]
        high = frame[f"don_high_{cfg.indicator_window}"]
        low = frame[f"don_low_{cfg.indicator_window}"]
        long = (close > high) & (close.shift(1) <= high.shift(1)) & (fast > slow) & (plus > minus)
        short = (close < low) & (close.shift(1) >= low.shift(1)) & (fast < slow) & (minus > plus)
        range_atr = (high - low) / atr.replace(0.0, np.nan)
        score = (
            0.35 * (adx / 45.0).clip(0.0, 1.0)
            + 0.30 * (rvol / 2.0).clip(0.0, 1.0)
            + 0.20 * (frame["body_atr"] / 1.5).clip(0.0, 1.0)
            + 0.15 * (range_atr / 12.0).clip(0.0, 1.0)
        )
    else:
        rsi = frame[f"rsi_{cfg.indicator_window}"]
        macd = frame[f"macd_{cfg.aux_fast}_{cfg.aux_slow}"]
        long = (rsi > cfg.threshold_long) & (rsi.shift(1) <= cfg.threshold_long) & (macd > 0.0)
        short = (rsi < cfg.threshold_short) & (rsi.shift(1) >= cfg.threshold_short) & (macd < 0.0)
        score = (
            0.40 * ((rsi - 50.0).abs() / 30.0).clip(0.0, 1.0)
            + 0.25 * (macd.abs() / atr.replace(0.0, np.nan) / 2.0).clip(0.0, 1.0)
            + 0.20 * (rvol / 2.0).clip(0.0, 1.0)
            + 0.15 * (1.0 - (adx / 45.0).clip(0.0, 1.0))
        )
    if cfg.require_h1:
        h1_long = (frame["h1_ema_24"] > frame["h1_ema_96"]) & (frame["h1_pdi_21"] > frame["h1_mdi_21"])
        h1_short = (frame["h1_ema_24"] < frame["h1_ema_96"]) & (frame["h1_mdi_21"] > frame["h1_pdi_21"])
        if cfg.mechanism == "reversal":
            long &= ~((~h1_long) & (frame["h1_adx_21"] > 30.0))
            short &= ~((~h1_short) & (frame["h1_adx_21"] > 30.0))
        else:
            long &= h1_long
            short &= h1_short
    if cfg.require_body:
        long &= close > open_
        short &= close < open_
    long &= common
    short &= common
    if cfg.side_mode == "long":
        short &= False
    elif cfg.side_mode == "short":
        long &= False
    conflict = long & short
    side = np.where(long & ~conflict, 1, np.where(short & ~conflict, -1, 0)).astype(np.int8)
    return side, np.asarray(score.fillna(0.0).clip(0.0, 1.0), dtype=np.float64)


def funding_arrays(funding: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    times = funding["ts"].astype("datetime64[ns, UTC]").astype("int64").to_numpy()
    rates = funding["funding_rate"].to_numpy(dtype=np.float64)
    return times, np.concatenate(([0.0], np.cumsum(rates)))


def funding_return(side: int, entry_ts: pd.Timestamp, exit_ts: pd.Timestamp, times: np.ndarray, prefix: np.ndarray) -> float:
    left = int(np.searchsorted(times, int(entry_ts.value), side="left"))
    right = int(np.searchsorted(times, int(exit_ts.value), side="left"))
    return float(-side * (prefix[right] - prefix[left]))


def adverse_fill(price: float, side: int, *, entry: bool, slippage: float) -> float:
    direction = side if entry else -side
    return float(price * (1.0 + direction * slippage))


def simulate_opportunities(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: StrategyConfig,
    *,
    end: pd.Timestamp,
    slippage: float = BASE_SLIPPAGE,
    entry_delay_bars: int = 1,
) -> list[Opportunity]:
    sides, scores = build_signal(frame, cfg)
    funding_times, funding_prefix = funding_arrays(funding)
    open_ = frame["open"].to_numpy(dtype=np.float64)
    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    close = frame["close"].to_numpy(dtype=np.float64)
    atr = frame["atr14"].to_numpy(dtype=np.float64)
    slow = frame[f"ema_{cfg.ema_slow}"].to_numpy(dtype=np.float64) if cfg.ema_slow else np.full(len(frame), np.nan)
    ts = frame["ts"].tolist()
    opportunities: list[Opportunity] = []
    for signal_i in np.flatnonzero(sides):
        entry_i = int(signal_i + entry_delay_bars)
        if entry_i >= len(frame) or ts[entry_i] >= end or not np.isfinite(atr[signal_i]):
            continue
        side = int(sides[signal_i])
        entry_fill = adverse_fill(open_[entry_i], side, entry=True, slippage=slippage)
        stop = entry_fill - side * cfg.sl_atr * atr[signal_i]
        target = entry_fill + side * cfg.tp_atr * atr[signal_i] if cfg.tp_atr > 0.0 else math.nan
        exit_i = min(entry_i + cfg.max_hold_bars, len(frame) - 1)
        exit_base = open_[exit_i]
        reason = "time_open"
        high_water = entry_fill
        low_water = entry_fill
        trail_stop = math.nan
        for index in range(entry_i, min(entry_i + cfg.max_hold_bars, len(frame))):
            if side > 0:
                if open_[index] <= stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_stop"
                    break
                if np.isfinite(target) and open_[index] >= target:
                    exit_i, exit_base, reason = index, open_[index], "gap_target"
                    break
                if np.isfinite(trail_stop) and open_[index] <= trail_stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_trail"
                    break
                if low[index] <= stop:
                    exit_i, exit_base, reason = index, stop, "stop"
                    break
                if np.isfinite(trail_stop) and low[index] <= trail_stop:
                    exit_i, exit_base, reason = index, trail_stop, "trail"
                    break
                if np.isfinite(target) and high[index] >= target:
                    exit_i, exit_base, reason = index, target, "target"
                    break
            else:
                if open_[index] >= stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_stop"
                    break
                if np.isfinite(target) and open_[index] <= target:
                    exit_i, exit_base, reason = index, open_[index], "gap_target"
                    break
                if np.isfinite(trail_stop) and open_[index] >= trail_stop:
                    exit_i, exit_base, reason = index, open_[index], "gap_trail"
                    break
                if high[index] >= stop:
                    exit_i, exit_base, reason = index, stop, "stop"
                    break
                if np.isfinite(trail_stop) and high[index] >= trail_stop:
                    exit_i, exit_base, reason = index, trail_stop, "trail"
                    break
                if np.isfinite(target) and low[index] <= target:
                    exit_i, exit_base, reason = index, target, "target"
                    break
            if cfg.mechanism == "trend_state" and index > entry_i:
                if (side > 0 and close[index - 1] < slow[index - 1]) or (side < 0 and close[index - 1] > slow[index - 1]):
                    exit_i, exit_base, reason = index, open_[index], "trend_break_open"
                    break
            high_water = max(high_water, high[index])
            low_water = min(low_water, low[index])
            if cfg.mechanism == "trend_state" and cfg.trail_activate_atr > 0.0:
                mfe = side * ((high_water if side > 0 else low_water) - entry_fill) / atr[signal_i]
                if mfe >= cfg.trail_activate_atr:
                    candidate = high_water - cfg.trail_atr * atr[signal_i] if side > 0 else low_water + cfg.trail_atr * atr[signal_i]
                    if not np.isfinite(trail_stop):
                        trail_stop = candidate
                    elif side > 0:
                        trail_stop = max(trail_stop, candidate)
                    else:
                        trail_stop = min(trail_stop, candidate)
        if exit_i >= len(frame) or ts[exit_i] >= end:
            continue
        exit_fill = adverse_fill(exit_base, side, entry=False, slippage=slippage)
        price_return = float(side * (exit_fill / entry_fill - 1.0))
        funding_ret = funding_return(side, ts[entry_i], ts[exit_i], funding_times, funding_prefix)
        fee_ret = -2.0 * FEE_PER_FILL
        if side > 0:
            mae_price = float(np.nanmin(low[entry_i : exit_i + 1] / entry_fill - 1.0))
        else:
            mae_price = float(np.nanmin(1.0 - high[entry_i : exit_i + 1] / entry_fill))
        opportunities.append(
            Opportunity(
                symbol=cfg.symbol, mechanism=cfg.mechanism, config_id=cfg.config_id,
                side=side, signal_ts=ts[signal_i], entry_ts=ts[entry_i], exit_ts=ts[exit_i],
                entry_fill=entry_fill, exit_fill=exit_fill, score=float(scores[signal_i]),
                price_return_1x=price_return, funding_return_1x=funding_ret,
                fee_return_1x=fee_ret, net_return_1x=price_return + funding_ret + fee_ret,
                mae_return_1x=mae_price + fee_ret,
                exit_reason=reason,
            )
        )
    return opportunities


def select_nonoverlap(opportunities: Iterable[Opportunity], *, start: pd.Timestamp, end: pd.Timestamp) -> list[Opportunity]:
    selected: list[Opportunity] = []
    blocked_until = start
    for item in sorted(opportunities, key=lambda value: (value.entry_ts, -value.score, value.exit_ts)):
        if item.entry_ts < start or item.entry_ts >= end or item.exit_ts >= end:
            continue
        if item.entry_ts < blocked_until:
            continue
        selected.append(item)
        blocked_until = item.exit_ts
    return selected


def metrics(opportunities: Iterable[Opportunity], *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float]:
    selected = select_nonoverlap(opportunities, start=start, end=end)
    returns = [item.net_return_1x for item in selected]
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for item, value in zip(selected, returns, strict=True):
        trough = equity * max(1e-9, 1.0 + item.mae_return_1x)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value <= 0.0]
    years = max((end - start).total_seconds() / (365.25 * 86400.0), 1.0 / 365.25)
    gross_loss = abs(sum(negatives))
    return {
        "trades": float(len(returns)), "wins": float(len(positives)),
        "win_rate": float(len(positives) / len(returns)) if returns else 0.0,
        "total_return": float(equity - 1.0),
        "annual_multiple": float(equity ** (1.0 / years)) if equity > 0.0 else 0.0,
        "max_dd": float(max_dd),
        "profit_factor": float(sum(positives) / gross_loss) if gross_loss > 0.0 else 999.0,
        "avg_return": float(np.mean(returns)) if returns else 0.0,
        "worst_trade": float(min(returns)) if returns else 0.0,
        "long_trades": float(sum(item.side > 0 for item in selected)),
        "short_trades": float(sum(item.side < 0 for item in selected)),
    }


def prefit_windows(symbol: str) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    start = STARTS[symbol]
    return {
        "train": (start, pd.Timestamp("2025-10-14T09:00:00Z")),
        "validation_1": (pd.Timestamp("2025-10-14T09:00:00Z"), pd.Timestamp("2026-01-14T09:00:00Z")),
        "validation_2": (pd.Timestamp("2026-01-14T09:00:00Z"), PREFIT_END),
        "prefit": (start, PREFIT_END),
    }


def evaluate_prefit(opportunities: list[Opportunity], symbol: str) -> dict[str, dict[str, float]]:
    return {name: metrics(opportunities, start=start, end=end) for name, (start, end) in prefit_windows(symbol).items()}


def prefit_score(result: dict[str, dict[str, float]]) -> float:
    train = result["train"]
    val1 = result["validation_1"]
    val2 = result["validation_2"]
    prefit = result["prefit"]
    if prefit["trades"] < 18 or val1["trades"] < 3 or val2["trades"] < 3 or prefit["max_dd"] <= -0.45:
        return -1e9
    return float(
        7.0 * prefit["win_rate"] + 3.0 * val1["win_rate"] + 4.0 * val2["win_rate"]
        + 1.5 * math.log(max(min(prefit["profit_factor"], 10.0), 1e-8))
        + 0.7 * math.log(max(prefit["annual_multiple"], 1e-8))
        + 3.0 * prefit["max_dd"] + 0.2 * math.log1p(prefit["trades"])
        + 12.0 * min(train["total_return"], 0.0)
        + 18.0 * min(val1["total_return"], 0.0)
        + 22.0 * min(val2["total_return"], 0.0)
    )
