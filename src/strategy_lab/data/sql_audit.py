from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from strategy_lab.data.authenticity import (
    DEFAULT_BLOCKED_SOURCE_PATTERNS,
    DEFAULT_REAL_SOURCE_ALLOWLIST,
)
from strategy_lab.data.sessions import timeframe_delta

SQL_AUDIT_RULE_VERSION = "binance_ohlcv_sql_audit_v1"
REQUIRED_OHLCV_COLUMNS = (
    "ts",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "vwap",
    "is_closed",
    "source",
)


def timeframe_seconds(timeframe: str) -> int:
    return int(timeframe_delta(timeframe).total_seconds())


def unverified_source_sql(column: str = "source") -> str:
    """SQL predicate: true when source is missing, blocked, unknown, or illegal composite."""

    src = f"lower(trim(CAST({column} AS VARCHAR)))"
    parts = (
        f"list_filter(string_split(replace({src}, 'composite:', ''), '+'), "
        "part -> length(trim(part)) > 0)"
    )
    part_bad = (
        "NOT list_contains(allowed_sources, trim(part)) "
        "OR len(list_filter(blocked_patterns, p -> contains(trim(part), p))) > 0"
    )
    atomic_bad = (
        f"NOT list_contains(allowed_sources, {src}) "
        f"OR len(list_filter(blocked_patterns, p -> contains({src}, p))) > 0"
    )
    return f"""
    (
      {column} IS NULL
      OR (
        starts_with({src}, 'composite:')
        AND (
          len({parts}) < 2
          OR len(list_filter({parts}, part -> {part_bad})) > 0
        )
      )
      OR (
        NOT starts_with({src}, 'composite:')
        AND ({atomic_bad})
      )
    )
    """


def describe_parquet_columns(
    connection: duckdb.DuckDBPyConnection,
    files: list[Path],
) -> list[str]:
    described = connection.execute(
        "DESCRIBE SELECT * FROM read_parquet(?, hive_partitioning = false, union_by_name = true) LIMIT 0",
        [[str(path) for path in files]],
    ).fetch_df()
    return [str(name) for name in described["column_name"].tolist()]


def _quality_status(schema_errors: list[str], blockers: dict[str, Any]) -> str:
    if schema_errors:
        return "FAIL"
    for key, value in blockers.items():
        if key == "schema_errors":
            continue
        if int(value or 0) > 0:
            return "FAIL"
    return "PASS"


