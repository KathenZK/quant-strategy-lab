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


DATA_ROOT = Path("data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1m")
RAW_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=1m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

FAMILY_ROOT = Path("research/hype/1m-ma-pullback-scalp")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

RUN_DATE = "2026-06-26"
REPORT_PATH = ARTIFACT_ROOT / f"hype_1m_ma_pullback_scalp_search_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_1m_ma_pullback_scalp_search_summary_{RUN_DATE}.csv"
SLICES_PATH = ARTIFACT_ROOT / f"hype_1m_ma_pullback_scalp_search_slices_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_1m_ma_pullback_scalp_search_monthly_{RUN_DATE}.csv"
TOP_TRADES_PATH = ARTIFACT_ROOT / f"hype_1m_ma_pullback_scalp_search_top_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-1m-ma-pullback-scalp-search-{RUN_DATE}.md"

# Conservative execution-cost constants for a taker-heavy 1m scalp.
FEE_BPS_PER_FILL = 5.0
ENTRY_SLIPPAGE_BPS = 10.73
EXIT_SLIPPAGE_BPS = 5.0

MIN_PAPER_TRADES = 60
MIN_PAPER_WIN_RATE = 0.52
MIN_PAPER_PROFIT_FACTOR = 1.15
MAX_PAPER_DRAWDOWN = -0.20


@dataclass(frozen=True, slots=True)
class PullbackConfig:
    name: str
    side_mode: str
    trigger_style: str
    fast_ma: int
    slow_ma: int
    structure_window: int
    platform_window: int
    structure_margin_bps: float
    slope_lookback: int
    min_slow_slope_bps: float
    min_fast_slope_bps: float
    pullback_touch_bps: float
    reclaim_bps: float
    min_body_atr: float
    max_dist_slow_bps: float
    min_atr_bps: float
    max_atr_bps: float
    min_rvol60: float
    min_adx14: float
    close_pos: float
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
    parser = argparse.ArgumentParser(
        description="Search executable HYPE 1m moving-average pullback scalp variants."
    )
    parser.add_argument("--max-random-configs", type=int, default=3500)
    parser.add_argument("--seed", type=int, default=20260626)
    parser.add_argument("--top-keep", type=int, default=80)
    parser.add_argument("--progress-every", type=int, default=500)
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


