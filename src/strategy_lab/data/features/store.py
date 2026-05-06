from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import pandas as pd

from strategy_lab.data.lake import DataLakeLayout
from strategy_lab.data.features.manifest import FactorArtifactManifest
from strategy_lab.fs import atomic_write_path


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
    ) -> pd.DataFrame:
        root = self.feature_root(factor_name, factor_version=factor_version)
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
        frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
        if "ts" in frame.columns:
            frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
            dedup = [column for column in ("ts", "exchange", "symbol", "market_type", "timeframe") if column in frame.columns]
            if dedup:
                frame = frame.drop_duplicates(subset=dedup, keep="last")
            frame = frame.sort_values([column for column in ("ts", "symbol") if column in frame.columns]).reset_index(drop=True)
        return frame

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
