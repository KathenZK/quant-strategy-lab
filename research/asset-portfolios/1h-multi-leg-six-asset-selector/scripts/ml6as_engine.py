from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import math
from pathlib import Path
import random
from typing import Any, Iterable, Literal

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
FUNDING_ROOT = (
    ROOT / "data/normalized/funding/exchange=binance/market_type=perp"
)
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "TRXUSDT", "HYPEUSDT")
SLUGS = {symbol: f"{symbol[:-4].lower()}_usdt_usdt" for symbol in SYMBOLS}
RESEARCH_START = pd.Timestamp("2025-05-30T10:00:00Z")
TRAIN_END = pd.Timestamp("2026-01-01T00:00:00Z")
OOS_START = pd.Timestamp("2026-04-14T09:00:00Z")
FULL_END = pd.Timestamp("2026-07-14T09:00:00Z")
FEE_PER_FILL = 0.001
BASE_SLIPPAGE = 0.0004

Arm = Literal["trend_pullback", "breakout", "mean_reversion"]
Route = Literal["independent", "fused"]
Occupancy = Literal["nonpreemptive", "preemptive"]


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    config_id: str
    symbol: str
    arm: Arm
    side_mode: str
    ema_fast: int
    ema_slow: int
    h4_fast: int
    h4_slow: int
    indicator_window: int
    threshold: float
    min_adx: float
    max_adx: float
    min_rvol: float
    min_body_atr: float
    max_dist_atr: float
    require_h4_alignment: bool
    require_body_direction: bool
    tp_atr: float
    sl_atr: float
    max_hold_bars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StrategyConfig:
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class Opportunity:
    symbol: str
    arm: Arm
    config_id: str
    signal_i: int
    entry_i: int
    exit_i: int
    side: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    entry_fill: float
    exit_fill: float
    score: float
    regime_trendiness: float
    price_return_1x: float
    funding_return_1x: float
    fee_return_1x: float
    net_return_1x: float
    exit_reason: str


@dataclass(frozen=True, slots=True)
class RoutedOpportunity:
    opportunity: Opportunity
    route_score: float
    support_count: int


@dataclass(frozen=True, slots=True)
class PortfolioTrade:
    symbol: str
    arm: Arm
    config_id: str
    side: int
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    route_score: float
    exposure: float
    net_return: float
    exit_reason: str
    preempted: bool


@dataclass(frozen=True, slots=True)
class RouteConfig:
    route: Route
    occupancy: Occupancy
    entry_threshold: float
    exposure: float
    conflict_margin: float
    preempt_margin: float
    min_hold_bars: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RouteConfig:
        return cls(**payload)


def load_symbol_frame(symbol: str, *, end: pd.Timestamp) -> pd.DataFrame:
    slug = SLUGS[symbol]
    files = sorted(DATA_ROOT.glob(f"date=*/symbol={slug}.parquet"))
    if not files:
        raise FileNotFoundError(f"no normalized 1h files for {symbol}")
    pieces: list[pd.DataFrame] = []
    for path in files:
        date_token = path.parent.name.removeprefix("date=")
        if pd.Timestamp(date_token, tz="UTC") > end.normalize():
            continue
        pieces.append(pd.read_parquet(path))
    frame = pd.concat(pieces, ignore_index=True, sort=False)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = (
        frame.loc[
            (frame["ts"] >= RESEARCH_START)
            & (frame["ts"] < end)
            & frame["is_closed"].astype(bool)
        ]
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = pd.date_range(RESEARCH_START, end - pd.Timedelta(hours=1), freq="1h")
    missing = expected.difference(pd.DatetimeIndex(frame["ts"]))
    if len(frame) != len(expected) or len(missing):
        raise RuntimeError(
            f"{symbol} research frame is incomplete: rows={len(frame)} "
            f"expected={len(expected)} missing={len(missing)}"
        )
    critical = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]
    if frame[critical].isna().any().any():
        raise RuntimeError(f"{symbol} research frame contains critical nulls")
    return add_features(frame)


