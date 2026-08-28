from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from research_binance_1d_ma7_regime_continuation import (
    infer_mean,
    rolling_percentile_current,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation"
CONFIG_PATH = FAMILY_DIR / "configs/binance-1d-ma7-regime-continuation-p3.json"
EXPECTED_CONFIG_SHA256 = (
    "690dcfef2e1dff6f73ada050f253ca6dc0803002fae379fa212978229a587b62"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CACHE_DIR = ROOT / "data/cache/binance-1d-ma7-rc-p3"
DAILY_PANEL_PATH = CACHE_DIR / "binance_1d_ma7_rc_p3_daily_panel.parquet"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/binance-1d-ma7-regime-continuation-p3-confirmatory-2026-08-25.md"
)
INPUT_GLOB = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
    / "**/*.parquet"
)
SOURCES = ("binance_vision_kline_monthly", "binance_futures_kline_api")
CUTOFF = pd.Timestamp("2026-08-25T00:00:00Z")
DEVELOPMENT_CUTOFF = pd.Timestamp("2026-07-01T00:00:00Z")
HORIZONS = (1, 3, 5, 10, 20, 40)
PRIMARY_HORIZONS = (10, 20)
MA_PERIODS = (5, 7, 10)
ROUND_TRIP_COST = 0.0028
SIDE_COST = ROUND_TRIP_COST / 2.0
MAX_POSITIONS = 5
POSITION_ALLOCATION = 0.20
US_STOCK_LIKE_BASES = {
    "AAPL",
    "AMZN",
    "COIN",
    "CRCL",
    "GOOGL",
    "HOOD",
    "META",
    "MSFT",
    "MSTR",
    "NVDA",
    "PLTR",
    "TSLA",
}

FEATURE_COLUMNS = [
    "direction_sign",
    "aligned_ma7_slope",
    "aligned_ma30_slope",
    "aligned_return_5",
    "aligned_return_10",
    "aligned_return_20",
    "er20",
    "rv20",
    "atr_change_5d_pre",
    "atr_change_10d_pre",
    "atr_change_20d_pre",
    "atr_path_percentile_60",
    "atr_down_share_10_pre",
    "atr_up_share_10_pre",
    "breakout_range_ratio",
    "aligned_distance_ma7_atr",
    "volume_ratio_5_20",
    "aligned_breadth_trend_balance_loo",
    "breadth_atr_expansion_share_loo",
    "aligned_breadth_median_return_10_loo",
    "breadth_return_10_dispersion_loo",
]

FIXED_FILTERS = (
    "ALL_MA7",
    "SLOPE_ALIGNED",
    "P2_LOCAL_FIXED",
    "P2_LOCAL_BREADTH_FIXED",
)

