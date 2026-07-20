from __future__ import annotations

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
DATASET_ROOT = ARTIFACT_DIR / "multihorizon_factor_dataset"
PANEL_GLOB = DATASET_ROOT / "panel/**/*.parquet"
MANIFEST_PATH = DATASET_ROOT / "factor_dataset_manifest.json"
AUDIT_PATH = ARTIFACT_DIR / "factor_panel_audit_2026-07-18.json"
COVERAGE_PATH = ARTIFACT_DIR / "factor_coverage_2026-07-18.csv"
HORIZONS = (4, 8, 12, 24, 48)
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
REUSED_END = pd.Timestamp("2026-07-01T00:00:00Z")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
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


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def scalar(connection: duckdb.DuckDBPyConnection, query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def feature_names(manifest: dict[str, Any]) -> list[str]:
    names = list(manifest["base_factor_names"])
    names.extend(
        f"cs_rank_{name}" for name in manifest["cross_sectional_rank_factors"]
    )
    names.extend(CONTEXT_FEATURES)
    return list(dict.fromkeys(names))


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise RuntimeError("factor dataset manifest is not PASS")
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    relation = (
        f"read_parquet('{sql_path(PANEL_GLOB)}', "
        "hive_partitioning=false, union_by_name=true)"
    )
    schema = connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetch_df()
    columns = set(schema["column_name"])
    features = feature_names(manifest)
    missing_features = sorted(set(features) - columns)
    if missing_features:
        raise RuntimeError(f"manifest features missing from panel: {missing_features}")

    summary_row = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            strftime(min(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ')
                AS first_ts,
            strftime(max(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ')
                AS last_ts,
            count(*) FILTER (WHERE ts >= TIMESTAMPTZ '{PROSPECTIVE_START.isoformat()}')
                AS prospective_rows,
            count(*) FILTER (WHERE universe_main) AS main_rows,
            max(liquidity_rank) AS max_liquidity_rank,
            count(*) FILTER (WHERE liquidity_rank > 150) AS rank_over_150,
            count(*) FILTER (WHERE ts IS NULL OR symbol IS NULL) AS null_keys
        FROM {relation}
        """
    ).fetchone()
    duplicate_groups = int(
        scalar(
            connection,
            f"""
            SELECT count(*) FROM (
                SELECT ts, symbol FROM {relation}
                GROUP BY ts, symbol HAVING count(*) > 1
            )
            """,
        )
    )

    coverage_expressions = []
    for feature in features:
        coverage_expressions.extend(
            [
                f"count({feature}) FILTER (WHERE universe_main AND "
                f"ts < TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}') "
                f"AS dev__{feature}",
                f"count({feature}) FILTER (WHERE universe_main AND "
                f"ts >= TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}' AND "
                f"ts < TIMESTAMPTZ '{REUSED_END.isoformat()}') "
                f"AS reused__{feature}",
                f"count(*) FILTER (WHERE universe_main AND {feature} IS NOT NULL "
                f"AND NOT isfinite({feature})) AS inf__{feature}",
            ]
        )
    denominator = connection.execute(
        f"""
        SELECT
            count(*) FILTER (WHERE universe_main AND
                ts < TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}') AS dev_rows,
            count(*) FILTER (WHERE universe_main AND
                ts >= TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}' AND
                ts < TIMESTAMPTZ '{REUSED_END.isoformat()}') AS reused_rows
        FROM {relation}
        """
    ).fetchone()
    coverage_values = connection.execute(
        f"SELECT {', '.join(coverage_expressions)} FROM {relation}"
    ).fetchone()
    coverage_rows = []
    for index, feature in enumerate(features):
        development_count = int(coverage_values[index * 3])
        reused_count = int(coverage_values[index * 3 + 1])
        infinity_count = int(coverage_values[index * 3 + 2])
        coverage_rows.append(
            {
                "factor": feature,
                "development_non_null": development_count,
                "development_coverage": development_count / int(denominator[0]),
                "reused_non_null": reused_count,
                "reused_coverage": reused_count / int(denominator[1]),
                "infinity_count": infinity_count,
            }
        )
    coverage = pd.DataFrame(coverage_rows).sort_values(
        ["development_coverage", "factor"], ascending=[False, True]
    )
    coverage.to_csv(COVERAGE_PATH, index=False)

    rank_columns = [
        feature for feature in features if feature.startswith("cs_rank_")
    ]
    rank_violations = {}
    for column in rank_columns:
        count = int(
            scalar(
                connection,
                f"""
                SELECT count(*) FROM {relation}
                WHERE {column} IS NOT NULL AND ({column} < 0 OR {column} > 1)
                """,
            )
        )
        if count:
            rank_violations[column] = count

    label_audits = {}
    blockers = []
    for horizon in HORIZONS:
        row = connection.execute(
            f"""
            SELECT
                count(*) FILTER (WHERE label_path_valid_{horizon}h) AS valid_rows,
                count(*) FILTER (WHERE NOT label_path_valid_{horizon}h) AS invalid_rows,
                count(*) FILTER (
                    WHERE label_path_valid_{horizon}h AND (
                        label_long_net_{horizon}h IS NULL OR
                        label_short_net_{horizon}h IS NULL OR
                        label_gross_return_{horizon}h IS NULL OR
                        label_funding_sum_{horizon}h IS NULL
                    )
                ) AS valid_null_labels,
                count(*) FILTER (
                    WHERE NOT label_path_valid_{horizon}h AND (
                        label_long_net_{horizon}h IS NOT NULL OR
                        label_short_net_{horizon}h IS NOT NULL
                    )
                ) AS invalid_non_null_labels,
                max(abs(
                    label_long_net_{horizon}h + label_short_net_{horizon}h
                    + {2.0 * ROUND_TRIP_COST}
                )) FILTER (WHERE label_path_valid_{horizon}h)
                    AS max_long_short_identity_error,
                count(*) FILTER (WHERE label_long_mae_{horizon}h > 0) AS long_mae_positive,
                count(*) FILTER (WHERE label_short_mae_{horizon}h > 0) AS short_mae_positive,
                count(*) FILTER (WHERE label_long_mfe_{horizon}h < 0) AS long_mfe_negative,
                count(*) FILTER (WHERE label_short_mfe_{horizon}h < 0) AS short_mfe_negative
            FROM {relation}
            """
        ).fetchone()
        detail = {
            "valid_rows": int(row[0]),
            "invalid_rows": int(row[1]),
            "valid_null_labels": int(row[2]),
            "invalid_non_null_labels": int(row[3]),
            "max_long_short_identity_error": float(row[4]),
            "long_mae_positive": int(row[5]),
            "short_mae_positive": int(row[6]),
            "long_mfe_negative": int(row[7]),
            "short_mfe_negative": int(row[8]),
        }
        label_audits[f"{horizon}h"] = detail
        for key in [
            "valid_null_labels",
            "invalid_non_null_labels",
            "long_mae_positive",
            "short_mae_positive",
            "long_mfe_negative",
            "short_mfe_negative",
        ]:
            if detail[key]:
                blockers.append(f"labels.{horizon}h.{key}={detail[key]}")
        if detail["max_long_short_identity_error"] > 1e-10:
            blockers.append(
                f"labels.{horizon}h.identity_error="
                f"{detail['max_long_short_identity_error']}"
            )

    if int(summary_row[4]):
        blockers.append(f"prospective_rows={summary_row[4]}")
    if duplicate_groups:
        blockers.append(f"duplicate_key_groups={duplicate_groups}")
    if int(summary_row[7]):
        blockers.append(f"rank_over_150={summary_row[7]}")
    if int(summary_row[8]):
        blockers.append(f"null_keys={summary_row[8]}")
    if rank_violations:
        blockers.append(f"rank_range_violations={sum(rank_violations.values())}")
    infinity_total = int(coverage["infinity_count"].sum())
    if infinity_total:
        blockers.append(f"factor_infinity_count={infinity_total}")

    audit = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "panel": {
            "rows": int(summary_row[0]),
            "symbols": int(summary_row[1]),
            "first_ts": str(summary_row[2]),
            "last_ts": str(summary_row[3]),
            "prospective_rows": int(summary_row[4]),
            "main_rows": int(summary_row[5]),
            "max_liquidity_rank": int(summary_row[6]),
            "duplicate_key_groups": duplicate_groups,
            "null_keys": int(summary_row[8]),
        },
        "features": {
            "count": len(features),
            "base_count": manifest["base_factor_count"],
            "cross_sectional_rank_count": len(rank_columns),
            "context_count": len(CONTEXT_FEATURES),
            "minimum_development_coverage": float(
                coverage["development_coverage"].min()
            ),
            "median_development_coverage": float(
                coverage["development_coverage"].median()
            ),
            "features_below_95pct_coverage": int(
                coverage["development_coverage"].lt(0.95).sum()
            ),
            "infinity_count": infinity_total,
            "rank_range_violations": rank_violations,
            "coverage_artifact": str(COVERAGE_PATH.relative_to(ROOT)),
        },
        "labels": label_audits,
        "leakage_evidence": {
            "factor_future_perturbation_test": "tests/test_multi_asset_tail_1h_factors.py",
            "label_timing_and_gap_test": "tests/test_multihorizon_labels.py",
            "prospective_oos_outcomes_read": False,
        },
        "blockers": blockers,
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"factor panel blockers: {blockers}")


if __name__ == "__main__":
    main()
