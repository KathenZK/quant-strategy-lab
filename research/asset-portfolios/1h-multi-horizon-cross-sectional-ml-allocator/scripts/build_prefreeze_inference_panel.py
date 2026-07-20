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
import pandas as pd

from strategy_lab.data.factors.multi_asset_tail_1h import multi_asset_tail_1h_registry


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FREEZE_DIR = ARTIFACT_DIR / "freeze"
TAIL_MANIFEST = FREEZE_DIR / "freeze_gap_data_manifest_2026-07-18.json"
EXCHANGE_INFO = FREEZE_DIR / "exchange_info_prefreeze_2026-07-18.json"
BASE_STAGING = ARTIFACT_DIR / "multihorizon_factor_dataset/staging"
WORK_ROOT = FREEZE_DIR / "prefreeze_inference_work"
TAIL_STAGING = WORK_ROOT / "tail_staging"
BY_SYMBOL = WORK_ROOT / "by_symbol"
PANEL_PATH = FREEZE_DIR / "prefreeze_inference_panel_2026-07-18.parquet"
MANIFEST_PATH = FREEZE_DIR / "prefreeze_inference_panel_manifest_2026-07-18.json"
MATRIX_MANIFEST = ARTIFACT_DIR / "development_model_matrix_manifest.json"
UNIVERSE_CATALOG = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/artifacts/"
    "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
)
OLD_SCRIPT_DIR = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/scripts"
)
if str(OLD_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(OLD_SCRIPT_DIR))

import build_cross_sectional_factor_panel as legacy  # noqa: E402
import build_multihorizon_factor_panel as research_panel  # noqa: E402


START = pd.Timestamp("2026-07-01T00:00:00Z")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a feature-only prefreeze inference panel without labels."
    )
    parser.add_argument("--workers", type=int, default=8)
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


def current_slugs(exchange_info_path: Path = EXCHANGE_INFO) -> set[str]:
    info = json.loads(exchange_info_path.read_text(encoding="utf-8"))
    symbols = {
        str(row["symbol"])
        for row in info["symbols"]
        if row.get("contractType") == "PERPETUAL"
        and row.get("quoteAsset") == "USDT"
        and row.get("status") == "TRADING"
    }
    return {
        (symbol.removesuffix("USDT") + "_usdt_usdt").lower()
        for symbol in symbols
    }


def stage_tail(
    *, end: pd.Timestamp, overwrite: bool, staging_root: Path = TAIL_STAGING
) -> tuple[Path, Path]:
    market_root = staging_root / "market"
    funding_root = staging_root / "funding"
    if overwrite:
        shutil.rmtree(staging_root, ignore_errors=True)
    if list(market_root.glob("symbol_slug=*/*.parquet")) and list(
        funding_root.glob("symbol_slug=*/*.parquet")
    ):
        return market_root, funding_root
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    market_root.mkdir(parents=True, exist_ok=True)
    funding_root.mkdir(parents=True, exist_ok=True)
    connection.execute(
        f"""
        COPY (
            WITH ohlcv AS (
                SELECT * EXCLUDE (_rn) FROM (
                    SELECT *, row_number() OVER (
                        PARTITION BY ts, symbol
                        ORDER BY CASE
                            WHEN source LIKE '%prospective_oos%' THEN 0
                            WHEN source LIKE '%freeze_gap%' THEN 1
                            ELSE 2
                        END
                    ) AS _rn
                    FROM read_parquet(
                        '{sql_path(OHLCV_GLOB)}',
                        hive_partitioning=false,
                        union_by_name=true
                    )
                    WHERE ts >= TIMESTAMPTZ '{START.isoformat()}'
                      AND ts < TIMESTAMPTZ '{end.isoformat()}'
                ) WHERE _rn = 1
            ), mark AS (
                SELECT ts, symbol, close AS mark_price FROM (
                    SELECT *, row_number() OVER (
                        PARTITION BY ts, symbol
                        ORDER BY CASE
                            WHEN source LIKE '%prospective_oos%' THEN 0
                            WHEN source LIKE '%freeze_gap%' THEN 1
                            ELSE 2
                        END
                    ) AS _rn
                    FROM read_parquet(
                        '{sql_path(MARK_GLOB)}',
                        hive_partitioning=false,
                        union_by_name=true
                    )
                    WHERE ts >= TIMESTAMPTZ '{START.isoformat()}'
                      AND ts < TIMESTAMPTZ '{end.isoformat()}'
                ) WHERE _rn = 1
            )
            SELECT
                o.ts, o.exchange, o.symbol, o.market_type, o.timeframe,
                o.open, o.high, o.low, o.close, o.volume, o.quote_volume,
                o.trade_count, o.taker_buy_volume, o.taker_buy_quote_volume,
                o.vwap, m.mark_price,
                lower(replace(replace(o.symbol, '/', '_'), ':', '_')) AS symbol_slug
            FROM ohlcv AS o
            LEFT JOIN mark AS m USING (ts, symbol)
        ) TO '{sql_path(market_root)}' (
            FORMAT PARQUET, PARTITION_BY (symbol_slug), COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE TRUE
        )
        """
    )
    connection.execute(
        f"""
        COPY (
            SELECT
                ts, symbol, funding_rate, funding_interval_hours, mark_price,
                lower(replace(replace(symbol, '/', '_'), ':', '_')) AS symbol_slug
            FROM (
                SELECT *, row_number() OVER (
                    PARTITION BY ts, symbol
                    ORDER BY CASE
                        WHEN source LIKE '%prospective_oos%' THEN 0
                        WHEN source LIKE '%freeze_gap%' THEN 1
                        ELSE 2
                    END
                ) AS _rn
                FROM read_parquet(
                    '{sql_path(FUNDING_GLOB)}',
                    hive_partitioning=false,
                    union_by_name=true
                )
                WHERE ts >= TIMESTAMPTZ '{START.isoformat()}'
                  AND ts < TIMESTAMPTZ '{end.isoformat()}'
            ) WHERE _rn = 1
        ) TO '{sql_path(funding_root)}' (
            FORMAT PARQUET, PARTITION_BY (symbol_slug), COMPRESSION ZSTD,
            OVERWRITE_OR_IGNORE TRUE
        )
        """
    )
    connection.close()
    return market_root, funding_root


