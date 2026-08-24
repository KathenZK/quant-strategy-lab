from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def feature_paths(feature_dir: Path, slug: str) -> dict[str, Path]:
    return {
        "daily": feature_dir / f"{slug}_perp_1d.parquet",
        "hourly": feature_dir / f"{slug}_perp_1h.parquet",
        "funding": feature_dir / f"{slug}_perp_funding_mark.parquet",
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
    feature_dir: Path,
    *,
    asset: str,
    slug: str,
    end_exclusive: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    paths = feature_paths(feature_dir, slug)
    for path in paths.values():
        if not path.exists():
            raise FileNotFoundError(path)
        if "hype" in path.name.lower():
            raise RuntimeError(f"Forbidden HYPE input path: {path}")
    daily = pd.read_parquet(
        paths["daily"],
        filters=[("ts", "<", end_exclusive.to_pydatetime())],
    )
    hourly = pd.read_parquet(
        paths["hourly"],
        filters=[("ts", "<", end_exclusive.to_pydatetime())],
    )
    funding = pd.read_parquet(
        paths["funding"],
        filters=[("ts", "<", end_exclusive.to_pydatetime())],
    )
    for frame in (daily, hourly, funding):
        frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
        frame.sort_values("ts", inplace=True)
        frame.reset_index(drop=True, inplace=True)
        if frame.empty or frame["ts"].max() >= end_exclusive:
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


def funding_return(
    funding: pd.DataFrame,
    *,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    side: int,
    entry_fill: float,
) -> tuple[float, int]:
    timestamps = pd.DatetimeIndex(funding["ts"])
    left = int(timestamps.searchsorted(entry_ts, side="right"))
    right = int(timestamps.searchsorted(exit_ts, side="left"))
    window = funding.iloc[left:right]
    value = float(
        (
            -side
            * window["funding_rate"].to_numpy(dtype="float64")
            * window["mark_price"].to_numpy(dtype="float64")
            / entry_fill
        ).sum()
    )
    return value, int(len(window))


def levered_trade_return(
    *,
    side: int,
    entry_reference: float,
    exit_reference: float,
    slippage: float,
    fee_rate: float,
    leverage: float,
    funding_component: float,
) -> dict[str, float]:
    entry_fill = entry_reference * (1.0 + side * slippage)
    exit_fill = exit_reference * (1.0 - side * slippage)
    gross_return = side * (exit_fill - entry_fill) / entry_fill
    entry_fee = fee_rate
    exit_fee = fee_rate * exit_fill / entry_fill
    net_return = leverage * (
        gross_return + funding_component - entry_fee - exit_fee
    )
    return {
        "entry_fill": float(entry_fill),
        "exit_fill": float(exit_fill),
        "gross_return": float(leverage * gross_return),
        "funding_return": float(leverage * funding_component),
        "fee_return": float(leverage * (entry_fee + exit_fee)),
        "direct_net_return": float(net_return),
    }


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