FOLDS = (
    ("Y2022", pd.Timestamp("2022-01-01T00:00:00Z"), pd.Timestamp("2023-01-01T00:00:00Z")),
    ("Y2023", pd.Timestamp("2023-01-01T00:00:00Z"), pd.Timestamp("2024-01-01T00:00:00Z")),
    ("Y2024", pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2025-01-01T00:00:00Z")),
    ("Y2025", pd.Timestamp("2025-01-01T00:00:00Z"), pd.Timestamp("2026-01-01T00:00:00Z")),
    ("H1_2026", pd.Timestamp("2026-01-01T00:00:00Z"), DEVELOPMENT_CUTOFF),
    ("CONFIRM_2026_07_08", DEVELOPMENT_CUTOFF, CUTOFF),
)

OUTPUTS = {
    "audit": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_data_quality_audit.json",
    "events": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_events.parquet",
    "fixed_stats": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_fixed_rule_stats.csv",
    "fixed_frequency": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_fixed_rule_frequency.csv",
    "fixed_robustness": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_fixed_rule_robustness.csv",
    "ml_predictions": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_ml_predictions.parquet",
    "ml_metrics": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_ml_metrics.csv",
    "ml_quintiles": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_ml_score_quintiles.csv",
    "ml_importance": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_ml_feature_importance.csv",
    "account_metrics": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_account_metrics.csv",
    "account_equity": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_account_equity.csv",
    "account_trades": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_account_trades.parquet",
    "summary": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_summary.json",
    "manifest": ARTIFACT_DIR / "binance_1d_ma7_rc_p3_artifact_manifest.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen BIN-1D-MA7-RC-P3 fixed-rule and small-ML confirmation."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required acknowledgement that the locked confirmation outcomes will be read.",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--reuse-daily-panel",
        action="store_true",
        help="Reuse the audited P3 daily cache when reproducing model outputs.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_frozen_config() -> dict[str, Any]:
    actual = sha256_file(CONFIG_PATH)
    if actual != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(
            f"frozen config hash mismatch: {actual} != {EXPECTED_CONFIG_SHA256}"
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != "BIN-1D-MA7-RC-P3":
        raise RuntimeError("unexpected P3 study id")
    return config


def prepare_outputs(force: bool) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        raise FileExistsError(
            "P3 outputs already exist; pass --force: "
            + ", ".join(str(path) for path in existing)
        )


def input_audit(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    source_query = """
        SELECT
            source,
            count(*) AS row_count,
            count(DISTINCT symbol) AS symbol_count,
            min(ts) AS start_ts,
            max(ts) AS end_ts,
            count(*) - count(DISTINCT (symbol, ts)) AS duplicate_rows,
            count(*) FILTER (WHERE NOT is_closed) AS open_bar_rows,
            count(*) FILTER (
                WHERE symbol IS NULL OR ts IS NULL OR open IS NULL OR high IS NULL
                   OR low IS NULL OR close IS NULL OR volume IS NULL
                   OR quote_volume IS NULL OR trade_count IS NULL OR is_closed IS NULL
            ) AS critical_null_rows,
            count(*) FILTER (
                WHERE open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                   OR volume < 0 OR quote_volume < 0 OR trade_count < 0
                   OR high < greatest(open, close, low)
                   OR low > least(open, close, high)
            ) AS invalid_market_rows
        FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
        WHERE source IN (?, ?) AND ts < ?
        GROUP BY source
        ORDER BY source
    """
    by_source = connection.execute(
        source_query, [str(INPUT_GLOB), *SOURCES, CUTOFF.to_pydatetime()]
    ).fetch_df()
    union_query = """
        WITH selected AS (
            SELECT *, row_number() OVER (
                PARTITION BY symbol, ts
                ORDER BY CASE source
                    WHEN 'binance_vision_kline_monthly' THEN 0
                    WHEN 'binance_futures_kline_api' THEN 1
                    ELSE 2
                END
            ) AS source_rank
            FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
            WHERE source IN (?, ?) AND ts < ?
        )
        SELECT
            count(*) AS raw_union_rows,
            count(*) FILTER (WHERE source_rank = 1) AS selected_rows,
            count(DISTINCT symbol) AS symbol_count,
            min(ts) AS start_ts,
            max(ts) AS end_ts,
            count(*) - count(*) FILTER (WHERE source_rank = 1) AS controlled_overlap_rows
        FROM selected
    """
    union = connection.execute(
        union_query, [str(INPUT_GLOB), *SOURCES, CUTOFF.to_pydatetime()]
    ).fetch_df().iloc[0]
    records = []
    for row in by_source.to_dict("records"):
        records.append(
            {
                key: (
                    pd.Timestamp(value).isoformat()
                    if key.endswith("_ts")
                    else int(value)
                    if key.endswith("_count") or key.endswith("_rows")
                    else value
                )
                for key, value in row.items()
            }
        )
    blockers = []
    for row in records:
        for field in (
            "duplicate_rows",
            "open_bar_rows",
            "critical_null_rows",
            "invalid_market_rows",
        ):
            if row[field] != 0:
                blockers.append(f"{row['source']}:{field}")
    if blockers:
        raise RuntimeError(f"15m data-quality blockers: {blockers}")
    return {
        "cutoff_exclusive_utc": CUTOFF.isoformat(),
        "sources": list(SOURCES),
        "source_priority": list(SOURCES),
        "by_source": records,
        "raw_union_rows": int(union["raw_union_rows"]),
        "selected_rows": int(union["selected_rows"]),
        "symbol_count": int(union["symbol_count"]),
        "start_ts": pd.Timestamp(union["start_ts"]).isoformat(),
        "end_ts": pd.Timestamp(union["end_ts"]).isoformat(),
        "controlled_overlap_rows": int(union["controlled_overlap_rows"]),
    }


def load_daily_bars(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    query = """
        WITH source_rows AS (
            SELECT
                ts, symbol, base_asset, quote_asset, open, high, low, close,
                volume, quote_volume, trade_count, is_closed
            FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
            WHERE source IN (?, ?) AND ts < ? AND symbol IS NOT NULL
            QUALIFY row_number() OVER (
                PARTITION BY symbol, ts
                ORDER BY CASE source
                    WHEN 'binance_vision_kline_monthly' THEN 0
                    WHEN 'binance_futures_kline_api' THEN 1
                    ELSE 2
                END
            ) = 1
        ),
        listing AS (
            SELECT symbol, min(ts) AS first_observed_ts, max(ts) AS last_observed_ts,
                   count(*) AS input_rows
            FROM source_rows
            GROUP BY symbol
        ),
        daily AS (
            SELECT
                symbol,
                any_value(base_asset) AS base_asset,
                any_value(quote_asset) AS quote_asset,
                date_trunc('day', ts) AS event_date,
                arg_min(open, ts) AS open,
                max(high) AS high,
                min(low) AS low,
                arg_max(close, ts) AS close,
                sum(volume) AS volume,
                sum(quote_volume) AS quote_volume,
                sum(trade_count) AS trade_count,
                count(*) AS bar_count,
                min(ts) AS first_bar_ts,
                max(ts) AS last_bar_ts,
                bool_and(is_closed) AS all_closed
            FROM source_rows
            GROUP BY symbol, date_trunc('day', ts)
        )
        SELECT daily.*, listing.first_observed_ts, listing.last_observed_ts,
               listing.input_rows
        FROM daily JOIN listing USING (symbol)
        ORDER BY symbol, event_date
    """
    frame = connection.execute(
        query, [str(INPUT_GLOB), *SOURCES, CUTOFF.to_pydatetime()]
    ).fetch_df()
    for column in (
        "event_date",
        "first_bar_ts",
        "last_bar_ts",
        "first_observed_ts",
        "last_observed_ts",
    ):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    expected_last = frame["event_date"] + pd.Timedelta(hours=23, minutes=45)
    frame["is_complete_day"] = (
        frame["bar_count"].eq(96)
        & frame["first_bar_ts"].eq(frame["event_date"])
        & frame["last_bar_ts"].eq(expected_last)
        & frame["all_closed"].fillna(False)
    )
    complete = frame.loc[frame["is_complete_day"]].copy()
    complete = complete.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    gap_days = complete.groupby("symbol", sort=False)["event_date"].diff().dt.days
    quality = {
        "daily_groups": int(len(frame)),
        "complete_daily_bars": int(len(complete)),
        "partial_daily_groups": int((~frame["is_complete_day"]).sum()),
        "symbols_with_complete_days": int(complete["symbol"].nunique()),
        "complete_start": complete["event_date"].min().isoformat(),
        "complete_end": complete["event_date"].max().isoformat(),
        "gap_2_to_4_observations": int(gap_days.between(2, 4).sum()),
        "gap_gt_4_observations": int(gap_days.gt(4).sum()),
        "maximum_gap_days": int(gap_days.max()),
    }
    stock = complete.loc[complete["base_asset"].isin(US_STOCK_LIKE_BASES)]
    quality["us_stock_like_symbols"] = int(stock["symbol"].nunique())
    quality["us_stock_like_complete_daily_bars"] = int(len(stock))
    return frame, quality


def _feature_block(group: pd.DataFrame) -> pd.DataFrame:
    block = group.copy()
    close = block["close"].astype(float)
    high = block["high"].astype(float)
    low = block["low"].astype(float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr20 = true_range.rolling(20, min_periods=20).mean()
    atr_delta = atr20.diff()
    block["true_range"] = true_range
    block["atr20"] = atr20
    block["atr20_pre"] = atr20.shift(1)
    block["atr_change_5d_pre"] = atr20.shift(1) / atr20.shift(6) - 1.0
    block["atr_change_10d_pre"] = atr20.shift(1) / atr20.shift(11) - 1.0
    block["atr_change_20d_pre"] = atr20.shift(1) / atr20.shift(21) - 1.0
    block["atr_path_percentile_60"] = rolling_percentile_current(
        block["atr_change_10d_pre"].to_numpy(dtype=float), 60
    )
    down = atr_delta.lt(0).astype(float).where(atr_delta.notna())
    up = atr_delta.gt(0).astype(float).where(atr_delta.notna())
    block["atr_down_count_10_pre"] = down.rolling(10, min_periods=10).sum().shift(1)
    block["atr_up_count_10_pre"] = up.rolling(10, min_periods=10).sum().shift(1)
    block["breakout_range_ratio"] = true_range / atr20.shift(1).replace(0.0, np.nan)
    for period in MA_PERIODS:
        block[f"sma{period}"] = close.rolling(period, min_periods=period).mean()
        block[f"ma{period}_slope_normalized"] = (
            block[f"sma{period}"] - block[f"sma{period}"].shift(1)
        ) / block["atr20_pre"].replace(0.0, np.nan)
        block[f"distance_ma{period}_atr"] = (
            close - block[f"sma{period}"]
        ) / block["atr20_pre"].replace(0.0, np.nan)
    block["sma30"] = close.rolling(30, min_periods=30).mean()
    block["ma30_slope_normalized"] = (
        block["sma30"] - block["sma30"].shift(1)
    ) / block["atr20_pre"].replace(0.0, np.nan)
    absolute_path = close.diff().abs().rolling(20, min_periods=20).sum()
    block["er20"] = (close - close.shift(20)).abs() / absolute_path.replace(0, np.nan)
    log_return = np.log(close).diff()
    block["rv20"] = log_return.rolling(20, min_periods=20).std(ddof=1) * math.sqrt(365)
    for horizon in (5, 10, 20):
        block[f"return_{horizon}"] = close / close.shift(horizon) - 1.0
    quote_volume = block["quote_volume"].astype(float)
    block["volume_ratio_5_20"] = (
        quote_volume.rolling(5, min_periods=5).mean()
        / quote_volume.rolling(20, min_periods=20).mean().replace(0.0, np.nan)
    )
    block["adv30_median"] = quote_volume.rolling(30, min_periods=30).median()
    for horizon in HORIZONS:
        block[f"entry_date_{horizon}"] = block["event_date"].shift(-1)
        block[f"entry_open_{horizon}"] = block["open"].shift(-1)
        block[f"exit_date_{horizon}"] = block["event_date"].shift(-(horizon + 1))
        block[f"exit_open_{horizon}"] = block["open"].shift(-(horizon + 1))
    return block


def prepare_feature_panel(daily: pd.DataFrame) -> pd.DataFrame:
    panel = daily.loc[daily["is_complete_day"]].copy()
    panel = panel.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    previous_date = panel.groupby("symbol", sort=False)["event_date"].shift(1)
    gap = (panel["event_date"] - previous_date).dt.days
    panel["new_block"] = previous_date.isna() | gap.gt(4)
    panel["block_id"] = panel.groupby("symbol", sort=False)["new_block"].cumsum().astype(int)
    blocks = [
        _feature_block(group)
        for _, group in panel.groupby(["symbol", "block_id"], sort=False)
    ]
    panel = pd.concat(blocks, ignore_index=True)
    panel["listing_age_days"] = np.floor(
        (panel["event_date"] - panel["first_observed_ts"]).dt.total_seconds() / 86_400.0
    ).astype(int)
    required = [
        "atr20_pre",
        "atr_change_5d_pre",
        "atr_change_10d_pre",
        "atr_change_20d_pre",
        "atr_path_percentile_60",
        "breakout_range_ratio",
        "ma7_slope_normalized",
        "ma30_slope_normalized",
        "er20",
        "rv20",
        "return_5",
        "return_10",
        "return_20",
        "distance_ma7_atr",
        "volume_ratio_5_20",
    ]
    finite = np.isfinite(panel[required].astype(float).to_numpy()).all(axis=1)
    panel["eligible_features"] = finite & panel["listing_age_days"].ge(120)
    panel["up_state"] = panel["close"].gt(panel["sma30"]) & panel[
        "ma30_slope_normalized"
    ].gt(0)
    panel["down_state"] = panel["close"].lt(panel["sma30"]) & panel[
        "ma30_slope_normalized"
    ].lt(0)
    panel["atr_expanding"] = panel["atr_change_10d_pre"].gt(0)
    add_leave_one_out_breadth(panel)
    eligible_index = panel.index[panel["eligible_features"]]
    panel.loc[eligible_index, "liquidity_rank"] = (
        panel.loc[eligible_index]
        .groupby("event_date")["adv30_median"]
        .rank(method="first", ascending=False)
    )
    panel["liquidity_segment"] = np.where(
        panel["liquidity_rank"].le(20), "top20", "long_tail"
    )
    panel.loc[panel["liquidity_rank"].isna(), "liquidity_segment"] = "unavailable"
    panel["asset_slice"] = np.where(
        panel["base_asset"].isin(US_STOCK_LIKE_BASES), "us_stock_like", "other"
    )
    panel["calendar_year"] = panel["event_date"].dt.year.astype(int)
    return panel


def _loo_median(values: pd.Series) -> pd.Series:
    array = values.to_numpy(dtype=float)
    output = np.full(len(array), np.nan, dtype=float)
    valid_positions = np.flatnonzero(np.isfinite(array))
    valid = array[valid_positions]
    n = len(valid)
    if n < 2:
        return pd.Series(output, index=values.index)
    order = np.argsort(valid, kind="mergesort")
    sorted_values = valid[order]
    ranks = np.empty(n, dtype=int)
    ranks[order] = np.arange(n)
    if n % 2 == 0:
        k = n // 2
        medians = np.where(ranks <= k - 1, sorted_values[k], sorted_values[k - 1])
    else:
        k = n // 2
        below = (sorted_values[k] + sorted_values[k + 1]) / 2.0
        at = (sorted_values[k - 1] + sorted_values[k + 1]) / 2.0
        above = (sorted_values[k - 1] + sorted_values[k]) / 2.0
        medians = np.where(ranks < k, below, np.where(ranks == k, at, above))
    output[valid_positions] = medians
    return pd.Series(output, index=values.index)


def add_leave_one_out_breadth(panel: pd.DataFrame) -> None:
    eligible = panel.loc[panel["eligible_features"]].copy()
    group = eligible.groupby("event_date", sort=False)
    count = group["symbol"].transform("size").astype(float)
    denominator = (count - 1.0).replace(0.0, np.nan)
    up = eligible["up_state"].astype(float)
    down = eligible["down_state"].astype(float)
    expand = eligible["atr_expanding"].astype(float)
    up_loo = (group["up_state"].transform("sum") - up) / denominator
    down_loo = (group["down_state"].transform("sum") - down) / denominator
    eligible["breadth_trend_balance_loo"] = up_loo - down_loo
    eligible["breadth_atr_expansion_share_loo"] = (
        group["atr_expanding"].transform("sum") - expand
    ) / denominator
    eligible["breadth_median_return_10_loo"] = group["return_10"].transform(
        _loo_median
    )
    value = eligible["return_10"].astype(float)
    sum_value = group["return_10"].transform("sum") - value
    sum_square = group["return_10"].transform(lambda x: float(np.square(x).sum())) - np.square(value)
    loo_count = count - 1.0
    variance = (
        sum_square - np.square(sum_value) / loo_count.replace(0.0, np.nan)
    ) / (loo_count - 1.0).replace(0.0, np.nan)
    eligible["breadth_return_10_dispersion_loo"] = np.sqrt(variance.clip(lower=0.0))
    eligible["breadth_eligible_count"] = count
    columns = [
        "breadth_trend_balance_loo",
        "breadth_atr_expansion_share_loo",
        "breadth_median_return_10_loo",
        "breadth_return_10_dispersion_loo",
        "breadth_eligible_count",
    ]
    panel.loc[eligible.index, columns] = eligible[columns]


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    grouped = panel.groupby(["symbol", "block_id"], sort=False)
    previous_close = grouped["close"].shift(1)
    frames: list[pd.DataFrame] = []
    identity = [
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "open",
        "high",
        "low",
        "close",
        "atr20_pre",
        "atr_change_5d_pre",
        "atr_change_10d_pre",
        "atr_change_20d_pre",
        "atr_path_percentile_60",
        "atr_down_count_10_pre",
        "atr_up_count_10_pre",
        "breakout_range_ratio",
        "ma30_slope_normalized",
        "er20",
        "rv20",
        "return_5",
        "return_10",
        "return_20",
        "volume_ratio_5_20",
        "breadth_trend_balance_loo",
        "breadth_atr_expansion_share_loo",
        "breadth_median_return_10_loo",
        "breadth_return_10_dispersion_loo",
        "breadth_eligible_count",
        "listing_age_days",
        "liquidity_segment",
        "asset_slice",
        "calendar_year",
    ]
    for period in MA_PERIODS:
        previous_ma = grouped[f"sma{period}"].shift(1)
        long_trigger = previous_close.le(previous_ma) & panel["close"].gt(
            panel[f"sma{period}"]
        )
        short_trigger = previous_close.ge(previous_ma) & panel["close"].lt(
            panel[f"sma{period}"]
        )
        for direction, sign, trigger in (
            ("long", 1.0, long_trigger),
            ("short", -1.0, short_trigger),
        ):
            mask = trigger & panel["eligible_features"]
            events = panel.loc[mask, identity].copy()
            events["ma_period"] = period
            events["direction"] = direction
            events["direction_sign"] = sign
            events["ma_slope_normalized"] = panel.loc[
                mask, f"ma{period}_slope_normalized"
            ].to_numpy(dtype=float)
            events["distance_ma_atr"] = panel.loc[
                mask, f"distance_ma{period}_atr"
            ].to_numpy(dtype=float)
            events["ma_slope_aligned"] = sign * events["ma_slope_normalized"] > 0
            events["aligned_ma7_slope"] = sign * panel.loc[
                mask, "ma7_slope_normalized"
            ].to_numpy(dtype=float)
            events["aligned_ma30_slope"] = sign * events["ma30_slope_normalized"]
            for horizon in (5, 10, 20):
                events[f"aligned_return_{horizon}"] = sign * events[f"return_{horizon}"]
            events["atr_down_share_10_pre"] = events["atr_down_count_10_pre"] / 10.0
            events["atr_up_share_10_pre"] = events["atr_up_count_10_pre"] / 10.0
            events["aligned_distance_ma7_atr"] = sign * panel.loc[
                mask, "distance_ma7_atr"
            ].to_numpy(dtype=float)
            events["aligned_breadth_trend_balance_loo"] = (
                sign * events["breadth_trend_balance_loo"]
            )
            events["aligned_breadth_median_return_10_loo"] = (
                sign * events["breadth_median_return_10_loo"]
            )
            for horizon in HORIZONS:
                entry_open = panel.loc[mask, f"entry_open_{horizon}"].to_numpy(dtype=float)
                exit_open = panel.loc[mask, f"exit_open_{horizon}"].to_numpy(dtype=float)
                gross = sign * (exit_open / entry_open - 1.0)
                events[f"entry_date_{horizon}"] = panel.loc[
                    mask, f"entry_date_{horizon}"
                ].to_numpy()
                events[f"exit_date_{horizon}"] = panel.loc[
                    mask, f"exit_date_{horizon}"
                ].to_numpy()
                events[f"entry_open_{horizon}"] = entry_open
                events[f"exit_open_{horizon}"] = exit_open
                events[f"gross_return_{horizon}"] = gross
                events[f"net_return_{horizon}"] = gross - ROUND_TRIP_COST
                events[f"target_{horizon}"] = events[f"net_return_{horizon}"].gt(0).astype("Int64")
            events["event_id"] = (
                "P3|MA"
                + str(period)
                + "|"
                + direction
                + "|"
                + events["symbol"].astype(str)
                + "|"
                + events["event_date"].dt.strftime("%Y-%m-%d")
            )
            frames.append(events)
    result = pd.concat(frames, ignore_index=True)
    if result["event_id"].duplicated().any():
        raise RuntimeError("duplicate P3 event identifiers")
    if set(result["direction"].unique()) != {"long", "short"}:
        raise RuntimeError("P3 events do not contain both directions")
    return result.sort_values(["ma_period", "event_date", "symbol"]).reset_index(drop=True)


def fixed_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    aligned = events["ma_slope_aligned"].astype(bool)
    burst = events["breakout_range_ratio"].gt(1.20)
    local_style = (
        events["direction"].eq("long") & events["atr_path_percentile_60"].gt(0.80)
    ) | (
        events["direction"].eq("short")
        & events["atr_path_percentile_60"].le(0.20)
    )
    local = aligned & burst & local_style
    breadth = events["aligned_breadth_trend_balance_loo"].gt(0)
    return {
        "ALL_MA7": pd.Series(True, index=events.index),
        "SLOPE_ALIGNED": aligned,
        "P2_LOCAL_FIXED": local,
        "P2_LOCAL_BREADTH_FIXED": local & breadth,
    }


def scope_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    masks = {
        "DEVELOPMENT_ALL": events["event_date"].lt(DEVELOPMENT_CUTOFF),
        "CONFIRMATION": events["event_date"].ge(DEVELOPMENT_CUTOFF),
    }
    for name, start, end in FOLDS:
        masks[name] = events["event_date"].ge(start) & events["event_date"].lt(end)
    return masks


def stats_row(frame: pd.DataFrame, column: str) -> dict[str, Any]:
    return infer_mean(frame[column], frame["symbol"], frame["event_date"])


def build_fixed_stats(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period in MA_PERIODS:
        base = events.loc[events["ma_period"].eq(period)]
        filters = fixed_masks(base)
        scopes = scope_masks(base)
        for filter_name in FIXED_FILTERS:
            for scope, scope_mask in scopes.items():
                selected = base.loc[filters[filter_name] & scope_mask]
                for direction in ("both", "long", "short"):
                    directional = (
                        selected
                        if direction == "both"
                        else selected.loc[selected["direction"].eq(direction)]
                    )
                    for horizon in PRIMARY_HORIZONS:
                        valid = directional.loc[
                            directional[f"net_return_{horizon}"].notna()
                        ]
                        for metric in ("gross_return", "net_return"):
                            rows.append(
                                {
                                    "ma_period": period,
                                    "filter_name": filter_name,
                                    "scope": scope,
                                    "direction": direction,
                                    "horizon_sessions": horizon,
                                    "return_metric": metric,
                                    **stats_row(valid, f"{metric}_{horizon}"),
                                }
                            )
    return pd.DataFrame(rows).sort_values(
        ["ma_period", "filter_name", "scope", "direction", "horizon_sessions", "return_metric"]
    )


def build_fixed_frequency(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)].copy()
    rows: list[dict[str, Any]] = []
    for filter_name, mask in fixed_masks(primary).items():
        selected = primary.loc[mask]
        for scope, scope_mask in scope_masks(primary).items():
            scoped = selected.loc[scope_mask.loc[selected.index]]
            for direction in ("both", "long", "short"):
                directional = (
                    scoped if direction == "both" else scoped.loc[scoped["direction"].eq(direction)]
                )
                for period_type, period_code in (("day", "D"), ("week", "W-SUN"), ("month", "M")):
                    if directional.empty:
                        values = np.asarray([], dtype=float)
                    else:
                        key = directional["event_date"].dt.tz_convert(None).dt.to_period(period_code)
                        values = key.value_counts().to_numpy(dtype=float)
                    rows.append(
                        {
                            "filter_name": filter_name,
                            "scope": scope,
                            "direction": direction,
                            "period_type": period_type,
                            "event_count": int(len(directional)),
                            "symbol_count": int(directional["symbol"].nunique()),
                            "event_date_count": int(directional["event_date"].nunique()),
                            "active_period_count": int(len(values)),
                            "mean_when_active": float(values.mean()) if len(values) else math.nan,
                            "median_when_active": float(np.median(values)) if len(values) else math.nan,
                            "maximum": int(values.max()) if len(values) else 0,
                        }
                    )
    return pd.DataFrame(rows)


def build_fixed_robustness(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)].copy()
    rows: list[dict[str, Any]] = []
    masks = fixed_masks(primary)
    for filter_name in FIXED_FILTERS:
        selected = primary.loc[masks[filter_name]]
        for scope, scope_mask in scope_masks(primary).items():
            scoped = selected.loc[scope_mask.loc[selected.index]]
            for slice_type, column in (
                ("asset_slice", "asset_slice"),
                ("liquidity_segment", "liquidity_segment"),
                ("calendar_year", "calendar_year"),
            ):
                for slice_value, sliced in scoped.groupby(column, dropna=False):
                    for direction in ("both", "long", "short"):
                        directional = (
                            sliced
                            if direction == "both"
                            else sliced.loc[sliced["direction"].eq(direction)]
                        )
                        for horizon in PRIMARY_HORIZONS:
                            valid = directional.loc[
                                directional[f"net_return_{horizon}"].notna()
                            ]
                            rows.append(
                                {
                                    "filter_name": filter_name,
                                    "scope": scope,
                                    "slice_type": slice_type,
                                    "slice_value": slice_value,
                                    "direction": direction,
                                    "horizon_sessions": horizon,
                                    **stats_row(valid, f"net_return_{horizon}"),
                                }
                            )
    return pd.DataFrame(rows)


def fold_for_events(events: pd.DataFrame) -> pd.Series:
    output = pd.Series(pd.NA, index=events.index, dtype="string")
    for name, start, end in FOLDS:
        output.loc[events["event_date"].ge(start) & events["event_date"].lt(end)] = name
    return output


def score_quintile(scores: np.ndarray, train_scores: np.ndarray) -> np.ndarray:
    edges = np.quantile(train_scores, [0.2, 0.4, 0.6, 0.8])
    return np.searchsorted(edges, scores, side="left") + 1


def train_models(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    candidates = events.loc[
        events["ma_period"].eq(7) & events["ma_slope_aligned"]
    ].copy()
    predictions: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []
    quintiles: list[dict[str, Any]] = []
    importance: list[dict[str, Any]] = []
    for horizon in PRIMARY_HORIZONS:
        exit_column = f"exit_date_{horizon}"
        target_column = f"target_{horizon}"
        net_column = f"net_return_{horizon}"
        complete = candidates.loc[
            candidates[exit_column].notna()
            & candidates[target_column].notna()
            & candidates[net_column].notna()
        ].copy()
        for fold_name, test_start, test_end in FOLDS:
            train = complete.loc[complete[exit_column].lt(test_start)].copy()
            test = complete.loc[
                complete["event_date"].ge(test_start)
                & complete["event_date"].lt(test_end)
            ].copy()
            if len(train) < 1000 or len(test) < 20:
                continue
            x_train = train[FEATURE_COLUMNS]
            x_test = test[FEATURE_COLUMNS]
            y_train = train[target_column].astype(int).to_numpy()
            y_test = test[target_column].astype(int).to_numpy()
            if np.unique(y_train).size < 2 or np.unique(y_test).size < 2:
                continue
            model_specs: dict[str, Any] = {
                "LOGISTIC": Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                        (
                            "model",
                            LogisticRegression(
                                C=0.2,
                                max_iter=2000,
                                solver="lbfgs",
                                random_state=42,
                            ),
                        ),
                    ]
                ),
                "LIGHTGBM": Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        (
                            "model",
                            lgb.LGBMClassifier(
                                n_estimators=160,
                                learning_rate=0.03,
                                num_leaves=15,
                                max_depth=4,
                                min_child_samples=200,
                                subsample=0.8,
                                colsample_bytree=0.8,
                                reg_lambda=5.0,
                                random_state=42,
                                n_jobs=4,
                                verbosity=-1,
                            ),
                        ),
                    ]
                ),
            }
            for model_name, model in model_specs.items():
                model.fit(x_train, y_train)
                train_score = model.predict_proba(x_train)[:, 1]
                test_score = model.predict_proba(x_test)[:, 1]
                threshold = float(np.quantile(train_score, 0.80))
                selected = test_score > threshold
                q = score_quintile(test_score, train_score)
                output = test[
                    [
                        "event_id",
                        "symbol",
                        "base_asset",
                        "event_date",
                        "direction",
                        "direction_sign",
                        "asset_slice",
                        "liquidity_segment",
                        f"entry_date_{horizon}",
                        f"entry_open_{horizon}",
                        f"exit_date_{horizon}",
                        f"exit_open_{horizon}",
                        f"gross_return_{horizon}",
                        f"net_return_{horizon}",
                        f"target_{horizon}",
                    ]
                ].copy()
                output["horizon_sessions"] = horizon
                output["fold"] = fold_name
                output["model"] = model_name
                output["score"] = test_score
                output["threshold_train_q80"] = threshold
                output["selected"] = selected
                output["score_quintile_train_edges"] = q
                predictions.append(output)
                selected_frame = test.loc[selected]
                selected_stats = stats_row(selected_frame, net_column)
                metrics.append(
                    {
                        "horizon_sessions": horizon,
                        "fold": fold_name,
                        "model": model_name,
                        "train_count": len(train),
                        "test_count": len(test),
                        "test_positive_rate": float(y_test.mean()),
                        "roc_auc": float(roc_auc_score(y_test, test_score)),
                        "brier_score": float(brier_score_loss(y_test, test_score)),
                        "threshold_train_q80": threshold,
                        "selected_count": int(selected.sum()),
                        "selected_share": float(selected.mean()),
                        **{f"selected_{key}": value for key, value in selected_stats.items()},
                    }
                )
                for quintile in range(1, 6):
                    q_frame = test.loc[q == quintile]
                    quintiles.append(
                        {
                            "horizon_sessions": horizon,
                            "fold": fold_name,
                            "model": model_name,
                            "score_quintile_train_edges": quintile,
                            **stats_row(q_frame, net_column),
                        }
                    )
                if model_name == "LOGISTIC":
                    values = model.named_steps["model"].coef_[0]
                else:
                    values = model.named_steps["model"].feature_importances_
                for feature, value in zip(FEATURE_COLUMNS, values, strict=True):
                    importance.append(
                        {
                            "horizon_sessions": horizon,
                            "fold": fold_name,
                            "model": model_name,
                            "feature": feature,
                            "importance": float(value),
                        }
                    )
    return (
        pd.concat(predictions, ignore_index=True),
        pd.DataFrame(metrics),
        pd.DataFrame(quintiles),
        pd.DataFrame(importance),
    )


def candidate_score(frame: pd.DataFrame, strategy: str) -> pd.Series:
    if strategy == "ALL_MA7":
        return frame["breakout_range_ratio"].fillna(-np.inf)
    if strategy == "SLOPE_ALIGNED":
        return frame["aligned_ma7_slope"].fillna(-np.inf)
    if strategy == "P2_LOCAL_FIXED":
        return frame["breakout_range_ratio"].fillna(-np.inf) + frame[
            "atr_path_percentile_60"
        ].where(frame["direction"].eq("long"), 1.0 - frame["atr_path_percentile_60"])
    if strategy == "P2_LOCAL_BREADTH_FIXED":
        return candidate_score(frame, "P2_LOCAL_FIXED") + frame[
            "aligned_breadth_trend_balance_loo"
        ].fillna(-np.inf)
    raise ValueError(strategy)


def fixed_oos_candidates(events: pd.DataFrame, strategy: str, horizon: int) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)].copy()
    primary["fold"] = fold_for_events(primary)
    primary = primary.loc[
        primary["fold"].notna() & primary[f"exit_date_{horizon}"].notna()
    ].copy()
    mask = fixed_masks(primary)[strategy]
    selected = primary.loc[mask].copy()
    selected["rank_score"] = candidate_score(selected, strategy)
    selected["strategy"] = strategy
    selected["horizon_sessions"] = horizon
    return selected


