"""Bollinger-inside-Keltner squeeze breakout research kernel.

This module is a frozen multi-timeframe research engine. Consumers must pin its
SHA256 before importing it.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DatasetKind, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings


EXCHANGE = "binance"
SYMBOL = "HYPE/USDT:USDT"
BASE_TIMEFRAME = "15m"
BASE_DELTA = pd.Timedelta(minutes=15)
BASE_PERIODS_PER_YEAR = 365 * 24 * 4
TIMEFRAME_RULES = {
    "15m": ("15min", 1),
    "1h": ("1h", 4),
    "4h": ("4h", 16),
    "1d": ("1D", 96),
}
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}
EVENT_HORIZONS = (1, 2, 4, 8, 16)
UPSTREAM_QUALITY_RELATIVE = (
    "research/hype/15m-ema-trend-breakout/artifacts/"
    "hype_binance_15m_data_quality.json"
)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    bb_window: int = 20
    bb_std_multiplier: float = 2.0
    kc_window: int = 20
    kc_atr_multiplier: float = 1.5
    min_squeeze_bars: int = 3
    breakout_window_bars: int = 3
    hard_stop_atr: float = 3.0
    max_hold_bars: int = 40
    cooldown_bars: int = 1
    allocation: float = 1.0
    fee_per_fill: float = 0.001
    adverse_slippage_per_fill: float = 0.0004

    def validate(self) -> None:
        integers = (
            self.bb_window,
            self.kc_window,
            self.min_squeeze_bars,
            self.breakout_window_bars,
            self.max_hold_bars,
        )
        if any(value <= 0 for value in integers):
            raise ValueError("indicator/state windows must be positive")
        if self.cooldown_bars < 0:
            raise ValueError("cooldown_bars must be non-negative")
        positives = (
            self.bb_std_multiplier,
            self.kc_atr_multiplier,
            self.hard_stop_atr,
            self.allocation,
        )
        if any(value <= 0.0 for value in positives):
            raise ValueError("multipliers and allocation must be positive")
        if min(self.fee_per_fill, self.adverse_slippage_per_fill) < 0.0:
            raise ValueError("cost rates must be non-negative")


@dataclass(frozen=True, slots=True)
class RunSpec:
    name: str
    entry_delay_bars: int = 1

    def validate(self) -> None:
        if self.entry_delay_bars not in {1, 2}:
            raise ValueError("entry_delay_bars must be 1 or 2")


@dataclass(slots=True)
class Position:
    direction: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    entry_equity: float
    previous_price: float
    entry_tf_pos: int
    entry_base_pos: int


@dataclass(frozen=True, slots=True)
class BacktestResult:
    spec: RunSpec
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    time_splits: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series
    open_position: dict[str, Any] | None


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out


def load_base_data(
    root: Path,
) -> tuple[pd.DataFrame, pd.Series, dict[str, Any]]:
    warehouse = DuckDBWarehouse(DataLakeLayout.from_settings(load_settings(None)))
    columns = [
        "ts",
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
        "timeframe",
    ]
    normalized = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=BASE_TIMEFRAME,
        columns=columns,
    )
    raw = warehouse.load_dataset(
        layer="raw",
        kind=DatasetKind.OHLCV,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        timeframe=BASE_TIMEFRAME,
        columns=columns,
    )
    if normalized.empty or raw.empty:
        raise RuntimeError("raw or normalized HYPEUSDT 15m OHLCV is empty")
    duplicate_stats = {
        "raw_loader": raw.attrs.get("duplicate_stats", {}),
        "normalized_loader": normalized.attrs.get("duplicate_stats", {}),
    }
    for candidate in (raw, normalized):
        candidate["ts"] = pd.to_datetime(candidate["ts"], utc=True)
        candidate.sort_values("ts", inplace=True)
    raw_duplicates = int(raw.duplicated("ts").sum())
    normalized_duplicates = int(normalized.duplicated("ts").sum())
    raw = _numeric_frame(raw.drop_duplicates("ts", keep="last"))
    normalized = _numeric_frame(normalized.drop_duplicates("ts", keep="last"))

    raw_indexed = raw.set_index("ts")
    normalized_indexed = normalized.set_index("ts")
    expected = pd.date_range(
        normalized_indexed.index.min(),
        normalized_indexed.index.max(),
        freq="15min",
    )
    missing = expected.difference(normalized_indexed.index)
    critical = [
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
        "timeframe",
    ]
    critical_nulls = {
        column: int(normalized_indexed[column].isna().sum()) for column in critical
    }
    invalid_ohlcv = int(
        (
            normalized_indexed["high"].lt(
                normalized_indexed[["open", "close", "low"]].max(axis=1)
            )
            | normalized_indexed["low"].gt(
                normalized_indexed[["open", "close", "high"]].min(axis=1)
            )
            | normalized_indexed[["open", "high", "low", "close"]]
            .le(0.0)
            .any(axis=1)
            | normalized_indexed["volume"].lt(0.0)
            | normalized_indexed["quote_volume"].lt(0.0)
            | normalized_indexed["trade_count"].lt(0.0)
        ).sum()
    )
    non_closed = int(
        (~normalized_indexed["is_closed"].fillna(False).astype(bool)).sum()
    )
    source_values = sorted(
        str(value) for value in normalized_indexed["source"].dropna().unique()
    )
    timeframe_values = sorted(
        str(value) for value in normalized_indexed["timeframe"].dropna().unique()
    )
    common = raw_indexed.index.intersection(normalized_indexed.index)
    raw_normalized_mismatch: dict[str, int] = {}
    for column in [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
    ]:
        left = raw_indexed.loc[common, column].to_numpy(dtype="float64")
        right = normalized_indexed.loc[common, column].to_numpy(dtype="float64")
        raw_normalized_mismatch[column] = int(
            (~np.isclose(left, right, rtol=0.0, atol=1e-12, equal_nan=True)).sum()
        )
    raw_normalized_mismatch["is_closed"] = int(
        (
            raw_indexed.loc[common, "is_closed"].astype(bool).to_numpy()
            != normalized_indexed.loc[common, "is_closed"].astype(bool).to_numpy()
        ).sum()
    )

    upstream_path = root / UPSTREAM_QUALITY_RELATIVE
    if not upstream_path.exists():
        raise RuntimeError(f"missing upstream quality evidence: {upstream_path}")
    upstream_bytes = upstream_path.read_bytes()
    upstream = json.loads(upstream_bytes)
    upstream_quality = upstream["data_quality"]
    upstream_last = pd.Timestamp(upstream_quality["last_ts"])
    if upstream_last != normalized_indexed.index.max():
        raise RuntimeError(
            f"quality evidence ends {upstream_last}, data ends "
            f"{normalized_indexed.index.max()}"
        )

    blocker_count = (
        raw_duplicates
        + normalized_duplicates
        + len(missing)
        + sum(critical_nulls.values())
        + invalid_ohlcv
        + non_closed
        + sum(raw_normalized_mismatch.values())
        + int(len(common) != len(normalized_indexed))
        + int(source_values != ["binance_futures_kline_api"])
        + int(timeframe_values != [BASE_TIMEFRAME])
        + int(upstream_quality.get("blocker_count", -1) != 0)
    )
    quality: dict[str, Any] = {
        "market": "Binance USD-M Futures",
        "symbol": SYMBOL,
        "source_timeframe": BASE_TIMEFRAME,
        "rows": int(len(normalized_indexed)),
        "start": normalized_indexed.index.min().isoformat(),
        "end": normalized_indexed.index.max().isoformat(),
        "missing_bars": int(len(missing)),
        "raw_duplicate_rows": raw_duplicates,
        "normalized_duplicate_rows": normalized_duplicates,
        "critical_nulls": critical_nulls,
        "invalid_ohlcv_rows": invalid_ohlcv,
        "non_closed_rows": non_closed,
        "source_values": source_values,
        "timeframe_values": timeframe_values,
        "raw_normalized_mismatch": raw_normalized_mismatch,
        "loader_duplicate_stats": duplicate_stats,
        "upstream_quality": {
            "path": UPSTREAM_QUALITY_RELATIVE,
            "sha256": hashlib.sha256(upstream_bytes).hexdigest(),
            "generated_at_utc": upstream["generated_at_utc"],
            "blocker_count": upstream_quality["blocker_count"],
        },
        "blocker_count": int(blocker_count),
    }
    if blocker_count:
        raise RuntimeError(f"data-quality blockers found: {quality}")

    funding_frame = warehouse.load_dataset(
        layer="normalized",
        kind=DatasetKind.FUNDING_RATES,
        exchange=EXCHANGE,
        market_type=MarketType.PERP,
        symbol=SYMBOL,
        columns=["ts", "funding_rate", "source"],
    )
    if funding_frame.empty:
        raise RuntimeError("HYPEUSDT funding history is empty")
    funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True).dt.floor(
        "15min"
    )
    funding_frame["funding_rate"] = pd.to_numeric(
        funding_frame["funding_rate"], errors="coerce"
    )
    if funding_frame["funding_rate"].isna().any():
        raise RuntimeError("funding history contains null/non-numeric values")
    funding_raw = (
        funding_frame.sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .set_index("ts")["funding_rate"]
    )
    funding = funding_raw.reindex(normalized_indexed.index).fillna(0.0)
    quality["funding"] = {
        "rows": int(len(funding_frame)),
        "start": funding_frame["ts"].min().isoformat(),
        "end": funding_frame["ts"].max().isoformat(),
        "non_zero_aligned_rows": int(funding.ne(0.0).sum()),
        "aligned_sum_rate": float(funding.sum()),
        "duplicate_stats": funding_frame.attrs.get("duplicate_stats", {}),
    }
    return (
        normalized_indexed[["open", "high", "low", "close", "volume"]],
        funding.rename("funding_rate"),
        quality,
    )


def aggregate_complete_bars(
    base: pd.DataFrame,
    timeframe: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if timeframe not in TIMEFRAME_RULES:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    rule, expected_count = TIMEFRAME_RULES[timeframe]
    if timeframe == BASE_TIMEFRAME:
        bars = base.copy()
        audit = {
            "timeframe": timeframe,
            "source": "native closed 15m",
            "expected_source_bars_per_bar": 1,
            "candidate_bars": int(len(bars)),
            "complete_bars": int(len(bars)),
            "dropped_partial_bars": 0,
            "start": bars.index.min().isoformat(),
            "end": bars.index.max().isoformat(),
        }
        return bars, audit

    grouped = base.resample(rule, label="left", closed="left", origin="epoch")
    counts = grouped["close"].count()
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    complete = counts.eq(expected_count)
    bars = bars.loc[complete].dropna()
    expected_index = pd.date_range(
        bars.index.min(),
        bars.index.max(),
        freq=rule,
    )
    missing_aggregated = expected_index.difference(bars.index)
    invalid_ohlc = int(
        (
            bars["high"].lt(bars[["open", "close", "low"]].max(axis=1))
            | bars["low"].gt(bars[["open", "close", "high"]].min(axis=1))
            | bars[["open", "high", "low", "close"]].le(0.0).any(axis=1)
        ).sum()
    )
    audit = {
        "timeframe": timeframe,
        "source": "complete UTC buckets resampled from audited native 15m",
        "rule": rule,
        "expected_source_bars_per_bar": expected_count,
        "candidate_bars": int(len(counts)),
        "complete_bars": int(len(bars)),
        "dropped_partial_bars": int((~complete).sum()),
        "missing_aggregated_bars": int(len(missing_aggregated)),
        "invalid_ohlcv_rows": invalid_ohlc,
        "start": bars.index.min().isoformat(),
        "end": bars.index.max().isoformat(),
        "blocker_count": int(len(missing_aggregated) + invalid_ohlc),
    }
    if audit["blocker_count"]:
        raise RuntimeError(f"aggregated data-quality blockers: {audit}")
    return bars, audit


def build_features(
    bars: pd.DataFrame,
    config: StrategyConfig,
) -> pd.DataFrame:
    config.validate()
    out = bars.copy()
    basis = out["close"].rolling(
        config.bb_window, min_periods=config.bb_window
    ).mean()
    std = out["close"].rolling(
        config.bb_window, min_periods=config.bb_window
    ).std(ddof=0)
    atr = true_range(out).rolling(
        config.kc_window, min_periods=config.kc_window
    ).mean()
    out["basis"] = basis
    out["atr"] = atr
    out["bb_upper"] = basis + config.bb_std_multiplier * std
    out["bb_lower"] = basis - config.bb_std_multiplier * std
    out["kc_upper"] = basis + config.kc_atr_multiplier * atr
    out["kc_lower"] = basis - config.kc_atr_multiplier * atr
    out["bb_width"] = (out["bb_upper"] - out["bb_lower"]) / basis
    out["squeeze_on"] = (
        out["bb_upper"].lt(out["kc_upper"])
        & out["bb_lower"].gt(out["kc_lower"])
    ).fillna(False)
    out["release_event"] = False
    out["squeeze_length"] = 0
    out["squeeze_high"] = np.nan
    out["squeeze_low"] = np.nan
    out["long_signal"] = False
    out["short_signal"] = False

    episode_length = 0
    episode_high = -np.inf
    episode_low = np.inf
    armed_remaining = 0
    frozen_high = np.nan
    frozen_low = np.nan
    for i in range(len(out)):
        squeeze = bool(out["squeeze_on"].iloc[i])
        if squeeze:
            episode_length += 1
            episode_high = max(episode_high, float(out["high"].iloc[i]))
            episode_low = min(episode_low, float(out["low"].iloc[i]))
            out.iat[i, out.columns.get_loc("squeeze_length")] = episode_length
            armed_remaining = 0
            continue

        expanding = (
            i > 0
            and np.isfinite(out["bb_width"].iloc[i])
            and np.isfinite(out["bb_width"].iloc[i - 1])
            and float(out["bb_width"].iloc[i]) > float(out["bb_width"].iloc[i - 1])
        )
        previous_squeeze = i > 0 and bool(out["squeeze_on"].iloc[i - 1])
        if (
            previous_squeeze
            and episode_length >= config.min_squeeze_bars
            and expanding
        ):
            armed_remaining = config.breakout_window_bars
            frozen_high = episode_high
            frozen_low = episode_low
            out.iat[i, out.columns.get_loc("release_event")] = True

        if armed_remaining > 0:
            out.iat[i, out.columns.get_loc("squeeze_high")] = frozen_high
            out.iat[i, out.columns.get_loc("squeeze_low")] = frozen_low
            close = float(out["close"].iloc[i])
            long_signal = expanding and close > frozen_high
            short_signal = expanding and close < frozen_low
            if long_signal and short_signal:
                raise RuntimeError("conflicting squeeze breakout signals")
            if long_signal:
                out.iat[i, out.columns.get_loc("long_signal")] = True
                armed_remaining = 0
            elif short_signal:
                out.iat[i, out.columns.get_loc("short_signal")] = True
                armed_remaining = 0
            else:
                armed_remaining -= 1

        episode_length = 0
        episode_high = -np.inf
        episode_low = np.inf
    return out


def adverse_fill(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    config: StrategyConfig,
) -> float:
    sign = direction if is_entry else -direction
    return raw_price * (1.0 + sign * config.adverse_slippage_per_fill)


def max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peaks = equity.cummax()
    return float((equity / peaks - 1.0).min() * 100.0)


def sharpe_ratio(returns: pd.Series) -> float:
    clean = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty or float(clean.std(ddof=0)) == 0.0:
        return 0.0
    return float(
        clean.mean() / clean.std(ddof=0) * math.sqrt(BASE_PERIODS_PER_YEAR)
    )


def metrics_from_path(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
    *,
    trading_cost_rate_total: float,
    funding_rate_total: float,
) -> dict[str, Any]:
    if equity.empty:
        raise RuntimeError("empty equity path")
    duration_years = max(
        (equity.index[-1] - equity.index[0]).total_seconds()
        / (365.0 * 24.0 * 3600.0),
        1.0 / 365.0,
    )
    final_equity = float(equity.iloc[-1])
    annualized_factor = (
        float(final_equity ** (1.0 / duration_years))
        if final_equity > 0.0
        else 0.0
    )
    trade_returns = (
        trades["trade_return"].astype(float)
        if not trades.empty
        else pd.Series(dtype=float)
    )
    wins = trade_returns.loc[trade_returns > 0.0]
    losses = trade_returns.loc[trade_returns < 0.0]
    profit_factor = (
        float(wins.sum() / -losses.sum())
        if not losses.empty
        else (float("inf") if not wins.empty else 0.0)
    )
    return {
        "final_equity": final_equity,
        "return_pct": (final_equity - 1.0) * 100.0,
        "annualized_factor": annualized_factor,
        "max_drawdown_pct": max_drawdown_pct(equity),
        "sharpe": sharpe_ratio(returns),
        "trades": int(len(trades)),
        "win_rate_pct": (
            float((trade_returns > 0.0).mean() * 100.0)
            if not trade_returns.empty
            else 0.0
        ),
        "profit_factor": profit_factor,
        "trading_cost_rate_total": float(trading_cost_rate_total),
        "funding_rate_total": float(funding_rate_total),
    }


def _slice_metrics(
    name: str,
    delta: pd.Timedelta,
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
) -> dict[str, Any]:
    end = equity.index[-1]
    start = max(equity.index[0], end - delta)
    selected = equity.loc[equity.index >= start]
    selected_returns = returns.reindex(selected.index).fillna(0.0)
    base_equity = (
        float(equity.loc[equity.index < start].iloc[-1])
        if bool((equity.index < start).any())
        else 1.0
    )
    path = pd.concat(
        [
            pd.Series([base_equity], index=[selected.index[0] - BASE_DELTA]),
            selected,
        ]
    )
    selected_trades = (
        trades.loc[
            pd.to_datetime(trades["exit_ts"], utc=True).between(
                start, end, inclusive="both"
            )
        ]
        if not trades.empty
        else trades
    )
    return {
        "window": name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "return_pct": float((selected.iloc[-1] / base_equity - 1.0) * 100.0),
        "max_drawdown_pct": max_drawdown_pct(path),
        "sharpe": sharpe_ratio(selected_returns),
        "trades": int(len(selected_trades)),
    }


def _chronological_splits(
    equity: pd.Series,
    returns: pd.Series,
    trades: pd.DataFrame,
) -> list[dict[str, Any]]:
    boundaries = [0, int(len(equity) * 0.50), int(len(equity) * 0.75), len(equity)]
    names = ["development", "validation", "test"]
    rows: list[dict[str, Any]] = []
    for idx, name in enumerate(names):
        start_pos, end_pos = boundaries[idx], boundaries[idx + 1]
        selected = equity.iloc[start_pos:end_pos]
        selected_returns = returns.iloc[start_pos:end_pos]
        base_equity = float(equity.iloc[start_pos - 1]) if start_pos else 1.0
        path = pd.concat(
            [
                pd.Series([base_equity], index=[selected.index[0] - BASE_DELTA]),
                selected,
            ]
        )
        start, end = selected.index[0], selected.index[-1]
        selected_trades = (
            trades.loc[
                pd.to_datetime(trades["exit_ts"], utc=True).between(
                    start, end, inclusive="both"
                )
            ]
            if not trades.empty
            else trades
        )
        rows.append(
            {
                "split": name,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "return_pct": float(
                    (selected.iloc[-1] / base_equity - 1.0) * 100.0
                ),
                "max_drawdown_pct": max_drawdown_pct(path),
                "sharpe": sharpe_ratio(selected_returns),
                "trades": int(len(selected_trades)),
            }
        )
    return rows


def _close_position(
    *,
    equity: float,
    position: Position,
    raw_exit_price: float,
    exit_ts: pd.Timestamp,
    exit_base_pos: int,
    reason: str,
    config: StrategyConfig,
    trades: list[dict[str, Any]],
) -> tuple[float, float]:
    exit_price = adverse_fill(
        raw_exit_price,
        position.direction,
        is_entry=False,
        config=config,
    )
    equity *= 1.0 + position.direction * (
        exit_price / position.previous_price - 1.0
    )
    fee = config.fee_per_fill * config.allocation
    equity *= 1.0 - fee
    trades.append(
        {
            "signal_ts": position.signal_ts,
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": config.allocation,
            "hold_base_bars": exit_base_pos - position.entry_base_pos,
            "exit_reason": reason,
            "raw_price_return": position.direction
            * (exit_price / position.entry_price - 1.0),
            "trade_return": equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": equity,
        }
    )
    return equity, fee


def run_backtest(
    base: pd.DataFrame,
    funding: pd.Series,
    bars: pd.DataFrame,
    features: pd.DataFrame,
    timeframe: str,
    spec: RunSpec,
    config: StrategyConfig,
) -> BacktestResult:
    spec.validate()
    rule, source_bars_per_bar = TIMEFRAME_RULES[timeframe]
    timeframe_delta = pd.Timedelta(rule)
    valid_feature_positions = np.flatnonzero(features["atr"].notna().to_numpy())
    if not len(valid_feature_positions):
        raise RuntimeError(f"{timeframe}: no valid feature rows")
    first_feature_pos = int(valid_feature_positions[0])
    start_tf_pos = min(first_feature_pos + 1, len(bars) - 1)
    execution_start = bars.index[start_tf_pos]
    execution_end_exclusive = bars.index[-1] + timeframe_delta
    execution_base = base.loc[
        (base.index >= execution_start) & (base.index < execution_end_exclusive)
    ]
    execution_funding = funding.reindex(execution_base.index).fillna(0.0)
    if execution_base.empty:
        raise RuntimeError(f"{timeframe}: empty execution grid")

    entry_schedule: dict[pd.Timestamp, tuple[int, pd.Timestamp, int]] = {}
    for signal_pos in np.flatnonzero(
        (features["long_signal"] | features["short_signal"]).to_numpy()
    ):
        entry_tf_pos = int(signal_pos + spec.entry_delay_bars)
        if entry_tf_pos >= len(bars):
            continue
        direction = 1 if bool(features["long_signal"].iloc[signal_pos]) else -1
        entry_schedule[pd.Timestamp(bars.index[entry_tf_pos])] = (
            direction,
            pd.Timestamp(bars.index[signal_pos]),
            entry_tf_pos,
        )
    close_to_tf_pos = {
        pd.Timestamp(start + timeframe_delta - BASE_DELTA): pos
        for pos, start in enumerate(bars.index)
    }

    equity = 1.0
    position: Position | None = None
    pending_exit_ts: pd.Timestamp | None = None
    pending_exit_reason: str | None = None
    cooldown_until_tf_pos = -1
    trades: list[dict[str, Any]] = []
    equity_values: list[float] = []
    period_returns: list[float] = []
    timestamps: list[pd.Timestamp] = []
    trading_cost_rate_total = 0.0
    funding_rate_total = 0.0

    for base_pos, (ts, row) in enumerate(execution_base.iterrows()):
        ts = pd.Timestamp(ts)
        start_equity = equity
        open_price = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        exited_this_bar = False

        if (
            position is not None
            and pending_exit_ts is not None
            and ts >= pending_exit_ts
        ):
            equity, fee = _close_position(
                equity=equity,
                position=position,
                raw_exit_price=open_price,
                exit_ts=ts,
                exit_base_pos=base_pos,
                reason=str(pending_exit_reason),
                config=config,
                trades=trades,
            )
            trading_cost_rate_total += fee
            cooldown_until_tf_pos = (
                position.entry_tf_pos
                + max(1, math.ceil((base_pos - position.entry_base_pos) / source_bars_per_bar))
                + config.cooldown_bars
            )
            position = None
            pending_exit_ts = None
            pending_exit_reason = None
            exited_this_bar = True

        scheduled = entry_schedule.get(ts)
        if position is None and not exited_this_bar and scheduled is not None:
            direction, signal_ts, entry_tf_pos = scheduled
            if entry_tf_pos >= cooldown_until_tf_pos:
                signal_atr = float(features["atr"].loc[signal_ts])
                if np.isfinite(signal_atr) and signal_atr > 0.0:
                    entry_price = adverse_fill(
                        open_price,
                        direction,
                        is_entry=True,
                        config=config,
                    )
                    entry_equity = equity
                    fee = config.fee_per_fill * config.allocation
                    equity *= 1.0 - fee
                    trading_cost_rate_total += fee
                    position = Position(
                        direction=direction,
                        signal_ts=signal_ts,
                        entry_ts=ts,
                        entry_price=entry_price,
                        entry_atr=signal_atr,
                        entry_equity=entry_equity,
                        previous_price=entry_price,
                        entry_tf_pos=entry_tf_pos,
                        entry_base_pos=base_pos,
                    )

        if position is not None:
            funding_effect = (
                -position.direction
                * config.allocation
                * float(execution_funding.loc[ts])
            )
            equity *= 1.0 + funding_effect
            funding_rate_total += funding_effect
            stop = (
                position.entry_price
                - position.direction * config.hard_stop_atr * position.entry_atr
            )
            stop_hit = False
            raw_exit_price = stop
            reason = "stop_loss"
            if position.direction == 1:
                if open_price <= stop:
                    stop_hit, raw_exit_price, reason = True, open_price, "stop_loss_gap"
                elif low <= stop:
                    stop_hit = True
            else:
                if open_price >= stop:
                    stop_hit, raw_exit_price, reason = True, open_price, "stop_loss_gap"
                elif high >= stop:
                    stop_hit = True
            if stop_hit:
                equity, fee = _close_position(
                    equity=equity,
                    position=position,
                    raw_exit_price=raw_exit_price,
                    exit_ts=ts,
                    exit_base_pos=base_pos,
                    reason=reason,
                    config=config,
                    trades=trades,
                )
                trading_cost_rate_total += fee
                cooldown_until_tf_pos = (
                    position.entry_tf_pos
                    + max(
                        1,
                        math.ceil(
                            (base_pos - position.entry_base_pos + 1)
                            / source_bars_per_bar
                        ),
                    )
                    + config.cooldown_bars
                )
                position = None
                exited_this_bar = True
            else:
                equity *= 1.0 + position.direction * config.allocation * (
                    close / position.previous_price - 1.0
                )
                position.previous_price = close

        tf_pos = close_to_tf_pos.get(ts)
        if position is not None and tf_pos is not None and pending_exit_ts is None:
            feature = features.iloc[tf_pos]
            crossed_midline = (
                position.direction == 1 and float(feature["close"]) < float(feature["basis"])
            ) or (
                position.direction == -1 and float(feature["close"]) > float(feature["basis"])
            )
            held_tf_bars = tf_pos - position.entry_tf_pos + 1
            if crossed_midline or held_tf_bars >= config.max_hold_bars:
                pending_exit_ts = pd.Timestamp(bars.index[tf_pos] + timeframe_delta)
                pending_exit_reason = (
                    "midline_next_open" if crossed_midline else "timeout_next_open"
                )

        timestamps.append(ts)
        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)

    index = pd.DatetimeIndex(timestamps)
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    period_return_series = pd.Series(period_returns, index=index, name=spec.name)
    trades_frame = pd.DataFrame(trades)
    metrics = metrics_from_path(
        equity_curve,
        period_return_series,
        trades_frame,
        trading_cost_rate_total=trading_cost_rate_total,
        funding_rate_total=funding_rate_total,
    )
    slices = [
        _slice_metrics(
            name,
            delta,
            equity_curve,
            period_return_series,
            trades_frame,
        )
        for name, delta in RECENT_WINDOWS.items()
    ]
    time_splits = _chronological_splits(
        equity_curve,
        period_return_series,
        trades_frame,
    )
    open_position = None
    if position is not None:
        open_position = {
            "direction": position.direction,
            "signal_ts": position.signal_ts.isoformat(),
            "entry_ts": position.entry_ts.isoformat(),
            "entry_price": position.entry_price,
            "entry_atr": position.entry_atr,
            "unrealized_trade_return_pct": (
                equity / position.entry_equity - 1.0
            )
            * 100.0,
        }
    return BacktestResult(
        spec=spec,
        metrics=metrics,
        slices=slices,
        time_splits=time_splits,
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=period_return_series,
        open_position=open_position,
    )


def event_study(
    bars: pd.DataFrame,
    features: pd.DataFrame,
    timeframe: str,
    config: StrategyConfig,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    rng = np.random.default_rng(
        {"15m": 1515, "1h": 101, "4h": 404, "1d": 1001}[timeframe]
    )
    signal_positions = np.flatnonzero(
        (features["long_signal"] | features["short_signal"]).to_numpy()
    )
    for signal_pos in signal_positions:
        entry_pos = int(signal_pos + 1)
        if entry_pos >= len(bars):
            continue
        direction = 1 if bool(features["long_signal"].iloc[signal_pos]) else -1
        raw_entry = float(bars["open"].iloc[entry_pos])
        for horizon in EVENT_HORIZONS:
            exit_pos = entry_pos + horizon
            if exit_pos >= len(bars):
                continue
            raw_exit = float(bars["open"].iloc[exit_pos])
            gross_return = direction * (raw_exit / raw_entry - 1.0)
            entry_fill = adverse_fill(
                raw_entry, direction, is_entry=True, config=config
            )
            exit_fill = adverse_fill(
                raw_exit, direction, is_entry=False, config=config
            )
            price_return_after_slippage = direction * (
                exit_fill / entry_fill - 1.0
            )
            net_return = (
                (1.0 - config.fee_per_fill)
                * (1.0 + price_return_after_slippage)
                * (1.0 - config.fee_per_fill)
                - 1.0
            )
            rows.append(
                {
                    "signal_ts": bars.index[signal_pos],
                    "direction": direction,
                    "entry_ts": bars.index[entry_pos],
                    "exit_ts": bars.index[exit_pos],
                    "horizon_bars": horizon,
                    "gross_return": gross_return,
                    "net_return": net_return,
                }
            )
    frame = pd.DataFrame(rows)
    summary: list[dict[str, Any]] = []
    for horizon in EVENT_HORIZONS:
        selected = (
            frame.loc[frame["horizon_bars"].eq(horizon), "net_return"]
            .astype(float)
            .to_numpy()
            if not frame.empty
            else np.array([], dtype=float)
        )
        gross = (
            frame.loc[frame["horizon_bars"].eq(horizon), "gross_return"]
            .astype(float)
            .to_numpy()
            if not frame.empty
            else np.array([], dtype=float)
        )
        if len(selected) >= 2:
            samples = rng.choice(selected, size=(2000, len(selected)), replace=True).mean(
                axis=1
            )
            ci_low, ci_high = np.quantile(samples, [0.05, 0.95])
        else:
            ci_low = ci_high = np.nan
        summary.append(
            {
                "horizon_bars": horizon,
                "events": int(len(selected)),
                "gross_mean_pct": (
                    float(np.mean(gross) * 100.0) if len(gross) else 0.0
                ),
                "net_mean_pct": (
                    float(np.mean(selected) * 100.0) if len(selected) else 0.0
                ),
                "net_median_pct": (
                    float(np.median(selected) * 100.0) if len(selected) else 0.0
                ),
                "net_win_rate_pct": (
                    float(np.mean(selected > 0.0) * 100.0) if len(selected) else 0.0
                ),
                "bootstrap_mean_p05_pct": (
                    float(ci_low * 100.0) if np.isfinite(ci_low) else None
                ),
                "bootstrap_mean_p95_pct": (
                    float(ci_high * 100.0) if np.isfinite(ci_high) else None
                ),
            }
        )
    return frame, summary


def buy_and_hold_metrics(
    base: pd.DataFrame,
    config: StrategyConfig,
) -> dict[str, float]:
    entry = float(base["open"].iloc[0]) * (
        1.0 + config.adverse_slippage_per_fill
    )
    exit_price = float(base["close"].iloc[-1]) * (
        1.0 - config.adverse_slippage_per_fill
    )
    final_equity = (
        (1.0 - config.fee_per_fill)
        * (exit_price / entry)
        * (1.0 - config.fee_per_fill)
    )
    return {
        "return_pct": (final_equity - 1.0) * 100.0,
        "final_equity": final_equity,
    }


def viability_gate(result: BacktestResult) -> dict[str, Any]:
    split_returns = {
        row["split"]: float(row["return_pct"]) for row in result.time_splits
    }
    recent = {row["window"]: row for row in result.slices}
    checks = {
        "full_return_positive": result.metrics["return_pct"] > 0.0,
        "max_drawdown_not_worse_than_35pct": (
            result.metrics["max_drawdown_pct"] >= -35.0
        ),
        "minimum_30_closed_trades": result.metrics["trades"] >= 30,
        "development_positive": split_returns["development"] > 0.0,
        "validation_positive": split_returns["validation"] > 0.0,
        "test_positive": split_returns["test"] > 0.0,
        "recent_3m_positive": recent["3m"]["return_pct"] > 0.0,
        "recent_6m_positive": recent["6m"]["return_pct"] > 0.0,
    }
    return {
        "checks": checks,
        "passed_count": int(sum(checks.values())),
        "total_count": int(len(checks)),
        "passed": bool(all(checks.values())),
    }


def _serialize_result(result: BacktestResult) -> dict[str, Any]:
    return {
        "spec": asdict(result.spec),
        "metrics": result.metrics,
        "slices": result.slices,
        "time_splits": result.time_splits,
        "open_position": result.open_position,
    }


def render_report(payload: dict[str, Any], artifact_stem: str) -> str:
    primary = payload["results"]["primary_k1"]
    k2 = payload["results"]["entry_delay_k2"]
    gross = payload["results"]["zero_cost_ablation"]
    quality = payload["data_quality"]
    aggregate = payload["aggregation_quality"]
    recent = {row["window"]: row for row in primary["slices"]}
    splits = primary["time_splits"]
    events = payload["event_study"]["summary"]
    gate = payload["viability_gate"]
    outcome = (
        "通过本轮最低可行性门槛"
        if gate["passed"]
        else "未通过本轮最低可行性门槛"
    )
    event_rows = "\n".join(
        "| {horizon_bars} | {events} | {gross_mean_pct:+.2f}% | "
        "{net_mean_pct:+.2f}% | {net_median_pct:+.2f}% | "
        "{net_win_rate_pct:.1f}% | {ci_low} |".format(
            **row,
            ci_low=(
                f"{row['bootstrap_mean_p05_pct']:+.2f}% / "
                f"{row['bootstrap_mean_p95_pct']:+.2f}%"
                if row["bootstrap_mean_p05_pct"] is not None
                else "样本不足"
            ),
        )
        for row in events
    )
    slice_rows = "\n".join(
        f"| {name} | {recent[name]['return_pct']:+.2f}% | "
        f"{recent[name]['max_drawdown_pct']:.2f}% | {recent[name]['trades']} |"
        for name in RECENT_WINDOWS
    )
    split_rows = "\n".join(
        f"| {row['split']} | {row['start']} | {row['end']} | "
        f"{row['return_pct']:+.2f}% | {row['max_drawdown_pct']:.2f}% | "
        f"{row['trades']} |"
        for row in splits
    )
    failed_checks = [
        name for name, passed in gate["checks"].items() if not passed
    ]
    return f"""# {payload['family_name']} 基础策略诊断（{payload['run_date']}）