def load_funding(symbol: str, *, end: pd.Timestamp) -> pd.DataFrame:
    path = FUNDING_ROOT / f"symbol={SLUGS[symbol]}" / "funding.parquet"
    frame = pd.read_parquet(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame = (
        frame.loc[(frame["ts"] >= RESEARCH_START) & (frame["ts"] < end)]
        .drop_duplicates("ts", keep="last")
        .sort_values("ts")
        .reset_index(drop=True)
    )
    if frame.empty or frame["funding_rate"].isna().any():
        raise RuntimeError(f"{symbol} funding missing or invalid")
    return frame


def _atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
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


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    loss = (-delta.clip(upper=0.0)).ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean()
    rs = gain / loss.replace(0.0, np.nan)
    result = 100.0 - 100.0 / (1.0 + rs)
    return result.fillna(50.0)


def _adx(frame: pd.DataFrame, window: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = frame["high"].diff()
    down = -frame["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0.0), up, 0.0), index=frame.index)
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0.0), down, 0.0), index=frame.index
    )
    atr = _atr(frame, window)
    plus_di = 100.0 * plus_dm.ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean() / atr.replace(0.0, np.nan)
    minus_di = 100.0 * minus_dm.ewm(
        alpha=1.0 / window, adjust=False, min_periods=window
    ).mean() / atr.replace(0.0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    return adx.fillna(0.0), plus_di.fillna(0.0), minus_di.fillna(0.0)


def _four_hour_features(frame: pd.DataFrame) -> pd.DataFrame:
    indexed = frame.set_index("ts")
    h4 = indexed.resample("4h", origin="epoch", label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "quote_volume": "sum",
        }
    )
    h4 = h4.dropna(subset=["open", "high", "low", "close"]).reset_index()
    h4["known_ts"] = h4["ts"] + pd.Timedelta(hours=4)
    h4["h4_atr"] = _atr(h4)
    h4["h4_adx"], h4["h4_pdi"], h4["h4_mdi"] = _adx(h4)
    for window in (8, 13, 21, 34, 55):
        h4[f"h4_ema_{window}"] = h4["close"].ewm(
            span=window, adjust=False, min_periods=window
        ).mean()
    feature_columns = [column for column in h4.columns if column.startswith("h4_")]
    return h4[["known_ts", *feature_columns]]


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["atr"] = _atr(result)
    result["atr_bps"] = result["atr"] / result["close"] * 10_000.0
    result["rsi"] = _rsi(result["close"])
    result["adx"], result["pdi"], result["mdi"] = _adx(result)
    result["body_atr"] = (
        (result["close"] - result["open"]).abs() / result["atr"].replace(0.0, np.nan)
    )
    for window in (8, 12, 13, 21, 24, 34, 48, 55, 72, 89, 96, 144):
        result[f"ema_{window}"] = result["close"].ewm(
            span=window, adjust=False, min_periods=window
        ).mean()
    for window in (12, 24, 48, 72, 96):
        previous_high = result["high"].shift(1)
        previous_low = result["low"].shift(1)
        result[f"donchian_high_{window}"] = previous_high.rolling(
            window, min_periods=window
        ).max()
        result[f"donchian_low_{window}"] = previous_low.rolling(
            window, min_periods=window
        ).min()
        mean = result["close"].rolling(window, min_periods=window).mean()
        std = result["close"].rolling(window, min_periods=window).std(ddof=0)
        result[f"z_{window}"] = (result["close"] - mean) / std.replace(0.0, np.nan)
        qv = result["quote_volume"].rolling(window, min_periods=window).sum()
        volume = result["volume"].rolling(window, min_periods=window).sum()
        result[f"rvwap_{window}"] = qv / volume.replace(0.0, np.nan)
    volume_mean = result["volume"].rolling(48, min_periods=24).mean()
    result["rvol"] = result["volume"] / volume_mean.replace(0.0, np.nan)
    h4 = _four_hour_features(result)
    left = result.copy()
    left["signal_known_ts"] = left["ts"] + pd.Timedelta(hours=1)
    result = pd.merge_asof(
        left.sort_values("signal_known_ts"),
        h4.sort_values("known_ts"),
        left_on="signal_known_ts",
        right_on="known_ts",
        direction="backward",
    ).drop(columns=["signal_known_ts", "known_ts"])
    h4_spread = (result["h4_ema_13"] - result["h4_ema_34"]).abs()
    h4_spread_atr = h4_spread / result["h4_atr"].replace(0.0, np.nan)
    result["regime_trendiness"] = (
        0.55 * (result["h4_adx"] / 40.0).clip(0.0, 1.0)
        + 0.45 * (h4_spread_atr / 1.5).clip(0.0, 1.0)
    ).fillna(0.5)
    return result.reset_index(drop=True)