def json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def load_partitioned(root: Path) -> tuple[pd.DataFrame, list[Path]]:
    files = sorted(root.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no parquet files under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame, files


def validate_hype_1m() -> tuple[pd.DataFrame, dict[str, Any]]:
    normalized, normalized_files = load_partitioned(DATA_ROOT)
    raw, raw_files = load_partitioned(RAW_ROOT)

    duplicate_ts = int(normalized.duplicated("ts").sum())
    raw_duplicate_ts = int(raw.duplicated("ts").sum())
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    raw = raw.sort_values("ts").reset_index(drop=True)

    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="1min")
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
    nulls = {column: int(normalized[column].isna().sum()) for column in required if column in normalized.columns}
    violations = {
        "high_lt_max_open_close": int((normalized["high"] < normalized[["open", "close"]].max(axis=1)).sum()),
        "low_gt_min_open_close": int((normalized["low"] > normalized[["open", "close"]].min(axis=1)).sum()),
        "nonpositive_ohlc": int(((normalized[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()),
        "negative_volume": int((normalized["volume"] < 0).sum()),
        "negative_quote_volume": int((normalized["quote_volume"] < 0).sum()),
        "negative_trade_count": int((normalized["trade_count"] < 0).sum()),
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

    compare_columns = ["open", "high", "low", "close", "volume", "quote_volume", "trade_count", "vwap"]
    merged = normalized[["ts", *compare_columns]].merge(
        raw[["ts", *compare_columns]],
        on="ts",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    alignment = {
        "rows": int(len(merged)),
        "left_only": int((merged["_merge"] == "left_only").sum()),
        "right_only": int((merged["_merge"] == "right_only").sum()),
        "mismatch_counts": {},
        "max_abs_diff": {},
    }
    both = merged.loc[merged["_merge"].eq("both")].copy()
    for column in compare_columns:
        lhs = both[f"{column}_normalized"].astype(float).to_numpy()
        rhs = both[f"{column}_raw"].astype(float).to_numpy()
        diff = np.abs(lhs - rhs)
        tolerance = 1e-9 if column != "trade_count" else 0.0
        mismatch = ~np.isclose(lhs, rhs, rtol=0.0, atol=tolerance, equal_nan=True)
        alignment["mismatch_counts"][column] = int(mismatch.sum())
        alignment["max_abs_diff"][column] = float(np.nanmax(diff)) if len(diff) else 0.0

    source_counts = {
        str(key): int(value) for key, value in normalized["source"].value_counts(dropna=False).to_dict().items()
    }
    closed_counts = {
        str(key): int(value) for key, value in normalized["is_closed"].value_counts(dropna=False).to_dict().items()
    }
    quality = {
        "normalized_file_count": len(normalized_files),
        "raw_ohlcv_file_count": len(raw_files),
        "rows": int(len(normalized)),
        "raw_rows": int(len(raw)),
        "start_ts": str(normalized["ts"].iloc[0]),
        "end_ts": str(normalized["ts"].iloc[-1]),
        "expected_bars": int(len(expected)),
        "missing_bars": int(len(missing)),
        "first_missing": str(missing[0]) if len(missing) else None,
        "duplicate_ts": duplicate_ts,
        "raw_duplicate_ts": raw_duplicate_ts,
        "nulls": nulls,
        "source_counts": source_counts,
        "is_closed_counts": closed_counts,
        "ohlcv_violations": violations,
        "raw_normalized_alignment": alignment,
        "zero_volume_bars": int((normalized["volume"] == 0).sum()),
        "volume_p99": float(normalized["volume"].quantile(0.99)),
        "volume_max": float(normalized["volume"].max()),
    }

    blockers: list[str] = []
    if duplicate_ts:
        blockers.append(f"normalized duplicate ts={duplicate_ts}")
    if raw_duplicate_ts:
        blockers.append(f"raw duplicate ts={raw_duplicate_ts}")
    if len(missing):
        blockers.append(f"missing bars={len(missing)}, first={missing[0]}")
    if sum(nulls.values()):
        blockers.append(f"required nulls={nulls}")
    if any(violations.values()):
        blockers.append(f"OHLCV violations={violations}")
    if set(normalized["is_closed"].dropna().unique()) != {True}:
        blockers.append("non-closed bars are present")
    if alignment["left_only"] or alignment["right_only"]:
        blockers.append(f"raw/normalized ts mismatch={alignment}")
    if any(alignment["mismatch_counts"].values()):
        blockers.append(f"raw/normalized value mismatch={alignment['mismatch_counts']}")
    if blockers:
        raise RuntimeError("data-quality blocker: " + "; ".join(blockers))
    return normalized, quality


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)


def adx_di(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(high, low, close)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    atr = tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / window, adjust=False, min_periods=window).mean() / atr.replace(0.0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def add_features(
    frame: pd.DataFrame, spans: list[int], structure_windows: list[int], platform_windows: list[int]
) -> pd.DataFrame:
    result = frame.sort_values("ts").reset_index(drop=True).copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"].astype("float64")
    high = result["high"].astype("float64")
    low = result["low"].astype("float64")
    open_ = result["open"].astype("float64")
    volume = result["volume"].astype("float64")

    for span in sorted(set(spans)):
        result[f"ema{span}"] = close.ewm(span=span, adjust=False, min_periods=span).mean()

    tr = true_range(high, low, close)
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    result["atr60"] = tr.rolling(60, min_periods=60).mean()
    result["atr_bps"] = result["atr14"] / close.replace(0.0, np.nan) * 10000.0
    result["rvol60"] = volume / volume.rolling(60, min_periods=60).mean().replace(0.0, np.nan)
    result["adx14"], result["pdi14"], result["mdi14"] = adx_di(high, low, close, 14)

    candle_range = (high - low).replace(0.0, np.nan)
    result["close_pos"] = (close - low) / candle_range
    result["body_dir"] = np.sign(close - open_).fillna(0.0)
    result["body_atr"] = (close - open_).abs() / result["atr14"].replace(0.0, np.nan)

    for window in sorted(set(structure_windows)):
        recent_high = high.rolling(window, min_periods=window).max()
        recent_low = low.rolling(window, min_periods=window).min()
        previous_high = high.shift(window).rolling(window, min_periods=window).max()
        previous_low = low.shift(window).rolling(window, min_periods=window).min()
        result[f"recent_high{window}"] = recent_high
        result[f"recent_low{window}"] = recent_low
        result[f"previous_high{window}"] = previous_high
        result[f"previous_low{window}"] = previous_low

    for window in sorted(set(platform_windows)):
        result[f"platform_high{window}"] = high.shift(1).rolling(window, min_periods=window).max()
        result[f"platform_low{window}"] = low.shift(1).rolling(window, min_periods=window).min()

    return result


def build_signal(frame: pd.DataFrame, cfg: PullbackConfig) -> np.ndarray:
    close = frame["close"].to_numpy("float64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    high_prev = np.r_[np.nan, high[:-1]]
    low_prev = np.r_[np.nan, low[:-1]]
    open_prev = np.r_[np.nan, open_[:-1]]
    fast = frame[f"ema{cfg.fast_ma}"].to_numpy("float64")
    slow = frame[f"ema{cfg.slow_ma}"].to_numpy("float64")
    fast_prev = np.r_[np.nan, fast[:-1]]
    close_prev = np.r_[np.nan, close[:-1]]

    recent_high = frame[f"recent_high{cfg.structure_window}"].to_numpy("float64")
    recent_low = frame[f"recent_low{cfg.structure_window}"].to_numpy("float64")
    previous_high = frame[f"previous_high{cfg.structure_window}"].to_numpy("float64")
    previous_low = frame[f"previous_low{cfg.structure_window}"].to_numpy("float64")
    platform_high = frame[f"platform_high{cfg.platform_window}"].to_numpy("float64")
    platform_low = frame[f"platform_low{cfg.platform_window}"].to_numpy("float64")

    slow_slope = (slow / np.r_[np.full(cfg.slope_lookback, np.nan), slow[:-cfg.slope_lookback]] - 1.0) * 10000.0
    fast_slope = (fast / np.r_[np.full(cfg.slope_lookback, np.nan), fast[:-cfg.slope_lookback]] - 1.0) * 10000.0
    margin = cfg.structure_margin_bps / 10000.0

    higher_structure = (recent_high > previous_high * (1.0 + margin)) & (recent_low > previous_low * (1.0 + margin / 2.0))
    lower_structure = (recent_low < previous_low * (1.0 - margin)) & (recent_high < previous_high * (1.0 - margin / 2.0))

    dist_slow_bps = np.abs(close / slow - 1.0) * 10000.0
    touch = cfg.pullback_touch_bps / 10000.0
    reclaim = cfg.reclaim_bps / 10000.0

    long_trend = (
        (fast > slow)
        & (close > slow)
        & (slow_slope >= cfg.min_slow_slope_bps)
        & (fast_slope >= cfg.min_fast_slope_bps)
        & higher_structure
    )
    short_trend = (
        (fast < slow)
        & (close < slow)
        & (slow_slope <= -cfg.min_slow_slope_bps)
        & (fast_slope <= -cfg.min_fast_slope_bps)
        & lower_structure
    )

    long_touch = (low <= fast * (1.0 + touch)) | (close_prev <= fast_prev * (1.0 + touch))
    short_touch = (high >= fast * (1.0 - touch)) | (close_prev >= fast_prev * (1.0 - touch))
    long_reclaim = (
        long_touch
        & (close >= fast * (1.0 + reclaim))
        & (frame["close_pos"].to_numpy("float64") >= cfg.close_pos)
    )
    short_reclaim = (
        short_touch
        & (close <= fast * (1.0 - reclaim))
        & (frame["close_pos"].to_numpy("float64") <= 1.0 - cfg.close_pos)
    )
    if cfg.trigger_style == "reclaim":
        long_pullback_end = long_reclaim
        short_pullback_end = short_reclaim
    elif cfg.trigger_style == "platform_break":
        long_pullback_end = (
            long_touch
            & (close >= fast)
            & (close >= platform_high * (1.0 + reclaim))
            & (frame["close_pos"].to_numpy("float64") >= cfg.close_pos)
        )
        short_pullback_end = (
            short_touch
            & (close <= fast)
            & (close <= platform_low * (1.0 - reclaim))
            & (frame["close_pos"].to_numpy("float64") <= 1.0 - cfg.close_pos)
        )
    elif cfg.trigger_style == "engulf_reclaim":
        body_atr = frame["body_atr"].to_numpy("float64")
        long_pullback_end = (
            long_reclaim
            & (close > high_prev)
            & (close_prev < open_prev)
            & (body_atr >= cfg.min_body_atr)
        )
        short_pullback_end = (
            short_reclaim
            & (close < low_prev)
            & (close_prev > open_prev)
            & (body_atr >= cfg.min_body_atr)
        )
    else:
        raise ValueError(f"unknown trigger_style={cfg.trigger_style}")

    long_pullback_end = (
        long_pullback_end
    )

    common = (
        (dist_slow_bps <= cfg.max_dist_slow_bps)
        & (frame["atr_bps"].to_numpy("float64") >= cfg.min_atr_bps)
        & (frame["atr_bps"].to_numpy("float64") <= cfg.max_atr_bps)
        & (frame["rvol60"].to_numpy("float64") >= cfg.min_rvol60)
        & (frame["adx14"].to_numpy("float64") >= cfg.min_adx14)
    )
    if cfg.require_body_dir:
        long_pullback_end &= close > open_
        short_pullback_end &= close < open_

    signal = np.zeros(len(frame), dtype=np.int8)
    if cfg.side_mode != "short":
        signal[np.nan_to_num(common & long_trend & long_pullback_end, nan=False).astype(bool)] = 1
    if cfg.side_mode != "long":
        signal[np.nan_to_num(common & short_trend & short_pullback_end, nan=False).astype(bool)] = -1

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


def simulate_trades(frame: pd.DataFrame, signal: np.ndarray, cfg: PullbackConfig) -> tuple[list[Trade], dict[str, int]]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    trades: list[Trade] = []
    reason_counts: dict[str, int] = {}
    blocked_until = -1
    n = len(frame)

    entry_slip = ENTRY_SLIPPAGE_BPS / 10000.0
    exit_slip = EXIT_SLIPPAGE_BPS / 10000.0
    fee_rate = FEE_BPS_PER_FILL / 10000.0

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        timeout_i = entry_i + cfg.max_hold_bars
        if entry_i >= n or timeout_i >= n or entry_i <= blocked_until or side == 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * entry_slip))
        target_price = entry_price * (1.0 + side * cfg.tp_bps / 10000.0)
        stop_price = entry_price * (1.0 - side * cfg.sl_bps / 10000.0)
        last_intrabar_i = timeout_i - 1
        exit_i = timeout_i
        reason = "time_open"
        raw_exit_price = float(open_[timeout_i])

        for bar_i in range(entry_i, last_intrabar_i + 1):
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

        exit_price = float(raw_exit_price * (1.0 - side * exit_slip))
        gross = side * (exit_price / entry_price - 1.0)
        fee_cost = fee_rate * (1.0 + exit_price / entry_price)
        net = float(gross - fee_cost)

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
                net_ret_1x=net,
                mae_1x=float(mae - fee_rate),
                mfe_1x=mfe,
            )
        )
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, reason_counts


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=1)
    span = end - start
    train_end = start + span * 0.60
    val_end = start + span * 0.80
    return [
        {"name": "full", "start": start, "end": end},
        {"name": "train_first_60pct", "start": start, "end": train_end},
        {"name": "val_next_20pct", "start": train_end, "end": val_end},
        {"name": "fwd_last_20pct", "start": val_end, "end": end},
        {"name": "recent_30d", "start": max(start, end - pd.Timedelta(days=30)), "end": end},
        {"name": "recent_14d", "start": max(start, end - pd.Timedelta(days=14)), "end": end},
    ]


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=1)
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
    profit_factor = float(wins.sum() / abs(losses.sum())) if len(losses) and losses.sum() < 0 else float("inf")
    payoff_ratio = float(avg_win / avg_loss_abs) if avg_loss_abs > 0 else float("inf") if avg_win > 0 else 0.0
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
    if trades_per_day <= 0:
        return 0.0
    center = 4.0
    width = 3.5
    return float(math.exp(-((trades_per_day - center) / width) ** 2))


