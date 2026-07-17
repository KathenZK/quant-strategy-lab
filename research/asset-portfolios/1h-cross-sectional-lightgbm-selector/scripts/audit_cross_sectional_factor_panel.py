from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from strategy_lab.data.factors.multi_asset_1h import multi_asset_1h_registry


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATASET_ROOT = ARTIFACT_DIR / "cross_sectional_factor_dataset"
PANEL_GLOB = DATASET_ROOT / "panel/**/*.parquet"
CATALOG_PATH = ARTIFACT_DIR / "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
OOS_START = "2026-04-01T00:00:00Z"
OOS_END = "2026-07-01T00:00:00Z"
PURGED_PRE_OOS_END = "2026-03-31T00:00:00Z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the crypto-only cross-sectional factor panel."
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def scalar(connection: duckdb.DuckDBPyConnection, query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def main() -> None:
    args = parse_args()
    if not list((DATASET_ROOT / "panel").glob("**/*.parquet")):
        raise RuntimeError(f"factor panel is missing: {PANEL_GLOB}")
    connection = duckdb.connect()
    connection.execute(
        f"""
        CREATE TEMP VIEW panel AS
        SELECT * FROM read_parquet(
            '{sql_path(PANEL_GLOB)}',
            hive_partitioning = false,
            union_by_name = true
        )
        """
    )
    common = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            strftime(min(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS first_ts,
            strftime(max(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS last_ts,
            count(*) FILTER (WHERE ts IS NULL OR symbol IS NULL) AS null_keys,
            count(*) FILTER (WHERE universe_main) AS main_rows,
            count(*) FILTER (WHERE ts < TIMESTAMPTZ '{PURGED_PRE_OOS_END}')
                AS purged_pre_oos_rows,
            count(*) FILTER (
                WHERE ts >= TIMESTAMPTZ '{OOS_START}'
                  AND ts < TIMESTAMPTZ '{OOS_END}'
            ) AS sealed_oos_rows
        FROM panel
        """
    ).fetchone()
    duplicate_groups = int(
        scalar(
            connection,
            """
            SELECT count(*) FROM (
                SELECT ts, symbol FROM panel
                GROUP BY ts, symbol HAVING count(*) > 1
            )
            """,
        )
    )
    excluded_rows = int(
        scalar(
            connection,
            f"""
            SELECT count(*)
            FROM panel
            INNER JOIN read_csv_auto('{sql_path(CATALOG_PATH)}', header = true)
            USING (symbol)
            WHERE NOT eligible
            """,
        )
    )
    invalid_universe_rows = int(
        scalar(
            connection,
            """
            SELECT count(*) FROM panel
            WHERE age_hours < 720 OR coverage_30d < 0.99
               OR avg_daily_quote_volume_7d < 5000000
               OR liquidity_rank > 150
            """,
        )
    )
    monthly = connection.execute(
        """
        SELECT
            strftime(ts AT TIME ZONE 'UTC', '%Y-%m') AS month,
            count(DISTINCT symbol) AS broad_symbols,
            count(DISTINCT symbol) FILTER (WHERE universe_main) AS main_symbols,
            count(*) AS rows,
            count(*) FILTER (WHERE universe_main) AS main_rows
        FROM panel
        GROUP BY month ORDER BY month
        """
    ).fetch_df()
    factor_names = multi_asset_1h_registry().names()
    cs_names = [
        row[0]
        for row in connection.execute("DESCRIBE panel").fetchall()
        if str(row[0]).startswith("cs_rank_")
    ]
    audited_features = factor_names + cs_names + [
        "relative_to_btc_24",
        "relative_to_btc_168",
        "market_breadth_ret24_positive",
        "market_breadth_trend_positive",
        "market_median_realized_vol_24",
    ]
    coverage_expressions = ",\n".join(
        f"avg(CASE WHEN {name} IS NOT NULL AND isfinite({name}) THEN 1.0 ELSE 0.0 END) AS \"{name}\""
        for name in audited_features
    )
    coverage_row = connection.execute(
        f"""
        SELECT {coverage_expressions}
        FROM panel
        WHERE ts < TIMESTAMPTZ '{PURGED_PRE_OOS_END}'
          AND universe_main
        """
    ).fetch_df().iloc[0]
    coverage = pd.DataFrame(
        {
            "feature": coverage_row.index,
            "pre_oos_coverage": coverage_row.to_numpy(dtype="float64"),
        }
    ).sort_values(["pre_oos_coverage", "feature"])
    coverage_path = ARTIFACT_DIR / "factor_coverage_pre_oos_2026-07-17.csv"
    coverage.to_csv(coverage_path, index=False)
    monthly_path = ARTIFACT_DIR / "dynamic_universe_monthly_2026-07-17.csv"
    monthly.to_csv(monthly_path, index=False)

    blockers = []
    checks = {
        "null_keys": int(common[4]),
        "duplicate_key_groups": duplicate_groups,
        "excluded_non_crypto_rows": excluded_rows,
        "invalid_point_in_time_universe_rows": invalid_universe_rows,
        "features_below_80pct_pre_oos_coverage": int(
            coverage["pre_oos_coverage"].lt(0.80).sum()
        ),
    }
    for key in [
        "null_keys",
        "duplicate_key_groups",
        "excluded_non_crypto_rows",
        "invalid_point_in_time_universe_rows",
    ]:
        if checks[key]:
            blockers.append(f"{key}={checks[key]}")
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "blockers": blockers,
        "panel": {
            "rows": int(common[0]),
            "symbols": int(common[1]),
            "first_ts": str(common[2]),
            "last_ts": str(common[3]),
            "main_rows": int(common[5]),
            "purged_pre_oos_rows": int(common[6]),
            "sealed_oos_rows": int(common[7]),
        },
        "checks": checks,
        "feature_count": len(audited_features),
        "minimum_feature_coverage": float(coverage["pre_oos_coverage"].min()),
        "oos_policy": (
            "Only row count and key integrity were inspected; no OOS label, "
            "prediction, return, or performance statistics were computed."
        ),
        "coverage_csv": str(coverage_path),
        "dynamic_universe_csv": str(monthly_path),
    }
    report_path = ARTIFACT_DIR / "cross_sectional_factor_panel_audit_2026-07-17.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.strict and blockers:
        raise RuntimeError(f"factor panel blockers: {blockers}")


if __name__ == "__main__":
    main()
