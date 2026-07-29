from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

import sds_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-sequential-drift-state"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
NORMALIZED_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
OUTPUT = ARTIFACT_DIR / "hype_15m_sds_dataset_freeze.json"
SOURCE_METADATA = ARTIFACT_DIR / "hype_binance_15m_data_quality.json"


def _paths(root: Path) -> list[Path]:
    result = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not result:
        raise RuntimeError(f"no partitions below {root}")
    return result


def _combined_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _load(paths: list[Path], timestamp_column: str) -> pd.DataFrame:
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    frame[timestamp_column] = pd.to_datetime(frame[timestamp_column], utc=True)
    return frame.sort_values(timestamp_column).reset_index(drop=True)


def _audit(raw: pd.DataFrame, normalized: pd.DataFrame) -> dict[str, object]:
    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="15min")
    critical = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "source",
        "is_closed",
    ]
    nulls = {column: int(normalized[column].isna().sum()) for column in critical}
    violations = {
        "missing_bars": int(len(expected.difference(pd.DatetimeIndex(normalized["ts"])))),
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
    comparisons: dict[str, int] = {}
    raw = raw.sort_values("open_time").reset_index(drop=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
    if len(raw) != len(normalized):
        raise RuntimeError(f"raw/normalized row mismatch: {len(raw)} != {len(normalized)}")
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
    raw_paths = _paths(RAW_ROOT)
    normalized_paths = _paths(NORMALIZED_ROOT)
    raw = _load(raw_paths, "open_time")
    normalized = _load(normalized_paths, "ts")
    quality = _audit(raw, normalized)
    funding = engine.load_funding()
    if funding["ts"].duplicated().any() or funding["funding_rate"].isna().any():
        raise RuntimeError("funding history contains duplicate timestamps or null rates")

    terminal = pd.Timestamp(normalized["ts"].iloc[-1]) + pd.Timedelta(minutes=15)
    oos_start = terminal - pd.DateOffset(months=3)
    prefit = normalized.loc[normalized["ts"] < oos_start]
    locked = normalized.loc[normalized["ts"] >= oos_start]
    if prefit.empty or locked.empty:
        raise RuntimeError("prefit or locked OOS is empty")

    source_metadata = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
    engine_path = Path(engine.__file__).resolve()
    baseline_raw = json.dumps(
        engine.config_payload(engine.BASELINE_CONFIG),
        sort_keys=True,
        separators=(",", ":"),
    )
    manifest = {
        "family": "HYPE-15M-Sequential-Drift-State",
        "status": "explore / not promoted / not live-ready",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m",
        "freeze_contract": {
            "data_terminal_exclusive": terminal.isoformat(),
            "locked_oos_start_inclusive": pd.Timestamp(oos_start).isoformat(),
            "locked_oos_end_exclusive": terminal.isoformat(),
            "selection_rule": "baseline mechanism and parameters were written before any family-local locked OOS reveal",
            "reveal_rule": "the locked segment may be evaluated once for this baseline and must not be used for post-reveal tuning",
            "oos_provenance": "reused market window; other HYPE families have previously inspected overlapping dates, so this is not pristine OOS",
        },
        "rows": {
            "all": int(len(normalized)),
            "prefit": int(len(prefit)),
            "locked_oos": int(len(locked)),
            "funding": int(len(funding.loc[funding["ts"] < terminal])),
        },
        "quality": quality,
        "funding_quality": {
            "first_ts": funding["ts"].iloc[0].isoformat(),
            "last_ts": funding["ts"].iloc[-1].isoformat(),
            "duplicate_ts": int(funding["ts"].duplicated().sum()),
            "null_rates": int(funding["funding_rate"].isna().sum()),
        },
        "baseline_config": engine.config_payload(engine.BASELINE_CONFIG),
        "hashes": {
            "raw_partitions_sha256": _combined_sha256(raw_paths),
            "normalized_partitions_sha256": _combined_sha256(normalized_paths),
            "engine_sha256": hashlib.sha256(engine_path.read_bytes()).hexdigest(),
            "baseline_config_sha256": hashlib.sha256(baseline_raw.encode("utf-8")).hexdigest(),
        },
        "contract_snapshot": source_metadata["contract_snapshot"],
        "cost_contract": {
            "fee_per_fill": engine.BASE_FEE,
            "adverse_slippage_per_fill": engine.BASE_SLIPPAGE,
            "funding": "actual Binance history",
        },
        "execution_contract": {
            "signal": "closed 15m bar",
            "execution": "next bar open",
            "position": "single net position",
            "intrabar": "emergency stop, gap-open aware",
            "stop_lock": "after an emergency stop, same-direction re-entry is blocked until the estimator leaves that state",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