def score_row(row: dict[str, Any]) -> dict[str, Any]:
    full_trades = int(row["full_trades"])
    full_tpd = float(row["full_trades_per_day"])
    full_ann = float(row["full_annualized_multiple"])
    full_total = float(row["full_total_return"])
    full_win = float(row["full_win_rate"])
    full_pf = float(row["full_profit_factor"])
    full_dd = float(row["full_max_dd"])
    val_pf = float(row["val_next_20pct_profit_factor"])
    fwd_pf = float(row["fwd_last_20pct_profit_factor"])
    val_ret = float(row["val_next_20pct_total_return"])
    fwd_ret = float(row["fwd_last_20pct_total_return"])
    recent30 = float(row["recent_30d_total_return"])
    recent14 = float(row["recent_14d_total_return"])

    paper_pass = (
        full_trades >= MIN_PAPER_TRADES
        and full_total > 0
        and full_ann > 1.0
        and full_win >= MIN_PAPER_WIN_RATE
        and full_pf >= MIN_PAPER_PROFIT_FACTOR
        and full_dd >= MAX_PAPER_DRAWDOWN
        and val_pf >= 1.0
        and fwd_pf >= 1.0
        and val_ret >= -0.03
        and fwd_ret >= -0.03
        and recent30 >= -0.03
        and recent14 >= -0.03
    )
    row["paper_candidate_pass"] = bool(paper_pass)
    row["frequency_fit"] = frequency_fit(full_tpd)
    sample_ratio = min(full_trades / MIN_PAPER_TRADES, 1.0)
    pf_score = min(full_pf if np.isfinite(full_pf) else 3.0, 3.0)
    val_pf_score = min(val_pf if np.isfinite(val_pf) else 3.0, 3.0)
    fwd_pf_score = min(fwd_pf if np.isfinite(fwd_pf) else 3.0, 3.0)
    base_score = (
        min(80.0, math.log(max(full_ann, 1e-9)) * 16.0)
        + 65.0 * full_win
        + 35.0 * pf_score
        + 45.0 * row["frequency_fit"]
        + 35.0 * max(full_dd, -1.0)
        + 14.0 * val_pf_score
        + 18.0 * fwd_pf_score
        + 10.0 * max(min(recent30 * 5.0, 2.0), -3.0)
    )
    row["score"] = float(
        base_score * sample_ratio
        - 140.0 * (1.0 - sample_ratio)
        - (35.0 if int(row["val_next_20pct_trades"]) < 10 else 0.0)
        - (35.0 if int(row["fwd_last_20pct_trades"]) < 10 else 0.0)
    )
    return row


