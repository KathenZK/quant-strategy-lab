from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import shutil

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.models import DatasetKind, MarketType
from strategy_lab.data.store import write_dataframe
from strategy_lab.fs import atomic_write_path


CANONICAL_DATA_DIRS = {
    "raw",
    "normalized",
    "features",
    "quality",
    "snapshots",
    "checkpoints",
    "logs",
    "_archive",
    "_state",
}


@dataclass(frozen=True, slots=True)
class DataLakeMigrationRecord:
    source_path: str
    target_path: str | None
    layer: str
    kind: str
    rows: int
    action: str
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class DataLakeMigrationSummary:
    root_dir: str
    dry_run: bool
    archive_legacy: bool
    legacy_roots: list[str]
    records: list[DataLakeMigrationRecord] = field(default_factory=list)

    @property
    def copied(self) -> int:
        return sum(1 for record in self.records if record.action == "copy")

    @property
    def skipped(self) -> int:
        return sum(1 for record in self.records if record.action == "skip")

    @property
    def failed(self) -> int:
        return sum(1 for record in self.records if record.action == "failed")

    def to_dict(self) -> dict[str, object]:
        return {
            "root_dir": self.root_dir,
            "dry_run": self.dry_run,
            "archive_legacy": self.archive_legacy,
            "legacy_roots": self.legacy_roots,
            "copied": self.copied,
            "skipped": self.skipped,
            "failed": self.failed,
            "records": [asdict(record) for record in self.records],
        }


def _dataset_kind_from_dir(value: str) -> DatasetKind | None:
    for kind in DatasetKind:
        if kind.value == value:
            return kind
    return None


def _partition_value(path: Path, key: str) -> str | None:
    prefix = f"{key}="
    for part in path.parts:
        if part.startswith(prefix):
            return part.removeprefix(prefix)
    return None


def _symbol_file_stem(symbol: str) -> str:
    return f"symbol={symbol.replace('/', '_').replace(':', '_').lower()}"


def _feature_path(
    layout: DataLakeLayout,
    *,
    factor_name: str,
    factor_version: str,
    exchange: str,
    market_type: str,
    symbol: str,
    timeframe: str | None,
    partition_date: str,
) -> Path:
    path = (
        layout.features_dir
        / f"factor={factor_name}"
        / f"version={factor_version}"
        / f"exchange={exchange.lower()}"
        / f"market_type={market_type.lower()}"
        / f"symbol={symbol.replace('/', '_').replace(':', '_').lower()}"
    )
    if timeframe:
        path = path / f"timeframe={timeframe.lower()}"
    return path / f"date={partition_date}" / f"{_symbol_file_stem(symbol)}.parquet"


def _infer_profile_timeframe(profile_name: str, kind: DatasetKind, frame: pd.DataFrame, path: Path) -> str | None:
    if "timeframe" in frame.columns:
        values = frame["timeframe"].dropna().astype(str).str.lower().unique()
        if len(values) == 1:
            return str(values[0])
    path_timeframe = _partition_value(path, "timeframe")
    if path_timeframe:
        return path_timeframe.lower()
    if kind not in {DatasetKind.OHLCV, DatasetKind.OPEN_INTEREST, DatasetKind.BASIS}:
        return None
    if "daily" in profile_name:
        return "1d"
    if "4h" in profile_name:
        return "4h"
    if "1h" in profile_name:
        return "1h"
    return "1h"


def _date_series(frame: pd.DataFrame) -> pd.Series:
    if "date" in frame.columns:
        return frame["date"].astype(str)
    return pd.to_datetime(frame["ts"], utc=True).dt.date.astype(str)


def _legacy_profile_roots(root_dir: Path) -> list[Path]:
    if not root_dir.exists():
        return []
    roots = []
    for candidate in sorted(root_dir.iterdir()):
        if not candidate.is_dir() or candidate.name in CANONICAL_DATA_DIRS:
            continue
        if any((candidate / layer).exists() for layer in ("raw", "normalized", "features")):
            roots.append(candidate)
    return roots


