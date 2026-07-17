from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from strategy_lab.data.factors.multi_asset_1h import multi_asset_1h_registry


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATASET_ROOT = ARTIFACT_DIR / "cross_sectional_factor_dataset"
PANEL_ROOT = DATASET_ROOT / "panel"
MATRIX_ROOT = ARTIFACT_DIR / "prefit_model_matrix"
MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
PANEL_AUDIT_PATH = ARTIFACT_DIR / "cross_sectional_factor_panel_audit_2026-07-17.json"
COVERAGE_PATH = ARTIFACT_DIR / "factor_coverage_pre_oos_2026-07-17.csv"
PREFIT_END = pd.Timestamp("2026-03-31T00:00:00Z")
OOS_START = pd.Timestamp("2026-04-01T00:00:00Z")
HORIZONS = (4, 12, 24)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize a physically pre-OOS-only main-universe model matrix."
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs() -> dict[str, Any]:
    if not PANEL_AUDIT_PATH.exists():
        raise RuntimeError(f"panel audit is missing: {PANEL_AUDIT_PATH}")
    audit = json.loads(PANEL_AUDIT_PATH.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS" or audit.get("blockers"):
        raise RuntimeError("factor panel audit is not PASS")
    if not COVERAGE_PATH.exists():
        raise RuntimeError(f"feature coverage is missing: {COVERAGE_PATH}")
    return audit


def prefit_panel_files() -> list[Path]:
    result: list[Path] = []
    for directory in sorted(PANEL_ROOT.glob("year_month=*")):
        month = directory.name.removeprefix("year_month=")
        if month >= OOS_START.strftime("%Y-%m"):
            continue
        result.extend(sorted(directory.glob("*.parquet")))
    if not result:
        raise RuntimeError("no physically pre-OOS panel partitions were found")
    if any("year_month=2026-04" in str(path) for path in result):
        raise RuntimeError("sealed OOS partition entered the prefit file list")
    return result


def quoted_file_list(paths: list[Path]) -> str:
    return "[" + ",".join(f"'{sql_path(path)}'" for path in paths) + "]"


def feature_sets(
    connection: duckdb.DuckDBPyConnection,
    source_sql: str,
) -> dict[str, list[str]]:
    columns = [row[0] for row in connection.execute(f"DESCRIBE {source_sql}").fetchall()]
    base = multi_asset_1h_registry().names()
    cs_rank = sorted(column for column in columns if column.startswith("cs_rank_"))
    context = [
        "relative_to_btc_24",
        "relative_to_btc_168",
        "market_breadth_ret24_positive",
        "market_breadth_trend_positive",
        "market_median_realized_vol_24",
    ]
    full = base + cs_rank + context
    missing = sorted(set(full) - set(columns))
    if missing:
        raise RuntimeError(f"model features are missing from panel: {missing}")
    coverage = pd.read_csv(COVERAGE_PATH).set_index("feature")["pre_oos_coverage"]
    full_coverage = [name for name in full if float(coverage.loc[name]) >= 0.80]
    sparse_events = [name for name in full if name not in full_coverage]
    compact_base = [
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
        "ret_12",
        "ret_24",
        "ret_72",
        "ret_168",
        "rsi_24",
        "taker_imbalance_mean_24",
        "trade_count_ratio_24",
    ]
    compact = list(dict.fromkeys(compact_base + cs_rank + context))
    return {
        "compact": compact,
        "full_coverage": full_coverage,
        "full_plus_sparse": full,
        "sparse_event_features": sparse_events,
    }


def main() -> None:
    args = parse_args()
    audit = validate_inputs()
    files = prefit_panel_files()
    source_sql = (
        "SELECT * FROM read_parquet("
        f"{quoted_file_list(files)}, hive_partitioning=false, union_by_name=true)"
    )
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    sets = feature_sets(connection, source_sql)
    features = sets["full_plus_sparse"]
    labels = [
        name
        for horizon in HORIZONS
        for name in (
            f"label_funding_sum_{horizon}h",
            f"label_long_net_{horizon}h",
            f"label_short_net_{horizon}h",
            f"label_gross_return_{horizon}h",
            f"label_long_relative_{horizon}h",
            f"label_short_relative_{horizon}h",
        )
    ]
    if args.overwrite:
        shutil.rmtree(MATRIX_ROOT, ignore_errors=True)
    existing = list(MATRIX_ROOT.glob("**/*.parquet"))
    if not existing:
        MATRIX_ROOT.mkdir(parents=True, exist_ok=True)
        feature_sql = ",\n".join(
            f'CAST("{name}" AS FLOAT) AS "{name}"' for name in features
        )
        label_sql = ",\n".join(
            f'CAST("{name}" AS FLOAT) AS "{name}"' for name in labels
        )
        connection.execute(
            f"""
            COPY (
                SELECT
                    ts,
                    symbol,
                    CAST(liquidity_rank AS USMALLINT) AS liquidity_rank,
                    CAST(avg_daily_quote_volume_7d AS FLOAT)
                        AS avg_daily_quote_volume_7d,
                    CAST(open AS FLOAT) AS open,
                    CAST(funding_event_rate AS FLOAT) AS funding_event_rate,
                    {feature_sql},
                    {label_sql},
                    year(ts AT TIME ZONE 'UTC') AS year
                FROM ({source_sql})
                WHERE universe_main
                  AND ts < TIMESTAMPTZ '{PREFIT_END.isoformat()}'
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
            strftime(min(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ')
                AS first_ts,
            strftime(max(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ')
                AS last_ts,
            count(*) FILTER (WHERE ts >= TIMESTAMPTZ '{PREFIT_END.isoformat()}')
                AS forbidden_rows,
            count(*) FILTER (
                WHERE label_long_net_24h IS NULL
                   OR label_short_net_24h IS NULL
            ) AS null_24h_labels
        FROM read_parquet(
            '{sql_path(matrix_glob)}',
            hive_partitioning = false,
            union_by_name = true
        )
        """
    ).fetchone()
    if int(summary[4]) != 0:
        raise RuntimeError(f"forbidden OOS rows entered prefit matrix: {summary[4]}")
    manifest = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "physical_oos_isolation": True,
        "source_partition_policy": "only panel year_month partitions before 2026-04",
        "prefit_end_exclusive": PREFIT_END.isoformat(),
        "oos_start": OOS_START.isoformat(),
        "purge_hours_before_oos": 24,
        "source_panel_audit": str(PANEL_AUDIT_PATH),
        "source_panel_audit_sha256": file_sha256(PANEL_AUDIT_PATH),
        "source_panel_audit_status": audit["status"],
        "source_files": [str(path) for path in files],
        "rows": int(summary[0]),
        "symbols": int(summary[1]),
        "first_ts": str(summary[2]),
        "last_ts": str(summary[3]),
        "forbidden_rows": int(summary[4]),
        "null_24h_labels": int(summary[5]),
        "missing_exit_policy": (
            "Rows remain point-in-time eligible. They are excluded from model fitting; "
            "if selected during portfolio validation they receive a conservative "
            "forced-loss outcome rather than being removed with future knowledge."
        ),
        "feature_count": len(features),
        "feature_sets": sets,
        "labels": labels,
        "matrix_root": str(MATRIX_ROOT),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({
        "rows": manifest["rows"],
        "symbols": manifest["symbols"],
        "first_ts": manifest["first_ts"],
        "last_ts": manifest["last_ts"],
        "feature_count": manifest["feature_count"],
        "feature_set_sizes": {
            key: len(value) for key, value in sets.items()
        },
        "physical_oos_isolation": True,
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
