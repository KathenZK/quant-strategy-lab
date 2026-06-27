from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
RAW_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=5m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_ROOT = Path("research/hype/5m-event-quality-scoring")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

RUN_DATE = "2026-06-27"
REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_{RUN_DATE}.json"
EVENTS_PATH = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_events_{RUN_DATE}.parquet"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_summary_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_monthly_{RUN_DATE}.csv"
SOURCE_CSV = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_source_quality_{RUN_DATE}.csv"
TOP_TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_top_trades_{RUN_DATE}.csv"
TOP_EVENTS_CSV = ARTIFACT_ROOT / f"hype_5m_event_quality_v0_top_selected_events_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-event-quality-v0-{RUN_DATE}.md"

# Observed Binance live cost model copied from HYPE-5M-Micro-Scalp research:
# fee: 3.0578 / 7374.2110 = 4.1466 bps per fill.
# entry slippage: 10.73 bps against entry direction.
# exit slippage: -2.64 bps, the observed exit-side average.
FEE_RATE_PER_FILL = 3.0578 / 7374.2110
ENTRY_SLIPPAGE_RATE = 10.73 / 10000.0
EXIT_SLIPPAGE_RATE = -2.64 / 10000.0

TRAIN_START_FLOOR = pd.Timestamp("2025-09-01T00:00:00Z")
MIN_TRAIN_EVENTS = 700
BIN_COUNT = 7
SHRINK = 50.0
QUANTILES = (0.70, 0.80, 0.85, 0.90, 0.95)


@dataclass(frozen=True, slots=True)
class EventSpec:
    name: str
    style: str
    threshold: float
    fast: int = 21
    slow: int = 55
    lookback: int = 24
    buffer_bps: float = 0.0
    close_pos_long: float = 0.55
    close_pos_short: float = 0.45
    require_trend: bool = False


@dataclass(frozen=True, slots=True)
class BracketSpec:
    name: str
    tp_bps: float
    sl_bps: float
    max_hold_bars: int
    cooldown_bars: int = 0


@dataclass(slots=True)
class Trade:
    candidate_id: str
    event_id: int
    source: str
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    score: float
    entry_price: float
    exit_price: float
    reason: str
    bars_held: int
    net_ret_1x: float
    mfe_1x: float
    mae_1x: float