def audit_selected_sql(
    connection: duckdb.DuckDBPyConnection,
    *,
    selected_cte: str,
    params: list[Any],
    timeframe: str,
    require_closed: bool,
    allowed_sources: tuple[str, ...] = DEFAULT_REAL_SOURCE_ALLOWLIST,
    blocked_source_patterns: tuple[str, ...] = DEFAULT_BLOCKED_SOURCE_PATTERNS,
    columns: list[str] | None = None,
    cutoff_unclosed_excluded_rows: int = 0,
) -> dict[str, Any]:
    schema_errors: list[str] = []
    present = set(columns or [])
    missing = [name for name in REQUIRED_OHLCV_COLUMNS if name not in present]
    if missing:
        schema_errors.append(f"missing required columns: {missing}")
        return {
            "rule_version": SQL_AUDIT_RULE_VERSION,
            "quality_status": "FAIL",
            "rows": 0,
            "trusted": False,
            "schema_errors": schema_errors,
            "blockers": {"schema_errors": schema_errors},
            "source_counts": {},
            "duplicate_rows": 0,
            "open_rows": 0,
            "timeframe_mismatches": 0,
            "internal_missing_bars": 0,
            "unaligned_gap_transitions": 0,
            "cutoff_unclosed_excluded_rows": int(cutoff_unclosed_excluded_rows),
        }

    seconds = timeframe_seconds(timeframe)
    allowed = [source.strip().lower() for source in allowed_sources]
    blocked = [pattern.strip().lower() for pattern in blocked_source_patterns]
    source_pred = unverified_source_sql("source")
    numeric_cols = [
        name
        for name in ("open", "high", "low", "close", "volume", "quote_volume", "vwap")
        if not present or name in present
    ]
    finite_pred = " OR ".join(f"NOT isfinite(CAST({name} AS DOUBLE))" for name in numeric_cols) or "FALSE"
    config_and_selected = f"""
        config AS (
            SELECT ?::VARCHAR[] AS allowed_sources, ?::VARCHAR[] AS blocked_patterns
        ),
        {selected_cte}
    """
    query_params = [allowed, blocked, *params]
    row = connection.execute(
        f"""
        WITH {config_and_selected}
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbol_count,
            min(ts) AS start_ts,
            max(ts) AS end_ts,
            count(*) - count(DISTINCT (exchange, symbol, market_type, timeframe, ts))
                AS duplicate_business_key_rows,
            count(*) FILTER (
                WHERE ts IS NULL OR exchange IS NULL OR symbol IS NULL
                   OR market_type IS NULL OR timeframe IS NULL
                   OR open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                   OR volume IS NULL OR quote_volume IS NULL OR trade_count IS NULL
                   OR vwap IS NULL OR is_closed IS NULL OR source IS NULL
            ) AS critical_null_rows,
            count(*) FILTER (WHERE {finite_pred}) AS non_finite_rows,
            count(*) FILTER (
                WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                   OR high < greatest(open, close, low)
                   OR low > least(open, close, high)
                   OR vwap <= 0
            ) AS illegal_ohlc_rows,
            count(*) FILTER (
                WHERE volume < 0 OR quote_volume < 0
                   OR trade_count < 0
                   OR trade_count != floor(CAST(trade_count AS DOUBLE))
            ) AS negative_volume_or_count_rows,
            count(*) FILTER (WHERE {source_pred}) AS unverified_source_rows,
            count(*) FILTER (WHERE NOT CAST(is_closed AS BOOLEAN)) AS open_rows,
            count(*) FILTER (
                WHERE lower(trim(CAST(timeframe AS VARCHAR))) != lower(trim(?))
            ) AS timeframe_mismatches,
            count(*) FILTER (
                WHERE CAST(epoch(ts) AS BIGINT) % {seconds} != 0
            ) AS off_grid_rows
        FROM selected, config
        """,
        [*query_params, timeframe],
    ).fetch_df().iloc[0]

    sources = connection.execute(
        f"""
        WITH {selected_cte}
        SELECT CAST(source AS VARCHAR) AS source, count(*) AS rows
        FROM selected
        GROUP BY 1
        ORDER BY rows DESC
        """,
        params,
    ).fetch_df()
    source_counts = {str(item["source"]): int(item["rows"]) for _, item in sources.iterrows()}

    gaps = connection.execute(
        f"""
        WITH {selected_cte},
        ordered AS (
            SELECT
                symbol,
                ts,
                lag(ts) OVER (PARTITION BY symbol ORDER BY ts) AS prev_ts
            FROM selected
        ),
        gap_rows AS (
            SELECT datediff('second', prev_ts, ts) AS delta_sec
            FROM ordered
            WHERE prev_ts IS NOT NULL
        )
        SELECT
            count(*) FILTER (WHERE delta_sec > {seconds}) AS internal_gap_transitions,
            coalesce(
                sum(
                    CASE
                        WHEN delta_sec > {seconds} THEN (delta_sec / {seconds}) - 1
                        ELSE 0
                    END
                ),
                0
            ) AS internal_missing_bars,
            count(*) FILTER (
                WHERE delta_sec > {seconds} AND (delta_sec % {seconds}) != 0
            ) AS unaligned_gap_transitions
        FROM gap_rows
        """,
        params,
    ).fetch_df().iloc[0]

    blockers: dict[str, Any] = {
        "schema_errors": schema_errors,
        "duplicate_business_key_rows": int(row["duplicate_business_key_rows"] or 0),
        "critical_null_rows": int(row["critical_null_rows"] or 0),
        "non_finite_rows": int(row["non_finite_rows"] or 0),
        "illegal_ohlc_rows": int(row["illegal_ohlc_rows"] or 0),
        "negative_volume_or_count_rows": int(row["negative_volume_or_count_rows"] or 0),
        "unverified_source_rows": int(row["unverified_source_rows"] or 0),
        "timeframe_mismatches": int(row["timeframe_mismatches"] or 0),
        "off_grid_rows": int(row["off_grid_rows"] or 0),
        "unaligned_gap_transitions": int(gaps["unaligned_gap_transitions"] or 0),
    }
    if require_closed:
        blockers["open_rows"] = int(row["open_rows"] or 0)

    quality_status = _quality_status(schema_errors, blockers)
    start_ts = row["start_ts"]
    end_ts = row["end_ts"]
    visible_blockers = {
        key: value
        for key, value in blockers.items()
        if (key == "schema_errors" and value) or (key != "schema_errors" and int(value) > 0)
    }
    return {
        "rule_version": SQL_AUDIT_RULE_VERSION,
        "quality_status": quality_status,
        "rows": int(row["rows"] or 0),
        "symbol_count": int(row["symbol_count"] or 0),
        "start_utc": pd.Timestamp(start_ts).isoformat() if pd.notna(start_ts) else None,
        "end_utc": pd.Timestamp(end_ts).isoformat() if pd.notna(end_ts) else None,
        "duplicate_rows": int(row["duplicate_business_key_rows"] or 0),
        "duplicate_business_key_rows": int(row["duplicate_business_key_rows"] or 0),
        "critical_null_rows": int(row["critical_null_rows"] or 0),
        "non_finite_rows": int(row["non_finite_rows"] or 0),
        "illegal_ohlc_rows": int(row["illegal_ohlc_rows"] or 0),
        "negative_volume_or_count_rows": int(row["negative_volume_or_count_rows"] or 0),
        "unverified_source_rows": int(row["unverified_source_rows"] or 0),
        "open_rows": int(row["open_rows"] or 0),
        "timeframe_mismatches": int(row["timeframe_mismatches"] or 0),
        "off_grid_rows": int(row["off_grid_rows"] or 0),
        "internal_gap_transitions": int(gaps["internal_gap_transitions"] or 0),
        "internal_missing_bars": int(gaps["internal_missing_bars"] or 0),
        "unaligned_gap_transitions": int(gaps["unaligned_gap_transitions"] or 0),
        "missing_bars": int(gaps["internal_missing_bars"] or 0),
        "unexpected_intervals": int(gaps["unaligned_gap_transitions"] or 0),
        "cutoff_unclosed_excluded_rows": int(cutoff_unclosed_excluded_rows),
        "schema_errors": schema_errors,
        "source_counts": source_counts,
        "blockers": visible_blockers,
        "gap_classification": {
            "listing_boundary": (
                "symbol first/last bars are listing edges; they are not counted as internal gaps"
            ),
            "internal_aligned_gaps": "missing multiples of the timeframe inside a symbol span",
            "unaligned_gaps": "internal jumps that are not a multiple of the timeframe",
            "incomplete_aggregation_buckets": (
                "derived complete-bucket formula drops incomplete windows; "
                "those appear as aligned internal gaps"
            ),
        },
        "trusted": quality_status == "PASS",
    }