def row_for_config(
    frame: pd.DataFrame, cfg: PullbackConfig, slices: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade]]:
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


def curated_configs() -> list[PullbackConfig]:
    configs: list[PullbackConfig] = []
    pairs = [(5, 34), (8, 55), (13, 89), (21, 144), (34, 233), (55, 377)]
    exits = [
        (80.0, 60.0, 5, 2),
        (100.0, 70.0, 10, 5),
        (140.0, 100.0, 10, 5),
        (200.0, 100.0, 10, 10),
        (220.0, 140.0, 15, 10),
        (300.0, 180.0, 30, 20),
    ]
    filters = [
        (0.0, 0.0, 0.0, 9999.0, 0.0, 0.0, 600.0),
        (5.0, 0.0, 8.0, 600.0, 0.5, 8.0, 400.0),
        (10.0, 5.0, 12.0, 500.0, 0.8, 12.0, 300.0),
        (20.0, 10.0, 20.0, 350.0, 1.0, 16.0, 220.0),
    ]
    idx = 0
    for side_mode in ("both", "long", "short"):
        for trigger_style in ("reclaim", "platform_break", "engulf_reclaim"):
            platform_windows = (5,) if trigger_style == "reclaim" else (5, 8, 13)
            if trigger_style == "engulf_reclaim":
                platform_windows = (5, 8)
            min_body_atrs = (0.35, 0.60) if trigger_style == "engulf_reclaim" else (0.0,)
            structure_windows = (12, 20, 30, 45) if trigger_style == "reclaim" else (12, 30)
            exit_grid = exits if trigger_style == "reclaim" else (exits[1], exits[3], exits[5])
            filter_grid = filters if trigger_style == "reclaim" else (filters[1], filters[2])
            for platform_window in platform_windows:
                for min_body_atr in min_body_atrs:
                    for fast_ma, slow_ma in pairs:
                        for structure_window in structure_windows:
                            for tp_bps, sl_bps, hold, cooldown in exit_grid:
                                for slow_slope, fast_slope, min_atr, max_atr, rvol, adx, max_dist in filter_grid:
                                    idx += 1
                                    configs.append(
                                        PullbackConfig(
                                            name=f"HYPE_1M_MA_PBS_C{idx:05d}",
                                            side_mode=side_mode,
                                            trigger_style=trigger_style,
                                            fast_ma=fast_ma,
                                            slow_ma=slow_ma,
                                            structure_window=structure_window,
                                            platform_window=platform_window,
                                            structure_margin_bps=5.0,
                                            slope_lookback=20,
                                            min_slow_slope_bps=slow_slope,
                                            min_fast_slope_bps=fast_slope,
                                            pullback_touch_bps=20.0,
                                            reclaim_bps=5.0,
                                            min_body_atr=min_body_atr,
                                            max_dist_slow_bps=max_dist,
                                            min_atr_bps=min_atr,
                                            max_atr_bps=max_atr,
                                            min_rvol60=rvol,
                                            min_adx14=adx,
                                            close_pos=0.62,
                                            require_body_dir=True,
                                            tp_bps=tp_bps,
                                            sl_bps=sl_bps,
                                            max_hold_bars=hold,
                                            cooldown_bars=cooldown,
                                        )
                                    )
    return configs


