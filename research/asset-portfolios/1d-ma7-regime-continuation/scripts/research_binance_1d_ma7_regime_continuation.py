from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

import duckdb
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation"
CONFIG_PATH = FAMILY_DIR / "configs/binance-1d-ma7-regime-continuation-p0.json"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FIGURE_DIR = FAMILY_DIR / "figures"
INPUT_GLOB = (
    ROOT
    / "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
    / "**/*.parquet"
)
EXPECTED_CONFIG_SHA256 = (
    "15bc78f14bf3f7026440d778d849252e8ff0d1af1aa80d3d064bd569e850a84b"
)
SOURCES = ("binance_vision_kline_monthly", "binance_futures_kline_api")
CUTOFF = pd.Timestamp("2026-07-01T00:00:00Z")
HORIZONS = (1, 3, 5, 10, 20, 40)
MA_PERIODS = (5, 7, 10)
REGIME_VARIABLES = {
    "normalized_slope": "slope_q",
    "er20": "er_q",
    "rv_percentile": "rv_q",
}
RETURN_METRICS = ("raw_return", "atr_return")
RELIABLE_MIN_EVENTS = 100
RELIABLE_MIN_SYMBOLS = 10
RELIABLE_MIN_DATES = 30
TEMPORAL_SPLIT = pd.Timestamp("2024-01-01T00:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen BIN-1D-MA7-RC-P0 historical regime event study."
        )
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required acknowledgement that the frozen historical outcomes may be read.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace previously generated P0 artifacts.",
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
    if config.get("study_id") != "BIN-1D-MA7-RC-P0":
        raise RuntimeError("unexpected study_id in frozen config")
    return config


def prepare_output_directories(*, force: bool) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    sentinel = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_summary.json"
    if sentinel.exists() and not force:
        raise RuntimeError(
            "P0 artifacts already exist; pass --force to reproduce the frozen run"
        )


