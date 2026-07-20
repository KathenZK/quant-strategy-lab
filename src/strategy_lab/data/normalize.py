from __future__ import annotations

from typing import Iterable

import pandas as pd

from strategy_lab.data.models import DatasetKind, dataset_specs
from strategy_lab.data.quality import (
    DuplicatePolicy,
    OHLCVDerivationPolicy,
    derive_ohlcv_columns,
    resolve_duplicates,
    validate_frame,
)


def _coerce_timestamp(frame: pd.DataFrame) -> pd.DataFrame:
    if "ts" not in frame.columns:
        return frame
    normalized = frame.copy()
    parsed = []
    for row_number, value in normalized["ts"].items():
        try:
            timestamp = pd.Timestamp(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid ts at row {row_number}: {value!r}") from exc
        if timestamp.tzinfo is None:
            raise ValueError(
                f"ts must include an explicit timezone at row {row_number}: {value!r}"
            )
        parsed.append(timestamp.tz_convert("UTC"))
    normalized["ts"] = pd.DatetimeIndex(parsed)
    normalized["date"] = normalized["ts"].dt.date.astype("string")
    return normalized


def _normalize_strings(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    normalized = frame.copy()
    for column in columns:
        if column not in normalized.columns:
            continue
        if column in {"exchange", "market_type", "timeframe", "source", "chain", "metric_name", "status", "side"}:
            normalized[column] = normalized[column].astype("string").str.lower()
        elif column in {"symbol"}:
            normalized[column] = normalized[column].astype("string").str.upper()
        else:
            normalized[column] = normalized[column].astype("string").str.upper()
    return normalized


def _sort_columns(kind: DatasetKind, frame: pd.DataFrame) -> pd.DataFrame:
    priority = list(dataset_specs()[kind].required_columns)
    if "timeframe" in frame.columns and "timeframe" not in priority:
        priority.append("timeframe")
    if "date" in frame.columns:
        priority.append("date")
    remaining = [column for column in frame.columns if column not in priority]
    return frame[priority + remaining]


def normalize_dataset(
    kind: DatasetKind,
    frame: pd.DataFrame,
    *,
    ohlcv_derivation: OHLCVDerivationPolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
) -> pd.DataFrame:
    normalized = _coerce_timestamp(frame)
    normalized = _normalize_strings(
        normalized,
        ["exchange", "symbol", "market_type", "timeframe", "base_asset", "quote_asset", "source", "chain", "metric_name", "status", "side"],
    )

    numeric_candidates = {
        "open",
        "high",
        "low",
        "close",
        "volume",
        "funding_rate",
        "open_interest",
        "open_interest_value",
        "basis",
        "basis_rate",
        "annualized_basis",
        "futures_price",
        "index_price",
        "mark_price",
        "premium_index",
        "bid",
        "ask",
        "price",
        "quote_volume",
        "trade_count",
        "vwap",
        "size",
        "filled_quantity",
        "notional",
        "value",
    }
    for column in numeric_candidates.intersection(normalized.columns):
        try:
            normalized[column] = pd.to_numeric(normalized[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid numeric value in column {column}") from exc
    if kind == DatasetKind.OHLCV:
        normalized = derive_ohlcv_columns(normalized, ohlcv_derivation)

    normalized, duplicate_stats = resolve_duplicates(
        kind,
        normalized,
        policy=duplicate_policy,
    )
    if "ts" in normalized.columns:
        sort_by = [column for column in ("exchange", "symbol", "ts") if column in normalized.columns]
        normalized = normalized.sort_values(sort_by).reset_index(drop=True)
    validate_frame(kind, normalized)
    normalized = _sort_columns(kind, normalized)
    normalized.attrs["duplicate_stats"] = duplicate_stats.to_dict()
    return normalized
