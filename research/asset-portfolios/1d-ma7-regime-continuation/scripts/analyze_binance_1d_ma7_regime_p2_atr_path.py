from __future__ import annotations

import argparse
import hashlib
import json
import math
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
CONFIG_PATH = FAMILY_DIR / "configs/binance-1d-ma7-regime-continuation-p2.json"
EXPECTED_CONFIG_SHA256 = (
    "6b3290646d70f8d7717100812e1b858a063abefc9e3d86526e6ef296d69e6295"
)
DAILY_PANEL_PATH = (
    ROOT
    / "data/cache/binance-1d-ma7-rc-p0"
    / "binance_1d_ma7_rc_p0_daily_panel.parquet"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/binance-1d-ma7-regime-continuation-p2-atr-path-2026-08-25.md"
)

OUTPUTS = {
    "events": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_events.parquet",
    "style_stats": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_atr_path_stats.csv",
    "interaction_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p2_atr_path_breakout_stats.csv",
    "filter_stats": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_filter_expectancy_stats.csv",
    "filter_counts": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_filter_counts.csv",
    "frequency_stats": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_frequency_stats.csv",
    "frequency_timeseries": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p2_frequency_timeseries.csv",
    "comparison_stats": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p2_vs_historical_rv_stats.csv",
    "comparison_diagnostics": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p2_vs_historical_rv_diagnostics.csv",
    "robustness_stats": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_robustness_stats.csv",
    "candidate_robustness": ARTIFACT_DIR
    / "binance_1d_ma7_rc_p2_opposite_cells_robustness.csv",
    "summary": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_summary.json",
    "manifest": ARTIFACT_DIR / "binance_1d_ma7_rc_p2_artifact_manifest.json",
}

MA_PERIODS = (5, 7, 10)
PRIMARY_MA = 7
ATR_PATH_WINDOW = 60
ATR_PATH_LABELS = {
    1: "Q1_FAST_CONTRACTION",
    2: "Q2_MILD_CONTRACTION",
    3: "Q3_STABLE",
    4: "Q4_MILD_EXPANSION",
    5: "Q5_FAST_EXPANSION",
}
RV_LABELS = {
    1: "Q1_EXTREME_LOW",
    2: "Q2_LOW",
    3: "Q3_MEDIUM",
    4: "Q4_HIGH",
    5: "Q5_EXTREME_HIGH",
}
BREAKOUT_STYLE_ORDER = ("WEAK", "NORMAL", "BURST")
FILTER_ORDER = (
    "ALL_MA7",
    "SLOPE_ALIGNED",
    "ALIGNED_CONTRACTION",
    "ALIGNED_STABLE",
    "ALIGNED_EXPANSION",
    "ALIGNED_Q1_FAST_CONTRACTION",
    "ALIGNED_Q5_FAST_EXPANSION",
    "ALIGNED_PERSISTENT_CONTRACTION",
    "ALIGNED_PERSISTENT_EXPANSION",
    "HYPOTHESIS_EXTREME_BURST",
    "HYPOTHESIS_PERSISTENT_BURST",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen BIN-1D-MA7-RC-P2 ATR-path event study."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required acknowledgement that P2 outcomes will be read.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing P2 outputs.",
    )
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(force: bool) -> dict[str, Any]:
    actual_hash = sha256_file(CONFIG_PATH)
    if actual_hash != EXPECTED_CONFIG_SHA256:
        raise RuntimeError(
            f"frozen P2 config hash mismatch: {actual_hash} != {EXPECTED_CONFIG_SHA256}"
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != "BIN-1D-MA7-RC-P2":
        raise RuntimeError("unexpected P2 study_id")
    if not DAILY_PANEL_PATH.exists():
        raise FileNotFoundError(f"daily panel is missing: {DAILY_PANEL_PATH}")
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        names = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"P2 outputs already exist; use --force: {names}")
    return config


