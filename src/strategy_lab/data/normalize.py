from __future__ import annotations

from typing import Iterable

import pandas as pd

from strategy_lab.data.models import DatasetKind, dataset_specs


def _coerce_timestamp(frame: pd.DataFrame) -> pd.DataFrame:
    if "ts" not in frame.columns:
        return frame
    normalized = frame.copy()
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
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


def _ensure_ohlcv_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if "close" not in frame.columns or "volume" not in frame.columns:
        return frame
    enriched = frame.copy()
    if "quote_volume" not in enriched.columns:
        enriched["quote_volume"] = enriched["close"] * enriched["volume"]
    if "trade_count" not in enriched.columns:
        enriched["trade_count"] = 0
    if "vwap" not in enriched.columns:
        volume = enriched["volume"].replace(0.0, pd.NA)
        enriched["vwap"] = enriched["quote_volume"] / volume
        if {"high", "low", "close"}.issubset(enriched.columns):
            fallback = (enriched["high"] + enriched["low"] + enriched["close"]) / 3.0
            enriched["vwap"] = enriched["vwap"].fillna(fallback)
    else:
        enriched["vwap"] = enriched["vwap"].fillna(enriched["close"])
    if "is_closed" not in enriched.columns:
        enriched["is_closed"] = True
    return enriched


def normalize_dataset(kind: DatasetKind, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()

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
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    if kind == DatasetKind.OHLCV:
        normalized = _ensure_ohlcv_columns(normalized)

    subset = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in normalized.columns]
    if subset:
        normalized = normalized.drop_duplicates(subset=subset, keep="last")
    if "ts" in normalized.columns:
        sort_by = [column for column in ("exchange", "symbol", "ts") if column in normalized.columns]
        normalized = normalized.sort_values(sort_by).reset_index(drop=True)
    if "is_closed" in normalized.columns:
        normalized["is_closed"] = normalized["is_closed"].astype(bool)
    return _sort_columns(kind, normalized)