## 结论

`{payload['timeframe']}` 基础规则{outcome}，门槛为
`{gate['passed_count']}/{gate['total_count']}`。主口径净收益
`{primary['metrics']['return_pct']:+.2f}%`，MaxDD
`{primary['metrics']['max_drawdown_pct']:.2f}%`，闭合交易
`{primary['metrics']['trades']}` 笔，胜率
`{primary['metrics']['win_rate_pct']:.2f}%`，profit factor
`{primary['metrics']['profit_factor']:.3f}`。失败检查：
`{", ".join(failed_checks) if failed_checks else "无"}`。

本报告是冻结基础机制的探索性诊断，不是参数搜索，不登记版本，也不支持
promotion。当前状态保持 `explore / not promoted / not live-ready`。

## 冻结规则

- Bollinger：收盘 `SMA20 ± 2 × population std20`。
- Keltner：同一 `SMA20 ± 1.5 × mean true range20`。
- squeeze：布林上轨低于 Keltner 上轨且布林下轨高于 Keltner 下轨，连续至少
  `3` 根。
- release/breakout：布林离开 Keltner 且宽度扩张；释放当根及随后 `2` 根内，
  收盘突破 squeeze episode 的 high/low 才产生对应多/空信号。
- K0 闭合确认，主口径 K1 open 入场；固定 `1x`、单持仓、不加仓。
- 紧急止损：`3 × signal ATR20`，从入场 15m 子柱起生效，gap 按更差 open。
- 正常退出：多头收盘跌破 SMA20、空头收盘升破 SMA20，下一目标周期 open；
  最长 `40` 根目标周期，冷却 `1` 根。
