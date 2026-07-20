from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.models import DatasetKind, MarketType
from strategy_lab.data.normalize import normalize_dataset
from strategy_lab.data.fs import atomic_write_path
from strategy_lab.data.quality import (
    DuplicatePolicy,
    OHLCVDerivationPolicy,
    derive_ohlcv_columns,
    resolve_duplicates,
    validate_frame,
)


def _infer_timeframe(frame: pd.DataFrame, timeframe: str | None) -> str | None:
    if timeframe:
        return timeframe
    if "timeframe" not in frame.columns:
        return None
    values = frame["timeframe"].dropna().astype(str).str.lower().unique()
    return str(values[0]) if len(values) == 1 else None


def write_dataframe(
    frame: pd.DataFrame,
    *,
    layout: DataLakeLayout,
    layer: str,
    kind: DatasetKind,
    exchange: str,
    market_type: MarketType,
    symbol: str,
    partition_date: date,
    timeframe: str | None = None,
    file_stem: str | None = None,
    ohlcv_derivation: OHLCVDerivationPolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
) -> Path:
    prepared = frame.copy()
    if timeframe:
        prepared["timeframe"] = timeframe.lower()
    if kind == DatasetKind.OHLCV:
        prepared = derive_ohlcv_columns(prepared, ohlcv_derivation)
    prepared, duplicate_stats = resolve_duplicates(
        kind,
        prepared,
        policy=duplicate_policy,
    )
    validate_frame(kind, prepared)
    prepared.attrs["duplicate_stats"] = duplicate_stats.to_dict()
    effective_timeframe = _infer_timeframe(prepared, timeframe)
    path = layout.dataset_path(
        layer=layer,
        kind=kind,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        timeframe=effective_timeframe,
        partition_date=partition_date,
        file_stem=file_stem,
    )
    return atomic_write_path(
        path,
        lambda temp_path: prepared.to_parquet(temp_path, index=False),
    )


def write_normalized_dataframe(
    frame: pd.DataFrame,
    *,
    layout: DataLakeLayout,
    kind: DatasetKind,
    exchange: str,
    market_type: MarketType,
    symbol: str,
    partition_date: date | None = None,
    timeframe: str | None = None,
    file_stem: str | None = None,
    ohlcv_derivation: OHLCVDerivationPolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
) -> Path:
    normalized = normalize_dataset(
        kind,
        frame,
        ohlcv_derivation=ohlcv_derivation,
        duplicate_policy=duplicate_policy,
    )
    derived_partition = partition_date or normalized["ts"].max().date()
    return write_dataframe(
        normalized,
        layout=layout,
        layer="normalized",
        kind=kind,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        partition_date=derived_partition,
        timeframe=timeframe,
        file_stem=file_stem,
        duplicate_policy=DuplicatePolicy.ERROR,
    )