def random_config(rng: random.Random, idx: int) -> PullbackConfig:
    fast_ma, slow_ma = rng.choice(
        [(5, 34), (8, 55), (13, 89), (21, 144), (34, 233), (55, 377), (89, 610)]
    )
    tp_bps = rng.choice([50.0, 60.0, 80.0, 100.0, 120.0, 140.0, 180.0, 200.0, 260.0, 320.0])
    sl_bps = rng.choice([35.0, 45.0, 60.0, 75.0, 90.0, 100.0, 130.0, 160.0, 220.0])
    return PullbackConfig(
        name=f"HYPE_1M_MA_PBS_R{idx:05d}",
        side_mode=rng.choice(["both", "both", "long", "short"]),
        trigger_style=rng.choice(["reclaim", "reclaim", "platform_break", "engulf_reclaim"]),
        fast_ma=fast_ma,
        slow_ma=slow_ma,
        structure_window=rng.choice([8, 12, 16, 20, 30, 45, 60, 90]),
        platform_window=rng.choice([3, 5, 8, 13, 21]),
        structure_margin_bps=rng.choice([0.0, 3.0, 5.0, 10.0, 20.0, 35.0]),
        slope_lookback=rng.choice([5, 10, 20, 30, 60]),
        min_slow_slope_bps=rng.choice([0.0, 3.0, 5.0, 10.0, 20.0, 35.0, 60.0]),
        min_fast_slope_bps=rng.choice([-10.0, 0.0, 3.0, 5.0, 10.0, 20.0, 35.0]),
        pullback_touch_bps=rng.choice([0.0, 5.0, 10.0, 20.0, 35.0, 50.0, 75.0]),
        reclaim_bps=rng.choice([0.0, 3.0, 5.0, 10.0, 20.0, 35.0]),
        min_body_atr=rng.choice([0.0, 0.20, 0.35, 0.50, 0.75, 1.0]),
        max_dist_slow_bps=rng.choice([120.0, 180.0, 240.0, 320.0, 450.0, 650.0, 900.0]),
        min_atr_bps=rng.choice([0.0, 5.0, 10.0, 15.0, 25.0, 40.0, 60.0]),
        max_atr_bps=rng.choice([80.0, 120.0, 180.0, 260.0, 400.0, 650.0, 9999.0]),
        min_rvol60=rng.choice([0.0, 0.4, 0.6, 0.8, 1.0, 1.25, 1.5]),
        min_adx14=rng.choice([0.0, 8.0, 12.0, 16.0, 20.0, 25.0, 32.0]),
        close_pos=rng.choice([0.54, 0.58, 0.62, 0.68, 0.74, 0.80]),
        require_body_dir=rng.choice([False, True, True]),
        tp_bps=tp_bps,
        sl_bps=sl_bps,
        max_hold_bars=rng.choice([3, 5, 8, 10, 15, 20, 30, 45]),
        cooldown_bars=rng.choice([0, 1, 2, 3, 5, 8, 10, 15, 20, 30]),
    )


