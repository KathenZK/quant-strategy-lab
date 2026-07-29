from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

import sma_xs_engine as engine


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-sma-crossover-slope"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
NORMALIZED_ROOT = (
    ROOT / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
OUTPUT = ARTIFACT_DIR / "hype_15m_sma_xs_dataset_freeze.json"


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
        "ts", "open", "high", "low", "close", "volume",
        "quote_volume", "trade_count", "vwap", "source", "is_closed",
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


def _candidate_grid() -> list[dict[str, object]]:
    candidates = [engine.config_payload(engine.Config(exit_mode="cross_only"))]
    for exit_mode in ["fast_slope", "gap_slope", "hybrid_any", "hybrid_both"]:
        for slope_window in [1, 3, 6]:
            for confirmation in [1, 2, 3]:
                candidates.append(
                    engine.config_payload(
                        engine.Config(
                            exit_mode=exit_mode,
                            slope_window=slope_window,
                            exit_confirm_bars=confirmation,
                        )
                    )
                )
    return candidates


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
    validation_start = oos_start - pd.DateOffset(months=3)
    candidates = _candidate_grid()
    candidates_raw = json.dumps(candidates, sort_keys=True, separators=(",", ":"))
    manifest = {
        "family": "HYPE-15M-SMA-Crossover-Slope",
        "status": "explore / not promoted / not live-ready",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m",
        "freeze_contract": {
            "data_terminal_exclusive": terminal.isoformat(),
            "locked_oos_start_inclusive": pd.Timestamp(oos_start).isoformat(),
            "locked_oos_end_exclusive": terminal.isoformat(),
            "prefit_validation_start_inclusive": pd.Timestamp(validation_start).isoformat(),
            "selection_rule": "rank the frozen finite grid using prefit train plus the final three prefit months; never use locked OOS for selection",
            "reveal_rule": "reveal every frozen candidate once on locked OOS; do not tune or promote from this reused window",
            "oos_provenance": "reused market window; other HYPE families have inspected overlapping dates, so this is not pristine OOS",
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
        "candidate_grid": candidates,
        "candidate_grid_sha256": hashlib.sha256(candidates_raw.encode("utf-8")).hexdigest(),
        "hashes": {
            "raw_partitions_sha256": _combined_sha256(raw_paths),
            "normalized_partitions_sha256": _combined_sha256(normalized_paths),
            "engine_sha256": hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
        },
        "cost_contract": {
            "fee_per_fill": engine.BASE_FEE,
            "adverse_slippage_per_fill": engine.BASE_SLIPPAGE,
            "funding": "actual Binance history",
        },
        "execution_contract": {
            "signal": "closed 15m bar",
            "execution": "next bar open",
            "position": "single net position at 1x",
            "entry": "SMA30/SMA120 golden cross opens long; dead cross opens short",
            "cross_exit": "opposite cross closes and reverses at next open",
            "slope_exit_lock": "after a slope exit, stay flat until a fresh cross; no same-regime re-entry",
            "fixed_stop": "disabled in this exact mechanism test",
        },
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
