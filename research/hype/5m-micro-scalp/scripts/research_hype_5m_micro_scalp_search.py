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
RAW_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_ROOT = Path("research/hype/5m-micro-scalp")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_2026-06-26.json"
SUMMARY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_summary_2026-06-26.csv"
SLICES_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_slices_2026-06-26.csv"
MONTHLY_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_monthly_2026-06-26.csv"
TOP_TRADES_PATH = ARTIFACT_ROOT / "hype_5m_micro_scalp_search_top_trades_2026-06-26.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / "hype-5m-micro-scalp-search-2026-06-26.md"

# Observed Binance live cost model copied as constants, not imported from another family:
# - fee: 3.0578 USDT / 7374.2110 USDT turnover = 4.1466 bps per fill
# - entry slippage: +10.73 bps against entry direction
# - exit slippage: -2.64 bps, the observed exit-side average from prior live audit
FEE_RATE_PER_FILL = 3.0578 / 7374.2110
ENTRY_SLIPPAGE_RATE = 10.73 / 10000.0
EXIT_SLIPPAGE_RATE = -2.64 / 10000.0

TARGET_TRADES_PER_DAY_MIN = 3.0
TARGET_TRADES_PER_DAY_MAX = 5.0
TARGET_WIN_RATE = 0.65
TARGET_MAX_DD = -0.15
TARGET_PROFIT_FACTOR = 1.05
TRAIN_END = pd.Timestamp("2026-03-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")


