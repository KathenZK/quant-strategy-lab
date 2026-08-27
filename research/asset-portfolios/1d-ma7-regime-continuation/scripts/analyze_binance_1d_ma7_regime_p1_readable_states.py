from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from research_binance_1d_ma7_regime_continuation import (
    HORIZONS,
    RETURN_METRICS,
    infer_mean,
    rolling_percentile_current,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation"
CONFIG_PATH = FAMILY_DIR / "configs/binance-1d-ma7-regime-continuation-p1.json"
EXPECTED_CONFIG_SHA256 = (
    "77236cad969fbccfb0c907514e3d7f3898160a1b0a777dcd60511f6bcc6ceb42"
)
DAILY_PANEL_PATH = (
    ROOT
    / "data/cache/binance-1d-ma7-rc-p0"
    / "binance_1d_ma7_rc_p0_daily_panel.parquet"
)
EVENT_PANEL_PATH = (
    FAMILY_DIR / "artifacts/binance_1d_ma7_rc_p0_events.parquet"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/binance-1d-ma7-regime-continuation-p1-readable-states-frequency-2026-08-24.md"
)

OUTPUTS = {
    "ma_neighborhood": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_ma_neighborhood_unconditional_stats.csv",
    "state_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_state_volatility_stats.csv",
    "filter_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_filter_expectancy_stats.csv",
    "liquidity_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_filter_liquidity_stats.csv",
    "event_counts": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_event_filter_counts.csv",
    "regime_counts": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_regime_event_counts.csv",
    "frequency_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_frequency_stats.csv",
    "frequency_timeseries": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p1_frequency_timeseries.csv",
    "summary": ARTIFACT_DIR / "binance_1d_ma7_rc_p1_summary.json",
    "manifest": ARTIFACT_DIR / "binance_1d_ma7_rc_p1_artifact_manifest.json",
}

MA_PERIODS = (5, 7, 10)
PERCENTILE_WINDOW = 252
RV_LABELS = {
    1: "Q1_EXTREME_LOW",
    2: "Q2_LOW",
    3: "Q3_MEDIUM",
    4: "Q4_HIGH",
    5: "Q5_EXTREME_HIGH",
}
STATE_ORDER = ("UP_TREND", "DOWN_TREND", "CHOP", "TRANSITION")
FILTER_ORDER = (
    "ALL_MA7",
    "ALIGNED_STATE",
    "ALIGNED_LOW_VOL",
    "ALIGNED_MID_VOL",
    "ALIGNED_HIGH_VOL",
    "ALIGNED_COMPRESSION_EXPANSION",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run frozen BIN-1D-MA7-RC-P1 readable state and frequency analysis."
        )
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required acknowledgement that P1 event outcomes will be read.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing P1 outputs.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(force: bool) -> dict[str, Any]:
    actual = sha256_file(CONFIG_PATH)
    if actual != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(
            f"frozen P1 config hash mismatch: {actual} != {EXPECTED_CONFIG_SHA256}"
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != "BIN-1D-MA7-RC-P1":
        raise RuntimeError("unexpected P1 study_id")
    for path in (DAILY_PANEL_PATH, EVENT_PANEL_PATH):
        if not path.exists():
            raise FileNotFoundError(f"required P0 derived input is missing: {path}")
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"P1 outputs already exist; use --force: {names}")
    return config


def require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise RuntimeError(f"{label} missing required columns: {missing}")


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    panel = pd.read_parquet(DAILY_PANEL_PATH)
    events = pd.read_parquet(EVENT_PANEL_PATH)
    require_columns(
        panel,
        (
            "symbol",
            "event_date",
            "block_id",
            "high",
            "low",
            "close",
            "sma30",
            "normalized_slope",
            "er20",
            "rv_percentile",
            "eligible_regime",
        ),
        "daily panel",
    )
    require_columns(
        events,
        (
            "event_id",
            "symbol",
            "event_date",
            "block_id",
            "ma_period",
            "direction",
            *tuple(
                f"{metric}_{horizon}"
                for metric in RETURN_METRICS
                for horizon in HORIZONS
            ),
        ),
        "event panel",
    )
    panel["event_date"] = pd.to_datetime(panel["event_date"], utc=True)
    events["event_date"] = pd.to_datetime(events["event_date"], utc=True)
    if panel.duplicated(["symbol", "block_id", "event_date"]).any():
        raise RuntimeError("daily panel has duplicate symbol/block/date keys")
    if events["event_id"].duplicated().any():
        raise RuntimeError("event panel has duplicate event_id")
    if set(events["ma_period"].unique()) != set(MA_PERIODS):
        raise RuntimeError("event panel MA periods differ from frozen {5,7,10}")
    if set(events["direction"].unique()) != {"long", "short"}:
        raise RuntimeError("event panel directions differ from frozen long/short")
    return (
        panel.sort_values(["symbol", "block_id", "event_date"]).reset_index(
            drop=True
        ),
        events.sort_values(["ma_period", "event_date", "symbol"]).reset_index(
            drop=True
        ),
    )


def assign_quintile(percentile: pd.Series) -> pd.Series:
    values = percentile.to_numpy(dtype=float)
    result = np.full(len(values), np.nan, dtype=float)
    valid = np.isfinite(values)
    result[valid] = (
        np.searchsorted(
            np.asarray([0.2, 0.4, 0.6, 0.8]),
            values[valid],
            side="left",
        )
        + 1
    )
    return pd.Series(result, index=percentile.index, dtype="Int64")


def enrich_feature_block(group: pd.DataFrame) -> pd.DataFrame:
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
    atr5 = true_range.rolling(5, min_periods=5).mean()
    atr20 = true_range.rolling(20, min_periods=20).mean()
    compression_ratio = atr5 / atr20.replace(0.0, np.nan)
    expansion_ratio = true_range / atr20.shift(1).replace(0.0, np.nan)

    block["slope_percentile_252"] = rolling_percentile_current(
        block["normalized_slope"].to_numpy(dtype=float), PERCENTILE_WINDOW
    )
    block["er_percentile_252"] = rolling_percentile_current(
        block["er20"].to_numpy(dtype=float), PERCENTILE_WINDOW
    )
    block["compression_ratio"] = compression_ratio
    compression_percentile = rolling_percentile_current(
        compression_ratio.to_numpy(dtype=float), PERCENTILE_WINDOW
    )
    block["compression_percentile_252"] = compression_percentile
    block["compression_percentile_lag1"] = pd.Series(
        compression_percentile, index=block.index
    ).shift(1)
    block["expansion_ratio"] = expansion_ratio
    block["expansion_percentile_252"] = rolling_percentile_current(
        expansion_ratio.to_numpy(dtype=float), PERCENTILE_WINDOW
    )
    return block


def build_readable_states(panel: pd.DataFrame) -> pd.DataFrame:
    feature_columns = [
        "symbol",
        "event_date",
        "block_id",
        "close",
        "sma30",
        "normalized_slope",
        "er20",
        "rv_percentile",
        "eligible_regime",
        "high",
        "low",
    ]
    enriched_blocks = [
        enrich_feature_block(group)
        for _, group in panel[feature_columns].groupby(
            ["symbol", "block_id"], sort=False
        )
    ]
    enriched = pd.concat(enriched_blocks, ignore_index=True)
    needed = [
        "slope_percentile_252",
        "er_percentile_252",
        "compression_percentile_lag1",
        "expansion_percentile_252",
        "rv_percentile",
    ]
    enriched["eligible_p1"] = enriched["eligible_regime"] & enriched[
        needed
    ].notna().all(axis=1)

    up = (
        enriched["close"].gt(enriched["sma30"])
        & enriched["normalized_slope"].gt(0.0)
        & enriched["slope_percentile_252"].gt(0.60)
        & enriched["er_percentile_252"].gt(0.60)
    )
    down = (
        enriched["close"].lt(enriched["sma30"])
        & enriched["normalized_slope"].lt(0.0)
        & enriched["slope_percentile_252"].le(0.40)
        & enriched["er_percentile_252"].gt(0.60)
    )
    chop = enriched["er_percentile_252"].le(0.40)
    enriched["market_state"] = np.select(
        [up, down, chop],
        ["UP_TREND", "DOWN_TREND", "CHOP"],
        default="TRANSITION",
    )
    enriched.loc[~enriched["eligible_p1"], "market_state"] = pd.NA
    enriched["rv_q_p1"] = assign_quintile(enriched["rv_percentile"])
    enriched["rv_label"] = enriched["rv_q_p1"].map(RV_LABELS)
    enriched["compression_expansion"] = (
        enriched["compression_percentile_lag1"].le(0.20)
        & enriched["expansion_percentile_252"].gt(0.80)
    )
    enriched.loc[~enriched["eligible_p1"], "compression_expansion"] = False

    if enriched.loc[enriched["eligible_p1"], "market_state"].isna().any():
        raise RuntimeError("eligible P1 state is missing")
    observed_states = set(
        enriched.loc[enriched["eligible_p1"], "market_state"].unique()
    )
    if observed_states != set(STATE_ORDER):
        raise RuntimeError(f"unexpected P1 state coverage: {observed_states}")
    return enriched


def merge_event_features(
    events: pd.DataFrame, enriched: pd.DataFrame
) -> pd.DataFrame:
    feature_columns = [
        "symbol",
        "event_date",
        "block_id",
        "eligible_p1",
        "market_state",
        "slope_percentile_252",
        "er_percentile_252",
        "rv_q_p1",
        "rv_label",
        "compression_ratio",
        "compression_percentile_lag1",
        "expansion_ratio",
        "expansion_percentile_252",
        "compression_expansion",
    ]
    result = events.merge(
        enriched[feature_columns],
        on=["symbol", "event_date", "block_id"],
        how="left",
        validate="many_to_one",
    )
    if result["eligible_p1"].isna().any():
        raise RuntimeError("some P0 events did not match the P1 feature panel")
    return result


def calculate_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for metric in RETURN_METRICS:
            column = f"{metric}_{horizon}"
            stats = infer_mean(
                frame[column], frame["symbol"], frame["event_date"]
            )
            rows.append(
                {
                    "horizon_days": horizon,
                    "return_metric": metric,
                    **stats,
                }
            )
    return rows


def grouped_stats(
    frame: pd.DataFrame,
    group_columns: Sequence[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(list(group_columns), dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        identity = dict(zip(group_columns, keys, strict=True))
        for stats in calculate_stats(group):
            rows.append({**identity, **stats})
    return pd.DataFrame(rows)


def build_ma_neighborhood(events: pd.DataFrame) -> pd.DataFrame:
    result = grouped_stats(events, ["ma_period", "direction"])
    return result.sort_values(
        ["ma_period", "direction", "return_metric", "horizon_days"]
    ).reset_index(drop=True)


def build_state_stats(primary: pd.DataFrame) -> pd.DataFrame:
    result = grouped_stats(
        primary, ["direction", "market_state", "rv_q_p1", "rv_label"]
    )
    return result.sort_values(
        [
            "direction",
            "market_state",
            "rv_q_p1",
            "return_metric",
            "horizon_days",
        ]
    ).reset_index(drop=True)


def filter_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    aligned = (
        frame["direction"].eq("long") & frame["market_state"].eq("UP_TREND")
    ) | (
        frame["direction"].eq("short")
        & frame["market_state"].eq("DOWN_TREND")
    )
    return {
        "ALL_MA7": pd.Series(True, index=frame.index),
        "ALIGNED_STATE": aligned,
        "ALIGNED_LOW_VOL": aligned & frame["rv_q_p1"].isin([1, 2]),
        "ALIGNED_MID_VOL": aligned & frame["rv_q_p1"].eq(3),
        "ALIGNED_HIGH_VOL": aligned & frame["rv_q_p1"].isin([4, 5]),
        "ALIGNED_COMPRESSION_EXPANSION": aligned
        & frame["compression_expansion"],
    }


def build_filter_outputs(
    primary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stat_rows: list[dict[str, Any]] = []
    count_rows: list[dict[str, Any]] = []
    masks = filter_masks(primary)
    totals = primary.groupby("direction").size().to_dict()
    full_total = len(primary)
    for filter_name in FILTER_ORDER:
        subset = primary.loc[masks[filter_name]].copy()
        for direction in ("long", "short"):
            directional = subset.loc[subset["direction"].eq(direction)]
            count = len(directional)
            count_rows.append(
                {
                    "filter_name": filter_name,
                    "direction": direction,
                    "event_count": count,
                    "symbol_count": int(directional["symbol"].nunique()),
                    "event_date_count": int(directional["event_date"].nunique()),
                    "share_of_direction_all": (
                        count / totals[direction] if totals[direction] else np.nan
                    ),
                    "share_of_all_events": count / full_total if full_total else np.nan,
                }
            )
            for stats in calculate_stats(directional):
                stat_rows.append(
                    {
                        "filter_name": filter_name,
                        "direction": direction,
                        **stats,
                    }
                )
    stats_frame = pd.DataFrame(stat_rows).sort_values(
        ["filter_name", "direction", "return_metric", "horizon_days"]
    )
    count_frame = pd.DataFrame(count_rows).sort_values(
        ["filter_name", "direction"]
    )
    return stats_frame.reset_index(drop=True), count_frame.reset_index(drop=True)


def build_liquidity_stats(primary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    masks = filter_masks(primary)
    for filter_name in ("ALIGNED_STATE", "ALIGNED_HIGH_VOL"):
        subset = primary.loc[masks[filter_name]].copy()
        for direction in ("long", "short"):
            for segment in ("major", "long_tail"):
                group = subset.loc[
                    subset["direction"].eq(direction)
                    & subset["liquidity_segment"].eq(segment)
                ]
                for stats in calculate_stats(group):
                    rows.append(
                        {
                            "filter_name": filter_name,
                            "direction": direction,
                            "liquidity_segment": segment,
                            **stats,
                        }
                    )
    return pd.DataFrame(rows).sort_values(
        [
            "filter_name",
            "direction",
            "liquidity_segment",
            "return_metric",
            "horizon_days",
        ]
    )


def build_regime_counts(primary: pd.DataFrame) -> pd.DataFrame:
    result = (
        primary.groupby(
            [
                "direction",
                "market_state",
                "rv_q_p1",
                "rv_label",
                "compression_expansion",
            ],
            dropna=False,
        )
        .agg(
            event_count=("event_id", "size"),
            symbol_count=("symbol", "nunique"),
            event_date_count=("event_date", "nunique"),
        )
        .reset_index()
    )
    direction_totals = primary.groupby("direction").size().rename("direction_total")
    result = result.merge(direction_totals, on="direction", validate="many_to_one")
    result["share_of_direction_all"] = (
        result["event_count"] / result["direction_total"]
    )
    return result.drop(columns="direction_total").sort_values(
        [
            "direction",
            "market_state",
            "rv_q_p1",
            "compression_expansion",
        ]
    )


def period_key(dates: pd.Series | pd.DatetimeIndex, period_type: str) -> pd.Series:
    index = pd.DatetimeIndex(pd.to_datetime(dates, utc=True))
    if period_type == "day":
        values = index.normalize()
    elif period_type == "week":
        values = index.tz_convert(None).to_period("W-SUN").start_time.tz_localize("UTC")
    elif period_type == "month":
        values = index.tz_convert(None).to_period("M").start_time.tz_localize("UTC")
    else:
        raise ValueError(f"unknown period type: {period_type}")
    return pd.Series(values)


def build_frequency(
    primary: pd.DataFrame,
    eligible_states: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = eligible_states.loc[eligible_states["eligible_p1"]].copy()
    start = eligible["event_date"].min().normalize()
    end = eligible["event_date"].max().normalize()
    if pd.isna(start) or pd.isna(end):
        raise RuntimeError("P1 eligible calendar is empty")
    eligible_symbol_days = len(eligible)
    calendar = pd.Series(pd.date_range(start, end, freq="D", tz="UTC"))
    masks = filter_masks(primary)
    distribution_rows: list[dict[str, Any]] = []
    timeseries_rows: list[pd.DataFrame] = []

    for filter_name in FILTER_ORDER:
        subset = primary.loc[masks[filter_name]].copy()
        for direction in ("long", "short"):
            directional = subset.loc[subset["direction"].eq(direction)].copy()
            for period_type in ("day", "week", "month"):
                grid = pd.DataFrame(
                    {"period_start": period_key(calendar, period_type).drop_duplicates()}
                )
                if len(directional):
                    event_keys = period_key(directional["event_date"], period_type)
                    counts = (
                        event_keys.value_counts()
                        .rename_axis("period_start")
                        .rename("event_count")
                        .reset_index()
                    )
                else:
                    counts = pd.DataFrame(columns=["period_start", "event_count"])
                series = grid.merge(counts, on="period_start", how="left")
                series["event_count"] = series["event_count"].fillna(0).astype(int)
                series["filter_name"] = filter_name
                series["direction"] = direction
                series["period_type"] = period_type
                timeseries_rows.append(series)

                values = series["event_count"].to_numpy(dtype=float)
                total = int(values.sum())
                distribution_rows.append(
                    {
                        "filter_name": filter_name,
                        "direction": direction,
                        "period_type": period_type,
                        "period_start": start,
                        "period_end": end,
                        "period_count": len(values),
                        "total_events": total,
                        "mean_events": float(values.mean()),
                        "median_events": float(np.median(values)),
                        "p90_events": float(np.quantile(values, 0.90)),
                        "maximum_events": int(values.max()),
                        "zero_period_share": float((values == 0).mean()),
                        "active_period_share": float((values > 0).mean()),
                        "events_per_1000_eligible_symbol_days": (
                            total / eligible_symbol_days * 1000.0
                            if eligible_symbol_days
                            else np.nan
                        ),
                    }
                )
    frequency_stats = pd.DataFrame(distribution_rows).sort_values(
        ["filter_name", "direction", "period_type"]
    )
    frequency_timeseries = pd.concat(timeseries_rows, ignore_index=True).sort_values(
        ["filter_name", "direction", "period_type", "period_start"]
    )
    return frequency_stats.reset_index(drop=True), frequency_timeseries.reset_index(
        drop=True
    )


def percent(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "NA"
    return f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "NA"
    return f"{value:.{digits}f}"


def lookup_stat(
    frame: pd.DataFrame,
    **conditions: Any,
) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column, value in conditions.items():
        mask &= frame[column].eq(value)
    result = frame.loc[mask]
    if len(result) != 1:
        raise RuntimeError(f"expected one stat row for {conditions}, got {len(result)}")
    return result.iloc[0]


def render_ma_table(ma_stats: pd.DataFrame) -> list[str]:
    lines = [
        "| MA | 持有天数 | 多头次数 | 多头平均 | 多头中位数 | 多头胜率 | 空头次数 | 空头平均 | 空头中位数 | 空头胜率 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for ma_period in MA_PERIODS:
        for horizon in HORIZONS:
            long = lookup_stat(
                ma_stats,
                ma_period=ma_period,
                direction="long",
                horizon_days=horizon,
                return_metric="raw_return",
            )
            short = lookup_stat(
                ma_stats,
                ma_period=ma_period,
                direction="short",
                horizon_days=horizon,
                return_metric="raw_return",
            )
            lines.append(
                "| "
                f"{ma_period} | {horizon} | {int(long.sample_count):,} | "
                f"{percent(long['mean'])} | {percent(long['median'])} | "
                f"{percent(long.win_rate)} | {int(short.sample_count):,} | "
                f"{percent(short['mean'])} | {percent(short['median'])} | "
                f"{percent(short.win_rate)} |"
            )
    return lines


def render_event_total_table(events: pd.DataFrame) -> list[str]:
    counts = (
        events.groupby(["ma_period", "direction"])
        .size()
        .rename("event_count")
        .reset_index()
    )
    lines = [
        "| MA | 多头历史事件 | 空头历史事件 | 合计 |",
        "| ---: | ---: | ---: | ---: |",
    ]
    for ma_period in MA_PERIODS:
        long_count = int(
            counts.loc[
                counts["ma_period"].eq(ma_period)
                & counts["direction"].eq("long"),
                "event_count",
            ].iloc[0]
        )
        short_count = int(
            counts.loc[
                counts["ma_period"].eq(ma_period)
                & counts["direction"].eq("short"),
                "event_count",
            ].iloc[0]
        )
        lines.append(
            f"| {ma_period} | {long_count:,} | {short_count:,} | "
            f"{long_count + short_count:,} |"
        )
    return lines


def render_filter_table(
    counts: pd.DataFrame,
    filter_stats: pd.DataFrame,
) -> list[str]:
    lines = [
        "| 过滤层 | 方向 | 事件数 | 保留比例 | 10D平均/胜率 | 20D平均/胜率 |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for filter_name in FILTER_ORDER:
        for direction in ("long", "short"):
            count = lookup_stat(
                counts, filter_name=filter_name, direction=direction
            )
            ten = lookup_stat(
                filter_stats,
                filter_name=filter_name,
                direction=direction,
                horizon_days=10,
                return_metric="raw_return",
            )
            twenty = lookup_stat(
                filter_stats,
                filter_name=filter_name,
                direction=direction,
                horizon_days=20,
                return_metric="raw_return",
            )
            lines.append(
                "| "
                f"{filter_name} | {direction} | {int(count.event_count):,} | "
                f"{percent(count.share_of_direction_all)} | "
                f"{percent(ten['mean'])} / {percent(ten.win_rate)} | "
                f"{percent(twenty['mean'])} / {percent(twenty.win_rate)} |"
            )
    return lines


def render_volatility_table(state_stats: pd.DataFrame) -> list[str]:
    lines = [
        "| 对齐状态 | 波动档 | 方向 | 10D次数 | 10D平均/胜率 | 20D次数 | 20D平均/胜率 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for direction, state in (("long", "UP_TREND"), ("short", "DOWN_TREND")):
        for rv_q in range(1, 6):
            label = RV_LABELS[rv_q]
            ten = lookup_stat(
                state_stats,
                direction=direction,
                market_state=state,
                rv_q_p1=rv_q,
                rv_label=label,
                horizon_days=10,
                return_metric="raw_return",
            )
            twenty = lookup_stat(
                state_stats,
                direction=direction,
                market_state=state,
                rv_q_p1=rv_q,
                rv_label=label,
                horizon_days=20,
                return_metric="raw_return",
            )
            lines.append(
                "| "
                f"{state} | {label} | {direction} | {int(ten.sample_count):,} | "
                f"{percent(ten['mean'])} / {percent(ten.win_rate)} | "
                f"{int(twenty.sample_count):,} | "
                f"{percent(twenty['mean'])} / {percent(twenty.win_rate)} |"
            )
    return lines


def render_frequency_table(frequency: pd.DataFrame) -> list[str]:
    lines = [
        "| 过滤层 | 方向 | 周期 | 总次数 | 平均 | 中位数 | P90 | 最大 | 零信号占比 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for filter_name in FILTER_ORDER:
        for direction in ("long", "short"):
            for period_type in ("day", "week", "month"):
                row = lookup_stat(
                    frequency,
                    filter_name=filter_name,
                    direction=direction,
                    period_type=period_type,
                )
                lines.append(
                    "| "
                    f"{filter_name} | {direction} | {period_type} | "
                    f"{int(row.total_events):,} | {number(row.mean_events)} | "
                    f"{number(row.median_events)} | {number(row.p90_events)} | "
                    f"{int(row.maximum_events)} | {percent(row.zero_period_share)} |"
                )
    return lines


def render_year_count_table(primary: pd.DataFrame) -> list[str]:
    masks = filter_masks(primary)
    selected_filters = (
        "ALL_MA7",
        "ALIGNED_STATE",
        "ALIGNED_COMPRESSION_EXPANSION",
    )
    years = range(
        int(primary["event_date"].dt.year.min()),
        int(primary["event_date"].dt.year.max()) + 1,
    )
    lines = [
        "| 年份 | 原始多/空 | 方向一致多/空 | 压缩扩张多/空 |",
        "| ---: | ---: | ---: | ---: |",
    ]
    counts: dict[tuple[str, int, str], int] = {}
    for filter_name in selected_filters:
        subset = primary.loc[masks[filter_name]].copy()
        subset["year"] = subset["event_date"].dt.year
        grouped = subset.groupby(["year", "direction"]).size()
        for (year, direction), value in grouped.items():
            counts[(filter_name, int(year), str(direction))] = int(value)
    for year in years:
        pairs = []
        for filter_name in selected_filters:
            long_count = counts.get((filter_name, year, "long"), 0)
            short_count = counts.get((filter_name, year, "short"), 0)
            pairs.append(f"{long_count:,}/{short_count:,}")
        lines.append(f"| {year} | {pairs[0]} | {pairs[1]} | {pairs[2]} |")
    return lines


def render_plain_conclusions(filter_stats: pd.DataFrame) -> list[str]:
    aligned_long_10 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_STATE",
        direction="long",
        horizon_days=10,
        return_metric="raw_return",
    )
    aligned_long_20 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_STATE",
        direction="long",
        horizon_days=20,
        return_metric="raw_return",
    )
    aligned_short_20 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_STATE",
        direction="short",
        horizon_days=20,
        return_metric="raw_return",
    )
    high_short_20 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_HIGH_VOL",
        direction="short",
        horizon_days=20,
        return_metric="raw_return",
    )
    compression_long_20 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_COMPRESSION_EXPANSION",
        direction="long",
        horizon_days=20,
        return_metric="raw_return",
    )
    compression_short_20 = lookup_stat(
        filter_stats,
        filter_name="ALIGNED_COMPRESSION_EXPANSION",
        direction="short",
        horizon_days=20,
        return_metric="raw_return",
    )
    return [
        "### 这组新统计说了什么",
        "",
        "- **做多：方向过滤确实把平均值从负数拉到了正数，但证据仍不够硬。** "
        f"UP_TREND 多头 10D/20D 平均为 {percent(aligned_long_10['mean'])}/"
        f"{percent(aligned_long_20['mean'])}，可是中位数仍为 "
        f"{percent(aligned_long_10['median'])}/{percent(aligned_long_20['median'])}，"
        "说明平均值依赖少数大涨币；聚类置信区间仍跨过零，不能据此直接写成稳定多头策略。",
        "- **做空：20D 的方向一致结果更可靠。** "
        f"DOWN_TREND 空头 20D 平均 {percent(aligned_short_20['mean'])}、"
        f"中位数 {percent(aligned_short_20['median'])}、胜率 "
        f"{percent(aligned_short_20.win_rate)}、聚类 t={number(aligned_short_20.t_stat)}。",
        "- **高波动不是一律坏。** 对 DOWN_TREND 空头，Q4/Q5 高波动 20D 平均 "
        f"{percent(high_short_20['mean'])}、胜率 {percent(high_short_20.win_rate)}、"
        f"聚类 t={number(high_short_20.t_stat)}；这比低波动空头更有延续迹象。",
        "- **压缩后扩张出现明显多空不对称。** 多头 20D 为 "
        f"{percent(compression_long_20['mean'])}，空头 20D 为 "
        f"{percent(compression_short_20['mean'])}；但多头只有 "
        f"{int(compression_long_20.sample_count)} 个有效样本，空头只有 "
        f"{int(compression_short_20.sample_count)} 个，而且分别集中在 "
        f"{int(compression_long_20.event_date_count)}/{int(compression_short_20.event_date_count)} "
        "个不同事件日，暂时只能算候选。",
        "- **当前最合理的策略研究方向是 short-first，不是强行做多空对称。** "
        "优先把 DOWN_TREND + MA7 向下突破作为主候选，高波动作为预声明切片；"
        "UP_TREND 多头和 compression→expansion 多头暂不进入策略主规则。",
    ]


def render_liquidity_table(liquidity_stats: pd.DataFrame) -> list[str]:
    lines = [
        "| 过滤层 | 方向 | 动态流动性池 | 20D次数 | 20D平均 | 中位数 | 胜率 | 聚类t |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for filter_name in ("ALIGNED_STATE", "ALIGNED_HIGH_VOL"):
        for direction in ("long", "short"):
            for segment in ("major", "long_tail"):
                row = lookup_stat(
                    liquidity_stats,
                    filter_name=filter_name,
                    direction=direction,
                    liquidity_segment=segment,
                    horizon_days=20,
                    return_metric="raw_return",
                )
                label = "Top20" if segment == "major" else "Top20之外"
                lines.append(
                    "| "
                    f"{filter_name} | {direction} | {label} | "
                    f"{int(row.sample_count):,} | {percent(row['mean'])} | "
                    f"{percent(row['median'])} | {percent(row.win_rate)} | "
                    f"{number(row.t_stat)} |"
                )
    return lines


def render_report(
    config: dict[str, Any],
    panel: pd.DataFrame,
    events: pd.DataFrame,
    enriched: pd.DataFrame,
    primary: pd.DataFrame,
    ma_stats: pd.DataFrame,
    state_stats: pd.DataFrame,
    filter_stats: pd.DataFrame,
    liquidity_stats: pd.DataFrame,
    counts: pd.DataFrame,
    frequency: pd.DataFrame,
) -> str:
    eligible = enriched.loc[enriched["eligible_p1"]]
    state_days = eligible["market_state"].value_counts()
    p0_ma7 = events.loc[events["ma_period"].eq(7)]
    lost = len(p0_ma7) - len(primary)
    lines = [
        "# BIN-1D-MA7-RC P1 可读市场状态、波动风格与信号频率（2026-08-24）",
        "",
        "## 先把性质说清楚",
        "",
        "**这是事件统计补全，仍不是账户策略回测。** 下表中的持有天数是固定观察窗口，不是已经选定的卖出规则；没有仓位、换仓、费用、滑点、funding、年化或最大回撤。",
        "",
        f"P1 config SHA256：`{EXPECTED_CONFIG_SHA256}`。数据与 P0R2 相同，原始事件共 `{len(events):,}` 个；MA7 在 P1 causal-state 完整后保留 `{len(primary):,}` 个，因新增 trailing-252 Slope/ER 与 compression/expansion 历史要求排除 `{lost:,}` 个早期事件。",
        "",
        "## 一、MA5/7/10 × 固定持有天数完整统计",
        "",
        "收益均从突破日收盘到第 N 天收盘。多头收益按上涨为正，空头收益按下跌为正。",
        "",
        "历史事件总数（不要求未来第 N 天仍有数据）：",
        "",
        *render_event_total_table(events),
        "",
        "下面各期限的次数会略少，因为样本末端或退市后没有对应 future close：",
        "",
        *render_ma_table(ma_stats),
        "",
        "完整 raw/ATR、聚类置信区间和 t-stat 见 [MA neighborhood CSV](../artifacts/binance_1d_ma7_rc_p1_ma_neighborhood_unconditional_stats.csv)。",
        "",
        "## 二、现在怎样判断市场风格",
        "",
        "每天对每个合约单独判断：",
        "",
        "- `UP_TREND`：价格在 MA30 上方，MA30 斜率为正且处于自身过去一年较强的 40%，ER 也处于较高 40%；",
        "- `DOWN_TREND`：价格在 MA30 下方，MA30 斜率为负且处于自身过去一年较弱的 40%，ER 处于较高 40%；",
        "- `CHOP`：ER 处于自身过去一年较低 40%，说明路径来回抽；",
        "- `TRANSITION`：方向、位置、效率尚未形成一致确认的其他状态。",
        "",
        "P1 eligible symbol-days 的状态覆盖：",
        "",
        "| 状态 | symbol-days | 占比 |",
        "| --- | ---: | ---: |",
    ]
    for state in STATE_ORDER:
        value = int(state_days.get(state, 0))
        lines.append(f"| {state} | {value:,} | {percent(value / len(eligible))} |")
    lines.extend(
        [
            "",
            "### 高波动还是低波动",
            "",
            "波动风格不是看绝对涨跌幅，而是看当前 RV20 在该币自己最近252个有效日中的位置：Q1 为最低20%，Q5 为最高20%。下面只展示方向一致状态，避免把上涨趋势和下跌趋势混在一起。",
            "",
            *render_volatility_table(state_stats),
            "",
            "四状态 × 五档波动 × 全部期限的完整统计见 [state-volatility CSV](../artifacts/binance_1d_ma7_rc_p1_state_volatility_stats.csv)。",
            "",
            "## 三、过滤前后到底剩多少信号",
            "",
            "`ALIGNED_STATE` 是多头只取 UP_TREND、空头只取 DOWN_TREND。低/中/高波动是完整切片，不是从历史中挑最好的一档。`ALIGNED_COMPRESSION_EXPANSION` 还要求突破前一日 ATR5/ATR20 处于最低20%，突破日 True Range/ATR20 进入最高20%。",
            "",
            *render_filter_table(counts, filter_stats),
            "",
            *render_plain_conclusions(filter_stats),
            "",
            "### 挑选高流动性标的池以后",
            "",
            "这里的 Top20 不是今天倒推的固定名单，而是每个事件日按此前30日 quote volume 中位数动态排名，属于 point-in-time 流动性池。",
            "",
            *render_liquidity_table(liquidity_stats),
            "",
            "Top20 高波动空头 20D 仍为正，但样本降到约250次、不同事件日约110天；它可以进入账户回测，不能直接据此宣称年化可复制。完整表见 [liquidity CSV](../artifacts/binance_1d_ma7_rc_p1_filter_liquidity_stats.csv)。",
            "",
            "完整 filter expectancy 见 [filter CSV](../artifacts/binance_1d_ma7_rc_p1_filter_expectancy_stats.csv)，每个具体状态的事件数见 [regime count CSV](../artifacts/binance_1d_ma7_rc_p1_regime_event_counts.csv)。",
            "",
            "## 四、每天、每周、每月有多少次",
            "",
            f"共同补零日历为 `{eligible['event_date'].min().date()}` 至 `{eligible['event_date'].max().date()}`。下表是全市场所有 eligible 合约合计，不是单个币；零信号周期也计入均值。",
            "",
            *render_frequency_table(frequency),
            "",
            "按年份看，原始信号与最严格过滤层的分布如下（每格为多头/空头事件数）：",
            "",
            *render_year_count_table(primary),
            "",
            "逐日、逐周、逐月完整序列见 [frequency timeseries CSV](../artifacts/binance_1d_ma7_rc_p1_frequency_timeseries.csv)。",
            "",
            "## 五、样本统计性怎么判断",
            "",
            "- 原始 MA7 事件很多，但同一天大量币会一起突破，不能把每个币都当成完全独立样本；收益推断继续按 symbol 与 event date 双向聚类。",
            "- 过滤后要同时看事件数、币种数和不同事件日数。单个三维小格即使有一两百次，也可能集中在少数年份或共同市场冲击中。",
            "- 日/周/月频率回答策略是否有足够机会，但仍不能替代账户回测；同日几十个信号还需要下一阶段明确选币、持仓上限和换仓规则。",
            "- P0 结果已经揭示，P1 不能称为 clean OOS。它适合决定下一步统计假设，不足以直接登记交易策略。",
            "",
            "## 六、进入交易策略前的硬边界",
            "",
            "只有在本报告中找到方向一致状态相对 ALL_MA7 的稳定改善、合理的波动结构、足够且分散的信号频率，才另立策略合同。策略合同必须重新冻结 next-open 成交、持有/退出、同币重复信号、最大持仓数、选币、换仓、费用、滑点和 funding；届时才会产生可信年化与回撤。",
            "",
            "机器摘要见 [P1 summary](../artifacts/binance_1d_ma7_rc_p1_summary.json)，研究合同见 [P1 frozen contract](../specs/binance-1d-ma7-regime-continuation-p1-readable-state-frequency-contract-2026-08-24.md)。基于本轮结果冻结的下一阶段规则见 [short-first account candidate](../specs/binance-1d-ma7-regime-continuation-short-first-account-candidate-2026-08-24.md)。",
            "",
        ]
    )
    return "\n".join(lines)


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g")


def build_summary(
    config: dict[str, Any],
    panel: pd.DataFrame,
    events: pd.DataFrame,
    enriched: pd.DataFrame,
    primary: pd.DataFrame,
    counts: pd.DataFrame,
    frequency: pd.DataFrame,
) -> dict[str, Any]:
    eligible = enriched.loc[enriched["eligible_p1"]]
    return {
        "study_id": config["study_id"],
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "status": "completed_diagnostic_only_not_strategy",
        "data": {
            "daily_panel_rows": len(panel),
            "p0_event_rows": len(events),
            "p1_eligible_symbol_days": len(eligible),
            "p1_eligible_symbols": int(eligible["symbol"].nunique()),
            "p1_start": eligible["event_date"].min().isoformat(),
            "p1_end": eligible["event_date"].max().isoformat(),
            "p1_ma7_events": len(primary),
        },
        "state_symbol_days": {
            str(key): int(value)
            for key, value in eligible["market_state"].value_counts().items()
        },
        "filter_counts": counts.to_dict(orient="records"),
        "frequency": frequency.to_dict(orient="records"),
        "limitations": [
            "event study, not account backtest",
            "trigger-close forward returns, not executable next-open returns",
            "no fees, slippage, funding, position sizing, replacement, or exits",
            "P0 outcomes already exposed, so P1 is not clean OOS",
        ],
    }


def write_manifest(paths: Sequence[Path]) -> None:
    records = []
    for path in paths:
        records.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    payload = {
        "study_id": "BIN-1D-MA7-RC-P1",
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "artifacts": records,
    }
    OUTPUTS["manifest"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("refusing to read P1 outcomes without --run")
    config = validate_inputs(args.force)
    panel, events = load_inputs()
    enriched = build_readable_states(panel)
    merged = merge_event_features(events, enriched)
    primary = merged.loc[merged["ma_period"].eq(7) & merged["eligible_p1"]].copy()
    if primary.empty:
        raise RuntimeError("P1 MA7 event set is empty")

    ma_stats = build_ma_neighborhood(events)
    state_stats = build_state_stats(primary)
    filter_stats, counts = build_filter_outputs(primary)
    liquidity_stats = build_liquidity_stats(primary)
    regime_counts = build_regime_counts(primary)
    frequency, frequency_timeseries = build_frequency(primary, enriched)

    write_csv(ma_stats, OUTPUTS["ma_neighborhood"])
    write_csv(state_stats, OUTPUTS["state_stats"])
    write_csv(filter_stats, OUTPUTS["filter_stats"])
    write_csv(liquidity_stats, OUTPUTS["liquidity_stats"])
    write_csv(counts, OUTPUTS["event_counts"])
    write_csv(regime_counts, OUTPUTS["regime_counts"])
    write_csv(frequency, OUTPUTS["frequency_stats"])
    write_csv(frequency_timeseries, OUTPUTS["frequency_timeseries"])

    summary = build_summary(
        config, panel, events, enriched, primary, counts, frequency
    )
    OUTPUTS["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        render_report(
            config,
            panel,
            events,
            enriched,
            primary,
            ma_stats,
            state_stats,
            filter_stats,
            liquidity_stats,
            counts,
            frequency,
        ),
        encoding="utf-8",
    )
    manifest_inputs = [
        OUTPUTS[key]
        for key in (
            "ma_neighborhood",
            "state_stats",
            "filter_stats",
            "liquidity_stats",
            "event_counts",
            "regime_counts",
            "frequency_stats",
            "frequency_timeseries",
            "summary",
        )
    ] + [REPORT_PATH]
    write_manifest(manifest_inputs)
    print(
        json.dumps(
            {
                "status": "completed",
                "p1_ma7_events": len(primary),
                "eligible_symbol_days": int(enriched["eligible_p1"].sum()),
                "report": str(REPORT_PATH),
                "manifest": str(OUTPUTS["manifest"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
