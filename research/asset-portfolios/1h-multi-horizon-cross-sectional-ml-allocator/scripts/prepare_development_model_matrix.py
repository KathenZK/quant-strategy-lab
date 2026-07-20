from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATASET_ROOT = ARTIFACT_DIR / "multihorizon_factor_dataset"
PANEL_ROOT = DATASET_ROOT / "panel"
PANEL_MANIFEST_PATH = DATASET_ROOT / "factor_dataset_manifest.json"
PANEL_AUDIT_PATH = ARTIFACT_DIR / "factor_panel_audit_2026-07-18.json"
COVERAGE_PATH = ARTIFACT_DIR / "factor_coverage_2026-07-18.csv"
MATRIX_ROOT = ARTIFACT_DIR / "development_model_matrix_4h"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "development_model_matrix_manifest.json"
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
REUSED_HOLDOUT_START = DEVELOPMENT_END
BASE_DECISION_HOURS = 4
HORIZONS = (4, 8, 12, 24, 48)
CONTEXT_FEATURES = [
    "liquidity_rank",
    "avg_daily_quote_volume_7d",
    "coverage_30d",
    "relative_to_btc_24",
    "relative_to_btc_168",
    "market_breadth_ret24_positive",
    "market_breadth_trend_positive",
    "market_median_realized_vol_24",
    "market_dispersion_ret24",
    "market_dispersion_vol24",
    "market_positive_funding_share",
]
SPARSE_EVENT_PREFIX = "donchian_breakout_strength_"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize a physically development-only 4h decision matrix without "
            "reading reused-holdout or prospective-OOS outcomes."
        )
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    panel_manifest = json.loads(PANEL_MANIFEST_PATH.read_text(encoding="utf-8"))
    panel_audit = json.loads(PANEL_AUDIT_PATH.read_text(encoding="utf-8"))
    if panel_manifest.get("status") != "PASS":
        raise RuntimeError("factor dataset manifest is not PASS")
    if panel_audit.get("status") != "PASS" or panel_audit.get("blockers"):
        raise RuntimeError("factor panel audit is not PASS")
    if panel_manifest["time_contract"].get("prospective_oos_outcomes_read"):
        raise RuntimeError("source manifest reports protected OOS outcome access")
    return panel_manifest, panel_audit


def development_panel_files() -> list[Path]:
    files: list[Path] = []
    for directory in sorted(PANEL_ROOT.glob("year_month=*")):
        month = directory.name.removeprefix("year_month=")
        if month >= DEVELOPMENT_END.strftime("%Y-%m"):
            continue
        files.extend(sorted(directory.glob("*.parquet")))
    if not files:
        raise RuntimeError("no development panel files found")
    forbidden = [path for path in files if "year_month=2026-04" in str(path)]
    if forbidden:
        raise RuntimeError(f"reused holdout entered source list: {forbidden[:3]}")
    return files


def quoted_file_list(paths: list[Path]) -> str:
    return "[" + ",".join(f"'{sql_path(path)}'" for path in paths) + "]"


def feature_sets(panel_manifest: dict[str, Any]) -> dict[str, list[str]]:
    base = list(panel_manifest["base_factor_names"])
    cross_sectional = [
        f"cs_rank_{name}"
        for name in panel_manifest["cross_sectional_rank_factors"]
    ]
    full = list(dict.fromkeys(base + cross_sectional + CONTEXT_FEATURES))
    coverage = pd.read_csv(COVERAGE_PATH).set_index("factor")[
        "development_coverage"
    ]
    missing_coverage = sorted(set(full) - set(coverage.index))
    if missing_coverage:
        raise RuntimeError(f"features missing coverage audit: {missing_coverage}")
    stable = [name for name in full if float(coverage.loc[name]) >= 0.80]
    sparse_events = [
        name for name in full if name.startswith(SPARSE_EVENT_PREFIX)
    ]
    tail_tokens = (
        "downside_vol_",
        "upside_vol_",
        "return_skew_",
        "return_kurtosis_",
        "extreme_return_",
        "jump_count_",
        "range_max_",
        "max_drawdown_",
        "mark_premium_max_",
        "mark_premium_min_",
        "taker_imbalance_std_",
        "funding_event_sum_",
    )
    tail = [name for name in stable if any(token in name for token in tail_tokens)]
    compact_names = [
        "age_bars",
        "atr_pct_24",
        "atr_pct_168",
        "ema_spread_6_24",
        "ema_spread_24_96",
        "ema_spread_96_384",
        "funding_rate",
        "funding_zscore_168",
        "ma_distance_24",
        "ma_distance_96",
        "mark_premium",
        "mark_premium_zscore_168",
        "max_drawdown_72",
        "max_drawdown_336",
        "quote_volume_ratio_24",
        "realized_vol_24",
        "realized_vol_168",
        "ret_4",
        "ret_8",
        "ret_12",
        "ret_24",
        "ret_48",
        "ret_72",
        "ret_168",
        "rsi_24",
        "taker_imbalance_mean_24",
        "trade_count_ratio_24",
        *cross_sectional,
        *CONTEXT_FEATURES,
    ]
    compact = [name for name in dict.fromkeys(compact_names) if name in full]
    return {
        "compact": compact,
        "stable_full": stable,
        "full_plus_sparse": full,
        "tail_stable": tail,
        "sparse_event_features": sparse_events,
    }