def read_optional(directory: Path) -> pd.DataFrame:
    if not directory.exists():
        return pd.DataFrame()
    return legacy.read_partition(directory)


def compute_one(
    slug: str,
    tail_market_root: str,
    tail_funding_root: str,
    end_text: str,
    output_root: str | None = None,
) -> dict[str, Any]:
    tail_market = read_optional(Path(tail_market_root) / f"symbol_slug={slug}")
    base_market = read_optional(BASE_STAGING / "market" / f"symbol_slug={slug}")
    market_parts = [frame for frame in (base_market, tail_market) if not frame.empty]
    if not market_parts:
        return {"slug": slug, "status": "no_market"}
    market = (
        pd.concat(market_parts, ignore_index=True)
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
    )
    tail_funding = read_optional(Path(tail_funding_root) / f"symbol_slug={slug}")
    base_funding = read_optional(BASE_STAGING / "funding" / f"symbol_slug={slug}")
    funding_parts = [frame for frame in (base_funding, tail_funding) if not frame.empty]
    funding = (
        pd.concat(funding_parts, ignore_index=True)
        .sort_values("ts")
        .drop_duplicates("ts", keep="last")
        if funding_parts
        else pd.DataFrame()
    )
    grid = legacy.attach_funding(legacy.hourly_grid(market), funding)
    grid = legacy.add_point_in_time_state(grid)
    registry = multi_asset_tail_1h_registry()
    factor_values = {
        name: registry.get(name).compute(grid).to_numpy()
        for name in registry.names()
    }
    grid = grid.drop(columns=[name for name in registry.names() if name in grid.columns], errors="ignore")
    grid = pd.concat([grid, pd.DataFrame(factor_values, index=grid.index)], axis=1)
    end = pd.Timestamp(end_text)
    output = grid.loc[
        grid["bar_present"] & grid["ts"].ge(START) & grid["ts"].lt(end)
    ].drop(columns="bar_present")
    if output.empty:
        return {"slug": slug, "status": "no_prefreeze_rows"}
    path = Path(output_root) / f"{slug}.parquet" if output_root else BY_SYMBOL / f"{slug}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(path, index=False, compression="zstd")
    return {
        "slug": slug,
        "status": "written",
        "rows": len(output),
        "first_ts": output["ts"].min().isoformat(),
        "last_ts": output["ts"].max().isoformat(),
    }


