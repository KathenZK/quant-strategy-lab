from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-15m-hierarchical-trend-opportunity"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NORMALIZED_ROOT = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
RAW_ROOT = ROOT / "data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
FUNDING_ROOT = (
    ROOT
    / "data/normalized/funding_rates/exchange=binance/market_type=perp"
)
FILE_NAME = "symbol=hype_usdt_usdt.parquet"
RUN_DATE = "2026-07-29"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_partitions(root: Path) -> pd.DataFrame:
    paths = sorted(root.glob(f"date=*/{FILE_NAME}"))
    if not paths:
        raise RuntimeError(f"no parquet partitions under {root}")
    frame = pd.concat([pd.read_parquet(path) for path in paths], ignore_index=True)
    timestamp = "ts" if "ts" in frame.columns else "open_time"
    frame[timestamp] = pd.to_datetime(frame[timestamp], utc=True)
    return frame.sort_values(timestamp).drop_duplicates(timestamp, keep="last").reset_index(drop=True)


def audit(normalized: pd.DataFrame, raw: pd.DataFrame) -> dict[str, object]:
    raw = raw.loc[raw["is_closed"]].copy()
    raw["open_time"] = pd.to_datetime(raw["open_time"], utc=True)
    expected = pd.date_range(normalized["ts"].iloc[0], normalized["ts"].iloc[-1], freq="15min")
    missing = expected.difference(pd.DatetimeIndex(normalized["ts"]))
    critical = [
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "source", "is_closed",
    ]
    nulls = {column: int(normalized[column].isna().sum()) for column in critical}
    violations = {
        "high_lt_open_or_close": int(
            (normalized["high"] < normalized[["open", "close"]].max(axis=1)).sum()
        ),
        "low_gt_open_or_close": int(
            (normalized["low"] > normalized[["open", "close"]].min(axis=1)).sum()
        ),
        "high_lt_low": int((normalized["high"] < normalized["low"]).sum()),
        "nonpositive_ohlc": int(
            ((normalized[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
        ),
        "negative_volume": int((normalized["volume"] < 0).sum()),
        "negative_quote_volume": int((normalized["quote_volume"] < 0).sum()),
        "negative_trade_count": int((normalized["trade_count"] < 0).sum()),
    }
    raw = raw.sort_values("open_time").reset_index(drop=True)
    mismatch: dict[str, int] = {}
    for column in ["open", "high", "low", "close", "volume", "quote_volume", "trade_count"]:
        tolerance = 0.0 if column == "trade_count" else 1e-12
        mismatch[column] = int(
            (~np.isclose(
                raw[column].to_numpy("float64"),
                normalized[column].to_numpy("float64"),
                rtol=0.0,
                atol=tolerance,
            )).sum()
        )
    duplicate_normalized = int(normalized.duplicated("ts").sum())
    duplicate_raw = int(raw.duplicated("open_time").sum())
    blockers = (
        len(missing)
        + duplicate_normalized
        + duplicate_raw
        + sum(nulls.values())
        + sum(violations.values())
        + sum(mismatch.values())
        + int(set(normalized["is_closed"].unique()) != {True})
    )
    result = {
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].iloc[0].isoformat(),
        "last_ts": normalized["ts"].iloc[-1].isoformat(),
        "expected_rows": int(len(expected)),
        "missing_bars": int(len(missing)),
        "duplicate_normalized": duplicate_normalized,
        "duplicate_raw": duplicate_raw,
        "critical_nulls": nulls,
        "ohlcv_violations": violations,
        "raw_normalized_mismatch": mismatch,
        "source_values": {
            str(key): int(value)
            for key, value in normalized["source"].value_counts(dropna=False).items()
        },
        "closed_values": {
            str(key): int(value)
            for key, value in normalized["is_closed"].value_counts(dropna=False).items()
        },
        "blocker_count": int(blockers),
    }
    if blockers:
        raise RuntimeError(f"data-quality blockers: {result}")
    return result


def complete_daily_summary(frame: pd.DataFrame) -> dict[str, object]:
    daily = frame.set_index("ts").resample("1D", label="left", closed="left").agg(
        rows=("close", "size"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    )
    complete = daily.loc[daily["rows"] == 96]
    incomplete = daily.loc[daily["rows"] != 96]
    return {
        "complete_days": int(len(complete)),
        "first_complete_day": complete.index[0].isoformat(),
        "last_complete_day": complete.index[-1].isoformat(),
        "incomplete_days": [
            {"day": timestamp.isoformat(), "rows": int(row["rows"])}
            for timestamp, row in incomplete.iterrows()
        ],
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    normalized = load_partitions(NORMALIZED_ROOT)
    raw = load_partitions(RAW_ROOT)
    normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
    quality = audit(normalized, raw)

    terminal_exclusive = normalized["ts"].iloc[-1] + pd.Timedelta(minutes=15)
    oos_start = terminal_exclusive - pd.DateOffset(months=3)
    if oos_start.minute % 15:
        raise RuntimeError("locked OOS boundary is not aligned to 15m")
    prefit = normalized.loc[normalized["ts"] < oos_start]
    locked_oos = normalized.loc[
        (normalized["ts"] >= oos_start) & (normalized["ts"] < terminal_exclusive)
    ]
    if len(prefit) + len(locked_oos) != len(normalized):
        raise RuntimeError("prefit/OOS split does not cover the frozen snapshot")

    funding = load_partitions(FUNDING_ROOT)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.loc[
        (funding["ts"] >= normalized["ts"].iloc[0])
        & (funding["ts"] < terminal_exclusive)
    ].reset_index(drop=True)
    if funding["funding_rate"].isna().any():
        raise RuntimeError("funding_rate contains nulls")

    snapshot_path = ARTIFACT_DIR / f"hype_d15_hto_frozen_15m_{RUN_DATE}.parquet"
    funding_path = ARTIFACT_DIR / f"hype_d15_hto_frozen_funding_{RUN_DATE}.parquet"
    normalized.to_parquet(snapshot_path, index=False)
    funding.to_parquet(funding_path, index=False)
    manifest = {
        "family": "HYPE-1D-15M-Hierarchical-Trend-Opportunity",
        "alias": "HYPE-D15-HTO",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "market": "Binance USD-M Futures",
        "symbol": "HYPEUSDT",
        "timeframe": "15m execution / complete UTC 1d regime",
        "quality": quality,
        "daily_aggregation": complete_daily_summary(normalized),
        "freeze_contract": {
            "data_start_inclusive": normalized["ts"].iloc[0].isoformat(),
            "data_terminal_exclusive": terminal_exclusive.isoformat(),
            "locked_oos_start_inclusive": oos_start.isoformat(),
            "locked_oos_end_exclusive": terminal_exclusive.isoformat(),
            "prefit_rule": "ts < locked_oos_start_inclusive",
            "oos_rule": "locked_oos_start_inclusive <= ts < locked_oos_end_exclusive",
            "daily_rule": "UTC day with exactly 96 closed 15m bars; intraday rows see only prior complete day",
            "locked_oos_performance_accessed": False,
        },
        "rows": {
            "all": int(len(normalized)),
            "prefit": int(len(prefit)),
            "locked_oos": int(len(locked_oos)),
            "funding": int(len(funding)),
        },
        "artifacts": {
            "snapshot": snapshot_path.name,
            "snapshot_sha256": sha256(snapshot_path),
            "funding": funding_path.name,
            "funding_sha256": sha256(funding_path),
        },
    }
    manifest_path = ARTIFACT_DIR / f"hype_d15_hto_dataset_freeze_{RUN_DATE}.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
