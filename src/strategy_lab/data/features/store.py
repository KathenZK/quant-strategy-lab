from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.features.manifest import FactorArtifactManifest
from strategy_lab.data.fs import atomic_write_path
from strategy_lab.data.quality import DuplicatePolicy, DuplicateStats


@dataclass(slots=True)
class FeatureStore:
    layout: DataLakeLayout

    @staticmethod
    def _symbol_partition(symbol: str) -> str:
        return symbol.replace("/", "_").replace(":", "_").lower()

    def feature_root(
        self,
        factor_name: str,
        *,
        exchange: str | None = None,
        market_type: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        factor_version: str | None = None,
    ) -> Path:
        path = self.layout.features_dir / f"factor={factor_name}"
        if factor_version:
            path = path / f"version={factor_version}"
        if exchange:
            path = path / f"exchange={exchange.lower()}"
        if market_type:
            path = path / f"market_type={market_type.lower()}"
        if symbol:
            path = path / f"symbol={self._symbol_partition(symbol)}"
        if timeframe:
            path = path / f"timeframe={timeframe.lower()}"
        return path

    def manifest_root(self, factor_name: str) -> Path:
        return self.layout.features_dir / "_manifests" / f"factor={factor_name}"

    def write_factor_frame(
        self,
        factor_name: str,
        frame: pd.DataFrame,
        *,
        exchange: str | None = None,
        market_type: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        factor_version: str | None = None,
        file_stem: str = "part-0000",
    ) -> Path:
        if "ts" not in frame.columns:
            raise ValueError("factor frame must include ts column")
        partition_date = pd.to_datetime(frame["ts"], utc=True).max().date().isoformat()
        path = self.feature_root(
            factor_name,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
            factor_version=factor_version,
        ) / f"date={partition_date}" / f"{file_stem}.parquet"
        return atomic_write_path(path, lambda temp_path: frame.to_parquet(temp_path, index=False))

    def load_factor_frame(
        self,
        factor_name: str,
        *,
        exchange: str | None = None,
        market_type: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        factor_version: str | None = None,
        duplicate_policy: DuplicatePolicy = DuplicatePolicy.ERROR,
    ) -> pd.DataFrame:
        root = self.feature_root(factor_name, factor_version=factor_version)
        direct_root = self._direct_feature_root(
            factor_name,
            factor_version=factor_version,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
        )
        if direct_root is not None:
            files = sorted(direct_root.glob("**/*.parquet"))
        else:
            files = [
                path
                for path in sorted(root.glob("**/*.parquet"))
                if self._matches_feature_filters(
                    path,
                    exchange=exchange,
                    market_type=market_type,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            ]
        if not files and direct_root is not None and any((exchange, market_type, symbol, timeframe)):
            # Fall back to the old scan path so legacy non-canonical layouts remain readable.
            files = [
                path
                for path in sorted(root.glob("**/*.parquet"))
                if self._matches_feature_filters(
                    path,
                    exchange=exchange,
                    market_type=market_type,
                    symbol=symbol,
                    timeframe=timeframe,
                )
            ]
        if not files:
            return pd.DataFrame()
        parts = []
        for file_order, path in enumerate(files):
            part = pd.read_parquet(path)
            part["__source_file_order"] = file_order
            parts.append(part)
        frame = pd.concat(parts, ignore_index=True)
        if "ts" in frame.columns:
            frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
            dedup = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in frame.columns]
            duplicate_mask = frame.duplicated(subset=dedup, keep=False) if dedup else pd.Series(False, index=frame.index)
            duplicate_rows = int(duplicate_mask.sum())
            duplicate_groups = (
                int(frame.loc[duplicate_mask].groupby(dedup, dropna=False).ngroups)
                if duplicate_rows
                else 0
            )
            if duplicate_rows and duplicate_policy == DuplicatePolicy.ERROR:
                raise ValueError(
                    f"duplicate feature business keys: {duplicate_rows} rows "
                    f"across {duplicate_groups} key groups; keys={dedup}"
                )
            before = len(frame)
            if duplicate_rows:
                frame = frame.sort_values(
                    [*dedup, "__source_file_order"],
                    kind="stable",
                )
                frame = frame.drop_duplicates(subset=dedup, keep="last")
            frame = frame.sort_values([column for column in ("ts", "symbol") if column in frame.columns]).reset_index(drop=True)
            frame.attrs["duplicate_stats"] = DuplicateStats(
                policy=duplicate_policy,
                key_columns=tuple(dedup),
                duplicate_rows=duplicate_rows,
                duplicate_key_groups=duplicate_groups,
                dropped_rows=before - len(frame),
            ).to_dict()
        frame = frame.drop(columns="__source_file_order", errors="ignore")
        return frame

    def _direct_feature_root(
        self,
        factor_name: str,
        *,
        exchange: str | None,
        market_type: str | None,
        symbol: str | None,
        timeframe: str | None,
        factor_version: str | None,
    ) -> Path | None:
        if exchange is None:
            return self.feature_root(factor_name, factor_version=factor_version) if not any((market_type, symbol, timeframe)) else None
        if market_type is None and any((symbol, timeframe)):
            return None
        if symbol is None and timeframe is not None:
            return None
        return self.feature_root(
            factor_name,
            exchange=exchange,
            market_type=market_type,
            symbol=symbol,
            timeframe=timeframe,
            factor_version=factor_version,
        )

    def _matches_feature_filters(
        self,
        path: Path,
        *,
        exchange: str | None,
        market_type: str | None,
        symbol: str | None,
        timeframe: str | None,
    ) -> bool:
        parts = set(path.parts)
        filters = {
            "exchange": exchange.lower() if exchange else None,
            "market_type": market_type.lower() if market_type else None,
            "symbol": self._symbol_partition(symbol) if symbol else None,
            "timeframe": timeframe.lower() if timeframe else None,
        }
        return all(value is None or f"{key}={value}" in parts for key, value in filters.items())

    def write_manifest(self, manifest: FactorArtifactManifest) -> Path:
        partition_date = pd.Timestamp(manifest.input_end).date().isoformat()
        path = self.manifest_root(manifest.factor_name) / f"date={partition_date}" / f"{manifest.manifest_id}.json"
        return manifest.write(path)

    def load_manifests(self, factor_name: str | None = None) -> list[dict]:
        root = self.manifest_root(factor_name) if factor_name else self.layout.features_dir / "_manifests"
        files = sorted(root.glob("**/*.json"))
        manifests = []
        for path in files:
            manifests.append(json.loads(path.read_text(encoding="utf-8")))
        return manifests
