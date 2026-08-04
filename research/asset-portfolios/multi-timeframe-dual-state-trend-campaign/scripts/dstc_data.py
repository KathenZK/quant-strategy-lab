from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
DATA_ROOT = ROOT / "data"
EXCHANGE = "binance"
MARKET_TYPE = "perp"
TIMEFRAME = "15m"
SYMBOLS = {
    "BTC": "BTC/USDT:USDT",
    "ETH": "ETH/USDT:USDT",
    "HYPE": "HYPE/USDT:USDT",
}
CUTOFFS = {
    "BTC": pd.Timestamp("2026-08-03 11:45:00", tz="UTC"),
    "ETH": pd.Timestamp("2026-08-03 11:45:00", tz="UTC"),
    "HYPE": pd.Timestamp("2026-08-01 15:15:00", tz="UTC"),
}
COMPARE_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "vwap",
)
DATE_PARTITION = re.compile(r"(?:^|/)date=(\d{4}-\d{2}-\d{2})(?:/|$)")


@dataclass(frozen=True, slots=True)
class AssetData:
    asset: str
    symbol: str
    cutoff: pd.Timestamp
    bars15: pd.DataFrame
    funding15: pd.Series
    bars1h: pd.DataFrame
    bars4h: pd.DataFrame
    bars1d: pd.DataFrame
    quality: dict[str, Any]


def _symbol_stem(symbol: str) -> str:
    return symbol.replace("/", "_").replace(":", "_").lower()


def cutoff_scoped_files(root: Path, symbol: str, cutoff: pd.Timestamp) -> list[str]:
    """Return only daily parquet partitions at or before cutoff's UTC date.

    The HYPE prospective boundary is protected before DuckDB is invoked: files
    dated after the frozen cutoff are not passed to the query engine at all.
    """

    cutoff_date = cutoff.tz_convert("UTC").date().isoformat()
    files: list[str] = []
    for path in sorted(root.glob(f"date=*/symbol={_symbol_stem(symbol)}.parquet")):
        match = DATE_PARTITION.search(path.as_posix())
        if match is not None and match.group(1) <= cutoff_date:
            files.append(str(path))
    return files


def _read_parquet_cutoff(
    files: list[str],
    cutoff: pd.Timestamp,
    projection: str,
    *,
    timestamp_column: str = "ts",
) -> pd.DataFrame:
    if not files:
        return pd.DataFrame()
    sql = (
        f"SELECT {projection} FROM read_parquet(?, "
        "hive_partitioning = false, union_by_name = true) "
        f"WHERE {timestamp_column} <= ? ORDER BY {timestamp_column}"
    )
    with duckdb.connect() as connection:
        return connection.execute(sql, [files, cutoff.to_pydatetime()]).fetch_df()


def _layer_root(layer: str, kind: str, *, timeframe: str | None = None) -> Path:
    path = DATA_ROOT / layer / kind / f"exchange={EXCHANGE}" / f"market_type={MARKET_TYPE}"
    if timeframe is not None:
        path = path / f"timeframe={timeframe}"
    return path


def prepare_ohlcv(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    if frame.empty:
        return frame, 0
    out = frame.copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    duplicate_count = int(out["ts"].duplicated().sum())
    out = out.sort_values("ts").drop_duplicates("ts", keep="last").set_index("ts")
    for column in COMPARE_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out, duplicate_count


def load_cutoff_ohlcv(asset: str, layer: str) -> tuple[pd.DataFrame, int, int]:
    symbol = SYMBOLS[asset]
    cutoff = CUTOFFS[asset]
    files = cutoff_scoped_files(
        _layer_root(layer, "ohlcv", timeframe=TIMEFRAME), symbol, cutoff
    )
    projection = (
        "ts, open, high, low, close, volume, quote_volume, trade_count, "
        "vwap, is_closed, source, timeframe"
    )
    frame = _read_parquet_cutoff(files, cutoff, projection)
    prepared, duplicates = prepare_ohlcv(frame)
    if not prepared.empty:
        prepared = prepared.loc[prepared["is_closed"].fillna(False).astype(bool)]
    return prepared, duplicates, len(files)


def load_cutoff_funding(asset: str, bars_index: pd.DatetimeIndex) -> tuple[pd.Series, dict[str, Any]]:
    symbol = SYMBOLS[asset]
    cutoff = CUTOFFS[asset]
    files = cutoff_scoped_files(_layer_root("normalized", "funding_rates"), symbol, cutoff)
    frame = _read_parquet_cutoff(files, cutoff, "ts, funding_rate, source")
    if frame.empty:
        return (
            pd.Series(0.0, index=bars_index, name="funding_rate"),
            {"rows": 0, "files_scoped": len(files), "accepted": False},
        )
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True).dt.floor("15min")
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    duplicate_count = int(frame["ts"].duplicated().sum())
    rates = (
        frame.sort_values("ts")
        .drop_duplicates("ts", keep="last")
        .set_index("ts")["funding_rate"]
    )
    aligned = rates.reindex(bars_index).fillna(0.0).rename("funding_rate")
    quality = {
        "rows": int(len(frame)),
        "files_scoped": len(files),
        "start": frame["ts"].min().isoformat(),
        "end": frame["ts"].max().isoformat(),
        "duplicate_ts_before_dedup": duplicate_count,
        "null_rates": int(frame["funding_rate"].isna().sum()),
        "non_zero_aligned_rows": int(aligned.ne(0.0).sum()),
        "aligned_sum_rate": float(aligned.sum()),
    }
    quality["accepted"] = bool(
        duplicate_count == 0 and quality["null_rates"] == 0 and quality["rows"] > 0
    )
    return aligned, quality