EVENT_SPECS: tuple[EventSpec, ...] = (
    EventSpec("vwap_revert_12", "vwap_revert", 12.0, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("vwap_revert_20", "vwap_revert", 20.0, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("vwap_revert_30", "vwap_revert", 30.0, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("vwap_revert_50", "vwap_revert", 50.0, close_pos_long=0.54, close_pos_short=0.46),
    EventSpec("vwap_revert_75", "vwap_revert", 75.0, close_pos_long=0.54, close_pos_short=0.46),
    EventSpec("vwap_revert_100", "vwap_revert", 100.0, close_pos_long=0.56, close_pos_short=0.44),
    EventSpec("vwap_revert_140", "vwap_revert", 140.0, close_pos_long=0.58, close_pos_short=0.42),
    EventSpec("vwap_revert_200", "vwap_revert", 200.0, close_pos_long=0.60, close_pos_short=0.40),
    EventSpec("bb_revert_1p2", "bb_revert", 1.2, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("bb_revert_1p5", "bb_revert", 1.5, close_pos_long=0.54, close_pos_short=0.46),
    EventSpec("bb_revert_1p8", "bb_revert", 1.8, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("bb_revert_2p0", "bb_revert", 2.0, close_pos_long=0.56, close_pos_short=0.44),
    EventSpec("bb_revert_2p4", "bb_revert", 2.4, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("ema21_55_reclaim", "ema_reclaim", 0.0, fast=21, slow=55, require_trend=True),
    EventSpec("ema21_96_reclaim", "ema_reclaim", 0.0, fast=21, slow=96, require_trend=True),
    EventSpec("ema34_144_reclaim", "ema_reclaim", 0.0, fast=34, slow=144, require_trend=True),
    EventSpec("ema21_55_reclaim_buf5", "ema_reclaim", 0.0, fast=21, slow=55, buffer_bps=5.0, require_trend=True),
    EventSpec("wick_reject_0p6", "wick_reject", 0.6, close_pos_long=0.58, close_pos_short=0.42),
    EventSpec("wick_reject_1p0", "wick_reject", 1.0, close_pos_long=0.58, close_pos_short=0.42),
    EventSpec("breakout_24", "micro_breakout", 8.0, lookback=24, close_pos_long=0.62, close_pos_short=0.38),
    EventSpec("breakout_48", "micro_breakout", 8.0, lookback=48, close_pos_long=0.62, close_pos_short=0.38),
    EventSpec("macd_flip", "macd_flip", 0.0, close_pos_long=0.52, close_pos_short=0.48),
    EventSpec("momentum_pause_48", "momentum_pause", 45.0, lookback=48),
)

BRACKETS: tuple[BracketSpec, ...] = (
    BracketSpec("tp50_sl75_h12", 50.0, 75.0, 12),
    BracketSpec("tp75_sl100_h18", 75.0, 100.0, 18),
    BracketSpec("tp90_sl130_h24", 90.0, 130.0, 24),
    BracketSpec("tp120_sl160_h36", 120.0, 160.0, 36),
    BracketSpec("tp160_sl220_h48", 160.0, 220.0, 48),
    BracketSpec("tp220_sl300_h72", 220.0, 300.0, 72),
)

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "core": (
        "source_id",
        "style_id",
        "side",
        "hour",
        "ema21_55_spread_dir_bps",
        "ema21_96_spread_dir_bps",
        "dist_ema21_dir_bps",
        "vwap96_revert_bps",
        "day_vwap_revert_bps",
        "bb_revert_z",
        "rsi14_revert",
        "adx14",
        "plus_minus_di_dir",
        "atr_pct_bps",
        "rvol96",
        "ret12_dir_bps",
        "ret48_dir_bps",
        "close_pos_dir",
    ),
    "all": (
        "source_id",
        "style_id",
        "side",
        "hour",
        "day_of_week",
        "threshold",
        "ema21_55_spread_dir_bps",
        "ema21_96_spread_dir_bps",
        "ema55_144_spread_dir_bps",
        "ema21_slope3_dir_bps",
        "ema55_slope6_dir_bps",
        "dist_ema21_dir_bps",
        "abs_dist_ema21_bps",
        "vwap96_revert_bps",
        "day_vwap_revert_bps",
        "bb_revert_z",
        "bb_width20_bps",
        "bb_width_z192",
        "rsi7_revert",
        "rsi14_revert",
        "rsi28_revert",
        "adx14",
        "plus_minus_di_dir",
        "chop14",
        "atr_pct_bps",
        "atr_ratio_14_96",
        "range_atr",
        "abs_body_atr",
        "body_dir_bps",
        "close_pos_dir",
        "rejection_wick_atr",
        "extension_wick_atr",
        "rvol96",
        "quote_rvol96",
        "trade_count_rvol96",
        "ret1_dir_bps",
        "ret3_dir_bps",
        "ret6_dir_bps",
        "ret12_dir_bps",
        "ret24_dir_bps",
        "ret48_dir_bps",
        "ret96_dir_bps",
        "ret192_dir_bps",
    ),
}

CATEGORICAL_FEATURES = {"source_id", "style_id", "side", "hour", "day_of_week"}


def pct(value: float, digits: int = 2) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def bps(value: float, digits: int = 2) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(value):
        return "inf"
    return f"{value * 10000:.{digits}f} bps"


def num(value: float, digits: int = 3) -> str:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def read_ohlcv(root: Path) -> pd.DataFrame:
    files = sorted(root.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no HYPE 5m parquet files under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.sort_values("ts").reset_index(drop=True)


def validate_and_load() -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized = read_ohlcv(DATA_ROOT)
    raw = read_ohlcv(RAW_ROOT)
    normalized_dupes = int(normalized.duplicated("ts").sum())
    raw_dupes = int(raw.duplicated("ts").sum())
    normalized = normalized.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    raw = raw.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)

    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="5min")
    missing = expected.difference(normalized["ts"])
    required = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "is_closed",
        "source",
    ]
    nulls = {column: int(normalized[column].isna().sum()) for column in required}
    violations = {
        "high_lt_max_open_close": int(
            (normalized["high"] < normalized[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_min_open_close": int(
            (normalized["low"] > normalized[["open", "close"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            ((normalized[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
        "negative_volume": int((normalized["volume"] < 0).sum()),
        "negative_quote_volume": int((normalized["quote_volume"] < 0).sum()),
        "vwap_outside_hilo_nonzero_vol": int(
            (
                (normalized["volume"] > 0)
                & (
                    (normalized["vwap"] < normalized["low"] * 0.999999)
                    | (normalized["vwap"] > normalized["high"] * 1.000001)
                )
            ).sum()
        ),
    }
    if len(missing):
        raise RuntimeError(f"HYPE 5m normalized data has {len(missing)} missing bars")
    if sum(nulls.values()):
        raise RuntimeError(f"HYPE 5m normalized data has required-column nulls: {nulls}")
    if any(violations.values()):
        raise RuntimeError(f"HYPE 5m normalized data has OHLCV violations: {violations}")
    if set(normalized["is_closed"].dropna().unique()) != {True}:
        raise RuntimeError("HYPE 5m normalized data contains non-closed bars")

    same_ts_sequence = bool(
        len(raw) == len(normalized)
        and (raw["ts"].to_numpy(dtype="datetime64[ns]") == normalized["ts"].to_numpy(dtype="datetime64[ns]")).all()
    )
    raw_alignment: dict[str, Any] = {
        "raw_rows": int(len(raw)),
        "raw_duplicate_ts": raw_dupes,
        "normalized_rows": int(len(normalized)),
        "normalized_duplicate_ts": normalized_dupes,
        "same_ts_sequence": same_ts_sequence,
        "max_abs_diff": {},
    }
    if not raw_alignment["same_ts_sequence"]:
        raise RuntimeError("raw and normalized HYPE 5m data do not share the same timestamp sequence")
    for column in ("open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"):
        diff = (raw[column].astype("float64") - normalized[column].astype("float64")).abs()
        max_diff = float(diff.max())
        raw_alignment["max_abs_diff"][column] = max_diff
        tolerance = 1e-9 if column != "trade_count" else 0.0
        if max_diff > tolerance:
            raise RuntimeError(f"raw/normalized mismatch in {column}: max_abs_diff={max_diff}")

    quality = {
        "data_root": str(DATA_ROOT),
        "raw_root": str(RAW_ROOT),
        "symbol_file": SYMBOL_FILE,
        "rows": int(len(normalized)),
        "start_ts": str(normalized["ts"].iloc[0]),
        "end_ts": str(normalized["ts"].iloc[-1]),
        "expected_bars": int(len(expected)),
        "missing_bars": int(len(missing)),
        "nulls": nulls,
        "ohlcv_violations": violations,
        "source_counts": {
            str(key): int(value)
            for key, value in normalized["source"].value_counts(dropna=False).to_dict().items()
        },
        "is_closed_counts": {
            str(key): int(value)
            for key, value in normalized["is_closed"].value_counts(dropna=False).to_dict().items()
        },
        "zero_volume_bars": int((normalized["volume"] == 0).sum()),
        "raw_alignment": raw_alignment,
    }
    return normalized, quality


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
    tr = pd.concat(
        [(high - low), (high - close.shift(1)).abs(), (low - close.shift(1)).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = (
        100
        * pd.Series(plus_dm, index=frame.index)
        .ewm(alpha=1 / window, adjust=False, min_periods=window)
        .mean()
        / atr
    )
    minus_di = (
        100
        * pd.Series(minus_dm, index=frame.index)
        .ewm(alpha=1 / window, adjust=False, min_periods=window)
        .mean()
        / atr
    )
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
    quote_volume = result["quote_volume"]
    trade_count = result["trade_count"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)

    for span in (8, 12, 21, 34, 55, 96, 144, 192, 384):
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

    bb_mid = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std(ddof=0)
    result["bb_z20"] = (close - bb_mid) / bb_std.replace(0.0, np.nan)
    result["bb_width20_bps"] = 4 * bb_std / bb_mid.replace(0.0, np.nan) * 10000.0
    result["bb_width_z192"] = rolling_zscore(result["bb_width20_bps"], 192)

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
    tr14 = tr.rolling(14, min_periods=14).sum()
    result["chop14"] = 100 * np.log10(tr14 / (high14 - low14).replace(0.0, np.nan)) / np.log10(14)
    result["rvol96"] = volume / volume.rolling(96, min_periods=96).mean().replace(0.0, np.nan)
    result["quote_rvol96"] = (
        quote_volume / quote_volume.rolling(96, min_periods=96).mean().replace(0.0, np.nan)
    )
    result["trade_count_rvol96"] = (
        trade_count / trade_count.rolling(96, min_periods=96).mean().replace(0.0, np.nan)
    )

    body = close - open_
    candle_range = (high - low).replace(0.0, np.nan)
    result["body_dir_bps"] = (close / open_.replace(0.0, np.nan) - 1.0) * 10000.0
    result["abs_body_atr"] = body.abs() / result["atr14"].replace(0.0, np.nan)
    result["range_atr"] = (high - low) / result["atr14"].replace(0.0, np.nan)
    result["close_pos"] = (close - low) / candle_range
    candle_top = pd.concat([open_, close], axis=1).max(axis=1)
    candle_bottom = pd.concat([open_, close], axis=1).min(axis=1)
    result["upper_wick_atr"] = (high - candle_top) / result["atr14"].replace(0.0, np.nan)
    result["lower_wick_atr"] = (candle_bottom - low) / result["atr14"].replace(0.0, np.nan)

    for window in (1, 3, 6, 12, 24, 48, 96, 192):
        result[f"ret{window}_bps"] = close.pct_change(window) * 10000.0
    for window in (24, 48):
        result[f"donchian_high{window}"] = high.shift(1).rolling(window, min_periods=window).max()
        result[f"donchian_low{window}"] = low.shift(1).rolling(window, min_periods=window).min()

    return add_adx(result)


def compact_signals(long_entry: np.ndarray, short_entry: np.ndarray) -> np.ndarray:
    signal = np.zeros(len(long_entry), dtype=np.int8)
    signal[np.nan_to_num(long_entry, nan=False).astype(bool)] = 1
    signal[np.nan_to_num(short_entry, nan=False).astype(bool)] = -1
    same_as_previous = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[same_as_previous] = 0
    return signal


def build_signal_for_spec(frame: pd.DataFrame, spec: EventSpec) -> np.ndarray:
    close = frame["close"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    open_ = frame["open"].to_numpy("float64")
    close_pos = frame["close_pos"].to_numpy("float64")
    fast = frame[f"ema{spec.fast}"].to_numpy("float64")
    slow = frame[f"ema{spec.slow}"].to_numpy("float64")
    trend_long = fast > slow
    trend_short = fast < slow
    if not spec.require_trend:
        trend_long = np.isfinite(fast)
        trend_short = np.isfinite(fast)

    if spec.style == "vwap_revert":
        vwap_dev = frame["vwap96_dev_bps"].to_numpy("float64")
        day_vwap_dev = frame["day_vwap_dev_bps"].to_numpy("float64")
        long_entry = ((vwap_dev <= -spec.threshold) | (day_vwap_dev <= -spec.threshold)) & (
            close_pos >= spec.close_pos_long
        )
        short_entry = ((vwap_dev >= spec.threshold) | (day_vwap_dev >= spec.threshold)) & (
            close_pos <= spec.close_pos_short
        )
    elif spec.style == "bb_revert":
        bb_z = frame["bb_z20"].to_numpy("float64")
        long_entry = (bb_z <= -spec.threshold) & (close_pos >= spec.close_pos_long)
        short_entry = (bb_z >= spec.threshold) & (close_pos <= spec.close_pos_short)
    elif spec.style == "ema_reclaim":
        buffer = spec.buffer_bps / 10000.0
        long_entry = (low <= fast * (1.0 + buffer)) & (close > fast) & (close_pos >= spec.close_pos_long)
        short_entry = (high >= fast * (1.0 - buffer)) & (close < fast) & (close_pos <= spec.close_pos_short)
    elif spec.style == "wick_reject":
        lower_wick = frame["lower_wick_atr"].to_numpy("float64")
        upper_wick = frame["upper_wick_atr"].to_numpy("float64")
        long_entry = (lower_wick >= spec.threshold) & (close_pos >= spec.close_pos_long)
        short_entry = (upper_wick >= spec.threshold) & (close_pos <= spec.close_pos_short)
    elif spec.style == "micro_breakout":
        don_high = frame[f"donchian_high{spec.lookback}"].to_numpy("float64")
        don_low = frame[f"donchian_low{spec.lookback}"].to_numpy("float64")
        buffer = spec.threshold / 10000.0
        long_entry = (close >= don_high * (1.0 - buffer)) & (close_pos >= spec.close_pos_long)
        short_entry = (close <= don_low * (1.0 + buffer)) & (close_pos <= spec.close_pos_short)
    elif spec.style == "macd_flip":
        macd = frame["macd_hist"].to_numpy("float64")
        macd_prev = np.r_[np.nan, macd[:-1]]
        long_entry = (macd_prev <= 0.0) & (macd > 0.0) & (close_pos >= spec.close_pos_long)
        short_entry = (macd_prev >= 0.0) & (macd < 0.0) & (close_pos <= spec.close_pos_short)
    elif spec.style == "momentum_pause":
        ret3 = frame["ret3_bps"].to_numpy("float64")
        ret12 = frame["ret12_bps"].to_numpy("float64")
        ret_lookback = frame[f"ret{spec.lookback}_bps"].to_numpy("float64")
        long_entry = (
            (ret_lookback >= spec.threshold)
            & (ret12 >= -0.75 * spec.threshold)
            & (ret3 > 0.0)
            & (close >= open_)
        )
        short_entry = (
            (ret_lookback <= -spec.threshold)
            & (ret12 <= 0.75 * spec.threshold)
            & (ret3 < 0.0)
            & (close <= open_)
        )
    else:
        raise ValueError(f"unknown event style: {spec.style}")

    valid = np.isfinite(close) & np.isfinite(fast) & np.isfinite(frame["atr14"].to_numpy("float64"))
    long_entry &= valid & trend_long
    short_entry &= valid & trend_short
    return compact_signals(long_entry, short_entry)


def build_events(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int], dict[str, int]]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    close = frame["close"].to_numpy("float64")
    source_id = {spec.name: idx for idx, spec in enumerate(EVENT_SPECS)}
    style_names = sorted({spec.style for spec in EVENT_SPECS})
    style_id = {name: idx for idx, name in enumerate(style_names)}
    event_frames: list[pd.DataFrame] = []

    for spec in EVENT_SPECS:
        signal = build_signal_for_spec(frame, spec)
        sig_idx = np.flatnonzero(signal)
        sig_idx = sig_idx[sig_idx + 1 < len(frame)]
        if not len(sig_idx):
            continue
        side = signal[sig_idx].astype("int8")
        ema21 = frame["ema21"].to_numpy("float64")
        ema55 = frame["ema55"].to_numpy("float64")
        ema96 = frame["ema96"].to_numpy("float64")
        ema144 = frame["ema144"].to_numpy("float64")
        close_arr = close[sig_idx]
        side_float = side.astype("float64")
        data: dict[str, Any] = {
            "event_id": np.arange(len(sig_idx), dtype="int64"),
            "signal_idx": sig_idx.astype("int64"),
            "entry_idx": (sig_idx + 1).astype("int64"),
            "signal_ts": frame["ts"].to_numpy()[sig_idx],
            "source": spec.name,
            "style": spec.style,
            "source_id": float(source_id[spec.name]),
            "style_id": float(style_id[spec.style]),
            "side": side_float,
            "threshold": float(spec.threshold),
            "hour": ts.dt.hour.to_numpy()[sig_idx].astype("float64"),
            "day_of_week": ts.dt.dayofweek.to_numpy()[sig_idx].astype("float64"),
            "ema21_55_spread_dir_bps": side_float * (ema21[sig_idx] - ema55[sig_idx]) / close_arr * 10000.0,
            "ema21_96_spread_dir_bps": side_float * (ema21[sig_idx] - ema96[sig_idx]) / close_arr * 10000.0,
            "ema55_144_spread_dir_bps": side_float * (ema55[sig_idx] - ema144[sig_idx]) / close_arr * 10000.0,
            "ema21_slope3_dir_bps": side_float * (ema21[sig_idx] / ema21[np.maximum(sig_idx - 3, 0)] - 1.0)
            * 10000.0,
            "ema55_slope6_dir_bps": side_float * (ema55[sig_idx] / ema55[np.maximum(sig_idx - 6, 0)] - 1.0)
            * 10000.0,
            "dist_ema21_dir_bps": side_float * (close_arr / ema21[sig_idx] - 1.0) * 10000.0,
            "abs_dist_ema21_bps": np.abs(close_arr / ema21[sig_idx] - 1.0) * 10000.0,
            "vwap96_revert_bps": -side_float * frame["vwap96_dev_bps"].to_numpy("float64")[sig_idx],
            "day_vwap_revert_bps": -side_float * frame["day_vwap_dev_bps"].to_numpy("float64")[sig_idx],
            "bb_revert_z": -side_float * frame["bb_z20"].to_numpy("float64")[sig_idx],
            "bb_width20_bps": frame["bb_width20_bps"].to_numpy("float64")[sig_idx],
            "bb_width_z192": frame["bb_width_z192"].to_numpy("float64")[sig_idx],
            "rsi7_revert": -side_float * (frame["rsi7"].to_numpy("float64")[sig_idx] - 50.0),
            "rsi14_revert": -side_float * (frame["rsi14"].to_numpy("float64")[sig_idx] - 50.0),
            "rsi28_revert": -side_float * (frame["rsi28"].to_numpy("float64")[sig_idx] - 50.0),
            "adx14": frame["adx14"].to_numpy("float64")[sig_idx],
            "plus_minus_di_dir": side_float
            * (
                frame["plus_di14"].to_numpy("float64")[sig_idx]
                - frame["minus_di14"].to_numpy("float64")[sig_idx]
            ),
            "chop14": frame["chop14"].to_numpy("float64")[sig_idx],
            "atr_pct_bps": frame["atr_pct_bps"].to_numpy("float64")[sig_idx],
            "atr_ratio_14_96": frame["atr_ratio_14_96"].to_numpy("float64")[sig_idx],
            "range_atr": frame["range_atr"].to_numpy("float64")[sig_idx],
            "abs_body_atr": frame["abs_body_atr"].to_numpy("float64")[sig_idx],
            "body_dir_bps": side_float * frame["body_dir_bps"].to_numpy("float64")[sig_idx],
            "close_pos_dir": np.where(
                side > 0,
                frame["close_pos"].to_numpy("float64")[sig_idx],
                1.0 - frame["close_pos"].to_numpy("float64")[sig_idx],
            ),
            "rejection_wick_atr": np.where(
                side > 0,
                frame["lower_wick_atr"].to_numpy("float64")[sig_idx],
                frame["upper_wick_atr"].to_numpy("float64")[sig_idx],
            ),
            "extension_wick_atr": np.where(
                side > 0,
                frame["upper_wick_atr"].to_numpy("float64")[sig_idx],
                frame["lower_wick_atr"].to_numpy("float64")[sig_idx],
            ),
            "rvol96": frame["rvol96"].to_numpy("float64")[sig_idx],
            "quote_rvol96": frame["quote_rvol96"].to_numpy("float64")[sig_idx],
            "trade_count_rvol96": frame["trade_count_rvol96"].to_numpy("float64")[sig_idx],
        }
        for window in (1, 3, 6, 12, 24, 48, 96, 192):
            data[f"ret{window}_dir_bps"] = (
                side_float * frame[f"ret{window}_bps"].to_numpy("float64")[sig_idx]
            )
        event_frame = pd.DataFrame(data)
        event_frames.append(event_frame)

    if not event_frames:
        raise RuntimeError("no candidate events generated")
    events = pd.concat(event_frames, ignore_index=True)
    events["event_id"] = np.arange(len(events), dtype="int64")
    events["signal_ts"] = pd.to_datetime(events["signal_ts"], utc=True)
    feature_cols = sorted(set().union(*FEATURE_SETS.values()))
    finite_mask = np.ones(len(events), dtype=bool)
    for column in feature_cols:
        if column in events.columns:
            finite_mask &= np.isfinite(events[column].to_numpy("float64"))
    events = events.loc[finite_mask].sort_values(["signal_idx", "source", "side"]).reset_index(drop=True)
    events["event_id"] = np.arange(len(events), dtype="int64")
    return events, source_id, style_id


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


def simulate_event(frame: pd.DataFrame, signal_idx: int, side: int, bracket: BracketSpec) -> dict[str, Any] | None:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    n = len(frame)
    entry_idx = signal_idx + 1
    if entry_idx >= n or side == 0:
        return None

    entry_price = float(open_[entry_idx] * (1.0 + side * ENTRY_SLIPPAGE_RATE))
    target_price = entry_price * (1.0 + side * bracket.tp_bps / 10000.0)
    stop_price = entry_price * (1.0 - side * bracket.sl_bps / 10000.0)
    last_intrabar_i = min(n - 1, entry_idx + bracket.max_hold_bars - 1)
    timeout_i = min(n - 1, entry_idx + bracket.max_hold_bars)
    exit_idx = timeout_i
    reason = "time_open"
    raw_exit_price = float(open_[timeout_i] if timeout_i > last_intrabar_i else close[timeout_i])

    for bar_i in range(entry_idx, last_intrabar_i + 1):
        if crossed_stop(float(open_[bar_i]), stop_price, side):
            exit_idx = bar_i
            reason = "gap_stop_market"
            raw_exit_price = float(open_[bar_i])
            break
        if touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side):
            exit_idx = bar_i
            reason = "stop_market"
            raw_exit_price = float(stop_price)
            break
        if crossed_target(float(open_[bar_i]), target_price, side):
            exit_idx = bar_i
            reason = "gap_target_market"
            raw_exit_price = float(open_[bar_i])
            break
        if touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side):
            exit_idx = bar_i
            reason = "target_limit"
            raw_exit_price = float(target_price)
            break

    exit_price = apply_exit_cost(raw_exit_price, side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    net = gross - fee_cost

    path_high = high[entry_idx : exit_idx + 1]
    path_low = low[entry_idx : exit_idx + 1]
    if side > 0:
        mfe = float(np.nanmax(path_high / entry_price - 1.0))
        mae = float(np.nanmin(path_low / entry_price - 1.0))
    else:
        mfe = float(np.nanmax(1.0 - path_low / entry_price))
        mae = float(np.nanmin(1.0 - path_high / entry_price))

    return {
        "entry_idx": int(entry_idx),
        "exit_idx": int(exit_idx),
        "signal_ts": pd.Timestamp(ts_ns[signal_idx], unit="ns", tz="UTC"),
        "entry_ts": pd.Timestamp(ts_ns[entry_idx], unit="ns", tz="UTC"),
        "exit_ts": pd.Timestamp(ts_ns[exit_idx], unit="ns", tz="UTC"),
        "entry_price": float(entry_price),
        "exit_price": float(exit_price),
        "reason": reason,
        "bars_held": int(exit_idx - entry_idx + 1),
        "net_ret_1x": float(net),
        "mfe_1x": float(mfe),
        "mae_1x": float(mae - FEE_RATE_PER_FILL),
        "target_before_stop": bool(reason in {"target_limit", "gap_target_market"}),
    }


def add_event_outcomes(frame: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    for bracket in BRACKETS:
        rows: list[dict[str, Any]] = []
        for event in result[["signal_idx", "side"]].itertuples(index=False):
            outcome = simulate_event(frame, int(event.signal_idx), int(event.side), bracket)
            rows.append(outcome or {})
        outcome_frame = pd.DataFrame(rows)
        prefix = bracket.name
        result[f"{prefix}_net_ret_1x"] = outcome_frame["net_ret_1x"].to_numpy("float64")
        result[f"{prefix}_mfe_1x"] = outcome_frame["mfe_1x"].to_numpy("float64")
        result[f"{prefix}_mae_1x"] = outcome_frame["mae_1x"].to_numpy("float64")
        result[f"{prefix}_target_before_stop"] = outcome_frame["target_before_stop"].astype(bool).to_numpy()
        result[f"{prefix}_reason"] = outcome_frame["reason"].astype(str).to_numpy()
        result[f"{prefix}_exit_idx"] = outcome_frame["exit_idx"].astype("int64").to_numpy()
    return result


def feature_columns(name: str, events: pd.DataFrame) -> list[str]:
    columns = []
    for column in FEATURE_SETS[name]:
        if column in events.columns and np.isfinite(events[column].to_numpy("float64")).any():
            columns.append(column)
    return columns


def fit_ranker(train: pd.DataFrame, target_col: str, columns: list[str]) -> dict[str, Any]:
    target = train[target_col].to_numpy("float64")
    finite_target = np.isfinite(target)
    global_mean = float(target[finite_target].mean()) if finite_target.any() else 0.0
    model: dict[str, Any] = {
        "global_mean": global_mean,
        "target_col": target_col,
        "numeric": {},
        "categorical": {},
    }
    for column in columns:
        values = train[column].to_numpy("float64")
        finite = np.isfinite(values) & finite_target
        if int(finite.sum()) < max(100, MIN_TRAIN_EVENTS // 4):
            continue
        if column in CATEGORICAL_FEATURES:
            mapping: dict[str, float] = {}
            counts: dict[str, int] = {}
            for category in sorted(np.unique(values[finite])):
                mask = finite & (values == category)
                count = int(mask.sum())
                total = float(target[mask].sum())
                mapping[str(float(category))] = (total + SHRINK * global_mean) / (count + SHRINK)
                counts[str(float(category))] = count
            model["categorical"][column] = {"scores": mapping, "counts": counts}
            continue
        edges = np.unique(np.quantile(values[finite], np.linspace(0.0, 1.0, BIN_COUNT + 1)))
        if len(edges) < 3:
            continue
        bins = np.searchsorted(edges[1:-1], values[finite], side="right")
        scores: list[float] = []
        counts: list[int] = []
        target_finite = target[finite]
        for bin_idx in range(len(edges) - 1):
            in_bin = bins == bin_idx
            count = int(in_bin.sum())
            counts.append(count)
            if count:
                total = float(target_finite[in_bin].sum())
                scores.append((total + SHRINK * global_mean) / (count + SHRINK))
            else:
                scores.append(global_mean)
        model["numeric"][column] = {
            "edges": edges.tolist(),
            "scores": scores,
            "counts": counts,
        }
    return model


def score_with_ranker(events: pd.DataFrame, model: dict[str, Any]) -> np.ndarray:
    global_mean = float(model["global_mean"])
    contributions = np.zeros(len(events), dtype="float64")
    used = np.zeros(len(events), dtype="float64")
    for column, spec in model["numeric"].items():
        values = events[column].to_numpy("float64")
        edges = np.array(spec["edges"], dtype="float64")
        scores = np.array(spec["scores"], dtype="float64")
        finite = np.isfinite(values)
        if not len(scores):
            continue
        bins = np.searchsorted(edges[1:-1], values[finite], side="right")
        contributions[finite] += scores[np.clip(bins, 0, len(scores) - 1)]
        used[finite] += 1.0
    for column, spec in model["categorical"].items():
        values = events[column].to_numpy("float64")
        finite = np.isfinite(values)
        mapped = np.array(
            [spec["scores"].get(str(float(value)), global_mean) for value in values[finite]],
            dtype="float64",
        )
        contributions[finite] += mapped
        used[finite] += 1.0
    scores = np.full(len(events), global_mean, dtype="float64")
    valid = used > 0
    scores[valid] = contributions[valid] / used[valid]
    return scores


def walk_forward_segments(events: pd.DataFrame, train_mode: str, purge_bars: int) -> list[dict[str, Any]]:
    data_start = pd.Timestamp(events["signal_ts"].min())
    data_end = pd.Timestamp(events["signal_ts"].max()) + pd.Timedelta(minutes=5)
    first_month = max(TRAIN_START_FLOOR, data_start.ceil("D").replace(day=1))
    starts = pd.date_range(first_month, data_end, freq="MS", tz="UTC")
    segments: list[dict[str, Any]] = []
    purge_delta = pd.Timedelta(minutes=5 * max(1, purge_bars + 1))
    for idx, test_start in enumerate(starts, start=1):
        test_end = min(test_start + pd.DateOffset(months=1), data_end)
        if test_start >= data_end or test_start >= test_end:
            continue
        if train_mode == "expanding":
            train_start = data_start
        elif train_mode == "trailing_180d":
            train_start = max(data_start, test_start - pd.Timedelta(days=180))
        elif train_mode == "trailing_120d":
            train_start = max(data_start, test_start - pd.Timedelta(days=120))
        else:
            raise ValueError(f"unknown train_mode={train_mode}")
        train_end = test_start - purge_delta
        train_count = int(((events["signal_ts"] >= train_start) & (events["signal_ts"] < train_end)).sum())
        test_count = int(((events["signal_ts"] >= test_start) & (events["signal_ts"] < test_end)).sum())
        if train_count >= MIN_TRAIN_EVENTS and test_count:
            segments.append(
                {
                    "segment": f"{idx:02d}_{test_start:%Y_%m}",
                    "train_start": train_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "train_events": train_count,
                    "test_events": test_count,
                }
            )
    return segments


def score_walk_forward(
    events: pd.DataFrame,
    bracket: BracketSpec,
    feature_set: str,
    train_mode: str,
) -> pd.DataFrame:
    target_col = f"{bracket.name}_net_ret_1x"
    columns = feature_columns(feature_set, events)
    segments = walk_forward_segments(events, train_mode, bracket.max_hold_bars)
    scored_segments: list[pd.DataFrame] = []
    for segment in segments:
        train_mask = (
            (events["signal_ts"] >= segment["train_start"])
            & (events["signal_ts"] < segment["train_end"])
            & np.isfinite(events[target_col].to_numpy("float64"))
        )
        test_mask = (events["signal_ts"] >= segment["test_start"]) & (
            events["signal_ts"] < segment["test_end"]
        )
        train = events.loc[train_mask]
        test = events.loc[test_mask].copy()
        if len(train) < MIN_TRAIN_EVENTS or test.empty:
            continue
        model = fit_ranker(train, target_col, columns)
        train_scores = score_with_ranker(train, model)
        test["score"] = score_with_ranker(test, model)
        test["segment"] = segment["segment"]
        test["train_events"] = int(len(train))
        test["global_train_mean"] = float(model["global_mean"])
        finite_train_scores = train_scores[np.isfinite(train_scores)]
        for quantile in QUANTILES:
            column = f"threshold_q{int(round(quantile * 100)):02d}"
            if len(finite_train_scores):
                test[column] = float(np.quantile(finite_train_scores, quantile))
            else:
                test[column] = np.nan
        scored_segments.append(test)
    if not scored_segments:
        return pd.DataFrame()
    return pd.concat(scored_segments, ignore_index=True)


def replay_events(
    frame: pd.DataFrame,
    selected: pd.DataFrame,
    bracket: BracketSpec,
    candidate_id: str,
) -> list[Trade]:
    if selected.empty:
        return []
    selected = selected.sort_values(["signal_idx", "score"], ascending=[True, False])
    selected = selected.drop_duplicates("signal_idx", keep="first")
    selected = selected.sort_values("signal_idx")
    blocked_until = -1
    trades: list[Trade] = []
    for row in selected.itertuples(index=False):
        signal_idx = int(row.signal_idx)
        side = int(row.side)
        entry_idx = signal_idx + 1
        if entry_idx <= blocked_until:
            continue
        outcome = simulate_event(frame, signal_idx, side, bracket)
        if outcome is None:
            continue
        trades.append(
            Trade(
                candidate_id=candidate_id,
                event_id=int(row.event_id),
                source=str(row.source),
                signal_ts=outcome["signal_ts"],
                entry_ts=outcome["entry_ts"],
                exit_ts=outcome["exit_ts"],
                side=side,
                score=float(row.score),
                entry_price=float(outcome["entry_price"]),
                exit_price=float(outcome["exit_price"]),
                reason=str(outcome["reason"]),
                bars_held=int(outcome["bars_held"]),
                net_ret_1x=float(outcome["net_ret_1x"]),
                mfe_1x=float(outcome["mfe_1x"]),
                mae_1x=float(outcome["mae_1x"]),
            )
        )
        blocked_until = int(outcome["exit_idx"]) + bracket.cooldown_bars
    return trades


def slice_trades(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> list[Trade]:
    return [trade for trade in trades if start <= trade.entry_ts < end]


def equity_max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    drawdown = equity / peak - 1.0
    return float(drawdown.min()) if len(drawdown) else 0.0


def metrics_for_trades(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    returns = np.array([trade.net_ret_1x for trade in trades], dtype="float64")
    days = max((end - start).total_seconds() / 86400.0, 1e-9)
    total_return = float(np.prod(1.0 + returns) - 1.0) if len(returns) else 0.0
    annualized = float((1.0 + total_return) ** (365.0 / days) - 1.0) if total_return > -1.0 else -1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else math.inf
    return {
        "trades": int(len(returns)),
        "days": float(days),
        "trades_per_day": float(len(returns) / days),
        "total_return_1x": total_return,
        "annualized_1x": annualized,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": profit_factor,
        "avg_trade_bps": float(returns.mean() * 10000.0) if len(returns) else 0.0,
        "median_trade_bps": float(np.median(returns) * 10000.0) if len(returns) else 0.0,
        "max_drawdown_1x": equity_max_drawdown(returns),
        "avg_bars_held": float(np.mean([trade.bars_held for trade in trades])) if trades else 0.0,
    }


def monthly_rows(candidate_id: str, trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start.floor("D").replace(day=1)
    while cursor < end:
        next_month = cursor + pd.offsets.MonthBegin(1)
        slice_start = max(start, cursor)
        slice_end = min(end, next_month)
        if slice_start < slice_end:
            monthly_trades = slice_trades(trades, slice_start, slice_end)
            row = {"candidate_id": candidate_id, "month": slice_start.strftime("%Y_%m")}
            row.update(metrics_for_trades(monthly_trades, slice_start, slice_end))
            rows.append(row)
        cursor = next_month
    return rows


def top_level_slices(trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, dict[str, Any]]:
    if not trades:
        return {
            "oos_full": metrics_for_trades([], start, end),
            "fwd_last_20pct": metrics_for_trades([], start, end),
            "recent_90d": metrics_for_trades([], start, end),
            "recent_30d": metrics_for_trades([], start, end),
        }
    last_20_start = start + (end - start) * 0.8
    recent_90_start = max(start, end - pd.Timedelta(days=90))
    recent_30_start = max(start, end - pd.Timedelta(days=30))
    return {
        "oos_full": metrics_for_trades(trades, start, end),
        "fwd_last_20pct": metrics_for_trades(slice_trades(trades, last_20_start, end), last_20_start, end),
        "recent_90d": metrics_for_trades(slice_trades(trades, recent_90_start, end), recent_90_start, end),
        "recent_30d": metrics_for_trades(slice_trades(trades, recent_30_start, end), recent_30_start, end),
    }


def source_quality(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bracket in BRACKETS:
        target_col = f"{bracket.name}_net_ret_1x"
        reason_col = f"{bracket.name}_reason"
        for source, group in events.groupby("source", sort=True):
            returns = group[target_col].to_numpy("float64")
            rows.append(
                {
                    "bracket": bracket.name,
                    "source": source,
                    "events": int(len(group)),
                    "avg_event_bps": float(np.nanmean(returns) * 10000.0),
                    "win_rate": float(np.nanmean(returns > 0)),
                    "target_rate": float(
                        group[reason_col].isin(["target_limit", "gap_target_market"]).mean()
                    ),
                    "long_share": float((group["side"] > 0).mean()),
                }
            )
    return pd.DataFrame(rows).sort_values(["bracket", "avg_event_bps"], ascending=[True, False])


def pass_gate(summary: dict[str, Any], monthly: list[dict[str, Any]]) -> bool:
    oos = summary["oos_full"]
    fwd = summary["fwd_last_20pct"]
    recent = summary["recent_30d"]
    active_months = [row for row in monthly if row["trades"] > 0]
    negative_months = sum(1 for row in active_months if row["total_return_1x"] < 0)
    if oos["trades"] < 80:
        return False
    if not (0.30 <= oos["trades_per_day"] <= 5.50):
        return False
    if oos["total_return_1x"] <= 0 or oos["profit_factor"] < 1.20:
        return False
    if oos["avg_trade_bps"] < 5.0 or oos["max_drawdown_1x"] < -0.20:
        return False
    if fwd["total_return_1x"] <= 0 or recent["total_return_1x"] <= 0:
        return False
    return bool(not active_months or negative_months <= len(active_months) // 2)


def evaluate_candidate(
    frame: pd.DataFrame,
    scored: pd.DataFrame,
    bracket: BracketSpec,
    feature_set: str,
    train_mode: str,
    quantile: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade], pd.DataFrame]:
    q_col = f"threshold_q{int(round(quantile * 100)):02d}"
    selected = scored[scored["score"] >= scored[q_col]].copy()
    candidate_id = f"{bracket.name}__{feature_set}__{train_mode}__q{int(round(quantile * 100)):02d}"
    trades = replay_events(frame, selected, bracket, candidate_id)
    if not scored.empty:
        start = pd.Timestamp(scored["signal_ts"].min())
        end = pd.Timestamp(scored["signal_ts"].max()) + pd.Timedelta(minutes=5)
    else:
        start = pd.Timestamp(frame["ts"].iloc[0])
        end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    slices = top_level_slices(trades, start, end)
    monthly = monthly_rows(candidate_id, trades, start, end)
    active_months = [row for row in monthly if row["trades"] > 0]
    negative_months = sum(1 for row in active_months if row["total_return_1x"] < 0)
    summary = {
        "candidate_id": candidate_id,
        "bracket": bracket.name,
        "tp_bps": bracket.tp_bps,
        "sl_bps": bracket.sl_bps,
        "max_hold_bars": bracket.max_hold_bars,
        "feature_set": feature_set,
        "train_mode": train_mode,
        "quantile": quantile,
        "selected_events": int(len(selected)),
        "selected_unique_signal_bars": int(selected["signal_idx"].nunique()) if not selected.empty else 0,
        "selected_positive_score_events": int((selected["score"] > 0.0).sum()) if not selected.empty else 0,
        "active_months": int(len(active_months)),
        "negative_active_months": int(negative_months),
        "paper_gate": False,
    }
    for slice_name, metrics in slices.items():
        for key, value in metrics.items():
            summary[f"{slice_name}_{key}"] = value
    summary["paper_gate"] = pass_gate(slices, monthly)
    selected_export = selected[
        [
            "event_id",
            "signal_idx",
            "signal_ts",
            "source",
            "style",
            "side",
            "score",
            q_col,
            f"{bracket.name}_net_ret_1x",
            f"{bracket.name}_reason",
        ]
    ].copy()
    selected_export["candidate_id"] = candidate_id
    return summary, monthly, trades, selected_export


def run_search(frame: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[Trade], pd.DataFrame]:
    summaries: list[dict[str, Any]] = []
    monthly_all: list[dict[str, Any]] = []
    top_trades: list[Trade] = []
    top_selected_events = pd.DataFrame()

    scored_cache: dict[tuple[str, str, str], pd.DataFrame] = {}
    for bracket in BRACKETS:
        for feature_set in FEATURE_SETS:
            for train_mode in ("expanding", "trailing_180d", "trailing_120d"):
                cache_key = (bracket.name, feature_set, train_mode)
                scored = score_walk_forward(events, bracket, feature_set, train_mode)
                scored_cache[cache_key] = scored
                if scored.empty:
                    continue
                for quantile in QUANTILES:
                    summary, monthly, trades, selected_export = evaluate_candidate(
                        frame,
                        scored,
                        bracket,
                        feature_set,
                        train_mode,
                        quantile,
                    )
                    summaries.append(summary)
                    monthly_all.extend(monthly)
                    if not top_trades or summary["oos_full_total_return_1x"] > max(
                        row["oos_full_total_return_1x"] for row in summaries[:-1]
                    ):
                        top_trades = trades
                        top_selected_events = selected_export

    summary_frame = pd.DataFrame(summaries)
    if not summary_frame.empty:
        summary_frame["has_trades"] = summary_frame["oos_full_trades"] > 0
        summary_frame = summary_frame.sort_values(
            [
                "paper_gate",
                "has_trades",
                "oos_full_total_return_1x",
                "fwd_last_20pct_total_return_1x",
                "recent_30d_total_return_1x",
            ],
            ascending=[False, False, False, False, False],
        ).reset_index(drop=True)
    monthly_frame = pd.DataFrame(monthly_all)
    return summary_frame, monthly_frame, top_trades, top_selected_events


def trade_frame(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame()
    return pd.DataFrame([asdict(trade) for trade in trades])


def serializable(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not np.isfinite(value):
        return "inf" if value > 0 else "-inf"
    return value


def top_candidate_summary(summary_frame: pd.DataFrame) -> dict[str, Any]:
    if summary_frame.empty:
        return {}
    top = summary_frame.iloc[0].to_dict()
    return {key: serializable(value) for key, value in top.items()}


def render_markdown(
    quality: dict[str, Any],
    events: pd.DataFrame,
    source_frame: pd.DataFrame,
    summary_frame: pd.DataFrame,
    monthly_frame: pd.DataFrame,
) -> str:
    top = top_candidate_summary(summary_frame)
    pass_count = int(summary_frame["paper_gate"].sum()) if not summary_frame.empty else 0
    event_start = pd.Timestamp(events["signal_ts"].min())
    event_end = pd.Timestamp(events["signal_ts"].max())
    lines = [
        "# HYPE-5M-Event-Quality-Scoring V0 诊断",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
    ]
    if pass_count:
        lines.extend(
            [
                f"- V0 找到 `{pass_count}` 个通过 paper gate 的 walk-forward 候选。",
                f"- 当前排名第一：`{top.get('candidate_id')}`。",
            ]
        )
    elif top:
        lines.extend(
            [
                "- V0 没有找到可直接提升为 paper-live 的候选。",
                f"- 最好的 walk-forward 行是 `{top.get('candidate_id')}`，但至少一项稳定性门槛未过。",
            ]
        )
    else:
        lines.append("- V0 没有产生可评估候选。")
    lines.extend(
        [
            "",
            "这不是深度学习版本，而是低依赖的事件质量分箱 ranker。目标是先确认：",
            "入场前特征是否能把同一批事件区分出高低质量。如果 V0 不能稳定分层，",
            "直接上更重的模型也很容易只是更隐蔽地过拟合。",
            "",
            "## 数据质量",
            "",
            "- 数据：Binance HYPEUSDT perpetual `5m`。",
            f"- 时间范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
            f"- 行数：`{quality['rows']}`，期望 K 线：`{quality['expected_bars']}`。",
            f"- 缺口：`{quality['missing_bars']}`。",
            f"- raw/normalized timestamp 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
            f"- raw/normalized 最大差异：`{quality['raw_alignment']['max_abs_diff']}`。",
            f"- `is_closed` 分布：`{quality['is_closed_counts']}`。",
            f"- `source` 分布：`{quality['source_counts']}`。",
            "",
            "## V0 方法",
            "",
            "- 事件源：EMA reclaim、VWAP revert、BB revert、wick reject、micro breakout、MACD flip、momentum pause。",
            "- 标签：closed-bar signal，下一根 open 入场，立即固定 TP/SL bracket。",
            "- 执行：同一根 K 同时触发 TP/SL 时按 stop-first；开盘穿越 stop/target 按 open 市价成交。",
            "- 成本：沿用 5m micro-scalp 的 Binance 观测成本，entry slippage `10.73 bps`，fee `4.1466 bps/fill`。",
            "- 训练：月度 walk-forward，只用测试月之前的事件，并按 bracket 持仓窗口 purge。",
            "- 筛选：使用训练集 score 分位数阈值，只交易测试月里分数排名足够高的事件。",
            "",
            "## 事件集",
            "",
            f"- 事件数：`{len(events)}`。",
            f"- 事件时间范围：`{event_start}` 到 `{event_end}`。",
            f"- 事件源数量：`{events['source'].nunique()}`。",
            "",
            "## 最佳候选",
            "",
        ]
    )
    if top:
        lines.extend(
            [
                f"- candidate：`{top['candidate_id']}`",
                f"- 交易数：`{top['oos_full_trades']}`",
                f"- 频率：`{num(top['oos_full_trades_per_day'])}` trades/day",
                f"- OOS 1x 收益：`{pct(top['oos_full_total_return_1x'])}`",
                f"- OOS 年化：`{pct(top['oos_full_annualized_1x'])}`",
                f"- 胜率：`{pct(top['oos_full_win_rate'])}`",
                f"- PF：`{num(top['oos_full_profit_factor'])}`",
                f"- 平均单笔：`{top['oos_full_avg_trade_bps']:.2f} bps`",
                f"- 最大回撤：`{pct(top['oos_full_max_drawdown_1x'])}`",
                f"- last 20% 收益：`{pct(top['fwd_last_20pct_total_return_1x'])}`",
                f"- 最近 30 天收益：`{pct(top['recent_30d_total_return_1x'])}`",
                f"- 活跃月份/亏损活跃月份：`{top['active_months']}` / `{top['negative_active_months']}`",
                f"- paper gate：`{top['paper_gate']}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Top 10",
            "",
            "| rank | candidate | trades | t/day | ret | PF | win | DD | fwd20 | recent30 | gate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for idx, row in summary_frame.head(10).iterrows():
        lines.append(
            "| "
            f"{idx + 1} | `{row['candidate_id']}` | {int(row['oos_full_trades'])} | "
            f"{row['oos_full_trades_per_day']:.2f} | {pct(row['oos_full_total_return_1x'])} | "
            f"{num(row['oos_full_profit_factor'])} | {pct(row['oos_full_win_rate'])} | "
            f"{pct(row['oos_full_max_drawdown_1x'])} | "
            f"{pct(row['fwd_last_20pct_total_return_1x'])} | "
            f"{pct(row['recent_30d_total_return_1x'])} | {bool(row['paper_gate'])} |"
        )
    lines.extend(
        [
            "",
            "## 事件源质量",
            "",
            "以下是按独立事件标签计算的平均质量，不等于最终可交易回放。",
            "",
            "| bracket | source | events | avg bps | win | target rate | long share |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in source_frame.head(20).iterrows():
        lines.append(
            f"| `{row['bracket']}` | `{row['source']}` | {int(row['events'])} | "
            f"{row['avg_event_bps']:.2f} | {pct(row['win_rate'])} | "
            f"{pct(row['target_rate'])} | {pct(row['long_share'])} |"
        )
    lines.extend(
        [
            "",
            "## 保留产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- 事件表：`{EVENTS_PATH}`",
            f"- 排名表：`{SUMMARY_CSV}`",
            f"- 月度切片：`{MONTHLY_CSV}`",
            f"- 事件源质量：`{SOURCE_CSV}`",
            f"- 最佳候选交易：`{TOP_TRADES_CSV}`",
            f"- 最佳候选入选事件：`{TOP_EVENTS_CSV}`",
            "",
        ]
    )
    if not monthly_frame.empty and top:
        top_monthly = monthly_frame[monthly_frame["candidate_id"] == top["candidate_id"]]
        lines.extend(
            [
                "## 最佳候选月度",
                "",
                "| month | trades | ret | PF | win | avg bps | DD |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for _, row in top_monthly.iterrows():
            lines.append(
                f"| `{row['month']}` | {int(row['trades'])} | {pct(row['total_return_1x'])} | "
                f"{num(row['profit_factor'])} | {pct(row['win_rate'])} | "
                f"{row['avg_trade_bps']:.2f} | {pct(row['max_drawdown_1x'])} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    raw_frame, quality = validate_and_load()
    frame = add_features(raw_frame)
    events, source_id, style_id = build_events(frame)
    events = add_event_outcomes(frame, events)
    source_frame = source_quality(events)
    summary_frame, monthly_frame, top_trades, top_selected_events = run_search(frame, events)

    events.to_parquet(EVENTS_PATH, index=False)
    source_frame.to_csv(SOURCE_CSV, index=False)
    summary_frame.to_csv(SUMMARY_CSV, index=False)
    monthly_frame.to_csv(MONTHLY_CSV, index=False)
    trade_frame(top_trades).to_csv(TOP_TRADES_CSV, index=False)
    top_selected_events.to_csv(TOP_EVENTS_CSV, index=False)

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "quality": quality,
        "cost_model": {
            "fee_rate_per_fill": FEE_RATE_PER_FILL,
            "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
            "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
        },
        "event_specs": [asdict(spec) for spec in EVENT_SPECS],
        "brackets": [asdict(bracket) for bracket in BRACKETS],
        "feature_sets": {key: list(value) for key, value in FEATURE_SETS.items()},
        "source_id": source_id,
        "style_id": style_id,
        "event_count": int(len(events)),
        "summary_rows": int(len(summary_frame)),
        "paper_candidate_pass_count": int(summary_frame["paper_gate"].sum()) if not summary_frame.empty else 0,
        "top_candidate": top_candidate_summary(summary_frame),
        "artifact_paths": {
            "events": str(EVENTS_PATH),
            "summary": str(SUMMARY_CSV),
            "monthly": str(MONTHLY_CSV),
            "source_quality": str(SOURCE_CSV),
            "top_trades": str(TOP_TRADES_CSV),
            "top_selected_events": str(TOP_EVENTS_CSV),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=serializable),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(
        render_markdown(quality, events, source_frame, summary_frame, monthly_frame),
        encoding="utf-8",
    )
    print(json.dumps(report["top_candidate"], ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
