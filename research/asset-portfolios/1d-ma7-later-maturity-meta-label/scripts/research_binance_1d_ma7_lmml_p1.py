from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-later-maturity-meta-label"
FEATURE_DIR = ROOT / "data/features/binance_1d_ma7_rsi6_dapml_p0"
DEFAULT_OUTPUT_DIR = FAMILY_DIR / "artifacts/p1_development_2026-08-10"
SHARED_KERNEL_PATH = (
    ROOT
    / "research/_shared-kernels/binance-ma7-root-data/v1/engine.py"
)
EXPECTED_SHARED_KERNEL_SHA256 = (
    "3d7c6d295568b96627a4b6aa4efad0fc7fdc8a53503f9f4fa55922c7069bfa3d"
)
if hashlib.sha256(SHARED_KERNEL_PATH.read_bytes()).hexdigest() != (
    EXPECTED_SHARED_KERNEL_SHA256
):
    raise RuntimeError("Shared Binance MA7 root-data kernel SHA256 mismatch")
SHARED_SPEC = importlib.util.spec_from_file_location(
    "binance_ma7_root_data_v1_lmml",
    SHARED_KERNEL_PATH,
)
if SHARED_SPEC is None or SHARED_SPEC.loader is None:
    raise ImportError(f"Cannot load shared kernel: {SHARED_KERNEL_PATH}")
shared = importlib.util.module_from_spec(SHARED_SPEC)
sys.modules[SHARED_SPEC.name] = shared
SHARED_SPEC.loader.exec_module(shared)

ASSETS = {
    "BTC": "btcusdt",
    "ETH": "ethusdt",
    "BNB": "bnbusdt",
    "SOL": "solusdt",
    "TRX": "trxusdt",
}
DEVELOPMENT_END_EXCLUSIVE = pd.Timestamp("2025-05-31T00:00:00Z")
FEE_RATE = 0.001
BASE_SLIPPAGE = 0.0004
MAIN_SLIPPAGE = 0.0008
LEVERAGE = 0.25
ROOT_MAX_AGE_DAYS = 5
PROBE_MAX_HOLD_DAYS = 5
EMBARGO_DAYS = 5
SEED = 20260810
BOOTSTRAP_SAMPLES = 5_000
C_GRID = (0.03, 0.10, 0.30, 1.00)
THRESHOLD_GRID = (0.50, 0.55, 0.60, 0.65, 0.70)
ROUTES = ("combined", "long_only", "short_only")

FEATURES = (
    "is_short",
    "maturity_age_days",
    "aligned_distance_atr",
    "aligned_slope_atr",
    "cross_aligned_distance_atr",
    "cross_aligned_slope_atr",
    "distance_change_atr",
    "slope_change_atr",
    "aligned_return_1_atr",
    "aligned_return_3_atr",
    "aligned_return_5_atr",
    "aligned_return_10_atr",
    "aligned_efficiency_5",
    "aligned_efficiency_7",
    "aligned_efficiency_14",
    "atr7_pct",
    "atr7_atr20",
    "aligned_body_atr",
    "range_atr",
    "rejection_wick_atr",
    "opposition_wick_atr",
    "aligned_close_location",
    "aligned_rsi6",
    "aligned_rsi6_delta_1",
    "directional_rsi_extreme_5",
    "counter_rsi_extreme_5",
    "volume_ratio_20",
    "quote_volume_ratio_20",
    "trade_count_ratio_20",
    "hourly_disp_6_atr",
    "hourly_disp_24_atr",
    "hourly_disp_72_atr",
    "hourly_direction_fraction_24",
    "hourly_direction_fraction_72",
    "hourly_signed_efficiency_24",
    "hourly_signed_efficiency_72",
    "hourly_directional_rv_balance_24",
    "hourly_aligned_close_location_24",
    "hourly_impulse_6_vs_18_atr",
    "aligned_funding_carry_24h",
    "aligned_funding_carry_72h",
    "aligned_market_return_1d",
    "aligned_market_return_3d",
    "market_median_atr_pct",
    "aligned_market_breadth",
    "relative_strength_1d",
    "relative_strength_3d",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build pre-HYPE five-asset V6-style maturity events and run frozen "
            "nested LOAO/time meta-label diagnostics."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def atomic_write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def input_paths(slug: str) -> dict[str, Path]:
    return {
        "daily": FEATURE_DIR / f"{slug}_perp_1d.parquet",
        "hourly": FEATURE_DIR / f"{slug}_perp_1h.parquet",
        "funding": FEATURE_DIR / f"{slug}_perp_funding_mark.parquet",
    }


def wilder_rsi(close: pd.Series, period: int = 6) -> pd.Series:
    values = close.to_numpy(dtype="float64")
    result = np.full(len(values), np.nan, dtype="float64")
    if len(values) <= period:
        return pd.Series(result, index=close.index)
    deltas = np.diff(values)
    gains = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)
    avg_gain = float(gains[:period].mean())
    avg_loss = float(losses[:period].mean())

    def value(gain: float, loss: float) -> float:
        if gain == 0.0 and loss == 0.0:
            return 50.0
        if loss == 0.0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    result[period] = value(avg_gain, avg_loss)
    for index in range(period + 1, len(values)):
        delta_index = index - 1
        avg_gain = (avg_gain * (period - 1) + gains[delta_index]) / period
        avg_loss = (avg_loss * (period - 1) + losses[delta_index]) / period
        result[index] = value(avg_gain, avg_loss)
    return pd.Series(result, index=close.index)


