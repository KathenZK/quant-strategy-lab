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
    source: str | None = None,
    file_stem: str | None = None,
    ohlcv_derivation: OHLCVDerivationPolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
) -> Path:
    prepared = frame.copy()
    identity = {
        "exchange": exchange,
        "market_type": market_type.value,
        "symbol": symbol,
    }
    if timeframe is not None:
        identity["timeframe"] = timeframe.lower()
    if source is not None:
        identity["source"] = source.lower()
    if kind == DatasetKind.OHLCV and timeframe is None:
        raise ValueError(
            "OHLCV writes require an explicit timeframe partition identity"
        )
    for column, expected in identity.items():
        if column in prepared.columns:
            actual = prepared[column].astype("string").str.strip()
            compare_actual = actual.str.lower() if column != "symbol" else actual
            compare_expected = expected.lower() if column != "symbol" else expected
            mismatches = compare_actual.ne(compare_expected)
            if mismatches.any():
                values = sorted(actual.loc[mismatches].dropna().unique().tolist())
                raise ValueError(
                    f"{column} values do not match write partition {expected!r}: {values}"
                )
        else:
            prepared[column] = expected
    if kind == DatasetKind.OHLCV:
        if layer == "raw" and ohlcv_derivation is not None:
            raise ValueError("raw OHLCV writes cannot contain derived proxy fields")
        prepared = derive_ohlcv_columns(prepared, ohlcv_derivation)
    prepared, duplicate_stats = resolve_duplicates(
        kind,
        prepared,
        policy=duplicate_policy,
    )
    validate_frame(kind, prepared)
    if "ts" in prepared.columns:
        row_dates = pd.to_datetime(prepared["ts"], utc=True, errors="raise").dt.date
        if not row_dates.eq(partition_date).all():
            values = sorted(str(value) for value in row_dates.unique())
            raise ValueError(
                f"rows span dates {values}, cannot write to partition {partition_date}"
            )
    prepared.attrs["duplicate_stats"] = duplicate_stats.to_dict()
    effective_timeframe = _infer_timeframe(prepared, timeframe)
    path = layout.dataset_path(
        layer=layer,
        kind=kind,
        exchange=exchange,
        market_type=market_type,
        symbol=symbol,
        timeframe=effective_timeframe,
        source=source,
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
    source: str | None = None,
    file_stem: str | None = None,
    ohlcv_derivation: OHLCVDerivationPolicy | None = None,
    duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
) -> tuple[Path, ...]:
    normalized = normalize_dataset(
        kind,
        frame,
        ohlcv_derivation=ohlcv_derivation,
        duplicate_policy=duplicate_policy,
    )
    if partition_date is not None:
        groups = [(partition_date, normalized)]
    else:
        timestamps = pd.to_datetime(normalized["ts"], utc=True, errors="raise")
        groups = normalized.groupby(timestamps.dt.date, sort=True)
    return tuple(
        write_dataframe(
            day.reset_index(drop=True),
            layout=layout,
            layer="normalized",
            kind=kind,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            partition_date=derived_partition,
            timeframe=timeframe,
            source=source,
            file_stem=file_stem,
            duplicate_policy=DuplicatePolicy.ERROR,
        )
        for derived_partition, day in groups
    )
