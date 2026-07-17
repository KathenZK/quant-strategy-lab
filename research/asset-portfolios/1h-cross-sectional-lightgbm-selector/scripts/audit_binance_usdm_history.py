from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
INVENTORY_PATH = ARTIFACT_DIR / "binance_usdm_historical_inventory_2026-07-17.csv"
START_MONTH = "2020-01"
END_MONTH = "2026-06"
DATASETS = {
    "kline_1h": ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=1h/**/*.parquet",
    "mark_1h": ROOT
    / "data/normalized/mark_price_klines/exchange=binance/market_type=perp/timeframe=1h/**/*.parquet",
    "funding": ROOT
    / "data/normalized/funding_rates/exchange=binance/market_type=perp/**/*.parquet",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit normalized Binance USD-M 1h cross-sectional history."
    )
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    parser.add_argument("--start-month", default=START_MONTH)
    parser.add_argument("--end-month", default=END_MONTH)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def expected_symbol_months(
    inventory: pd.DataFrame,
    dataset: str,
    start_month: str,
    end_month: str,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    column = f"{dataset}_month_list"
    for item in inventory[["symbol", column]].itertuples(index=False):
        archive_symbol = str(item.symbol)
        value = getattr(item, column)
        months = [] if pd.isna(value) else str(value).split(";")
        for month in months:
            if start_month <= month <= end_month:
                rows.append(
                    {
                        "archive_symbol": archive_symbol,
                        "symbol": f"{archive_symbol.removesuffix('USDT')}/USDT:USDT",
                        "month": month,
                    }
                )
    return pd.DataFrame(rows)


def dataset_relation(connection: duckdb.DuckDBPyConnection, dataset: str) -> str:
    path = DATASETS[dataset]
    scan_root = Path(str(path).split("**", maxsplit=1)[0])
    if not list(scan_root.glob("**/*.parquet")):
        raise RuntimeError(f"no parquet files for {dataset}: {path}")
    view = f"lake_{dataset}"
    end_exclusive = (
        (pd.Period(END_MONTH, freq="M") + 1).start_time.tz_localize("UTC").isoformat()
    )
    timestamp_filter = (
        f"ts >= TIMESTAMPTZ '{START_MONTH}-01 00:00:00+00' "
        f"AND ts < TIMESTAMPTZ '{end_exclusive}'"
    )
    connection.execute(
        f"""
        CREATE OR REPLACE TEMP VIEW {view} AS
        SELECT *
        FROM read_parquet(
            '{sql_path(path)}',
            hive_partitioning = false,
            union_by_name = true
        )
        WHERE {timestamp_filter}
        """
    )
    return view


def scalar(connection: duckdb.DuckDBPyConnection, query: str) -> Any:
    return connection.execute(query).fetchone()[0]


def common_audit(connection: duckdb.DuckDBPyConnection, view: str) -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            strftime(min(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS first_ts,
            strftime(max(ts) AT TIME ZONE 'UTC', '%Y-%m-%dT%H:%M:%SZ') AS last_ts,
            count(*) FILTER (WHERE ts IS NULL OR symbol IS NULL) AS null_keys,
            count(*) FILTER (
                WHERE exchange != 'binance' OR market_type != 'perp'
            ) AS identity_violations,
            count(*) FILTER (WHERE source IS NULL OR source = '') AS missing_source
        FROM {view}
        """
    ).fetchone()
    duplicate_groups = scalar(
        connection,
        f"""
        SELECT count(*) FROM (
            SELECT ts, symbol
            FROM {view}
            GROUP BY ts, symbol
            HAVING count(*) > 1
        )
        """,
    )
    duplicate_rows = scalar(
        connection,
        f"""
        SELECT coalesce(sum(n - 1), 0) FROM (
            SELECT count(*) AS n
            FROM {view}
            GROUP BY ts, symbol
            HAVING count(*) > 1
        )
        """,
    )
    return {
        "rows": int(row[0]),
        "symbols": int(row[1]),
        "first_ts": str(row[2]),
        "last_ts": str(row[3]),
        "null_keys": int(row[4]),
        "identity_violations": int(row[5]),
        "missing_source": int(row[6]),
        "duplicate_key_groups": int(duplicate_groups),
        "duplicate_extra_rows": int(duplicate_rows),
    }


def kline_audit(
    connection: duckdb.DuckDBPyConnection,
    view: str,
    *,
    with_volume: bool,
) -> dict[str, Any]:
    volume_checks = (
        "count(*) FILTER (WHERE volume IS NULL OR quote_volume IS NULL OR "
        "trade_count IS NULL OR taker_buy_volume IS NULL OR "
        "taker_buy_quote_volume IS NULL) AS null_market_fields,"
        "count(*) FILTER (WHERE volume < 0 OR quote_volume < 0 OR trade_count < 0 "
        "OR taker_buy_volume < 0 OR taker_buy_quote_volume < 0) "
        "AS negative_market_fields,"
        if with_volume
        else "0 AS null_market_fields, 0 AS negative_market_fields,"
    )
    row = connection.execute(
        f"""
        SELECT
            count(*) FILTER (
                WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
            ) AS null_ohlc,
            count(*) FILTER (
                WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
            ) AS nonpositive_ohlc,
            count(*) FILTER (
                WHERE high < greatest(open, close) OR low > least(open, close)
                   OR high < low
            ) AS invalid_ohlc,
            {volume_checks}
            count(*) FILTER (WHERE timeframe != '1h') AS timeframe_violations,
            count(*) FILTER (WHERE is_closed IS DISTINCT FROM TRUE) AS unclosed_rows
        FROM {view}
        """
    ).fetchone()
    return {
        "null_ohlc": int(row[0]),
        "nonpositive_ohlc": int(row[1]),
        "invalid_ohlc": int(row[2]),
        "null_market_fields": int(row[3]),
        "negative_market_fields": int(row[4]),
        "timeframe_violations": int(row[5]),
        "unclosed_rows": int(row[6]),
    }


def continuity_audit(
    connection: duckdb.DuckDBPyConnection,
    view: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = connection.execute(
        f"""
        WITH differences AS (
            SELECT
                symbol,
                ts,
                date_diff(
                    'hour',
                    lag(ts) OVER (PARTITION BY symbol ORDER BY ts),
                    ts
                ) AS delta_hours
            FROM {view}
        )
        SELECT
            symbol,
            count(*) FILTER (WHERE delta_hours > 1) AS gap_events,
            coalesce(sum(delta_hours - 1) FILTER (WHERE delta_hours > 1), 0)
                AS missing_hours,
            max(delta_hours) AS max_gap_hours
        FROM differences
        GROUP BY symbol
        ORDER BY missing_hours DESC, symbol
        """
    ).fetch_df()
    summary = {
        "symbols_with_gaps": int(frame["gap_events"].gt(0).sum()),
        "gap_events": int(frame["gap_events"].sum()),
        "estimated_missing_hours": int(frame["missing_hours"].sum()),
        "max_gap_hours": int(frame["max_gap_hours"].max()),
    }
    return summary, frame


def archive_coverage(
    connection: duckdb.DuckDBPyConnection,
    view: str,
    expected: pd.DataFrame,
    dataset: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    expected_name = f"expected_{dataset}"
    connection.register(expected_name, expected)
    actual = connection.execute(
        f"""
        SELECT
            symbol,
            strftime(ts AT TIME ZONE 'UTC', '%Y-%m') AS month,
            count(*) AS rows
        FROM {view}
        GROUP BY symbol, month
        """
    ).fetch_df()
    merged = expected.merge(actual, on=["symbol", "month"], how="left")
    missing = merged.loc[merged["rows"].isna()].copy()
    return {
        "expected_symbol_months": int(len(expected)),
        "present_symbol_months": int(merged["rows"].notna().sum()),
        "missing_symbol_months": int(len(missing)),
    }, missing


def funding_audit(connection: duckdb.DuckDBPyConnection, view: str) -> dict[str, Any]:
    row = connection.execute(
        f"""
        SELECT
            count(*) FILTER (WHERE funding_rate IS NULL) AS null_rates,
            count(*) FILTER (WHERE funding_interval_hours IS NULL) AS null_intervals,
            count(*) FILTER (WHERE funding_interval_hours <= 0) AS invalid_intervals,
            count(*) FILTER (WHERE abs(funding_rate) > 0.10) AS extreme_rates,
            count(*) FILTER (WHERE next_funding_ts <= ts) AS invalid_next_ts
        FROM {view}
        """
    ).fetchone()
    return {
        "null_rates": int(row[0]),
        "null_intervals": int(row[1]),
        "invalid_intervals": int(row[2]),
        "absolute_rate_gt_10pct": int(row[3]),
        "invalid_next_funding_ts": int(row[4]),
    }


def strict_blockers(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for dataset, audit in report["datasets"].items():
        common = audit["common"]
        for key in [
            "null_keys",
            "identity_violations",
            "missing_source",
            "duplicate_key_groups",
        ]:
            if common[key]:
                blockers.append(f"{dataset}.{key}={common[key]}")
        if audit["archive_coverage"]["missing_symbol_months"]:
            blockers.append(
                f"{dataset}.missing_symbol_months="
                f"{audit['archive_coverage']['missing_symbol_months']}"
            )
    for dataset in ["kline_1h", "mark_1h"]:
        detail = report["datasets"][dataset]["market_data"]
        for key in [
            "null_ohlc",
            "nonpositive_ohlc",
            "invalid_ohlc",
            "null_market_fields",
            "negative_market_fields",
            "timeframe_violations",
            "unclosed_rows",
        ]:
            if detail[key]:
                blockers.append(f"{dataset}.{key}={detail[key]}")
    funding = report["datasets"]["funding"]["funding"]
    for key in ["null_rates", "invalid_intervals", "invalid_next_funding_ts"]:
        if funding[key]:
            blockers.append(f"funding.{key}={funding[key]}")
    return blockers


def main() -> None:
    args = parse_args()
    global START_MONTH, END_MONTH
    START_MONTH = args.start_month
    END_MONTH = args.end_month
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    inventory = pd.read_csv(args.inventory, dtype={"symbol": str})
    connection = duckdb.connect()
    report: dict[str, Any] = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "research_months": {"start": START_MONTH, "end": END_MONTH},
        "datasets": {},
    }
    gap_frames = []
    missing_frames = []
    for dataset in DATASETS:
        view = dataset_relation(connection, dataset)
        expected = expected_symbol_months(
            inventory,
            dataset,
            START_MONTH,
            END_MONTH,
        )
        coverage, missing = archive_coverage(
            connection,
            view,
            expected,
            dataset,
        )
        continuity = None
        detail: dict[str, Any] = {
            "common": common_audit(connection, view),
            "archive_coverage": coverage,
        }
        if dataset == "funding":
            detail["funding"] = funding_audit(connection, view)
        else:
            detail["market_data"] = kline_audit(
                connection,
                view,
                with_volume=dataset == "kline_1h",
            )
            continuity, gaps = continuity_audit(connection, view)
            detail["continuity"] = continuity
            gaps.insert(0, "dataset", dataset)
            gap_frames.append(gaps)
        report["datasets"][dataset] = detail
        if not missing.empty:
            missing.insert(0, "dataset", dataset)
            missing_frames.append(missing)

    report["blockers"] = strict_blockers(report)
    report["status"] = "PASS" if not report["blockers"] else "BLOCKED"
    stamp = pd.Timestamp.now("UTC").strftime("%Y%m%dT%H%M%SZ")
    report_path = ARTIFACT_DIR / f"binance_usdm_data_quality_{stamp}.json"
    gaps_path = ARTIFACT_DIR / f"binance_usdm_internal_gaps_{stamp}.csv"
    missing_path = ARTIFACT_DIR / f"binance_usdm_missing_symbol_months_{stamp}.csv"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat(gap_frames, ignore_index=True).to_csv(gaps_path, index=False)
    if missing_frames:
        pd.concat(missing_frames, ignore_index=True).to_csv(missing_path, index=False)
    else:
        pd.DataFrame(columns=["dataset", "archive_symbol", "symbol", "month", "rows"]).to_csv(
            missing_path,
            index=False,
        )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    print(f"report -> {report_path}")
    print(f"gaps -> {gaps_path}")
    print(f"missing -> {missing_path}")
    if args.strict and report["blockers"]:
        raise RuntimeError(f"data quality blockers: {report['blockers']}")


if __name__ == "__main__":
    main()