def require_columns(frame: pd.DataFrame, columns: Sequence[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise RuntimeError(f"{label} missing required columns: {missing}")


def load_daily_panel() -> pd.DataFrame:
    panel = pd.read_parquet(DAILY_PANEL_PATH)
    required = [
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "open",
        "high",
        "low",
        "close",
        "atr14",
        "listing_age_days",
        "market_phase",
        "liquidity_segment",
        "calendar_year",
        "rv_percentile",
        "is_complete_day",
        *[f"sma{period}" for period in MA_PERIODS],
        *[f"future_close_{horizon}" for horizon in HORIZONS],
    ]
    require_columns(panel, required, "daily panel")
    panel["event_date"] = pd.to_datetime(panel["event_date"], utc=True)
    panel = panel.loc[panel["is_complete_day"]].copy()
    panel = panel.sort_values(["symbol", "block_id", "event_date"]).reset_index(
        drop=True
    )
    if panel.duplicated(["symbol", "block_id", "event_date"]).any():
        raise RuntimeError("daily panel has duplicate symbol/block/date keys")
    if panel["event_date"].max() >= pd.Timestamp("2026-07-01T00:00:00Z"):
        raise RuntimeError("daily panel exceeds frozen P2 cutoff")
    return panel


def assign_quintile(percentile: pd.Series) -> pd.Series:
    values = percentile.to_numpy(dtype=float)
    result = np.full(len(values), np.nan, dtype=float)
    valid = np.isfinite(values)
    result[valid] = (
        np.searchsorted(
            np.asarray([0.20, 0.40, 0.60, 0.80]),
            values[valid],
            side="left",
        )
        + 1
    )
    return pd.Series(result, index=percentile.index, dtype="Int64")


def classify_breakout_style(ratio: pd.Series) -> pd.Series:
    values = ratio.to_numpy(dtype=float)
    labels = np.select(
        [values < 0.80, values <= 1.20],
        ["WEAK", "NORMAL"],
        default="BURST",
    ).astype(object)
    labels[~np.isfinite(values)] = pd.NA
    return pd.Series(labels, index=ratio.index, dtype="string")


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
    atr20 = true_range.rolling(20, min_periods=20).mean()
    atr_delta = atr20.diff()
    down_indicator = atr_delta.lt(0).astype(float).where(atr_delta.notna())
    up_indicator = atr_delta.gt(0).astype(float).where(atr_delta.notna())

    block["true_range"] = true_range
    block["atr20"] = atr20
    block["atr20_pre"] = atr20.shift(1)
    block["atr_change_10d_pre"] = atr20.shift(1) / atr20.shift(11) - 1.0
    block["atr_change_percentile_60"] = rolling_percentile_current(
        block["atr_change_10d_pre"].to_numpy(dtype=float), ATR_PATH_WINDOW
    )
    block["atr_down_count_10_pre"] = (
        down_indicator.rolling(10, min_periods=10).sum().shift(1)
    )
    block["atr_up_count_10_pre"] = (
        up_indicator.rolling(10, min_periods=10).sum().shift(1)
    )
    block["breakout_range_ratio"] = true_range / atr20.shift(1).replace(0.0, np.nan)
    block["breakout_style"] = classify_breakout_style(block["breakout_range_ratio"])
    block["atr_path_q"] = assign_quintile(block["atr_change_percentile_60"])
    block["atr_path_label"] = block["atr_path_q"].map(ATR_PATH_LABELS)
    block["persistent_contraction"] = block["atr_path_q"].eq(1) & block[
        "atr_down_count_10_pre"
    ].ge(7)
    block["persistent_expansion"] = block["atr_path_q"].eq(5) & block[
        "atr_up_count_10_pre"
    ].ge(7)
    block["rv_q_p2_comparison"] = assign_quintile(block["rv_percentile"])
    block["rv_label_p2_comparison"] = block["rv_q_p2_comparison"].map(RV_LABELS)
    for period in MA_PERIODS:
        block[f"ma{period}_slope_normalized"] = (
            block[f"sma{period}"] - block[f"sma{period}"].shift(1)
        ) / block["atr20_pre"].replace(0.0, np.nan)

    needed = [
        "atr20_pre",
        "atr_change_10d_pre",
        "atr_change_percentile_60",
        "breakout_range_ratio",
        "atr_path_q",
    ]
    finite = np.isfinite(block[needed].astype(float).to_numpy()).all(axis=1)
    block["eligible_p2_base"] = finite & block["listing_age_days"].ge(120)
    return block


def build_feature_panel(panel: pd.DataFrame) -> pd.DataFrame:
    blocks = [
        enrich_feature_block(group)
        for _, group in panel.groupby(["symbol", "block_id"], sort=False)
    ]
    enriched = pd.concat(blocks, ignore_index=True)
    eligible = enriched.loc[enriched["eligible_p2_base"]]
    if eligible.empty:
        raise RuntimeError("P2 eligible panel is empty")
    if eligible["atr_path_q"].isna().any() or eligible["breakout_style"].isna().any():
        raise RuntimeError("eligible P2 rows have missing style labels")
    if set(eligible["atr_path_q"].astype(int).unique()) != {1, 2, 3, 4, 5}:
        raise RuntimeError("P2 ATR-path quintiles do not cover all five styles")
    return enriched


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    event_frames: list[pd.DataFrame] = []
    grouped = panel.groupby(["symbol", "block_id"], sort=False)
    previous_close = grouped["close"].shift(1)
    identity_columns = [
        "symbol",
        "base_asset",
        "event_date",
        "block_id",
        "close",
        "atr14",
        "atr20_pre",
        "atr_change_10d_pre",
        "atr_change_percentile_60",
        "atr_path_q",
        "atr_path_label",
        "atr_down_count_10_pre",
        "atr_up_count_10_pre",
        "persistent_contraction",
        "persistent_expansion",
        "breakout_range_ratio",
        "breakout_style",
        "rv_percentile",
        "rv_q_p2_comparison",
        "rv_label_p2_comparison",
        "listing_age_days",
        "market_phase",
        "liquidity_segment",
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
        slope_column = f"ma{period}_slope_normalized"
        period_eligible = panel["eligible_p2_base"] & np.isfinite(
            panel[slope_column].to_numpy(dtype=float)
        )
        for direction, trigger, sign in (
            ("long", long_trigger, 1.0),
            ("short", short_trigger, -1.0),
        ):
            mask = trigger & period_eligible
            events = panel.loc[mask, identity_columns].copy()
            events["ma_period"] = period
            events["direction"] = direction
            events["direction_sign"] = sign
            events["trigger_ma"] = panel.loc[mask, f"sma{period}"].to_numpy()
            events["ma_slope_normalized"] = panel.loc[mask, slope_column].to_numpy(
                dtype=float
            )
            events["ma_slope_aligned"] = (
                sign * events["ma_slope_normalized"].to_numpy(dtype=float) > 0.0
            )
            for horizon in HORIZONS:
                future = panel.loc[mask, f"future_close_{horizon}"].to_numpy(
                    dtype=float
                )
                entry = events["close"].to_numpy(dtype=float)
                atr = events["atr14"].to_numpy(dtype=float)
                events[f"raw_return_{horizon}"] = sign * (future / entry - 1.0)
                events[f"atr_return_{horizon}"] = sign * (future - entry) / atr
            events["event_id"] = (
                "P2|MA"
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
        raise RuntimeError("duplicate P2 event identifiers detected")
    if set(result["direction"].unique()) != {"long", "short"}:
        raise RuntimeError("P2 events do not contain both directions")
    return result.sort_values(["ma_period", "event_date", "symbol"]).reset_index(
        drop=True
    )


def calculate_stats(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for metric in RETURN_METRICS:
            column = f"{metric}_{horizon}"
            stats = infer_mean(frame[column], frame["symbol"], frame["event_date"])
            rows.append({"horizon_days": horizon, "return_metric": metric, **stats})
    return rows


def grouped_stats(frame: pd.DataFrame, group_columns: Sequence[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(list(group_columns), dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        identity = dict(zip(group_columns, keys, strict=True))
        for stats in calculate_stats(group):
            rows.append({**identity, **stats})
    return pd.DataFrame(rows)


def build_style_stats(events: pd.DataFrame) -> pd.DataFrame:
    result = grouped_stats(
        events,
        [
            "ma_period",
            "direction",
            "ma_slope_aligned",
            "atr_path_q",
            "atr_path_label",
        ],
    )
    return result.sort_values(
        [
            "ma_period",
            "direction",
            "ma_slope_aligned",
            "atr_path_q",
            "return_metric",
            "horizon_days",
        ]
    ).reset_index(drop=True)


def build_interaction_stats(primary: pd.DataFrame) -> pd.DataFrame:
    aligned = primary.loc[primary["ma_slope_aligned"]].copy()
    result = grouped_stats(
        aligned,
        [
            "direction",
            "atr_path_q",
            "atr_path_label",
            "breakout_style",
        ],
    )
    result["reliable_cell"] = (
        result["sample_count"].ge(100)
        & result["symbol_count"].ge(10)
        & result["event_date_count"].ge(30)
    )
    return result.sort_values(
        [
            "direction",
            "atr_path_q",
            "breakout_style",
            "return_metric",
            "horizon_days",
        ]
    ).reset_index(drop=True)


def filter_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    aligned = frame["ma_slope_aligned"].astype(bool)
    contraction = frame["atr_path_q"].isin([1, 2])
    stable = frame["atr_path_q"].eq(3)
    expansion = frame["atr_path_q"].isin([4, 5])
    burst = frame["breakout_style"].eq("BURST")
    direct_extreme = (frame["direction"].eq("long") & frame["atr_path_q"].eq(1)) | (
        frame["direction"].eq("short") & frame["atr_path_q"].eq(5)
    )
    direct_persistent = (
        frame["direction"].eq("long") & frame["persistent_contraction"]
    ) | (frame["direction"].eq("short") & frame["persistent_expansion"])
    return {
        "ALL_MA7": pd.Series(True, index=frame.index),
        "SLOPE_ALIGNED": aligned,
        "ALIGNED_CONTRACTION": aligned & contraction,
        "ALIGNED_STABLE": aligned & stable,
        "ALIGNED_EXPANSION": aligned & expansion,
        "ALIGNED_Q1_FAST_CONTRACTION": aligned & frame["atr_path_q"].eq(1),
        "ALIGNED_Q5_FAST_EXPANSION": aligned & frame["atr_path_q"].eq(5),
        "ALIGNED_PERSISTENT_CONTRACTION": aligned & frame["persistent_contraction"],
        "ALIGNED_PERSISTENT_EXPANSION": aligned & frame["persistent_expansion"],
        "HYPOTHESIS_EXTREME_BURST": aligned & direct_extreme & burst,
        "HYPOTHESIS_PERSISTENT_BURST": aligned & direct_persistent & burst,
    }


def build_filter_outputs(
    primary: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    stats_rows: list[dict[str, Any]] = []
    count_rows: list[dict[str, Any]] = []
    masks = filter_masks(primary)
    totals = primary.groupby("direction").size().to_dict()
    for filter_name in FILTER_ORDER:
        subset = primary.loc[masks[filter_name]]
        for direction in ("long", "short"):
            directional = subset.loc[subset["direction"].eq(direction)]
            count_rows.append(
                {
                    "filter_name": filter_name,
                    "direction": direction,
                    "event_count": len(directional),
                    "symbol_count": int(directional["symbol"].nunique()),
                    "event_date_count": int(directional["event_date"].nunique()),
                    "share_of_direction_all": (
                        len(directional) / totals[direction]
                        if totals[direction]
                        else np.nan
                    ),
                }
            )
            for stats in calculate_stats(directional):
                stats_rows.append(
                    {"filter_name": filter_name, "direction": direction, **stats}
                )
    stats = pd.DataFrame(stats_rows).sort_values(
        ["filter_name", "direction", "return_metric", "horizon_days"]
    )
    counts = pd.DataFrame(count_rows).sort_values(["filter_name", "direction"])
    return stats.reset_index(drop=True), counts.reset_index(drop=True)


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
    primary: pd.DataFrame, enriched: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = enriched.loc[enriched["eligible_p2_base"]]
    start = eligible["event_date"].min().normalize()
    end = eligible["event_date"].max().normalize()
    calendar = pd.Series(pd.date_range(start, end, freq="D", tz="UTC"))
    masks = filter_masks(primary)
    stats_rows: list[dict[str, Any]] = []
    series_frames: list[pd.DataFrame] = []
    for filter_name in FILTER_ORDER:
        subset = primary.loc[masks[filter_name]]
        for direction in ("long", "short"):
            directional = subset.loc[subset["direction"].eq(direction)]
            for period_type in ("day", "week", "month"):
                grid = pd.DataFrame(
                    {
                        "period_start": period_key(
                            calendar, period_type
                        ).drop_duplicates()
                    }
                )
                event_keys = period_key(directional["event_date"], period_type)
                counts = (
                    event_keys.value_counts()
                    .rename_axis("period_start")
                    .rename("event_count")
                    .reset_index()
                )
                series = grid.merge(counts, on="period_start", how="left")
                series["event_count"] = series["event_count"].fillna(0).astype(int)
                series["filter_name"] = filter_name
                series["direction"] = direction
                series["period_type"] = period_type
                series_frames.append(series)
                values = series["event_count"].to_numpy(dtype=float)
                stats_rows.append(
                    {
                        "filter_name": filter_name,
                        "direction": direction,
                        "period_type": period_type,
                        "period_start": start,
                        "period_end": end,
                        "period_count": len(values),
                        "total_events": int(values.sum()),
                        "mean_events": float(values.mean()),
                        "median_events": float(np.median(values)),
                        "p90_events": float(np.quantile(values, 0.90)),
                        "maximum_events": int(values.max()),
                        "zero_period_share": float((values == 0).mean()),
                    }
                )
    stats = pd.DataFrame(stats_rows).sort_values(
        ["filter_name", "direction", "period_type"]
    )
    timeseries = pd.concat(series_frames, ignore_index=True).sort_values(
        ["filter_name", "direction", "period_type", "period_start"]
    )
    return stats.reset_index(drop=True), timeseries.reset_index(drop=True)


def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_series = pd.Series(np.asarray(left, dtype=float))
    right_series = pd.Series(np.asarray(right, dtype=float))
    valid = left_series.notna() & right_series.notna()
    if valid.sum() < 3:
        return math.nan
    left_rank = left_series.loc[valid].rank(method="average").to_numpy()
    right_rank = right_series.loc[valid].rank(method="average").to_numpy()
    if np.std(left_rank) == 0 or np.std(right_rank) == 0:
        return math.nan
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def comparison_long_frame(common: pd.DataFrame) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    for classification, q_column, label_column in (
        ("ATR_PATH_60", "atr_path_q", "atr_path_label"),
        ("HISTORICAL_RV_252", "rv_q_p2_comparison", "rv_label_p2_comparison"),
    ):
        stats = grouped_stats(common, ["direction", q_column, label_column])
        stats = stats.rename(
            columns={q_column: "group_order", label_column: "group_label"}
        )
        stats["classification"] = classification
        outputs.append(stats)
    return pd.concat(outputs, ignore_index=True).sort_values(
        [
            "classification",
            "direction",
            "return_metric",
            "horizon_days",
            "group_order",
        ]
    )


def _comparison_means(
    frame: pd.DataFrame,
    classification: str,
    direction: str,
    horizon: int,
    metric: str,
) -> pd.DataFrame:
    return frame.loc[
        frame["classification"].eq(classification)
        & frame["direction"].eq(direction)
        & frame["horizon_days"].eq(horizon)
        & frame["return_metric"].eq(metric)
    ].sort_values("group_order")


def build_comparison_diagnostics(common: pd.DataFrame) -> pd.DataFrame:
    full = comparison_long_frame(common)
    period_frames: dict[str, pd.DataFrame] = {}
    for period_name, period_mask in (
        ("pre_2024", common["event_date"].lt(pd.Timestamp("2024-01-01", tz="UTC"))),
        ("post_2024", common["event_date"].ge(pd.Timestamp("2024-01-01", tz="UTC"))),
    ):
        period_frames[period_name] = comparison_long_frame(common.loc[period_mask])
    rows: list[dict[str, Any]] = []
    for classification in ("ATR_PATH_60", "HISTORICAL_RV_252"):
        for direction in ("long", "short"):
            for horizon in HORIZONS:
                for metric in RETURN_METRICS:
                    group = _comparison_means(
                        full, classification, direction, horizon, metric
                    )
                    if set(group["group_order"].astype(int)) != {1, 2, 3, 4, 5}:
                        continue
                    means = group["mean"].to_numpy(dtype=float)
                    pre = _comparison_means(
                        period_frames["pre_2024"],
                        classification,
                        direction,
                        horizon,
                        metric,
                    )
                    post = _comparison_means(
                        period_frames["post_2024"],
                        classification,
                        direction,
                        horizon,
                        metric,
                    )
                    stability = math.nan
                    if len(pre) == 5 and len(post) == 5:
                        stability = _spearman(pre["mean"], post["mean"])
                    expected_means = means[::-1] if direction == "long" else means
                    rows.append(
                        {
                            "classification": classification,
                            "direction": direction,
                            "horizon_days": horizon,
                            "return_metric": metric,
                            "raw_order_spearman": _spearman(range(1, 6), means),
                            "direction_hypothesis_spearman": _spearman(
                                range(1, 6), expected_means
                            ),
                            "q5_minus_q1": float(means[-1] - means[0]),
                            "max_minus_min": float(np.max(means) - np.min(means)),
                            "best_group_order": int(
                                group.iloc[np.argmax(means)]["group_order"]
                            ),
                            "worst_group_order": int(
                                group.iloc[np.argmin(means)]["group_order"]
                            ),
                            "pre_post_2024_rank_correlation": stability,
                            "minimum_group_events": int(group["sample_count"].min()),
                        }
                    )
    return pd.DataFrame(rows).sort_values(
        ["classification", "direction", "return_metric", "horizon_days"]
    )


def build_robustness(events: pd.DataFrame) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    primary = events.loc[
        events["ma_period"].eq(PRIMARY_MA) & events["ma_slope_aligned"]
    ]
    for slice_type, column, subset in (
        ("calendar_year", "calendar_year", primary),
        (
            "btc_market_phase",
            "market_phase",
            primary.loc[primary["market_phase"].notna()],
        ),
        (
            "liquidity_segment",
            "liquidity_segment",
            primary.loc[primary["liquidity_segment"].isin(["major", "long_tail"])],
        ),
    ):
        stats = grouped_stats(
            subset,
            ["direction", column, "atr_path_q", "atr_path_label"],
        ).rename(columns={column: "slice_value"})
        stats["slice_type"] = slice_type
        outputs.append(stats)
    neighborhood = grouped_stats(
        events.loc[events["ma_slope_aligned"]],
        ["direction", "ma_period", "atr_path_q", "atr_path_label"],
    ).rename(columns={"ma_period": "slice_value"})
    neighborhood["slice_type"] = "ma_neighborhood"
    outputs.append(neighborhood)
    return pd.concat(outputs, ignore_index=True).sort_values(
        [
            "slice_type",
            "slice_value",
            "direction",
            "atr_path_q",
            "return_metric",
            "horizon_days",
        ]
    )


def build_opposite_cell_robustness(events: pd.DataFrame) -> pd.DataFrame:
    """Audit the two outcome-exposed opposite cells without promoting them."""
    candidates = {
        "LONG_FAST_EXPANSION_BURST": (
            events["direction"].eq("long")
            & events["ma_slope_aligned"]
            & events["atr_path_q"].eq(5)
            & events["breakout_style"].eq("BURST")
        ),
        "SHORT_FAST_CONTRACTION_BURST": (
            events["direction"].eq("short")
            & events["ma_slope_aligned"]
            & events["atr_path_q"].eq(1)
            & events["breakout_style"].eq("BURST")
        ),
    }
    rows: list[dict[str, Any]] = []
    for candidate_name, mask in candidates.items():
        candidate = events.loc[mask]
        primary = candidate.loc[candidate["ma_period"].eq(PRIMARY_MA)]
        slices: list[tuple[str, str, pd.DataFrame]] = [("all", "all", primary)]
        for column, slice_type in (
            ("calendar_year", "calendar_year"),
            ("market_phase", "btc_market_phase"),
            ("liquidity_segment", "liquidity_segment"),
        ):
            for value, group in primary.groupby(column, dropna=False):
                slices.append((slice_type, str(value), group))
        for value, group in candidate.groupby("ma_period", dropna=False):
            slices.append(("ma_neighborhood", str(value), group))
        for slice_type, slice_value, group in slices:
            for stats in calculate_stats(group):
                rows.append(
                    {
                        "candidate_name": candidate_name,
                        "selection_status": (
                            "post_outcome_opposite_cell_descriptive_only"
                        ),
                        "slice_type": slice_type,
                        "slice_value": slice_value,
                        **stats,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        [
            "candidate_name",
            "slice_type",
            "slice_value",
            "return_metric",
            "horizon_days",
        ]
    )


def lookup_stat(frame: pd.DataFrame, **conditions: Any) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column, value in conditions.items():
        mask &= frame[column].eq(value)
    result = frame.loc[mask]
    if len(result) != 1:
        raise RuntimeError(f"expected one row for {conditions}, got {len(result)}")
    return result.iloc[0]


def percent(value: float, digits: int = 2) -> str:
    return "NA" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def number(value: float, digits: int = 2) -> str:
    return "NA" if not np.isfinite(value) else f"{value:.{digits}f}"


def render_filter_table(counts: pd.DataFrame, stats: pd.DataFrame) -> list[str]:
    selected = (
        "ALL_MA7",
        "SLOPE_ALIGNED",
        "ALIGNED_CONTRACTION",
        "ALIGNED_STABLE",
        "ALIGNED_EXPANSION",
        "HYPOTHESIS_EXTREME_BURST",
        "HYPOTHESIS_PERSISTENT_BURST",
    )
    lines = [
        "| 过滤层 | 方向 | 事件数 | 保留率 | 10D平均/中位/胜率 | 20D平均/中位/胜率 | 20D聚类t |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for filter_name in selected:
        for direction in ("long", "short"):
            count = lookup_stat(counts, filter_name=filter_name, direction=direction)
            ten = lookup_stat(
                stats,
                filter_name=filter_name,
                direction=direction,
                horizon_days=10,
                return_metric="raw_return",
            )
            twenty = lookup_stat(
                stats,
                filter_name=filter_name,
                direction=direction,
                horizon_days=20,
                return_metric="raw_return",
            )
            lines.append(
                f"| {filter_name} | {direction} | {int(count.event_count):,} | "
                f"{percent(count.share_of_direction_all)} | "
                f"{percent(ten['mean'])} / {percent(ten['median'])} / {percent(ten.win_rate)} | "
                f"{percent(twenty['mean'])} / {percent(twenty['median'])} / {percent(twenty.win_rate)} | "
                f"{number(twenty.t_stat)} |"
            )
    return lines


def render_path_table(style_stats: pd.DataFrame) -> list[str]:
    sample = style_stats.loc[
        style_stats["ma_period"].eq(PRIMARY_MA)
        & style_stats["ma_slope_aligned"].eq(True)
        & style_stats["return_metric"].eq("raw_return")
    ]
    lines = [
        "| ATR路径 | 方向 | 10D次数/平均/中位 | 20D次数/平均/中位 | 40D次数/平均/中位 |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for path_q in range(1, 6):
        for direction in ("long", "short"):
            values = []
            for horizon in (10, 20, 40):
                row = lookup_stat(
                    sample,
                    atr_path_q=path_q,
                    direction=direction,
                    horizon_days=horizon,
                )
                values.append(
                    f"{int(row.sample_count):,} / {percent(row['mean'])} / {percent(row['median'])}"
                )
            lines.append(
                f"| {ATR_PATH_LABELS[path_q]} | {direction} | "
                + " | ".join(values)
                + " |"
            )
    return lines


def render_interaction_table(interaction: pd.DataFrame, horizon: int = 20) -> list[str]:
    sample = interaction.loc[
        interaction["return_metric"].eq("raw_return")
        & interaction["horizon_days"].eq(horizon)
    ]
    lines = [
        f"| ATR路径 | 方向 | WEAK {horizon}D | NORMAL {horizon}D | BURST {horizon}D |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for path_q in range(1, 6):
        for direction in ("long", "short"):
            cells = []
            for breakout_style in BREAKOUT_STYLE_ORDER:
                row = lookup_stat(
                    sample,
                    atr_path_q=path_q,
                    direction=direction,
                    breakout_style=breakout_style,
                )
                cells.append(
                    f"{int(row.sample_count):,}次 / {percent(row['mean'])} / t={number(row.t_stat)}"
                )
            lines.append(
                f"| {ATR_PATH_LABELS[path_q]} | {direction} | "
                + " | ".join(cells)
                + " |"
            )
    return lines


def render_comparison_table(comparison: pd.DataFrame, horizon: int = 20) -> list[str]:
    sample = comparison.loc[
        comparison["return_metric"].eq("raw_return")
        & comparison["horizon_days"].eq(horizon)
    ]
    lines = [
        f"| 分法 | 档位 | 多头 {horizon}D次数/平均/中位 | 空头 {horizon}D次数/平均/中位 |",
        "| --- | --- | ---: | ---: |",
    ]
    for classification in ("ATR_PATH_60", "HISTORICAL_RV_252"):
        for order in range(1, 6):
            long = lookup_stat(
                sample,
                classification=classification,
                direction="long",
                group_order=order,
            )
            short = lookup_stat(
                sample,
                classification=classification,
                direction="short",
                group_order=order,
            )
            lines.append(
                f"| {classification} | {long.group_label} | "
                f"{int(long.sample_count):,} / {percent(long['mean'])} / {percent(long['median'])} | "
                f"{int(short.sample_count):,} / {percent(short['mean'])} / {percent(short['median'])} |"
            )
    return lines


def render_frequency_table(frequency: pd.DataFrame) -> list[str]:
    selected = (
        "ALL_MA7",
        "SLOPE_ALIGNED",
        "HYPOTHESIS_EXTREME_BURST",
        "HYPOTHESIS_PERSISTENT_BURST",
    )
    lines = [
        "| 过滤层 | 方向 | 周期 | 总次数 | 平均 | 中位数 | P90 | 零信号占比 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for filter_name in selected:
        for direction in ("long", "short"):
            for period_type in ("day", "week", "month"):
                row = lookup_stat(
                    frequency,
                    filter_name=filter_name,
                    direction=direction,
                    period_type=period_type,
                )
                lines.append(
                    f"| {filter_name} | {direction} | {period_type} | "
                    f"{int(row.total_events):,} | {number(row.mean_events)} | "
                    f"{number(row.median_events)} | {number(row.p90_events)} | "
                    f"{percent(row.zero_period_share)} |"
                )
    return lines


def render_phase_candidate_table(candidate_robustness: pd.DataFrame) -> list[str]:
    sample = candidate_robustness.loc[
        candidate_robustness["slice_type"].eq("btc_market_phase")
        & candidate_robustness["return_metric"].eq("raw_return")
        & candidate_robustness["horizon_days"].eq(20)
    ]
    lines = [
        "| 事后识别的相反组合 | BTC阶段 | 20D次数 | 平均 | 中位数 | 胜率 | 聚类t |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for candidate_name in (
        "LONG_FAST_EXPANSION_BURST",
        "SHORT_FAST_CONTRACTION_BURST",
    ):
        for phase in ("bull", "bear", "transition"):
            row = lookup_stat(sample, candidate_name=candidate_name, slice_value=phase)
            lines.append(
                f"| {candidate_name} | {phase} | {int(row.sample_count):,} | "
                f"{percent(row['mean'])} | {percent(row['median'])} | "
                f"{percent(row.win_rate)} | {number(row.t_stat)} |"
            )
    return lines


def render_report(
    config: dict[str, Any],
    panel: pd.DataFrame,
    enriched: pd.DataFrame,
    events: pd.DataFrame,
    primary: pd.DataFrame,
    style_stats: pd.DataFrame,
    interaction: pd.DataFrame,
    filter_stats: pd.DataFrame,
    filter_counts: pd.DataFrame,
    frequency: pd.DataFrame,
    comparison: pd.DataFrame,
    diagnostics: pd.DataFrame,
    candidate_robustness: pd.DataFrame,
) -> str:
    eligible = enriched.loc[enriched["eligible_p2_base"]]
    common = primary.loc[
        primary["ma_slope_aligned"] & primary["rv_q_p2_comparison"].notna()
    ]
    lines = [
        "# BIN-1D-MA7-RC P2：ATR 路径市场风格统计（2026-08-25）",
        "",
        "## 先说研究性质",
        "",
        "**这是事件统计，不是账户策略回测。** 收益从突破日收盘观察到未来固定日期；没有 next-open、仓位、换仓、费用、滑点、funding、年化或回撤。P2 只回答 ATR 正在下降还是上升，能否帮助过滤 MA 突破。",
        "",
        f"冻结 config SHA256：`{EXPECTED_CONFIG_SHA256}`。日线面板 `{len(panel):,}` 行、{panel['symbol'].nunique():,} 个历史合约；P2 eligible symbol-days `{len(eligible):,}`，从 `{eligible['event_date'].min().date()}` 至 `{eligible['event_date'].max().date()}`。MA7 事件 `{len(primary):,}`，共同 RV252 对比样本（且 MA7 斜率一致）`{len(common):,}`。",
        "",
        "Universe 的精确边界是冻结 P0R2 中全部历史 USDT 本位永续合约标的，没有 crypto-only 或当前成分白名单；它不包含 Binance spot、COIN-M 或 USDC 本位合约。790 个历史合约中，647 个达到 P2 资格，645 个实际产生至少一次 MA7 事件。",
        "",
        "**大白话结论：先过滤市场风格这件事有效，但最初猜的方向不对。** ATR 路径比上一轮历史波动率高低更能把好坏突破分开；真正出现的是“做多偏向 ATR 已快速扩张，做空偏向 ATR 快速收缩”。",
        "",
        "## 一、这轮怎样定义市场",
        "",
        "- 只看突破前：比较昨天 ATR20 与十天前 ATR20，判断市场在收缩还是扩张。",
        "- 再和这个合约最近 60 次同类变化比较：Q1 是收缩最快，Q5 是扩张最快。",
        "- 突破当天 True Range 小于昨日 ATR20 的 0.8 倍叫 WEAK，0.8–1.2 倍叫 NORMAL，大于 1.2 倍叫 BURST。",
        "- 多头要求对应 MA 当天斜率大于零，空头要求小于零；这只是方向确认。",
        "- 最近十次 ATR 日变化至少七次同向，才额外贴“持续收缩/持续扩张”标签。",
        "",
        "## 二、过滤前后总结果",
        "",
        *render_filter_table(filter_counts, filter_stats),
        "",
        "## 三、ATR路径本身的五档结果",
        "",
        "下表已经先要求 MA 斜率与突破方向一致。每格为次数 / 平均收益 / 中位数。",
        "",
        *render_path_table(style_stats),
        "",
        "## 四、再加突破当天是否爆发",
        "",
        "每格为次数 / 20D平均收益 / 双向聚类t。",
        "",
        *render_interaction_table(interaction),
        "",
        "### 这张表最重要的两格",
        "",
        "- 多头：`Q5_FAST_EXPANSION + BURST` 的 MA7 事件，20D 平均 `+6.37%`，但中位数仍为 `-0.53%`、胜率 `48.92%`。它依赖少数大涨行情，不是稳定的普通交易优势。",
        "- 空头：`Q1_FAST_CONTRACTION + BURST` 的 MA7 事件，20D 平均 `+4.89%`、中位数 `+6.88%`、胜率 `67.19%`、聚类 `t=3.28`，样本形状明显更扎实。",
        "- 原假设的多头 `Q1收缩+BURST` 为 `-3.44%`，空头 `Q5扩张+BURST` 为 `-0.23%`；不能按最初故事直接写策略。",
        "",
        "## 五、与上一轮历史波动率分位公平对比",
        "",
        "这里只用同时具备 ATR-path 与 RV252 的完全相同 MA7 斜率一致事件。ATR_PATH_60 的 Q1→Q5 是快速收缩→快速扩张；HISTORICAL_RV_252 的 Q1→Q5 是历史低波动→历史高波动。",
        "",
        *render_comparison_table(comparison),
        "",
        "同样本 20D 上，ATR 路径把多头 Q1 与 Q5 拉开 `8.45` 个百分点，把空头五档最大差拉开 `4.70` 个百分点；旧 RV252 对应差异只有 `1.56` 和 `0.99` 个百分点。ATR 路径在 `10/20D` 更有区分力，到了 `40D` 明显衰减。",
        "",
        "完整的单调性、极端档差异和 2024 前后排序稳定性见 [comparison diagnostics CSV](../artifacts/binance_1d_ma7_rc_p2_vs_historical_rv_diagnostics.csv)。",
        "",
        "## 六、分年份和大盘阶段以后",
        "",
        "五档 ATR 路径的相对排序在 MA5/7/10、动态 Top20/长尾以及大多数年份仍保持：多头 Q5 通常好于 Q1，空头 Q1 通常好于 Q5。不过，正收益是否真正落地仍明显依赖大盘阶段。",
        "",
        *render_phase_candidate_table(candidate_robustness),
        "",
        "这里的两个组合是读取 P2 后才识别出的相反格子，只能作为下一阶段候选，不能冒充预先冻结的策略。多头组合主要在 BTC bull 有效；空头组合在 bear/transition 更强。完整分年、流动性和 MA 邻域见 [opposite-cell robustness CSV](../artifacts/binance_1d_ma7_rc_p2_opposite_cells_robustness.csv)。",
        "",
        "## 七、信号数量",
        "",
        *render_frequency_table(frequency),
        "",
        "## 八、最终研究结论",
        "",
        "1. **验证了“先分市场风格，再看 MA 突破”比裸突破更有信息。** 但有效变量是 ATR 正在怎么走，不只是 ATR 历史上高不高。",
        "2. **推翻了“收缩后向上突破更好、扩张后向下破更好”的具体猜测。** 历史上恰好相反：做多偏扩张，做空偏收缩。",
        "3. **多头证据仍弱于空头。** 多头扩张突破有正均值，但中位数和胜率不漂亮，并且主要依赖 BTC bull；不能仅靠挑币池解决。",
        "4. **空头的收缩后爆发下破更可信。** 它在 MA5/7/10 均保留，10D 分年尤其稳定；20D 总体更高但部分年份失效。",
        "5. **60 日窗口是够用的。** P2 MA7 事件从 P1 的 `74,645` 增至 `97,629`，多 `22,984` 个（约 `30.8%`），同时共同样本比较仍显示 ATR 路径优于 RV252，因此改善不是只靠加入新样本。",
        "",
        "这仍不是可交易策略。下一步若写账户规则，合理候选是：BTC bull 才允许 `long Q5/BURST + MA向上`；BTC bear/transition 才允许 `short Q1/BURST + MA向下`。必须另冻 next-open、持有/退出、同日选币、最大持仓、费用和 funding，再谈年化与回撤。任何单格历史均值再高，都不能直接变成策略参数。完整基础稳健性见 [robustness CSV](../artifacts/binance_1d_ma7_rc_p2_robustness_stats.csv)。",
        "",
        "P2 config：[机器合同](../configs/binance-1d-ma7-regime-continuation-p2.json)；人工合同：[ATR path contract](../specs/binance-1d-ma7-regime-continuation-p2-atr-path-contract-2026-08-25.md)。",
        "",
    ]
    return "\n".join(lines)


def build_summary(
    config: dict[str, Any],
    panel: pd.DataFrame,
    enriched: pd.DataFrame,
    events: pd.DataFrame,
    primary: pd.DataFrame,
    counts: pd.DataFrame,
    diagnostics: pd.DataFrame,
) -> dict[str, Any]:
    eligible = enriched.loc[enriched["eligible_p2_base"]]
    common = primary.loc[
        primary["ma_slope_aligned"] & primary["rv_q_p2_comparison"].notna()
    ]
    focus_diagnostics = diagnostics.loc[
        diagnostics["return_metric"].eq("raw_return")
        & diagnostics["horizon_days"].isin([10, 20, 40])
    ]
    return {
        "study_id": config["study_id"],
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "status": "completed_diagnostic_only_not_strategy",
        "data": {
            "daily_panel_rows": len(panel),
            "daily_panel_symbols": int(panel["symbol"].nunique()),
            "p2_eligible_symbol_days": len(eligible),
            "p2_eligible_symbols": int(eligible["symbol"].nunique()),
            "p2_start": eligible["event_date"].min().isoformat(),
            "p2_end": eligible["event_date"].max().isoformat(),
            "p2_all_ma_events": len(events),
            "p2_ma7_events": len(primary),
            "common_comparison_ma7_slope_aligned_events": len(common),
        },
        "filter_counts": counts.to_dict(orient="records"),
        "comparison_diagnostics_10_20_40d": focus_diagnostics.to_dict(orient="records"),
        "limitations": [
            "event study, not account backtest",
            "trigger-close forward returns, not executable next-open returns",
            "no fees, slippage, funding, position sizing, replacement, or exits",
            "P2 is not clean OOS because prior outcomes are exposed",
            "all classifications remain historical diagnostics, not selected parameters",
        ],
    }


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g")


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
        "study_id": "BIN-1D-MA7-RC-P2",
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "artifacts": records,
    }
    OUTPUTS["manifest"].write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    args = parse_args()
    if not args.run:
        raise SystemExit("refusing to read P2 outcomes without --run")
    config = validate_inputs(args.force)
    panel = load_daily_panel()
    enriched = build_feature_panel(panel)
    events = build_events(enriched)
    primary = events.loc[events["ma_period"].eq(PRIMARY_MA)].copy()
    if primary.empty:
        raise RuntimeError("P2 MA7 event set is empty")

    style_stats = build_style_stats(events)
    interaction = build_interaction_stats(primary)
    filter_stats, filter_counts = build_filter_outputs(primary)
    frequency, frequency_timeseries = build_frequency(primary, enriched)
    common = primary.loc[
        primary["ma_slope_aligned"] & primary["rv_q_p2_comparison"].notna()
    ].copy()
    comparison = comparison_long_frame(common)
    comparison_diagnostics = build_comparison_diagnostics(common)
    robustness = build_robustness(events)
    candidate_robustness = build_opposite_cell_robustness(events)

    OUTPUTS["events"].parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(OUTPUTS["events"], index=False)
    write_csv(style_stats, OUTPUTS["style_stats"])
    write_csv(interaction, OUTPUTS["interaction_stats"])
    write_csv(filter_stats, OUTPUTS["filter_stats"])
    write_csv(filter_counts, OUTPUTS["filter_counts"])
    write_csv(frequency, OUTPUTS["frequency_stats"])
    write_csv(frequency_timeseries, OUTPUTS["frequency_timeseries"])
    write_csv(comparison, OUTPUTS["comparison_stats"])
    write_csv(comparison_diagnostics, OUTPUTS["comparison_diagnostics"])
    write_csv(robustness, OUTPUTS["robustness_stats"])
    write_csv(candidate_robustness, OUTPUTS["candidate_robustness"])

    summary = build_summary(
        config,
        panel,
        enriched,
        events,
        primary,
        filter_counts,
        comparison_diagnostics,
    )
    OUTPUTS["summary"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        render_report(
            config,
            panel,
            enriched,
            events,
            primary,
            style_stats,
            interaction,
            filter_stats,
            filter_counts,
            frequency,
            comparison,
            comparison_diagnostics,
            candidate_robustness,
        ),
        encoding="utf-8",
    )
    manifest_inputs = [
        OUTPUTS[key]
        for key in (
            "events",
            "style_stats",
            "interaction_stats",
            "filter_stats",
            "filter_counts",
            "frequency_stats",
            "frequency_timeseries",
            "comparison_stats",
            "comparison_diagnostics",
            "robustness_stats",
            "candidate_robustness",
            "summary",
        )
    ] + [REPORT_PATH]
    write_manifest(manifest_inputs)
    print(
        json.dumps(
            {
                "status": "completed",
                "p2_ma7_events": len(primary),
                "p2_slope_aligned_ma7_events": int(primary["ma_slope_aligned"].sum()),
                "common_comparison_events": len(common),
                "eligible_symbol_days": int(enriched["eligible_p2_base"].sum()),
                "report": str(REPORT_PATH),
                "manifest": str(OUTPUTS["manifest"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
