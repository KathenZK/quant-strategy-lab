from __future__ import annotations

import argparse
import json
import math
import random
import warnings
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)


ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
)
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1h"
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=hype_usdt_usdt/funding.parquet"
)
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
DATE_TAG = "2026-07-01"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_adaptive_regime_search_{DATE_TAG}.json"
PREFIT_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_prefit_{DATE_TAG}.csv"
RANKING_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_ranking_{DATE_TAG}.csv"
SLICES_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_slices_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_adaptive_regime_top_trades_{DATE_TAG}.csv"
REPORT_MD = DIAGNOSTIC_DIR / f"hype-1h-adaptive-regime-search-{DATE_TAG}.md"

FEE_PER_FILL = 0.001
SLIPPAGE_PER_FILL = 0.0004
TARGET_ANNUAL_MULTIPLE = 10.0
TARGET_WIN_RATE = 0.50
TARGET_MAX_DD = -0.20
MIN_PREFIT_TRADES = 20
MIN_VALIDATION_TRADES = 5
MIN_HOLDOUT_TRADES = 5
WARMUP_DAYS = 45

EMA_VALUES = (8, 13, 21, 34, 55, 89, 144, 233, 377)
RSI_WINDOWS = (5, 7, 9, 14, 21)
BAND_WINDOWS = (12, 20, 32, 48, 72, 96)
DONCHIAN_WINDOWS = (12, 24, 48, 72, 96, 168, 240)
STOCH_WINDOWS = (7, 14, 21, 28)
CCI_WINDOWS = (14, 20, 40, 72)
VWAP_WINDOWS = (24, 48, 96, 168)
ROC_WINDOWS = (3, 6, 12, 24, 48, 72, 168)
MACD_SETS = ((8, 21, 5), (12, 26, 9), (21, 55, 9), (34, 89, 13))
STYLES = (
    "ema_cross",
    "macd_flip",
    "donchian_break",
    "bb_revert",
    "bb_break",
    "rsi_reversal",
    "stoch_reversal",
    "cci_reversal",
    "williams_reversal",
    "ema_pullback",
    "keltner_break",
    "squeeze_release",
    "di_cross",
    "vwap_revert",
    "momentum_break",
    "wick_reject",
)
TREND_STYLES = {
    "ema_cross",
    "macd_flip",
    "donchian_break",
    "bb_break",
    "ema_pullback",
    "keltner_break",
    "squeeze_release",
    "di_cross",
    "momentum_break",
}
REVERSION_STYLES = set(STYLES) - TREND_STYLES


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    name: str
    style: str
    side_mode: str
    ema_fast: int
    ema_slow: int
    ema_htf: int
    indicator_window: int
    threshold_low: float
    threshold_high: float
    band_k: float
    pullback_atr: float
    roc_window: int
    roc_threshold_bps: float
    macd_fast: int
    macd_slow: int
    macd_signal: int
    min_adx: float
    max_adx: float
    min_rvol: float
    min_atr_bps: float
    max_atr_bps: float
    min_dir_roc_bps: float
    max_dist_ema_bps: float
    htf_mode: str
    require_macd_turn: bool
    require_body_dir: bool
    max_aligned_funding_bps: float
    exit_kind: str
    tp_atr: float
    sl_atr: float
    trail_activation_atr: float
    trail_atr: float
    max_hold_bars: int
    cooldown_bars: int
    entry_delay_bars: int
    sizing_kind: str
    fixed_leverage: float
    risk_fraction: float
    max_leverage: float


@dataclass(slots=True)
class Trade:
    config: str
    style: str
    signal_i: int
    entry_i: int
    exit_i: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    side: int
    entry_price: float
    exit_price: float
    exit_reason: str
    bars_held: int
    exposure: float
    net_ret_1x: float
    equity_ret: float
    mae_1x: float
    equity_mae: float
    mfe_1x: float
    funding_ret_1x: float
    signal_atr_bps: float


@dataclass(slots=True)
class Candidate:
    name: str
    kind: str
    styles: str
    config_names: str
    prefit_score: float
    prefit_pass: bool
    train: dict[str, float]
    validation: dict[str, float]
    prefit: dict[str, float]
    holdout: dict[str, float] | None = None
    full: dict[str, float] | None = None
    target_pass: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad locked-holdout HYPEUSDT 1h adaptive-regime search."
    )
    parser.add_argument("--random-configs", type=int, default=120_000)
    parser.add_argument("--seed", type=int, default=20260701)
    parser.add_argument("--prefit-keep", type=int, default=400)
    parser.add_argument("--holdout-keep", type=int, default=160)
    parser.add_argument("--progress-every", type=int, default=2_000)
    parser.add_argument("--no-ensembles", action="store_true")
    return parser.parse_args()