def random_config(
    symbol: str, arm: Arm, rng: random.Random, index: int
) -> StrategyConfig:
    fast = rng.choice((8, 12, 13, 21, 24, 34))
    slow = rng.choice(tuple(value for value in (34, 55, 72, 89, 96, 144) if value > fast))
    h4_fast, h4_slow = rng.choice(((8, 21), (13, 34), (21, 55)))
    if arm == "trend_pullback":
        indicator_window = rng.choice((12, 24, 48, 72))
        threshold = rng.choice((0.0, 0.15, 0.3, 0.5, 0.75, 1.0))
        min_adx = rng.choice((10.0, 14.0, 18.0, 22.0, 26.0, 30.0))
        max_adx = 100.0
        min_rvol = rng.choice((0.0, 0.5, 0.75, 1.0, 1.25))
        min_body_atr = rng.choice((0.0, 0.1, 0.2, 0.3, 0.5))
        max_dist_atr = rng.choice((0.15, 0.25, 0.4, 0.6, 0.8, 1.0))
        require_h4 = rng.random() < 0.8
        body = rng.random() < 0.8
        tp = rng.choice((0.35, 0.5, 0.65, 0.8, 1.0, 1.25, 1.5, 2.0))
        sl = rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0))
        hold = rng.choice((6, 8, 12, 18, 24, 36, 48, 72))
    elif arm == "breakout":
        indicator_window = rng.choice((12, 24, 48, 72, 96))
        threshold = rng.choice((0.0, 0.05, 0.1, 0.2, 0.35, 0.5))
        min_adx = rng.choice((0.0, 10.0, 14.0, 18.0, 22.0, 26.0, 30.0))
        max_adx = 100.0
        min_rvol = rng.choice((0.0, 0.75, 1.0, 1.25, 1.5, 2.0))
        min_body_atr = rng.choice((0.0, 0.15, 0.25, 0.4, 0.6, 0.8))
        max_dist_atr = rng.choice((1.0, 1.5, 2.0, 3.0, 5.0))
        require_h4 = rng.random() < 0.65
        body = True
        tp = rng.choice((0.35, 0.5, 0.65, 0.8, 1.0, 1.25, 1.5, 2.0, 2.5))
        sl = rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0))
        hold = rng.choice((4, 6, 8, 12, 18, 24, 36, 48, 72))
    else:
        indicator_window = rng.choice((12, 24, 48, 72, 96))
        threshold = rng.choice((1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0))
        min_adx = 0.0
        max_adx = rng.choice((16.0, 20.0, 24.0, 28.0, 32.0, 36.0, 45.0, 100.0))
        min_rvol = rng.choice((0.0, 0.5, 0.75, 1.0, 1.25))
        min_body_atr = rng.choice((0.0, 0.05, 0.1, 0.2, 0.3))
        max_dist_atr = rng.choice((0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0))
        require_h4 = rng.random() < 0.35
        body = rng.random() < 0.8
        tp = rng.choice((0.25, 0.35, 0.5, 0.65, 0.8, 1.0, 1.25))
        sl = rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0))
        hold = rng.choice((3, 4, 6, 8, 12, 18, 24, 36))
    sl = min(sl, max(0.75, 3.0 * tp))
    return StrategyConfig(
        config_id=f"{symbol}_{arm}_{index:06d}",
        symbol=symbol,
        arm=arm,
        side_mode=rng.choices(("both", "long", "short"), weights=(0.55, 0.25, 0.20), k=1)[0],
        ema_fast=fast,
        ema_slow=slow,
        h4_fast=h4_fast,
        h4_slow=h4_slow,
        indicator_window=indicator_window,
        threshold=threshold,
        min_adx=min_adx,
        max_adx=max_adx,
        min_rvol=min_rvol,
        min_body_atr=min_body_atr,
        max_dist_atr=max_dist_atr,
        require_h4_alignment=require_h4,
        require_body_direction=body,
        tp_atr=tp,
        sl_atr=sl,
        max_hold_bars=hold,
    )


