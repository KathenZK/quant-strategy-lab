from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
NORMALIZED_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=hype_usdt_usdt/funding.parquet"
)
SOURCE_METADATA = ARTIFACT_DIR / "hype_binance_15m_data_quality.json"
OUTPUT = ARTIFACT_DIR / "hype_15m_mmtf_dataset_freeze_2026-07-22.json"


def _combined_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load_partitions(root: Path, timestamp_column: str) -> tuple[pd.DataFrame, list[Path]]:
    paths = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not paths:
        raise RuntimeError(f"no data partitions found below {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame[timestamp_column] = pd.to_datetime(frame[timestamp_column], utc=True)
    return frame.sort_values(timestamp_column).reset_index(drop=True), paths


def _audit(raw: pd.DataFrame, normalized: pd.DataFrame) -> dict[str, object]:
    if len(raw) != len(normalized):
        raise RuntimeError(f"raw/normalized row mismatch: {len(raw)} != {len(normalized)}")
    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="15min")
    missing = expected.difference(pd.DatetimeIndex(normalized["ts"]))
    critical = [
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "source", "is_closed",
    ]
    nulls = {column: int(normalized[column].isna().sum()) for column in critical}
    violations = {
        "missing_bars": int(len(missing)),
        "duplicate_raw": int(raw["open_time"].duplicated().sum()),
        "duplicate_normalized": int(normalized["ts"].duplicated().sum()),
        "critical_nulls": int(sum(nulls.values())),
        "unclosed_rows": int((~normalized["is_closed"].astype(bool)).sum()),
        "high_violation": int(
            normalized["high"].lt(normalized[["open", "close", "low"]].max(axis=1)).sum()
        ),
        "low_violation": int(
            normalized["low"].gt(normalized[["open", "close", "high"]].min(axis=1)).sum()
        ),
        "nonpositive_ohlc": int(
            (normalized[["open", "high", "low", "close"]] <= 0.0).any(axis=1).sum()
        ),
        "negative_volume": int((normalized["volume"] < 0.0).sum()),
    }
    raw = raw.sort_values("open_time").reset_index(drop=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    comparisons: dict[str, int] = {}
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]:
        tolerance = 0.0 if column == "trade_count" else 1e-12
        comparisons[column] = int(
            (~np.isclose(
                raw[column].to_numpy("float64"),
                normalized[column].to_numpy("float64"),
                rtol=0.0,
                atol=tolerance,
            )).sum()
        )
    blocker_count = int(sum(violations.values()) + sum(comparisons.values()))
    quality = {
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "nulls": nulls,
        "violations": violations,
        "raw_normalized_mismatch": comparisons,
        "blocker_count": blocker_count,
    }
    if blocker_count:
        raise RuntimeError(f"data-quality blocker: {quality}")
    return quality


def main() -> None:
    raw, raw_paths = _load_partitions(RAW_ROOT, "open_time")
    normalized, normalized_paths = _load_partitions(NORMALIZED_ROOT, "ts")
    quality = _audit(raw, normalized)
    funding = pd.read_parquet(FUNDING_PATH).sort_values("ts").reset_index(drop=True)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    if funding["ts"].duplicated().any() or funding["funding_rate"].isna().any():
        raise RuntimeError("funding history contains duplicate timestamps or null rates")

    terminal = pd.Timestamp(normalized["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
    oos_start = terminal - pd.DateOffset(months=3)
    prefit = normalized.loc[normalized["ts"] < oos_start]
    locked = normalized.loc[normalized["ts"] >= oos_start]
    funding_in_scope = funding.loc[funding["ts"] < terminal]
    if prefit.empty or locked.empty or funding_in_scope.empty:
        raise RuntimeError("prefit, locked OOS, or funding partition is empty")

    source_metadata = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
    manifest = {
        "family": "HYPE-15M-Multi-Mechanism-Trend-Following",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m",
        "freeze_contract": {
            "data_terminal_exclusive": terminal.isoformat(),
            "locked_oos_start_inclusive": pd.Timestamp(oos_start).isoformat(),
            "locked_oos_end_exclusive": terminal.isoformat(),
            "selection_rule": "all candidate generation, ranking, ablation, and tuning use ts < locked_oos_start_inclusive",
            "reveal_rule": "locked OOS may be evaluated once only after final config and code hashes are frozen",
            "minimum_sample_rule": "V1 ranking requires prefit trades >= 100 and validation trades >= 20; locked OOS is reported without post-reveal relaxation",
        },
        "rows": {
            "all": int(len(normalized)),
            "prefit": int(len(prefit)),
            "locked_oos": int(len(locked)),
            "funding_in_scope": int(len(funding_in_scope)),
        },
        "quality": quality,
        "funding_quality": {
            "first_ts": funding_in_scope["ts"].iloc[0].isoformat(),
            "last_ts": funding_in_scope["ts"].iloc[-1].isoformat(),
            "rows": int(len(funding_in_scope)),
            "duplicate_ts": int(funding_in_scope["ts"].duplicated().sum()),
            "null_rates": int(funding_in_scope["funding_rate"].isna().sum()),
            "max_gap_hours": float(
                funding_in_scope["ts"].diff().dropna().max().total_seconds() / 3600.0
            ),
        },
        "hashes": {
            "raw_partitions_sha256": _combined_sha256(raw_paths),
            "normalized_partitions_sha256": _combined_sha256(normalized_paths),
            "funding_parquet_sha256": hashlib.sha256(FUNDING_PATH.read_bytes()).hexdigest(),
        },
        "contract_snapshot": source_metadata["contract_snapshot"],
        "source_paths": {
            "raw": str(RAW_ROOT.relative_to(ROOT)),
            "normalized": str(NORMALIZED_ROOT.relative_to(ROOT)),
            "funding": str(FUNDING_PATH.relative_to(ROOT)),
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