def build_configs(max_random: int, seed: int) -> list[PullbackConfig]:
    rng = random.Random(seed)
    configs = curated_configs()
    for idx in range(max_random):
        configs.append(random_config(rng, idx))
    return configs


def monthly_rows(frame: pd.DataFrame, cfg_by_name: dict[str, PullbackConfig], top_names: list[str]) -> list[dict[str, Any]]:
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
        "| name | trigger | side | fast/slow | TP/SL/hold | trades/day | trades | ann | win | PF | avg | maxDD | VAL PF | FWD PF | recent30 |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in rows.head(limit).to_dict(orient="records"):
        output.append(
            f"| `{item['name']}` | `{item['cfg_trigger_style']}` | `{item['cfg_side_mode']}` | "
            f"`{int(item['cfg_fast_ma'])}/{int(item['cfg_slow_ma'])}` | "
            f"`{float(item['cfg_tp_bps']):.0f}/{float(item['cfg_sl_bps']):.0f}/{int(item['cfg_max_hold_bars'])}` | "
            f"`{float(item['full_trades_per_day']):.2f}` | `{int(item['full_trades'])}` | "
            f"`{mult(float(item['full_annualized_multiple']))}` | `{pct(float(item['full_win_rate']))}` | "
            f"`{num(float(item['full_profit_factor']))}` | `{bps(float(item['full_avg_trade']))}` | "
            f"`{pct(float(item['full_max_dd']))}` | `{num(float(item['val_next_20pct_profit_factor']))}` | "
            f"`{num(float(item['fwd_last_20pct_profit_factor']))}` | `{pct(float(item['recent_30d_total_return']))}` |"
        )
    return output


