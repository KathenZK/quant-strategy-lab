from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from strategy_lab.data.factors.multi_asset_tail_1h import (
    multi_asset_tail_1h_registry,
)
from strategy_lab.data.linear_contract_returns import long_net_return, short_net_return


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DATASET_ROOT = ARTIFACT_DIR / "multihorizon_factor_dataset"
STAGING_ROOT = DATASET_ROOT / "staging"
BY_SYMBOL_ROOT = DATASET_ROOT / "by_symbol"
LIQUID_MONTHLY_ROOT = DATASET_ROOT / "liquid_monthly"
PANEL_ROOT = DATASET_ROOT / "panel"
DUCKDB_TEMP_ROOT = DATASET_ROOT / "duckdb_temp"
MANIFEST_PATH = DATASET_ROOT / "factor_dataset_manifest.json"
QUALITY_MANIFEST_PATH = ARTIFACT_DIR / "data_quality_manifest_2026-07-18.json"
UNIVERSE_CATALOG_PATH = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/artifacts/"
    "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
)
OLD_SCRIPT_DIR = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/scripts"
)
if str(OLD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(OLD_SCRIPT_DIR))

import build_cross_sectional_factor_panel as legacy_panel  # noqa: E402


HORIZONS = (4, 8, 12, 24, 48)
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
REUSED_HOLDOUT_END = pd.Timestamp("2026-07-01T00:00:00Z")
PROSPECTIVE_OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
PROSPECTIVE_OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
ROUND_TRIP_COST = 2.0 * (0.001 + 4.0 / 10_000.0)
CROSS_SECTIONAL_FACTORS = list(
    dict.fromkeys(
        [
            *legacy_panel.CROSS_SECTIONAL_FACTORS,
            "ret_8",
            "ret_48",
            "upside_vol_24",
            "upside_vol_168",
            "return_kurtosis_24",
            "return_kurtosis_168",
            "extreme_return_up_24",
            "extreme_return_up_168",
            "extreme_return_down_24",
            "extreme_return_down_168",
            "jump_count_up_3pct_24",
            "jump_count_up_3pct_168",
            "jump_count_down_3pct_24",
            "jump_count_down_3pct_168",
            "range_max_24",
            "range_max_168",
            "taker_imbalance_std_24",
            "taker_imbalance_std_168",
            "funding_event_sum_24",
            "funding_event_sum_168",
            "mark_premium_max_24",
            "mark_premium_max_168",
            "mark_premium_min_24",
            "mark_premium_min_168",
        ]
    )
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build leakage-safe multi-horizon long/short/tail factor panel."
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--symbols", nargs="*")
    return parser.parse_args()


def path_sql(path: Path) -> str:
    return str(path).replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_quality_manifest() -> dict[str, Any]:
    quality = json.loads(QUALITY_MANIFEST_PATH.read_text(encoding="utf-8"))
    if quality.get("status") != "PASS" or quality.get("blockers"):
        raise RuntimeError("data quality manifest is not PASS")
    if quality.get("oos_label_or_performance_read"):
        raise RuntimeError("data quality process accessed protected OOS outcomes")
    return quality


def configure_staging() -> None:
    legacy_panel.STAGING_ROOT = STAGING_ROOT


def all_future_present(present: pd.Series, horizon: int) -> pd.Series:
    shifted = [present.shift(-step).fillna(False) for step in range(1, horizon + 2)]
    return pd.concat(shifted, axis=1).all(axis=1)


def future_extreme(
    values: pd.Series, horizon: int, *, maximum: bool
) -> pd.Series:
    shifted = [values.shift(-step) for step in range(1, horizon + 1)]
    future = pd.concat(shifted, axis=1)
    return future.max(axis=1) if maximum else future.min(axis=1)


def add_multihorizon_labels(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    funding_cumulative = result["funding_event_rate"].fillna(0.0).cumsum()
    entry_open = result["open"].shift(-1).replace(0.0, np.nan)
    for horizon in HORIZONS:
        valid = all_future_present(result["bar_present"], horizon)
        exit_open = result["open"].shift(-(horizon + 1))
        funding_sum = (
            funding_cumulative.shift(-(horizon + 1))
            - funding_cumulative.shift(-1)
        )
        gross = exit_open / entry_open - 1.0
        path_high = future_extreme(result["high"], horizon, maximum=True)
        path_low = future_extreme(result["low"], horizon, maximum=False)
        upside_excursion = path_high / entry_open - 1.0
        downside_excursion = path_low / entry_open - 1.0
        result[f"label_path_valid_{horizon}h"] = valid
        result[f"label_funding_sum_{horizon}h"] = funding_sum.where(valid)
        result[f"label_gross_return_{horizon}h"] = gross.where(valid)
        result[f"label_long_net_{horizon}h"] = long_net_return(
            entry_open,
            exit_open,
            round_trip_cost=ROUND_TRIP_COST,
            funding_sum=funding_sum,
        ).where(valid)
        result[f"label_short_net_{horizon}h"] = short_net_return(
            entry_open,
            exit_open,
            round_trip_cost=ROUND_TRIP_COST,
            funding_sum=funding_sum,
        ).where(valid)
        result[f"label_long_mae_{horizon}h"] = downside_excursion.clip(
            upper=0.0
        ).where(valid)
        result[f"label_long_mfe_{horizon}h"] = upside_excursion.clip(
            lower=0.0
        ).where(valid)
        result[f"label_short_mae_{horizon}h"] = (-upside_excursion).clip(
            upper=0.0
        ).where(valid)
        result[f"label_short_mfe_{horizon}h"] = (-downside_excursion).clip(
            lower=0.0
        ).where(valid)
        result[f"label_short_squeeze_10pct_{horizon}h"] = (
            upside_excursion.ge(0.10).astype("float64").where(valid)
        )
        result[f"label_short_squeeze_20pct_{horizon}h"] = (
            upside_excursion.ge(0.20).astype("float64").where(valid)
        )
        result[f"label_long_crash_10pct_{horizon}h"] = (
            downside_excursion.le(-0.10).astype("float64").where(valid)
        )
        result[f"label_long_crash_20pct_{horizon}h"] = (
            downside_excursion.le(-0.20).astype("float64").where(valid)
        )
    return result


def compute_symbol_job(
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
    market = legacy_panel.read_partition(market_dir)
    if market.empty:
        return {"slug": slug, "status": "empty"}
    funding = legacy_panel.read_partition(
        Path(funding_root) / f"symbol_slug={slug}"
    )
    grid = legacy_panel.attach_funding(legacy_panel.hourly_grid(market), funding)
    grid = legacy_panel.add_point_in_time_state(grid)
    registry = multi_asset_tail_1h_registry()
    factor_names = registry.names()
    factor_values = {
        name: registry.get(name).compute(grid).to_numpy() for name in factor_names
    }
    grid = grid.drop(
        columns=[name for name in factor_names if name in grid.columns],
        errors="ignore",
    )
    grid = pd.concat([grid, pd.DataFrame(factor_values, index=grid.index)], axis=1)
    grid = add_multihorizon_labels(grid)
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
    DUCKDB_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    connection.execute(f"SET temp_directory = '{path_sql(DUCKDB_TEMP_ROOT)}'")
    return connection


def build_cross_sectional_panel(*, overwrite: bool) -> None:
    if overwrite:
        shutil.rmtree(LIQUID_MONTHLY_ROOT, ignore_errors=True)
        shutil.rmtree(PANEL_ROOT, ignore_errors=True)
        shutil.rmtree(DUCKDB_TEMP_ROOT, ignore_errors=True)
    if list(PANEL_ROOT.glob("**/*.parquet")):
        return
    factor_glob = BY_SYMBOL_ROOT / "*.parquet"
    if not list(LIQUID_MONTHLY_ROOT.glob("**/*.parquet")):
        LIQUID_MONTHLY_ROOT.mkdir(parents=True, exist_ok=True)
        connection = panel_connection()
        connection.execute(
            f"""
            COPY (
                SELECT
                    factors.*,
                    strftime(ts AT TIME ZONE 'UTC', '%Y-%m') AS year_month
                FROM read_parquet(
                    '{path_sql(factor_glob)}',
                    hive_partitioning=false,
                    union_by_name=true
                ) AS factors
                INNER JOIN read_csv_auto(
                    '{path_sql(UNIVERSE_CATALOG_PATH)}', header=true
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
    PANEL_ROOT.mkdir(parents=True, exist_ok=True)
    for index, month_directory in enumerate(month_directories, start=1):
        month = month_directory.name.removeprefix("year_month=")
        output = PANEL_ROOT / f"year_month={month}" / "part.parquet"
        if output.exists():
            continue
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".parquet.incomplete")
        temporary.unlink(missing_ok=True)
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
                        stddev_pop(ret_24) OVER (PARTITION BY ts)
                            AS market_dispersion_ret24,
                        stddev_pop(realized_vol_24) OVER (PARTITION BY ts)
                            AS market_dispersion_vol24,
                        avg(CASE WHEN funding_rate > 0 THEN 1.0 ELSE 0.0 END)
                            OVER (PARTITION BY ts)
                            AS market_positive_funding_share,
                        max(CASE WHEN symbol = 'BTC/USDT:USDT' THEN ret_24 END)
                            OVER (PARTITION BY ts) AS btc_ret_24,
                        max(CASE WHEN symbol = 'BTC/USDT:USDT' THEN ret_168 END)
                            OVER (PARTITION BY ts) AS btc_ret_168,
                        {relative_labels}
                    FROM read_parquet(
                        '{path_sql(month_directory / '*.parquet')}',
                        hive_partitioning=false,
                        union_by_name=true
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
            ) TO '{path_sql(temporary)}' (
                FORMAT PARQUET,
                COMPRESSION ZSTD
            )
            """
        )
        connection.close()
        temporary.replace(output)
        if index % 6 == 0 or index == len(month_directories):
            print(
                f"cross_sectional_months {index}/{len(month_directories)}",
                flush=True,
            )


def write_manifest(
    quality: dict[str, Any], symbol_results: list[dict[str, Any]]
) -> None:
    registry = multi_asset_tail_1h_registry()
    connection = duckdb.connect()
    counts = connection.execute(
        f"""
        SELECT
            count(*) AS rows,
            count(DISTINCT symbol) AS symbols,
            count(*) FILTER (
                WHERE ts < TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}'
            ) AS development_rows,
            count(*) FILTER (
                WHERE ts >= TIMESTAMPTZ '{DEVELOPMENT_END.isoformat()}'
                  AND ts < TIMESTAMPTZ '{REUSED_HOLDOUT_END.isoformat()}'
            ) AS reused_holdout_rows,
            count(*) FILTER (WHERE universe_main) AS main_universe_rows
        FROM read_parquet(
            '{path_sql(PANEL_ROOT / '**/*.parquet')}',
            hive_partitioning=false,
            union_by_name=true
        )
        """
    ).fetchone()
    connection.close()
    feature_count = (
        len(registry.names())
        + len(CROSS_SECTIONAL_FACTORS)
        + 11
    )
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS",
        "source_quality_manifest": str(QUALITY_MANIFEST_PATH.relative_to(ROOT)),
        "source_quality_sha256": sha256(QUALITY_MANIFEST_PATH),
        "source_quality_status": quality["status"],
        "universe_catalog": str(UNIVERSE_CATALOG_PATH.relative_to(ROOT)),
        "universe_catalog_sha256": sha256(UNIVERSE_CATALOG_PATH),
        "time_contract": {
            "feature_time": "K0 close using K0 and earlier information only",
            "entry_time": "K1 open",
            "label_horizons_hours": list(HORIZONS),
            "development_end_exclusive": DEVELOPMENT_END.isoformat(),
            "reused_holdout_end_exclusive": REUSED_HOLDOUT_END.isoformat(),
            "prospective_oos_start": PROSPECTIVE_OOS_START.isoformat(),
            "prospective_oos_end_exclusive": PROSPECTIVE_OOS_END.isoformat(),
            "prospective_oos_outcomes_read": False,
        },
        "cost_contract": {
            "fee_per_fill": 0.001,
            "adverse_slippage_bps_per_fill": 4.0,
            "round_trip_rate_before_funding": ROUND_TRIP_COST,
            "funding": "actual settlements strictly after K1 entry through exit",
        },
        "label_contract": {
            "long": "exit/entry-1-cost-funding",
            "short": "1-exit/entry-cost+funding",
            "tail": "path MAE/MFE plus 10%/20% squeeze and crash events",
            "nontradable_policy": (
                "label_path_valid=false when any entry-through-exit bar is absent"
            ),
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
        "cross_sectional_rank_factor_count": len(CROSS_SECTIONAL_FACTORS),
        "cross_sectional_rank_factors": CROSS_SECTIONAL_FACTORS,
        "estimated_model_feature_count": feature_count,
        "rows": int(counts[0]),
        "symbols": int(counts[1]),
        "development_rows": int(counts[2]),
        "reused_holdout_rows": int(counts[3]),
        "main_universe_rows": int(counts[4]),
        "symbol_jobs": symbol_results,
        "panel_root": str(PANEL_ROOT.relative_to(ROOT)),
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    quality = validate_quality_manifest()
    configure_staging()
    market_root, funding_root = legacy_panel.stage_inputs(overwrite=args.overwrite)
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
    symbol_results = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                compute_symbol_job,
                str(directory),
                str(funding_root),
                str(BY_SYMBOL_ROOT),
                args.overwrite,
            )
            for directory in market_directories
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            symbol_results.append(future.result())
            if index % 25 == 0 or index == len(futures):
                print(f"factors {index}/{len(futures)}", flush=True)
    if args.symbols:
        print("symbol subset complete; cross-sectional panel not built")
        return
    build_cross_sectional_panel(overwrite=args.overwrite)
    write_manifest(quality, symbol_results)
    print(f"panel -> {PANEL_ROOT}")
    print(f"manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
