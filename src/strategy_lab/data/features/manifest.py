from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json

import pandas as pd

from strategy_lab.data.fs import atomic_write_text


def fingerprint_payload(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class FactorArtifactManifest:
    factor_name: str
    factor_version: str
    factor_category: str
    exchange: str
    symbol: str
    market_type: str
    timeframe: str | None
    rows: int
    columns: list[str]
    benchmark_symbol: str | None
    input_start: str
    input_end: str
    feature_path: str
    generated_at: str
    manifest_id: str

    @classmethod
    def create(
        cls,
        *,
        factor_name: str,
        factor_version: str,
        factor_category: str,
        exchange: str,
        symbol: str,
        market_type: str,
        timeframe: str | None,
        frame: pd.DataFrame,
        feature_path: Path,
        benchmark_symbol: str | None = None,
    ) -> "FactorArtifactManifest":
        payload = {
            "factor_name": factor_name,
            "factor_version": factor_version,
            "factor_category": factor_category,
            "exchange": exchange.lower(),
            "symbol": symbol.upper(),
            "market_type": market_type,
            "timeframe": timeframe.lower() if timeframe else None,
            "rows": len(frame),
            "columns": frame.columns.tolist(),
            "benchmark_symbol": benchmark_symbol.upper() if benchmark_symbol else None,
            "input_start": pd.to_datetime(frame["ts"], utc=True).min().isoformat(),
            "input_end": pd.to_datetime(frame["ts"], utc=True).max().isoformat(),
            "feature_path": str(feature_path),
        }
        return cls(
            **payload,
            generated_at=pd.Timestamp.now(tz="UTC").isoformat(),
            manifest_id=fingerprint_payload(payload),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def write(self, path: Path) -> Path:
        return atomic_write_text(path, json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
