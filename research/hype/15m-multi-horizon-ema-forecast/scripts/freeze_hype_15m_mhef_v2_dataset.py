from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

import mhef_v2_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-horizon-ema-forecast"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
NORMALIZED_ROOT = engine.NORMALIZED_ROOT
FILE_NAME = engine.FILE_NAME
OUTPUT = engine.FREEZE_PATH


def _paths(root: Path) -> list[Path]:
    paths = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not paths:
        raise RuntimeError(f"no partitions below {root}")
    return paths


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
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "source", "is_closed",
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
    if len(raw) != len(normalized):
        raise RuntimeError(f"raw/normalized row mismatch: {len(raw)} != {len(normalized)}")
    comparisons: dict[str, int] = {}
    raw = raw.sort_values("open_time").reset_index(drop=True)
    normalized = normalized.sort_values("ts").reset_index(drop=True)
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
    validation_start = oos_start - pd.DateOffset(months=3)
    tune_start = validation_start - pd.DateOffset(months=3)
    rows = {
        "all": int(len(normalized)),
        "development": int((normalized["ts"] < validation_start).sum()),
        "prefit_validation": int(
            ((normalized["ts"] >= validation_start) & (normalized["ts"] < oos_start)).sum()
        ),
        "reused_locked_oos": int((normalized["ts"] >= oos_start).sum()),
        "funding": int((funding["ts"] < terminal).sum()),
    }
    engine_path = Path(engine.__file__).resolve()
    manifest = {
        "family": "HYPE-15M-Multi-Horizon-EMA-Forecast",
        "research_identity": "MHEF-V2 continuous risk-target prototype; unregistered observation",
        "status": "explore / not promoted / not live-ready",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m",
        "freeze_contract": {
            "data_terminal_exclusive": terminal.isoformat(),
            "development_tune_start_inclusive": tune_start.isoformat(),
            "prefit_validation_start_inclusive": validation_start.isoformat(),
            "locked_oos_start_inclusive": oos_start.isoformat(),
            "locked_oos_end_exclusive": terminal.isoformat(),
            "selection_rule": (
                "freeze conceptual baseline first; perform component ablation and "
                "parameter sensitivity only before prefit validation; freeze one "
                "candidate before a one-time prefit-validation reveal"
            ),
            "reveal_rule": (
                "the final three-month market window is already revealed by other "
                "HYPE studies and is prohibited from candidate selection in this study"
            ),
            "oos_provenance": (
                "2026-04-28 onward is reused revealed OOS, not pristine; it remains "
                "unread by the V2 development and validation scripts"
            ),
        },
        "rows": rows,
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
            "baseline_config_sha256": engine.config_sha256(engine.BASELINE_CONFIG),
        },
        "cost_contract": {
            "fee_per_turnover": engine.BASE_FEE,
            "adverse_slippage_per_turnover": engine.BASE_SLIPPAGE,
            "funding": "actual Binance history",
        },
        "execution_contract": {
            "signal": "closed 15m bar",
            "execution": "next bar open",
            "position": "continuous single net position in [-1, 1]",
            "no_trade_zone": "trade only to the nearest target-band boundary",
            "staging": "absolute position change per bar is capped",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