def label_columns() -> list[str]:
    names: list[str] = []
    for horizon in HORIZONS:
        names.extend(
            [
                f"label_path_valid_{horizon}h",
                f"label_funding_sum_{horizon}h",
                f"label_gross_return_{horizon}h",
                f"label_long_net_{horizon}h",
                f"label_short_net_{horizon}h",
                f"label_long_relative_{horizon}h",
                f"label_short_relative_{horizon}h",
                f"label_long_mae_{horizon}h",
                f"label_long_mfe_{horizon}h",
                f"label_short_mae_{horizon}h",
                f"label_short_mfe_{horizon}h",
                f"label_short_squeeze_10pct_{horizon}h",
                f"label_short_squeeze_20pct_{horizon}h",
                f"label_long_crash_10pct_{horizon}h",
                f"label_long_crash_20pct_{horizon}h",
            ]
        )
    return names


def main() -> None:
    args = parse_args()
    panel_manifest, panel_audit = validate_inputs()
    files = development_panel_files()
    sets = feature_sets(panel_manifest)
    features = sets["full_plus_sparse"]
    labels = label_columns()
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    source = (
        "read_parquet("
        f"{quoted_file_list(files)}, hive_partitioning=false, union_by_name=true)"
    )
    columns = {
        row[0]
        for row in connection.execute(f"DESCRIBE SELECT * FROM {source}").fetchall()
    }
    missing = sorted(set(features + labels) - columns)
    if missing:
        raise RuntimeError(f"matrix source columns missing: {missing}")
    if args.overwrite:
        shutil.rmtree(MATRIX_ROOT, ignore_errors=True)
    if not list(MATRIX_ROOT.glob("**/*.parquet")):
        MATRIX_ROOT.mkdir(parents=True, exist_ok=True)
        feature_sql = ",\n".join(
            f'CAST("{name}" AS FLOAT) AS "{name}"' for name in features
        )
        label_sql = ",\n".join(
            (
                f'CAST("{name}" AS BOOLEAN) AS "{name}"'
                if name.startswith("label_path_valid_")
                else f'CAST("{name}" AS FLOAT) AS "{name}"'
            )
            for name in labels
        )
        connection.execute(
            f"""
            COPY (
                SELECT
                    ts,
                    symbol,
                    {feature_sql},
                    {label_sql},
                    year(ts AT TIME ZONE 'UTC') AS year
                FROM {source}
                WHERE universe_main
                  AND ts < TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}'
                  AND (floor(epoch(ts) / 3600)::BIGINT % {BASE_DECISION_HOURS}) = 0
                ORDER BY ts, symbol
            ) TO '{sql_path(MATRIX_ROOT)}' (
                FORMAT PARQUET,
                PARTITION_BY (year),
                COMPRESSION ZSTD,
                OVERWRITE_OR_IGNORE TRUE
            )
            """
        )
    matrix_glob = MATRIX_ROOT / "**/*.parquet"
    summary = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            strftime(min(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS first_ts,
            strftime(max(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS last_ts,
            count(*) FILTER (
                WHERE ts >= TIMESTAMPTZ '{REUSED_HOLDOUT_START.isoformat()}'
            ) AS forbidden_rows,
            count(*) FILTER (
                WHERE (floor(epoch(ts) / 3600)::BIGINT % {BASE_DECISION_HOURS}) != 0
            ) AS off_grid_rows,
            count(*) - count(DISTINCT (ts, symbol)) AS duplicate_rows
        FROM read_parquet(
            '{sql_path(matrix_glob)}',
            hive_partitioning=false,
            union_by_name=true
        )
        """
    ).fetchone()
    connection.close()
    if int(summary[4]) or int(summary[5]) or int(summary[6]):
        raise RuntimeError(
            "development matrix isolation failed: "
            f"forbidden={summary[4]} off_grid={summary[5]} duplicates={summary[6]}"
        )
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS",
        "physical_outcome_isolation": True,
        "development_end_exclusive": DEVELOPMENT_END.isoformat(),
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "source_partition_policy": "only panel year_month partitions before 2026-04",
        "source_files": [str(path.relative_to(ROOT)) for path in files],
        "source_panel_manifest": str(PANEL_MANIFEST_PATH.relative_to(ROOT)),
        "source_panel_manifest_sha256": sha256(PANEL_MANIFEST_PATH),
        "source_panel_audit": str(PANEL_AUDIT_PATH.relative_to(ROOT)),
        "source_panel_audit_sha256": sha256(PANEL_AUDIT_PATH),
        "source_panel_audit_status": panel_audit["status"],
        "base_decision_hours": BASE_DECISION_HOURS,
        "rows": int(summary[0]),
        "symbols": int(summary[1]),
        "first_ts": str(summary[2]),
        "last_ts": str(summary[3]),
        "forbidden_rows": int(summary[4]),
        "off_grid_rows": int(summary[5]),
        "duplicate_rows": int(summary[6]),
        "feature_count": len(features),
        "feature_sets": sets,
        "labels": labels,
        "horizons_hours": list(HORIZONS),
        "matrix_root": str(MATRIX_ROOT.relative_to(ROOT)),
    }
    MATRIX_MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "rows": manifest["rows"],
                "symbols": manifest["symbols"],
                "first_ts": manifest["first_ts"],
                "last_ts": manifest["last_ts"],
                "feature_count": manifest["feature_count"],
                "feature_set_sizes": {
                    key: len(value) for key, value in sets.items()
                },
                "physical_outcome_isolation": True,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