class DataLakeMigrator:
    def __init__(self, layout: DataLakeLayout) -> None:
        self.layout = layout

    def legacy_roots(self) -> list[Path]:
        return _legacy_profile_roots(self.layout.root_dir)

    def migrate(
        self,
        *,
        dry_run: bool = True,
        archive_legacy: bool = False,
        report_path: Path | None = None,
    ) -> DataLakeMigrationSummary:
        records: list[DataLakeMigrationRecord] = []
        legacy_roots = self.legacy_roots()
        for root in legacy_roots:
            records.extend(self._migrate_profile(root, dry_run=dry_run))

        if archive_legacy and not dry_run:
            archive_root = self.layout.root_dir / "_archive" / "legacy-profiles"
            archive_root.mkdir(parents=True, exist_ok=True)
            for root in legacy_roots:
                target = archive_root / root.name
                if target.exists():
                    target = archive_root / f"{root.name}.{pd.Timestamp.now(tz='UTC').strftime('%Y%m%dT%H%M%SZ')}"
                shutil.move(str(root), str(target))

        summary = DataLakeMigrationSummary(
            root_dir=str(self.layout.root_dir),
            dry_run=dry_run,
            archive_legacy=archive_legacy,
            legacy_roots=[str(path) for path in legacy_roots],
            records=records,
        )
        if report_path is not None:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8")
        return summary

    def _migrate_profile(self, profile_root: Path, *, dry_run: bool) -> list[DataLakeMigrationRecord]:
        records: list[DataLakeMigrationRecord] = []
        for layer in ("raw", "normalized"):
            layer_root = profile_root / layer
            if not layer_root.exists():
                continue
            for path in sorted(layer_root.rglob("*.parquet")):
                records.extend(self._migrate_dataset_file(profile_root, layer, path, dry_run=dry_run))

        feature_root = profile_root / "features"
        if feature_root.exists():
            for path in sorted(feature_root.rglob("*.parquet")):
                records.extend(self._migrate_feature_file(profile_root, path, dry_run=dry_run))
        return records

    def _migrate_dataset_file(
        self,
        profile_root: Path,
        layer: str,
        path: Path,
        *,
        dry_run: bool,
    ) -> list[DataLakeMigrationRecord]:
        try:
            relative = path.relative_to(profile_root / layer)
            kind = _dataset_kind_from_dir(relative.parts[0])
            if kind is None:
                return [self._skip(path, layer, "unknown", "unsupported dataset kind")]
            frame = pd.read_parquet(path)
            if frame.empty:
                return [self._skip(path, layer, kind.value, "empty parquet")]
            return self._write_dataset_groups(
                profile_name=profile_root.name,
                source_path=path,
                layer=layer,
                kind=kind,
                frame=frame,
                dry_run=dry_run,
            )
        except Exception as exc:
            return [self._failed(path, layer, "unknown", exc)]

    def _write_dataset_groups(
        self,
        *,
        profile_name: str,
        source_path: Path,
        layer: str,
        kind: DatasetKind,
        frame: pd.DataFrame,
        dry_run: bool,
    ) -> list[DataLakeMigrationRecord]:
        working = frame.copy()
        timeframe = _infer_profile_timeframe(profile_name, kind, working, source_path)
        if timeframe:
            working["timeframe"] = timeframe
        if "date" not in working.columns and "ts" in working.columns:
            working["date"] = _date_series(working)
        group_columns = [column for column in ("exchange", "market_type", "symbol", "timeframe", "date") if column in working.columns]
        if not {"exchange", "market_type", "symbol", "date"} <= set(group_columns):
            return [self._skip(source_path, layer, kind.value, "missing canonical grouping columns")]

        records: list[DataLakeMigrationRecord] = []
        for keys, group in working.groupby(group_columns, dropna=False, sort=False):
            key_map = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,), strict=True))
            market_type = MarketType(str(key_map["market_type"]))
            target = self.layout.dataset_path(
                layer=layer,
                kind=kind,
                exchange=str(key_map["exchange"]),
                market_type=market_type,
                symbol=str(key_map["symbol"]),
                timeframe=str(key_map["timeframe"]) if "timeframe" in key_map and pd.notna(key_map["timeframe"]) else None,
                partition_date=pd.Timestamp(str(key_map["date"])).date(),
            )
            if not dry_run:
                write_dataframe(
                    group.reset_index(drop=True),
                    layout=self.layout,
                    layer=layer,
                    kind=kind,
                    exchange=str(key_map["exchange"]),
                    market_type=market_type,
                    symbol=str(key_map["symbol"]),
                    timeframe=str(key_map["timeframe"]) if "timeframe" in key_map and pd.notna(key_map["timeframe"]) else None,
                    partition_date=pd.Timestamp(str(key_map["date"])).date(),
                )
            records.append(
                DataLakeMigrationRecord(
                    source_path=str(source_path),
                    target_path=str(target),
                    layer=layer,
                    kind=kind.value,
                    rows=int(len(group)),
                    action="copy",
                )
            )
        return records

    def _migrate_feature_file(self, profile_root: Path, path: Path, *, dry_run: bool) -> list[DataLakeMigrationRecord]:
        factor_name = _partition_value(path, "factor")
        if factor_name is None:
            return [self._skip(path, "features", "feature", "missing factor partition")]
        try:
            frame = pd.read_parquet(path)
            if frame.empty:
                return [self._skip(path, "features", factor_name, "empty parquet")]
            timeframe = _infer_profile_timeframe(profile_root.name, DatasetKind.OHLCV, frame, path)
            if timeframe:
                frame = frame.copy()
                frame["timeframe"] = timeframe
            group_columns = [column for column in ("exchange", "market_type", "symbol", "timeframe") if column in frame.columns]
            if not {"exchange", "market_type", "symbol"} <= set(group_columns):
                return [self._skip(path, "features", factor_name, "missing feature identity columns")]

            records: list[DataLakeMigrationRecord] = []
            for keys, group in frame.groupby(group_columns, dropna=False, sort=False):
                key_map = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,), strict=True))
                target = _feature_path(
                    self.layout,
                    factor_name=factor_name,
                    factor_version="legacy",
                    exchange=str(key_map["exchange"]),
                    market_type=str(key_map["market_type"]),
                    symbol=str(key_map["symbol"]),
                    timeframe=str(key_map["timeframe"]) if "timeframe" in key_map and pd.notna(key_map["timeframe"]) else None,
                    partition_date=pd.to_datetime(group["ts"], utc=True).max().date().isoformat(),
                )
                if not dry_run:
                    output = group.reset_index(drop=True)
                    atomic_write_path(target, lambda temp_path: output.to_parquet(temp_path, index=False))
                records.append(
                    DataLakeMigrationRecord(
                        source_path=str(path),
                        target_path=str(target),
                        layer="features",
                        kind=factor_name,
                        rows=int(len(group)),
                        action="copy",
                    )
                )
            return records
        except Exception as exc:
            return [self._failed(path, "features", factor_name, exc)]

    @staticmethod
    def _skip(path: Path, layer: str, kind: str, reason: str) -> DataLakeMigrationRecord:
        return DataLakeMigrationRecord(
            source_path=str(path),
            target_path=None,
            layer=layer,
            kind=kind,
            rows=0,
            action="skip",
            reason=reason,
        )

    @staticmethod
    def _failed(path: Path, layer: str, kind: str, exc: Exception) -> DataLakeMigrationRecord:
        return DataLakeMigrationRecord(
            source_path=str(path),
            target_path=None,
            layer=layer,
            kind=kind,
            rows=0,
            action="failed",
            reason=f"{type(exc).__name__}: {exc}",
        )