def render_markdown(summary: pd.DataFrame, monthly: pd.DataFrame, quality: dict[str, Any], args: argparse.Namespace) -> str:
    paper = summary.loc[summary["paper_candidate_pass"].eq(True)].sort_values("score", ascending=False)
    enough_sample = summary.loc[summary["full_trades"].ge(MIN_PAPER_TRADES)].sort_values("score", ascending=False)
    nearest = paper.head(20) if not paper.empty else enough_sample.head(20)
    if nearest.empty:
        nearest = summary.sort_values("score", ascending=False).head(20)
    high_win = summary.loc[summary["full_trades"].ge(MIN_PAPER_TRADES)].sort_values(
        ["full_win_rate", "full_profit_factor", "score"], ascending=[False, False, False]
    )
    frequency_rows = []
    for min_tpd in (1.0, 2.0, 3.0, 5.0, 8.0):
        subset = summary.loc[summary["full_trades_per_day"] >= min_tpd]
        best_ann = float(subset["full_annualized_multiple"].max()) if not subset.empty else 0.0
        best_pf = float(subset["full_profit_factor"].max()) if not subset.empty else 0.0
        frequency_rows.append((min_tpd, len(subset), best_ann, best_pf))

    lines = [
        "# HYPE 1m MA Pullback Scalp executable search 2026-06-26",
        "",
        "Family id: `HYPE-1M-MA-Pullback-Scalp`",
        "",
        "目标：把“两条均线剥头皮”拆成可执行规则：慢 EMA 判断趋势，快 EMA 判断价格波浪/回调，HH/HL 或 LL/LH 判断结构，回调结束后下一根 open 入场，入场即挂固定 TP/SL，并在固定 K 数内超时退出。",
        "",
        "## 数据质量",
        "",
        f"- Normalized OHLCV: `{quality['normalized_file_count']}` 个日分区，`{quality['rows']}` 根 K。",
        f"- Raw OHLCV: `{quality['raw_ohlcv_file_count']}` 个日分区，`{quality['raw_rows']}` 根 K。",
        f"- 时间范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 连续性：expected `{quality['expected_bars']}`，missing `{quality['missing_bars']}`，duplicate `{quality['duplicate_ts']}`。",
        f"- `is_closed`：`{quality['is_closed_counts']}`。",
        f"- `source`：`{quality['source_counts']}`。",
        f"- OHLC/VWAP/volume hard violations：`{quality['ohlcv_violations']}`。",
        f"- Raw/normalized alignment：`{quality['raw_normalized_alignment']}`。",
        "",
        "## 执行模型",
        "",
        "- 信号只使用已收盘 `1m` K；下一根 K 的 open 入场。",
        "- 入场后立即有固定 TP/SL bracket；保护止损从第一根持仓 K 开始有效。",
        "- 同一根 K 同时可能触及 TP/SL 时，保守按止损先成交。",
        "- stop/target 被 open 穿越时按 open 市价成交，不按旧 stop/target 价成交。",
        "- 超时退出使用下一根 open，不使用不可保证的 bar close。",
        f"- 成本：fee `{FEE_BPS_PER_FILL:.2f} bps/fill`，entry slippage `{ENTRY_SLIPPAGE_BPS:.2f} bps`，exit slippage `{EXIT_SLIPPAGE_BPS:.2f} bps`。",
        "",
        "## 搜索规模",
        "",
        f"- curated + random configs: `{len(summary)}`。",
        f"- random seed: `{args.seed}`。",
        "- 搜索维度：trigger style、fast/slow EMA、结构窗口、平台窗口、结构突破幅度、均线斜率、回调触碰/收回阈值、ATR/RVOL/ADX/离慢线距离过滤、TP/SL、max-hold、cooldown、long/short/both。",
        "",
        "## 候选门槛",
        "",
        f"- paper candidate gate: trades >= `{MIN_PAPER_TRADES}`，full return > `0`，ann > `1x`，win >= `{MIN_PAPER_WIN_RATE:.0%}`，PF >= `{MIN_PAPER_PROFIT_FACTOR}`，maxDD >= `{MAX_PAPER_DRAWDOWN:.0%}`，VAL/FWD PF >= `1`，VAL/FWD/recent returns 不得明显失血。",
        f"- 通过 paper candidate gate：`{len(paper)}`。",
        "",
    ]
    if paper.empty:
        lines.append("没有配置通过完整 paper candidate gate。")
    else:
        lines.append("通过 paper candidate gate 的配置如下；它们仍然只能进入 paper audit，不能直接实盘。")
        lines.extend(markdown_table(paper, limit=15))

    lines.extend(["", "## 最接近目标的配置", "", *markdown_table(nearest, limit=15), ""])
    if not high_win.empty:
        lines.extend(["## 样本数足够时胜率最高的配置", "", *markdown_table(high_win, limit=10), ""])

    lines.extend(["## 频率压力测试", "", "| 最低 trades/day | 配置数 | 最高全样本年化 | 最高 PF |", "| ---: | ---: | ---: | ---: |"])
    for min_tpd, count, best_ann, best_pf in frequency_rows:
        lines.append(f"| `{min_tpd:.1f}` | `{count}` | `{mult(best_ann)}` | `{num(best_pf)}` |")

    lines.extend(["", "## 月度提示", ""])
    if not nearest.empty and not monthly.empty:
        top_name = str(nearest.iloc[0]["name"])
        top_monthly = monthly.loc[monthly["name"].eq(top_name)].copy()
        negative_months = int((top_monthly["total_return"] < 0).sum()) if not top_monthly.empty else 0
        worst = top_monthly.sort_values("total_return").head(1).to_dict(orient="records") if not top_monthly.empty else []
        lines.append(f"- top score `{top_name}` 的负收益月份数：`{negative_months}`。")
        if worst:
            item = worst[0]
            lines.append(
                f"- 最差月份 `{item['month']}`：return `{pct(float(item['total_return']))}`，PF `{num(float(item['profit_factor']))}`，trades `{int(item['trades'])}`。"
            )

    lines.extend(["", "## 结论", ""])
    if paper.empty:
        lines.append("本轮不能把这套 MA 回调剥头皮策略提升为 paper-live 或 live 候选；可以保留最佳配置继续做机制诊断，但不能宣称已盈利可实盘。")
    else:
        lines.append("本轮找到可进入 paper audit 的盈利配置，但还不能真实资金上线；下一步必须做参数邻域、逐笔路径图、paper runner 和重启/订单维护审计。")

    lines.extend(
        [
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/1m-ma-pullback-scalp/scripts/research_hype_1m_ma_pullback_scalp.py`",
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

    configs = build_configs(args.max_random_configs, args.seed)
    spans = sorted({span for cfg in configs for span in (cfg.fast_ma, cfg.slow_ma)})
    structure_windows = sorted({cfg.structure_window for cfg in configs})
    platform_windows = sorted({cfg.platform_window for cfg in configs})

    frame_raw, quality = validate_hype_1m()
    frame = add_features(frame_raw, spans, structure_windows, platform_windows)
    slices = validation_slices(frame)
    cfg_by_name = {cfg.name: cfg for cfg in configs}

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    best_trades: list[Trade] = []
    best_score = -float("inf")
    best_row: dict[str, Any] | None = None

    for idx, cfg in enumerate(configs, start=1):
        row, per_slices, trades = row_for_config(frame, cfg, slices)
        summary_rows.append(row)
        slice_rows.extend(per_slices)
        if float(row["score"]) > best_score:
            best_score = float(row["score"])
            best_trades = trades
            best_row = row
        if args.progress_every and idx % args.progress_every == 0:
            progress_row = best_row if best_row is not None else row
            print(
                f"[{idx}/{len(configs)}] best={progress_row['name']} "
                f"score={float(progress_row['score']):.2f} "
                f"ann={float(progress_row['full_annualized_multiple']):.3f} "
                f"pf={float(progress_row['full_profit_factor']):.3f} "
                f"trades={int(progress_row['full_trades'])}"
            )

    summary = pd.DataFrame(summary_rows).sort_values("score", ascending=False).reset_index(drop=True)
    slices_frame = pd.DataFrame(slice_rows)
    top_names = [str(name) for name in summary.head(args.top_keep)["name"].tolist()]
    monthly = pd.DataFrame(monthly_rows(frame, cfg_by_name, top_names))

    summary.to_csv(SUMMARY_PATH, index=False)
    slices_frame.to_csv(SLICES_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    if best_trades:
        trades_to_frame(best_trades).to_csv(TOP_TRADES_PATH, index=False)
    else:
        pd.DataFrame().to_csv(TOP_TRADES_PATH, index=False)

    payload = {
        "family_id": "HYPE-1M-MA-Pullback-Scalp",
        "run_date": RUN_DATE,
        "quality": quality,
        "cost_model": {
            "fee_bps_per_fill": FEE_BPS_PER_FILL,
            "entry_slippage_bps": ENTRY_SLIPPAGE_BPS,
            "exit_slippage_bps": EXIT_SLIPPAGE_BPS,
        },
        "args": vars(args),
        "config_count": int(len(configs)),
        "paper_candidate_pass_count": int(summary["paper_candidate_pass"].sum()),
        "top_rows": summary.head(40).to_dict(orient="records"),
        "paths": {
            "summary": str(SUMMARY_PATH),
            "slices": str(SLICES_PATH),
            "monthly": str(MONTHLY_PATH),
            "top_trades": str(TOP_TRADES_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default))
    MARKDOWN_PATH.write_text(render_markdown(summary, monthly, quality, args))
    print(f"wrote {MARKDOWN_PATH}")
    print(f"paper_candidate_pass_count={payload['paper_candidate_pass_count']}")
    if not summary.empty:
        top = summary.iloc[0]
        print(
            "top="
            f"{top['name']} ann={float(top['full_annualized_multiple']):.3f} "
            f"ret={float(top['full_total_return']):.3f} pf={float(top['full_profit_factor']):.3f} "
            f"win={float(top['full_win_rate']):.3f} dd={float(top['full_max_dd']):.3f} "
            f"trades={int(top['full_trades'])}"
        )


if __name__ == "__main__":
    main()
