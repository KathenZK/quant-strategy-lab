from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from strategy_lab.data.factors.multi_asset_1h import multi_asset_1h_registry


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATASET_ROOT = ARTIFACT_DIR / "cross_sectional_factor_dataset"
STAGING_ROOT = DATASET_ROOT / "staging"
BY_SYMBOL_ROOT = DATASET_ROOT / "by_symbol"
LIQUID_MONTHLY_ROOT = DATASET_ROOT / "liquid_monthly"
PANEL_ROOT = DATASET_ROOT / "panel"
DUCKDB_PANEL_TEMP_ROOT = DATASET_ROOT / "duckdb_panel_temp"
MANIFEST_PATH = DATASET_ROOT / "factor_dataset_manifest.json"
UNIVERSE_CATALOG_PATH = (
    ARTIFACT_DIR / "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
)
OOS_START = pd.Timestamp("2026-04-01T00:00:00Z")
OOS_END = pd.Timestamp("2026-07-01T00:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
HORIZONS = (4, 12, 24)

OHLCV_GLOB = ROOT / (
    "data/normalized/ohlcv/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet"
)
MARK_GLOB = ROOT / (
    "data/normalized/mark_price_klines/exchange=binance/market_type=perp/"
    "timeframe=1h/**/*.parquet"
)
FUNDING_GLOB = ROOT / (
    "data/normalized/funding_rates/exchange=binance/market_type=perp/**/*.parquet"
)

CROSS_SECTIONAL_FACTORS = [
    "ret_4",
    "ret_12",
    "ret_24",
    "ret_72",
    "ret_168",
    "ema_spread_6_24",
    "ema_spread_24_96",
    "ema_spread_96_384",
    "ma_distance_24",
    "ma_distance_96",
    "rsi_24",
    "atr_pct_24",
    "atr_pct_168",
    "realized_vol_24",
    "realized_vol_168",
    "max_drawdown_72",
    "max_drawdown_336",
    "quote_volume_ratio_24",
    "trade_count_ratio_24",
    "taker_imbalance_mean_24",
    "funding_rate",
    "funding_zscore_168",
    "mark_premium",
    "mark_premium_zscore_168",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build the leakage-safe point-in-time Binance USD-M 1h factor panel."
        )
    )
    parser.add_argument("--quality-report", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--symbols", nargs="*")
    return parser.parse_args()


def path_sql(path: Path) -> str:
    return str(path).replace("'", "''")


def latest_quality_report() -> Path:
    candidates = sorted(ARTIFACT_DIR.glob("binance_usdm_data_quality_*.json"))
    if not candidates:
        raise RuntimeError("no Binance USD-M data-quality report exists")
    return candidates[-1]


def validate_quality_report(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("blockers"):
        raise RuntimeError(f"data-quality report is not PASS: {path}")
    months = report.get("research_months", {})
    if months.get("start") != "2020-01" or months.get("end") != "2026-06":
        raise RuntimeError(
            "factor panel requires the final 2020-01..2026-06 quality report"
        )
    return report


def stage_inputs(*, overwrite: bool) -> tuple[Path, Path]:
    market_root = STAGING_ROOT / "market"
    funding_root = STAGING_ROOT / "funding"
    if overwrite:
        shutil.rmtree(STAGING_ROOT, ignore_errors=True)
    if list(market_root.glob("symbol_slug=*/*.parquet")) and list(
        funding_root.glob("symbol_slug=*/*.parquet")
    ):
        return market_root, funding_root

    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    market_root.mkdir(parents=True, exist_ok=True)
    funding_root.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"""
        COPY (
            SELECT
                o.ts,
                o.exchange,
                o.symbol,
                o.market_type,
                o.timeframe,
                o.open,
                o.high,
                o.low,
                o.close,
                o.volume,
                o.quote_volume,
                o.trade_count,
                o.taker_buy_volume,
                o.taker_buy_quote_volume,
                o.vwap,
                m.close AS mark_price,
                lower(replace(replace(o.symbol, '/', '_'), ':', '_')) AS symbol_slug
            FROM read_parquet(
                '{path_sql(OHLCV_GLOB)}',
                hive_partitioning = false,
                union_by_name = true
            ) AS o
            LEFT JOIN read_parquet(
                '{path_sql(MARK_GLOB)}',
                hive_partitioning = false,
                union_by_name = true
            ) AS m
            USING (ts, symbol)
            WHERE o.ts >= TIMESTAMPTZ '2020-01-01 00:00:00+00'
              AND o.ts < TIMESTAMPTZ '2026-07-01 00:00:00+00'
        ) TO '{path_sql(market_root)}' (
            FORMAT PARQUET,
            PARTITION_BY (symbol_slug),
            COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE TRUE
        )
        """
    )
    connection.execute(
        f"""
        COPY (
            SELECT
                ts,
                symbol,
                funding_rate,
                funding_interval_hours,
                mark_price,
                lower(replace(replace(symbol, '/', '_'), ':', '_')) AS symbol_slug
            FROM read_parquet(
                '{path_sql(FUNDING_GLOB)}',
                hive_partitioning = false,
                union_by_name = true
            )
            WHERE ts >= TIMESTAMPTZ '2020-01-01 00:00:00+00'
              AND ts < TIMESTAMPTZ '2026-07-01 00:00:00+00'
        ) TO '{path_sql(funding_root)}' (
            FORMAT PARQUET,
            PARTITION_BY (symbol_slug),
            COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE TRUE
        )
        """
    )
    return market_root, funding_root


def read_partition(directory: Path) -> pd.DataFrame:
    paths = sorted(directory.glob("*.parquet"))
    if not paths:
        return pd.DataFrame()
    frame = pd.concat((pd.read_parquet(path) for path in paths), ignore_index=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.sort_values("ts").drop_duplicates("ts", keep="last").reset_index(
        drop=True
    )


def hourly_grid(market: pd.DataFrame) -> pd.DataFrame:
    market = market.sort_values("ts").drop_duplicates("ts", keep="last")
    timestamps = pd.date_range(
        market["ts"].min(),
        market["ts"].max(),
        freq="1h",
        tz="UTC",
    )
    identity = {
        column: market[column].dropna().iloc[0]
        for column in ["exchange", "symbol", "market_type", "timeframe"]
    }
    result = market.set_index("ts").reindex(timestamps).rename_axis("ts").reset_index()
    result["bar_present"] = result["close"].notna()
    for column, value in identity.items():
        result[column] = value
    return result


def attach_funding(grid: pd.DataFrame, funding: pd.DataFrame) -> pd.DataFrame:
    result = grid.sort_values("ts").copy()
    if funding.empty:
        result["funding_rate"] = np.nan
        result["funding_age_hours"] = np.nan
        result["funding_event_rate"] = 0.0
        return result
    events = funding[["ts", "funding_rate"]].dropna().sort_values("ts")
    latest = pd.merge_asof(
        result[["ts"]],
        events.rename(columns={"ts": "funding_ts"}),
        left_on="ts",
        right_on="funding_ts",
        direction="backward",
    )
    result["funding_rate"] = latest["funding_rate"].to_numpy()
    result["funding_age_hours"] = (
        result["ts"] - latest["funding_ts"]
    ).dt.total_seconds() / 3600.0
    event_map = events.set_index("ts")["funding_rate"]
    result["funding_event_rate"] = result["ts"].map(event_map).fillna(0.0)
    return result


def add_point_in_time_state(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["age_hours"] = (
        result["ts"] - result.loc[result["bar_present"], "ts"].min()
    ).dt.total_seconds() / 3600.0
    result["coverage_30d"] = (
        result["bar_present"].astype("float64").rolling(24 * 30, min_periods=24 * 30).mean()
    )
    result["avg_daily_quote_volume_7d"] = (
        result["quote_volume"].rolling(24 * 7, min_periods=24 * 7).sum() / 7.0
    )
    return result


def add_labels(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    funding_cumulative = result["funding_event_rate"].fillna(0.0).cumsum()
    entry_open = result["open"].shift(-1)
    for horizon in HORIZONS:
        exit_open = result["open"].shift(-(horizon + 1))
        funding_sum = funding_cumulative.shift(-(horizon + 1)) - funding_cumulative.shift(-1)
        result[f"label_funding_sum_{horizon}h"] = funding_sum
        result[f"label_long_net_{horizon}h"] = (
            exit_open / entry_open.replace(0.0, np.nan)
            - 1.0
            - ROUND_TRIP_COST
            - funding_sum
        )
        result[f"label_short_net_{horizon}h"] = (
            entry_open / exit_open.replace(0.0, np.nan)
            - 1.0
            - ROUND_TRIP_COST
            + funding_sum
        )
        result[f"label_gross_return_{horizon}h"] = (
            exit_open / entry_open.replace(0.0, np.nan) - 1.0
        )
    return result


def compute_symbol_factors(
    market_directory: str,
    funding_root: str,
    output_root: str,
    overwrite: bool,
) -> dict[str, Any]:
    market_dir = Path(market_directory)
    slug = market_dir.name.removeprefix("symbol_slug=")
    output = Path(output_root) / f"{slug}.parquet"
    if output.exists() and not overwrite:
        return {"slug": slug, "status": "existing", "path": str(output)}
    market = read_partition(market_dir)
    if market.empty:
        return {"slug": slug, "status": "empty"}
    funding = read_partition(Path(funding_root) / f"symbol_slug={slug}")
    grid = attach_funding(hourly_grid(market), funding)
    grid = add_point_in_time_state(grid)
    registry = multi_asset_1h_registry()
    factor_names = registry.names()
    factor_values = {
        name: registry.get(name).compute(grid).to_numpy()
        for name in factor_names
    }
    grid = grid.drop(
        columns=[name for name in factor_names if name in grid.columns],
        errors="ignore",
    )
    grid = pd.concat(
        [grid, pd.DataFrame(factor_values, index=grid.index)],
        axis=1,
    )
    grid = add_labels(grid)
    output_frame = grid.loc[grid["bar_present"]].drop(columns="bar_present").copy()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".parquet.tmp")
    output_frame.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(output)
    return {
        "slug": slug,
        "symbol": str(output_frame["symbol"].iloc[0]),
        "status": "written",
        "rows": len(output_frame),
        "start": output_frame["ts"].min().isoformat(),
        "end": output_frame["ts"].max().isoformat(),
        "factor_count": len(factor_names),
        "path": str(output),
    }


def rank_expression(column: str) -> str:
    return f"""
        CASE WHEN {column} IS NULL THEN NULL ELSE
            (rank() OVER (PARTITION BY ts ORDER BY {column} NULLS LAST) - 1)::DOUBLE
            / nullif(count({column}) OVER (PARTITION BY ts) - 1, 0)
        END AS cs_rank_{column}
    """


def panel_connection() -> duckdb.DuckDBPyConnection:
    DUCKDB_PANEL_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    connection.execute(
        f"SET temp_directory = '{path_sql(DUCKDB_PANEL_TEMP_ROOT)}'"
    )
    return connection


def build_cross_sectional_panel(*, overwrite: bool) -> None:
    if overwrite:
        shutil.rmtree(LIQUID_MONTHLY_ROOT, ignore_errors=True)
        shutil.rmtree(PANEL_ROOT, ignore_errors=True)
        shutil.rmtree(DUCKDB_PANEL_TEMP_ROOT, ignore_errors=True)
    if list(PANEL_ROOT.glob("**/*.parquet")):
        return
    factor_glob = BY_SYMBOL_ROOT / "*.parquet"
    if not list(LIQUID_MONTHLY_ROOT.glob("**/*.parquet")):
        LIQUID_MONTHLY_ROOT.mkdir(parents=True, exist_ok=True)
        connection = panel_connection()
        if not UNIVERSE_CATALOG_PATH.exists():
            raise RuntimeError(
                f"crypto universe catalog is missing: {UNIVERSE_CATALOG_PATH}"
            )
        connection.execute(
            f"""
            COPY (
                SELECT
                    factors.*,
                    strftime(ts AT TIME ZONE 'UTC', '%Y-%m') AS year_month
                FROM read_parquet(
                    '{path_sql(factor_glob)}',
                    hive_partitioning = false,
                    union_by_name = true
                ) AS factors
                INNER JOIN read_csv_auto(
                    '{path_sql(UNIVERSE_CATALOG_PATH)}',
                    header = true
                ) AS catalog
                USING (symbol)
                WHERE catalog.eligible
                  AND age_hours >= 24 * 30
                  AND coverage_30d >= 0.99
                  AND avg_daily_quote_volume_7d >= 5000000.0
            ) TO '{path_sql(LIQUID_MONTHLY_ROOT)}' (
                FORMAT PARQUET,
                PARTITION_BY (year_month),
                COMPRESSION ZSTD,
                OVERWRITE_OR_IGNORE TRUE
            )
            """
        )
        connection.close()

    month_directories = sorted(
        path
        for path in LIQUID_MONTHLY_ROOT.glob("year_month=*")
        if list(path.glob("*.parquet"))
    )
    if not month_directories:
        raise RuntimeError("liquid monthly staging produced no partitions")

    PANEL_ROOT.mkdir(parents=True, exist_ok=True)
    ranks = ",\n".join(rank_expression(column) for column in CROSS_SECTIONAL_FACTORS)
    relative_labels = ",\n".join(
        f"""
        label_long_net_{horizon}h
          - avg(label_long_net_{horizon}h) OVER (PARTITION BY ts)
          AS label_long_relative_{horizon}h,
        label_short_net_{horizon}h
          - avg(label_short_net_{horizon}h) OVER (PARTITION BY ts)
          AS label_short_relative_{horizon}h
        """
        for horizon in HORIZONS
    )
    for index, month_directory in enumerate(month_directories, start=1):
        month = month_directory.name.removeprefix("year_month=")
        output_directory = PANEL_ROOT / f"year_month={month}"
        output = output_directory / "part.parquet"
        if output.exists():
            continue
        output_directory.mkdir(parents=True, exist_ok=True)
        input_glob = month_directory / "*.parquet"
        temporary_output = output.with_suffix(".parquet.incomplete")
        temporary_output.unlink(missing_ok=True)
        connection = panel_connection()
        connection.execute(
            f"""
            COPY (
                WITH ranked AS (
                    SELECT
                        *,
                        row_number() OVER (
                            PARTITION BY ts
                            ORDER BY avg_daily_quote_volume_7d DESC, symbol
                        ) AS liquidity_rank,
                        {ranks},
                        avg(CASE WHEN ret_24 > 0 THEN 1.0 ELSE 0.0 END)
                            OVER (PARTITION BY ts)
                            AS market_breadth_ret24_positive,
                        avg(CASE WHEN ema_spread_24_96 > 0 THEN 1.0 ELSE 0.0 END)
                            OVER (PARTITION BY ts)
                            AS market_breadth_trend_positive,
                        median(realized_vol_24) OVER (PARTITION BY ts)
                            AS market_median_realized_vol_24,
                        max(CASE WHEN symbol = 'BTC/USDT:USDT' THEN ret_24 END)
                            OVER (PARTITION BY ts) AS btc_ret_24,
                        max(CASE WHEN symbol = 'BTC/USDT:USDT' THEN ret_168 END)
                            OVER (PARTITION BY ts) AS btc_ret_168,
                        {relative_labels}
                    FROM read_parquet(
                        '{path_sql(input_glob)}',
                        hive_partitioning = false,
                        union_by_name = true
                    )
                )
                SELECT
                    *,
                    ret_24 - btc_ret_24 AS relative_to_btc_24,
                    ret_168 - btc_ret_168 AS relative_to_btc_168,
                    avg_daily_quote_volume_7d >= 10000000.0
                        AND liquidity_rank <= 100 AS universe_main,
                    '{month}' AS year_month
                FROM ranked
                WHERE liquidity_rank <= 150
            ) TO '{path_sql(temporary_output)}' (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )
        connection.close()
        temporary_output.replace(output)
        if index % 6 == 0 or index == len(month_directories):
            print(
                f"cross_sectional_months {index}/{len(month_directories)}",
                flush=True,
            )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(
    quality_path: Path,
    quality: dict[str, Any],
    symbol_results: list[dict[str, Any]],
) -> None:
    registry = multi_asset_1h_registry()
    factor_glob = PANEL_ROOT / "**/*.parquet"
    connection = duckdb.connect()
    counts = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            count(*) FILTER (
                WHERE ts < TIMESTAMPTZ '{OOS_START.isoformat()}'
            ) AS pre_oos_rows,
            count(*) FILTER (
                WHERE ts >= TIMESTAMPTZ '{OOS_START.isoformat()}'
                  AND ts < TIMESTAMPTZ '{OOS_END.isoformat()}'
            ) AS sealed_oos_rows,
            count(*) FILTER (WHERE universe_main) AS main_universe_rows
        FROM read_parquet(
            '{path_sql(factor_glob)}',
            hive_partitioning = false,
            union_by_name = true
        )
        """
    ).fetchone()
    manifest = {
        "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "source_quality_report": str(quality_path),
        "source_quality_sha256": file_sha256(quality_path),
        "source_quality_status": quality["status"],
        "universe_catalog": str(UNIVERSE_CATALOG_PATH),
        "universe_catalog_sha256": file_sha256(UNIVERSE_CATALOG_PATH),
        "time_contract": {
            "feature_time": "K0 close using K0 and earlier information only",
            "entry_time": "K1 open",
            "label_horizons_hours": list(HORIZONS),
            "oos_start": OOS_START.isoformat(),
            "oos_end_exclusive": OOS_END.isoformat(),
            "oos_policy": "sealed; row count only, no label or performance statistics",
        },
        "cost_contract": {
            "fee_per_fill": 0.001,
            "adverse_slippage_bps_per_fill": 4.0,
            "round_trip_rate_before_funding": ROUND_TRIP_COST,
            "funding": "actual settlements strictly after K1 entry through exit",
        },
        "universe_contract": {
            "minimum_age_hours": 720,
            "coverage_30d": 0.99,
            "broad_min_avg_daily_quote_volume_7d": 5_000_000.0,
            "broad_top_n": 150,
            "main_min_avg_daily_quote_volume_7d": 10_000_000.0,
            "main_top_n": 100,
        },
        "base_factor_count": len(registry.names()),
        "base_factor_names": registry.names(),
        "base_factor_specs": registry.specs(),
        "cross_sectional_rank_factors": CROSS_SECTIONAL_FACTORS,
        "rows": int(counts[0]),
        "symbols": int(counts[1]),
        "pre_oos_rows": int(counts[2]),
        "sealed_oos_rows": int(counts[3]),
        "main_universe_rows": int(counts[4]),
        "symbol_jobs": symbol_results,
        "panel_root": str(PANEL_ROOT),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    quality_path = args.quality_report or latest_quality_report()
    quality = validate_quality_report(quality_path)
    market_root, funding_root = stage_inputs(overwrite=args.overwrite)
    market_directories = sorted(market_root.glob("symbol_slug=*"))
    if args.symbols:
        selected = {
            symbol.replace("/", "_").replace(":", "_").lower()
            for symbol in args.symbols
        }
        market_directories = [
            path
            for path in market_directories
            if path.name.removeprefix("symbol_slug=") in selected
        ]
    print(f"factor_jobs={len(market_directories)} workers={args.workers}")
    symbol_results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                compute_symbol_factors,
                str(directory),
                str(funding_root),
                str(BY_SYMBOL_ROOT),
                args.overwrite,
            ): directory
            for directory in market_directories
        }
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            symbol_results.append(result)
            if index % 25 == 0 or index == len(futures):
                print(f"factors {index}/{len(futures)}", flush=True)
    if args.symbols:
        print("symbol subset complete; cross-sectional panel not built")
        return
    build_cross_sectional_panel(overwrite=args.overwrite)
    write_manifest(quality_path, quality, symbol_results)
    print(f"panel -> {PANEL_ROOT}")
    print(f"manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