def model_oos_candidates(predictions: pd.DataFrame, model: str, horizon: int) -> pd.DataFrame:
    selected = predictions.loc[
        predictions["model"].eq(model)
        & predictions["horizon_sessions"].eq(horizon)
        & predictions["selected"]
    ].copy()
    selected = selected.rename(columns={"score": "rank_score"})
    selected["strategy"] = f"{model}_TOP20"
    return selected


def _price_lookup(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], tuple[float, float]]:
    return {
        (str(row.symbol), pd.Timestamp(row.event_date)): (float(row.open), float(row.close))
        for row in panel[["symbol", "event_date", "open", "close"]].itertuples(index=False)
    }


def run_account(
    candidates: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    strategy: str,
    horizon: int,
    scope: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    entry_column = f"entry_date_{horizon}"
    exit_column = f"exit_date_{horizon}"
    entry_price_column = f"entry_open_{horizon}"
    exit_price_column = f"exit_open_{horizon}"
    if scope == "HISTORICAL_OOS":
        candidates = candidates.loc[
            candidates["event_date"].lt(DEVELOPMENT_CUTOFF)
            & candidates[exit_column].lt(DEVELOPMENT_CUTOFF)
        ]
        calendar_end = DEVELOPMENT_CUTOFF - pd.Timedelta(days=1)
    elif scope == "CONFIRMATION":
        candidates = candidates.loc[candidates["event_date"].ge(DEVELOPMENT_CUTOFF)]
        calendar_end = CUTOFF - pd.Timedelta(days=1)
    elif scope == "ALL_OOS":
        calendar_end = CUTOFF - pd.Timedelta(days=1)
    else:
        raise ValueError(scope)
    if candidates.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "strategy": strategy,
            "horizon_sessions": horizon,
            "scope": scope,
            "trade_count": 0,
        }
    candidates = candidates.sort_values(
        [entry_column, "rank_score", "symbol"], ascending=[True, False, True]
    ).copy()
    by_entry = {
        pd.Timestamp(date): group
        for date, group in candidates.groupby(entry_column, sort=True)
    }
    calendar_start = pd.Timestamp(candidates[entry_column].min()).normalize()
    calendar = pd.date_range(calendar_start, calendar_end, freq="D", tz="UTC")
    price = _price_lookup(panel)
    equity = 1.0
    active: list[dict[str, Any]] = []
    equity_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []
    total_cost = 0.0
    turnover = 0.0
    ruined = False
    ruin_date: pd.Timestamp | None = None
    for date in calendar:
        day_pnl = 0.0
        survivors: list[dict[str, Any]] = []
        for position in active:
            if date == position["exit_date"]:
                exit_price = position["exit_price"]
                pnl = (
                    position["direction_sign"]
                    * (exit_price - position["last_mark"])
                    / position["entry_price"]
                    * position["notional"]
                )
                cost = SIDE_COST * position["notional"]
                day_pnl += pnl - cost
                total_cost += cost
                turnover += position["notional"]
                gross_trade = position["direction_sign"] * (
                    exit_price / position["entry_price"] - 1.0
                )
                trade_rows.append(
                    {
                        **{key: position[key] for key in (
                            "event_id",
                            "symbol",
                            "direction",
                            "entry_date",
                            "exit_date",
                            "notional",
                            "rank_score",
                        )},
                        "strategy": strategy,
                        "horizon_sessions": horizon,
                        "scope": scope,
                        "gross_trade_return": gross_trade,
                        "net_trade_return": gross_trade - ROUND_TRIP_COST,
                        "dollar_pnl": position["notional"] * (gross_trade - ROUND_TRIP_COST),
                    }
                )
            else:
                survivors.append(position)
        active = survivors
        day_candidates = by_entry.get(date)
        if day_candidates is not None:
            active_symbols = {position["symbol"] for position in active}
            available = MAX_POSITIONS - len(active)
            for row in day_candidates.itertuples(index=False):
                if available <= 0:
                    break
                symbol = str(row.symbol)
                if symbol in active_symbols:
                    continue
                entry_price = float(getattr(row, entry_price_column))
                exit_price = float(getattr(row, exit_price_column))
                exit_date = pd.Timestamp(getattr(row, exit_column))
                if not np.isfinite(entry_price) or not np.isfinite(exit_price):
                    continue
                notional = POSITION_ALLOCATION * max(equity + day_pnl, 0.0)
                cost = SIDE_COST * notional
                day_pnl -= cost
                total_cost += cost
                turnover += notional
                active.append(
                    {
                        "event_id": str(row.event_id),
                        "symbol": symbol,
                        "direction": str(row.direction),
                        "direction_sign": float(row.direction_sign),
                        "entry_date": date,
                        "exit_date": exit_date,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "last_mark": entry_price,
                        "notional": notional,
                        "rank_score": float(row.rank_score),
                    }
                )
                active_symbols.add(symbol)
                available -= 1
        for position in active:
            observed = price.get((position["symbol"], date))
            if observed is None:
                continue
            close_price = observed[1]
            pnl = (
                position["direction_sign"]
                * (close_price - position["last_mark"])
                / position["entry_price"]
                * position["notional"]
            )
            day_pnl += pnl
            position["last_mark"] = close_price
        equity += day_pnl
        if equity <= 0.0:
            equity = 0.0
            ruined = True
            ruin_date = date
            active = []
        equity_rows.append(
            {
                "date": date,
                "strategy": strategy,
                "horizon_sessions": horizon,
                "scope": scope,
                "equity": equity,
                "daily_pnl": day_pnl,
                "active_positions": len(active),
            }
        )
        if ruined:
            break
    equity_frame = pd.DataFrame(equity_rows)
    trades = pd.DataFrame(trade_rows)
    if equity_frame.empty:
        metrics = {
            "strategy": strategy,
            "horizon_sessions": horizon,
            "scope": scope,
            "trade_count": 0,
        }
        return equity_frame, trades, metrics
    running_peak = equity_frame["equity"].cummax()
    drawdown = equity_frame["equity"] / running_peak - 1.0
    days = max((equity_frame["date"].iloc[-1] - equity_frame["date"].iloc[0]).days, 1)
    total_return = float(equity_frame["equity"].iloc[-1] - 1.0)
    annualized = float((1.0 + total_return) ** (365.0 / days) - 1.0) if total_return > -1 else -1.0
    net_trade = trades["net_trade_return"] if not trades.empty else pd.Series(dtype=float)
    positive = float(net_trade.loc[net_trade > 0].sum())
    negative = float(-net_trade.loc[net_trade < 0].sum())
    metrics = {
        "strategy": strategy,
        "horizon_sessions": horizon,
        "scope": scope,
        "start_date": equity_frame["date"].iloc[0],
        "end_date": equity_frame["date"].iloc[-1],
        "calendar_days": days + 1,
        "total_return": total_return,
        "annualized_return": annualized,
        "maximum_drawdown": float(drawdown.min()),
        "trade_count": int(len(trades)),
        "win_rate": float((net_trade > 0).mean()) if len(net_trade) else math.nan,
        "profit_factor": positive / negative if negative > 0 else math.inf if positive > 0 else math.nan,
        "average_concurrent_positions": float(equity_frame["active_positions"].mean()),
        "maximum_concurrent_positions": int(equity_frame["active_positions"].max()),
        "turnover_notional": turnover,
        "explicit_cost_paid": total_cost,
        "funding_included": False,
        "ruined": ruined,
        "ruin_date": ruin_date,
    }
    return equity_frame, trades, metrics