@dataclass(frozen=True, slots=True)
class ScalpConfig:
    name: str
    side_mode: str
    entry_style: str
    ema_fast: int
    ema_slow: int
    ema_htf: int
    donchian: int
    rsi_window: int
    rsi_low: float
    rsi_high: float
    bb_z: float
    vwap_dev_bps: float
    pullback_bps: float
    breakout_bps: float
    min_dir_roc_bps: float
    max_counter_roc_bps: float
    min_adx: float
    max_chop: float
    min_rvol: float
    min_atr_pct_bps: float
    max_atr_pct_bps: float
    max_dist_ema_bps: float
    wick_atr: float
    close_pos: float
    require_trend: bool
    require_htf: bool
    require_macd_turn: bool
    require_body_dir: bool
    tp_bps: float
    sl_bps: float
    max_hold_bars: int
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
    parser = argparse.ArgumentParser(description="Executable Binance HYPE 5m micro-scalp broad search.")
    parser.add_argument("--max-random-configs", type=int, default=30000)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--top-keep", type=int, default=120)
    parser.add_argument("--progress-every", type=int, default=1000)
    return parser.parse_args()


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def bps(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 10000:.{digits}f} bps"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def load_hype_5m() -> tuple[pd.DataFrame, dict[str, Any]]:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no local HYPE 5m parquet files under {DATA_ROOT}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    duplicate_ts = int(frame.duplicated("ts").sum())
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="5min")
    missing = expected.difference(frame["ts"])

    required = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap", "is_closed", "source"]
    nulls = {column: int(frame[column].isna().sum()) for column in required if column in frame.columns}
    violations = {
        "high_lt_max_open_close": int((frame["high"] < frame[["open", "close"]].max(axis=1)).sum()),
        "low_gt_min_open_close": int((frame["low"] > frame[["open", "close"]].min(axis=1)).sum()),
        "nonpositive_ohlc": int(((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()),
        "negative_volume": int((frame["volume"] < 0).sum()),
        "negative_quote_volume": int((frame["quote_volume"] < 0).sum()),
        "vwap_outside_hilo_nonzero_vol": int(
            (
                (frame["volume"] > 0)
                & ((frame["vwap"] < frame["low"] * 0.999999) | (frame["vwap"] > frame["high"] * 1.000001))
            ).sum()
        ),
    }
    source_counts = {str(key): int(value) for key, value in frame["source"].value_counts(dropna=False).to_dict().items()}
    closed_counts = {str(key): int(value) for key, value in frame["is_closed"].value_counts(dropna=False).to_dict().items()}
    raw_files = sorted(RAW_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    quality = {
        "normalized_file_count": len(files),
        "raw_ohlcv_file_count": len(raw_files),
        "rows": int(len(frame)),
        "start_ts": str(frame["ts"].iloc[0]),
        "end_ts": str(frame["ts"].iloc[-1]),
        "duplicate_ts": duplicate_ts,
        "expected_bars": int(len(expected)),
        "missing_bars": int(len(missing)),
        "first_missing": str(missing[0]) if len(missing) else None,
        "nulls": nulls,
        "source_counts": source_counts,
        "is_closed_counts": closed_counts,
        "ohlcv_violations": violations,
        "zero_volume_bars": int((frame["volume"] == 0).sum()),
        "volume_p99": float(frame["volume"].quantile(0.99)),
        "volume_max": float(frame["volume"].max()),
    }
    if len(missing):
        raise RuntimeError(f"HYPE 5m data has {len(missing)} missing bars, first={missing[0]}")
    if any(violations.values()):
        raise RuntimeError(f"HYPE 5m data has hard OHLCV violations: {violations}")
    if sum(nulls.values()):
        raise RuntimeError(f"HYPE 5m data has nulls in required columns: {nulls}")
    if set(frame["is_closed"].dropna().unique()) != {True}:
        raise RuntimeError("HYPE 5m data contains non-closed bars")
    return frame, quality


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
    open_ = result["open"]
    volume = result["volume"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    for span in (5, 8, 9, 12, 21, 34, 55, 96, 144, 192, 288, 384):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    for window in (7, 14, 28, 96):
        result[f"atr{window}"] = tr.rolling(window, min_periods=window).mean()
    result["atr_pct_bps"] = result["atr14"] / close.replace(0.0, np.nan) * 10000.0
    result["atr_ratio_14_96"] = result["atr14"] / result["atr96"].replace(0.0, np.nan)

    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    for window in (7, 14, 28):
        avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        result[f"rsi{window}"] = 100 - 100 / (1 + rs)

    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    result["macd_hist"] = macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()
    result["macd_hist_delta"] = result["macd_hist"].diff()

    mid = close.rolling(20, min_periods=20).mean()
    std = close.rolling(20, min_periods=20).std(ddof=0)
    result["bb_z20"] = (close - mid) / std.replace(0.0, np.nan)
    result["bb_pos20"] = (close - (mid - 2 * std)) / (4 * std).replace(0.0, np.nan)
    result["bb_width20"] = 4 * std / mid.replace(0.0, np.nan)
    result["bb_width_z192"] = rolling_zscore(result["bb_width20"], 192)

    typical = (high + low + close) / 3.0
    roll_vwap_denom = volume.rolling(96, min_periods=96).sum().replace(0.0, np.nan)
    result["vwap96"] = (typical * volume).rolling(96, min_periods=96).sum() / roll_vwap_denom
    result["vwap96_dev_bps"] = (close / result["vwap96"].replace(0.0, np.nan) - 1.0) * 10000.0
    day_key = result["ts"].dt.strftime("%Y-%m-%d")
    day_pv = (typical * volume).groupby(day_key).cumsum()
    day_vol = volume.groupby(day_key).cumsum().replace(0.0, np.nan)
    result["day_vwap"] = day_pv / day_vol
    result["day_vwap_dev_bps"] = (close / result["day_vwap"].replace(0.0, np.nan) - 1.0) * 10000.0

    high14 = high.rolling(14, min_periods=14).max()
    low14 = low.rolling(14, min_periods=14).min()
    tr14 = (high - low).rolling(14, min_periods=14).sum()
    result["chop14"] = 100 * np.log10(tr14 / (high14 - low14).replace(0.0, np.nan)) / np.log10(14)
    result["rvol96"] = volume / volume.rolling(96, min_periods=96).mean().replace(0.0, np.nan)

    body = close - open_
    candle_range = (high - low).replace(0.0, np.nan)
    result["body_dir"] = np.sign(body).fillna(0.0)
    result["body_pct_range"] = body.abs() / candle_range
    result["close_pos"] = (close - low) / candle_range
    result["upper_wick_atr"] = (high - pd.concat([open_, close], axis=1).max(axis=1)) / result["atr14"].replace(0.0, np.nan)
    result["lower_wick_atr"] = (pd.concat([open_, close], axis=1).min(axis=1) - low) / result["atr14"].replace(0.0, np.nan)

    for window in (1, 3, 6, 12, 24, 48, 96, 192):
        result[f"ret{window}_bps"] = close.pct_change(window) * 10000.0
    for window in (12, 24, 48, 96):
        result[f"donchian_high{window}"] = high.shift(1).rolling(window, min_periods=window).max()
        result[f"donchian_low{window}"] = low.shift(1).rolling(window, min_periods=window).min()

    return add_adx(result)


def side_masks(frame: pd.DataFrame, cfg: ScalpConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    ema_htf = frame[f"ema{cfg.ema_htf}"].to_numpy("float64")
    trend_dir = np.sign(ema_fast - ema_slow).astype("float64")
    htf_dir = np.sign(close - ema_htf).astype("float64")
    valid = np.isfinite(ema_fast) & np.isfinite(ema_slow) & np.isfinite(ema_htf)
    long_allowed = valid & (cfg.side_mode != "short")
    short_allowed = valid & (cfg.side_mode != "long")
    if cfg.require_trend:
        long_allowed &= trend_dir > 0
        short_allowed &= trend_dir < 0
    if cfg.require_htf:
        long_allowed &= htf_dir > 0
        short_allowed &= htf_dir < 0
    direction = np.zeros(len(frame), dtype=np.int8)
    direction[long_allowed] = 1
    direction[short_allowed] = -1
    return long_allowed, short_allowed, direction


def build_signal(frame: pd.DataFrame, cfg: ScalpConfig) -> np.ndarray:
    close = frame["close"].to_numpy("float64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    don_high = frame[f"donchian_high{cfg.donchian}"].to_numpy("float64")
    don_low = frame[f"donchian_low{cfg.donchian}"].to_numpy("float64")
    rsi = frame[f"rsi{cfg.rsi_window}"].to_numpy("float64")
    rsi_prev = np.r_[np.nan, rsi[:-1]]
    macd = frame["macd_hist"].to_numpy("float64")
    macd_delta = frame["macd_hist_delta"].to_numpy("float64")
    bb_z = frame["bb_z20"].to_numpy("float64")
    vwap_dev = frame["vwap96_dev_bps"].to_numpy("float64")
    day_vwap_dev = frame["day_vwap_dev_bps"].to_numpy("float64")
    close_pos = frame["close_pos"].to_numpy("float64")
    lower_wick = frame["lower_wick_atr"].to_numpy("float64")
    upper_wick = frame["upper_wick_atr"].to_numpy("float64")
    ret3 = frame["ret3_bps"].to_numpy("float64")
    ret12 = frame["ret12_bps"].to_numpy("float64")
    ret48 = frame["ret48_bps"].to_numpy("float64")
    long_allowed, short_allowed, _ = side_masks(frame, cfg)

    if cfg.entry_style == "trend_rsi_snapback":
        long_entry = (rsi_prev <= cfg.rsi_low) & (rsi > rsi_prev + 0.5) & (close_pos >= cfg.close_pos)
        short_entry = (rsi_prev >= cfg.rsi_high) & (rsi < rsi_prev - 0.5) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "ema_reclaim":
        pull = cfg.pullback_bps / 10000.0
        long_entry = (low <= ema_fast * (1.0 + pull)) & (close > ema_fast) & (close_pos >= cfg.close_pos)
        short_entry = (high >= ema_fast * (1.0 - pull)) & (close < ema_fast) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "bb_revert":
        long_entry = (bb_z <= -cfg.bb_z) & (close_pos >= cfg.close_pos)
        short_entry = (bb_z >= cfg.bb_z) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "vwap_revert":
        long_entry = ((vwap_dev <= -cfg.vwap_dev_bps) | (day_vwap_dev <= -cfg.vwap_dev_bps)) & (close_pos >= cfg.close_pos)
        short_entry = ((vwap_dev >= cfg.vwap_dev_bps) | (day_vwap_dev >= cfg.vwap_dev_bps)) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "micro_breakout":
        breakout = cfg.breakout_bps / 10000.0
        long_entry = (close >= don_high * (1.0 - breakout)) & (close_pos >= cfg.close_pos)
        short_entry = (close <= don_low * (1.0 + breakout)) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "macd_flip":
        macd_prev = np.r_[np.nan, macd[:-1]]
        long_entry = (macd_prev <= 0) & (macd > 0) & (close_pos >= cfg.close_pos)
        short_entry = (macd_prev >= 0) & (macd < 0) & (close_pos <= 1.0 - cfg.close_pos)
    elif cfg.entry_style == "wick_reject":
        long_entry = (lower_wick >= cfg.wick_atr) & (close_pos >= cfg.close_pos) & (ret3 >= -cfg.max_counter_roc_bps)
        short_entry = (upper_wick >= cfg.wick_atr) & (close_pos <= 1.0 - cfg.close_pos) & (ret3 <= cfg.max_counter_roc_bps)
    elif cfg.entry_style == "momentum_pause":
        long_entry = (ret48 >= cfg.min_dir_roc_bps) & (ret12 >= -cfg.max_counter_roc_bps) & (ret3 > 0) & (close_pos >= cfg.close_pos)
        short_entry = (ret48 <= -cfg.min_dir_roc_bps) & (ret12 <= cfg.max_counter_roc_bps) & (ret3 < 0) & (close_pos <= 1.0 - cfg.close_pos)
    else:
        raise ValueError(f"unknown entry_style={cfg.entry_style}")

    dist_bps = np.abs(close / ema_fast - 1.0) * 10000.0
    common = (
        (frame["adx14"].to_numpy("float64") >= cfg.min_adx)
        & (frame["chop14"].to_numpy("float64") <= cfg.max_chop)
        & (frame["rvol96"].to_numpy("float64") >= cfg.min_rvol)
        & (frame["atr_pct_bps"].to_numpy("float64") >= cfg.min_atr_pct_bps)
        & (frame["atr_pct_bps"].to_numpy("float64") <= cfg.max_atr_pct_bps)
        & (dist_bps <= cfg.max_dist_ema_bps)
    )
    if cfg.require_macd_turn:
        long_entry &= (macd_delta > 0) | (macd > 0)
        short_entry &= (macd_delta < 0) | (macd < 0)
    if cfg.require_body_dir:
        long_entry &= close > open_
        short_entry &= close < open_

    signal = np.zeros(len(frame), dtype=np.int8)
    long_mask = np.nan_to_num(common & long_allowed & long_entry, nan=False).astype(bool)
    short_mask = np.nan_to_num(common & short_allowed & short_entry, nan=False).astype(bool)
    signal[long_mask] = 1
    signal[short_mask] = -1
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return bool(open_price <= stop_price if side > 0 else open_price >= stop_price)


def touched_stop(high_price: float, low_price: float, stop_price: float, side: int) -> bool:
    return bool(low_price <= stop_price if side > 0 else high_price >= stop_price)


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return bool(open_price >= target_price if side > 0 else open_price <= target_price)


def touched_target(high_price: float, low_price: float, target_price: float, side: int) -> bool:
    return bool(high_price >= target_price if side > 0 else low_price <= target_price)


def apply_exit_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * EXIT_SLIPPAGE_RATE))


def simulate_trades(frame: pd.DataFrame, signal: np.ndarray, cfg: ScalpConfig) -> tuple[list[Trade], dict[str, int]]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    trades: list[Trade] = []
    reason_counts: dict[str, int] = {}
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or side == 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
        target_price = entry_price * (1.0 + side * cfg.tp_bps / 10000.0)
        stop_price = entry_price * (1.0 - side * cfg.sl_bps / 10000.0)
        last_intrabar_i = min(n - 1, entry_i + cfg.max_hold_bars - 1)
        timeout_i = min(n - 1, entry_i + cfg.max_hold_bars)
        exit_i = timeout_i
        reason = "time_open"
        raw_exit_price = float(open_[timeout_i] if timeout_i > last_intrabar_i else close[timeout_i])

        for bar_i in range(entry_i, last_intrabar_i + 1):
            # Conservative executable semantics: if a bar can hit both, assume the stop fills first.
            if crossed_stop(float(open_[bar_i]), stop_price, side):
                exit_i = bar_i
                reason = "gap_stop_market"
                raw_exit_price = float(open_[bar_i])
                break
            if touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side):
                exit_i = bar_i
                reason = "stop_market"
                raw_exit_price = float(stop_price)
                break
            if crossed_target(float(open_[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "gap_target_market"
                raw_exit_price = float(open_[bar_i])
                break
            if touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side):
                exit_i = bar_i
                reason = "target_limit"
                raw_exit_price = float(target_price)
                break

        exit_price = apply_exit_cost(raw_exit_price, side)
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        path_end = max(entry_i, exit_i)
        path_high = high[entry_i : path_end + 1]
        path_low = low[entry_i : path_end + 1]
        if side > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
        trades.append(
            Trade(
                config=cfg.name,
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
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, reason_counts


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "train_2025_05_30_to_2026_03_01", "start": start, "end": min(TRAIN_END, end)},
        {"name": "val_2026_03_01_to_2026_06_01", "start": max(TRAIN_END, start), "end": min(VAL_END, end)},
        {"name": "fwd_2026_06_01_to_latest", "start": max(VAL_END, start), "end": end},
        {"name": "recent_90d", "start": max(start, end - pd.Timedelta(days=90)), "end": end},
        {"name": "recent_30d", "start": max(start, end - pd.Timedelta(days=30)), "end": end},
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    current = start.floor("D").replace(day=1)
    rows: list[dict[str, Any]] = []
    while current < end:
        next_month = current + pd.offsets.MonthBegin(1)
        slice_start = max(start, current)
        slice_end = min(end, next_month)
        if slice_start < slice_end:
            rows.append({"name": slice_start.strftime("%Y_%m"), "start": slice_start, "end": slice_end})
        current = next_month
    return rows


def metric_from_trades(trades: list[Trade], *, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, float | int]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    empty = {
        "trades": 0,
        "trades_per_day": 0.0,
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
        "target_rate": 0.0,
        "stop_rate": 0.0,
        "time_rate": 0.0,
        "long_trades": 0,
        "short_trades": 0,
        "avg_bars_held": 0.0,
    }
    if not selected:
        return empty
    raw_rets = np.array([trade.net_ret_1x for trade in selected], dtype=float)
    maes = np.array([trade.mae_1x for trade in selected], dtype=float)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for ret, mae in zip(raw_rets, maes, strict=True):
        trough = equity * max(0.001, 1.0 + mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
    wins = raw_rets[raw_rets > 0]
    losses = raw_rets[raw_rets <= 0]
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss_abs = float(abs(losses.mean())) if len(losses) else 0.0
    payoff_ratio = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    annualized = float(equity ** (365.25 / days)) if equity > 0 else 0.0
    reasons = pd.Series([trade.reason for trade in selected])
    sides = np.array([trade.side for trade in selected], dtype=int)
    bars = np.array([trade.bars_held for trade in selected], dtype=float)
    return {
        "trades": int(len(selected)),
        "trades_per_day": float(len(selected) / days),
        "equity_multiple": float(equity),
        "annualized_multiple": annualized,
        "total_return": float(equity - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float((raw_rets > 0).mean()),
        "profit_factor": profit_factor,
        "avg_trade": float(raw_rets.mean()),
        "avg_win": avg_win,
        "avg_loss_abs": avg_loss_abs,
        "payoff_ratio": payoff_ratio,
        "worst_trade": float(raw_rets.min()),
        "best_trade": float(raw_rets.max()),
        "target_rate": float(reasons.str.contains("target").mean()),
        "stop_rate": float(reasons.str.contains("stop").mean()),
        "time_rate": float(reasons.str.contains("time").mean()),
        "long_trades": int((sides > 0).sum()),
        "short_trades": int((sides < 0).sum()),
        "avg_bars_held": float(bars.mean()),
    }


def frequency_fit(trades_per_day: float) -> float:
    center = (TARGET_TRADES_PER_DAY_MIN + TARGET_TRADES_PER_DAY_MAX) / 2.0
    width = (TARGET_TRADES_PER_DAY_MAX - TARGET_TRADES_PER_DAY_MIN) / 2.0
    return float(math.exp(-((trades_per_day - center) / max(width, 0.1)) ** 2))


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    full_tpd = float(row["full_trades_per_day"])
    train_pf = float(row["train_2025_05_30_to_2026_03_01_profit_factor"])
    val_pf = float(row["val_2026_03_01_to_2026_06_01_profit_factor"])
    fwd_pf = float(row["fwd_2026_06_01_to_latest_profit_factor"])
    full_ann = float(row["full_annualized_multiple"])
    full_win = float(row["full_win_rate"])
    full_dd = float(row["full_max_dd"])
    freq_ok = TARGET_TRADES_PER_DAY_MIN <= full_tpd <= TARGET_TRADES_PER_DAY_MAX
    train_ok = train_pf >= TARGET_PROFIT_FACTOR and float(row["train_2025_05_30_to_2026_03_01_annualized_multiple"]) >= 1.0
    val_ok = val_pf >= 1.0 and float(row["val_2026_03_01_to_2026_06_01_total_return"]) >= -0.02
    fwd_ok = fwd_pf >= 1.0 and float(row["fwd_2026_06_01_to_latest_total_return"]) >= -0.02
    dd_ok = full_dd >= TARGET_MAX_DD
    win_ok = full_win >= TARGET_WIN_RATE
    pf_ok = float(row["full_profit_factor"]) >= TARGET_PROFIT_FACTOR
    row["frequency_pass"] = bool(freq_ok)
    row["hard_pass"] = bool(freq_ok and dd_ok and win_ok and pf_ok and full_ann > 1.0)
    row["audit_pass"] = bool(row["hard_pass"] and train_ok and val_ok and fwd_ok and float(row["recent_30d_total_return"]) >= -0.02)
    row["frequency_fit"] = frequency_fit(full_tpd)
    if full_tpd < TARGET_TRADES_PER_DAY_MIN:
        frequency_gap = (TARGET_TRADES_PER_DAY_MIN - full_tpd) / TARGET_TRADES_PER_DAY_MIN
    elif full_tpd > TARGET_TRADES_PER_DAY_MAX:
        frequency_gap = (full_tpd - TARGET_TRADES_PER_DAY_MAX) / TARGET_TRADES_PER_DAY_MAX
    else:
        frequency_gap = 0.0
    row["frequency_gap"] = float(frequency_gap)
    val_trade_penalty = 35.0 if int(row["val_2026_03_01_to_2026_06_01_trades"]) < 20 else 0.0
    fwd_trade_penalty = 35.0 if int(row["fwd_2026_06_01_to_latest_trades"]) < 5 else 0.0
    row["score"] = float(
        min(50.0, math.log(max(full_ann, 1e-9)) * 14.0)
        + 80.0 * full_win
        + 35.0 * min(float(row["full_profit_factor"]), 3.0)
        + 120.0 * row["frequency_fit"]
        + 35.0 * max(full_dd, -1.0)
        + 10.0 * min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
        + 10.0 * min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
        - 170.0 * frequency_gap
        - val_trade_penalty
        - fwd_trade_penalty
    )
    row["train_rank_score"] = float(
        min(50.0, math.log(max(float(row["train_2025_05_30_to_2026_03_01_annualized_multiple"]), 1e-9)) * 14.0)
        + 80.0 * float(row["train_2025_05_30_to_2026_03_01_win_rate"])
        + 35.0 * min(train_pf if np.isfinite(train_pf) else 3.0, 3.0)
        + 35.0 * frequency_fit(float(row["train_2025_05_30_to_2026_03_01_trades_per_day"]))
        + 35.0 * max(float(row["train_2025_05_30_to_2026_03_01_max_dd"]), -1.0)
    )
    return row


def row_for_config(frame: pd.DataFrame, cfg: ScalpConfig, slices: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade]]:
    signal = build_signal(frame, cfg)
    trades, reason_counts = simulate_trades(frame, signal, cfg)
    row: dict[str, Any] = {
        "name": cfg.name,
        "signals": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
        **{f"reason_{key}": value for key, value in reason_counts.items()},
    }
    slice_rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_from_trades(trades, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value
        slice_rows.append({"name": cfg.name, "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
    return score_row(row), slice_rows, trades


def random_config(rng: random.Random, idx: int) -> ScalpConfig:
    ema_fast, ema_slow, ema_htf = rng.choice(
        [
            (5, 21, 96),
            (8, 34, 144),
            (9, 55, 192),
            (12, 96, 288),
            (21, 96, 384),
            (34, 144, 384),
        ]
    )
    tp_bps = rng.choice([18.0, 22.0, 25.0, 30.0, 35.0, 40.0, 50.0, 60.0, 75.0, 90.0, 120.0])
    sl_bps = rng.choice([22.0, 30.0, 40.0, 55.0, 75.0, 100.0, 130.0, 160.0, 220.0, 300.0])
    if rng.random() < 0.58 and sl_bps < tp_bps:
        sl_bps = rng.choice([tp_bps * 1.25, tp_bps * 1.75, tp_bps * 2.5])
    close_pos = rng.choice([0.52, 0.58, 0.64, 0.70, 0.76, 0.82])
    return ScalpConfig(
        name=f"HYPE_5M_MS_R{idx:05d}",
        side_mode=rng.choice(["both", "both", "long", "short"]),
        entry_style=rng.choice(
            [
                "trend_rsi_snapback",
                "ema_reclaim",
                "bb_revert",
                "vwap_revert",
                "micro_breakout",
                "macd_flip",
                "wick_reject",
                "momentum_pause",
            ]
        ),
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        ema_htf=ema_htf,
        donchian=rng.choice([12, 24, 48, 96]),
        rsi_window=rng.choice([7, 14, 28]),
        rsi_low=rng.choice([28.0, 32.0, 36.0, 40.0, 44.0, 48.0]),
        rsi_high=rng.choice([52.0, 56.0, 60.0, 64.0, 68.0, 72.0]),
        bb_z=rng.choice([0.75, 1.0, 1.25, 1.5, 1.75, 2.0]),
        vwap_dev_bps=rng.choice([20.0, 35.0, 50.0, 75.0, 100.0, 140.0, 200.0]),
        pullback_bps=rng.choice([0.0, 10.0, 20.0, 35.0, 50.0, 75.0, 100.0]),
        breakout_bps=rng.choice([0.0, 5.0, 10.0, 20.0, 35.0]),
        min_dir_roc_bps=rng.choice([0.0, 20.0, 40.0, 70.0, 100.0, 150.0, 220.0]),
        max_counter_roc_bps=rng.choice([15.0, 30.0, 50.0, 75.0, 120.0, 180.0, 260.0]),
        min_adx=rng.choice([0.0, 10.0, 14.0, 18.0, 22.0, 28.0]),
        max_chop=rng.choice([45.0, 52.0, 60.0, 68.0, 80.0, 100.0]),
        min_rvol=rng.choice([0.0, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]),
        min_atr_pct_bps=rng.choice([0.0, 12.0, 18.0, 25.0, 35.0]),
        max_atr_pct_bps=rng.choice([70.0, 90.0, 120.0, 160.0, 220.0, 350.0, 9999.0]),
        max_dist_ema_bps=rng.choice([35.0, 60.0, 90.0, 130.0, 180.0, 260.0, 400.0, 800.0]),
        wick_atr=rng.choice([0.10, 0.18, 0.25, 0.35, 0.50, 0.75, 1.0]),
        close_pos=close_pos,
        require_trend=rng.choice([False, True, True]),
        require_htf=rng.choice([False, False, True]),
        require_macd_turn=rng.choice([False, False, True]),
        require_body_dir=rng.choice([False, True, True]),
        tp_bps=float(tp_bps),
        sl_bps=float(sl_bps),
        max_hold_bars=rng.choice([2, 3, 4, 6, 9, 12, 18, 24, 36]),
        cooldown_bars=rng.choice([0, 1, 2, 3, 6, 9, 12, 18, 24, 36, 48]),
    )


def curated_configs() -> list[ScalpConfig]:
    configs: list[ScalpConfig] = []
    idx = 0
    for side_mode in ("both", "long", "short"):
        for entry_style in (
            "trend_rsi_snapback",
            "ema_reclaim",
            "bb_revert",
            "vwap_revert",
            "micro_breakout",
            "macd_flip",
            "wick_reject",
            "momentum_pause",
        ):
            for ema_fast, ema_slow, ema_htf in ((5, 21, 96), (8, 34, 144), (9, 55, 192), (21, 96, 384)):
                for tp_bps, sl_bps, hold, cooldown in (
                    (22.0, 55.0, 4, 1),
                    (30.0, 75.0, 6, 2),
                    (40.0, 100.0, 9, 3),
                    (50.0, 130.0, 12, 6),
                    (75.0, 160.0, 18, 9),
                    (90.0, 220.0, 24, 12),
                ):
                    idx += 1
                    configs.append(
                        ScalpConfig(
                            name=f"HYPE_5M_MS_C{idx:05d}",
                            side_mode=side_mode,
                            entry_style=entry_style,
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            ema_htf=ema_htf,
                            donchian=24,
                            rsi_window=14,
                            rsi_low=40.0,
                            rsi_high=60.0,
                            bb_z=1.25,
                            vwap_dev_bps=75.0,
                            pullback_bps=35.0,
                            breakout_bps=10.0,
                            min_dir_roc_bps=40.0,
                            max_counter_roc_bps=75.0,
                            min_adx=10.0,
                            max_chop=68.0,
                            min_rvol=0.5,
                            min_atr_pct_bps=12.0,
                            max_atr_pct_bps=220.0,
                            max_dist_ema_bps=180.0,
                            wick_atr=0.25,
                            close_pos=0.64,
                            require_trend=True,
                            require_htf=False,
                            require_macd_turn=False,
                            require_body_dir=True,
                            tp_bps=tp_bps,
                            sl_bps=sl_bps,
                            max_hold_bars=hold,
                            cooldown_bars=cooldown,
                        )
                    )
    return configs


def build_configs(max_random: int, seed: int) -> list[ScalpConfig]:
    rng = random.Random(seed)
    configs = curated_configs()
    for idx in range(max_random):
        configs.append(random_config(rng, idx))
    return configs


def monthly_rows(frame: pd.DataFrame, cfg_by_name: dict[str, ScalpConfig], top_names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    months = month_slices(frame)
    for name in top_names:
        cfg = cfg_by_name[name]
        trades, _ = simulate_trades(frame, build_signal(frame, cfg), cfg)
        for item in months:
            rows.append(
                {
                    "name": name,
                    "month": item["name"],
                    "month_start": item["start"],
                    "month_end": item["end"],
                    **metric_from_trades(trades, start=item["start"], end=item["end"]),
                }
            )
    return rows


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([{**asdict(trade), "side_label": "long" if trade.side > 0 else "short"} for trade in trades])


def markdown_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    output = [
        "| name | style | side | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['name']}` | `{item['cfg_entry_style']}` | `{item['cfg_side_mode']}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{pct(float(item['full_win_rate']))}` | "
            f"`{num(float(item['full_profit_factor']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | "
            f"`{num(float(item['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{num(float(item['fwd_2026_06_01_to_latest_profit_factor']))}` |"
        )
    return output


def render_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any], args: argparse.Namespace) -> str:
    hard = summary.loc[summary["hard_pass"].eq(True)].sort_values("score", ascending=False)
    audit = summary.loc[summary["audit_pass"].eq(True)].sort_values("score", ascending=False)
    freq = summary.loc[summary["frequency_pass"].eq(True)].sort_values("score", ascending=False)
    if not audit.empty:
        nearest = audit.sort_values("score", ascending=False).head(20)
    elif not hard.empty:
        nearest = hard.sort_values("score", ascending=False).head(20)
    elif not freq.empty:
        nearest = freq.sort_values("score", ascending=False).head(20)
    else:
        nearest = summary.sort_values("score", ascending=False).head(20)
    high_win_freq = freq.sort_values(["full_win_rate", "full_profit_factor", "score"], ascending=[False, False, False]).head(12)
    ann_by_min_trades = []
    for min_tpd in (1.0, 2.0, 3.0, 4.0, 5.0):
        subset = summary.loc[summary["full_trades_per_day"] >= min_tpd]
        best_ann = float(subset["full_annualized_multiple"].max()) if not subset.empty else 0.0
        ann_by_min_trades.append((min_tpd, len(subset), best_ann))

    lines = [
        "# HYPE 5m Micro-Scalp executable search 2026-06-26",
        "",
        "Family id: `HYPE-5M-Micro-Scalp`",
        "",
        "目标：在 Binance HYPEUSDT 永续 `5m` K 上搜索每天约 `3-5` 笔、回撤小、单笔微利、高胜率、累计年化尽量高的可实盘微利 scalp。",
        "",
        "## 数据质量",
        "",
        f"- Normalized OHLCV: `{quality['normalized_file_count']}` 个日分区，`{quality['rows']}` 根 K。",
        f"- 时间范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 连续性：expected `{quality['expected_bars']}`，missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`。",
        f"- `is_closed`：`{quality['is_closed_counts']}`。",
        f"- `source`：`{quality['source_counts']}`。",
        f"- OHLC/VWAP/volume 硬违规：`{quality['ohlcv_violations']}`。",
        f"- Raw OHLCV evidence file count：`{quality['raw_ohlcv_file_count']}`。",
        "",
        "## 执行模型",
        "",
        "- 信号只使用已收盘 K 线信息；下一根 K 的 open 入场。",
        "- 入场后立刻有固定 TP/SL bracket；保护止损从第一根持仓 K 开始生效。",
        "- 同一根 K 同时可能触及 TP/SL 时，保守按止损先成交。",
        "- stop/target 被 open 穿越时按 open 市价成交，不按旧 stop/target 价成交。",
        "- 超时退出使用下一根 open，不使用不可实盘保证的 bar close。",
        f"- 成本：fee `{FEE_RATE_PER_FILL * 10000:.4f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_RATE * 10000:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_RATE * 10000:.2f} bps`。",
        "",
        "## 搜索规模",
        "",
        f"- curated + random configs: `{len(summary)}`。",
        f"- random seed: `{args.seed}`。",
        f"- 指标族：EMA、RSI、MACD、Bollinger z-score、rolling/day VWAP deviation、Donchian、ATR、ADX、Choppiness、relative volume、wick/close-position candle structure。",
        "",
        "## 用户目标命中",
        "",
        f"- frequency pass (`3-5` trades/day): `{int(summary['frequency_pass'].sum())}`。",
        f"- hard pass (`3-5` trades/day, win >= `{TARGET_WIN_RATE:.0%}`, PF >= `{TARGET_PROFIT_FACTOR}`, maxDD >= `{TARGET_MAX_DD:.0%}`, ann > 1x): `{len(hard)}`。",
        f"- audit pass (hard pass plus train/val/fwd/recent checks): `{len(audit)}`。",
        "",
    ]
    if audit.empty:
        lines.append("没有配置通过完整 audit gate。")
    else:
        lines.append("通过完整 audit gate 的配置：")
        lines.extend(markdown_table(audit))
    lines.extend(["", "## 最接近用户目标的配置", "", *markdown_table(nearest), ""])
    if not high_win_freq.empty:
        lines.extend(["## 频率达标内胜率最高的配置", "", *markdown_table(high_win_freq), ""])
    lines.extend(["## 年化上限审计", "", "| 最低 trades/day | 配置数 | 最高全样本年化 |", "| ---: | ---: | ---: |"])
    for min_tpd, count, best_ann in ann_by_min_trades:
        lines.append(f"| `{min_tpd:.1f}` | `{count}` | `{mult(best_ann)}` |")
    lines.extend(["", "## 月度风险提示", ""])
    if not monthly.empty and not nearest.empty:
        top_name = str(nearest.iloc[0]["name"])
        top_monthly = monthly.loc[monthly["name"].eq(top_name)].copy()
        negative_months = int((top_monthly["total_return"] < 0).sum()) if not top_monthly.empty else 0
        worst_month = top_monthly.sort_values("total_return").head(1).to_dict(orient="records") if not top_monthly.empty else []
        lines.append(f"- top score `{top_name}` 的负收益月份数：`{negative_months}`。")
        if worst_month:
            item = worst_month[0]
            lines.append(
                f"- 最差月份 `{item['month']}`：return `{pct(float(item['total_return']))}`，PF `{num(float(item['profit_factor']))}`，trades `{int(item['trades'])}`。"
            )
    lines.extend(
        [
            "",
            "## 结论",
            "",
        ]
    )
    if audit.empty:
        lines.append(
            "本轮不能提升 live/paper-live 候选。即使搜索空间专门偏向微利高胜率和每天 `3-5` 笔频率，最接近配置仍未同时通过频率、胜率、回撤、PF、VAL/FWD 和近期稳定性约束。"
        )
    else:
        lines.append(
            "本轮出现初步 audit pass，但仍不能直接上真实资金；下一步必须做逐笔订单路径审计、参数邻域、walk-forward 固化和 paper audit runner。"
        )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-micro-scalp/scripts/research_hype_5m_micro_scalp_search.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 切片 CSV：`{SLICES_PATH}`",
            f"- 月度 CSV：`{MONTHLY_PATH}`",
            f"- Top trades CSV：`{TOP_TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    frame_raw, quality = load_hype_5m()
    frame = add_features(frame_raw)
    slices = validation_slices(frame)
    configs = build_configs(args.max_random_configs, args.seed)
    cfg_by_name = {cfg.name: cfg for cfg in configs}

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    best_trades: list[Trade] = []
    best_name = ""
    best_score = -float("inf")
    best_row: dict[str, Any] | None = None

    for idx, cfg in enumerate(configs, start=1):
        row, per_slices, trades = row_for_config(frame, cfg, slices)
        summary_rows.append(row)
        slice_rows.extend(per_slices)
        if float(row["score"]) > best_score:
            best_score = float(row["score"])
            best_name = cfg.name
            best_trades = trades
            best_row = row
        if args.progress_every and idx % args.progress_every == 0:
            progress_row = best_row if best_row is not None else row
            print(
                "progress="
                f"{idx}/{len(configs)} best={best_name} score={best_score:.2f} "
                f"tpd={progress_row['full_trades_per_day']:.2f} ann={progress_row['full_annualized_multiple']:.2f} "
                f"win={progress_row['full_win_rate']:.3f} pf={progress_row['full_profit_factor']:.3f} "
                f"dd={progress_row['full_max_dd']:.3f}"
            )

    summary = pd.DataFrame(summary_rows).sort_values("score", ascending=False)
    slices_df = pd.DataFrame(slice_rows)
    top_names = summary.head(args.top_keep)["name"].tolist()
    monthly = pd.DataFrame(monthly_rows(frame, cfg_by_name, top_names))
    best_cfg_name = str(summary.iloc[0]["name"]) if not summary.empty else best_name
    if best_cfg_name != best_name and best_cfg_name in cfg_by_name:
        best_trades, _ = simulate_trades(frame, build_signal(frame, cfg_by_name[best_cfg_name]), cfg_by_name[best_cfg_name])
    top_trades = trades_to_frame(best_trades)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices_df.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    top_trades.to_csv(TOP_TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality, args), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-Micro-Scalp",
                "script": "research_hype_5m_micro_scalp_search.py",
                "seed": args.seed,
                "max_random_configs": args.max_random_configs,
                "data_quality": quality,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                },
                "targets": {
                    "trades_per_day_min": TARGET_TRADES_PER_DAY_MIN,
                    "trades_per_day_max": TARGET_TRADES_PER_DAY_MAX,
                    "win_rate": TARGET_WIN_RATE,
                    "max_dd": TARGET_MAX_DD,
                    "profit_factor": TARGET_PROFIT_FACTOR,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "top_trades": str(TOP_TRADES_PATH),
                },
                "frequency_pass_count": int(summary["frequency_pass"].sum()),
                "hard_pass_count": int(summary["hard_pass"].sum()),
                "audit_pass_count": int(summary["audit_pass"].sum()),
                "top": summary.head(50).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"top_trades={TOP_TRADES_PATH}")
    print(summary.head(20).to_string(index=False))
    print(
        f"frequency_pass={int(summary['frequency_pass'].sum())} "
        f"hard_pass={int(summary['hard_pass'].sum())} "
        f"audit_pass={int(summary['audit_pass'].sum())}"
    )


if __name__ == "__main__":
    main()