- 成本：每 fill 手续费 `0.001` + adverse slippage `4 bps`，实际 Binance
  funding 按 15m 执行网格计入。

所有参数在运行前冻结；K2、零成本和事件 horizon 只作诊断，不用于选择或调参。

## 数据与质量

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。
- 原始执行网格：闭合 `15m`，`{quality['start']}` 至 `{quality['end']}`，
  `{quality['rows']}` 根；缺口 `{quality['missing_bars']}`、raw/normalized
  mismatch `{sum(quality['raw_normalized_mismatch'].values())}`、blocker
  `{quality['blocker_count']}`。
- 本周期：`{aggregate['start']}` 至 `{aggregate['end']}`，
  `{aggregate['complete_bars']}` 根完整 `{payload['timeframe']}` K 线；
  丢弃不完整首尾桶 `{aggregate['dropped_partial_bars']}`，聚合 blocker
  `{aggregate.get('blocker_count', 0)}`。
- 高周期信号由完整 UTC 桶构建；实际止损、mark-to-market 与 funding 仍在真实
  15m 子柱执行，未用高周期 OHLC 猜测止损顺序。

## 主口径结果

| Run | Return | Annual factor | MaxDD | Sharpe | Trades | Win rate | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| K1 net | {primary['metrics']['return_pct']:+.2f}% | {primary['metrics']['annualized_factor']:.3f}x | {primary['metrics']['max_drawdown_pct']:.2f}% | {primary['metrics']['sharpe']:.2f} | {primary['metrics']['trades']} | {primary['metrics']['win_rate_pct']:.2f}% | {primary['metrics']['profit_factor']:.3f} |
| K2 entry delay | {k2['metrics']['return_pct']:+.2f}% | {k2['metrics']['annualized_factor']:.3f}x | {k2['metrics']['max_drawdown_pct']:.2f}% | {k2['metrics']['sharpe']:.2f} | {k2['metrics']['trades']} | {k2['metrics']['win_rate_pct']:.2f}% | {k2['metrics']['profit_factor']:.3f} |
| K1 zero fee/slippage | {gross['metrics']['return_pct']:+.2f}% | {gross['metrics']['annualized_factor']:.3f}x | {gross['metrics']['max_drawdown_pct']:.2f}% | {gross['metrics']['sharpe']:.2f} | {gross['metrics']['trades']} | {gross['metrics']['win_rate_pct']:.2f}% | {gross['metrics']['profit_factor']:.3f} |
| Buy & hold 1x net | {payload['buy_and_hold']['return_pct']:+.2f}% | - | - | - | 1 | - | - |