def build_accounts(
    events: pd.DataFrame, predictions: pd.DataFrame, panel: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    equity_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []
    for horizon in PRIMARY_HORIZONS:
        candidates_by_strategy = {
            strategy: fixed_oos_candidates(events, strategy, horizon)
            for strategy in FIXED_FILTERS
        }
        for model in ("LOGISTIC", "LIGHTGBM"):
            candidates_by_strategy[f"{model}_TOP20"] = model_oos_candidates(
                predictions, model, horizon
            )
        for strategy, candidates in candidates_by_strategy.items():
            for scope in ("HISTORICAL_OOS", "CONFIRMATION", "ALL_OOS"):
                equity, trades, result = run_account(
                    candidates,
                    panel,
                    strategy=strategy,
                    horizon=horizon,
                    scope=scope,
                )
                metrics.append(result)
                if not equity.empty:
                    equity_frames.append(equity)
                if not trades.empty:
                    trade_frames.append(trades)
    return (
        pd.DataFrame(metrics),
        pd.concat(equity_frames, ignore_index=True),
        pd.concat(trade_frames, ignore_index=True),
    )


def pass_assessment(
    fixed_stats: pd.DataFrame,
    ml_metrics: pd.DataFrame,
    events: pd.DataFrame,
    predictions: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict[str, Any]:
    primary = fixed_stats.loc[
        fixed_stats["ma_period"].eq(7)
        & fixed_stats["return_metric"].eq("net_return")
        & fixed_stats["direction"].eq("both")
    ]
    assessment: dict[str, Any] = {"fixed": {}, "ml": {}}
    for strategy in FIXED_FILTERS:
        rows = primary.loc[primary["filter_name"].eq(strategy)]
        item: dict[str, Any] = {}
        for horizon in PRIMARY_HORIZONS:
            horizon_rows = rows.loc[rows["horizon_sessions"].eq(horizon)]
            confirm = horizon_rows.loc[horizon_rows["scope"].eq("CONFIRMATION")]
            historical = horizon_rows.loc[
                horizon_rows["scope"].isin(["Y2022", "Y2023", "Y2024", "Y2025", "H1_2026"])
            ]
            item[str(horizon)] = {
                "confirmation_mean": float(confirm["mean"].iloc[0]) if len(confirm) else math.nan,
                "confirmation_count": int(confirm["sample_count"].iloc[0]) if len(confirm) else 0,
                "positive_historical_folds": int(historical["mean"].gt(0).sum()),
                "historical_fold_count": int(historical["mean"].notna().sum()),
            }
        assessment["fixed"][strategy] = item
    for model in ("LOGISTIC", "LIGHTGBM"):
        item = {}
        for horizon in PRIMARY_HORIZONS:
            rows = ml_metrics.loc[
                ml_metrics["model"].eq(model)
                & ml_metrics["horizon_sessions"].eq(horizon)
            ]
            confirm = rows.loc[rows["fold"].eq("CONFIRM_2026_07_08")]
            history = rows.loc[~rows["fold"].eq("CONFIRM_2026_07_08")]
            item[str(horizon)] = {
                "confirmation_mean": float(confirm["selected_mean"].iloc[0]) if len(confirm) else math.nan,
                "confirmation_count": int(confirm["selected_sample_count"].iloc[0]) if len(confirm) else 0,
                "confirmation_auc": float(confirm["roc_auc"].iloc[0]) if len(confirm) else math.nan,
                "positive_historical_folds": int(history["selected_mean"].gt(0).sum()),
                "historical_fold_count": int(history["selected_mean"].notna().sum()),
            }
        assessment["ml"][model] = item
    primary_events = events.loc[events["ma_period"].eq(7)]
    confirm_events = primary_events.loc[primary_events["event_date"].ge(DEVELOPMENT_CUTOFF)]
    fixed_confirm = fixed_stats.loc[
        fixed_stats["ma_period"].eq(7)
        & fixed_stats["return_metric"].eq("net_return")
        & fixed_stats["scope"].eq("CONFIRMATION")
    ]
    local_20 = fixed_confirm.loc[
        fixed_confirm["filter_name"].eq("P2_LOCAL_FIXED")
        & fixed_confirm["horizon_sessions"].eq(20)
    ].set_index("direction")
    breadth_20 = fixed_confirm.loc[
        fixed_confirm["filter_name"].eq("P2_LOCAL_BREADTH_FIXED")
        & fixed_confirm["horizon_sessions"].eq(20)
    ].set_index("direction")
    breadth_by_day = (
        panel.loc[
            panel["eligible_features"]
            & panel["event_date"].ge(DEVELOPMENT_CUTOFF),
            ["event_date", "breadth_trend_balance_loo"],
        ]
        .groupby("event_date")["breadth_trend_balance_loo"]
        .median()
    )
    assessment["confirmation_event_counts"] = {
        "all": int(len(confirm_events)),
        "us_stock_like": int(confirm_events["asset_slice"].eq("us_stock_like").sum()),
        "us_stock_like_symbols": int(
            confirm_events.loc[confirm_events["asset_slice"].eq("us_stock_like"), "symbol"].nunique()
        ),
        "us_stock_like_complete_10": int(
            confirm_events.loc[
                confirm_events["asset_slice"].eq("us_stock_like"), "net_return_10"
            ].notna().sum()
        ),
        "us_stock_like_complete_20": int(
            confirm_events.loc[
                confirm_events["asset_slice"].eq("us_stock_like"), "net_return_20"
            ].notna().sum()
        ),
    }
    model_direction: dict[str, Any] = {}
    for model in ("LOGISTIC", "LIGHTGBM"):
        model_direction[model] = {}
        for horizon in PRIMARY_HORIZONS:
            chosen = predictions.loc[
                predictions["model"].eq(model)
                & predictions["horizon_sessions"].eq(horizon)
                & predictions["fold"].eq("CONFIRM_2026_07_08")
                & predictions["selected"]
            ]
            model_direction[model][str(horizon)] = {
                direction: {
                    "count": int(len(group)),
                    "mean": float(group[f"net_return_{horizon}"].mean()),
                }
                for direction, group in chosen.groupby("direction")
            }
    fixed_passes = []
    for strategy, horizons in assessment["fixed"].items():
        for horizon, item in horizons.items():
            directions = fixed_confirm.loc[
                fixed_confirm["filter_name"].eq(strategy)
                & fixed_confirm["horizon_sessions"].eq(int(horizon))
                & fixed_confirm["direction"].isin(["long", "short"])
            ].set_index("direction")
            both_directions_positive = (
                {"long", "short"}.issubset(directions.index)
                and directions.loc["long", "sample_count"] >= 30
                and directions.loc["short", "sample_count"] >= 30
                and directions.loc["long", "mean"] > 0
                and directions.loc["short", "mean"] > 0
            )
            if (
                item["confirmation_mean"] > 0
                and item["confirmation_count"] >= 100
                and item["positive_historical_folds"] >= 3
                and both_directions_positive
            ):
                fixed_passes.append(f"{strategy}_{horizon}")
    ml_passes = []
    for model, horizons in assessment["ml"].items():
        for horizon, item in horizons.items():
            directions = model_direction[model][horizon]
            both_directions_positive = all(
                directions.get(direction, {}).get("count", 0) >= 30
                and directions.get(direction, {}).get("mean", math.nan) > 0
                for direction in ("long", "short")
            )
            if (
                item["confirmation_mean"] > 0
                and item["confirmation_count"] >= 100
                and item["positive_historical_folds"] >= 3
                and both_directions_positive
            ):
                ml_passes.append(f"{model}_{horizon}")
    assessment["plain_language"] = {
        "overall_decision": "NO-GO",
        "market_style_filtering": "WEAKLY_SUPPORTED_BUT_NOT_STABLE_OR_UNIVERSAL",
        "fixed_rule_passes": fixed_passes,
        "ml_rule_passes": ml_passes,
        "p2_local_20_confirmation": {
            direction: {
                "count": int(local_20.loc[direction, "sample_count"]),
                "mean": float(local_20.loc[direction, "mean"]),
                "median": float(local_20.loc[direction, "median"]),
                "t_stat": float(local_20.loc[direction, "t_stat"]),
            }
            for direction in ("both", "long", "short")
        },
        "p2_local_breadth_20_confirmation": {
            direction: {
                "count": int(breadth_20.loc[direction, "sample_count"]),
                "mean": float(breadth_20.loc[direction, "mean"]),
            }
            for direction in ("both", "long", "short")
        },
        "confirmation_breadth_days": {
            "positive": int(breadth_by_day.gt(0).sum()),
            "negative": int(breadth_by_day.lt(0).sum()),
            "zero": int(breadth_by_day.eq(0).sum()),
        },
        "model_confirmation_by_direction": model_direction,
        "universal_asset_claim": "INSUFFICIENT_NON_CRYPTO_SAMPLE",
    }
    return assessment


def fmt_pct(value: Any) -> str:
    return "NA" if value is None or not np.isfinite(float(value)) else f"{float(value):.2%}"


def fmt_num(value: Any, digits: int = 2) -> str:
    return "NA" if value is None or not np.isfinite(float(value)) else f"{float(value):.{digits}f}"


def plain_table(rows: Iterable[Sequence[Any]], headers: Sequence[str]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |" for row in rows)
    return lines


def write_report(
    audit: dict[str, Any],
    fixed_stats: pd.DataFrame,
    ml_metrics: pd.DataFrame,
    account_metrics: pd.DataFrame,
    assessment: dict[str, Any],
) -> None:
    plain = assessment["plain_language"]
    local = plain["p2_local_20_confirmation"]
    breadth_days = plain["confirmation_breadth_days"]
    fixed_primary = fixed_stats.loc[
        fixed_stats["ma_period"].eq(7)
        & fixed_stats["return_metric"].eq("net_return")
        & fixed_stats["direction"].eq("both")
        & fixed_stats["scope"].eq("CONFIRMATION")
    ]
    fixed_rows = []
    for strategy in FIXED_FILTERS:
        for horizon in PRIMARY_HORIZONS:
            row = fixed_primary.loc[
                fixed_primary["filter_name"].eq(strategy)
                & fixed_primary["horizon_sessions"].eq(horizon)
            ]
            if row.empty:
                continue
            value = row.iloc[0]
            fixed_rows.append(
                (
                    strategy,
                    horizon,
                    int(value["sample_count"]),
                    fmt_pct(value["mean"]),
                    fmt_pct(value["median"]),
                    fmt_pct(value["win_rate"]),
                    fmt_num(value["t_stat"]),
                    f"[{fmt_pct(value['ci95_low'])}, {fmt_pct(value['ci95_high'])}]",
                )
            )
    ml_confirm = ml_metrics.loc[ml_metrics["fold"].eq("CONFIRM_2026_07_08")]
    ml_rows = []
    for row in ml_confirm.itertuples(index=False):
        ml_rows.append(
            (
                row.model,
                row.horizon_sessions,
                row.selected_count,
                fmt_pct(row.selected_mean),
                fmt_pct(row.selected_median),
                fmt_pct(row.selected_win_rate),
                fmt_num(row.roc_auc, 3),
                fmt_pct(row.selected_share),
            )
        )
    accounts = account_metrics.loc[account_metrics["scope"].eq("CONFIRMATION")]
    account_rows = []
    for row in accounts.itertuples(index=False):
        account_rows.append(
            (
                row.strategy,
                row.horizon_sessions,
                int(row.trade_count),
                fmt_pct(row.total_return),
                fmt_pct(row.annualized_return),
                fmt_pct(row.maximum_drawdown),
                fmt_num(row.profit_factor),
            )
        )
    counts = assessment["confirmation_event_counts"]
    lines = [
        "# BIN-1D-MA7-RC-P3 确认研究结果",
        "",
        "## 先看结论",
        "",
        "**结论：P3 是 `NO-GO`，现在不能把它写成正式交易策略。**",
        "",
        "“先看市场风格，再做突破”不是完全没用，但这轮只得到**弱支持**，没有得到稳定、跨方向、跨资产的确认。最关键的证据是：",
        "",
        f"- 冻结的本地波动规则持有 20 日总体为 {fmt_pct(local['both']['mean'])}，但它完全由做多的 {fmt_pct(local['long']['mean'])} 拉动；做空反而为 {fmt_pct(local['short']['mean'])}。10 日结果则为负。",
        f"- 全市场广度没有救回来。确认段 {breadth_days['negative']}/{breadth_days['negative'] + breadth_days['positive'] + breadth_days['zero']} 天的广度为负，加入同向广度后，20 日事件均值变成 {fmt_pct(plain['p2_local_breadth_20_confirmation']['both']['mean'])}，而且没有留下任何做多事件。",
        f"- 逻辑回归在确认段 10/20 日都亏；LightGBM 只有 20 日为正，但历史五折只在 {assessment['ml']['LIGHTGBM']['20']['positive_historical_folds']} 折为正，且确认段没有选中美股类事件，不能叫稳定或跨资产。",
        f"- 美股类合约虽然终于产生了 {counts['us_stock_like']} 个 MA7 事件，但完整 10/20 日标签只有 {counts['us_stock_like_complete_10']}/{counts['us_stock_like_complete_20']} 个，远不足以支持‘所有资产都有效’。",
        "",
        "大白话说：**波动路径确实能把一部分好突破和坏突破拉开，但‘什么环境该做多、什么环境该做空’会随年份翻转；当前固定规则和小模型都还没有学会稳定识别这种翻转。**",
        "",
        "## 确认段固定规则：扣 28 bps 往返成本后的单次事件收益",
        "",
        *plain_table(
            fixed_rows,
            ["规则", "持有", "事件", "均值", "中位数", "胜率", "t-stat", "95% CI"],
        ),
        "",
        "## 确认段小模型：训练集 80 分位阈值筛出的事件",
        "",
        *plain_table(
            ml_rows,
            ["模型", "持有", "入选", "均值", "中位数", "胜率", "AUC", "覆盖率"],
        ),
        "",
        "## 确认段账户模拟（不含 funding）",
        "",
        *plain_table(
            account_rows,
            ["规则/模型", "持有", "成交", "总收益", "年化", "最大回撤", "PF"],
        ),
        "",
        "## 样本真实性",
        "",
        f"- 15m priority union：{audit['selected_rows']:,} 根，{audit['symbol_count']} 个合约；跨源受控重叠 {audit['controlled_overlap_rows']:,} 根。",
        f"- 锁定确认段 MA7 事件：{counts['all']:,} 个。",
        f"- 其中已知美股类 Binance 合约事件：{counts['us_stock_like']:,} 个，覆盖 {counts['us_stock_like_symbols']} 个合约。资产类别只用于这一项事后审计。",
        "- 账户结果已经扣单边 10 bps 手续费和 4 bps 滑点，但没有全市场实际 funding，因此不能直接视为可实盘收益。",
        "- 确认段只有不到两个月，年化数字仅是机械换算，必须同时看交易数、总收益和历史逐年前推结果。",
        "",
        "## 文件",
        "",
        "- 固定规则统计：`artifacts/binance_1d_ma7_rc_p3_fixed_rule_stats.csv`",
        "- 机器学习逐折统计：`artifacts/binance_1d_ma7_rc_p3_ml_metrics.csv`",
        "- 账户统计：`artifacts/binance_1d_ma7_rc_p3_account_metrics.csv`",
        "- 全部摘要：`artifacts/binance_1d_ma7_rc_p3_summary.json`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_csv(temporary, index=False)
    os.replace(temporary, path)


def write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, path)


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def artifact_manifest(paths: Iterable[Path]) -> dict[str, Any]:
    rows = []
    for path in paths:
        rows.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "study_id": "BIN-1D-MA7-RC-P3",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "artifacts": rows,
    }


def main() -> None:
    args = parse_args()
    if not args.run:
        raise RuntimeError("pass --run to acknowledge the locked confirmation reveal")
    config = validate_frozen_config()
    prepare_outputs(args.force)
    connection = duckdb.connect()
    connection.execute("SET TimeZone='UTC'")
    print("P3 input audit...", flush=True)
    audit = input_audit(connection)
    if args.reuse_daily_panel and DAILY_PANEL_PATH.exists():
        panel = pd.read_parquet(DAILY_PANEL_PATH)
        if OUTPUTS["audit"].exists():
            prior_audit = json.loads(OUTPUTS["audit"].read_text(encoding="utf-8"))
            daily_quality = prior_audit.get("daily", {})
        else:
            daily_quality = {}
        daily_quality = {
            **daily_quality,
            "reused_daily_panel": True,
            "panel_rows": len(panel),
        }
    else:
        print("P3 aggregate 15m -> complete daily bars...", flush=True)
        daily, daily_quality = load_daily_bars(connection)
        print("P3 feature panel and leave-one-out breadth...", flush=True)
        panel = prepare_feature_panel(daily)
        write_parquet(panel, DAILY_PANEL_PATH)
    audit["daily"] = daily_quality
    write_json(audit, OUTPUTS["audit"])
    print(f"P3 build events from panel rows={len(panel):,}...", flush=True)
    events = build_events(panel)
    write_parquet(events, OUTPUTS["events"])
    print(f"P3 fixed rules events={len(events):,}...", flush=True)
    fixed_stats = build_fixed_stats(events)
    fixed_frequency = build_fixed_frequency(events)
    fixed_robustness = build_fixed_robustness(events)
    write_csv(fixed_stats, OUTPUTS["fixed_stats"])
    write_csv(fixed_frequency, OUTPUTS["fixed_frequency"])
    write_csv(fixed_robustness, OUTPUTS["fixed_robustness"])
    print("P3 rolling logistic and LightGBM...", flush=True)
    predictions, ml_metrics, ml_quintiles, ml_importance = train_models(events)
    write_parquet(predictions, OUTPUTS["ml_predictions"])
    write_csv(ml_metrics, OUTPUTS["ml_metrics"])
    write_csv(ml_quintiles, OUTPUTS["ml_quintiles"])
    write_csv(ml_importance, OUTPUTS["ml_importance"])
    print("P3 account simulations...", flush=True)
    account_metrics, account_equity, account_trades = build_accounts(
        events, predictions, panel
    )
    write_csv(account_metrics, OUTPUTS["account_metrics"])
    write_csv(account_equity, OUTPUTS["account_equity"])
    write_parquet(account_trades, OUTPUTS["account_trades"])
    assessment = pass_assessment(
        fixed_stats, ml_metrics, events, predictions, panel
    )
    summary = {
        "study_id": config["study_id"],
        "status": "completed_confirmatory_diagnostic_not_promoted_not_live_ready",
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "data_quality": audit,
        "event_counts": {
            "all_ma_periods": len(events),
            "ma7": int(events["ma_period"].eq(7).sum()),
            "ma7_symbols": int(events.loc[events["ma_period"].eq(7), "symbol"].nunique()),
            "ma7_confirmation": int(
                (events["ma_period"].eq(7) & events["event_date"].ge(DEVELOPMENT_CUTOFF)).sum()
            ),
        },
        "assessment": assessment,
        "costs": {
            "fee_bps_per_side": 10,
            "slippage_bps_per_side": 4,
            "round_trip_bps": 28,
            "funding_included": False,
        },
        "decision_boundary": config["decision_boundary"],
    }
    write_json(summary, OUTPUTS["summary"])
    write_report(audit, fixed_stats, ml_metrics, account_metrics, assessment)
    manifest_paths = [
        CONFIG_PATH,
        OUTPUTS["audit"],
        OUTPUTS["events"],
        OUTPUTS["fixed_stats"],
        OUTPUTS["fixed_frequency"],
        OUTPUTS["fixed_robustness"],
        OUTPUTS["ml_predictions"],
        OUTPUTS["ml_metrics"],
        OUTPUTS["ml_quintiles"],
        OUTPUTS["ml_importance"],
        OUTPUTS["account_metrics"],
        OUTPUTS["account_equity"],
        OUTPUTS["account_trades"],
        OUTPUTS["summary"],
        REPORT_PATH,
    ]
    write_json(artifact_manifest(manifest_paths), OUTPUTS["manifest"])
    print(f"P3 complete -> {REPORT_PATH.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    main()
