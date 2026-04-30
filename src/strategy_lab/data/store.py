from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.models import DatasetKind, MarketType, dataset_specs
from strategy_lab.data.normalize import normalize_dataset
from strategy_lab.fs import atomic_write_path


def _infer_timeframe(frame: pd.DataFrame, timeframe: str | None) -> str | None:
    if timeframe:
        return timeframe
    if "timeframe" not in frame.columns:
        return None
    values = frame["timeframe"].dropna().astype(str).str.lower().unique()
    return str(values[0]) if len(values) == 1 else None


def validate_frame(kind: DatasetKind, frame: pd.DataFrame) -> None:
    spec = dataset_specs()[kind]
    missing = [column for column in spec.required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"missing required columns for {kind.value}: {missing}")


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
) -> Path:
    if timeframe:
        frame = frame.copy()
        frame["timeframe"] = timeframe.lower()
    validate_frame(kind, frame)
    effective_timeframe = _infer_timeframe(frame, timeframe)
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
    return atomic_write_path(path, lambda temp_path: frame.to_parquet(temp_path, index=False))


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
) -> Path:
    normalized = normalize_dataset(kind, frame)
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
    )