def build_signal(frame: pd.DataFrame, cfg: StrategyConfig) -> tuple[np.ndarray, np.ndarray]:
    close = frame["close"]
    open_ = frame["open"]
    high = frame["high"]
    low = frame["low"]
    atr = frame["atr"]
    ema_fast = frame[f"ema_{cfg.ema_fast}"]
    ema_slow = frame[f"ema_{cfg.ema_slow}"]
    h4_fast = frame[f"h4_ema_{cfg.h4_fast}"]
    h4_slow = frame[f"h4_ema_{cfg.h4_slow}"]
    adx = frame["adx"]
    rvol = frame["rvol"]
    body_atr = frame["body_atr"]
    common = (
        atr.notna()
        & (atr > 0.0)
        & (adx >= cfg.min_adx)
        & (adx <= cfg.max_adx)
        & (rvol >= cfg.min_rvol)
        & (body_atr >= cfg.min_body_atr)
    )
    h4_long = h4_fast > h4_slow
    h4_short = h4_fast < h4_slow
    if cfg.arm == "trend_pullback":
        spread = (ema_fast - ema_slow) / atr.replace(0.0, np.nan)
        long = (
            (spread >= cfg.threshold)
            & (low <= ema_fast + cfg.max_dist_atr * atr)
            & (close >= ema_fast)
            & (frame["rsi"] >= 42.0)
            & (frame["rsi"] <= 75.0)
        )
        short = (
            (spread <= -cfg.threshold)
            & (high >= ema_fast - cfg.max_dist_atr * atr)
            & (close <= ema_fast)
            & (frame["rsi"] <= 58.0)
            & (frame["rsi"] >= 25.0)
        )
        strength = (
            0.38 * (spread.abs() / 2.0).clip(0.0, 1.0)
            + 0.24 * (adx / 40.0).clip(0.0, 1.0)
            + 0.20 * (body_atr / 1.0).clip(0.0, 1.0)
            + 0.18 * (rvol / 2.0).clip(0.0, 1.0)
        )
    elif cfg.arm == "breakout":
        upper = frame[f"donchian_high_{cfg.indicator_window}"]
        lower = frame[f"donchian_low_{cfg.indicator_window}"]
        long_distance = (close - upper) / atr.replace(0.0, np.nan)
        short_distance = (lower - close) / atr.replace(0.0, np.nan)
        long = long_distance >= cfg.threshold
        short = short_distance >= cfg.threshold
        distance = pd.concat([long_distance, short_distance], axis=1).max(axis=1)
        strength = (
            0.38 * (distance / 1.0).clip(0.0, 1.0)
            + 0.24 * (body_atr / 1.25).clip(0.0, 1.0)
            + 0.22 * (rvol / 2.0).clip(0.0, 1.0)
            + 0.16 * (adx / 40.0).clip(0.0, 1.0)
        )
    else:
        z = frame[f"z_{cfg.indicator_window}"]
        rvwap = frame[f"rvwap_{cfg.indicator_window}"]
        distance = (close - rvwap) / atr.replace(0.0, np.nan)
        long = (z <= -cfg.threshold) & (distance <= -cfg.max_dist_atr)
        short = (z >= cfg.threshold) & (distance >= cfg.max_dist_atr)
        if cfg.require_body_direction:
            long &= close > open_
            short &= close < open_
        strength = (
            0.45 * (z.abs() / 3.0).clip(0.0, 1.0)
            + 0.25 * (distance.abs() / 3.0).clip(0.0, 1.0)
            + 0.15 * (body_atr / 0.8).clip(0.0, 1.0)
            + 0.15 * (1.0 - (adx / 45.0).clip(0.0, 1.0))
        )
    if cfg.require_body_direction and cfg.arm != "mean_reversion":
        long &= close > open_
        short &= close < open_
    if cfg.require_h4_alignment:
        if cfg.arm == "mean_reversion":
            long &= ~((h4_fast < h4_slow) & (frame["regime_trendiness"] > 0.72))
            short &= ~((h4_fast > h4_slow) & (frame["regime_trendiness"] > 0.72))
        else:
            long &= h4_long
            short &= h4_short
    long &= common
    short &= common
    if cfg.side_mode == "long":
        short &= False
    elif cfg.side_mode == "short":
        long &= False
    conflict = long & short
    long &= ~conflict
    short &= ~conflict
    side = np.where(long, 1, np.where(short, -1, 0)).astype(np.int8)
    score = np.asarray(strength.clip(0.0, 1.0).fillna(0.0), dtype=np.float64)
    return side, score