def pct(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.{digits}f}x"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    files = sorted(DATA_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    raw_files = sorted(RAW_ROOT.glob(f"date=*/{SYMBOL_FILE}"))
    if not files or not raw_files:
        raise FileNotFoundError(
            "Run scripts/fetch_hype_binance_1h.py --refresh before the search"
        )
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    duplicate = int(frame.duplicated("ts").sum())
    frame = frame.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    expected = pd.date_range(frame["ts"].iloc[0], frame["ts"].iloc[-1], freq="1h")
    missing = expected.difference(frame["ts"])
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
    nulls = {column: int(frame[column].isna().sum()) for column in required}
    violations = {
        "high_lt_open_close": int(
            (frame["high"] < frame[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_close": int(
            (frame["low"] > frame[["open", "close"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            ((frame[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
        "negative_volume": int((frame["volume"] < 0).sum()),
        "negative_quote_volume": int((frame["quote_volume"] < 0).sum()),
    }
    if duplicate or len(missing) or sum(nulls.values()) or sum(violations.values()):
        raise RuntimeError("Data-quality blocker in HYPEUSDT 1h normalized lake")
    if set(frame["is_closed"].unique()) != {True}:
        raise RuntimeError("Normalized HYPEUSDT 1h data contains open candles")
    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.drop_duplicates("ts", keep="last").sort_values("ts").reset_index(drop=True)
    if funding["funding_rate"].isna().any():
        raise RuntimeError("Funding history contains null funding_rate")
    quality = {
        "normalized_files": len(files),
        "raw_files": len(raw_files),
        "rows": int(len(frame)),
        "first_ts": frame["ts"].iloc[0].isoformat(),
        "last_ts": frame["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing)),
        "duplicate_bars": duplicate,
        "nulls": nulls,
        "violations": violations,
        "funding_rows": int(len(funding)),
        "funding_first_ts": funding["ts"].iloc[0].isoformat(),
        "funding_last_ts": funding["ts"].iloc[-1].isoformat(),
        "source_counts": {
            str(key): int(value) for key, value in frame["source"].value_counts().items()
        },
    }
    return frame, funding, quality


def rsi(series: pd.Series, window: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    relative = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + relative)


def adx_di(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int
) -> tuple[pd.Series, pd.Series, pd.Series]:
    previous_close = close.shift(1)
    true_range = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    up = high.diff()
    down = -low.diff()
    plus_dm = pd.Series(
        np.where((up > down) & (up > 0), up, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down > up) & (down > 0), down, 0.0), index=high.index
    )
    atr = true_range.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = (
        100.0
        * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    minus_di = (
        100.0
        * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
        / atr.replace(0.0, np.nan)
    )
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def add_htf(frame: pd.DataFrame, rule: str, prefix: str) -> pd.DataFrame:
    offset = pd.Timedelta(rule)
    bars = (
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
    htf = pd.DataFrame({"known_ts": bars.index + offset})
    htf[f"{prefix}_ema12"] = bars["close"].ewm(
        span=12, adjust=False, min_periods=12
    ).mean().to_numpy()
    htf[f"{prefix}_ema48"] = bars["close"].ewm(
        span=48, adjust=False, min_periods=48
    ).mean().to_numpy()
    htf[f"{prefix}_spread"] = htf[f"{prefix}_ema12"] / htf[
        f"{prefix}_ema48"
    ].replace(0.0, np.nan) - 1.0
    left = pd.DataFrame({"known_ts": frame["ts"] + pd.Timedelta(hours=1)})
    return pd.merge_asof(
        left.sort_values("known_ts"),
        htf.sort_values("known_ts"),
        on="known_ts",
        direction="backward",
    ).drop(columns="known_ts")


def add_features(frame: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = result["close"].astype("float64")
    high = result["high"].astype("float64")
    low = result["low"].astype("float64")
    open_ = result["open"].astype("float64")
    volume = result["volume"].astype("float64")
    previous_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    result["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    result["atr48"] = tr.rolling(48, min_periods=48).mean()
    result["atr_bps"] = result["atr14"] / close.replace(0.0, np.nan) * 10_000.0
    result["atr_ratio"] = result["atr14"] / result["atr48"].replace(0.0, np.nan)
    for span in EMA_VALUES:
        result[f"ema{span}"] = close.ewm(
            span=span, adjust=False, min_periods=span
        ).mean()
    for window in RSI_WINDOWS:
        result[f"rsi{window}"] = rsi(close, window)
    for window in ROC_WINDOWS:
        result[f"roc{window}_bps"] = close.pct_change(window) * 10_000.0
    result["rvol48"] = volume / volume.rolling(48, min_periods=48).mean().replace(0.0, np.nan)
    result["body_atr"] = (close - open_) / result["atr14"].replace(0.0, np.nan)
    candle_range = (high - low).replace(0.0, np.nan)
    result["close_pos"] = (close - low) / candle_range
    result["upper_wick_atr"] = (
        high - pd.concat([open_, close], axis=1).max(axis=1)
    ) / result["atr14"].replace(0.0, np.nan)
    result["lower_wick_atr"] = (
        pd.concat([open_, close], axis=1).min(axis=1) - low
    ) / result["atr14"].replace(0.0, np.nan)

    for fast, slow, signal in MACD_SETS:
        line = close.ewm(span=fast, adjust=False, min_periods=fast).mean() - close.ewm(
            span=slow, adjust=False, min_periods=slow
        ).mean()
        signal_line = line.ewm(span=signal, adjust=False, min_periods=signal).mean()
        result[f"macd_{fast}_{slow}_{signal}"] = line
        result[f"macd_hist_{fast}_{slow}_{signal}"] = line - signal_line

    for window in BAND_WINDOWS:
        mid = close.rolling(window, min_periods=window).mean()
        std = close.rolling(window, min_periods=window).std(ddof=0)
        result[f"band_mid{window}"] = mid
        result[f"band_std{window}"] = std
        result[f"bb_z{window}"] = (close - mid) / std.replace(0.0, np.nan)
        width = 4.0 * std / mid.replace(0.0, np.nan)
        result[f"bb_width_z{window}"] = (
            width - width.rolling(168, min_periods=168).mean()
        ) / width.rolling(168, min_periods=168).std(ddof=0).replace(0.0, np.nan)
    for window in DONCHIAN_WINDOWS:
        result[f"don_high{window}"] = high.shift(1).rolling(
            window, min_periods=window
        ).max()
        result[f"don_low{window}"] = low.shift(1).rolling(
            window, min_periods=window
        ).min()
    for window in STOCH_WINDOWS:
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        k = 100.0 * (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)
        result[f"stoch_k{window}"] = k
        result[f"stoch_d{window}"] = k.rolling(3, min_periods=3).mean()
    typical = (high + low + close) / 3.0
    for window in CCI_WINDOWS:
        mean = typical.rolling(window, min_periods=window).mean()
        deviation = typical.rolling(window, min_periods=window).apply(
            lambda values: float(np.mean(np.abs(values - np.mean(values)))), raw=True
        )
        result[f"cci{window}"] = (typical - mean) / (0.015 * deviation.replace(0.0, np.nan))
        rolling_high = high.rolling(window, min_periods=window).max()
        rolling_low = low.rolling(window, min_periods=window).min()
        result[f"willr{window}"] = -100.0 * (rolling_high - close) / (
            rolling_high - rolling_low
        ).replace(0.0, np.nan)
    for window in VWAP_WINDOWS:
        denominator = volume.rolling(window, min_periods=window).sum().replace(0.0, np.nan)
        rolling_vwap = (typical * volume).rolling(window, min_periods=window).sum() / denominator
        result[f"vwap_dev_atr{window}"] = (close - rolling_vwap) / result[
            "atr14"
        ].replace(0.0, np.nan)
    result["adx14"], result["pdi14"], result["mdi14"] = adx_di(high, low, close, 14)

    for rule, prefix in (("4h", "h4"), ("12h", "h12"), ("1D", "d1")):
        htf = add_htf(result, rule, prefix)
        for column in htf.columns:
            result[column] = htf[column].to_numpy()

    result = result.copy()
    funding_known = funding[["ts", "funding_rate"]].rename(columns={"ts": "known_ts"})
    funding_known["known_ts"] = funding_known["known_ts"].astype(
        "datetime64[ns, UTC]"
    )
    left = pd.DataFrame({"known_ts": result["ts"] + pd.Timedelta(hours=1)})
    left["known_ts"] = left["known_ts"].astype("datetime64[ns, UTC]")
    aligned = pd.merge_asof(
        left.sort_values("known_ts"),
        funding_known.sort_values("known_ts"),
        on="known_ts",
        direction="backward",
    )
    result["last_funding_rate"] = aligned["funding_rate"].fillna(0.0).to_numpy()
    return result


def side_allowed(signal: np.ndarray, side_mode: str) -> np.ndarray:
    if side_mode == "long":
        return np.where(signal > 0, signal, 0).astype(np.int8)
    if side_mode == "short":
        return np.where(signal < 0, signal, 0).astype(np.int8)
    return signal.astype(np.int8)


def crossed_up(values: np.ndarray, threshold: float | np.ndarray) -> np.ndarray:
    previous = np.r_[np.nan, values[:-1]]
    if isinstance(threshold, np.ndarray):
        previous_threshold = np.r_[np.nan, threshold[:-1]]
        return (values > threshold) & (previous <= previous_threshold)
    return (values > threshold) & (previous <= threshold)


def crossed_down(values: np.ndarray, threshold: float | np.ndarray) -> np.ndarray:
    previous = np.r_[np.nan, values[:-1]]
    if isinstance(threshold, np.ndarray):
        previous_threshold = np.r_[np.nan, threshold[:-1]]
        return (values < threshold) & (previous >= previous_threshold)
    return (values < threshold) & (previous >= threshold)


def build_signal(frame: pd.DataFrame, cfg: StrategyConfig) -> np.ndarray:
    close = frame["close"].to_numpy("float64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    signal = np.zeros(len(frame), dtype=np.int8)

    if cfg.style == "ema_cross":
        spread = fast - slow
        signal[crossed_up(spread, 0.0)] = 1
        signal[crossed_down(spread, 0.0)] = -1
    elif cfg.style == "macd_flip":
        hist = frame[
            f"macd_hist_{cfg.macd_fast}_{cfg.macd_slow}_{cfg.macd_signal}"
        ].to_numpy("float64")
        signal[crossed_up(hist, 0.0)] = 1
        signal[crossed_down(hist, 0.0)] = -1
    elif cfg.style == "donchian_break":
        upper = frame[f"don_high{cfg.indicator_window}"].to_numpy("float64")
        lower = frame[f"don_low{cfg.indicator_window}"].to_numpy("float64")
        signal[crossed_up(close, upper)] = 1
        signal[crossed_down(close, lower)] = -1
    elif cfg.style in {"bb_revert", "bb_break"}:
        zscore = frame[f"bb_z{cfg.indicator_window}"].to_numpy("float64")
        if cfg.style == "bb_revert":
            signal[crossed_up(zscore, -cfg.band_k)] = 1
            signal[crossed_down(zscore, cfg.band_k)] = -1
        else:
            signal[crossed_up(zscore, cfg.band_k)] = 1
            signal[crossed_down(zscore, -cfg.band_k)] = -1
    elif cfg.style == "rsi_reversal":
        values = frame[f"rsi{cfg.indicator_window}"].to_numpy("float64")
        signal[crossed_up(values, cfg.threshold_low)] = 1
        signal[crossed_down(values, cfg.threshold_high)] = -1
    elif cfg.style == "stoch_reversal":
        k = frame[f"stoch_k{cfg.indicator_window}"].to_numpy("float64")
        d = frame[f"stoch_d{cfg.indicator_window}"].to_numpy("float64")
        cross = k - d
        signal[crossed_up(cross, 0.0) & (k <= cfg.threshold_low)] = 1
        signal[crossed_down(cross, 0.0) & (k >= cfg.threshold_high)] = -1
    elif cfg.style == "cci_reversal":
        values = frame[f"cci{cfg.indicator_window}"].to_numpy("float64")
        signal[crossed_up(values, -cfg.threshold_high)] = 1
        signal[crossed_down(values, cfg.threshold_high)] = -1
    elif cfg.style == "williams_reversal":
        values = frame[f"willr{cfg.indicator_window}"].to_numpy("float64")
        signal[crossed_up(values, cfg.threshold_low)] = 1
        signal[crossed_down(values, cfg.threshold_high)] = -1
    elif cfg.style == "ema_pullback":
        trend = np.sign(fast - slow)
        long_mask = (
            (trend > 0)
            & (low <= fast + cfg.pullback_atr * atr)
            & (close > fast)
            & (close > open_)
        )
        short_mask = (
            (trend < 0)
            & (high >= fast - cfg.pullback_atr * atr)
            & (close < fast)
            & (close < open_)
        )
        signal[long_mask] = 1
        signal[short_mask] = -1
        repeated = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
        signal[repeated] = 0
    elif cfg.style == "keltner_break":
        mid = frame[f"band_mid{cfg.indicator_window}"].to_numpy("float64")
        upper = mid + cfg.band_k * atr
        lower = mid - cfg.band_k * atr
        signal[crossed_up(close, upper)] = 1
        signal[crossed_down(close, lower)] = -1
    elif cfg.style == "squeeze_release":
        width_z = frame[f"bb_width_z{cfg.indicator_window}"].to_numpy("float64")
        zscore = frame[f"bb_z{cfg.indicator_window}"].to_numpy("float64")
        previous_squeeze = np.r_[False, width_z[:-1] <= cfg.threshold_low]
        signal[previous_squeeze & crossed_up(zscore, cfg.band_k)] = 1
        signal[previous_squeeze & crossed_down(zscore, -cfg.band_k)] = -1
    elif cfg.style == "di_cross":
        pdi = frame["pdi14"].to_numpy("float64")
        mdi = frame["mdi14"].to_numpy("float64")
        spread = pdi - mdi
        signal[crossed_up(spread, 0.0)] = 1
        signal[crossed_down(spread, 0.0)] = -1
    elif cfg.style == "vwap_revert":
        deviation = frame[f"vwap_dev_atr{cfg.indicator_window}"].to_numpy("float64")
        signal[crossed_up(deviation, -cfg.band_k)] = 1
        signal[crossed_down(deviation, cfg.band_k)] = -1
    elif cfg.style == "momentum_break":
        momentum = frame[f"roc{cfg.roc_window}_bps"].to_numpy("float64")
        signal[crossed_up(momentum, cfg.roc_threshold_bps)] = 1
        signal[crossed_down(momentum, -cfg.roc_threshold_bps)] = -1
    elif cfg.style == "wick_reject":
        lower_wick = frame["lower_wick_atr"].to_numpy("float64")
        upper_wick = frame["upper_wick_atr"].to_numpy("float64")
        close_pos = frame["close_pos"].to_numpy("float64")
        signal[(lower_wick >= cfg.band_k) & (close_pos >= cfg.threshold_high)] = 1
        signal[(upper_wick >= cfg.band_k) & (close_pos <= cfg.threshold_low)] = -1
    else:
        raise ValueError(f"Unknown style: {cfg.style}")

    signal = side_allowed(signal, cfg.side_mode)
    return apply_filters(frame, signal, cfg)


def apply_filters(
    frame: pd.DataFrame, signal: np.ndarray, cfg: StrategyConfig
) -> np.ndarray:
    idx = np.flatnonzero(signal)
    if len(idx) == 0:
        return signal
    side = signal[idx].astype("float64")
    keep = np.ones(len(idx), dtype=bool)
    adx = frame["adx14"].to_numpy("float64")[idx]
    rvol = frame["rvol48"].to_numpy("float64")[idx]
    atr_bps = frame["atr_bps"].to_numpy("float64")[idx]
    keep &= np.isfinite(adx) & (adx >= cfg.min_adx) & (adx <= cfg.max_adx)
    keep &= np.isfinite(rvol) & (rvol >= cfg.min_rvol)
    keep &= (
        np.isfinite(atr_bps)
        & (atr_bps >= cfg.min_atr_bps)
        & (atr_bps <= cfg.max_atr_bps)
    )
    direction_roc = side * frame[f"roc{cfg.roc_window}_bps"].to_numpy("float64")[idx]
    keep &= np.isfinite(direction_roc) & (direction_roc >= cfg.min_dir_roc_bps)
    close = frame["close"].to_numpy("float64")[idx]
    htf_ema = frame[f"ema{cfg.ema_htf}"].to_numpy("float64")[idx]
    distance = np.abs(close / htf_ema - 1.0) * 10_000.0
    keep &= np.isfinite(distance) & (distance <= cfg.max_dist_ema_bps)
    if cfg.htf_mode != "none":
        spread = frame[f"{cfg.htf_mode}_spread"].to_numpy("float64")[idx]
        keep &= np.isfinite(spread) & (side * spread >= 0.0)
    if cfg.require_macd_turn:
        hist = frame[
            f"macd_hist_{cfg.macd_fast}_{cfg.macd_slow}_{cfg.macd_signal}"
        ].to_numpy("float64")
        delta = hist - np.r_[np.nan, hist[:-1]]
        keep &= np.isfinite(delta[idx]) & (side * delta[idx] > 0.0)
    if cfg.require_body_dir:
        body = frame["body_atr"].to_numpy("float64")[idx]
        keep &= np.isfinite(body) & (side * body > 0.0)
    aligned_funding = (
        side * frame["last_funding_rate"].to_numpy("float64")[idx] * 10_000.0
    )
    keep &= aligned_funding <= cfg.max_aligned_funding_bps
    filtered = np.zeros_like(signal)
    filtered[idx[keep]] = signal[idx[keep]]
    return filtered


def funding_prefix(funding: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    times = (
        funding["ts"]
        .astype("datetime64[ns, UTC]")
        .astype("int64")
        .to_numpy()
    )
    rates = funding["funding_rate"].to_numpy("float64")
    return times, np.r_[0.0, np.cumsum(rates)]


def trade_funding(
    entry_ts_ns: int,
    exit_ts_ns: int,
    side: int,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
) -> float:
    left = int(np.searchsorted(funding_times, entry_ts_ns, side="left"))
    right = int(np.searchsorted(funding_times, exit_ts_ns, side="left"))
    return float(-side * (funding_cumulative[right] - funding_cumulative[left]))


def crossed_stop(open_price: float, stop_price: float, side: int) -> bool:
    return open_price <= stop_price if side > 0 else open_price >= stop_price


def crossed_target(open_price: float, target_price: float, side: int) -> bool:
    return open_price >= target_price if side > 0 else open_price <= target_price


def touched_stop(high: float, low: float, stop_price: float, side: int) -> bool:
    return low <= stop_price if side > 0 else high >= stop_price


def touched_target(high: float, low: float, target_price: float, side: int) -> bool:
    return high >= target_price if side > 0 else low <= target_price


def exposure_for_trade(cfg: StrategyConfig, stop_distance_pct: float) -> float:
    if cfg.sizing_kind == "fixed":
        return cfg.fixed_leverage
    risk_distance = max(stop_distance_pct + 2 * (FEE_PER_FILL + SLIPPAGE_PER_FILL), 1e-6)
    return min(cfg.max_leverage, cfg.risk_fraction / risk_distance)


def simulate_trades(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: StrategyConfig,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
) -> list[Trade]:
    ts_ns = (
        frame["ts"]
        .astype("datetime64[ns, UTC]")
        .astype("int64")
        .to_numpy()
    )
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)
    for signal_i in np.flatnonzero(signal):
        side = int(signal[signal_i])
        entry_i = int(signal_i + cfg.entry_delay_bars)
        if side == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[signal_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        raw_entry = float(open_[entry_i])
        entry_price = raw_entry * (1.0 + side * SLIPPAGE_PER_FILL)
        initial_stop = entry_price - side * cfg.sl_atr * signal_atr
        target = (
            entry_price + side * cfg.tp_atr * signal_atr
            if cfg.exit_kind == "fixed"
            else None
        )
        stop_price = initial_stop
        best_price = entry_price
        timeout_i = min(n - 1, entry_i + cfg.max_hold_bars)
        exit_i = timeout_i
        raw_exit = float(open_[timeout_i])
        reason = "timeout_open"
        for bar_i in range(entry_i, timeout_i + 1):
            bar_open = float(open_[bar_i])
            if bar_i == timeout_i:
                exit_i = bar_i
                raw_exit = bar_open
                reason = "timeout_open"
                break
            if crossed_stop(bar_open, stop_price, side):
                exit_i = bar_i
                raw_exit = bar_open
                reason = "stop_gap_open"
                break
            if target is not None and crossed_target(bar_open, target, side):
                exit_i = bar_i
                raw_exit = float(target)
                reason = "target_gap_or_open"
                break
            stop_hit = touched_stop(float(high[bar_i]), float(low[bar_i]), stop_price, side)
            target_hit = target is not None and touched_target(
                float(high[bar_i]), float(low[bar_i]), float(target), side
            )
            if stop_hit and target_hit:
                exit_i = bar_i
                raw_exit = stop_price
                reason = "both_hit_stop_first"
                break
            if stop_hit:
                exit_i = bar_i
                raw_exit = stop_price
                reason = "stop_market"
                break
            if target_hit:
                exit_i = bar_i
                raw_exit = float(target)
                reason = "take_profit"
                break
            if cfg.exit_kind == "trailing":
                if side > 0:
                    best_price = max(best_price, float(high[bar_i]))
                    if best_price - entry_price >= cfg.trail_activation_atr * signal_atr:
                        stop_price = max(
                            stop_price, best_price - cfg.trail_atr * signal_atr
                        )
                else:
                    best_price = min(best_price, float(low[bar_i]))
                    if entry_price - best_price >= cfg.trail_activation_atr * signal_atr:
                        stop_price = min(
                            stop_price, best_price + cfg.trail_atr * signal_atr
                        )
        exit_price = raw_exit * (1.0 - side * SLIPPAGE_PER_FILL)
        price_ret = side * (exit_price / entry_price - 1.0)
        fee_ret = FEE_PER_FILL * (1.0 + exit_price / entry_price)
        funding_ret = trade_funding(
            int(ts_ns[entry_i]),
            int(ts_ns[exit_i]),
            side,
            funding_times,
            funding_cumulative,
        )
        net_ret_1x = price_ret - fee_ret + funding_ret
        if side > 0:
            mae = float(np.nanmin(low[entry_i : exit_i + 1] / entry_price - 1.0))
            mfe = float(np.nanmax(high[entry_i : exit_i + 1] / entry_price - 1.0))
        else:
            mae = float(np.nanmin(1.0 - high[entry_i : exit_i + 1] / entry_price))
            mfe = float(np.nanmax(1.0 - low[entry_i : exit_i + 1] / entry_price))
        mae -= 2 * FEE_PER_FILL
        stop_distance_pct = cfg.sl_atr * signal_atr / entry_price
        exposure = exposure_for_trade(cfg, stop_distance_pct)
        trades.append(
            Trade(
                config=cfg.name,
                style=cfg.style,
                signal_i=int(signal_i),
                entry_i=entry_i,
                exit_i=exit_i,
                signal_ts=pd.Timestamp(ts_ns[signal_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=side,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason=reason,
                bars_held=int(exit_i - entry_i),
                exposure=float(exposure),
                net_ret_1x=float(net_ret_1x),
                equity_ret=float(exposure * net_ret_1x),
                mae_1x=float(mae),
                equity_mae=float(exposure * mae),
                mfe_1x=float(mfe),
                funding_ret_1x=float(funding_ret),
                signal_atr_bps=float(signal_atr / frame["close"].iloc[signal_i] * 10_000.0),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades


def empty_metrics(days: float) -> dict[str, float]:
    return {
        "days": days,
        "trades": 0.0,
        "trades_per_day": 0.0,
        "final_equity": 1.0,
        "total_return": 0.0,
        "annual_multiple": 1.0,
        "annual_return": 0.0,
        "max_dd": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_trade": 0.0,
        "median_trade": 0.0,
        "avg_exposure": 0.0,
        "max_exposure": 0.0,
        "funding_return_1x": 0.0,
        "long_trades": 0.0,
        "short_trades": 0.0,
    }


def metrics(
    trades: list[Trade], start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, float]:
    selected = [trade for trade in trades if start <= trade.entry_ts < end]
    days = max((end - start).total_seconds() / 86_400.0, 1.0)
    if not selected:
        return empty_metrics(days)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    returns: list[float] = []
    for trade in selected:
        trough = equity * max(0.001, 1.0 + trade.equity_mae)
        max_dd = min(max_dd, trough / peak - 1.0)
        equity *= max(0.001, 1.0 + trade.equity_ret)
        peak = max(peak, equity)
        max_dd = min(max_dd, equity / peak - 1.0)
        returns.append(trade.equity_ret)
    annual_multiple = equity ** (365.25 / days) if equity > 0 else 0.0
    positives = [value for value in returns if value > 0]
    negatives = [abs(value) for value in returns if value < 0]
    return {
        "days": float(days),
        "trades": float(len(selected)),
        "trades_per_day": float(len(selected) / days),
        "final_equity": float(equity),
        "total_return": float(equity - 1.0),
        "annual_multiple": float(annual_multiple),
        "annual_return": float(annual_multiple - 1.0),
        "max_dd": float(max_dd),
        "win_rate": float(len(positives) / len(returns)),
        "profit_factor": float(sum(positives) / sum(negatives)) if negatives else math.inf,
        "avg_trade": float(np.mean(returns)),
        "median_trade": float(np.median(returns)),
        "avg_exposure": float(np.mean([trade.exposure for trade in selected])),
        "max_exposure": float(np.max([trade.exposure for trade in selected])),
        "funding_return_1x": float(sum(trade.funding_ret_1x for trade in selected)),
        "long_trades": float(sum(trade.side > 0 for trade in selected)),
        "short_trades": float(sum(trade.side < 0 for trade in selected)),
    }


def prefit_score(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> float:
    if prefit["trades"] < MIN_PREFIT_TRADES or validation["trades"] < MIN_VALIDATION_TRADES:
        return -1e9
    ann_values = [
        max(train["annual_multiple"], 1e-9),
        max(validation["annual_multiple"], 1e-9),
        max(prefit["annual_multiple"], 1e-9),
    ]
    log_ann = [math.log(min(value, 1e6)) for value in ann_values]
    dd_penalty = sum(max(0.0, -0.20 - item["max_dd"]) * 12.0 for item in (train, validation, prefit))
    win_penalty = sum(max(0.0, 0.50 - item["win_rate"]) * 5.0 for item in (train, validation, prefit))
    negative_penalty = 4.0 * sum(item["total_return"] <= 0.0 for item in (train, validation))
    balance = min(log_ann[0], log_ann[1])
    score = (
        0.7 * log_ann[2]
        + 0.8 * balance
        + 0.25 * min(prefit["profit_factor"], 5.0)
        + 0.35 * prefit["win_rate"]
        - dd_penalty
        - win_penalty
        - negative_penalty
    )
    if prefit_gate(train, validation, prefit):
        score += 8.0
    return float(score)


def shape_gate(metric: dict[str, float], *, min_trades: int) -> bool:
    return bool(
        metric["trades"] >= min_trades
        and metric["annual_multiple"] >= TARGET_ANNUAL_MULTIPLE
        and metric["win_rate"] >= TARGET_WIN_RATE
        and metric["max_dd"] > TARGET_MAX_DD
    )


def prefit_gate(
    train: dict[str, float], validation: dict[str, float], prefit: dict[str, float]
) -> bool:
    return bool(
        shape_gate(prefit, min_trades=MIN_PREFIT_TRADES)
        and train["total_return"] > 0.0
        and validation["trades"] >= MIN_VALIDATION_TRADES
        and validation["total_return"] > 0.0
        and validation["win_rate"] >= TARGET_WIN_RATE
        and validation["max_dd"] > TARGET_MAX_DD
    )


def target_gate(holdout: dict[str, float], full: dict[str, float]) -> bool:
    return bool(
        shape_gate(full, min_trades=MIN_PREFIT_TRADES)
        and shape_gate(holdout, min_trades=MIN_HOLDOUT_TRADES)
    )


def random_config(rng: random.Random, index: int) -> StrategyConfig:
    style = rng.choice(STYLES)
    fast = rng.choice(EMA_VALUES[:-2])
    valid_slow = [value for value in EMA_VALUES if value > fast * 1.35]
    slow = rng.choice(valid_slow)
    macd = rng.choice(MACD_SETS)
    if style in {"bb_revert", "bb_break", "keltner_break", "squeeze_release"}:
        indicator_window = rng.choice(BAND_WINDOWS)
    elif style == "donchian_break":
        indicator_window = rng.choice(DONCHIAN_WINDOWS)
    elif style == "rsi_reversal":
        indicator_window = rng.choice(RSI_WINDOWS)
    elif style == "stoch_reversal":
        indicator_window = rng.choice(STOCH_WINDOWS)
    elif style in {"cci_reversal", "williams_reversal"}:
        indicator_window = rng.choice(CCI_WINDOWS)
    elif style == "vwap_revert":
        indicator_window = rng.choice(VWAP_WINDOWS)
    else:
        indicator_window = rng.choice(BAND_WINDOWS)
    low = rng.choice((15.0, 20.0, 25.0, 30.0, 35.0, 40.0))
    high = rng.choice((60.0, 65.0, 70.0, 75.0, 80.0, 85.0))
    if style == "williams_reversal":
        low = rng.choice((-95.0, -90.0, -85.0, -80.0, -70.0))
        high = rng.choice((-30.0, -20.0, -15.0, -10.0, -5.0))
    if style == "cci_reversal":
        high = rng.choice((75.0, 100.0, 125.0, 150.0, 200.0))
    band_k = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0))
    if style in {"bb_revert", "bb_break"}:
        band_k = rng.choice((1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0))
    if style == "squeeze_release":
        low = rng.choice((-2.0, -1.5, -1.0, -0.5, 0.0))
        band_k = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5))
    if style == "wick_reject":
        low = rng.choice((0.15, 0.2, 0.25, 0.3, 0.35))
        high = rng.choice((0.65, 0.7, 0.75, 0.8, 0.85))
        band_k = rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0))
    min_adx = rng.choice((0.0, 0.0, 12.0, 16.0, 20.0, 24.0, 28.0, 32.0, 36.0))
    max_adx = rng.choice((100.0, 100.0, 100.0, 24.0, 30.0, 36.0, 45.0))
    if max_adx <= min_adx:
        max_adx = 100.0
    min_atr = rng.choice((0.0, 50.0, 75.0, 100.0, 125.0, 150.0, 200.0))
    max_atr = rng.choice((10_000.0, 10_000.0, 200.0, 250.0, 300.0, 400.0, 600.0))
    if max_atr <= min_atr:
        max_atr = 10_000.0
    exit_kind = rng.choices(("fixed", "trailing"), weights=(0.72, 0.28), k=1)[0]
    sizing_kind = rng.choices(("risk", "fixed"), weights=(0.65, 0.35), k=1)[0]
    side_mode = rng.choices(("both", "long", "short"), weights=(0.45, 0.35, 0.20), k=1)[0]
    return StrategyConfig(
        name=f"HYPE_1H_AR_R{index:06d}",
        style=style,
        side_mode=side_mode,
        ema_fast=fast,
        ema_slow=slow,
        ema_htf=rng.choice((55, 89, 144, 233, 377)),
        indicator_window=indicator_window,
        threshold_low=low,
        threshold_high=high,
        band_k=band_k,
        pullback_atr=rng.choice((-0.5, -0.25, 0.0, 0.25, 0.5, 0.75)),
        roc_window=rng.choice(ROC_WINDOWS),
        roc_threshold_bps=rng.choice((25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0, 500.0)),
        macd_fast=macd[0],
        macd_slow=macd[1],
        macd_signal=macd[2],
        min_adx=min_adx,
        max_adx=max_adx,
        min_rvol=rng.choice((0.0, 0.0, 0.6, 0.8, 1.0, 1.25, 1.5, 2.0)),
        min_atr_bps=min_atr,
        max_atr_bps=max_atr,
        min_dir_roc_bps=rng.choice((-10_000.0, -10_000.0, -200.0, -100.0, 0.0, 50.0, 100.0, 200.0)),
        max_dist_ema_bps=rng.choice((10_000.0, 10_000.0, 300.0, 500.0, 750.0, 1_000.0, 1_500.0, 2_500.0)),
        htf_mode=rng.choices(
            ("none", "h4", "h12", "d1"), weights=(0.50, 0.20, 0.20, 0.10), k=1
        )[0],
        require_macd_turn=rng.random() < 0.25,
        require_body_dir=rng.random() < 0.30,
        max_aligned_funding_bps=rng.choice((10_000.0, 10_000.0, 1.0, 2.0, 4.0, 8.0)),
        exit_kind=exit_kind,
        tp_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)),
        sl_atr=rng.choice((0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
        trail_activation_atr=rng.choice((0.75, 1.0, 1.5, 2.0, 3.0, 4.0)),
        trail_atr=rng.choice((0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)),
        max_hold_bars=rng.choice((6, 12, 18, 24, 36, 48, 72, 96, 120, 168, 240)),
        cooldown_bars=rng.choice((0, 0, 3, 6, 12, 24)),
        entry_delay_bars=1,
        sizing_kind=sizing_kind,
        fixed_leverage=rng.choice((0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
        risk_fraction=rng.choice((0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03)),
        max_leverage=rng.choice((1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
    )


def curated_configs() -> list[StrategyConfig]:
    rng = random.Random(2026070101)
    configs: list[StrategyConfig] = []
    index = 0
    for style, side, exit_kind, sizing_kind in product(
        STYLES, ("both", "long", "short"), ("fixed", "trailing"), ("risk", "fixed")
    ):
        for _ in range(4):
            cfg = random_config(rng, index)
            while cfg.style != style:
                cfg = random_config(rng, index)
            configs.append(
                replace(
                    cfg,
                    name=f"HYPE_1H_AR_C{index:05d}",
                    style=style,
                    side_mode=side,
                    exit_kind=exit_kind,
                    sizing_kind=sizing_kind,
                )
            )
            index += 1
    return configs


def candidate_from_config(
    cfg: StrategyConfig,
    trades: list[Trade],
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
) -> Candidate | None:
    train = metrics(trades, train_start, train_end)
    validation = metrics(trades, train_end, val_end)
    prefit = metrics(trades, train_start, val_end)
    score = prefit_score(train, validation, prefit)
    if score <= -1e8:
        return None
    return Candidate(
        name=cfg.name,
        kind="single",
        styles=cfg.style,
        config_names=cfg.name,
        prefit_score=score,
        prefit_pass=prefit_gate(train, validation, prefit),
        train=train,
        validation=validation,
        prefit=prefit,
    )


def candidate_sort_key(candidate: Candidate) -> tuple[int, float, float, float]:
    return (
        int(candidate.prefit_pass),
        candidate.prefit_score,
        candidate.prefit["annual_multiple"],
        candidate.prefit["profit_factor"],
    )


def retain_candidate(
    retained: list[tuple[Candidate, StrategyConfig]],
    item: tuple[Candidate, StrategyConfig],
    keep: int,
) -> list[tuple[Candidate, StrategyConfig]]:
    retained.append(item)
    if len(retained) > keep * 3:
        retained = sorted(
            retained, key=lambda value: candidate_sort_key(value[0]), reverse=True
        )[:keep]
    return retained


def merge_trade_sets(
    left: list[Trade], right: list[Trade], left_priority: float, right_priority: float
) -> list[Trade]:
    tagged = [(trade, left_priority) for trade in left] + [
        (trade, right_priority) for trade in right
    ]
    tagged.sort(key=lambda item: (item[0].entry_i, -item[1], item[0].exit_i))
    selected: list[Trade] = []
    blocked_until = -1
    for trade, _priority in tagged:
        if trade.entry_i <= blocked_until:
            continue
        selected.append(trade)
        blocked_until = trade.exit_i
    return selected


def make_ensembles(
    retained: list[tuple[Candidate, StrategyConfig]],
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    train_start: pd.Timestamp,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
) -> list[tuple[Candidate, tuple[StrategyConfig, StrategyConfig], list[Trade]]]:
    cache: dict[str, list[Trade]] = {}

    def trades_for(cfg: StrategyConfig) -> list[Trade]:
        if cfg.name not in cache:
            cache[cfg.name] = simulate_trades(
                frame,
                build_signal(frame, cfg),
                cfg,
                funding_times,
                funding_cumulative,
            )
        return cache[cfg.name]

    trend = [item for item in retained if item[1].style in TREND_STYLES][:35]
    reversion = [item for item in retained if item[1].style in REVERSION_STYLES][:35]
    ensembles: list[tuple[Candidate, tuple[StrategyConfig, StrategyConfig], list[Trade]]] = []
    for trend_item, reversion_item in product(trend, reversion):
        left_candidate, left_cfg = trend_item
        right_candidate, right_cfg = reversion_item
        merged = merge_trade_sets(
            trades_for(left_cfg),
            trades_for(right_cfg),
            left_candidate.prefit_score,
            right_candidate.prefit_score,
        )
        train_metrics = metrics(merged, train_start, train_end)
        validation_metrics = metrics(merged, train_end, val_end)
        prefit_metrics = metrics(merged, train_start, val_end)
        score = prefit_score(train_metrics, validation_metrics, prefit_metrics)
        if score <= -1e8:
            continue
        candidate = Candidate(
            name=f"ENS__{left_cfg.name}__{right_cfg.name}",
            kind="ensemble",
            styles=f"{left_cfg.style}+{right_cfg.style}",
            config_names=f"{left_cfg.name}+{right_cfg.name}",
            prefit_score=score,
            prefit_pass=prefit_gate(train_metrics, validation_metrics, prefit_metrics),
            train=train_metrics,
            validation=validation_metrics,
            prefit=prefit_metrics,
        )
        ensembles.append((candidate, (left_cfg, right_cfg), merged))
    return sorted(
        ensembles, key=lambda item: candidate_sort_key(item[0]), reverse=True
    )[:200]


def candidate_row(candidate: Candidate, configs: dict[str, StrategyConfig]) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": candidate.name,
        "kind": candidate.kind,
        "styles": candidate.styles,
        "config_names": candidate.config_names,
        "prefit_score": candidate.prefit_score,
        "prefit_pass": candidate.prefit_pass,
        "target_pass": candidate.target_pass,
    }
    for prefix, values in (
        ("train", candidate.train),
        ("validation", candidate.validation),
        ("prefit", candidate.prefit),
        ("holdout", candidate.holdout or {}),
        ("full", candidate.full or {}),
    ):
        for key, value in values.items():
            row[f"{prefix}_{key}"] = value
    if candidate.kind == "single" and candidate.name in configs:
        row.update({f"cfg_{key}": value for key, value in asdict(configs[candidate.name]).items()})
    return row


def finalize_candidate(
    candidate: Candidate,
    trades: list[Trade],
    train_start: pd.Timestamp,
    holdout_start: pd.Timestamp,
    full_end: pd.Timestamp,
) -> Candidate:
    candidate.holdout = metrics(trades, holdout_start, full_end)
    candidate.full = metrics(trades, train_start, full_end)
    candidate.target_pass = target_gate(candidate.holdout, candidate.full)
    return candidate


def final_sort_key(candidate: Candidate) -> tuple[int, int, float, float, float]:
    holdout = candidate.holdout or empty_metrics(1.0)
    full = candidate.full or empty_metrics(1.0)
    return (
        int(candidate.target_pass),
        int(candidate.prefit_pass),
        min(math.log(max(holdout["annual_multiple"], 1e-9)), 20.0)
        - max(0.0, -0.20 - holdout["max_dd"]) * 10.0,
        full["annual_multiple"],
        candidate.prefit_score,
    )


def diagnostic_slices(
    trades: list[Trade],
    start: pd.Timestamp,
    train_end: pd.Timestamp,
    val_end: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, Any]]:
    windows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = [
        ("train", start, train_end),
        ("validation", train_end, val_end),
        ("locked_holdout", val_end, end),
        ("full", start, end),
        ("last_30d", max(start, end - pd.Timedelta(days=30)), end),
        ("last_60d", max(start, end - pd.Timedelta(days=60)), end),
        ("last_90d", max(start, end - pd.Timedelta(days=90)), end),
    ]
    cursor = start
    month_no = 1
    while cursor < end:
        right = min(end, cursor + pd.Timedelta(days=30))
        windows.append((f"rolling_block_{month_no:02d}", cursor, right))
        cursor = right
        month_no += 1
    return [
        {"window": name, "start": left, "end": right, **metrics(trades, left, right)}
        for name, left, right in windows
    ]


def trade_rows(trades: list[Trade]) -> list[dict[str, Any]]:
    return [asdict(trade) for trade in trades]


def report_markdown(
    *,
    quality: dict[str, Any],
    split: dict[str, str],
    search_counts: dict[str, int],
    finalists: list[Candidate],
    best: Candidate,
    top_slices: list[dict[str, Any]],
) -> str:
    holdout = best.holdout or empty_metrics(1.0)
    full = best.full or empty_metrics(1.0)
    target_hits = sum(candidate.target_pass for candidate in finalists)
    prefit_hits = sum(candidate.prefit_pass for candidate in finalists)
    lines = [
        "# HYPE-1H-Adaptive-Regime 广泛搜索 - 2026-07-01",
        "",
        "## 结论",
        "",
        (
            "本轮找到同时通过 full 与 locked holdout 硬门槛的策略，仍需继续完成参数邻域、成本/延迟和生产状态机审计。"
            if target_hits
            else "本轮没有找到同时通过 full 与 locked holdout 硬门槛的策略，结论为 `NO-GO / not promoted`。"
        ),
        "",
        f"- 最终 finalists：`{len(finalists)}`；prefit 命中：`{prefit_hits}`；locked target 命中：`{target_hits}`。",
        f"- 目标：年化权益倍率 `>= {TARGET_ANNUAL_MULTIPLE:.1f}x`、胜率 `>= {TARGET_WIN_RATE:.0%}`、最大回撤 `> {TARGET_MAX_DD:.0%}`。",
        "- 年化倍率按复合净值计算；`10.0x` 对应 annual return `+900%`。",
        "",
        "## 数据质量",
        "",
        f"- Binance USD-M Futures `HYPEUSDT` `1h`：`{quality['rows']}` 根。",
        f"- UTC：`{quality['first_ts']}` 至 `{quality['last_ts']}`。",
        f"- missing=`{quality['missing_bars']}`，duplicate=`{quality['duplicate_bars']}`，raw/normalized 日分区均为 `{quality['raw_files']}`。",
        f"- funding rows：`{quality['funding_rows']}`。",
        "",
        "## 防泄漏时间切分",
        "",
        f"- train：`{split['train_start']}` 至 `{split['train_end']}`。",
        f"- validation：`{split['train_end']}` 至 `{split['validation_end']}`。",
        f"- locked holdout：`{split['validation_end']}` 至 `{split['full_end']}`。",
        "- 随机搜索、排序和 ensemble 组合只读取 train + validation 指标；locked holdout 只对冻结 finalists 解锁一次。",
        "",
        "## 执行与成本",
        "",
        "- 已闭合 `1h` K 生成信号，默认下一根 open 市价入场。",
        "- 成交后立即生效的 ATR bracket；trailing 仅在一根 K 完全闭合后更新，更新后的 stop 从下一根 K 生效。",
        "- 同 K TP/SL 双触发按 stop-first；stop 被 open 穿越时按 open 市价退出。",
        f"- fee `{FEE_PER_FILL:.4%}/fill`，slippage `{SLIPPAGE_PER_FILL:.4%}/fill`，另逐笔计入 Binance 历史 funding。",
        "",
        "## 搜索覆盖",
        "",
    ]
    for key, value in search_counts.items():
        lines.append(f"- {key}：`{value}`。")
    lines.extend(
        [
            "- 指标/机制：EMA、MACD、Donchian、Bollinger、RSI、Stochastic、CCI、Williams %R、EMA pullback、Keltner、squeeze、ADX/DI、rolling VWAP、momentum、wick rejection、ATR、RVOL、4h/12h/1d regime 和 funding filter。",
            "",
            "## 最佳冻结 finalist",
            "",
            f"- id：`{best.name}`。",
            f"- kind/style：`{best.kind}` / `{best.styles}`。",
            f"- full：annual `{mult(full['annual_multiple'])}`，return `{pct(full['total_return'])}`，DD `{pct(full['max_dd'])}`，win `{pct(full['win_rate'])}`，trades `{int(full['trades'])}`，PF `{full['profit_factor']:.3f}`。",
            f"- locked holdout：annual `{mult(holdout['annual_multiple'])}`，return `{pct(holdout['total_return'])}`，DD `{pct(holdout['max_dd'])}`，win `{pct(holdout['win_rate'])}`，trades `{int(holdout['trades'])}`，PF `{holdout['profit_factor']:.3f}`。",
            f"- target pass：`{best.target_pass}`。",
            "",
            "## 最佳 finalist 时间切片",
            "",
            "| Window | Annual | Return | DD | Win | Trades | PF |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in top_slices:
        lines.append(
            f"| `{row['window']}` | `{mult(row['annual_multiple'])}` | `{pct(row['total_return'])}` | `{pct(row['max_dd'])}` | `{pct(row['win_rate'])}` | `{int(row['trades'])}` | `{row['profit_factor']:.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            (
                "当前即使硬门槛命中，也只进入 robustness/live-executable 审计，不自动成为 candidate。"
                if target_hits
                else "当前没有策略通过 locked hard gate，因此不得标记为 candidate、paper-live、dry-run、handoff 或 live。"
            ),
            "",
            "## 产物",
            "",
            f"- Summary：`{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- Prefit：`{PREFIT_CSV.relative_to(ROOT)}`",
            f"- Ranking：`{RANKING_CSV.relative_to(ROOT)}`",
            f"- Slices：`{SLICES_CSV.relative_to(ROOT)}`",
            f"- Top trades：`{TRADES_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = load_data()
    frame = add_features(frame, funding)
    funding_times, funding_cumulative = funding_prefix(funding)

    raw_start = pd.Timestamp(frame["ts"].iloc[0])
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = raw_start + pd.Timedelta(days=WARMUP_DAYS)
    usable = full_end - train_start
    train_end = train_start + usable * 0.55
    validation_end = train_start + usable * 0.775
    split = {
        "raw_start": raw_start.isoformat(),
        "train_start": train_start.isoformat(),
        "train_end": train_end.isoformat(),
        "validation_end": validation_end.isoformat(),
        "full_end": full_end.isoformat(),
    }
    print(f"data rows={len(frame)} split={split}", flush=True)

    rng = random.Random(args.seed)
    configs = curated_configs()
    configs.extend(random_config(rng, index + len(configs)) for index in range(args.random_configs))
    retained: list[tuple[Candidate, StrategyConfig]] = []
    evaluated = 0
    eligible = 0
    prefit_passes = 0
    for index, cfg in enumerate(configs, start=1):
        signal = build_signal(frame, cfg)
        if int(np.count_nonzero(signal)) < 6:
            continue
        trades = simulate_trades(
            frame, signal, cfg, funding_times, funding_cumulative
        )
        candidate = candidate_from_config(
            cfg, trades, train_start, train_end, validation_end
        )
        evaluated += 1
        if candidate is None:
            continue
        eligible += 1
        prefit_passes += int(candidate.prefit_pass)
        retained = retain_candidate(
            retained, (candidate, cfg), args.prefit_keep
        )
        if index % args.progress_every == 0:
            current = max(
                retained, key=lambda item: candidate_sort_key(item[0])
            )[0]
            print(
                f"search {index}/{len(configs)} evaluated={evaluated} eligible={eligible} "
                f"prefit_pass={prefit_passes} retained={len(retained)} "
                f"best={current.name} score={current.prefit_score:.3f} "
                f"ann={current.prefit['annual_multiple']:.3f} dd={current.prefit['max_dd']:.3f}",
                flush=True,
            )
    retained = sorted(
        retained, key=lambda item: candidate_sort_key(item[0]), reverse=True
    )[: args.prefit_keep]
    config_map = {cfg.name: cfg for _candidate, cfg in retained}
    pd.DataFrame(
        [candidate_row(candidate, config_map) for candidate, _cfg in retained]
    ).to_csv(PREFIT_CSV, index=False)
    print(
        f"single search done generated={len(configs)} evaluated={evaluated} "
        f"eligible={eligible} prefit_pass={prefit_passes} retained={len(retained)}",
        flush=True,
    )

    ensembles: list[
        tuple[Candidate, tuple[StrategyConfig, StrategyConfig], list[Trade]]
    ] = []
    if not args.no_ensembles:
        ensembles = make_ensembles(
            retained,
            frame,
            funding_times,
            funding_cumulative,
            train_start,
            train_end,
            validation_end,
        )
        print(f"ensembles retained={len(ensembles)}", flush=True)

    finalists: list[tuple[Candidate, list[Trade]]] = []
    single_finalists = retained[: args.holdout_keep]
    for candidate, cfg in single_finalists:
        trades = simulate_trades(
            frame,
            build_signal(frame, cfg),
            cfg,
            funding_times,
            funding_cumulative,
        )
        finalists.append(
            (
                finalize_candidate(
                    candidate, trades, train_start, validation_end, full_end
                ),
                trades,
            )
        )
    for candidate, _cfg_pair, trades in ensembles[: args.holdout_keep]:
        finalists.append(
            (
                finalize_candidate(
                    candidate, trades, train_start, validation_end, full_end
                ),
                trades,
            )
        )
    finalists.sort(key=lambda item: final_sort_key(item[0]), reverse=True)
    if not finalists:
        raise RuntimeError("No finalists survived the prefit minimum-trade gate")
    best, best_trades = finalists[0]
    ranking = pd.DataFrame(
        [candidate_row(candidate, config_map) for candidate, _trades in finalists]
    )
    ranking.to_csv(RANKING_CSV, index=False)
    slices = diagnostic_slices(
        best_trades, train_start, train_end, validation_end, full_end
    )
    pd.DataFrame(slices).to_csv(SLICES_CSV, index=False)
    pd.DataFrame(trade_rows(best_trades)).to_csv(TRADES_CSV, index=False)

    search_counts = {
        "curated_configs": len(curated_configs()),
        "random_configs": args.random_configs,
        "generated_configs": len(configs),
        "evaluated_configs": evaluated,
        "prefit_eligible": eligible,
        "prefit_pass_observations": prefit_passes,
        "retained_single": len(retained),
        "evaluated_ensemble_pairs": min(35, sum(cfg.style in TREND_STYLES for _, cfg in retained))
        * min(35, sum(cfg.style in REVERSION_STYLES for _, cfg in retained)),
        "retained_ensembles": len(ensembles),
        "locked_finalists": len(finalists),
        "locked_target_pass": sum(candidate.target_pass for candidate, _ in finalists),
    }
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "family_id": "HYPE-1H-AR",
        "status": (
            "hard_gate_hit_pending_robustness_not_promoted"
            if any(candidate.target_pass for candidate, _ in finalists)
            else "no_go_not_promoted"
        ),
        "targets": {
            "annual_multiple": TARGET_ANNUAL_MULTIPLE,
            "annual_return": TARGET_ANNUAL_MULTIPLE - 1.0,
            "win_rate": TARGET_WIN_RATE,
            "max_drawdown_strictly_greater_than": TARGET_MAX_DD,
        },
        "costs": {
            "fee_per_fill": FEE_PER_FILL,
            "slippage_per_fill": SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "data_quality": quality,
        "split": split,
        "search_counts": search_counts,
        "best": candidate_row(best, config_map),
        "best_slices": slices,
        "top_20": [
            candidate_row(candidate, config_map)
            for candidate, _trades in finalists[:20]
        ],
        "retained_single_configs": {
            cfg.name: asdict(cfg) for _candidate, cfg in retained
        },
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    REPORT_MD.write_text(
        report_markdown(
            quality=quality,
            split=split,
            search_counts=search_counts,
            finalists=[candidate for candidate, _trades in finalists],
            best=best,
            top_slices=slices,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            json_safe(
                {
                    "status": payload["status"],
                    "search_counts": search_counts,
                    "best": candidate_row(best, config_map),
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
