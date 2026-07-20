from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
OLD_ARTIFACT_DIR = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/artifacts"
)
START = pd.Timestamp("2020-01-01T00:00:00Z")
END = pd.Timestamp("2026-07-01T00:00:00Z")
DATASETS = {
    "kline_1h": ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet",
    "mark_1h": ROOT
    / "data/normalized/mark_price_klines/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def latest_json(directory: Path, pattern: str, required_key: str | None = None) -> Path:
    for path in reversed(sorted(directory.glob(pattern))):
        if required_key is None:
            return path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if any(required_key in detail for detail in payload.get("datasets", {}).values()):
            return path
    raise RuntimeError(f"no matching JSON for {pattern}")


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def gap_frame(dataset: str) -> pd.DataFrame:
    connection = duckdb.connect()
    frame = connection.execute(
        f"""
        WITH ordered AS (
            SELECT
                symbol,
                ts,
                lag(ts) OVER (PARTITION BY symbol ORDER BY ts) AS previous_ts
            FROM read_parquet(
                '{sql_path(DATASETS[dataset])}',
                hive_partitioning=false,
                union_by_name=true
            )
            WHERE ts >= TIMESTAMPTZ '{START.isoformat()}'
              AND ts < TIMESTAMPTZ '{END.isoformat()}'
        )
        SELECT
            symbol,
            previous_ts + INTERVAL 1 HOUR AS start,
            ts AS end_exclusive,
            date_diff('hour', previous_ts, ts) - 1 AS missing_hours
        FROM ordered
        WHERE date_diff('hour', previous_ts, ts) > 1
        ORDER BY symbol, start
        """
    ).fetch_df()
    connection.close()
    for column in ["start", "end_exclusive"]:
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def fapi_empty_evidence(payload: dict[str, Any], dataset: str) -> dict[str, int]:
    detail = payload["datasets"][dataset]
    requests = detail["requests"]
    empty = [request for request in requests if request["returned_hours"] == 0]
    return {
        "requests": len(requests),
        "empty_responses": len(empty),
        "empty_expected_hours": int(
            sum(request["expected_hours"] for request in empty)
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    strict_report_path = latest_json(
        OLD_ARTIFACT_DIR, "binance_usdm_data_quality_*.json"
    )
    strict_report = json.loads(strict_report_path.read_text(encoding="utf-8"))
    if strict_report.get("status") != "PASS" or strict_report.get("blockers"):
        raise RuntimeError(f"strict data audit is not PASS: {strict_report_path}")
    daily_manifest_path = latest_json(
        ARTIFACT_DIR, "daily_gap_repair_manifest_*.json", "archives"
    )
    fapi_manifest_path = latest_json(
        ARTIFACT_DIR, "fapi_gap_repair_manifest_*.json", "requests"
    )
    funding_quarantine_path = (
        ARTIFACT_DIR / "redundant_hype_funding_quarantine_manifest.json"
    )
    daily_manifest = json.loads(daily_manifest_path.read_text(encoding="utf-8"))
    fapi_manifest = json.loads(fapi_manifest_path.read_text(encoding="utf-8"))
    funding_quarantine = json.loads(
        funding_quarantine_path.read_text(encoding="utf-8")
    )
    if not funding_quarantine.get("applied"):
        raise RuntimeError("funding duplicate quarantine was not applied")

    kline_gaps = gap_frame("kline_1h")
    mark_gaps = gap_frame("mark_1h")
    kline_api = fapi_empty_evidence(fapi_manifest, "kline_1h")
    mark_api = fapi_empty_evidence(fapi_manifest, "mark_1h")
    if len(kline_gaps) != kline_api["empty_responses"]:
        raise RuntimeError("remaining kline gaps do not match empty FAPI evidence")
    if int(kline_gaps["missing_hours"].sum()) != kline_api["empty_expected_hours"]:
        raise RuntimeError("remaining kline hours do not match empty FAPI evidence")
    if len(mark_gaps) != mark_api["empty_responses"]:
        raise RuntimeError("remaining mark gaps do not match empty FAPI evidence")
    if int(mark_gaps["missing_hours"].sum()) != mark_api["empty_expected_hours"]:
        raise RuntimeError("remaining mark hours do not match empty FAPI evidence")

    intervals = kline_gaps.copy()
    intervals["reason"] = "exchange_returned_no_trade_bars"
    intervals["fapi_kline_response"] = "empty"
    intervals["exclude_from_entry_and_label"] = True
    mark_overlap = []
    for row in intervals.itertuples(index=False):
        overlap = mark_gaps.loc[
            mark_gaps["symbol"].eq(row.symbol)
            & mark_gaps["start"].lt(row.end_exclusive)
            & mark_gaps["end_exclusive"].gt(row.start)
        ]
        mark_overlap.append(not overlap.empty)
    intervals["mark_gap_overlap"] = mark_overlap
    interval_path = ARTIFACT_DIR / "nontradable_intervals_2020_2026q2.csv"
    intervals.to_csv(interval_path, index=False)

    report = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS",
        "research_range": {
            "start": START.isoformat(),
            "end_exclusive": END.isoformat(),
        },
        "oos_label_or_performance_read": False,
        "source_strict_audit": {
            "path": str(strict_report_path.relative_to(ROOT)),
            "sha256": sha256(strict_report_path),
            "datasets": strict_report["datasets"],
        },
        "repairs": {
            "daily_archive_manifest": {
                "path": str(daily_manifest_path.relative_to(ROOT)),
                "sha256": sha256(daily_manifest_path),
                "datasets": {
                    name: {
                        "gap_hours_before": detail["gap_hours_before"],
                        "repaired_hours": detail["repaired_hours"],
                    }
                    for name, detail in daily_manifest["datasets"].items()
                },
            },
            "fapi_manifest": {
                "path": str(fapi_manifest_path.relative_to(ROOT)),
                "sha256": sha256(fapi_manifest_path),
                "datasets": {
                    name: {
                        "gap_hours_before": detail["gap_hours_before"],
                        "returned_hours": detail["returned_hours"],
                        "gap_hours_after": detail["gap_hours_after"],
                    }
                    for name, detail in fapi_manifest["datasets"].items()
                },
            },
            "funding_quarantine_manifest": {
                "path": str(funding_quarantine_path.relative_to(ROOT)),
                "sha256": sha256(funding_quarantine_path),
                "redundant_files_quarantined": funding_quarantine[
                    "fully_redundant_files"
                ],
                "retained_uncovered_rows": funding_quarantine[
                    "retained_uncovered_rows"
                ],
            },
        },
        "remaining_intervals": {
            "classification": "nontradable_not_fabricated",
            "kline_intervals": len(kline_gaps),
            "kline_hours": int(kline_gaps["missing_hours"].sum()),
            "mark_intervals": len(mark_gaps),
            "mark_hours": int(mark_gaps["missing_hours"].sum()),
            "all_verified_empty_by_fapi": True,
            "entry_and_label_policy": (
                "exclude any sample whose entry-to-exit interval intersects a "
                "nontradable interval"
            ),
            "artifact": str(interval_path.relative_to(ROOT)),
            "artifact_sha256": sha256(interval_path),
        },
        "blockers": [],
    }
    output = ARTIFACT_DIR / "data_quality_manifest_2026-07-18.json"
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print(f"manifest -> {output}")


if __name__ == "__main__":
    main()