策略相对 buy-and-hold 的 full excess return 为
`{payload['excess_return_vs_buy_hold_pct']:+.2f}` 个百分点。这只是方向 beta
对照，不替代结构化 OOS。

## 连续时间拆分

| Split | Start | End | Return | MaxDD | Trades |
| --- | --- | --- | ---: | ---: | ---: |
{split_rows}

## 最近切片

切片锚定本周期最后一个完整 bar 的执行终点，只用于审计。

| Window | Return | MaxDD | Closed trades |
| --- | ---: | ---: | ---: |
{slice_rows}

## 信号事件研究

固定在信号后下一周期 open 入场，并在第 `h` 根后 open 退出；net 已扣双边
手续费与滑点，不含 funding。bootstrap 为 2,000 次信号抽样均值的
`5% / 95%` 分位。

| Horizon bars | Events | Gross mean | Net mean | Net median | Net win rate | Bootstrap mean p05/p95 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{event_rows}

## 有效性判定

- 最低可行性门槛：full return `> 0`、MaxDD 不差于 `-35%`、至少 `30`
  笔闭合交易、development/validation/test、最近 `3m/6m` 均为正。
- 门槛结果：`{gate['passed_count']}/{gate['total_count']}`，总体
  `{"PASS" if gate["passed"] else "FAIL"}`。
