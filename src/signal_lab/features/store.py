from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from signal_lab.data.lake import DataLakeLayout


@dataclass(slots=True)
class FeatureStore:
    layout: DataLakeLayout

    def feature_root(self, factor_name: str) -> Path:
        return self.layout.features_dir / f"factor={factor_name}"

    def write_factor_frame(self, factor_name: str, frame: pd.DataFrame, *, file_stem: str = "part-0000") -> Path:
        if "ts" not in frame.columns:
            raise ValueError("factor frame must include ts column")
        partition_date = pd.to_datetime(frame["ts"], utc=True).max().date().isoformat()
        path = self.feature_root(factor_name) / f"date={partition_date}" / f"{file_stem}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        return path

    def load_factor_frame(self, factor_name: str) -> pd.DataFrame:
        root = self.feature_root(factor_name)
        files = list(root.glob("**/*.parquet"))
        if not files:
            return pd.DataFrame()
        return pd.concat((pd.read_parquet(path) for path in sorted(files)), ignore_index=True)