def aggregate_complete(frame: pd.DataFrame, rule: str, expected_bars: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    grouped = frame.resample(rule, label="left", closed="left")
    bars = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        source_bars=("close", "count"),
    )
    incomplete = bars.loc[bars["source_bars"].ne(expected_bars)]
    bars = bars.loc[bars["source_bars"].eq(expected_bars)].copy()
    delta = pd.Timedelta(minutes=15 * expected_bars)
    bars.index = bars.index + delta
    invalid = bars["high"].lt(bars[["open", "close", "low"]].max(axis=1)) | bars[
        "low"
    ].gt(bars[["open", "close", "high"]].min(axis=1))
    expected = (
        pd.date_range(bars.index.min(), bars.index.max(), freq=rule, tz="UTC")
        if not bars.empty
        else pd.DatetimeIndex([], tz="UTC")
    )
    missing = expected.difference(bars.index)
    quality = {
        "rows": int(len(bars)),
        "visible_start": bars.index.min().isoformat() if not bars.empty else None,
        "visible_end": bars.index.max().isoformat() if not bars.empty else None,
        "source_bars_required": expected_bars,
        "incomplete_edge_or_gap_bins_excluded": int(len(incomplete)),
        "missing_complete_bins": int(len(missing)),
        "invalid_ohlc_rows": int(invalid.sum()),
        "availability": f"bar-open timestamp shifted +{delta} to earliest causal visibility",
    }
    quality["accepted"] = bool(not bars.empty and not invalid.any() and len(missing) == 0)
    return bars, quality


def _raw_normalized_quality(raw: pd.DataFrame, normalized: pd.DataFrame) -> dict[str, Any]:
    common = raw.index.intersection(normalized.index)
    max_diff: dict[str, float | None] = {}
    for column in COMPARE_COLUMNS:
        diff = (raw.loc[common, column] - normalized.loc[common, column]).abs()
        value = float(diff.max()) if len(diff) else math.nan
        max_diff[column] = value if np.isfinite(value) else None
    accepted = bool(
        len(raw) == len(normalized) == len(common)
        and all(value is not None and value <= 1e-10 for value in max_diff.values())
    )
    return {
        "available": bool(len(raw)),
        "accepted": accepted,
        "raw_rows": int(len(raw)),
        "normalized_rows": int(len(normalized)),
        "common_rows": int(len(common)),
        "max_abs_diff": max_diff,
    }


def load_asset(asset: str) -> AssetData:
    if asset not in SYMBOLS:
        raise KeyError(f"unsupported asset: {asset}")
    normalized, normalized_duplicates, normalized_files = load_cutoff_ohlcv(asset, "normalized")
    raw, raw_duplicates, raw_files = load_cutoff_ohlcv(asset, "raw")
    if normalized.empty:
        raise RuntimeError(f"missing normalized cutoff-safe 15m data for {asset}")

    expected = pd.date_range(normalized.index.min(), normalized.index.max(), freq="15min", tz="UTC")
    missing = expected.difference(normalized.index)
    nulls = {column: int(normalized[column].isna().sum()) for column in COMPARE_COLUMNS}
    invalid = (
        normalized["high"].lt(normalized[["open", "close", "low"]].max(axis=1))
        | normalized["low"].gt(normalized[["open", "close", "high"]].min(axis=1))
        | normalized["volume"].lt(0.0)
    )
    parity = _raw_normalized_quality(raw, normalized)
    funding, funding_quality = load_cutoff_funding(asset, normalized.index)
    bars1h, quality1h = aggregate_complete(normalized, "1h", 4)
    bars4h, quality4h = aggregate_complete(normalized, "4h", 16)
    bars1d, quality1d = aggregate_complete(normalized, "1D", 96)
    source_quality = {
        "symbol": SYMBOLS[asset],
        "cutoff": CUTOFFS[asset].isoformat(),
        "rows": int(len(normalized)),
        "start": normalized.index.min().isoformat(),
        "end": normalized.index.max().isoformat(),
        "normalized_files_scoped": normalized_files,
        "raw_files_scoped": raw_files,
        "normalized_duplicate_ts": normalized_duplicates,
        "raw_duplicate_ts": raw_duplicates,
        "missing_15m_bars": int(len(missing)),
        "first_missing_15m_bars": [ts.isoformat() for ts in missing[:10]],
        "critical_nulls": nulls,
        "invalid_ohlcv_rows": int(invalid.sum()),
        "is_utc_index": str(normalized.index.tz) == "UTC",
        "last_bar_not_after_cutoff": bool(normalized.index.max() <= CUTOFFS[asset]),
        "raw_vs_normalized": parity,
        "funding": funding_quality,
    }
    source_quality["accepted"] = bool(
        normalized_duplicates == 0
        and raw_duplicates == 0
        and len(missing) == 0
        and sum(nulls.values()) == 0
        and not invalid.any()
        and source_quality["is_utc_index"]
        and source_quality["last_bar_not_after_cutoff"]
        and parity["accepted"]
        and funding_quality["accepted"]
    )
    quality = {
        "source": source_quality,
        "1h": quality1h,
        "4h": quality4h,
        "1d": quality1d,
    }
    if not all(section["accepted"] for section in quality.values()):
        raise RuntimeError(f"data quality blocker for {asset}: {quality}")
    keep = ["open", "high", "low", "close", "volume"]
    return AssetData(
        asset=asset,
        symbol=SYMBOLS[asset],
        cutoff=CUTOFFS[asset],
        bars15=normalized[keep].copy(),
        funding15=funding,
        bars1h=bars1h,
        bars4h=bars4h,
        bars1d=bars1d,
        quality=quality,
    )


def load_assets() -> dict[str, AssetData]:
    return {asset: load_asset(asset) for asset in ("BTC", "ETH", "HYPE")}