- 这不是 promotion review：未做消融、CPCV、Monte Carlo、真实 1m 相位扫描、
  拒单/断流/重启/kill-switch 或 runner parity，因此无论收益如何都保持
  `explore / not promoted / not live-ready`。

## 证据

- [汇总 JSON](../artifacts/{artifact_stem}-summary.json)
- [逐笔交易](../artifacts/{artifact_stem}-trades.csv)
- [权益曲线](../artifacts/{artifact_stem}-equity.csv)
- [事件路径](../artifacts/{artifact_stem}-event-study.csv)
- [消费方脚本](../scripts/run_baseline.py)
"""


def run_suite(
    root: Path,
    *,
    family_dir: Path,
    family_name: str,
    family_alias: str,
    timeframe: str,
    run_date: str,
) -> tuple[dict[str, Any], dict[str, pd.DataFrame | pd.Series]]:
    config = StrategyConfig()
    base, funding, quality = load_base_data(root)
    bars, aggregation_quality = aggregate_complete_bars(base, timeframe)
    features = build_features(bars, config)
    primary = run_backtest(
        base,
        funding,
        bars,
        features,
        timeframe,
        RunSpec(name="primary_k1", entry_delay_bars=1),
        config,
    )
    k2 = run_backtest(
        base,
        funding,
        bars,
        features,
        timeframe,
        RunSpec(name="entry_delay_k2", entry_delay_bars=2),
        config,
    )
    zero_cost_config = replace(
        config,
        fee_per_fill=0.0,
        adverse_slippage_per_fill=0.0,
    )
    zero_cost = run_backtest(
        base,
        funding,
        bars,
        features,
        timeframe,
        RunSpec(name="zero_cost_ablation", entry_delay_bars=1),
        zero_cost_config,
    )
    event_frame, event_summary = event_study(
        bars, features, timeframe, config
    )
    execution_start = primary.equity_curve.index[0]
    execution_end = primary.equity_curve.index[-1]
    buy_hold = buy_and_hold_metrics(
        base.loc[(base.index >= execution_start) & (base.index <= execution_end)],
        config,
    )
    gate = viability_gate(primary)
    payload: dict[str, Any] = {
        "family_name": family_name,
        "family_alias": family_alias,
        "timeframe": timeframe,
        "run_date": run_date,
        "status": "explore / not promoted / not live-ready",
        "selection_policy": (
            "All signal, execution and exit parameters were frozen before the "
            "first suite run. K2, zero-cost and event horizons are audit-only."
        ),
        "config": asdict(config),
        "data_quality": quality,
        "aggregation_quality": aggregation_quality,
        "signal_counts": {
            "squeeze_bars": int(features["squeeze_on"].sum()),
            "release_events": int(features["release_event"].sum()),
            "long_signals": int(features["long_signal"].sum()),
            "short_signals": int(features["short_signal"].sum()),
        },
        "results": {
            "primary_k1": _serialize_result(primary),
            "entry_delay_k2": _serialize_result(k2),
            "zero_cost_ablation": _serialize_result(zero_cost),
        },
        "buy_and_hold": buy_hold,
        "excess_return_vs_buy_hold_pct": (
            primary.metrics["return_pct"] - buy_hold["return_pct"]
        ),
        "event_study": {
            "horizons": list(EVENT_HORIZONS),
            "summary": event_summary,
            "bootstrap_draws": 2000,
        },
        "viability_gate": gate,
    }
    paths: dict[str, pd.DataFrame | pd.Series] = {
        "trades": primary.trades,
        "equity": pd.concat(
            [
                primary.equity_curve,
                k2.equity_curve,
                zero_cost.equity_curve,
            ],
            axis=1,
        ),
        "event_study": event_frame,
    }
    return payload, paths


def write_outputs(
    *,
    family_dir: Path,
    artifact_stem: str,
    payload: dict[str, Any],
    paths: dict[str, pd.DataFrame | pd.Series],
) -> None:
    artifact_dir = family_dir / "artifacts"
    diagnostic_dir = family_dir / "diagnostics"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / f"{artifact_stem}-summary.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    trades = paths["trades"]
    assert isinstance(trades, pd.DataFrame)
    trades.to_csv(artifact_dir / f"{artifact_stem}-trades.csv", index=False)
    equity = paths["equity"]
    assert isinstance(equity, (pd.DataFrame, pd.Series))
    equity.to_csv(artifact_dir / f"{artifact_stem}-equity.csv", index_label="ts")
    events = paths["event_study"]
    assert isinstance(events, pd.DataFrame)
    events.to_csv(
        artifact_dir / f"{artifact_stem}-event-study.csv", index=False
    )
    report_path = diagnostic_dir / f"{artifact_stem}.md"
    report_path.write_text(
        render_report(payload, artifact_stem),
        encoding="utf-8",
    )