def build_panel(
    end: pd.Timestamp,
    *,
    by_symbol_root: Path = BY_SYMBOL,
    panel_path: Path = PANEL_PATH,
    universe_catalog: Path = UNIVERSE_CATALOG,
) -> None:
    ranks = ",\n".join(
        research_panel.rank_expression(name)
        for name in research_panel.CROSS_SECTIONAL_FACTORS
    )
    connection = duckdb.connect()
    connection.execute("SET preserve_insertion_order = false")
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    temporary = panel_path.with_suffix(".parquet.tmp")
    temporary.unlink(missing_ok=True)
    connection.execute(
        f"""
        COPY (
            WITH ranked AS (
                SELECT
                    factors.*,
                    row_number() OVER (
                        PARTITION BY ts
                        ORDER BY avg_daily_quote_volume_7d DESC, symbol
                    ) AS liquidity_rank,
                    {ranks},
                    avg(CASE WHEN ret_24 > 0 THEN 1.0 ELSE 0.0 END)
                        OVER (PARTITION BY ts) AS market_breadth_ret24_positive,
                    avg(CASE WHEN ema_spread_24_96 > 0 THEN 1.0 ELSE 0.0 END)
                        OVER (PARTITION BY ts) AS market_breadth_trend_positive,
                    median(realized_vol_24) OVER (PARTITION BY ts)
                        AS market_median_realized_vol_24,
                    stddev_pop(ret_24) OVER (PARTITION BY ts)
                        AS market_dispersion_ret24,
                    stddev_pop(realized_vol_24) OVER (PARTITION BY ts)
                        AS market_dispersion_vol24,
                    avg(CASE WHEN funding_rate > 0 THEN 1.0 ELSE 0.0 END)
                        OVER (PARTITION BY ts) AS market_positive_funding_share,
                    max(CASE WHEN symbol='BTC/USDT:USDT' THEN ret_24 END)
                        OVER (PARTITION BY ts) AS btc_ret_24,
                    max(CASE WHEN symbol='BTC/USDT:USDT' THEN ret_168 END)
                        OVER (PARTITION BY ts) AS btc_ret_168
                FROM read_parquet(
                    '{sql_path(by_symbol_root / '*.parquet')}',
                    hive_partitioning=false, union_by_name=true
                ) AS factors
                INNER JOIN read_csv_auto(
                    '{sql_path(universe_catalog)}', header=true
                ) AS catalog USING (symbol)
                WHERE catalog.eligible
                  AND age_hours >= 24 * 30
                  AND coverage_30d >= 0.99
                  AND avg_daily_quote_volume_7d >= 5000000.0
                  AND ts < TIMESTAMPTZ '{end.isoformat()}'
            )
            SELECT
                * EXCLUDE (btc_ret_24, btc_ret_168),
                ret_24 - btc_ret_24 AS relative_to_btc_24,
                ret_168 - btc_ret_168 AS relative_to_btc_168,
                avg_daily_quote_volume_7d >= 10000000.0
                    AND liquidity_rank <= 100 AS universe_main
            FROM ranked
            WHERE liquidity_rank <= 150
            ORDER BY ts, symbol
        ) TO '{sql_path(temporary)}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    connection.close()
    temporary.replace(panel_path)


def main() -> None:
    args = parse_args()
    tail_manifest = json.loads(TAIL_MANIFEST.read_text(encoding="utf-8"))
    if tail_manifest.get("status") != "PASS" or tail_manifest.get("blockers"):
        raise RuntimeError("freeze-gap data manifest is not PASS")
    if tail_manifest.get("prospective_oos_outcomes_read"):
        raise RuntimeError("tail manifest reports protected outcome access")
    end = pd.Timestamp(tail_manifest["closed_end_exclusive"])
    if end > PROSPECTIVE_START:
        raise RuntimeError("prefreeze panel crossed prospective boundary")
    if args.overwrite:
        shutil.rmtree(WORK_ROOT, ignore_errors=True)
        PANEL_PATH.unlink(missing_ok=True)
    tail_market, tail_funding = stage_tail(end=end, overwrite=args.overwrite)
    slugs = sorted(current_slugs())
    results: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                compute_one, slug, str(tail_market), str(tail_funding), end.isoformat()
            )
            for slug in slugs
        ]
        for index, future in enumerate(as_completed(futures), start=1):
            results.append(future.result())
            if index % 50 == 0 or index == len(futures):
                print(f"inference_factors {index}/{len(futures)}", flush=True)
    written = [row for row in results if row["status"] == "written"]
    if len(written) < 400:
        raise RuntimeError(f"too few symbols produced inference factors: {len(written)}")
    build_panel(end)
    frame = pd.read_parquet(PANEL_PATH)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    label_columns = [name for name in frame.columns if name.startswith("label_")]
    matrix = json.loads(MATRIX_MANIFEST.read_text(encoding="utf-8"))
    required_features = set(matrix["feature_sets"]["stable_full"])
    missing_features = sorted(required_features - set(frame.columns))
    blockers: list[str] = []
    if label_columns:
        blockers.append("label_columns_present")
    if missing_features:
        blockers.append("frozen_features_missing")
    if frame["ts"].max() >= PROSPECTIVE_START:
        blockers.append("prospective_rows_present")
    if frame.duplicated(["ts", "symbol"]).any():
        blockers.append("duplicate_keys")
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "role": "feature-only prefreeze inference warmup",
        "source_tail_manifest": str(TAIL_MANIFEST.relative_to(ROOT)),
        "source_tail_manifest_sha256": sha256(TAIL_MANIFEST),
        "start": START.isoformat(),
        "end_exclusive": end.isoformat(),
        "rows": len(frame),
        "symbols": int(frame["symbol"].nunique()),
        "main_universe_rows": int(frame["universe_main"].sum()),
        "first_ts": frame["ts"].min().isoformat(),
        "last_ts": frame["ts"].max().isoformat(),
        "label_columns": label_columns,
        "missing_frozen_features": missing_features,
        "freeze_gap_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "panel_path": str(PANEL_PATH.relative_to(ROOT)),
        "panel_sha256": sha256(PANEL_PATH),
        "symbol_job_status_counts": pd.Series(
            [row["status"] for row in results]
        ).value_counts().to_dict(),
        "blockers": blockers,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"prefreeze inference panel blocked: {blockers}")


if __name__ == "__main__":
    main()