def funding_arrays(funding: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    times = (
        funding["ts"]
        .astype("datetime64[ns, UTC]")
        .astype("int64")
        .to_numpy()
    )
    rates = funding["funding_rate"].to_numpy(dtype=np.float64)
    return times, np.concatenate(([0.0], np.cumsum(rates)))


def funding_return(
    side: int,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    funding_times: np.ndarray,
    funding_prefix: np.ndarray,
) -> float:
    entry_ns = int(entry_ts.value)
    exit_ns = int(exit_ts.value)
    left = int(np.searchsorted(funding_times, entry_ns, side="left"))
    right = int(np.searchsorted(funding_times, exit_ns, side="left"))
    return float(-side * (funding_prefix[right] - funding_prefix[left]))


def _adverse_fill(price: float, side: int, *, is_entry: bool, slippage: float) -> float:
    direction = side if is_entry else -side
    return float(price * (1.0 + direction * slippage))


def simulate_opportunities(
    frame: pd.DataFrame,
    funding: pd.DataFrame,
    cfg: StrategyConfig,
    *,
    end: pd.Timestamp,
    slippage: float = BASE_SLIPPAGE,
) -> list[Opportunity]:
    side_array, score_array = build_signal(frame, cfg)
    funding_times, funding_prefix = funding_arrays(funding)
    open_ = frame["open"].to_numpy(dtype=np.float64)
    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    atr = frame["atr"].to_numpy(dtype=np.float64)
    ts = frame["ts"].tolist()
    opportunities: list[Opportunity] = []
    for signal_i in np.flatnonzero(side_array):
        entry_i = int(signal_i + 1)
        if entry_i >= len(frame) or ts[entry_i] >= end or not np.isfinite(atr[signal_i]):
            continue
        side = int(side_array[signal_i])
        entry_fill = _adverse_fill(open_[entry_i], side, is_entry=True, slippage=slippage)
        stop = entry_fill - side * cfg.sl_atr * atr[signal_i]
        target = entry_fill + side * cfg.tp_atr * atr[signal_i]
        exit_i = min(entry_i + cfg.max_hold_bars, len(frame) - 1)
        exit_base = open_[exit_i]
        exit_reason = "time_open"
        for index in range(entry_i, min(entry_i + cfg.max_hold_bars, len(frame))):
            if side > 0:
                if open_[index] <= stop:
                    exit_i, exit_base, exit_reason = index, open_[index], "gap_stop"
                    break
                if open_[index] >= target:
                    exit_i, exit_base, exit_reason = index, open_[index], "gap_target"
                    break
                stop_hit = low[index] <= stop
                target_hit = high[index] >= target
                if stop_hit:
                    exit_i, exit_base, exit_reason = index, stop, "stop"
                    break
                if target_hit:
                    exit_i, exit_base, exit_reason = index, target, "target"
                    break
            else:
                if open_[index] >= stop:
                    exit_i, exit_base, exit_reason = index, open_[index], "gap_stop"
                    break
                if open_[index] <= target:
                    exit_i, exit_base, exit_reason = index, open_[index], "gap_target"
                    break
                stop_hit = high[index] >= stop
                target_hit = low[index] <= target
                if stop_hit:
                    exit_i, exit_base, exit_reason = index, stop, "stop"
                    break
                if target_hit:
                    exit_i, exit_base, exit_reason = index, target, "target"
                    break
        if exit_i >= len(frame) or ts[exit_i] >= end:
            continue
        exit_fill = _adverse_fill(exit_base, side, is_entry=False, slippage=slippage)
        price_return = float(side * (exit_fill / entry_fill - 1.0))
        funding_ret = funding_return(
            side,
            ts[entry_i],
            ts[exit_i],
            funding_times,
            funding_prefix,
        )
        fee_ret = -2.0 * FEE_PER_FILL
        net = price_return + funding_ret + fee_ret
        opportunities.append(
            Opportunity(
                symbol=cfg.symbol,
                arm=cfg.arm,
                config_id=cfg.config_id,
                signal_i=int(signal_i),
                entry_i=entry_i,
                exit_i=int(exit_i),
                side=side,
                signal_ts=ts[signal_i],
                entry_ts=ts[entry_i],
                exit_ts=ts[exit_i],
                entry_fill=entry_fill,
                exit_fill=exit_fill,
                score=float(score_array[signal_i]),
                regime_trendiness=float(frame["regime_trendiness"].iloc[signal_i]),
                price_return_1x=price_return,
                funding_return_1x=funding_ret,
                fee_return_1x=fee_ret,
                net_return_1x=net,
                exit_reason=exit_reason,
            )
        )
    return opportunities


def select_nonoverlap(opportunities: Iterable[Opportunity]) -> list[Opportunity]:
    selected: list[Opportunity] = []
    blocked_until = pd.Timestamp.min.tz_localize("UTC")
    for opportunity in sorted(opportunities, key=lambda item: (item.entry_ts, item.exit_ts)):
        if opportunity.entry_ts < blocked_until:
            continue
        selected.append(opportunity)
        blocked_until = opportunity.exit_ts
    return selected


def _equity_metrics(returns: list[float]) -> tuple[float, float, float]:
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for value in returns:
        equity *= max(1e-9, 1.0 + value)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    return equity, equity - 1.0, max_dd


def metrics_from_returns(
    returns: list[float],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    equity, total_return, max_dd = _equity_metrics(returns)
    years = max((end - start).total_seconds() / (365.25 * 24.0 * 3600.0), 1.0 / 365.25)
    annual_multiple = float(equity ** (1.0 / years)) if equity > 0.0 else 0.0
    positives = [value for value in returns if value > 0.0]
    negatives = [value for value in returns if value <= 0.0]
    gross_profit = sum(positives)
    gross_loss = abs(sum(negatives))
    profit_factor = gross_profit / gross_loss if gross_loss > 0.0 else 999.0
    return {
        "trades": float(len(returns)),
        "wins": float(len(positives)),
        "win_rate": float(len(positives) / len(returns)) if returns else 0.0,
        "total_return": float(total_return),
        "annual_multiple": annual_multiple,
        "max_dd": float(max_dd),
        "profit_factor": float(profit_factor),
        "avg_return": float(np.mean(returns)) if returns else 0.0,
        "avg_win": float(np.mean(positives)) if positives else 0.0,
        "avg_loss": float(np.mean(negatives)) if negatives else 0.0,
        "worst_trade": float(min(returns)) if returns else 0.0,
    }


def opportunity_metrics(
    opportunities: Iterable[Opportunity],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    selected = [
        item
        for item in select_nonoverlap(opportunities)
        if start <= item.entry_ts < end and item.exit_ts < end
    ]
    return metrics_from_returns(
        [item.net_return_1x for item in selected], start=start, end=end
    )


def candidate_score(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> float:
    if (
        prefit["trades"] < 10
        or validation["trades"] < 3
        or prefit["max_dd"] <= -0.50
    ):
        return -1e9
    return float(
        6.0 * prefit["win_rate"]
        + 3.0 * validation["win_rate"]
        + 2.5 * math.log(max(prefit["profit_factor"], 1e-6))
        + 1.0 * math.log(max(prefit["annual_multiple"], 1e-6))
        + 2.0 * prefit["max_dd"]
        + 0.15 * math.log1p(prefit["trades"])
        + 10.0 * min(train["total_return"], 0.0)
        + 15.0 * min(validation["total_return"], 0.0)
    )


def route_candidates(
    opportunities: Iterable[Opportunity],
    *,
    route: Route,
    conflict_margin: float,
) -> dict[pd.Timestamp, list[RoutedOpportunity]]:
    by_time_symbol: dict[tuple[pd.Timestamp, str], list[Opportunity]] = {}
    for item in opportunities:
        by_time_symbol.setdefault((item.entry_ts, item.symbol), []).append(item)
    routed_by_time: dict[pd.Timestamp, list[RoutedOpportunity]] = {}
    for (entry_ts, _symbol), items in by_time_symbol.items():
        if route == "independent":
            routed_by_time.setdefault(entry_ts, []).extend(
                RoutedOpportunity(item, item.score, 1) for item in items
            )
            continue
        adjusted: list[tuple[Opportunity, float]] = []
        for item in items:
            trendiness = item.regime_trendiness
            if item.arm == "mean_reversion":
                weight = 1.15 - 0.9 * trendiness
            elif item.arm == "breakout":
                weight = 0.45 + 0.65 * trendiness
            else:
                weight = 0.55 + 0.55 * trendiness
            adjusted.append((item, float(np.clip(item.score * weight, 0.0, 1.25))))
        adjusted.sort(key=lambda pair: pair[1], reverse=True)
        best_item, best_score = adjusted[0]
        opposite = [score for item, score in adjusted[1:] if item.side != best_item.side]
        if opposite and best_score - max(opposite) < conflict_margin:
            continue
        support = [score for item, score in adjusted[1:] if item.side == best_item.side]
        fused_score = min(1.25, best_score + 0.12 * sum(support[:2]))
        routed_by_time.setdefault(entry_ts, []).append(
            RoutedOpportunity(best_item, fused_score, 1 + len(support))
        )
    return routed_by_time


def _choose_best(
    candidates: Iterable[RoutedOpportunity], entry_threshold: float
) -> RoutedOpportunity | None:
    valid = [item for item in candidates if item.route_score >= entry_threshold]
    if not valid:
        return None
    return max(
        valid,
        key=lambda item: (
            item.route_score,
            item.support_count,
            item.opportunity.score,
            item.opportunity.symbol,
            item.opportunity.arm,
        ),
    )


def _truncate_return(
    current: RoutedOpportunity,
    *,
    exit_ts: pd.Timestamp,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
    slippage: float,
) -> float:
    opportunity = current.opportunity
    frame = frames[opportunity.symbol]
    row = frame.loc[frame["ts"] == exit_ts]
    if len(row) != 1:
        raise RuntimeError(f"cannot locate {opportunity.symbol} switch open {exit_ts}")
    exit_base = float(row["open"].iloc[0])
    exit_fill = _adverse_fill(
        exit_base, opportunity.side, is_entry=False, slippage=slippage
    )
    price_return = opportunity.side * (exit_fill / opportunity.entry_fill - 1.0)
    funding_times, funding_prefix = funding_arrays(fundings[opportunity.symbol])
    funding_ret = funding_return(
        opportunity.side,
        opportunity.entry_ts,
        exit_ts,
        funding_times,
        funding_prefix,
    )
    return float(price_return + funding_ret - 2.0 * FEE_PER_FILL)


def replay_portfolio(
    opportunities: Iterable[Opportunity],
    route_config: RouteConfig,
    *,
    frames: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
    slippage: float = BASE_SLIPPAGE,
) -> list[PortfolioTrade]:
    routed = route_candidates(
        opportunities,
        route=route_config.route,
        conflict_margin=route_config.conflict_margin,
    )
    timeline = sorted(ts for ts in routed if start <= ts < end)
    current: RoutedOpportunity | None = None
    trades: list[PortfolioTrade] = []
    for timestamp in timeline:
        if current is not None and current.opportunity.exit_ts <= timestamp:
            opportunity = current.opportunity
            trades.append(
                PortfolioTrade(
                    symbol=opportunity.symbol,
                    arm=opportunity.arm,
                    config_id=opportunity.config_id,
                    side=opportunity.side,
                    entry_ts=opportunity.entry_ts,
                    exit_ts=opportunity.exit_ts,
                    route_score=current.route_score,
                    exposure=route_config.exposure,
                    net_return=route_config.exposure * opportunity.net_return_1x,
                    exit_reason=opportunity.exit_reason,
                    preempted=False,
                )
            )
            current = None
        challenger = _choose_best(routed[timestamp], route_config.entry_threshold)
        if challenger is None:
            continue
        if current is None:
            current = challenger
            continue
        if route_config.occupancy == "nonpreemptive":
            continue
        held_bars = int(
            (timestamp - current.opportunity.entry_ts) / pd.Timedelta(hours=1)
        )
        same_identity = (
            challenger.opportunity.symbol == current.opportunity.symbol
            and challenger.opportunity.config_id == current.opportunity.config_id
        )
        if (
            same_identity
            or held_bars < route_config.min_hold_bars
            or challenger.route_score
            < current.route_score + route_config.preempt_margin
        ):
            continue
        truncated = _truncate_return(
            current,
            exit_ts=timestamp,
            frames=frames,
            fundings=fundings,
            slippage=slippage,
        )
        opportunity = current.opportunity
        trades.append(
            PortfolioTrade(
                symbol=opportunity.symbol,
                arm=opportunity.arm,
                config_id=opportunity.config_id,
                side=opportunity.side,
                entry_ts=opportunity.entry_ts,
                exit_ts=timestamp,
                route_score=current.route_score,
                exposure=route_config.exposure,
                net_return=route_config.exposure * truncated,
                exit_reason="preempted",
                preempted=True,
            )
        )
        current = challenger
    if current is not None and current.opportunity.exit_ts < end:
        opportunity = current.opportunity
        trades.append(
            PortfolioTrade(
                symbol=opportunity.symbol,
                arm=opportunity.arm,
                config_id=opportunity.config_id,
                side=opportunity.side,
                entry_ts=opportunity.entry_ts,
                exit_ts=opportunity.exit_ts,
                route_score=current.route_score,
                exposure=route_config.exposure,
                net_return=route_config.exposure * opportunity.net_return_1x,
                exit_reason=opportunity.exit_reason,
                preempted=False,
            )
        )
    return sorted(trades, key=lambda item: (item.entry_ts, item.exit_ts))


def portfolio_metrics(
    trades: Iterable[PortfolioTrade],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end and trade.exit_ts < end]
    result = metrics_from_returns(
        [trade.net_return for trade in selected], start=start, end=end
    )
    result["preemptions"] = float(sum(trade.preempted for trade in selected))
    result["long_trades"] = float(sum(trade.side > 0 for trade in selected))
    result["short_trades"] = float(sum(trade.side < 0 for trade in selected))
    return result


def portfolio_score(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> tuple[bool, float]:
    hard = bool(
        prefit["trades"] >= 150
        and prefit["win_rate"] >= 0.80
        and prefit["max_dd"] > -0.20
        and validation["trades"] >= 30
        and validation["win_rate"] >= 0.78
        and validation["total_return"] > 0.0
    )
    score = float(
        8.0 * prefit["win_rate"]
        + 3.0 * validation["win_rate"]
        + 0.8 * math.log(max(prefit["annual_multiple"], 1e-9))
        + 0.6 * math.log(max(prefit["profit_factor"], 1e-9))
        + 3.0 * prefit["max_dd"]
        + 0.25 * math.log1p(prefit["trades"])
    )
    return hard, score


def replace_config_id(cfg: StrategyConfig, suffix: str) -> StrategyConfig:
    return replace(cfg, config_id=f"{cfg.config_id}_{suffix}")