def add_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy().sort_values("ts").reset_index(drop=True)
    close = result["close"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            result["high"].astype(float) - result["low"].astype(float),
            (result["high"].astype(float) - previous_close).abs(),
            (result["low"].astype(float) - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["sma7"] = close.rolling(7, min_periods=7).mean()
    result["atr7"] = true_range.rolling(7, min_periods=7).mean()
    result["atr20"] = true_range.rolling(20, min_periods=20).mean()
    result["rsi6"] = wilder_rsi(close, 6)
    result["rsi6_delta_1"] = result["rsi6"].diff()
    result["rsi6_min_5"] = result["rsi6"].rolling(5, min_periods=5).min()
    result["rsi6_max_5"] = result["rsi6"].rolling(5, min_periods=5).max()
    result["return_pct_1"] = close.pct_change(1)
    result["return_pct_3"] = close.pct_change(3)
    for horizon in (1, 3, 5, 10):
        result[f"return_{horizon}_atr"] = (
            close - close.shift(horizon)
        ) / result["atr7"]
    absolute_change = close.diff().abs()
    for horizon in (5, 7, 14):
        path = absolute_change.rolling(horizon, min_periods=horizon).sum()
        result[f"efficiency_{horizon}"] = (close - close.shift(horizon)) / path
    result["atr7_pct"] = result["atr7"] / close
    result["atr7_atr20"] = result["atr7"] / result["atr20"]
    result["body_atr"] = (
        result["close"].astype(float) - result["open"].astype(float)
    ) / result["atr7"]
    candle_range = result["high"].astype(float) - result["low"].astype(float)
    result["range_atr"] = candle_range / result["atr7"]
    result["upper_wick_atr"] = (
        result["high"].astype(float)
        - np.maximum(result["open"].astype(float), result["close"].astype(float))
    ) / result["atr7"]
    result["lower_wick_atr"] = (
        np.minimum(result["open"].astype(float), result["close"].astype(float))
        - result["low"].astype(float)
    ) / result["atr7"]
    result["close_location"] = np.where(
        candle_range.gt(0.0),
        (result["close"].astype(float) - result["low"].astype(float))
        / candle_range,
        0.5,
    )
    for column in ("volume", "quote_volume", "trade_count"):
        median = (
            result[column].astype(float).rolling(20, min_periods=20).median()
        )
        result[f"{column}_ratio_20"] = result[column].astype(float) / median
    return result


def _relative_mismatch(left: pd.Series, right: pd.Series) -> float:
    denominator = np.maximum(
        1.0,
        np.maximum(
            np.abs(left.to_numpy(dtype="float64")),
            np.abs(right.to_numpy(dtype="float64")),
        ),
    )
    return float(
        np.max(
            np.abs(
                left.to_numpy(dtype="float64")
                - right.to_numpy(dtype="float64")
            )
            / denominator
        )
    )


def load_asset_inputs(
    asset: str,
    slug: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    paths = input_paths(slug)
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
    daily = pd.read_parquet(
        paths["daily"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    hourly = pd.read_parquet(
        paths["hourly"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    funding = pd.read_parquet(
        paths["funding"],
        filters=[("ts", "<", DEVELOPMENT_END_EXCLUSIVE.to_pydatetime())],
    )
    for frame in (daily, hourly, funding):
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame.sort_values("ts", inplace=True)
        frame.reset_index(drop=True, inplace=True)
        if frame.empty or frame["ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
            raise RuntimeError(f"{asset} crossed development boundary")
    funding["funding_nominal_ts"] = pd.to_datetime(
        funding["funding_nominal_ts"], utc=True
    )
    if daily["ts"].duplicated().any() or hourly["ts"].duplicated().any():
        raise RuntimeError(f"{asset} OHLCV contains duplicate timestamps")
    if funding["funding_nominal_ts"].duplicated().any():
        raise RuntimeError(f"{asset} funding contains duplicate nominal timestamps")
    expected_hourly = pd.date_range(
        hourly["ts"].min(), hourly["ts"].max(), freq="1h"
    )
    missing_hourly = expected_hourly.difference(pd.DatetimeIndex(hourly["ts"]))
    if len(missing_hourly):
        raise RuntimeError(f"{asset} has {len(missing_hourly)} missing hourly bars")
    expected_daily = pd.date_range(daily["ts"].min(), daily["ts"].max(), freq="1D")
    missing_daily = expected_daily.difference(pd.DatetimeIndex(daily["ts"]))
    if len(missing_daily):
        raise RuntimeError(f"{asset} has {len(missing_daily)} missing daily bars")
    funding_gap_hours = (
        funding["funding_nominal_ts"].diff().dt.total_seconds().div(3600.0)
    )
    invalid_funding = funding_gap_hours.dropna().loc[
        funding_gap_hours.dropna().le(0.0)
        | funding_gap_hours.dropna().gt(8.0)
        | np.mod(funding_gap_hours.dropna(), 1.0).ne(0.0)
    ]
    if len(invalid_funding):
        raise RuntimeError(f"{asset} has invalid funding intervals")

    hourly_check = hourly.copy()
    hourly_check["day"] = hourly_check["ts"].dt.floor("1D")
    grouped = hourly_check.groupby("day", sort=True)
    sizes = grouped.size()
    complete_days = sizes.index[sizes.eq(24)]
    rebuilt = pd.DataFrame(
        {
            "ts": complete_days,
            "open_rebuilt": grouped["open"].first().reindex(complete_days).to_numpy(),
            "high_rebuilt": grouped["high"].max().reindex(complete_days).to_numpy(),
            "low_rebuilt": grouped["low"].min().reindex(complete_days).to_numpy(),
            "close_rebuilt": grouped["close"].last().reindex(complete_days).to_numpy(),
            "volume_rebuilt": grouped["volume"].sum().reindex(complete_days).to_numpy(),
            "quote_volume_rebuilt": (
                grouped["quote_volume"].sum().reindex(complete_days).to_numpy()
            ),
            "trade_count_rebuilt": (
                grouped["trade_count"].sum().reindex(complete_days).to_numpy()
            ),
        }
    )
    joined = daily.merge(rebuilt, on="ts", how="left", validate="one_to_one")
    if joined.filter(like="_rebuilt").isna().any().any():
        raise RuntimeError(f"{asset} daily rows lack complete 24h source")
    mismatch = max(
        _relative_mismatch(joined[column], joined[f"{column}_rebuilt"])
        for column in (
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_volume",
            "trade_count",
        )
    )
    if mismatch > 1e-12:
        raise RuntimeError(f"{asset} daily/hourly mismatch {mismatch}")
    quality = {
        "daily_rows": int(len(daily)),
        "daily_start": daily["ts"].min(),
        "daily_end": daily["ts"].max(),
        "hourly_rows": int(len(hourly)),
        "hourly_start": hourly["ts"].min(),
        "hourly_end": hourly["ts"].max(),
        "funding_rows": int(len(funding)),
        "funding_start": funding["funding_nominal_ts"].min(),
        "funding_end": funding["funding_nominal_ts"].max(),
        "missing_hourly": 0,
        "missing_daily": 0,
        "daily_rebuild_max_relative_mismatch": mismatch,
        "input_sha256": {
            name: sha256_path(path) for name, path in paths.items()
        },
    }
    return add_indicators(daily), hourly, funding, quality


def raw_cross(daily: pd.DataFrame, index: int) -> int:
    if index < 1:
        return 0
    values = (
        float(daily.at[index - 1, "close"]),
        float(daily.at[index - 1, "sma7"]),
        float(daily.at[index, "close"]),
        float(daily.at[index, "sma7"]),
    )
    if not all(math.isfinite(value) for value in values):
        return 0
    prior_close, prior_ma, close, ma = values
    if prior_close <= prior_ma and close > ma:
        return 1
    if prior_close >= prior_ma and close < ma:
        return -1
    return 0


def maturity_criteria(
    daily: pd.DataFrame,
    index: int,
    side: int,
) -> dict[str, Any]:
    lookback = 1 if side > 0 else 2
    buffer_threshold = 0.0 if side > 0 else 0.10
    if index < lookback:
        return {"finite": False}
    values = (
        float(daily.at[index, "close"]),
        float(daily.at[index, "sma7"]),
        float(daily.at[index, "atr7"]),
        float(daily.at[index - lookback, "sma7"]),
    )
    if not all(math.isfinite(value) for value in values) or values[2] <= 0.0:
        return {"finite": False}
    close, ma, atr, previous_ma = values
    distance = side * (close - ma) / atr
    slope = side * (ma - previous_ma) / atr
    return {
        "finite": True,
        "distance_atr": float(distance),
        "slope_atr": float(slope),
        "buffer_threshold": buffer_threshold,
        "slope_threshold": 0.02,
        "buffer_pass": bool(distance > buffer_threshold),
        "slope_pass": bool(slope >= 0.02),
    }


def intraday_features(
    hourly: pd.DataFrame,
    *,
    signal_ts: pd.Timestamp,
    side: int,
    atr: float,
) -> dict[str, float] | None:
    end = signal_ts + pd.Timedelta(days=1)
    timestamps = pd.DatetimeIndex(hourly["ts"])
    right = int(timestamps.searchsorted(end, side="left"))
    if right < 72:
        return None
    window = hourly.iloc[right - 72 : right].copy()
    if (
        pd.Timestamp(window.iloc[0]["ts"]) != end - pd.Timedelta(hours=72)
        or pd.Timestamp(window.iloc[-1]["ts"]) != end - pd.Timedelta(hours=1)
    ):
        return None

    def horizon_values(hours: int) -> tuple[float, float, float]:
        sample = window.iloc[-hours:]
        first_open = float(sample.iloc[0]["open"])
        last_close = float(sample.iloc[-1]["close"])
        path = np.concatenate(
            [
                np.asarray([first_open], dtype="float64"),
                sample["close"].to_numpy(dtype="float64"),
            ]
        )
        path_length = float(np.abs(np.diff(path)).sum())
        displacement = side * (last_close - first_open) / atr
        direction_fraction = float(
            np.mean(
                side
                * (
                    sample["close"].to_numpy(dtype="float64")
                    - sample["open"].to_numpy(dtype="float64")
                )
                > 0.0
            )
        )
        efficiency = (
            side * (last_close - first_open) / path_length
            if path_length > 0.0
            else 0.0
        )
        return float(displacement), direction_fraction, float(efficiency)

    disp6, _, _ = horizon_values(6)
    disp24, fraction24, efficiency24 = horizon_values(24)
    disp72, fraction72, efficiency72 = horizon_values(72)
    day = window.iloc[-24:]
    hourly_returns = (
        day["close"].to_numpy(dtype="float64")
        / day["open"].to_numpy(dtype="float64")
        - 1.0
    )
    aligned_returns = side * hourly_returns
    favorable_rv = float(np.square(hourly_returns[aligned_returns > 0.0]).sum())
    adverse_rv = float(np.square(hourly_returns[aligned_returns < 0.0]).sum())
    total_rv = favorable_rv + adverse_rv
    rv_balance = (
        (favorable_rv - adverse_rv) / total_rv if total_rv > 0.0 else 0.0
    )
    high = float(day["high"].max())
    low = float(day["low"].min())
    close = float(day.iloc[-1]["close"])
    location = (close - low) / (high - low) if high > low else 0.5
    aligned_location = location if side > 0 else 1.0 - location
    recent = day.iloc[-6:]
    prior = day.iloc[:18]
    recent_per_hour = (
        float(recent.iloc[-1]["close"]) - float(recent.iloc[0]["open"])
    ) / 6.0
    prior_per_hour = (
        float(prior.iloc[-1]["close"]) - float(prior.iloc[0]["open"])
    ) / 18.0
    impulse = side * (recent_per_hour - prior_per_hour) / atr
    return {
        "hourly_disp_6_atr": disp6,
        "hourly_disp_24_atr": disp24,
        "hourly_disp_72_atr": disp72,
        "hourly_direction_fraction_24": fraction24,
        "hourly_direction_fraction_72": fraction72,
        "hourly_signed_efficiency_24": efficiency24,
        "hourly_signed_efficiency_72": efficiency72,
        "hourly_directional_rv_balance_24": rv_balance,
        "hourly_aligned_close_location_24": float(aligned_location),
        "hourly_impulse_6_vs_18_atr": float(impulse),
    }


def funding_context_features(
    funding: pd.DataFrame,
    *,
    signal_ts: pd.Timestamp,
    side: int,
) -> dict[str, float]:
    end = signal_ts + pd.Timedelta(days=1)
    nominal = pd.DatetimeIndex(funding["funding_nominal_ts"])
    rates = funding["funding_rate"].to_numpy(dtype="float64")

    def carry(hours: int) -> float:
        left = int(
            nominal.searchsorted(end - pd.Timedelta(hours=hours), side="left")
        )
        right = int(nominal.searchsorted(end, side="left"))
        return float(-side * rates[left:right].sum())

    return {
        "aligned_funding_carry_24h": carry(24),
        "aligned_funding_carry_72h": carry(72),
    }


def market_features(
    dailies: dict[str, pd.DataFrame],
    *,
    asset: str,
    signal_ts: pd.Timestamp,
    side: int,
    asset_return_1d: float,
    asset_return_3d: float,
) -> dict[str, float] | None:
    rows: list[pd.Series] = []
    for other_asset, frame in dailies.items():
        if other_asset == asset:
            continue
        matches = frame.index[frame["ts"].eq(signal_ts)]
        if len(matches) != 1:
            continue
        row = frame.loc[int(matches[0])]
        values = (
            float(row["return_pct_1"]),
            float(row["return_pct_3"]),
            float(row["atr7_pct"]),
        )
        if all(math.isfinite(value) for value in values):
            rows.append(row)
    if len(rows) < 3:
        return None
    return_1 = np.asarray([float(row["return_pct_1"]) for row in rows])
    return_3 = np.asarray([float(row["return_pct_3"]) for row in rows])
    atr_pct = np.asarray([float(row["atr7_pct"]) for row in rows])
    median_1 = float(np.median(return_1))
    median_3 = float(np.median(return_3))
    breadth = float(np.mean(return_1 > 0.0))
    return {
        "aligned_market_return_1d": float(side * median_1),
        "aligned_market_return_3d": float(side * median_3),
        "market_median_atr_pct": float(np.median(atr_pct)),
        "aligned_market_breadth": float(side * (2.0 * breadth - 1.0)),
        "relative_strength_1d": float(side * (asset_return_1d - median_1)),
        "relative_strength_3d": float(side * (asset_return_3d - median_3)),
    }


def find_probe_exit_index(
    daily: pd.DataFrame,
    *,
    entry_index: int,
    side: int,
) -> tuple[int, str] | None:
    max_exit = entry_index + PROBE_MAX_HOLD_DAYS
    if max_exit >= len(daily):
        return None
    for signal_index in range(entry_index, max_exit):
        close = float(daily.at[signal_index, "close"])
        ma = float(daily.at[signal_index, "sma7"])
        if not all(math.isfinite(value) for value in (close, ma)):
            return signal_index + 1, "nonfinite"
        if side * (close - ma) <= 0.0:
            return signal_index + 1, "ma7_recross"
    return max_exit, "max_5d"


def trade_outcome(
    daily: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    maturity_index: int,
    side: int,
    slippage: float,
    include_funding: bool,
    lag_days: int = 0,
) -> dict[str, Any] | None:
    entry_index = maturity_index + 1 + lag_days
    if entry_index >= len(daily):
        return None
    prior_close = float(daily.at[entry_index - 1, "close"])
    prior_ma = float(daily.at[entry_index - 1, "sma7"])
    if (
        not all(math.isfinite(value) for value in (prior_close, prior_ma))
        or side * (prior_close - prior_ma) <= 0.0
    ):
        return None
    exit_result = find_probe_exit_index(
        daily,
        entry_index=entry_index,
        side=side,
    )
    if exit_result is None:
        return None
    exit_index, exit_reason = exit_result
    entry_ts = pd.Timestamp(daily.at[entry_index, "ts"])
    exit_ts = pd.Timestamp(daily.at[exit_index, "ts"])
    entry_reference = float(daily.at[entry_index, "open"])
    exit_reference = float(daily.at[exit_index, "open"])
    entry_fill = entry_reference * (1.0 + side * slippage)
    exit_fill = exit_reference * (1.0 - side * slippage)
    gross_return = side * (exit_fill - entry_fill) / entry_fill
    funding_return = 0.0
    funding_events = 0
    if include_funding:
        timestamps = pd.DatetimeIndex(funding["ts"])
        left = int(timestamps.searchsorted(entry_ts, side="right"))
        right = int(timestamps.searchsorted(exit_ts, side="left"))
        window = funding.iloc[left:right]
        funding_return = float(
            (
                -side
                * window["funding_rate"].to_numpy(dtype="float64")
                * window["mark_price"].to_numpy(dtype="float64")
                / entry_fill
            ).sum()
        )
        funding_events = int(len(window))
    entry_fee = FEE_RATE
    exit_fee = FEE_RATE * exit_fill / entry_fill
    direct_net_return = LEVERAGE * (
        gross_return + funding_return - entry_fee - exit_fee
    )
    return {
        "entry_index": entry_index,
        "entry_ts": entry_ts,
        "entry_reference": entry_reference,
        "entry_fill": entry_fill,
        "exit_index": exit_index,
        "exit_ts": exit_ts,
        "exit_reference": exit_reference,
        "exit_fill": exit_fill,
        "exit_reason": exit_reason,
        "gross_return": float(LEVERAGE * gross_return),
        "funding_return": float(LEVERAGE * funding_return),
        "funding_events": funding_events,
        "fee_return": float(LEVERAGE * (entry_fee + exit_fee)),
        "direct_net_return": float(direct_net_return),
    }


def event_features(
    dailies: dict[str, pd.DataFrame],
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
    *,
    asset: str,
    cross_index: int,
    maturity_index: int,
    side: int,
    cross_criteria: dict[str, Any],
    maturity: dict[str, Any],
) -> dict[str, float] | None:
    daily = dailies[asset]
    signal_ts = pd.Timestamp(daily.at[maturity_index, "ts"])
    atr = float(daily.at[maturity_index, "atr7"])
    close_value = float(daily.at[maturity_index, "close"])
    high = float(daily.at[maturity_index, "high"])
    low = float(daily.at[maturity_index, "low"])
    candle_range = high - low
    is_long = side > 0
    rsi = float(daily.at[maturity_index, "rsi6"])
    rsi_delta = float(daily.at[maturity_index, "rsi6_delta_1"])
    rsi_min = float(daily.at[maturity_index, "rsi6_min_5"])
    rsi_max = float(daily.at[maturity_index, "rsi6_max_5"])
    asset_return_1d = float(daily.at[maturity_index, "return_pct_1"])
    asset_return_3d = float(daily.at[maturity_index, "return_pct_3"])
    values: dict[str, float] = {
        "is_short": float(side < 0),
        "maturity_age_days": float(maturity_index - cross_index),
        "aligned_distance_atr": float(maturity["distance_atr"]),
        "aligned_slope_atr": float(maturity["slope_atr"]),
        "cross_aligned_distance_atr": float(cross_criteria["distance_atr"]),
        "cross_aligned_slope_atr": float(cross_criteria["slope_atr"]),
        "distance_change_atr": float(
            maturity["distance_atr"] - cross_criteria["distance_atr"]
        ),
        "slope_change_atr": float(
            maturity["slope_atr"] - cross_criteria["slope_atr"]
        ),
        "aligned_return_1_atr": float(
            side * daily.at[maturity_index, "return_1_atr"]
        ),
        "aligned_return_3_atr": float(
            side * daily.at[maturity_index, "return_3_atr"]
        ),
        "aligned_return_5_atr": float(
            side * daily.at[maturity_index, "return_5_atr"]
        ),
        "aligned_return_10_atr": float(
            side * daily.at[maturity_index, "return_10_atr"]
        ),
        "aligned_efficiency_5": float(
            side * daily.at[maturity_index, "efficiency_5"]
        ),
        "aligned_efficiency_7": float(
            side * daily.at[maturity_index, "efficiency_7"]
        ),
        "aligned_efficiency_14": float(
            side * daily.at[maturity_index, "efficiency_14"]
        ),
        "atr7_pct": float(daily.at[maturity_index, "atr7_pct"]),
        "atr7_atr20": float(daily.at[maturity_index, "atr7_atr20"]),
        "aligned_body_atr": float(
            side * daily.at[maturity_index, "body_atr"]
        ),
        "range_atr": float(daily.at[maturity_index, "range_atr"]),
        "rejection_wick_atr": float(
            daily.at[
                maturity_index,
                "lower_wick_atr" if is_long else "upper_wick_atr",
            ]
        ),
        "opposition_wick_atr": float(
            daily.at[
                maturity_index,
                "upper_wick_atr" if is_long else "lower_wick_atr",
            ]
        ),
        "aligned_close_location": float(
            (close_value - low) / candle_range
            if is_long and candle_range > 0.0
            else (high - close_value) / candle_range
            if candle_range > 0.0
            else 0.5
        ),
        "aligned_rsi6": float(rsi if is_long else 100.0 - rsi),
        "aligned_rsi6_delta_1": float(side * rsi_delta),
        "directional_rsi_extreme_5": float(
            rsi_max if is_long else 100.0 - rsi_min
        ),
        "counter_rsi_extreme_5": float(
            rsi_min if is_long else 100.0 - rsi_max
        ),
        "volume_ratio_20": float(
            daily.at[maturity_index, "volume_ratio_20"]
        ),
        "quote_volume_ratio_20": float(
            daily.at[maturity_index, "quote_volume_ratio_20"]
        ),
        "trade_count_ratio_20": float(
            daily.at[maturity_index, "trade_count_ratio_20"]
        ),
    }
    hourly_values = intraday_features(
        hourly,
        signal_ts=signal_ts,
        side=side,
        atr=atr,
    )
    market_values = market_features(
        dailies,
        asset=asset,
        signal_ts=signal_ts,
        side=side,
        asset_return_1d=asset_return_1d,
        asset_return_3d=asset_return_3d,
    )
    if hourly_values is None or market_values is None:
        return None
    values.update(hourly_values)
    values.update(
        funding_context_features(
            funding,
            signal_ts=signal_ts,
            side=side,
        )
    )
    values.update(market_values)
    if tuple(values) != FEATURES:
        missing = sorted(set(FEATURES).difference(values))
        extra = sorted(set(values).difference(FEATURES))
        raise RuntimeError(f"Feature contract mismatch missing={missing} extra={extra}")
    if not all(math.isfinite(value) for value in values.values()):
        return None
    return values


def build_events(
    dailies: dict[str, pd.DataFrame],
    hourlies: dict[str, pd.DataFrame],
    fundings: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    records: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    for asset in ASSETS:
        daily = dailies[asset]
        hourly = hourlies[asset]
        funding = fundings[asset]
        counts: Counter[str] = Counter()
        local_root = 0
        for cross_index in range(20, len(daily)):
            side = shared.raw_cross(daily, cross_index)
            if not side:
                continue
            counts["raw_crosses"] += 1
            local_root += 1
            cross_criteria = maturity_criteria(daily, cross_index, side)
            if not cross_criteria.get("finite"):
                counts["cross_nonfinite"] += 1
                continue
            maturity_index: int | None = None
            maturity: dict[str, Any] | None = None
            cancellation = "MAX_AGE"
            window_end = min(
                len(daily) - 1,
                cross_index + ROOT_MAX_AGE_DAYS,
            )
            for index in range(cross_index, window_end + 1):
                close = float(daily.at[index, "close"])
                ma = float(daily.at[index, "sma7"])
                if not all(math.isfinite(value) for value in (close, ma)):
                    cancellation = "NONFINITE"
                    break
                if index > cross_index and side * (close - ma) <= 0.0:
                    cancellation = "RECROSS"
                    break
                criteria = maturity_criteria(daily, index, side)
                if (
                    maturity_index is None
                    and criteria.get("finite")
                    and bool(criteria["buffer_pass"])
                    and bool(criteria["slope_pass"])
                ):
                    maturity_index = index
                    maturity = criteria
                    break
            if maturity_index is None or maturity is None:
                counts[f"no_maturity_{cancellation.lower()}"] += 1
                continue
            counts["matured"] += 1
            counts[
                "same_day_maturity"
                if maturity_index == cross_index
                else "later_maturity"
            ] += 1
            main = trade_outcome(
                daily,
                funding,
                maturity_index=maturity_index,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=True,
            )
            base = trade_outcome(
                daily,
                funding,
                maturity_index=maturity_index,
                side=side,
                slippage=BASE_SLIPPAGE,
                include_funding=True,
            )
            funding_off = trade_outcome(
                daily,
                funding,
                maturity_index=maturity_index,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=False,
            )
            lag = trade_outcome(
                daily,
                funding,
                maturity_index=maturity_index,
                side=side,
                slippage=MAIN_SLIPPAGE,
                include_funding=True,
                lag_days=1,
            )
            if main is None or base is None or funding_off is None:
                counts["incomplete_outcome"] += 1
                continue
            features = event_features(
                dailies,
                hourly,
                funding,
                asset=asset,
                cross_index=cross_index,
                maturity_index=maturity_index,
                side=side,
                cross_criteria=cross_criteria,
                maturity=maturity,
            )
            if features is None:
                counts["incomplete_features"] += 1
                continue
            record: dict[str, Any] = {
                "root_id": f"{asset}-ROOT{local_root:04d}",
                "asset": asset,
                "side": side,
                "side_name": "long" if side > 0 else "short",
                "cross_index": cross_index,
                "cross_ts": pd.Timestamp(daily.at[cross_index, "ts"]),
                "maturity_index": maturity_index,
                "signal_ts": pd.Timestamp(daily.at[maturity_index, "ts"]),
                "maturity_age_days": maturity_index - cross_index,
                "entry_ts": main["entry_ts"],
                "exit_ts": main["exit_ts"],
                "exit_reason": main["exit_reason"],
                "bars_held": int(main["exit_index"] - main["entry_index"]),
                "z_4bps": float(base["direct_net_return"]),
                "z_8bps": float(main["direct_net_return"]),
                "z_funding_off": float(funding_off["direct_net_return"]),
                "z_lag1": (
                    float(lag["direct_net_return"]) if lag is not None else np.nan
                ),
                "funding_return": float(main["funding_return"]),
                "funding_events": int(main["funding_events"]),
                "label": int(float(main["direct_net_return"]) > 0.0),
                **features,
            }
            records.append(record)
            counts["eligible_events"] += 1
            counts["positive_labels"] += record["label"]
        summary[asset] = dict(sorted(counts.items()))
    events = (
        pd.DataFrame(records)
        .sort_values(["signal_ts", "asset", "cross_ts", "side"], ascending=True)
        .reset_index(drop=True)
    )
    if events.empty:
        raise RuntimeError("No eligible maturity events")
    events.insert(0, "event_id", np.arange(len(events), dtype="int64"))
    if events["root_id"].duplicated().any():
        raise RuntimeError("Root ids are not unique")
    if events["signal_ts"].max() >= DEVELOPMENT_END_EXCLUSIVE:
        raise RuntimeError("Post-boundary event entered development")
    if events[list(FEATURES)].isna().any().any():
        raise RuntimeError("Feature matrix contains missing values")
    if not np.isfinite(events[list(FEATURES)].to_numpy(dtype="float64")).all():
        raise RuntimeError("Feature matrix contains non-finite values")
    return events, summary


def event_identity_sha256(events: pd.DataFrame) -> str:
    ordered = events.sort_values(["signal_ts", "asset", "root_id"]).reset_index(
        drop=True
    )
    digest = hashlib.sha256()
    for column in ("cross_ts", "signal_ts", "entry_ts", "exit_ts"):
        values = (
            pd.to_datetime(ordered[column], utc=True)
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )
        digest.update(np.ascontiguousarray(values).tobytes())
    for column in (
        "event_id",
        "side",
        "cross_index",
        "maturity_index",
        "maturity_age_days",
        "bars_held",
        "label",
    ):
        digest.update(
            np.ascontiguousarray(
                ordered[column].to_numpy(dtype="int64")
            ).tobytes()
        )
    for column in ("z_4bps", "z_8bps", "z_funding_off", "z_lag1", *FEATURES):
        values = ordered[column].to_numpy(dtype="float64")
        digest.update(np.ascontiguousarray(values).tobytes())
    for column in ("root_id", "asset", "exit_reason"):
        digest.update("\0".join(ordered[column].astype(str)).encode("utf-8"))
    return digest.hexdigest()


def asset_balanced_weights(events: pd.DataFrame) -> np.ndarray:
    counts = events["asset"].value_counts()
    mapping = {
        asset: len(events) / (len(counts) * count)
        for asset, count in counts.items()
    }
    return events["asset"].map(mapping).to_numpy(dtype="float64")


def fit_model(events: pd.DataFrame, c_value: float) -> Pipeline:
    if events["label"].nunique() < 2:
        raise RuntimeError("Training fold contains one label")
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "model",
                LogisticRegression(
                    C=c_value,
                    l1_ratio=0.0,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=SEED,
                ),
            ),
        ]
    )
    model.fit(
        events[list(FEATURES)],
        events["label"].astype(int),
        model__sample_weight=asset_balanced_weights(events),
    )
    return model


def predict_probability(model: Pipeline, events: pd.DataFrame) -> np.ndarray:
    return np.asarray(
        model.predict_proba(events[list(FEATURES)])[:, 1],
        dtype="float64",
    )


def route_mask(frame: pd.DataFrame, route: str) -> pd.Series:
    if route == "combined":
        return pd.Series(True, index=frame.index)
    if route == "long_only":
        return frame["side"].gt(0)
    if route == "short_only":
        return frame["side"].lt(0)
    raise ValueError(route)


def return_metrics(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    ordered = (
        frame.loc[frame[column].notna()]
        .sort_values(["entry_ts", "asset", "root_id"])
        .reset_index(drop=True)
    )
    if ordered.empty:
        return {
            "events": 0,
            "mean": 0.0,
            "median": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "compound": 0.0,
            "event_sequence_mdd": 0.0,
        }
    returns = ordered[column].to_numpy(dtype="float64")
    factors = np.cumprod(1.0 + returns)
    running_max = np.maximum.accumulate(np.concatenate([[1.0], factors]))[1:]
    drawdown = factors / running_max - 1.0
    positive = float(returns[returns > 0.0].sum())
    negative = float(-returns[returns < 0.0].sum())
    return {
        "events": int(len(ordered)),
        "mean": float(np.mean(returns)),
        "median": float(np.median(returns)),
        "profit_factor": (
            float(positive / negative) if negative > 0.0 else math.inf
        ),
        "win_rate": float(np.mean(returns > 0.0)),
        "compound": float(factors[-1] - 1.0),
        "event_sequence_mdd": float(np.min(drawdown)),
    }


def time_blocks(
    events: pd.DataFrame,
    *,
    initial_fraction: float,
    blocks: int,
) -> list[tuple[int, pd.Timestamp, pd.Timestamp]]:
    dates = pd.DatetimeIndex(sorted(events["signal_ts"].drop_duplicates()))
    initial = int(math.floor(len(dates) * initial_fraction))
    if initial < 10 or len(dates) - initial < blocks:
        raise RuntimeError("Insufficient dates for expanding-time folds")
    result: list[tuple[int, pd.Timestamp, pd.Timestamp]] = []
    for fold, block in enumerate(np.array_split(dates[initial:], blocks), start=1):
        if not len(block):
            raise RuntimeError("Empty time block")
        result.append((fold, pd.Timestamp(block[0]), pd.Timestamp(block[-1])))
    return result


def split_for_block(
    events: pd.DataFrame,
    *,
    first_test: pd.Timestamp,
    last_test: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    purge_boundary = first_test - pd.Timedelta(days=EMBARGO_DAYS)
    train = events.loc[
        events["signal_ts"].lt(first_test)
        & events["exit_ts"].lt(purge_boundary)
    ].copy()
    test = events.loc[
        events["signal_ts"].ge(first_test)
        & events["signal_ts"].le(last_test)
    ].copy()
    return train, test


def select_inner(
    events: pd.DataFrame,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    folds = time_blocks(events, initial_fraction=0.50, blocks=3)
    predictions_by_c: dict[float, pd.DataFrame] = {}
    for c_value in C_GRID:
        frames: list[pd.DataFrame] = []
        for fold, first_test, last_test in folds:
            train, test = split_for_block(
                events,
                first_test=first_test,
                last_test=last_test,
            )
            if train.empty or test.empty or train["label"].nunique() < 2:
                frames = []
                break
            model = fit_model(train, c_value)
            prediction = test.copy()
            prediction["inner_fold"] = fold
            prediction["probability"] = predict_probability(model, test)
            frames.append(prediction)
        if frames:
            predictions_by_c[c_value] = pd.concat(frames, ignore_index=True)
    scores: list[dict[str, Any]] = []
    for c_value, predictions in predictions_by_c.items():
        for route in ROUTES:
            routed = predictions.loc[route_mask(predictions, route)].copy()
            for threshold in THRESHOLD_GRID:
                selected = routed.loc[routed["probability"].ge(threshold)].copy()
                fold_counts = {
                    int(fold): int(
                        selected["inner_fold"].eq(fold).sum()
                    )
                    for fold in range(1, 4)
                }
                eligible = bool(
                    len(selected) >= 40
                    and all(count >= 8 for count in fold_counts.values())
                )
                fold_metrics = {
                    int(fold): return_metrics(
                        selected.loc[selected["inner_fold"].eq(fold)],
                        "z_8bps",
                    )
                    for fold in range(1, 4)
                }
                overall = return_metrics(selected, "z_8bps")
                scores.append(
                    {
                        "C": c_value,
                        "threshold": threshold,
                        "route": route,
                        "eligible": eligible,
                        "selected_events": int(len(selected)),
                        "fold_counts": fold_counts,
                        "worst_fold_mean": (
                            min(
                                float(metric["mean"])
                                for metric in fold_metrics.values()
                            )
                            if eligible
                            else None
                        ),
                        "overall": overall,
                        "fold_metrics": fold_metrics,
                    }
                )
    eligible_scores = [score for score in scores if score["eligible"]]
    if not eligible_scores:
        return None, scores
    choice = max(
        eligible_scores,
        key=lambda score: (
            float(score["worst_fold_mean"]),
            float(score["overall"]["mean"]),
            float(score["overall"]["profit_factor"]),
            float(score["threshold"]),
            -float(score["C"]),
        ),
    )
    return {
        "C": float(choice["C"]),
        "threshold": float(choice["threshold"]),
        "route": str(choice["route"]),
    }, scores


def run_outer_oof(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    blocks = time_blocks(events, initial_fraction=0.40, blocks=4)
    predictions: list[pd.DataFrame] = []
    reports: list[dict[str, Any]] = []
    for held_asset in ASSETS:
        for fold, first_test, last_test in blocks:
            base_train, base_test = split_for_block(
                events,
                first_test=first_test,
                last_test=last_test,
            )
            train = base_train.loc[base_train["asset"].ne(held_asset)].copy()
            test = base_test.loc[base_test["asset"].eq(held_asset)].copy()
            if train.empty or test.empty or train["label"].nunique() < 2:
                raise RuntimeError(
                    f"Invalid outer fold asset={held_asset} fold={fold}"
                )
            choice, inner_scores = select_inner(train)
            if choice is None:
                raise RuntimeError(
                    f"No eligible inner choice asset={held_asset} fold={fold}"
                )
            model = fit_model(train, float(choice["C"]))
            prediction = test.copy()
            prediction["held_asset"] = held_asset
            prediction["outer_fold"] = fold
            prediction["probability"] = predict_probability(model, test)
            prediction["selected_C"] = float(choice["C"])
            prediction["selected_threshold"] = float(choice["threshold"])
            prediction["selected_route"] = str(choice["route"])
            prediction["selected"] = (
                route_mask(prediction, str(choice["route"]))
                & prediction["probability"].ge(float(choice["threshold"]))
            )
            predictions.append(prediction)
            reports.append(
                {
                    "held_asset": held_asset,
                    "outer_fold": fold,
                    "train_rows": int(len(train)),
                    "train_assets": train["asset"].value_counts().to_dict(),
                    "train_start": train["signal_ts"].min(),
                    "train_end": train["signal_ts"].max(),
                    "test_rows": int(len(test)),
                    "test_start": test["signal_ts"].min(),
                    "test_end": test["signal_ts"].max(),
                    "choice": choice,
                    "selected_rows": int(prediction["selected"].sum()),
                    "inner_scores": inner_scores,
                }
            )
    return pd.concat(predictions, ignore_index=True), reports


def cluster_bootstrap(
    selected: pd.DataFrame,
    *,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    if selected.empty:
        return {
            "samples": samples,
            "positive_probability": 0.0,
            "quantiles": {"2.5%": 0.0, "50%": 0.0, "97.5%": 0.0},
        }
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    frame = selected.copy()
    frame["block_90d"] = (
        (pd.to_datetime(frame["entry_ts"], utc=True) - epoch)
        // pd.Timedelta(days=90)
    ).astype("int64")
    clusters = [
        group["z_8bps"].to_numpy(dtype="float64")
        for _, group in frame.groupby(["asset", "block_90d"], sort=True)
    ]
    rng = np.random.default_rng(SEED)
    outcomes = np.empty(samples, dtype="float64")
    for index in range(samples):
        choices = rng.integers(0, len(clusters), size=len(clusters))
        sample = np.concatenate([clusters[item] for item in choices])
        outcomes[index] = float(np.mean(sample))
    return {
        "samples": samples,
        "seed": SEED,
        "clusters": int(len(clusters)),
        "positive_probability": float(np.mean(outcomes > 0.0)),
        "quantiles": {
            "2.5%": float(np.quantile(outcomes, 0.025)),
            "50%": float(np.quantile(outcomes, 0.50)),
            "97.5%": float(np.quantile(outcomes, 0.975)),
        },
    }


def final_choice(outer_reports: list[dict[str, Any]]) -> dict[str, Any]:
    choices = [
        (
            float(report["choice"]["C"]),
            float(report["choice"]["threshold"]),
            str(report["choice"]["route"]),
        )
        for report in outer_reports
    ]
    counts = Counter(choices)
    route_priority = {"combined": 2, "long_only": 1, "short_only": 0}
    c_value, threshold, route = max(
        counts,
        key=lambda choice: (
            counts[choice],
            choice[1],
            -choice[0],
            route_priority[choice[2]],
        ),
    )
    return {
        "C": c_value,
        "threshold": threshold,
        "route": route,
        "outer_choice_count": int(counts[(c_value, threshold, route)]),
        "outer_folds": int(len(choices)),
        "choice_distribution": [
            {
                "C": key[0],
                "threshold": key[1],
                "route": key[2],
                "count": int(value),
            }
            for key, value in sorted(
                counts.items(),
                key=lambda item: (
                    -item[1],
                    -item[0][1],
                    item[0][0],
                    item[0][2],
                ),
            )
        ],
    }


def summarize_oof(
    oof: pd.DataFrame,
    outer_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    selected = oof.loc[oof["selected"]].copy()
    main = return_metrics(selected, "z_8bps")
    variants = {
        column: return_metrics(selected, column)
        for column in ("z_4bps", "z_8bps", "z_funding_off", "z_lag1")
    }
    per_asset: dict[str, Any] = {}
    positive_assets = 0
    dual_improved_assets = 0
    for asset in ASSETS:
        asset_oof = oof.loc[oof["asset"].eq(asset)].copy()
        asset_selected = asset_oof.loc[asset_oof["selected"]].copy()
        model_metrics = return_metrics(asset_selected, "z_8bps")
        baseline_metrics = return_metrics(asset_oof, "z_8bps")
        positive = float(model_metrics["mean"]) > 0.0
        dual_improved = bool(
            float(model_metrics["compound"]) > float(baseline_metrics["compound"])
            and float(model_metrics["event_sequence_mdd"])
            > float(baseline_metrics["event_sequence_mdd"])
        )
        positive_assets += int(positive)
        dual_improved_assets += int(dual_improved)
        per_asset[asset] = {
            "selected": model_metrics,
            "all_matured_baseline": baseline_metrics,
            "positive_mean": positive,
            "dual_improved": dual_improved,
        }
    fold_metrics: dict[str, Any] = {}
    positive_folds = 0
    for (held_asset, fold), frame in oof.groupby(
        ["held_asset", "outer_fold"], sort=True
    ):
        metric = return_metrics(frame.loc[frame["selected"]], "z_8bps")
        positive = int(metric["events"]) > 0 and float(metric["mean"]) > 0.0
        positive_folds += int(positive)
        fold_metrics[f"{held_asset}-{int(fold)}"] = {
            **metric,
            "positive_mean": positive,
        }
    side_counts = {
        "long": int(selected["side"].gt(0).sum()),
        "short": int(selected["side"].lt(0).sum()),
    }
    epoch = pd.Timestamp("1970-01-01T00:00:00Z")
    block_count = int(
        (
            (pd.to_datetime(selected["entry_ts"], utc=True) - epoch)
            // pd.Timedelta(days=90)
        ).nunique()
    )
    ranking_frame = oof.loc[oof["probability"].notna()]
    spearman = float(
        ranking_frame["probability"].corr(
            ranking_frame["z_8bps"], method="spearman"
        )
    )
    bootstrap = cluster_bootstrap(selected)
    choice = final_choice(outer_reports)
    if choice["route"] == "combined":
        direction_gate = side_counts["long"] >= 30 and side_counts["short"] >= 30
    elif choice["route"] == "long_only":
        direction_gate = side_counts["long"] >= 30
    else:
        direction_gate = side_counts["short"] >= 30
    gate_checks = {
        "accepted_total_and_per_asset": bool(
            len(selected) >= 100
            and all(
                int(per_asset[asset]["selected"]["events"]) >= 12
                for asset in ASSETS
            )
        ),
        "direction_coverage": bool(direction_gate),
        "time_block_coverage": bool(block_count >= 15),
        "main_economics": bool(
            float(main["mean"]) > 0.0
            and float(main["profit_factor"]) >= 1.15
        ),
        "positive_assets": bool(positive_assets >= 4),
        "positive_outer_folds": bool(positive_folds >= 15),
        "ranking": bool(math.isfinite(spearman) and spearman > 0.05),
        "cluster_bootstrap": bool(
            float(bootstrap["positive_probability"]) >= 0.90
        ),
        "stress_variants": bool(
            all(
                float(variants[column]["mean"]) > 0.0
                and float(variants[column]["profit_factor"]) >= 1.05
                for column in ("z_4bps", "z_funding_off", "z_lag1")
            )
        ),
        "per_asset_dual_improvement": bool(dual_improved_assets >= 3),
    }
    return {
        "selected_events": int(len(selected)),
        "side_counts": side_counts,
        "time_block_count_90d": block_count,
        "main": main,
        "variants": variants,
        "per_asset": per_asset,
        "positive_asset_count": positive_assets,
        "dual_improved_asset_count": dual_improved_assets,
        "folds": fold_metrics,
        "positive_outer_fold_count": positive_folds,
        "spearman_probability_vs_z8": spearman,
        "bootstrap": bootstrap,
        "final_choice": choice,
        "gate_checks": gate_checks,
        "development_gate_pass": bool(all(gate_checks.values())),
    }


def frozen_model_state(
    events: pd.DataFrame,
    choice: dict[str, Any],
    *,
    event_sha256: str,
    input_quality: dict[str, Any],
) -> dict[str, Any]:
    model = fit_model(events, float(choice["C"]))
    scaler = model.named_steps["scale"]
    estimator = model.named_steps["model"]
    state: dict[str, Any] = {
        "schema_version": "binance-1d-ma7-lmml-model-v1",
        "created_at_utc": datetime.now(UTC),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "assets": list(ASSETS),
        "features": list(FEATURES),
        "C": float(choice["C"]),
        "threshold": float(choice["threshold"]),
        "route": str(choice["route"]),
        "train_rows": int(len(events)),
        "positive_rate": float(events["label"].mean()),
        "event_identity_sha256": event_sha256,
        "input_sha256": {
            asset: quality["input_sha256"]
            for asset, quality in input_quality.items()
        },
        "scaler_mean": {
            feature: float(value)
            for feature, value in zip(FEATURES, scaler.mean_, strict=True)
        },
        "scaler_scale": {
            feature: float(value)
            for feature, value in zip(FEATURES, scaler.scale_, strict=True)
        },
        "coefficients": {
            feature: float(value)
            for feature, value in zip(
                FEATURES, estimator.coef_[0], strict=True
            )
        },
        "intercept": float(estimator.intercept_[0]),
    }
    canonical = json.dumps(
        json_ready(state), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    state["model_state_sha256"] = hashlib.sha256(canonical).hexdigest()
    return state


def build_payload() -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    dict[str, Any] | None,
]:
    dailies: dict[str, pd.DataFrame] = {}
    hourlies: dict[str, pd.DataFrame] = {}
    fundings: dict[str, pd.DataFrame] = {}
    quality: dict[str, Any] = {}
    for asset, slug in ASSETS.items():
        daily, hourly, funding, asset_quality = shared.load_asset_inputs(
            FEATURE_DIR,
            asset=asset,
            slug=slug,
            end_exclusive=DEVELOPMENT_END_EXCLUSIVE,
        )
        dailies[asset] = daily
        hourlies[asset] = hourly
        fundings[asset] = funding
        quality[asset] = asset_quality
    events, root_summary = build_events(dailies, hourlies, fundings)
    event_sha = event_identity_sha256(events)
    oof, outer_reports = run_outer_oof(events)
    summary = summarize_oof(oof, outer_reports)
    capacity = {
        "schema_version": "binance-1d-ma7-lmml-p0-v1",
        "generated_at_utc": datetime.now(UTC),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "assets": list(ASSETS),
        "hype_rows_consumed": 0,
        "shared_kernel": {
            "path": str(SHARED_KERNEL_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_SHARED_KERNEL_SHA256,
        },
        "event_rows": int(len(events)),
        "long_events": int(events["side"].gt(0).sum()),
        "short_events": int(events["side"].lt(0).sum()),
        "later_maturity_events": int(events["maturity_age_days"].gt(0).sum()),
        "positive_rate_8bps": float(events["label"].mean()),
        "event_identity_sha256": event_sha,
        "per_asset_root_summary": root_summary,
        "input_quality": quality,
    }
    report = {
        "schema_version": "binance-1d-ma7-lmml-p1-v1",
        "generated_at_utc": datetime.now(UTC),
        "contract": (
            "specs/binance-1d-ma7-lmml-p0-p1-contract-2026-08-10.md"
        ),
        "development_end_exclusive": DEVELOPMENT_END_EXCLUSIVE,
        "hype_data_loaded": False,
        "shared_kernel": {
            "path": str(SHARED_KERNEL_PATH.relative_to(ROOT)),
            "sha256": EXPECTED_SHARED_KERNEL_SHA256,
        },
        "event_identity_sha256": event_sha,
        "feature_count": len(FEATURES),
        "features": list(FEATURES),
        "cost_model": {
            "fee_per_fill": FEE_RATE,
            "main_slippage_per_fill": MAIN_SLIPPAGE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "funding": "actual event timestamp/rate/mark",
            "leverage": LEVERAGE,
        },
        "model_grid": {
            "C": list(C_GRID),
            "threshold": list(THRESHOLD_GRID),
            "routes": list(ROUTES),
        },
        "outer_fold_reports": outer_reports,
        "summary": summary,
    }
    frozen = (
        frozen_model_state(
            events,
            summary["final_choice"],
            event_sha256=event_sha,
            input_quality=quality,
        )
        if summary["development_gate_pass"]
        else None
    )
    return events, oof, {"capacity": capacity, "report": report}, frozen


def write_outputs(
    output_dir: Path,
    events: pd.DataFrame,
    oof: pd.DataFrame,
    payload: dict[str, Any],
    frozen: dict[str, Any] | None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "events": output_dir / "p0_p1_events.parquet",
        "oof_predictions": output_dir / "p1_oof_predictions.parquet",
        "capacity": output_dir / "p0_data_capacity.json",
        "report": output_dir / "p1_report.json",
        "summary": output_dir / "p1_summary.json",
    }
    atomic_write_parquet(paths["events"], events)
    atomic_write_parquet(paths["oof_predictions"], oof)
    atomic_write_json(paths["capacity"], payload["capacity"])
    atomic_write_json(paths["report"], payload["report"])
    atomic_write_json(paths["summary"], payload["report"]["summary"])
    if frozen is not None:
        paths["frozen_model"] = output_dir / "p1_frozen_model.json"
        atomic_write_json(paths["frozen_model"], frozen)
    hashes = {name: sha256_path(path) for name, path in paths.items()}
    manifest_path = output_dir / "manifest.json"
    atomic_write_json(
        manifest_path,
        {
            "schema_version": "binance-1d-ma7-lmml-manifest-v1",
            "generated_at_utc": datetime.now(UTC),
            "files": {
                name: {"path": path.name, "sha256": hashes[name]}
                for name, path in paths.items()
            },
        },
    )
    manifest_sha = sha256_path(manifest_path)
    checksum_path = output_dir / "manifest.sha256"
    checksum_path.write_text(
        f"{manifest_sha}  {manifest_path.name}\n",
        encoding="utf-8",
    )
    hashes["manifest"] = manifest_sha
    return hashes


def run_self_test() -> None:
    daily = pd.DataFrame(
        {
            "close": [10.0, 10.0, 9.9],
            "sma7": [10.0, 10.0, 10.0],
            "atr7": [1.0, 1.0, 1.0],
        }
    )
    long = maturity_criteria(daily, 1, 1)
    short = maturity_criteria(daily, 2, -1)
    if long["buffer_pass"]:
        raise AssertionError("Long buffer must remain strict")
    if short["buffer_pass"]:
        raise AssertionError("Short 0.10 buffer must remain strict")
    cross_frame = pd.DataFrame(
        {
            "close": [9.0, 10.1, 10.0, 9.9],
            "sma7": [10.0, 10.0, 10.0, 10.0],
        }
    )
    if raw_cross(cross_frame, 1) != 1:
        raise AssertionError("Soft long cross not detected")
    if raw_cross(cross_frame, 3) != -1:
        raise AssertionError("Soft short cross not detected")


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        print("self-test: PASS")
        return
    events, oof, payload, frozen = build_payload()
    result = {
        "event_rows": int(len(events)),
        "oof_rows": int(len(oof)),
        "development_gate_pass": bool(
            payload["report"]["summary"]["development_gate_pass"]
        ),
        "summary": payload["report"]["summary"],
    }
    if not args.no_write:
        result["artifact_sha256"] = write_outputs(
            args.output_dir,
            events,
            oof,
            payload,
            frozen,
        )
    print(json.dumps(json_ready(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
