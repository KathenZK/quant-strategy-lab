#!/usr/bin/env python3
"""Migrate legacy MU equity candles into the unified raw OHLCV lake."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile

import pandas as pd
from pandas.testing import assert_frame_equal


ROOT = Path(__file__).resolve().parents[3]
LEGACY_ROOT = ROOT / "data/external/us_equities"
RAW_OHLCV_ROOT = ROOT / "data/raw/ohlcv"
DEFAULT_MANIFEST = (
    ROOT / "research/mu/artifacts/mu-equity-ohlcv-migration-2026-08-05.json"
)
CORE_COLUMNS = ("ts", "open", "high", "low", "close", "volume")
STANDARD_COLUMNS = (
    "ts",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
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
)


@dataclass(frozen=True, slots=True)
class SourceDataset:
    path: Path
    companion_csv: Path
    source: str
    timeframe: str
    source_dataset_id: str
    adjustment: str
    session_scope: str


DATASETS = (
    SourceDataset(
        path=LEGACY_ROOT / "polygon/symbol=mu/timeframe=15m/"
        "mu_15m_2025-06-17_2026-06-17_adjusted.parquet",
        companion_csv=LEGACY_ROOT / "polygon/symbol=mu/timeframe=15m/"
        "mu_15m_2025-06-17_2026-06-17_adjusted.csv",
        source="polygon_api",
        timeframe="15m",
        source_dataset_id="polygon-mu-15m-adjusted-2025-06-17-2026-06-17",
        adjustment="provider_adjusted",
        session_scope="extended_hours_04:00-20:00_America/New_York",
    ),
    SourceDataset(
        path=LEGACY_ROOT / "yahoo/symbol=mu/timeframe=15m/"
        "mu_15m_60d_include_prepost.parquet",
        companion_csv=LEGACY_ROOT / "yahoo/symbol=mu/timeframe=15m/"
        "mu_15m_60d_include_prepost.csv",
        source="yahoo_finance",
        timeframe="15m",
        source_dataset_id="yahoo-mu-15m-60d-include-prepost",
        adjustment="provider_default_unverified",
        session_scope="include_prepost",
    ),
    SourceDataset(
        path=LEGACY_ROOT / "yahoo/symbol=mu/timeframe=1d/mu_1d_1y.parquet",
        companion_csv=LEGACY_ROOT / "yahoo/symbol=mu/timeframe=1d/mu_1d_1y.csv",
        source="yahoo_finance",
        timeframe="1d",
        source_dataset_id="yahoo-mu-1d-1y",
        adjustment="ohlc_provider_default_with_adj_close_retained",
        session_scope="regular_session_daily",
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_csv_matches_frame(csv_path: Path, frame: pd.DataFrame) -> None:
    csv_frame = pd.read_csv(csv_path)
    csv_frame["ts"] = pd.to_datetime(csv_frame["ts"], utc=True, errors="raise")
    columns = list(csv_frame.columns)
    actual = frame[columns].sort_values("ts").reset_index(drop=True)
    expected = csv_frame.sort_values("ts").reset_index(drop=True)
    assert_frame_equal(
        actual,
        expected,
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def load_and_audit(dataset: SourceDataset) -> tuple[pd.DataFrame, dict[str, object]]:
    if not dataset.path.is_file():
        raise FileNotFoundError(f"missing legacy dataset: {dataset.path}")
    frame = pd.read_parquet(dataset.path)
    missing_core = [column for column in CORE_COLUMNS if column not in frame.columns]
    if missing_core:
        raise ValueError(f"{dataset.path}: missing core OHLCV columns {missing_core}")

    prepared = frame.copy()
    prepared["ts"] = pd.to_datetime(prepared["ts"], utc=True, errors="raise")
    if dataset.companion_csv.is_file():
        assert_csv_matches_frame(dataset.companion_csv, prepared)
    nulls = {
        column: int(prepared[column].isna().sum())
        for column in CORE_COLUMNS
        if prepared[column].isna().any()
    }
    if nulls:
        raise ValueError(f"{dataset.path}: core OHLCV nulls {nulls}")
    duplicate_rows = int(prepared.duplicated("ts", keep=False).sum())
    if duplicate_rows:
        raise ValueError(f"{dataset.path}: duplicate timestamps {duplicate_rows}")

    invalid_ohlc = (
        prepared["high"].lt(prepared[["open", "close", "low"]].max(axis=1))
        | prepared["low"].gt(prepared[["open", "close", "high"]].min(axis=1))
        | prepared[["open", "high", "low", "close"]].le(0).any(axis=1)
        | prepared["volume"].lt(0)
    )
    if invalid_ohlc.any():
        raise ValueError(
            f"{dataset.path}: invalid OHLCV rows {int(invalid_ohlc.sum())}"
        )

    off_grid_rows = 0
    if dataset.timeframe == "15m":
        timestamps = prepared["ts"]
        off_grid_rows = int(
            (
                timestamps.dt.minute.mod(15).ne(0)
                | timestamps.dt.second.ne(0)
                | timestamps.dt.microsecond.ne(0)
            ).sum()
        )

    prepared["exchange"] = "nasdaq"
    prepared["symbol"] = "MU"
    prepared["market_type"] = "equity"
    prepared["timeframe"] = dataset.timeframe
    prepared["source"] = dataset.source
    prepared["source_dataset_id"] = dataset.source_dataset_id
    prepared["adjustment"] = dataset.adjustment
    prepared["session_scope"] = dataset.session_scope
    prepared["quality_status"] = "raw_unaccepted"

    audit = {
        "source_file": dataset.path.relative_to(ROOT).as_posix(),
        "source_sha256": sha256(dataset.path),
        "companion_csv": dataset.companion_csv.relative_to(ROOT).as_posix(),
        "companion_csv_sha256": (
            sha256(dataset.companion_csv) if dataset.companion_csv.is_file() else None
        ),
        "companion_csv_equivalent": dataset.companion_csv.is_file(),
        "source": dataset.source,
        "source_dataset_id": dataset.source_dataset_id,
        "timeframe": dataset.timeframe,
        "rows": len(prepared),
        "start": prepared["ts"].min().isoformat(),
        "end": prepared["ts"].max().isoformat(),
        "duplicate_rows": duplicate_rows,
        "core_nulls": nulls,
        "invalid_ohlc_rows": int(invalid_ohlc.sum()),
        "off_grid_rows": off_grid_rows,
        "missing_standard_columns": sorted(set(STANDARD_COLUMNS) - set(frame.columns)),
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
    }
    return prepared.sort_values("ts").reset_index(drop=True), audit


def destination_path(dataset: SourceDataset, partition_date: str) -> Path:
    return (
        RAW_OHLCV_ROOT
        / "exchange=nasdaq"
        / "market_type=equity"
        / f"timeframe={dataset.timeframe}"
        / f"source={dataset.source}"
        / f"date={partition_date}"
        / "symbol=mu.parquet"
    )


def atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".parquet.tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_dataset(
    dataset: SourceDataset,
    frame: pd.DataFrame,
) -> tuple[list[Path], dict[str, object]]:
    written: list[Path] = []
    original_columns = list(pd.read_parquet(dataset.path).columns)
    partition_dates = frame["ts"].dt.date.astype("string")
    for partition_date, day in frame.groupby(partition_dates, sort=True):
        path = destination_path(dataset, str(partition_date))
        if path.exists():
            raise FileExistsError(f"destination already exists: {path}")
        atomic_write_parquet(day.reset_index(drop=True), path)
        written.append(path)

    round_trip = (
        pd.concat(
            [pd.read_parquet(path) for path in written],
            ignore_index=True,
        )
        .sort_values("ts")
        .reset_index(drop=True)
    )
    expected = frame.sort_values("ts").reset_index(drop=True)
    assert_frame_equal(
        round_trip[original_columns],
        expected[original_columns],
        check_dtype=True,
        check_like=False,
    )
    destination_rows = sum(
        len(pd.read_parquet(path, columns=["ts"])) for path in written
    )
    if destination_rows != len(frame):
        raise ValueError(
            f"{dataset.source_dataset_id}: destination row mismatch "
            f"{destination_rows} != {len(frame)}"
        )
    result = {
        "destination_root": written[0].parents[1].relative_to(ROOT).as_posix(),
        "destination_files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "rows": len(pd.read_parquet(path, columns=["ts"])),
            }
            for path in written
        ],
        "destination_rows": destination_rows,
        "round_trip_verified": True,
    }
    return written, result


def atomic_write_json(payload: dict[str, object], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".json.tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def remove_legacy_sources(paths: list[Path]) -> None:
    for path in paths:
        path.unlink()
    directories = sorted(
        (path for path in LEGACY_ROOT.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass
    for directory in (LEGACY_ROOT, LEGACY_ROOT.parent):
        try:
            directory.rmdir()
        except OSError:
            pass


def verify_existing_migration(manifest_path: Path, *, cleanup_companions: bool) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    records = {
        record["source_dataset_id"]: record for record in payload.get("datasets", [])
    }
    for dataset in DATASETS:
        record = records.get(dataset.source_dataset_id)
        if record is None:
            raise ValueError(f"manifest missing {dataset.source_dataset_id}")
        destination_frames: list[pd.DataFrame] = []
        destination_rows = 0
        for item in record.get("destination_files", []):
            path = ROOT / item["path"]
            if not path.is_file():
                raise FileNotFoundError(f"missing destination file: {path}")
            if sha256(path) != item["sha256"]:
                raise ValueError(f"destination hash mismatch: {path}")
            frame = pd.read_parquet(path)
            if len(frame) != item["rows"]:
                raise ValueError(f"destination row mismatch: {path}")
            destination_rows += len(frame)
            destination_frames.append(frame)
        if destination_rows != record["destination_rows"]:
            raise ValueError(f"destination total mismatch: {dataset.source_dataset_id}")
        destination = pd.concat(destination_frames, ignore_index=True)
        if dataset.companion_csv.is_file():
            assert_csv_matches_frame(dataset.companion_csv, destination)
            record["companion_csv"] = dataset.companion_csv.relative_to(ROOT).as_posix()
            record["companion_csv_sha256"] = sha256(dataset.companion_csv)
            record["companion_csv_equivalent"] = True

    if cleanup_companions:
        for dataset in DATASETS:
            dataset.companion_csv.unlink(missing_ok=True)
        remove_legacy_sources([])
        payload["legacy_source_removed"] = all(
            not dataset.path.exists() and not dataset.companion_csv.exists()
            for dataset in DATASETS
        )
        atomic_write_json(payload, manifest_path)
    print(
        f"verified {sum(record['destination_rows'] for record in records.values())} "
        f"destination rows from {len(records)} datasets"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--remove-source", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--cleanup-companions", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    if args.remove_source and not args.apply:
        raise SystemExit("--remove-source requires --apply")
    if args.cleanup_companions and not args.verify_existing:
        raise SystemExit("--cleanup-companions requires --verify-existing")
    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    if args.verify_existing:
        verify_existing_migration(
            manifest_path,
            cleanup_companions=args.cleanup_companions,
        )
        return 0

    audited: list[tuple[SourceDataset, pd.DataFrame, dict[str, object]]] = []
    for dataset in DATASETS:
        frame, audit = load_and_audit(dataset)
        audited.append((dataset, frame, audit))

    if not args.apply:
        print(
            json.dumps(
                {
                    "mode": "dry-run",
                    "destination_root": RAW_OHLCV_ROOT.relative_to(ROOT).as_posix(),
                    "datasets": [audit for _, _, audit in audited],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    written_paths: list[Path] = []
    records: list[dict[str, object]] = []
    try:
        for dataset, frame, audit in audited:
            paths, result = write_dataset(dataset, frame)
            written_paths.extend(paths)
            records.append({**audit, **result})
    except Exception:
        for path in written_paths:
            path.unlink(missing_ok=True)
        raise

    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "migration": "legacy data/external/us_equities -> unified data/raw/ohlcv",
        "market_identity": {
            "exchange": "nasdaq",
            "market_type": "equity",
            "symbol": "MU",
        },
        "quality_status": "raw_unaccepted",
        "accepted_for_strategy_evidence": False,
        "datasets": records,
    }
    manifest["legacy_source_removed"] = False
    atomic_write_json(manifest, manifest_path)
    if args.remove_source:
        remove_legacy_sources(
            [
                path
                for dataset, _, _ in audited
                for path in (dataset.path, dataset.companion_csv)
            ]
        )
        manifest["legacy_source_removed"] = all(
            not dataset.path.exists() and not dataset.companion_csv.exists()
            for dataset, _, _ in audited
        )
        atomic_write_json(manifest, manifest_path)
    print(
        f"migrated {sum(record['destination_rows'] for record in records)} rows "
        f"into {len(written_paths)} daily partitions; manifest={manifest_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