def input_audit(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    query = """
        SELECT
            count(*) AS raw_union_rows,
            count(DISTINCT (symbol, ts)) AS selected_input_rows,
            count(DISTINCT symbol) AS symbols,
            min(ts) AS start_ts,
            max(ts) AS end_ts,
            count(*) - count(DISTINCT (symbol, ts)) AS cross_source_overlap_rows,
            count(*) - count(DISTINCT (source, symbol, ts)) AS within_source_duplicate_rows,
            count(*) FILTER (
                WHERE symbol IS NULL
                   OR ts IS NULL
                   OR open IS NULL
                   OR high IS NULL
                   OR low IS NULL
                   OR close IS NULL
                   OR volume IS NULL
                   OR quote_volume IS NULL
                   OR trade_count IS NULL
                   OR is_closed IS NULL
            ) AS critical_null_rows,
            count(*) FILTER (WHERE NOT is_closed) AS open_bar_rows,
            count(*) FILTER (
                WHERE open <= 0
                   OR high <= 0
                   OR low <= 0
                   OR close <= 0
                   OR volume < 0
                   OR quote_volume < 0
                   OR trade_count < 0
                   OR high < greatest(open, close, low)
                   OR low > least(open, close, high)
            ) AS invalid_market_rows
        FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
        WHERE source IN (?, ?) AND ts < ?
    """
    row = connection.execute(
        query,
        [str(INPUT_GLOB), *SOURCES, CUTOFF.to_pydatetime()],
    ).fetch_df().iloc[0]
    audit = {
        "sources": list(SOURCES),
        "source_priority": ["binance_vision_kline_monthly", "binance_futures_kline_api"],
        "cutoff_exclusive_utc": CUTOFF.isoformat(),
        "raw_union_rows": int(row["raw_union_rows"]),
        "input_rows": int(row["selected_input_rows"]),
        "symbols": int(row["symbols"]),
        "start_ts": pd.Timestamp(row["start_ts"]).isoformat(),
        "end_ts": pd.Timestamp(row["end_ts"]).isoformat(),
        "cross_source_overlap_rows": int(row["cross_source_overlap_rows"]),
        "within_source_duplicate_rows": int(row["within_source_duplicate_rows"]),
        "selected_union_duplicate_rows": 0,
        "critical_null_rows": int(row["critical_null_rows"]),
        "open_bar_rows": int(row["open_bar_rows"]),
        "invalid_market_rows": int(row["invalid_market_rows"]),
    }
    blockers = [
        key
        for key in (
            "within_source_duplicate_rows",
            "selected_union_duplicate_rows",
            "critical_null_rows",
            "open_bar_rows",
            "invalid_market_rows",
        )
        if audit[key] != 0
    ]
    if blockers:
        raise RuntimeError(f"input data-quality blockers: {blockers}")
    return audit


def load_daily_bars(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    query = """
        WITH source_rows AS (
            SELECT
                ts,
                symbol,
                base_asset,
                quote_asset,
                open,
                high,
                low,
                close,
                volume,
                quote_volume,
                trade_count,
                is_closed
            FROM read_parquet(?, hive_partitioning = false, union_by_name = true)
            WHERE source IN (?, ?)
              AND ts < ?
              AND symbol IS NOT NULL
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
            SELECT
                symbol,
                min(ts) AS first_observed_ts,
                max(ts) AS last_observed_ts,
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
        SELECT
            daily.*,
            listing.first_observed_ts,
            listing.last_observed_ts,
            listing.input_rows
        FROM daily
        JOIN listing USING (symbol)
        ORDER BY symbol, event_date
    """
    frame = connection.execute(
        query,
        [str(INPUT_GLOB), *SOURCES, CUTOFF.to_pydatetime()],
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

    inventory_rows: list[dict[str, Any]] = []
    for symbol, group in frame.groupby("symbol", sort=True):
        complete = group.loc[group["is_complete_day"]]
        if complete.empty:
            first_complete = pd.NaT
            last_complete = pd.NaT
            missing_complete_days = 0
        else:
            first_complete = complete["event_date"].min()
            last_complete = complete["event_date"].max()
            expected_days = int((last_complete - first_complete).days) + 1
            missing_complete_days = expected_days - int(len(complete))
        first_row = group.iloc[0]
        inventory_rows.append(
            {
                "symbol": symbol,
                "base_asset": first_row["base_asset"],
                "quote_asset": first_row["quote_asset"],
                "first_observed_ts": first_row["first_observed_ts"],
                "last_observed_ts": first_row["last_observed_ts"],
                "input_15m_rows": int(first_row["input_rows"]),
                "daily_groups": int(len(group)),
                "complete_daily_bars": int(len(complete)),
                "partial_daily_groups": int((~group["is_complete_day"]).sum()),
                "first_complete_day": first_complete,
                "last_complete_day": last_complete,
                "missing_complete_days_inside_span": int(missing_complete_days),
                "has_120_complete_days": bool(len(complete) >= 120),
                "left_truncated_at_archive_start": bool(
                    first_row["first_observed_ts"]
                    <= pd.Timestamp("2020-01-01T00:15:00Z")
                ),
            }
        )
    inventory = pd.DataFrame(inventory_rows)
    return frame, inventory


def rolling_percentile_current(
    values: Sequence[float] | np.ndarray,
    window: int,
) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    output = np.full(len(array), np.nan, dtype=float)
    if len(array) < window:
        return output
    windows = np.lib.stride_tricks.sliding_window_view(array, window)
    valid = np.isfinite(windows).all(axis=1)
    current = windows[:, -1]
    ranks = np.full(len(windows), np.nan, dtype=float)
    ranks[valid] = (windows[valid] <= current[valid, None]).mean(axis=1)
    output[window - 1 :] = ranks
    return output


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
    block["atr14"] = true_range.rolling(14, min_periods=14).mean()
    block["sma30"] = close.rolling(30, min_periods=30).mean()
    block["normalized_slope"] = (
        block["sma30"] - block["sma30"].shift(1)
    ) / block["atr14"]
    absolute_path = close.diff().abs().rolling(20, min_periods=20).sum()
    block["er20"] = (close - close.shift(20)).abs() / absolute_path.replace(0, np.nan)
    log_return = np.log(close).diff()
    block["rv20"] = (
        log_return.rolling(20, min_periods=20).std(ddof=1) * math.sqrt(365.0)
    )
    block["rv_percentile"] = rolling_percentile_current(
        block["rv20"].to_numpy(), 252
    )
    block["adv30_median"] = (
        block["quote_volume"].astype(float).rolling(30, min_periods=30).median()
    )
    block["sma200"] = close.rolling(200, min_periods=200).mean()
    block["return_30d"] = close / close.shift(30) - 1.0
    for period in MA_PERIODS:
        block[f"sma{period}"] = close.rolling(period, min_periods=period).mean()
    for horizon in HORIZONS:
        block[f"future_close_{horizon}"] = close.shift(-horizon)
    return block


def prepare_feature_panel(daily: pd.DataFrame) -> pd.DataFrame:
    panel = daily.loc[daily["is_complete_day"]].copy()
    panel = panel.sort_values(["symbol", "event_date"]).reset_index(drop=True)
    prior_date = panel.groupby("symbol", sort=False)["event_date"].shift(1)
    panel["new_block"] = prior_date.isna() | (
        (panel["event_date"] - prior_date) != pd.Timedelta(days=1)
    )
    panel["block_id"] = (
        panel.groupby("symbol", sort=False)["new_block"].cumsum().astype(int)
    )
    featured = [
        _feature_block(group)
        for _, group in panel.groupby(["symbol", "block_id"], sort=False)
    ]
    panel = pd.concat(featured, ignore_index=True)
    panel["listing_age_days"] = np.floor(
        (panel["event_date"] - panel["first_observed_ts"]).dt.total_seconds()
        / 86_400.0
    ).astype(int)
    regime_columns = ["normalized_slope", "er20", "rv_percentile", "atr14"]
    finite_regime = np.isfinite(panel[regime_columns].to_numpy()).all(axis=1)
    panel["eligible_regime"] = finite_regime & panel["listing_age_days"].ge(120)

    btc = panel.loc[
        panel["symbol"].eq("BTC/USDT:USDT"),
        ["event_date", "close", "sma200", "return_30d"],
    ].copy()
    if btc.empty:
        raise RuntimeError("BTC/USDT:USDT is required for frozen market phases")
    btc["market_phase"] = np.select(
        [
            btc["close"].gt(btc["sma200"]) & btc["return_30d"].gt(0),
            btc["close"].lt(btc["sma200"]) & btc["return_30d"].lt(0),
        ],
        ["bull", "bear"],
        default="transition",
    )
    panel = panel.merge(
        btc[["event_date", "market_phase"]],
        on="event_date",
        how="left",
        validate="many_to_one",
    )
    eligible_index = panel.index[panel["eligible_regime"]]
    panel.loc[eligible_index, "liquidity_rank"] = (
        panel.loc[eligible_index]
        .groupby("event_date")["adv30_median"]
        .rank(method="first", ascending=False)
    )
    panel["liquidity_segment"] = np.where(
        panel["liquidity_rank"].le(20), "major", "long_tail"
    )
    panel.loc[panel["liquidity_rank"].isna(), "liquidity_segment"] = "unavailable"
    panel["calendar_year"] = panel["event_date"].dt.year.astype(int)
    return panel


def quantile_edges(values: pd.Series, bins: int = 5) -> list[float]:
    clean = values[np.isfinite(values.to_numpy(dtype=float))].to_numpy(dtype=float)
    if len(clean) == 0:
        raise RuntimeError("cannot calculate quantiles from an empty series")
    edges = np.quantile(clean, np.linspace(0.0, 1.0, bins + 1), method="linear")
    if np.any(np.diff(edges) <= 0):
        raise RuntimeError(f"non-unique quintile edges: {edges.tolist()}")
    return [float(value) for value in edges]


def assign_quintile(values: pd.Series, edges: Sequence[float]) -> pd.Series:
    internal = np.asarray(edges[1:-1], dtype=float)
    array = values.to_numpy(dtype=float)
    result = np.full(len(array), np.nan, dtype=float)
    valid = np.isfinite(array)
    result[valid] = np.searchsorted(internal, array[valid], side="left") + 1
    return pd.Series(result, index=values.index, dtype="Int64")


def freeze_regime_bins(panel: pd.DataFrame) -> dict[str, list[float]]:
    eligible = panel.loc[panel["eligible_regime"]]
    edges = {
        "normalized_slope": quantile_edges(eligible["normalized_slope"]),
        "er20": quantile_edges(eligible["er20"]),
        "rv_percentile": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    }
    panel["slope_q"] = assign_quintile(panel["normalized_slope"], edges["normalized_slope"])
    panel["er_q"] = assign_quintile(panel["er20"], edges["er20"])
    panel["rv_q"] = assign_quintile(panel["rv_percentile"], edges["rv_percentile"])
    return edges


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    event_frames: list[pd.DataFrame] = []
    identity_columns = [
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "close",
        "atr14",
        "normalized_slope",
        "er20",
        "rv20",
        "rv_percentile",
        "slope_q",
        "er_q",
        "rv_q",
        "listing_age_days",
        "adv30_median",
        "liquidity_rank",
        "liquidity_segment",
        "market_phase",
        "calendar_year",
    ]
    grouped = panel.groupby(["symbol", "block_id"], sort=False)
    for period in MA_PERIODS:
        previous_close = grouped["close"].shift(1)
        previous_ma = grouped[f"sma{period}"].shift(1)
        long_trigger = (
            previous_close.le(previous_ma)
            & panel["close"].gt(panel[f"sma{period}"])
        )
        short_trigger = (
            previous_close.ge(previous_ma)
            & panel["close"].lt(panel[f"sma{period}"])
        )
        for direction, trigger, sign in (
            ("long", long_trigger, 1.0),
            ("short", short_trigger, -1.0),
        ):
            mask = trigger & panel["eligible_regime"]
            events = panel.loc[mask, identity_columns].copy()
            events["ma_period"] = period
            events["direction"] = direction
            events["direction_sign"] = sign
            events["trigger_ma"] = panel.loc[mask, f"sma{period}"].to_numpy()
            for horizon in HORIZONS:
                future = panel.loc[mask, f"future_close_{horizon}"].to_numpy(dtype=float)
                entry = events["close"].to_numpy(dtype=float)
                atr = events["atr14"].to_numpy(dtype=float)
                events[f"raw_return_{horizon}"] = sign * (future / entry - 1.0)
                events[f"atr_return_{horizon}"] = sign * (future - entry) / atr
            events["event_id"] = (
                "MA"
                + str(period)
                + "|"
                + direction
                + "|"
                + events["symbol"].astype(str)
                + "|"
                + events["event_date"].dt.strftime("%Y-%m-%d")
            )
            event_frames.append(events)
    result = pd.concat(event_frames, ignore_index=True)
    if result["event_id"].duplicated().any():
        raise RuntimeError("duplicate event identifiers detected")
    return result.sort_values(["ma_period", "event_date", "symbol"]).reset_index(drop=True)


def _cluster_variance(residual: np.ndarray, labels: pd.Series) -> tuple[float, int]:
    codes, uniques = pd.factorize(labels, sort=False)
    groups = len(uniques)
    if groups < 2:
        return math.nan, groups
    sums = np.bincount(codes, weights=residual)
    variance = (groups / (groups - 1.0)) * float(np.dot(sums, sums)) / len(residual) ** 2
    return variance, groups


def infer_mean(
    values: pd.Series,
    symbols: pd.Series,
    dates: pd.Series,
) -> dict[str, Any]:
    array = values.to_numpy(dtype=float)
    valid = np.isfinite(array)
    array = array[valid]
    symbol_values = symbols.loc[valid]
    date_values = dates.loc[valid]
    count = len(array)
    if count == 0:
        return {
            "sample_count": 0,
            "symbol_count": 0,
            "event_date_count": 0,
            "mean": math.nan,
            "median": math.nan,
            "win_rate": math.nan,
            "cluster_se": math.nan,
            "t_stat": math.nan,
            "ci95_low": math.nan,
            "ci95_high": math.nan,
            "p_value": math.nan,
            "cluster_variance_fallback": False,
        }
    mean = float(np.mean(array))
    residual = array - mean
    symbol_variance, symbol_count = _cluster_variance(residual, symbol_values)
    date_variance, date_count = _cluster_variance(residual, date_values)
    if count < 2 or not np.isfinite(symbol_variance) or not np.isfinite(date_variance):
        standard_error = math.nan
        fallback = False
    else:
        observation_variance = (
            count / (count - 1.0) * float(np.dot(residual, residual)) / count**2
        )
        combined = symbol_variance + date_variance - observation_variance
        fallback = combined <= 0
        if fallback:
            combined = max(symbol_variance, date_variance)
        standard_error = math.sqrt(max(combined, 0.0))
    if standard_error and np.isfinite(standard_error) and standard_error > 0:
        t_stat = mean / standard_error
        p_value = math.erfc(abs(t_stat) / math.sqrt(2.0))
        ci_low = mean - 1.959963984540054 * standard_error
        ci_high = mean + 1.959963984540054 * standard_error
    else:
        t_stat = math.nan
        p_value = math.nan
        ci_low = math.nan
        ci_high = math.nan
    return {
        "sample_count": int(count),
        "symbol_count": int(symbol_count),
        "event_date_count": int(date_count),
        "mean": mean,
        "median": float(np.median(array)),
        "win_rate": float(np.mean(array > 0)),
        "cluster_se": standard_error,
        "t_stat": t_stat,
        "ci95_low": ci_low,
        "ci95_high": ci_high,
        "p_value": p_value,
        "cluster_variance_fallback": bool(fallback),
    }


def summarize_groups(
    events: pd.DataFrame,
    group_columns: Sequence[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for metric in RETURN_METRICS:
            value_column = f"{metric}_{horizon}"
            valid_events = events.loc[np.isfinite(events[value_column])]
            for keys, group in valid_events.groupby(
                list(group_columns), dropna=False, sort=True
            ):
                key_values = keys if isinstance(keys, tuple) else (keys,)
                identity = dict(zip(group_columns, key_values, strict=True))
                stats = infer_mean(
                    group[value_column], group["symbol"], group["event_date"]
                )
                rows.append(
                    {
                        **identity,
                        "horizon_days": horizon,
                        "return_metric": metric,
                        **stats,
                    }
                )
    return pd.DataFrame(rows)


def benjamini_hochberg(values: pd.Series) -> pd.Series:
    array = values.to_numpy(dtype=float)
    output = np.full(len(array), np.nan, dtype=float)
    valid_positions = np.flatnonzero(np.isfinite(array))
    if len(valid_positions) == 0:
        return pd.Series(output, index=values.index)
    order = valid_positions[np.argsort(array[valid_positions])]
    count = len(order)
    adjusted = array[order] * count / np.arange(1, count + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    output[order] = np.minimum(adjusted, 1.0)
    return pd.Series(output, index=values.index)


def build_single_variable_stats(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)]
    outputs: list[pd.DataFrame] = []
    for variable, quintile_column in REGIME_VARIABLES.items():
        stats = summarize_groups(primary, ["direction", quintile_column])
        stats = stats.rename(columns={quintile_column: "quintile"})
        stats["variable"] = variable
        outputs.append(stats)
    result = pd.concat(outputs, ignore_index=True)
    return result.sort_values(
        ["direction", "variable", "horizon_days", "return_metric", "quintile"]
    ).reset_index(drop=True)


def build_three_way_stats(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)]
    result = summarize_groups(
        primary,
        ["direction", "slope_q", "er_q", "rv_q"],
    )
    result["reliable_cell"] = (
        result["sample_count"].ge(RELIABLE_MIN_EVENTS)
        & result["symbol_count"].ge(RELIABLE_MIN_SYMBOLS)
        & result["event_date_count"].ge(RELIABLE_MIN_DATES)
    )
    result["q_value_bh"] = result.groupby(
        ["direction", "horizon_days", "return_metric"], group_keys=False
    )["p_value"].transform(benjamini_hochberg)
    return result.sort_values(
        [
            "direction",
            "horizon_days",
            "return_metric",
            "slope_q",
            "er_q",
            "rv_q",
        ]
    ).reset_index(drop=True)


def _slice_variable_stats(
    events: pd.DataFrame,
    *,
    slice_type: str,
    slice_column: str,
    include_ma_period: bool = False,
) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for variable, quintile_column in REGIME_VARIABLES.items():
        groups = ["direction", slice_column, quintile_column]
        if include_ma_period and "ma_period" not in groups:
            groups.insert(1, "ma_period")
        stats = summarize_groups(events, groups)
        stats = stats.rename(
            columns={quintile_column: "quintile", slice_column: "slice_value"}
        )
        stats["slice_type"] = slice_type
        stats["variable"] = variable
        outputs.append(stats)
    return pd.concat(outputs, ignore_index=True)


def build_robustness_stats(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)]
    outputs = [
        _slice_variable_stats(
            primary,
            slice_type="calendar_year",
            slice_column="calendar_year",
        ),
        _slice_variable_stats(
            primary.loc[primary["market_phase"].notna()],
            slice_type="btc_market_phase",
            slice_column="market_phase",
        ),
        _slice_variable_stats(
            primary.loc[primary["liquidity_segment"].isin(["major", "long_tail"])],
            slice_type="liquidity_segment",
            slice_column="liquidity_segment",
        ),
        _slice_variable_stats(
            events,
            slice_type="ma_neighborhood",
            slice_column="ma_period",
            include_ma_period=False,
        ),
    ]
    result = pd.concat(outputs, ignore_index=True)
    return result.sort_values(
        [
            "slice_type",
            "slice_value",
            "direction",
            "variable",
            "horizon_days",
            "return_metric",
            "quintile",
        ]
    ).reset_index(drop=True)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_series = pd.Series(left, dtype=float)
    right_series = pd.Series(right, dtype=float)
    valid = left_series.notna() & right_series.notna()
    if valid.sum() < 3:
        return math.nan
    left_rank = left_series.loc[valid].rank(method="average").to_numpy()
    right_rank = right_series.loc[valid].rank(method="average").to_numpy()
    if np.std(left_rank) == 0 or np.std(right_rank) == 0:
        return math.nan
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def build_monotonicity_stats(single: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    groups = ["direction", "variable", "horizon_days", "return_metric"]
    for keys, group in single.groupby(groups, sort=True):
        direction, variable, horizon, metric = keys
        ordered = group.sort_values("quintile")
        if set(ordered["quintile"].astype(int)) != {1, 2, 3, 4, 5}:
            continue
        if variable == "normalized_slope" and direction == "short":
            aligned = ordered.sort_values("quintile", ascending=False)
        else:
            aligned = ordered.sort_values("quintile")
        means = aligned["mean"].to_numpy(dtype=float)
        rows.append(
            {
                "direction": direction,
                "variable": variable,
                "horizon_days": int(horizon),
                "return_metric": metric,
                "aligned_spearman": _spearman(range(1, 6), means),
                "adjacent_consistency": float(np.mean(np.diff(means) >= 0)),
                "aligned_extreme_spread": float(means[-1] - means[0]),
                "best_aligned_quintile": int(aligned.iloc[-1]["quintile"]),
                "worst_aligned_quintile": int(aligned.iloc[0]["quintile"]),
                "positive_mean_quintiles": int((ordered["mean"] > 0).sum()),
                "min_quintile_events": int(ordered["sample_count"].min()),
            }
        )
    return pd.DataFrame(rows).sort_values(groups).reset_index(drop=True)


def _surface_mean(
    events: pd.DataFrame,
    *,
    ma_period: int,
    date_start: pd.Timestamp | None = None,
    date_end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    sample = events.loc[events["ma_period"].eq(ma_period)].copy()
    if date_start is not None:
        sample = sample.loc[sample["event_date"].ge(date_start)]
    if date_end is not None:
        sample = sample.loc[sample["event_date"].lt(date_end)]
    rows: list[pd.DataFrame] = []
    cell_keys = ["direction", "slope_q", "er_q", "rv_q"]
    for horizon in HORIZONS:
        for metric in RETURN_METRICS:
            value_column = f"{metric}_{horizon}"
            valid = sample.loc[np.isfinite(sample[value_column])]
            summary = (
                valid.groupby(cell_keys, observed=True)[value_column]
                .agg(sample_count="count", mean="mean")
                .reset_index()
            )
            summary["horizon_days"] = horizon
            summary["return_metric"] = metric
            rows.append(summary)
    return pd.concat(rows, ignore_index=True)


def _surface_rank_correlation(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    direction: str,
    horizon: int,
    metric: str,
    minimum_count: int,
) -> tuple[float, int]:
    keys = ["slope_q", "er_q", "rv_q"]
    left_slice = left.loc[
        left["direction"].eq(direction)
        & left["horizon_days"].eq(horizon)
        & left["return_metric"].eq(metric)
        & left["sample_count"].ge(minimum_count),
        keys + ["mean"],
    ].rename(columns={"mean": "left_mean"})
    right_slice = right.loc[
        right["direction"].eq(direction)
        & right["horizon_days"].eq(horizon)
        & right["return_metric"].eq(metric)
        & right["sample_count"].ge(minimum_count),
        keys + ["mean"],
    ].rename(columns={"mean": "right_mean"})
    merged = left_slice.merge(right_slice, on=keys, how="inner")
    return _spearman(merged["left_mean"], merged["right_mean"]), int(len(merged))


def build_surface_diagnostics(
    events: pd.DataFrame,
    three_way: pd.DataFrame,
) -> pd.DataFrame:
    pre = _surface_mean(events, ma_period=7, date_end=TEMPORAL_SPLIT)
    post = _surface_mean(events, ma_period=7, date_start=TEMPORAL_SPLIT)
    ma5 = _surface_mean(events, ma_period=5)
    ma7 = _surface_mean(events, ma_period=7)
    ma10 = _surface_mean(events, ma_period=10)
    rows: list[dict[str, Any]] = []
    for direction in ("long", "short"):
        for horizon in HORIZONS:
            for metric in RETURN_METRICS:
                surface = three_way.loc[
                    three_way["direction"].eq(direction)
                    & three_way["horizon_days"].eq(horizon)
                    & three_way["return_metric"].eq(metric)
                    & three_way["reliable_cell"]
                ].copy()
                cell_values = {
                    (int(row.slope_q), int(row.er_q), int(row.rv_q)): float(row.mean)
                    for row in surface.itertuples()
                }
                neighbor_differences: list[float] = []
                for cell, value in cell_values.items():
                    for axis in range(3):
                        neighbor = list(cell)
                        neighbor[axis] += 1
                        neighbor_tuple = tuple(neighbor)
                        if neighbor_tuple in cell_values:
                            neighbor_differences.append(
                                abs(value - cell_values[neighbor_tuple])
                            )
                cell_standard_deviation = (
                    float(np.std(list(cell_values.values()), ddof=1))
                    if len(cell_values) > 1
                    else math.nan
                )
                neighbor_roughness = (
                    float(np.mean(neighbor_differences))
                    if neighbor_differences
                    else math.nan
                )
                normalized_roughness = (
                    neighbor_roughness / cell_standard_deviation
                    if cell_standard_deviation
                    and np.isfinite(cell_standard_deviation)
                    and cell_standard_deviation > 0
                    else math.nan
                )
                temporal_corr, temporal_cells = _surface_rank_correlation(
                    pre,
                    post,
                    direction=direction,
                    horizon=horizon,
                    metric=metric,
                    minimum_count=50,
                )
                ma5_corr, ma5_cells = _surface_rank_correlation(
                    ma5,
                    ma7,
                    direction=direction,
                    horizon=horizon,
                    metric=metric,
                    minimum_count=100,
                )
                ma10_corr, ma10_cells = _surface_rank_correlation(
                    ma10,
                    ma7,
                    direction=direction,
                    horizon=horizon,
                    metric=metric,
                    minimum_count=100,
                )
                full_cells = three_way.loc[
                    three_way["direction"].eq(direction)
                    & three_way["horizon_days"].eq(horizon)
                    & three_way["return_metric"].eq(metric)
                ]
                rows.append(
                    {
                        "direction": direction,
                        "horizon_days": horizon,
                        "return_metric": metric,
                        "populated_cells": int(len(full_cells)),
                        "reliable_cells": int(len(surface)),
                        "reliable_cell_fraction": float(len(surface) / 125.0),
                        "fdr_significant_reliable_cells": int(
                            (surface["q_value_bh"] <= 0.05).sum()
                        ),
                        "cell_standard_deviation": cell_standard_deviation,
                        "neighbor_pairs": int(len(neighbor_differences)),
                        "neighbor_absolute_roughness": neighbor_roughness,
                        "normalized_neighbor_roughness": normalized_roughness,
                        "pre2024_post2024_spearman": temporal_corr,
                        "pre2024_post2024_common_cells": temporal_cells,
                        "ma5_ma7_spearman": ma5_corr,
                        "ma5_ma7_common_cells": ma5_cells,
                        "ma10_ma7_spearman": ma10_corr,
                        "ma10_ma7_common_cells": ma10_cells,
                    }
                )
    return pd.DataFrame(rows)


def build_unconditional_stats(events: pd.DataFrame) -> pd.DataFrame:
    primary = events.loc[events["ma_period"].eq(7)]
    return summarize_groups(primary, ["direction"])


def _json_records(frame: pd.DataFrame, columns: Iterable[str]) -> list[dict[str, Any]]:
    selected = frame.loc[:, list(columns)].copy()
    selected = selected.replace({np.nan: None, np.inf: None, -np.inf: None})
    return selected.to_dict(orient="records")


def _svg_header(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f5ef"/>',
        '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#1f2a2a}.axis{stroke:#8b918d;stroke-width:1}.zero{stroke:#4b5552;stroke-width:1;stroke-dasharray:4 4}.grid{stroke:#d8d6cf;stroke-width:1}.panel{fill:#fffdf8;stroke:#cbc8be;stroke-width:1}</style>',
        f'<text x="40" y="38" font-size="24" font-weight="700">{html.escape(title)}</text>',
    ]


def write_single_variable_svg(single: pd.DataFrame) -> Path:
    width, height = 1500, 920
    svg = _svg_header(
        width,
        height,
        "MA7 regime marginal expectancy — raw close-to-close return",
    )
    colors = {
        1: "#5e81ac",
        3: "#4c9f70",
        5: "#d08770",
        10: "#b48ead",
        20: "#bf616a",
        40: "#2e3440",
    }
    variables = list(REGIME_VARIABLES)
    for row_index, direction in enumerate(("long", "short")):
        for column_index, variable in enumerate(variables):
            x0 = 45 + column_index * 485
            y0 = 75 + row_index * 405
            panel_width, panel_height = 450, 360
            plot_left, plot_top = x0 + 55, y0 + 45
            plot_width, plot_height = 360, 250
            svg.append(
                f'<rect class="panel" x="{x0}" y="{y0}" width="{panel_width}" height="{panel_height}" rx="4"/>'
            )
            svg.append(
                f'<text x="{x0 + 18}" y="{y0 + 27}" font-size="17" font-weight="700">{direction.upper()} · {html.escape(variable)}</text>'
            )
            data = single.loc[
                single["direction"].eq(direction)
                & single["variable"].eq(variable)
                & single["return_metric"].eq("raw_return")
            ]
            values = data["mean"].to_numpy(dtype=float)
            limit = max(0.002, float(np.nanmax(np.abs(values))) * 1.15)
            for quintile in range(1, 6):
                x = plot_left + (quintile - 1) * plot_width / 4
                svg.append(
                    f'<line class="grid" x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_top + plot_height}"/>'
                )
                svg.append(
                    f'<text x="{x:.1f}" y="{plot_top + plot_height + 22}" font-size="12" text-anchor="middle">Q{quintile}</text>'
                )
            zero_y = plot_top + plot_height / 2
            svg.append(
                f'<line class="zero" x1="{plot_left}" y1="{zero_y:.1f}" x2="{plot_left + plot_width}" y2="{zero_y:.1f}"/>'
            )
            svg.append(
                f'<text x="{plot_left - 8}" y="{plot_top + 5}" font-size="11" text-anchor="end">+{limit * 100:.1f}%</text>'
            )
            svg.append(
                f'<text x="{plot_left - 8}" y="{plot_top + plot_height}" font-size="11" text-anchor="end">-{limit * 100:.1f}%</text>'
            )
            for horizon in HORIZONS:
                line = data.loc[data["horizon_days"].eq(horizon)].sort_values("quintile")
                points: list[str] = []
                for item in line.itertuples():
                    x = plot_left + (int(item.quintile) - 1) * plot_width / 4
                    y = plot_top + (limit - float(item.mean)) / (2 * limit) * plot_height
                    points.append(f"{x:.1f},{y:.1f}")
                    svg.append(
                        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{colors[horizon]}"/>'
                    )
                if len(points) == 5:
                    svg.append(
                        f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[horizon]}" stroke-width="2"/>'
                    )
            legend_y = y0 + 333
            for index, horizon in enumerate(HORIZONS):
                legend_x = x0 + 45 + index * 64
                svg.append(
                    f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 15}" y2="{legend_y}" stroke="{colors[horizon]}" stroke-width="3"/>'
                )
                svg.append(
                    f'<text x="{legend_x + 19}" y="{legend_y + 4}" font-size="10">{horizon}D</text>'
                )
    svg.append("</svg>")
    path = FIGURE_DIR / "binance_1d_ma7_rc_p0_single_variable_expectancy.svg"
    path.write_text("\n".join(svg), encoding="utf-8")
    return path


def _heat_color(value: float, scale: float) -> str:
    intensity = min(abs(value) / scale, 1.0) if scale > 0 else 0.0
    neutral = np.array([247, 245, 239], dtype=float)
    target = (
        np.array([41, 122, 101], dtype=float)
        if value >= 0
        else np.array([184, 59, 59], dtype=float)
    )
    color = np.rint(neutral * (1 - intensity) + target * intensity).astype(int)
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"


def write_three_way_heatmap_svg(
    three_way: pd.DataFrame,
    *,
    direction: str,
    horizon: int,
) -> Path:
    width, height = 1480, 400
    title = f"{direction.upper()} MA7 {horizon}D raw expectancy — Slope panels × ER rows × RV columns"
    svg = _svg_header(width, height, title)
    data = three_way.loc[
        three_way["direction"].eq(direction)
        & three_way["horizon_days"].eq(horizon)
        & three_way["return_metric"].eq("raw_return")
    ]
    reliable_values = data.loc[data["reliable_cell"], "mean"].abs()
    scale = max(0.005, float(reliable_values.quantile(0.95)))
    cell_size = 44
    for slope_q in range(1, 6):
        panel_x = 40 + (slope_q - 1) * 285
        panel_y = 92
        svg.append(
            f'<text x="{panel_x + 110}" y="{panel_y - 16}" font-size="16" font-weight="700" text-anchor="middle">Slope Q{slope_q}</text>'
        )
        for er_q in range(1, 6):
            svg.append(
                f'<text x="{panel_x - 7}" y="{panel_y + (5 - er_q) * cell_size + 27}" font-size="10" text-anchor="end">ER Q{er_q}</text>'
            )
            for rv_q in range(1, 6):
                cell = data.loc[
                    data["slope_q"].eq(slope_q)
                    & data["er_q"].eq(er_q)
                    & data["rv_q"].eq(rv_q)
                ]
                x = panel_x + (rv_q - 1) * cell_size
                y = panel_y + (5 - er_q) * cell_size
                if cell.empty:
                    fill = "#dad8d2"
                    label = "NA"
                    opacity = 1.0
                else:
                    item = cell.iloc[0]
                    fill = _heat_color(float(item["mean"]), scale)
                    label = f"{float(item['mean']) * 100:.1f}"
                    opacity = 1.0 if bool(item["reliable_cell"]) else 0.35
                svg.append(
                    f'<rect x="{x}" y="{y}" width="{cell_size - 2}" height="{cell_size - 2}" fill="{fill}" fill-opacity="{opacity}" stroke="#ffffff"/>'
                )
                svg.append(
                    f'<text x="{x + 21}" y="{y + 25}" font-size="10" text-anchor="middle">{label}</text>'
                )
        for rv_q in range(1, 6):
            svg.append(
                f'<text x="{panel_x + (rv_q - 1) * cell_size + 21}" y="{panel_y + 240}" font-size="10" text-anchor="middle">RV Q{rv_q}</text>'
            )
    svg.append(
        f'<text x="40" y="365" font-size="12">Cell label = mean return in percent. Pale cells fail n≥{RELIABLE_MIN_EVENTS}, symbols≥{RELIABLE_MIN_SYMBOLS}, dates≥{RELIABLE_MIN_DATES}. Color scale clipped at ±{scale * 100:.2f}%.</text>'
    )
    svg.append("</svg>")
    path = FIGURE_DIR / f"binance_1d_ma7_rc_p0_{direction}_{horizon}d_three_way.svg"
    path.write_text("\n".join(svg), encoding="utf-8")
    return path


def _aligned_spread_from_robustness(robustness: pd.DataFrame) -> pd.DataFrame:
    data = robustness.loc[
        robustness["slice_type"].eq("ma_neighborhood")
        & robustness["return_metric"].eq("raw_return")
    ].copy()
    rows: list[dict[str, Any]] = []
    keys = ["slice_value", "direction", "variable", "horizon_days"]
    for key_values, group in data.groupby(keys, sort=True):
        ma_period, direction, variable, horizon = key_values
        qmap = group.set_index("quintile")["mean"].to_dict()
        if not all(quintile in qmap for quintile in range(1, 6)):
            continue
        if variable == "normalized_slope" and direction == "short":
            spread = qmap[1] - qmap[5]
        else:
            spread = qmap[5] - qmap[1]
        rows.append(
            {
                "ma_period": int(ma_period),
                "direction": direction,
                "variable": variable,
                "horizon_days": int(horizon),
                "aligned_extreme_spread": float(spread),
            }
        )
    return pd.DataFrame(rows)


def write_ma_robustness_svg(robustness: pd.DataFrame) -> Path:
    spread = _aligned_spread_from_robustness(robustness)
    width, height = 1500, 820
    svg = _svg_header(
        width,
        height,
        "MA5 / MA7 / MA10 robustness — hypothesis-aligned Q5 minus Q1 spread",
    )
    colors = {5: "#5e81ac", 7: "#bf616a", 10: "#4c9f70"}
    for row_index, direction in enumerate(("long", "short")):
        for column_index, variable in enumerate(REGIME_VARIABLES):
            x0 = 45 + column_index * 485
            y0 = 75 + row_index * 355
            plot_left, plot_top = x0 + 60, y0 + 50
            plot_width, plot_height = 350, 220
            svg.append(
                f'<rect class="panel" x="{x0}" y="{y0}" width="450" height="315" rx="4"/>'
            )
            svg.append(
                f'<text x="{x0 + 18}" y="{y0 + 27}" font-size="17" font-weight="700">{direction.upper()} · {html.escape(variable)}</text>'
            )
            data = spread.loc[
                spread["direction"].eq(direction) & spread["variable"].eq(variable)
            ]
            limit = max(
                0.002,
                float(np.nanmax(np.abs(data["aligned_extreme_spread"]))) * 1.15,
            )
            for index, horizon in enumerate(HORIZONS):
                x = plot_left + index * plot_width / (len(HORIZONS) - 1)
                svg.append(
                    f'<line class="grid" x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_top + plot_height}"/>'
                )
                svg.append(
                    f'<text x="{x:.1f}" y="{plot_top + plot_height + 20}" font-size="11" text-anchor="middle">{horizon}D</text>'
                )
            zero_y = plot_top + plot_height / 2
            svg.append(
                f'<line class="zero" x1="{plot_left}" y1="{zero_y:.1f}" x2="{plot_left + plot_width}" y2="{zero_y:.1f}"/>'
            )
            for ma_period in MA_PERIODS:
                line = data.loc[data["ma_period"].eq(ma_period)].sort_values(
                    "horizon_days"
                )
                points: list[str] = []
                for item in line.itertuples():
                    index = HORIZONS.index(int(item.horizon_days))
                    x = plot_left + index * plot_width / (len(HORIZONS) - 1)
                    y = (
                        plot_top
                        + (limit - float(item.aligned_extreme_spread))
                        / (2 * limit)
                        * plot_height
                    )
                    points.append(f"{x:.1f},{y:.1f}")
                    svg.append(
                        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{colors[ma_period]}"/>'
                    )
                svg.append(
                    f'<polyline points="{" ".join(points)}" fill="none" stroke="{colors[ma_period]}" stroke-width="2"/>'
                )
            for index, ma_period in enumerate(MA_PERIODS):
                lx = x0 + 95 + index * 92
                ly = y0 + 298
                svg.append(
                    f'<line x1="{lx}" y1="{ly}" x2="{lx + 17}" y2="{ly}" stroke="{colors[ma_period]}" stroke-width="3"/>'
                )
                svg.append(
                    f'<text x="{lx + 22}" y="{ly + 4}" font-size="11">MA{ma_period}</text>'
                )
    svg.append("</svg>")
    path = FIGURE_DIR / "binance_1d_ma7_rc_p0_ma_neighborhood_robustness.svg"
    path.write_text("\n".join(svg), encoding="utf-8")
    return path


def write_interactive_dashboard(
    single: pd.DataFrame,
    three_way: pd.DataFrame,
    monotonicity: pd.DataFrame,
    surface: pd.DataFrame,
    summary: dict[str, Any],
) -> Path:
    payload = {
        "single": _json_records(
            single,
            [
                "direction",
                "variable",
                "quintile",
                "horizon_days",
                "return_metric",
                "sample_count",
                "symbol_count",
                "event_date_count",
                "mean",
                "median",
                "win_rate",
                "t_stat",
                "ci95_low",
                "ci95_high",
            ],
        ),
        "three": _json_records(
            three_way,
            [
                "direction",
                "slope_q",
                "er_q",
                "rv_q",
                "horizon_days",
                "return_metric",
                "sample_count",
                "mean",
                "win_rate",
                "t_stat",
                "q_value_bh",
                "reliable_cell",
            ],
        ),
        "monotonicity": _json_records(monotonicity, monotonicity.columns),
        "surface": _json_records(surface, surface.columns),
        "summary": summary,
    }
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    template = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BIN-1D-MA7-RC-P0 Regime Dashboard</title>
<style>
:root{--ink:#16211f;--muted:#66706c;--paper:#f4f1e9;--card:#fffdf7;--line:#d1cec4;--pos:#297a65;--neg:#b83b3b;--accent:#263f56}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:34px 40px 22px;border-bottom:1px solid var(--line);background:#ece8dd}h1{margin:0 0 8px;font-size:30px;letter-spacing:-.02em}header p{margin:0;color:var(--muted);max-width:980px}.controls{display:flex;gap:16px;flex-wrap:wrap;padding:18px 40px;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(244,241,233,.96);backdrop-filter:blur(8px);z-index:5}label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}select{display:block;margin-top:6px;padding:8px 34px 8px 10px;border:1px solid var(--line);background:var(--card);color:var(--ink);font-size:14px}main{padding:26px 40px 60px;display:grid;gap:22px}.cards{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card,.section{background:var(--card);border:1px solid var(--line)}.card{padding:16px}.card .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.card .v{font-size:24px;font-weight:700;margin-top:8px}.section{padding:20px;overflow:auto}.section h2{margin:0 0 8px;font-size:20px}.section p{margin:0 0 16px;color:var(--muted)}.marginal{display:grid;grid-template-columns:repeat(3,minmax(280px,1fr));gap:14px}.mini{border:1px solid var(--line);padding:14px}.mini h3{margin:0 0 12px;font-size:15px}.barrow{display:grid;grid-template-columns:34px 1fr 74px 70px;gap:8px;align-items:center;margin:7px 0;font-size:12px}.track{height:12px;background:#ebe8df;position:relative}.bar{position:absolute;top:0;height:100%}.bar.pos{left:50%;background:var(--pos)}.bar.neg{right:50%;background:var(--neg)}.zero{position:absolute;left:50%;top:-2px;bottom:-2px;border-left:1px solid #6b716e}.heatwrap{display:grid;grid-template-columns:repeat(5,minmax(180px,1fr));gap:12px}.heatpanel h3{font-size:14px;margin:0 0 8px}.heatgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:2px}.cell{aspect-ratio:1;display:flex;flex-direction:column;justify-content:center;align-items:center;border:1px solid rgba(255,255,255,.7);font-size:11px}.cell small{font-size:9px;opacity:.75}.cell.unreliable{opacity:.35}table{border-collapse:collapse;width:100%;font-size:12px}th,td{text-align:right;padding:8px;border-bottom:1px solid #e1ded5;white-space:nowrap}th:first-child,td:first-child{text-align:left}.posText{color:var(--pos)}.negText{color:var(--neg)}@media(max-width:1050px){.cards{grid-template-columns:repeat(2,1fr)}.marginal{grid-template-columns:1fr}.heatwrap{grid-template-columns:1fr 1fr}}@media(max-width:640px){header,.controls,main{padding-left:16px;padding-right:16px}.cards{grid-template-columns:1fr}.heatwrap{grid-template-columns:1fr}}
</style>
</head>
<body>
<header><h1>BIN-1D-MA7-RC-P0</h1><p>全历史动态 Binance USD-M 永续合约池；MA7 只作 trigger。所有结果是 close-to-close historical diagnostic，不含手续费、滑点和 funding，不代表可交易净收益。</p></header>
<div class="controls"><label>Direction<select id="direction"><option>long</option><option>short</option></select></label><label>Horizon<select id="horizon"><option>1</option><option>3</option><option>5</option><option selected>10</option><option>20</option><option>40</option></select></label><label>Return metric<select id="metric"><option value="raw_return">Raw return</option><option value="atr_return">ATR units</option></select></label></div>
<main><div class="cards" id="cards"></div><section class="section"><h2>单变量 quintile</h2><p>柱长是 conditional mean；右侧给出胜率和双向聚类 t-stat。</p><div class="marginal" id="marginal"></div></section><section class="section"><h2>Slope × ER × RV 三维表</h2><p>每个 Slope panel 中，行是 ER Q1→Q5，列是 RV Q1→Q5。透明 cell 未达到冻结可靠性门槛。</p><div class="heatwrap" id="heat"></div></section><section class="section"><h2>最强与最弱可靠 cells</h2><div id="extremes"></div></section><section class="section"><h2>表面稳定性</h2><div id="surface"></div></section></main>
<script>
const DATA=__DATA__;
const fmt=(x,d=2)=>x===null||Number.isNaN(x)?"NA":Number(x).toFixed(d);
const metricScale=(metric)=>metric==="raw_return"?100:1;
const metricSuffix=(metric)=>metric==="raw_return"?"%":" ATR";
function color(value,scale){const neutral=[247,245,239],target=value>=0?[41,122,101]:[184,59,59],z=Math.min(Math.abs(value)/scale,1),c=neutral.map((n,i)=>Math.round(n*(1-z)+target[i]*z));return `rgb(${c[0]},${c[1]},${c[2]})`}
function state(){return{direction:document.querySelector("#direction").value,horizon:Number(document.querySelector("#horizon").value),metric:document.querySelector("#metric").value}}
function render(){const s=state(),factor=metricScale(s.metric),suffix=metricSuffix(s.metric);const single=DATA.single.filter(x=>x.direction===s.direction&&x.horizon_days===s.horizon&&x.return_metric===s.metric);const cells=DATA.three.filter(x=>x.direction===s.direction&&x.horizon_days===s.horizon&&x.return_metric===s.metric);const reliable=cells.filter(x=>x.reliable_cell);const maxAbs=Math.max(...single.map(x=>Math.abs(x.mean||0)),.0001);const eventCount=Math.max(...single.map(x=>x.sample_count||0));const sig=reliable.filter(x=>x.q_value_bh!==null&&x.q_value_bh<=.05).length;const surface=DATA.surface.find(x=>x.direction===s.direction&&x.horizon_days===s.horizon&&x.return_metric===s.metric);document.querySelector("#cards").innerHTML=`<div class="card"><div class="k">Primary events</div><div class="v">${eventCount.toLocaleString()}</div></div><div class="card"><div class="k">Reliable cells</div><div class="v">${reliable.length}/125</div></div><div class="card"><div class="k">BH-FDR q≤.05</div><div class="v">${sig}</div></div><div class="card"><div class="k">Pre/Post surface ρ</div><div class="v">${surface?fmt(surface.pre2024_post2024_spearman):"NA"}</div></div>`;const names={normalized_slope:"Normalized Slope",er20:"ER20",rv_percentile:"RV20 percentile"};document.querySelector("#marginal").innerHTML=Object.keys(names).map(v=>{const rows=single.filter(x=>x.variable===v).sort((a,b)=>a.quintile-b.quintile);return `<div class="mini"><h3>${names[v]}</h3>${rows.map(x=>{const width=Math.abs(x.mean)/maxAbs*50;return `<div class="barrow"><span>Q${x.quintile}</span><div class="track"><span class="zero"></span><span class="bar ${x.mean>=0?"pos":"neg"}" style="width:${width}%"></span></div><strong class="${x.mean>=0?"posText":"negText"}">${fmt(x.mean*factor)}${suffix}</strong><span>WR ${fmt(x.win_rate*100,1)} · t ${fmt(x.t_stat,1)}</span></div>`}).join("")}</div>`}).join("");const scale=Math.max(...reliable.map(x=>Math.abs(x.mean||0)),.0001);document.querySelector("#heat").innerHTML=[1,2,3,4,5].map(sq=>{const items=[];for(let eq=1;eq<=5;eq++){for(let rq=1;rq<=5;rq++){const x=cells.find(z=>z.slope_q===sq&&z.er_q===eq&&z.rv_q===rq);items.push(x?`<div class="cell ${x.reliable_cell?"":"unreliable"}" title="Slope Q${sq}, ER Q${eq}, RV Q${rq}, n=${x.sample_count}, q=${fmt(x.q_value_bh,3)}" style="background:${color(x.mean,scale)}"><b>${fmt(x.mean*factor)}${suffix}</b><small>ER${eq}/RV${rq} · n${x.sample_count}</small></div>`:`<div class="cell">NA</div>`)}}return `<div class="heatpanel"><h3>Slope Q${sq}</h3><div class="heatgrid">${items.join("")}</div></div>`}).join("");const sorted=[...reliable].sort((a,b)=>b.mean-a.mean),ext=[...sorted.slice(0,8),...sorted.slice(-8).reverse()];document.querySelector("#extremes").innerHTML=`<table><thead><tr><th>Cell</th><th>Mean</th><th>Median/WR proxy</th><th>n</th><th>t-stat</th><th>BH q</th></tr></thead><tbody>${ext.map(x=>`<tr><td>S${x.slope_q} · E${x.er_q} · R${x.rv_q}</td><td class="${x.mean>=0?"posText":"negText"}">${fmt(x.mean*factor)}${suffix}</td><td>${fmt(x.win_rate*100,1)}% wins</td><td>${x.sample_count}</td><td>${fmt(x.t_stat,2)}</td><td>${fmt(x.q_value_bh,3)}</td></tr>`).join("")}</tbody></table>`;document.querySelector("#surface").innerHTML=surface?`<table><tbody><tr><th>Reliable coverage</th><td>${surface.reliable_cells}/125</td></tr><tr><th>Normalized neighbor roughness</th><td>${fmt(surface.normalized_neighbor_roughness)}</td></tr><tr><th>&lt;2024 vs ≥2024 Spearman</th><td>${fmt(surface.pre2024_post2024_spearman)} (${surface.pre2024_post2024_common_cells} cells)</td></tr><tr><th>MA5 vs MA7 Spearman</th><td>${fmt(surface.ma5_ma7_spearman)} (${surface.ma5_ma7_common_cells} cells)</td></tr><tr><th>MA10 vs MA7 Spearman</th><td>${fmt(surface.ma10_ma7_spearman)} (${surface.ma10_ma7_common_cells} cells)</td></tr></tbody></table>`:"No surface record"}
document.querySelectorAll("select").forEach(x=>x.addEventListener("change",render));render();
</script>
</body>
</html>"""
    content = template.replace("__DATA__", data_json)
    path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_interactive_dashboard.html"
    path.write_text(content, encoding="utf-8")
    return path


def build_summary(
    input_quality: dict[str, Any],
    inventory: pd.DataFrame,
    panel: pd.DataFrame,
    events: pd.DataFrame,
    edges: dict[str, list[float]],
    unconditional: pd.DataFrame,
    monotonicity: pd.DataFrame,
    surface: pd.DataFrame,
    three_way: pd.DataFrame,
) -> dict[str, Any]:
    primary_events = events.loc[events["ma_period"].eq(7)]
    reliable = three_way.loc[three_way["reliable_cell"]]
    focus_cells: dict[str, Any] = {}
    for direction in ("long", "short"):
        for horizon in (10, 20):
            subset = reliable.loc[
                reliable["direction"].eq(direction)
                & reliable["horizon_days"].eq(horizon)
                & reliable["return_metric"].eq("raw_return")
            ].sort_values("mean")
            if subset.empty:
                continue
            weakest = subset.iloc[0]
            strongest = subset.iloc[-1]
            focus_cells[f"{direction}_{horizon}d"] = {
                "strongest_descriptive_cell": {
                    "slope_q": int(strongest["slope_q"]),
                    "er_q": int(strongest["er_q"]),
                    "rv_q": int(strongest["rv_q"]),
                    "sample_count": int(strongest["sample_count"]),
                    "mean": float(strongest["mean"]),
                    "t_stat": float(strongest["t_stat"]),
                    "q_value_bh": float(strongest["q_value_bh"]),
                },
                "weakest_descriptive_cell": {
                    "slope_q": int(weakest["slope_q"]),
                    "er_q": int(weakest["er_q"]),
                    "rv_q": int(weakest["rv_q"]),
                    "sample_count": int(weakest["sample_count"]),
                    "mean": float(weakest["mean"]),
                    "t_stat": float(weakest["t_stat"]),
                    "q_value_bh": float(weakest["q_value_bh"]),
                },
            }
    inventory_summary = {
        "archive_symbols": int(len(inventory)),
        "symbols_with_120_complete_days": int(
            inventory["has_120_complete_days"].sum()
        ),
        "symbols_left_truncated_at_2020_archive_start": int(
            inventory["left_truncated_at_archive_start"].sum()
        ),
        "complete_daily_bars": int(inventory["complete_daily_bars"].sum()),
        "partial_daily_groups_excluded": int(inventory["partial_daily_groups"].sum()),
        "symbols_with_internal_missing_complete_days": int(
            inventory["missing_complete_days_inside_span"].gt(0).sum()
        ),
        "eligible_regime_symbols": int(
            panel.loc[panel["eligible_regime"], "symbol"].nunique()
        ),
        "eligible_regime_days": int(panel["eligible_regime"].sum()),
    }
    event_counts = (
        events.groupby(["ma_period", "direction"])["event_id"]
        .nunique()
        .rename("events")
        .reset_index()
        .to_dict(orient="records")
    )
    return {
        "study_id": "BIN-1D-MA7-RC-P0",
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "input_quality": input_quality,
        "inventory": inventory_summary,
        "regime_bin_edges": edges,
        "event_counts": event_counts,
        "primary_ma7_events": int(primary_events["event_id"].nunique()),
        "unconditional_stats": _json_records(unconditional, unconditional.columns),
        "monotonicity": _json_records(monotonicity, monotonicity.columns),
        "surface_diagnostics": _json_records(surface, surface.columns),
        "descriptive_focus_cells_not_selected_candidates": focus_cells,
        "interpretation_warning": (
            "All thresholds and results are exposed historical diagnostics. No cost, "
            "funding, execution, capacity, or prospective validation is included."
        ),
    }


def write_manifest(paths: Iterable[Path]) -> Path:
    entries = []
    for path in sorted(set(paths)):
        entries.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = {
        "study_id": "BIN-1D-MA7-RC-P0",
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "files": entries,
    }
    path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_artifact_manifest.json"
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("pass --run to execute the frozen historical study")
    validate_frozen_config()
    prepare_output_directories(force=args.force)
    connection = duckdb.connect()
    connection.execute("SET TimeZone='UTC'")
    print("stage=1 input quality audit")
    quality = input_audit(connection)
    print(json.dumps(quality, ensure_ascii=False, default=str))

    print("stage=2 UTC daily aggregation and historical inventory")
    daily, inventory = load_daily_bars(connection)
    panel = prepare_feature_panel(daily)
    edges = freeze_regime_bins(panel)
    print(json.dumps({"regime_bin_edges": edges}, ensure_ascii=False))

    print("stage=3 symmetric MA5/7/10 event extraction")
    events = build_events(panel)
    print(
        events.groupby(["ma_period", "direction"])["event_id"]
        .nunique()
        .to_string()
    )

    print("stage=4 clustered conditional expectancy statistics")
    unconditional = build_unconditional_stats(events)
    single = build_single_variable_stats(events)
    three_way = build_three_way_stats(events)
    robustness = build_robustness_stats(events)
    monotonicity = build_monotonicity_stats(single)
    surface = build_surface_diagnostics(events, three_way)

    print("stage=5 durable artifacts and visualizations")
    output_paths: list[Path] = []
    inventory_path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_universe_inventory.csv"
    inventory.to_csv(inventory_path, index=False)
    output_paths.append(inventory_path)
    events_path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_events.parquet"
    events.to_parquet(events_path, index=False, compression="zstd")
    output_paths.append(events_path)
    tables = {
        "unconditional_stats": unconditional,
        "single_variable_stats": single,
        "three_way_stats": three_way,
        "robustness_stats": robustness,
        "monotonicity_stats": monotonicity,
        "surface_diagnostics": surface,
    }
    for name, frame in tables.items():
        path = ARTIFACT_DIR / f"binance_1d_ma7_rc_p0_{name}.csv"
        frame.to_csv(path, index=False)
        output_paths.append(path)

    quality.update(
        {
            "daily_groups": int(len(daily)),
            "complete_daily_bars": int(daily["is_complete_day"].sum()),
            "partial_daily_groups_excluded": int((~daily["is_complete_day"]).sum()),
            "eligible_regime_days": int(panel["eligible_regime"].sum()),
            "eligible_regime_symbols": int(
                panel.loc[panel["eligible_regime"], "symbol"].nunique()
            ),
        }
    )
    quality_path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_data_quality_audit.json"
    quality_path.write_text(
        json.dumps(quality, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    output_paths.append(quality_path)

    summary = build_summary(
        quality,
        inventory,
        panel,
        events,
        edges,
        unconditional,
        monotonicity,
        surface,
        three_way,
    )
    summary_path = ARTIFACT_DIR / "binance_1d_ma7_rc_p0_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    output_paths.append(summary_path)

    output_paths.append(write_single_variable_svg(single))
    for direction in ("long", "short"):
        for horizon in (10, 20):
            output_paths.append(
                write_three_way_heatmap_svg(
                    three_way,
                    direction=direction,
                    horizon=horizon,
                )
            )
    output_paths.append(write_ma_robustness_svg(robustness))
    output_paths.append(
        write_interactive_dashboard(
            single,
            three_way,
            monotonicity,
            surface,
            summary,
        )
    )
    manifest_path = write_manifest(output_paths)
    print(
        json.dumps(
            {
                "status": "complete",
                "summary": str(summary_path.relative_to(ROOT)),
                "manifest": str(manifest_path.relative_to(ROOT)),
                "files": len(output_paths) + 1,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
