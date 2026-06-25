from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"
REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_indicator_search.json")
RANKING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_indicator_search_ranking.csv")
TARGET_HITS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_indicator_search_target_hits.csv")
TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_indicator_search_top_trades.csv")

START_TS = pd.Timestamp("2025-06-01T00:00:00Z")
END_TS = pd.Timestamp("2026-06-01T00:00:00Z")
IS_END_TS = pd.Timestamp("2026-03-01T00:00:00Z")

FEE_RATE = 0.0004
SLIPPAGE_RATE = 0.0001
TARGET_ANNUALIZED_MULTIPLE = 20.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DD = -0.20
LEVERAGE_GRID = (1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0)


@dataclass(frozen=True, slots=True)
class SearchConfig:
    name: str
    side_mode: str
    ema_fast: int
    ema_slow: int
    entry_style: str
    donchian: int
    roc_window: int
    min_regime_age: int
    max_regime_age: int
    breakout_buffer: float
    pullback_buffer: float
    max_dist_ema: float
    min_dir_roc: float
    min_dir_rsi: float
    max_dir_rsi: float
    min_adx: float
    max_chop: float
    max_atr_ratio: float
    min_rvol: float
    min_dir_cmf: float
    require_macd: bool
    require_obv: bool
    require_htf: bool
    min_efficiency: float
    stop_atr: float
    tp_atr: float
    trail_atr: float
    max_hold_bars: int
    min_hold_bars: int
    exit_ema: int
    cooldown_bars: int


@dataclass(slots=True)
class Trade:
    config: str
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    entry_price: float
    exit_price: float
    reason: str
    bars_held: int
    net_ret_1x: float
    mae_1x: float
    mfe_1x: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HYPE Binance perp 5m broad indicator strategy search.")
    parser.add_argument("--max-configs", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260622)
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--min-trades", type=int, default=20)
    parser.add_argument("--max-signals", type=int, default=6000)
    return parser.parse_args()


def load_hype_5m() -> pd.DataFrame:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no local HYPE 5m parquet files under {DATA_ROOT}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    frame = frame.loc[(frame["ts"] >= START_TS) & (frame["ts"] < END_TS)].reset_index(drop=True)
    expected = pd.date_range(START_TS, END_TS - pd.Timedelta(minutes=5), freq="5min")
    missing = expected.difference(frame["ts"])
    if len(missing):
        raise RuntimeError(f"HYPE 5m data has {len(missing)} missing bars, first={missing[0]}")
    return frame


def rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / std.replace(0.0, np.nan)


