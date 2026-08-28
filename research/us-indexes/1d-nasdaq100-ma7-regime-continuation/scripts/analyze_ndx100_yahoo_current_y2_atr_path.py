from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/us-indexes/1d-nasdaq100-ma7-regime-continuation"
CONFIG_PATH = (
    FAMILY_DIR
    / "configs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path.json"
)
EXPECTED_CONFIG_SHA256 = (
    "58196be62c5b4b2a043c13b9651a73c6dcb6efefcf147700e3f8f71def603305"
)
Y0_SCRIPT = (
    FAMILY_DIR
    / "scripts/research_ndx100_current_yahoo_1d_ma7_regime_continuation.py"
)
BINANCE_FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-regime-continuation"
BINANCE_P2_SCRIPT = (
    BINANCE_FAMILY_DIR / "scripts/analyze_binance_1d_ma7_regime_p2_atr_path.py"
)
BINANCE_STYLE_PATH = (
    BINANCE_FAMILY_DIR / "artifacts/binance_1d_ma7_rc_p2_atr_path_stats.csv"
)
BINANCE_CANDIDATE_PATH = (
    BINANCE_FAMILY_DIR
    / "artifacts/binance_1d_ma7_rc_p2_opposite_cells_robustness.csv"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
REPORT_PATH = (
    FAMILY_DIR
    / "diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-2026-08-25.md"
)

PREFIX = "ndx100_1d_ma7_rc_y2"
STUDY_ID = "NDX100-1D-MA7-RC-Y2"
OUTPUTS = {
    "events": ARTIFACT_DIR / f"{PREFIX}_events.parquet",
    "style_stats": ARTIFACT_DIR / f"{PREFIX}_atr_path_stats.csv",
    "interaction_stats": ARTIFACT_DIR / f"{PREFIX}_atr_path_breakout_stats.csv",
    "filter_stats": ARTIFACT_DIR / f"{PREFIX}_filter_expectancy_stats.csv",
    "filter_counts": ARTIFACT_DIR / f"{PREFIX}_filter_counts.csv",
    "incremental_contrasts": ARTIFACT_DIR
    / f"{PREFIX}_crypto_transfer_incremental_contrasts.csv",
    "comparison_stats": ARTIFACT_DIR / f"{PREFIX}_vs_historical_rv_stats.csv",
    "comparison_diagnostics": ARTIFACT_DIR
    / f"{PREFIX}_vs_historical_rv_diagnostics.csv",
    "robustness_stats": ARTIFACT_DIR / f"{PREFIX}_robustness_stats.csv",
    "candidate_robustness": ARTIFACT_DIR
    / f"{PREFIX}_crypto_transfer_candidate_robustness.csv",
    "cross_market_style": ARTIFACT_DIR
    / f"{PREFIX}_cross_market_atr_path_stats.csv",
    "cross_market_candidates": ARTIFACT_DIR
    / f"{PREFIX}_cross_market_candidate_stats.csv",
    "summary": ARTIFACT_DIR / f"{PREFIX}_summary.json",
    "manifest": ARTIFACT_DIR / f"{PREFIX}_artifact_manifest.json",
}

HORIZONS = (1, 3, 5, 10, 20, 40)
RETURN_METRICS = ("raw_return", "atr_return")
MA_PERIODS = (5, 7, 10)
PRIMARY_MA = 7
FILTER_ORDER = (
    "ALL_MA7",
    "SLOPE_ALIGNED",
    "ALIGNED_CONTRACTION",
    "ALIGNED_STABLE",
    "ALIGNED_EXPANSION",
    "ALIGNED_Q1_FAST_CONTRACTION",
    "ALIGNED_Q5_FAST_EXPANSION",
    "CRYPTO_TRANSFER_DIRECTIONAL_CELL",
)
CANDIDATE_NAMES = {
    "long": "LONG_FAST_EXPANSION_BURST",
    "short": "SHORT_FAST_CONTRACTION_BURST",
}


def load_module(path: Path, name: str, import_dir: Path | None = None) -> Any:
    if import_dir is not None:
        sys.path.insert(0, str(import_dir))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if import_dir is not None:
            sys.path.remove(str(import_dir))


Y0 = load_module(Y0_SCRIPT, "ndx100_y0_for_y2")
P2 = load_module(BINANCE_P2_SCRIPT, "binance_p2_for_ndx_y2", BINANCE_P2_SCRIPT.parent)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run frozen NDX100 Yahoo-current Y2 ATR-path transfer study."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Required acknowledgement that frozen Y2 outcomes will be read.",
    )
    parser.add_argument("--force", action="store_true", help="Replace Y2 outputs.")
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
            f"frozen Y2 config hash mismatch: {actual_hash} != {EXPECTED_CONFIG_SHA256}"
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if config.get("study_id") != STUDY_ID:
        raise RuntimeError("unexpected Y2 study identity")
    if config["external_crypto_hypotheses"]["stock_outcome_parameter_search"]:
        raise RuntimeError("stock outcome parameter search must remain disabled")
    required = [
        Y0.PRICE_PATH,
        Y0.PRICE_AUDIT_PATH,
        Y0.UNIVERSE_PATH,
        BINANCE_STYLE_PATH,
        BINANCE_CANDIDATE_PATH,
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing frozen inputs: {missing}")
    existing = [path for path in [*OUTPUTS.values(), REPORT_PATH] if path.exists()]
    if existing and not force:
        raise FileExistsError("Y2 outputs already exist; pass --force to reproduce")
    return config


def build_stock_panel(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    base_config, yahoo_config = Y0.load_configs()
    bars, qqq, membership, price_audit = Y0.load_yahoo_panel_inputs(
        base_config, yahoo_config
    )
    panel = Y0.KERNEL.prepare_feature_panel(
        bars, membership, qqq, base_config
    ).sort_values(["entity_key", "block_id", "session_date"])
    first_date = panel.groupby(["entity_key", "block_id"], sort=False)[
        "session_date"
    ].transform("min")
    panel["listing_age_days"] = (
        pd.to_datetime(panel["session_date"]) - pd.to_datetime(first_date)
    ).dt.days
    panel["symbol"] = panel["ticker"].astype(str)
    panel["base_asset"] = panel["ticker"].astype(str)
    panel["event_date"] = pd.to_datetime(panel["session_date"], utc=True)
    start = pd.Timestamp(config["data"]["study_start_inclusive"])
    end = pd.Timestamp(config["data"]["study_end_inclusive"])
    panel["y2_study_scope"] = panel["is_member"] & panel["session_date"].between(
        start, end
    )
    panel["is_complete_day"] = True

    enriched = P2.build_feature_panel(panel)
    enriched["eligible_p2_base"] = (
        enriched["eligible_p2_base"] & enriched["y2_study_scope"]
    )
    eligible = enriched.loc[enriched["eligible_p2_base"]]
    enriched["liquidity_rank"] = np.nan
    enriched.loc[eligible.index, "liquidity_rank"] = eligible.groupby("event_date")[
        "adv30_median"
    ].rank(method="first", ascending=False)
    enriched["liquidity_segment"] = np.select(
        [enriched["liquidity_rank"].le(20), enriched["liquidity_rank"].gt(20)],
        ["top20", "other"],
        default="unavailable",
    )
    if enriched.loc[enriched["eligible_p2_base"]].empty:
        raise RuntimeError("Y2 eligible panel is empty")
    return enriched, price_audit


def build_events(panel: pd.DataFrame) -> pd.DataFrame:
    events = P2.build_events(panel)
    events["event_id"] = events["event_id"].str.replace(
        r"^P2\|", "Y2|", regex=True
    )
    return events


def transfer_mask(frame: pd.DataFrame) -> pd.Series:
    return frame["ma_slope_aligned"] & frame["breakout_style"].eq("BURST") & (
        (frame["direction"].eq("long") & frame["atr_path_q"].eq(5))
        | (frame["direction"].eq("short") & frame["atr_path_q"].eq(1))
    )


def filter_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    aligned = frame["ma_slope_aligned"].astype(bool)
    return {
        "ALL_MA7": pd.Series(True, index=frame.index),
        "SLOPE_ALIGNED": aligned,
        "ALIGNED_CONTRACTION": aligned & frame["atr_path_q"].isin([1, 2]),
        "ALIGNED_STABLE": aligned & frame["atr_path_q"].eq(3),
        "ALIGNED_EXPANSION": aligned & frame["atr_path_q"].isin([4, 5]),
        "ALIGNED_Q1_FAST_CONTRACTION": aligned & frame["atr_path_q"].eq(1),
        "ALIGNED_Q5_FAST_EXPANSION": aligned & frame["atr_path_q"].eq(5),
        "CRYPTO_TRANSFER_DIRECTIONAL_CELL": transfer_mask(frame),
    }


def build_filter_outputs(primary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
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
                    "event_count": int(len(directional)),
                    "symbol_count": int(directional["symbol"].nunique()),
                    "event_date_count": int(directional["event_date"].nunique()),
                    "share_of_direction_all": (
                        len(directional) / totals[direction]
                        if totals.get(direction, 0)
                        else np.nan
                    ),
                }
            )
            for stats in P2.calculate_stats(directional):
                stats_rows.append(
                    {"filter_name": filter_name, "direction": direction, **stats}
                )
    return pd.DataFrame(stats_rows), pd.DataFrame(count_rows)


def _cluster_meat(scores: np.ndarray, labels: pd.Series) -> tuple[np.ndarray, int]:
    codes, uniques = pd.factorize(labels, sort=False)
    group_count = len(uniques)
    if group_count < 2:
        return np.full((scores.shape[1], scores.shape[1]), np.nan), group_count
    sums = np.zeros((group_count, scores.shape[1]), dtype=float)
    np.add.at(sums, codes, scores)
    return (group_count / (group_count - 1.0)) * (sums.T @ sums), group_count


def infer_candidate_contrast(
    frame: pd.DataFrame,
    value_column: str,
    candidate: pd.Series,
) -> dict[str, Any]:
    values = frame[value_column].to_numpy(dtype=float)
    indicator = candidate.reindex(frame.index).fillna(False).to_numpy(dtype=bool)
    valid = np.isfinite(values)
    values = values[valid]
    indicator = indicator[valid]
    securities = frame.loc[valid, "symbol"]
    dates = frame.loc[valid, "event_date"]
    count = len(values)
    if count < 3 or indicator.all() or (~indicator).all():
        return {
            "sample_count": count,
            "candidate_count": int(indicator.sum()),
            "reference_count": int((~indicator).sum()),
            "candidate_mean": np.nan,
            "reference_mean": np.nan,
            "incremental_mean": np.nan,
            "cluster_se": np.nan,
            "t_stat": np.nan,
            "ci95_low": np.nan,
            "ci95_high": np.nan,
            "p_value": np.nan,
            "cluster_variance_fallback": False,
        }
    design = np.column_stack([np.ones(count), indicator.astype(float)])
    bread = np.linalg.inv(design.T @ design)
    beta = bread @ design.T @ values
    residual = values - design @ beta
    scores = design * residual[:, None]
    security_meat, security_count = _cluster_meat(scores, securities)
    date_meat, date_count = _cluster_meat(scores, dates)
    observation_meat = count / (count - 1.0) * (scores.T @ scores)
    covariance = bread @ (security_meat + date_meat - observation_meat) @ bread
    variance = float(covariance[1, 1])
    fallback = not np.isfinite(variance) or variance <= 0
    if fallback:
        security_covariance = bread @ security_meat @ bread
        date_covariance = bread @ date_meat @ bread
        variance = max(
            float(security_covariance[1, 1]), float(date_covariance[1, 1])
        )
    standard_error = float(np.sqrt(max(variance, 0.0)))
    incremental = float(beta[1])
    if standard_error > 0:
        t_stat = incremental / standard_error
        p_value = float(math.erfc(abs(t_stat) / np.sqrt(2.0)))
        ci_low = incremental - 1.959963984540054 * standard_error
        ci_high = incremental + 1.959963984540054 * standard_error
    else:
        t_stat = p_value = ci_low = ci_high = np.nan
    return {
        "sample_count": count,
        "candidate_count": int(indicator.sum()),
        "reference_count": int((~indicator).sum()),
        "security_count": int(security_count),
        "event_date_count": int(date_count),
        "candidate_mean": float(values[indicator].mean()),
        "reference_mean": float(values[~indicator].mean()),
        "incremental_mean": incremental,
        "cluster_se": standard_error,
        "t_stat": float(t_stat),
        "ci95_low": float(ci_low),
        "ci95_high": float(ci_high),
        "p_value": float(p_value),
        "cluster_variance_fallback": bool(fallback),
    }


def build_incremental_contrasts(primary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for direction in ("long", "short"):
        directional = primary.loc[primary["direction"].eq(direction)].copy()
        candidate = transfer_mask(directional)
        for reference_name, scope in (
            ("all_other_ma7", pd.Series(True, index=directional.index)),
            ("slope_aligned_other", directional["ma_slope_aligned"] | candidate),
        ):
            scoped = directional.loc[scope]
            scoped_candidate = candidate.loc[scope]
            for horizon in HORIZONS:
                for metric in RETURN_METRICS:
                    rows.append(
                        {
                            "direction": direction,
                            "reference": reference_name,
                            "horizon_days": horizon,
                            "return_metric": metric,
                            **infer_candidate_contrast(
                                scoped,
                                f"{metric}_{horizon}",
                                scoped_candidate,
                            ),
                        }
                    )
    return pd.DataFrame(rows)


def candidate_masks(events: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        CANDIDATE_NAMES["long"]: (
            events["direction"].eq("long")
            & events["ma_slope_aligned"]
            & events["atr_path_q"].eq(5)
            & events["breakout_style"].eq("BURST")
        ),
        CANDIDATE_NAMES["short"]: (
            events["direction"].eq("short")
            & events["ma_slope_aligned"]
            & events["atr_path_q"].eq(1)
            & events["breakout_style"].eq("BURST")
        ),
    }


def build_candidate_robustness(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, mask in candidate_masks(events).items():
        candidate = events.loc[mask]
        primary = candidate.loc[candidate["ma_period"].eq(PRIMARY_MA)]
        slices: list[tuple[str, str, pd.DataFrame]] = [("all", "all", primary)]
        for column, slice_type in (
            ("calendar_year", "calendar_year"),
            ("market_phase", "qqq_market_phase"),
            ("liquidity_segment", "liquidity_segment"),
        ):
            for value, group in primary.groupby(column, dropna=False):
                slices.append((slice_type, str(value), group))
        for value, group in candidate.groupby("ma_period", dropna=False):
            slices.append(("ma_neighborhood", str(value), group))
        for slice_type, slice_value, group in slices:
            for stats in P2.calculate_stats(group):
                rows.append(
                    {
                        "candidate_name": name,
                        "selection_status": "external_crypto_p2_hypothesis_fixed_pre_y2",
                        "slice_type": slice_type,
                        "slice_value": slice_value,
                        **stats,
                    }
                )
    return pd.DataFrame(rows)


def build_robustness(events: pd.DataFrame) -> pd.DataFrame:
    outputs: list[pd.DataFrame] = []
    primary = events.loc[
        events["ma_period"].eq(PRIMARY_MA) & events["ma_slope_aligned"]
    ]
    for slice_type, column in (
        ("calendar_year", "calendar_year"),
        ("qqq_market_phase", "market_phase"),
        ("liquidity_segment", "liquidity_segment"),
    ):
        stats = P2.grouped_stats(
            primary,
            ["direction", column, "atr_path_q", "atr_path_label"],
        ).rename(columns={column: "slice_value"})
        stats["slice_type"] = slice_type
        outputs.append(stats)
    neighborhood = P2.grouped_stats(
        events.loc[events["ma_slope_aligned"]],
        ["direction", "ma_period", "atr_path_q", "atr_path_label"],
    ).rename(columns={"ma_period": "slice_value"})
    neighborhood["slice_type"] = "ma_neighborhood"
    outputs.append(neighborhood)
    return pd.concat(outputs, ignore_index=True)


def cross_market_style(stock_style: pd.DataFrame) -> pd.DataFrame:
    crypto = pd.read_csv(BINANCE_STYLE_PATH)
    keys = [
        "ma_period",
        "direction",
        "ma_slope_aligned",
        "atr_path_q",
        "atr_path_label",
        "horizon_days",
        "return_metric",
    ]
    measures = [
        "sample_count",
        "symbol_count",
        "event_date_count",
        "mean",
        "median",
        "win_rate",
        "t_stat",
        "ci95_low",
        "ci95_high",
    ]
    crypto = crypto.loc[
        crypto["ma_period"].eq(PRIMARY_MA) & crypto["ma_slope_aligned"].eq(True),
        keys + measures,
    ].copy()
    stock = stock_style.loc[
        stock_style["ma_period"].eq(PRIMARY_MA)
        & stock_style["ma_slope_aligned"].eq(True),
        keys + measures,
    ].copy()
    crypto["market"] = "Crypto"
    stock["market"] = "Nasdaq100CurrentYahoo"
    return pd.concat([crypto, stock], ignore_index=True)


def cross_market_candidates(stock_candidates: pd.DataFrame) -> pd.DataFrame:
    crypto = pd.read_csv(BINANCE_CANDIDATE_PATH)
    common_columns = [
        "candidate_name",
        "selection_status",
        "slice_type",
        "slice_value",
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
    ]
    crypto = crypto.loc[crypto["slice_type"].eq("all"), common_columns].copy()
    stock = stock_candidates.loc[
        stock_candidates["slice_type"].eq("all"), common_columns
    ].copy()
    crypto["market"] = "Crypto"
    stock["market"] = "Nasdaq100CurrentYahoo"
    return pd.concat([crypto, stock], ignore_index=True)


def lookup(frame: pd.DataFrame, **conditions: Any) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    for column, value in conditions.items():
        mask &= frame[column].eq(value)
    result = frame.loc[mask]
    if len(result) != 1:
        raise RuntimeError(f"expected one row for {conditions}, got {len(result)}")
    return result.iloc[0]


def percent(value: float) -> str:
    return "NA" if not np.isfinite(value) else f"{value * 100:.2f}%"


def result_cell(row: pd.Series) -> str:
    return (
        f"{int(row['sample_count']):,} / {percent(row['mean'])} / "
        f"{percent(row['median'])} / {percent(row['win_rate'])} / "
        f"t={row['t_stat']:.2f}"
    )


def render_report(
    config: dict[str, Any],
    panel: pd.DataFrame,
    primary: pd.DataFrame,
    style: pd.DataFrame,
    interactions: pd.DataFrame,
    filters: pd.DataFrame,
    contrasts: pd.DataFrame,
    comparison_diagnostics: pd.DataFrame,
    candidates: pd.DataFrame,
    cross_candidates: pd.DataFrame,
) -> str:
    all_rows = {
        direction: lookup(
            filters,
            filter_name="ALL_MA7",
            direction=direction,
            horizon_days=20,
            return_metric="raw_return",
        )
        for direction in ("long", "short")
    }
    candidate_rows = {
        direction: lookup(
            filters,
            filter_name="CRYPTO_TRANSFER_DIRECTIONAL_CELL",
            direction=direction,
            horizon_days=20,
            return_metric="raw_return",
        )
        for direction in ("long", "short")
    }
    style_lines = []
    for q in range(1, 6):
        long_row = lookup(
            style,
            ma_period=7,
            direction="long",
            ma_slope_aligned=True,
            atr_path_q=q,
            horizon_days=20,
            return_metric="raw_return",
        )
        short_row = lookup(
            style,
            ma_period=7,
            direction="short",
            ma_slope_aligned=True,
            atr_path_q=q,
            horizon_days=20,
            return_metric="raw_return",
        )
        style_lines.append(
            f"| Q{q} | {int(long_row['sample_count']):,} / {percent(long_row['mean'])} / {percent(long_row['median'])} | "
            f"{int(short_row['sample_count']):,} / {percent(short_row['mean'])} / {percent(short_row['median'])} |"
        )

    interaction_lines = []
    for direction, q in (("long", 5), ("short", 1)):
        row = lookup(
            interactions,
            direction=direction,
            atr_path_q=q,
            breakout_style="BURST",
            horizon_days=20,
            return_metric="raw_return",
        )
        interaction_lines.append(
            f"| {CANDIDATE_NAMES[direction]} | {result_cell(row)} |"
        )

    phase_lines = []
    for direction in ("long", "short"):
        candidate_name = CANDIDATE_NAMES[direction]
        for phase in ("bull", "bear", "transition"):
            row = lookup(
                candidates,
                candidate_name=candidate_name,
                slice_type="qqq_market_phase",
                slice_value=phase,
                horizon_days=20,
                return_metric="raw_return",
            )
            phase_lines.append(
                f"| {candidate_name} | {phase} | {result_cell(row)} |"
            )

    cross_lines = []
    for candidate_name in CANDIDATE_NAMES.values():
        for market in ("Crypto", "Nasdaq100CurrentYahoo"):
            row = lookup(
                cross_candidates,
                candidate_name=candidate_name,
                market=market,
                horizon_days=20,
                return_metric="raw_return",
            )
            cross_lines.append(
                f"| {candidate_name} | {market} | {result_cell(row)} |"
            )

    diagnostic_lines = []
    for classification in ("ATR_PATH_60", "HISTORICAL_RV_252"):
        for direction in ("long", "short"):
            row = lookup(
                comparison_diagnostics,
                classification=classification,
                direction=direction,
                horizon_days=20,
                return_metric="raw_return",
            )
            diagnostic_lines.append(
                f"| {classification} | {direction} | {percent(row['q5_minus_q1'])} | "
                f"{percent(row['max_minus_min'])} | {row['raw_order_spearman']:.2f} |"
            )

    contrast_lines = []
    for direction in ("long", "short"):
        for horizon in (10, 20, 40):
            row = lookup(
                contrasts,
                direction=direction,
                reference="all_other_ma7",
                horizon_days=horizon,
                return_metric="raw_return",
            )
            contrast_lines.append(
                f"| {direction} | {horizon}D | {percent(row['candidate_mean'])} | "
                f"{percent(row['reference_mean'])} | {percent(row['incremental_mean'])} | "
                f"t={row['t_stat']:.2f} |"
            )

    long_improvement = candidate_rows["long"]["mean"] - all_rows["long"]["mean"]
    short_improvement = candidate_rows["short"]["mean"] - all_rows["short"]["mean"]
    eligible = panel.loc[panel["eligible_p2_base"]]
    return f"""# NDX100-1D-MA7-RC-Y2：Crypto ATR 路径迁移到股票

## 一句话结论

**加密 P2 的两个方向性格子在当前纳指成分股票上{{CONCLUSION}}。** 多头外部格相对裸 MA7 的 20 日均值变化为 `{percent(long_improvement)}`，但 10D/40D 不保持；空头虽然相对裸样本少亏 `{percent(short_improvement)}`，自身 expectancy 仍为负。本轮不根据股票结果换档位或阈值。

## 冻结口径与样本

- Config SHA256：`{EXPECTED_CONFIG_SHA256}`。
- Universe：Yahoo 当前 Nasdaq-100 terminal snapshot `102` 条证券，回填历史，明确 survivorship-biased。
- Eligible：`{len(eligible):,}` security-days、`{eligible['symbol'].nunique():,}` securities，`{eligible['event_date'].min().date()}` 至 `{eligible['event_date'].max().date()}`。
- MA7 events：`{len(primary):,}`；long `{int(primary['direction'].eq('long').sum()):,}`、short `{int(primary['direction'].eq('short').sum()):,}`。
- 完全复制 Crypto P2：ATR20 十日路径、同股 trailing-60 causal quintile、`TR/ATR20[t-1]` 的 0.8/1.2、MA slope aligned。

## 过滤前与外部格

每格为 `样本 / 20D平均 / 中位数 / 胜率 / 双向聚类t`。

| 口径 | long | short |
| --- | ---: | ---: |
| ALL_MA7 | {result_cell(all_rows['long'])} | {result_cell(all_rows['short'])} |
| CRYPTO_TRANSFER_DIRECTIONAL_CELL | {result_cell(candidate_rows['long'])} | {result_cell(candidate_rows['short'])} |

## 外部格相对其余 MA7 事件的增量

每行用事件级回归估计候选格与同方向其余 MA7 事件的均值差，标准误按股票和日期双向聚类。

| 方向 | 周期 | 外部格均值 | 其余事件均值 | 增量 | 增量t |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(contrast_lines)}

## ATR 路径五档

先要求 MA7 slope aligned。每格为 `次数 / 20D平均 / 中位数`；Q1 是最快收缩，Q5 是最快扩张。

| ATR path | long | short |
| --- | ---: | ---: |
{chr(10).join(style_lines)}

## Crypto 预先指定的两个 burst 格

| 外部格 | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | ---: |
{chr(10).join(interaction_lines)}

## QQQ 市场阶段

| 外部格 | QQQ phase | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | --- | ---: |
{chr(10).join(phase_lines)}

## 与 Crypto 直接对照

定义和 20D trigger-close raw return 一致；资产池和交易日结构不同。

| 外部格 | 市场 | 样本 / 20D平均 / 中位数 / 胜率 / t |
| --- | --- | ---: |
{chr(10).join(cross_lines)}

## ATR path 与旧 RV252 的同样本分离度

| 分类 | 方向 | Q5-Q1 | 最大-最小 | Q顺序Spearman |
| --- | --- | ---: | ---: | ---: |
{chr(10).join(diagnostic_lines)}

## 裁决边界

- 这是事件统计，不是账户策略回测；没有 next-open、持仓冲突、费用、分红、借券、退出、年化或回撤。
- Y2 参数来自 Crypto P2，股票结果只做 accept/reject/partial-transfer，不允许挑出股票端最好格另称“优化成功”。
- 历史 PIT Y1 仍因 `81.18%` 覆盖 fail closed；Y2 不能清除当前成分回填的 survivorship bias。

合同：[Y2 ATR path contract](../specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-contract-2026-08-25.md)。
"""


def outcome_conclusion(filters: pd.DataFrame, contrasts: pd.DataFrame) -> str:
    long_deltas = [
        lookup(
            contrasts,
            direction="long",
            reference="all_other_ma7",
            horizon_days=horizon,
            return_metric="raw_return",
        )
        for horizon in (10, 20, 40)
    ]
    short_20 = lookup(
        filters,
        filter_name="CRYPTO_TRANSFER_DIRECTIONAL_CELL",
        direction="short",
        horizon_days=20,
        return_metric="raw_return",
    )
    long_consistent = all(row["incremental_mean"] > 0 for row in long_deltas)
    short_positive = short_20["mean"] > 0 and short_20["t_stat"] >= 1.96
    if long_consistent and short_positive:
        return "形成了双向一致迁移"
    return "未形成稳定可迁移优化：多头仅有20D局部改善，空头方向相反"


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format="%.10g")


def write_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_manifest(paths: Sequence[Path]) -> None:
    payload = {
        "study_id": STUDY_ID,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "artifacts": [
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in paths
        ],
    }
    write_json(payload, OUTPUTS["manifest"])


def main() -> int:
    args = parse_args()
    if not args.run:
        raise SystemExit("refusing to read Y2 outcomes without --run")
    config = validate_inputs(args.force)
    panel, price_audit = build_stock_panel(config)
    events = build_events(panel)
    primary = events.loc[events["ma_period"].eq(PRIMARY_MA)].copy()
    if primary.empty:
        raise RuntimeError("Y2 MA7 events are empty")

    style = P2.build_style_stats(events)
    interactions = P2.build_interaction_stats(primary)
    filters, counts = build_filter_outputs(primary)
    contrasts = build_incremental_contrasts(primary)
    common = primary.loc[
        primary["ma_slope_aligned"] & primary["rv_q_p2_comparison"].notna()
    ].copy()
    comparison = P2.comparison_long_frame(common)
    comparison_diagnostics = P2.build_comparison_diagnostics(common)
    robustness = build_robustness(events)
    candidates = build_candidate_robustness(events)
    cross_style = cross_market_style(style)
    cross_candidates = cross_market_candidates(candidates)

    OUTPUTS["events"].parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(OUTPUTS["events"], index=False)
    for frame, key in (
        (style, "style_stats"),
        (interactions, "interaction_stats"),
        (filters, "filter_stats"),
        (counts, "filter_counts"),
        (contrasts, "incremental_contrasts"),
        (comparison, "comparison_stats"),
        (comparison_diagnostics, "comparison_diagnostics"),
        (robustness, "robustness_stats"),
        (candidates, "candidate_robustness"),
        (cross_style, "cross_market_style"),
        (cross_candidates, "cross_market_candidates"),
    ):
        write_csv(frame, OUTPUTS[key])

    conclusion = outcome_conclusion(filters, contrasts)
    summary = {
        "study_id": STUDY_ID,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "COMPLETED_DIAGNOSTIC_ONLY_SURVIVORSHIP_BIASED",
        "outcome_conclusion": conclusion,
        "data": {
            "price_rows_including_qqq": int(price_audit["rows"]),
            "eligible_security_days": int(panel["eligible_p2_base"].sum()),
            "eligible_securities": int(
                panel.loc[panel["eligible_p2_base"], "symbol"].nunique()
            ),
            "ma7_events": int(len(primary)),
            "ma7_long_events": int(primary["direction"].eq("long").sum()),
            "ma7_short_events": int(primary["direction"].eq("short").sum()),
            "common_atr_path_rv_ma7_aligned_events": int(len(common)),
        },
        "filter_counts": counts.to_dict(orient="records"),
        "limitations": [
            "current Nasdaq-100 constituents applied retrospectively",
            "event study from trigger close, not executable next open",
            "no fees, dividends, borrow, sizing, replacement, or exits",
            "Y2 cannot replace incomplete historical point-in-time Y1",
            "no stock-outcome threshold or cell search",
        ],
    }
    write_json(summary, OUTPUTS["summary"])
    report = render_report(
        config,
        panel,
        primary,
        style,
        interactions,
        filters,
        contrasts,
        comparison_diagnostics,
        candidates,
        cross_candidates,
    ).replace("{CONCLUSION}", conclusion)
    REPORT_PATH.write_text(report, encoding="utf-8")

    manifest_inputs = [
        OUTPUTS[key]
        for key in OUTPUTS
        if key != "manifest"
    ] + [REPORT_PATH]
    write_manifest(manifest_inputs)
    print(json.dumps(summary, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