def add_adx(frame: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = pd.concat([(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = 100 * pd.Series(plus_dm, index=frame.index).ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr
    minus_di = 100 * pd.Series(minus_dm, index=frame.index).ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    result = frame.copy()
    result["adx14"] = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    result["plus_di14"] = plus_di
    result["minus_di14"] = minus_di
    return result


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    volume = result["volume"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    for span in (9, 12, 21, 34, 55, 96, 144, 192, 288, 384):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    for window in (14, 28, 96, 288):
        result[f"atr{window}"] = tr.rolling(window, min_periods=window).mean()
    result["atr_ratio_14_96"] = result["atr14"] / result["atr96"].replace(0.0, np.nan)
    result["atr_pct_96"] = result["atr96"] / close.replace(0.0, np.nan)

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    for window in (14, 28):
        avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        result[f"rsi{window}"] = 100 - 100 / (1 + rs)

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    result["macd_hist"] = macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()

    mfv = ((close - low) - (high - close)) / (high - low).replace(0.0, np.nan) * volume
    result["cmf20"] = mfv.rolling(20, min_periods=20).sum() / volume.rolling(20, min_periods=20).sum().replace(0.0, np.nan)
    obv_step = np.sign(close.diff()).fillna(0.0) * volume
    result["obv"] = obv_step.cumsum()
    result["obv_slope48"] = result["obv"].diff(48) / volume.rolling(96, min_periods=96).sum().replace(0.0, np.nan)

    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    result["bb_width20"] = 4 * std / mid.replace(0.0, np.nan)
    result["bb_pos20"] = (close - (mid - 2 * std)) / (4 * std).replace(0.0, np.nan)
    result["bb_width_z192"] = rolling_zscore(result["bb_width20"], 192)
    result["squeeze_recent"] = result["bb_width_z192"].shift(1).rolling(48, min_periods=1).min() <= -0.75

    high14 = high.rolling(14, min_periods=14).max()
    low14 = low.rolling(14, min_periods=14).min()
    tr14 = (high - low).rolling(14, min_periods=14).sum()
    result["chop14"] = 100 * np.log10(tr14 / (high14 - low14).replace(0.0, np.nan)) / np.log10(14)
    result["eff96"] = close.pct_change(96).abs() / close.pct_change().abs().rolling(96, min_periods=96).sum().replace(0.0, np.nan)
    result["rvol96"] = volume / volume.rolling(96, min_periods=96).mean().replace(0.0, np.nan)
    result["htf_spread"] = result["ema96"] - result["ema384"]

    for window in (24, 48, 96, 192, 288):
        result[f"roc{window}"] = close.pct_change(window)
        result[f"donchian_high{window}"] = high.shift(1).rolling(window, min_periods=window).max()
        result[f"donchian_low{window}"] = low.shift(1).rolling(window, min_periods=window).min()
    return add_adx(result)


def regime_age(direction: np.ndarray) -> np.ndarray:
    age = np.zeros(len(direction), dtype=np.int32)
    last = 0
    current = 0
    for i, value in enumerate(direction):
        if value == 0 or value != current:
            current = value
            last = i
        age[i] = i - last
    return age


def build_signal(frame: pd.DataFrame, cfg: SearchConfig) -> np.ndarray:
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    if cfg.side_mode == "long":
        direction = np.where(direction > 0, 1, 0).astype(np.int8)
    elif cfg.side_mode == "short":
        direction = np.where(direction < 0, -1, 0).astype(np.int8)

    age = regime_age(direction)
    dir_roc = direction * frame[f"roc{cfg.roc_window}"].to_numpy("float64")
    dir_rsi = np.where(direction > 0, frame["rsi14"].to_numpy("float64"), 100 - frame["rsi14"].to_numpy("float64"))
    dir_macd = direction * frame["macd_hist"].to_numpy("float64")
    dir_cmf = direction * frame["cmf20"].to_numpy("float64")
    dir_obv = direction * frame["obv_slope48"].to_numpy("float64")
    dir_htf = direction * frame["htf_spread"].to_numpy("float64")
    dist = np.abs(close / ema_fast - 1.0)
    don_high = frame[f"donchian_high{cfg.donchian}"].to_numpy("float64")
    don_low = frame[f"donchian_low{cfg.donchian}"].to_numpy("float64")

    rsi_filter = (dir_rsi >= cfg.min_dir_rsi) & (dir_rsi <= cfg.max_dir_rsi)
    roc_filter = dir_roc >= cfg.min_dir_roc
    if cfg.entry_style in {"trend_rsi_rebound", "bb_reversion", "ema_deviation_revert"}:
        rsi_filter = dir_rsi <= cfg.max_dir_rsi
        roc_filter = dir_roc >= -0.03

    base = (
        (direction != 0)
        & (age >= cfg.min_regime_age)
        & (age <= cfg.max_regime_age)
        & (dist <= cfg.max_dist_ema)
        & roc_filter
        & rsi_filter
        & (frame["adx14"].to_numpy("float64") >= cfg.min_adx)
        & (frame["chop14"].to_numpy("float64") <= cfg.max_chop)
        & (frame["atr_ratio_14_96"].to_numpy("float64") <= cfg.max_atr_ratio)
        & (frame["rvol96"].to_numpy("float64") >= cfg.min_rvol)
        & (dir_cmf >= cfg.min_dir_cmf)
        & (frame["eff96"].to_numpy("float64") >= cfg.min_efficiency)
    )
    if cfg.require_macd:
        base &= dir_macd > 0
    if cfg.require_obv:
        base &= dir_obv > 0
    if cfg.require_htf:
        base &= dir_htf > 0

    if cfg.entry_style == "breakout":
        entry = np.where(direction > 0, close >= don_high * (1.0 - cfg.breakout_buffer), close <= don_low * (1.0 + cfg.breakout_buffer))
    elif cfg.entry_style == "squeeze_breakout":
        breakout = np.where(direction > 0, close >= don_high * (1.0 - cfg.breakout_buffer), close <= don_low * (1.0 + cfg.breakout_buffer))
        entry = breakout & frame["squeeze_recent"].fillna(False).to_numpy(bool)
    elif cfg.entry_style == "pullback_resume":
        touched = np.where(direction > 0, low <= ema_fast * (1.0 + cfg.pullback_buffer), high >= ema_fast * (1.0 - cfg.pullback_buffer))
        reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
        candle = np.where(direction > 0, close > frame["open"].to_numpy("float64"), close < frame["open"].to_numpy("float64"))
        entry = touched & reclaimed & candle
    elif cfg.entry_style == "momentum":
        entry = dir_roc >= cfg.min_dir_roc * 1.5
    elif cfg.entry_style == "cross_fresh":
        entry = age <= min(cfg.max_regime_age, cfg.donchian)
    elif cfg.entry_style == "channel_reclaim":
        channel_mid = (don_high + don_low) / 2.0
        entry = np.where(direction > 0, close > channel_mid, close < channel_mid) & (dist <= cfg.max_dist_ema * 0.75)
    elif cfg.entry_style == "trend_rsi_rebound":
        rsi = frame["rsi14"].to_numpy("float64")
        rsi_prev = np.r_[np.nan, rsi[:-1]]
        long_rebound = (direction > 0) & (rsi_prev <= cfg.min_dir_rsi) & (rsi > rsi_prev + 1.0) & (close > frame["open"].to_numpy("float64"))
        short_rebound = (direction < 0) & (rsi_prev >= 100.0 - cfg.min_dir_rsi) & (rsi < rsi_prev - 1.0) & (close < frame["open"].to_numpy("float64"))
        entry = long_rebound | short_rebound
    elif cfg.entry_style == "bb_reversion":
        bb_pos = frame["bb_pos20"].to_numpy("float64")
        long_revert = (direction > 0) & (bb_pos <= 0.25) & (close > frame["open"].to_numpy("float64"))
        short_revert = (direction < 0) & (bb_pos >= 0.75) & (close < frame["open"].to_numpy("float64"))
        entry = long_revert | short_revert
    elif cfg.entry_style == "ema_deviation_revert":
        raw_dist = close / ema_fast - 1.0
        long_revert = (direction > 0) & (raw_dist <= -cfg.pullback_buffer) & (close > frame["open"].to_numpy("float64"))
        short_revert = (direction < 0) & (raw_dist >= cfg.pullback_buffer) & (close < frame["open"].to_numpy("float64"))
        entry = long_revert | short_revert
    else:
        raise ValueError(cfg.entry_style)

    signal = np.zeros(len(frame), dtype=np.int8)
    mask = np.nan_to_num(base & entry, nan=False).astype(bool)
    signal[mask] = direction[mask]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def first_event_offset(mask: np.ndarray) -> int | None:
    indices = np.flatnonzero(mask)
    if len(indices) == 0:
        return None
    return int(indices[0])


def simulate_trades(frame: pd.DataFrame, signal: np.ndarray, cfg: SearchConfig) -> list[Trade]:
    if "_ts_ns" in frame.columns:
        ts_ns = frame["_ts_ns"].to_numpy("int64")
    else:
        ts_ns = frame["ts"].map(lambda value: pd.Timestamp(value).value).to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    exit_ema = frame[f"ema{cfg.exit_ema}"].to_numpy("float64") if cfg.exit_ema else np.full(len(frame), np.nan)
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        atr_value = float(atr[sig_i])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * SLIPPAGE_RATE))
        stop_price = entry_price - direction * cfg.stop_atr * atr_value
        target_price = entry_price + direction * cfg.tp_atr * atr_value
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        sl = slice(entry_i, end_i + 1)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]

        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.full(len(high_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.maximum(stop_levels, prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
            target_hit = high_seg >= target_price
            ema_exit = close_seg < exit_ema[sl] if cfg.exit_ema else np.zeros(len(high_seg), dtype=bool)
            mae = float(np.nanmin(low_seg / entry_price - 1.0))
            mfe = float(np.nanmax(high_seg / entry_price - 1.0))
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.full(len(low_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.minimum(stop_levels, prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
            target_hit = low_seg <= target_price
            ema_exit = close_seg > exit_ema[sl] if cfg.exit_ema else np.zeros(len(low_seg), dtype=bool)
            mae = float(np.nanmin(direction * (high_seg / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (low_seg / entry_price - 1.0)))

        if cfg.min_hold_bars > 0:
            stop_hit[: cfg.min_hold_bars] = False
            target_hit[: cfg.min_hold_bars] = False
            ema_exit[: cfg.min_hold_bars] = False
        event_mask = stop_hit | target_hit | ema_exit
        offset = first_event_offset(event_mask)
        reason = "time"
        if offset is None:
            offset = len(close_seg) - 1
            exit_price = float(close_seg[offset])
        elif stop_hit[offset]:
            reason = "stop"
            exit_price = float(stop_levels[offset])
        elif target_hit[offset]:
            reason = "target"
            exit_price = float(target_price)
        else:
            reason = "ema_exit"
            exit_price = float(close_seg[offset])

        exit_i = entry_i + offset
        exit_price = float(exit_price * (1.0 - direction * SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        net = gross - 2 * FEE_RATE
        trades.append(
            Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades


def metric_from_trades(trades: list[Trade], leverage: float, *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    if not selected:
        return {
            "trades": 0,
            "equity_multiple": 1.0,
            "annualized_multiple": 1.0,
            "total_return": 0.0,
            "max_dd": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade": 0.0,
            "worst_trade": 0.0,
        }
    rets = np.array([trade.net_ret_1x * leverage for trade in selected], dtype=float)
    maes = np.array([trade.mae_1x * leverage for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    bankrupt = False
    for ret, mae in zip(rets, maes, strict=True):
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= 1.0 + ret
        if equity <= 0:
            equity = 0.001
            bankrupt = True
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        if bankrupt:
            break
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    return {
        "trades": int(len(selected)),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((rets > 0).mean()),
        "profit_factor": profit_factor,
        "avg_trade": float(rets.mean()),
        "worst_trade": float(rets.min()),
    }


def random_config(rng: random.Random, idx: int) -> SearchConfig:
    ema_fast, ema_slow = rng.choice(
        [
            (9, 55),
            (12, 96),
            (21, 96),
            (34, 144),
            (55, 192),
            (96, 384),
        ]
    )
    entry_style = rng.choice(
        [
            "breakout",
            "pullback_resume",
            "momentum",
            "cross_fresh",
            "squeeze_breakout",
            "channel_reclaim",
            "trend_rsi_rebound",
            "bb_reversion",
            "ema_deviation_revert",
        ]
    )
    donchian = rng.choice([24, 48, 96, 192, 288])
    max_age = rng.choice([48, 96, 192, 384, 768, 2000])
    min_age = rng.choice([0, 3, 6, 12, 24])
    if min_age >= max_age:
        min_age = 0
    stop_atr = rng.choice([1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0])
    tp_atr = rng.choice([0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0])
    if tp_atr < stop_atr * 0.7:
        tp_atr = stop_atr * rng.choice([0.8, 1.0, 1.2, 1.5])
    cfg = SearchConfig(
        name=f"HYPE_5M_R{idx:05d}",
        side_mode=rng.choice(["both", "both", "long", "short"]),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        entry_style=entry_style,
        donchian=donchian,
        roc_window=rng.choice([24, 48, 96, 192]),
        min_regime_age=min_age,
        max_regime_age=max_age,
        breakout_buffer=rng.choice([0.0, 0.001, 0.002, 0.004, 0.006]),
        pullback_buffer=rng.choice([0.0, 0.0025, 0.005, 0.01, 0.015, 0.025]),
        max_dist_ema=rng.choice([0.015, 0.025, 0.04, 0.06, 0.08, 0.12, 0.20]),
        min_dir_roc=rng.choice([-0.01, -0.0025, 0.0, 0.0025, 0.005, 0.01, 0.02]),
        min_dir_rsi=rng.choice([35.0, 40.0, 45.0, 50.0, 55.0]),
        max_dir_rsi=rng.choice([65.0, 70.0, 75.0, 82.0, 95.0, 100.0]),
        min_adx=rng.choice([0.0, 14.0, 18.0, 22.0, 26.0, 30.0, 35.0]),
        max_chop=rng.choice([42.0, 48.0, 55.0, 62.0, 70.0, 100.0]),
        max_atr_ratio=rng.choice([0.85, 1.0, 1.15, 1.35, 1.6, 2.0, 99.0]),
        min_rvol=rng.choice([0.0, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0]),
        min_dir_cmf=rng.choice([-0.30, -0.15, -0.05, 0.0, 0.05, 0.10]),
        require_macd=rng.choice([False, False, True]),
        require_obv=rng.choice([False, False, True]),
        require_htf=rng.choice([False, False, True]),
        min_efficiency=rng.choice([0.0, 0.05, 0.10, 0.15, 0.20, 0.30]),
        stop_atr=stop_atr,
        tp_atr=tp_atr,
        trail_atr=rng.choice([0.0, 1.5, 2.0, 3.0, 4.0, 6.0]),
        max_hold_bars=rng.choice([6, 12, 24, 48, 96, 192, 384, 576]),
        min_hold_bars=rng.choice([0, 1, 3, 6, 12]),
        exit_ema=rng.choice([0, 9, 21, 55, 96, 144]),
        cooldown_bars=rng.choice([0, 3, 6, 12, 24, 48]),
    )
    return cfg


def curated_configs() -> list[SearchConfig]:
    configs: list[SearchConfig] = []
    idx = 0
    for side_mode in ("both", "long", "short"):
        for ema_fast, ema_slow in ((21, 96), (34, 144), (55, 192), (96, 384)):
            for entry_style in ("breakout", "pullback_resume", "channel_reclaim"):
                for stop_atr, tp_atr, trail_atr in ((2.0, 3.0, 2.0), (2.5, 4.0, 3.0), (3.0, 6.0, 4.0), (4.0, 8.0, 6.0)):
                    idx += 1
                    configs.append(
                        SearchConfig(
                            name=f"HYPE_5M_C{idx:04d}",
                            side_mode=side_mode,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            entry_style=entry_style,
                            donchian=96,
                            roc_window=48,
                            min_regime_age=3,
                            max_regime_age=384,
                            breakout_buffer=0.002,
                            pullback_buffer=0.01,
                            max_dist_ema=0.06,
                            min_dir_roc=0.0,
                            min_dir_rsi=45.0,
                            max_dir_rsi=82.0,
                            min_adx=18.0,
                            max_chop=62.0,
                            max_atr_ratio=1.6,
                            min_rvol=0.8,
                            min_dir_cmf=-0.05,
                            require_macd=True,
                            require_obv=False,
                            require_htf=True,
                            min_efficiency=0.10,
                            stop_atr=stop_atr,
                            tp_atr=tp_atr,
                            trail_atr=trail_atr,
                            max_hold_bars=192,
                            min_hold_bars=3,
                            exit_ema=55,
                            cooldown_bars=12,
                        )
                    )
    for side_mode in ("both", "long", "short"):
        for ema_fast, ema_slow in ((12, 96), (21, 96), (34, 144), (55, 192), (96, 384)):
            for entry_style in ("trend_rsi_rebound", "bb_reversion", "ema_deviation_revert"):
                for stop_atr, tp_atr, trail_atr, max_hold in (
                    (4.0, 0.75, 0.0, 12),
                    (6.0, 1.0, 0.0, 24),
                    (8.0, 1.25, 0.0, 24),
                    (10.0, 1.5, 0.0, 48),
                    (6.0, 1.5, 2.0, 48),
                    (8.0, 2.0, 3.0, 96),
                ):
                    idx += 1
                    configs.append(
                        SearchConfig(
                            name=f"HYPE_5M_C{idx:04d}",
                            side_mode=side_mode,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            entry_style=entry_style,
                            donchian=48,
                            roc_window=24,
                            min_regime_age=0,
                            max_regime_age=768,
                            breakout_buffer=0.0,
                            pullback_buffer=0.005,
                            max_dist_ema=0.12,
                            min_dir_roc=-0.01,
                            min_dir_rsi=42.0,
                            max_dir_rsi=80.0,
                            min_adx=0.0,
                            max_chop=100.0,
                            max_atr_ratio=2.0,
                            min_rvol=0.0,
                            min_dir_cmf=-0.30,
                            require_macd=False,
                            require_obv=False,
                            require_htf=True,
                            min_efficiency=0.0,
                            stop_atr=stop_atr,
                            tp_atr=tp_atr,
                            trail_atr=trail_atr,
                            max_hold_bars=max_hold,
                            min_hold_bars=0,
                            exit_ema=0,
                            cooldown_bars=6,
                        )
                    )
    return configs


def build_configs(max_configs: int, seed: int) -> list[SearchConfig]:
    rng = random.Random(seed)
    configs = curated_configs()
    seen = {json.dumps(asdict(cfg), sort_keys=True) for cfg in configs}
    idx = 0
    while len(configs) < max_configs:
        idx += 1
        cfg = random_config(rng, idx)
        key = json.dumps(asdict(cfg) | {"name": ""}, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        configs.append(cfg)
    return configs[:max_configs]


def target_gap(metrics: dict[str, Any]) -> float:
    return (
        max(0.0, TARGET_ANNUALIZED_MULTIPLE - float(metrics["annualized_multiple"])) / TARGET_ANNUALIZED_MULTIPLE
        + max(0.0, TARGET_WIN_RATE - float(metrics["win_rate"])) * 5
        + max(0.0, TARGET_MAX_DD - float(metrics["max_dd"])) * 5
    )


def row_for(cfg: SearchConfig, trades: list[Trade], leverage: float, min_trades: int) -> dict[str, Any]:
    full = metric_from_trades(trades, leverage, start=START_TS, end=END_TS)
    in_sample = metric_from_trades(trades, leverage, start=START_TS, end=IS_END_TS)
    oos = metric_from_trades(trades, leverage, start=IS_END_TS, end=END_TS)
    hit = (
        full["trades"] >= min_trades
        and full["annualized_multiple"] >= TARGET_ANNUALIZED_MULTIPLE
        and full["win_rate"] >= TARGET_WIN_RATE
        and full["max_dd"] >= TARGET_MAX_DD
    )
    row = {
        "name": cfg.name,
        "target_pass": bool(hit),
        "target_gap": target_gap(full) + max(0.0, min_trades - float(full["trades"])) / max(float(min_trades), 1.0),
        "leverage": leverage,
        **{f"full_{key}": value for key, value in full.items()},
        **{f"is_{key}": value for key, value in in_sample.items()},
        **{f"oos_{key}": value for key, value in oos.items()},
        **asdict(cfg),
    }
    row["score"] = (
        float(row["full_annualized_multiple"])
        + 30 * float(row["full_win_rate"])
        + 10 * float(row["full_max_dd"])
        + 5 * min(float(row["oos_win_rate"]), float(row["is_win_rate"]))
    )
    return row


def safe_float(value: Any) -> Any:
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return value


def main() -> None:
    args = parse_args()
    frame = add_features(load_hype_5m())
    configs = build_configs(args.max_configs, args.seed)
    rows: list[dict[str, Any]] = []
    trade_cache: dict[str, list[Trade]] = {}
    for idx, cfg in enumerate(configs, start=1):
        signal = build_signal(frame, cfg)
        signal_count = int(np.count_nonzero(signal))
        if signal_count < max(5, args.min_trades // 2) or signal_count > args.max_signals:
            continue
        trades = simulate_trades(frame, signal, cfg)
        if len(trades) >= max(5, args.min_trades // 2):
            trade_cache[cfg.name] = trades
            for leverage in LEVERAGE_GRID:
                rows.append(row_for(cfg, trades, leverage, args.min_trades))
        if idx % 250 == 0:
            print(f"searched={idx} configs rows={len(rows)} cached={len(trade_cache)}", flush=True)

    if not rows:
        raise RuntimeError("no candidate produced enough trades")
    ranking = pd.DataFrame(rows).sort_values(["target_pass", "target_gap", "score"], ascending=[False, True, False])
    target_hits = ranking.loc[ranking["target_pass"]].copy()
    top_names = set(ranking.head(args.top)["name"]) | set(target_hits.head(args.top)["name"])
    trade_rows: list[dict[str, Any]] = []
    for name in top_names:
        for trade in trade_cache.get(name, []):
            trade_rows.append(asdict(trade))
    trades_frame = pd.DataFrame(trade_rows)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(RANKING_PATH, index=False)
    target_hits.to_csv(TARGET_HITS_PATH, index=False)
    trades_frame.to_csv(TRADES_PATH, index=False)
    report = {
        "data": {
            "symbol": "HYPE/USDT:USDT",
            "exchange": "binance",
            "market_type": "perp",
            "timeframe": "5m",
            "start": START_TS.isoformat(),
            "end_exclusive": END_TS.isoformat(),
            "bars": int(len(frame)),
        },
        "assumptions": {
            "entry": "signal confirmed on bar close, enter next bar open",
            "same_bar_stop_target": "stop wins when stop and target touch in the same bar",
            "fee_rate_per_side": FEE_RATE,
            "slippage_rate_per_side": SLIPPAGE_RATE,
            "drawdown": "includes close-to-close equity and per-trade MAE approximation",
            "target_annualized_multiple": TARGET_ANNUALIZED_MULTIPLE,
            "target_win_rate": TARGET_WIN_RATE,
            "target_max_drawdown": TARGET_MAX_DD,
        },
        "search": {
            "seed": args.seed,
            "configs": len(configs),
            "rows": len(rows),
            "target_hits": int(len(target_hits)),
            "min_trades": args.min_trades,
            "leverage_grid": list(LEVERAGE_GRID),
        },
        "top": [{key: safe_float(value) for key, value in row.items()} for row in ranking.head(args.top).to_dict(orient="records")],
        "target_hits": [
            {key: safe_float(value) for key, value in row.items()} for row in target_hits.head(args.top).to_dict(orient="records")
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"wrote={REPORT_PATH}")
    print(f"ranking={RANKING_PATH}")
    print(f"target_hits={TARGET_HITS_PATH}")
    print(f"top_trades={TRADES_PATH}")
    cols = [
        "name",
        "target_pass",
        "target_gap",
        "leverage",
        "full_annualized_multiple",
        "full_equity_multiple",
        "full_max_dd",
        "full_win_rate",
        "full_trades",
        "is_annualized_multiple",
        "is_max_dd",
        "is_win_rate",
        "oos_annualized_multiple",
        "oos_max_dd",
        "oos_win_rate",
        "entry_style",
        "ema_fast",
        "ema_slow",
        "stop_atr",
        "tp_atr",
        "trail_atr",
        "max_hold_bars",
    ]
    print(ranking[cols].head(args.top).to_string(index=False))


if __name__ == "__main__":
    main()
