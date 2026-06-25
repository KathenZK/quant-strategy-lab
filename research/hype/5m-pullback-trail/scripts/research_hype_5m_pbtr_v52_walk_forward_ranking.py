from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides
from research_hype_5m_pbtr_v5_executable_search import END_TS, V5Config, add_features, simulate_executable
from research_hype_5m_pbtr_v51_event_quality import (
    add_quality_features,
    build_event_frame,
    build_signal,
    filtered_signal,
    num,
    pct,
    simulate_independent_events,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v52_walk_forward_ranking.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v52_walk_forward_ranking_summary.csv")
SEGMENTS_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v52_walk_forward_ranking_segments.csv")
AUDIT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v52_paper_audit_events.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v5-2-walk-forward-ranking-2026-06-24.md"
)

BASE_CFG = V5Config(
    model="observe_then_enter",
    ema_fast=21,
    ema_slow=96,
    pullback_buffer=0.01,
    stop_atr=2.0,
    trail_atr=3.0,
    time_exit_bars=24,
    htf_threshold=None,
    observation_bars=3,
    min_favorable_bps=40.0,
    max_adverse_bps=100.0,
)

WALK_FORWARD_START = pd.Timestamp("2025-09-01T00:00:00Z")
VAL_END = pd.Timestamp("2026-06-01T00:00:00Z")
MIN_TRAIN_EVENTS = 400
BIN_COUNT = 5
SHRINK = 40.0
V51_STATIC_EMA_SPREAD_BPS = 92.9084
V51_STATIC_OPP_WICK_ATR = 0.0

FEATURE_SETS: dict[str, tuple[str, ...]] = {
    "v51_core": (
        "opp_wick_atr",
        "abs_ema_spread_bps",
    ),
    "price_action": (
        "opp_wick_atr",
        "dir_upper_wick_atr",
        "abs_body_atr",
        "range_atr",
        "dist_ema_bps",
        "abs_ema_spread_bps",
    ),
    "trend_context": (
        "opp_wick_atr",
        "abs_ema_spread_bps",
        "htf_spread_bps",
        "regime_age",
        "dir_roc24_bps",
        "dir_roc48_bps",
        "dir_roc96_bps",
        "dir_roc192_bps",
    ),
    "all_liquid": (
        "side",
        "hour",
        "day_of_week",
        "ema_spread_bps",
        "abs_ema_spread_bps",
        "htf_spread_bps",
        "dist_ema_bps",
        "abs_dist_ema_bps",
        "atr_bps",
        "atr_ratio_14_96",
        "chop14",
        "range_atr",
        "abs_body_atr",
        "dir_body_bps",
        "dir_upper_wick_atr",
        "opp_wick_atr",
        "vol_ratio_96",
        "quote_vol_ratio_96",
        "trade_count_ratio_96",
        "regime_age",
        "dir_roc3_bps",
        "dir_roc6_bps",
        "dir_roc12_bps",
        "dir_roc24_bps",
        "dir_roc48_bps",
        "dir_roc96_bps",
        "dir_roc192_bps",
        "dir_roc384_bps",
    ),
}


def build_research_frame() -> pd.DataFrame:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    return add_quality_features(add_features(raw))


def prepare_events(frame: pd.DataFrame, cfg: V5Config) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    trigger, signal = build_signal(frame, cfg)
    events = build_event_frame(frame, cfg, signal)
    independent = simulate_independent_events(frame, signal, cfg)
    events = events.merge(independent, on="idx", how="inner")
    events["signal_ts"] = pd.to_datetime(events["signal_ts"], utc=True)
    return trigger, signal, events


def walk_forward_segments(events: pd.DataFrame, train_mode: str) -> list[dict[str, Any]]:
    data_start = pd.Timestamp(events["signal_ts"].min())
    data_end = pd.Timestamp(events["signal_ts"].max()) + pd.Timedelta(minutes=5)
    starts = pd.date_range(WALK_FORWARD_START, data_end, freq="MS", tz="UTC")
    segments: list[dict[str, Any]] = []
    for idx, test_start in enumerate(starts, start=1):
        test_end = min(test_start + pd.DateOffset(months=1), data_end)
        if test_start >= data_end or test_start >= test_end:
            continue
        if train_mode == "expanding":
            train_start = data_start
        elif train_mode == "trailing_180d":
            train_start = max(data_start, test_start - pd.Timedelta(days=180))
        elif train_mode == "trailing_120d":
            train_start = max(data_start, test_start - pd.Timedelta(days=120))
        elif train_mode == "trailing_90d":
            train_start = max(data_start, test_start - pd.Timedelta(days=90))
        else:
            raise ValueError(f"unknown train_mode={train_mode}")
        train_count = int(((events["signal_ts"] >= train_start) & (events["signal_ts"] < test_start)).sum())
        test_count = int(((events["signal_ts"] >= test_start) & (events["signal_ts"] < test_end)).sum())
        if train_count >= MIN_TRAIN_EVENTS and test_count:
            segments.append(
                {
                    "segment": f"{idx:02d}_{test_start:%Y_%m}",
                    "train_start": train_start,
                    "train_end": test_start,
                    "test_start": test_start,
                    "test_end": test_end,
                    "train_events": train_count,
                    "test_events": test_count,
                }
            )
    return segments


def finite_feature_columns(events: pd.DataFrame, features: tuple[str, ...]) -> list[str]:
    return [feature for feature in features if feature in events.columns and np.isfinite(events[feature].to_numpy("float64")).sum() > 0]


def fit_binned_ranker(train: pd.DataFrame, feature_cols: list[str]) -> dict[str, Any]:
    target = train["event_net_ret_1x"].to_numpy("float64")
    finite_target = target[np.isfinite(target)]
    global_mean = float(finite_target.mean()) if len(finite_target) else 0.0
    model: dict[str, Any] = {"global_mean": global_mean, "features": {}}
    for feature in feature_cols:
        values = train[feature].to_numpy("float64")
        finite = np.isfinite(values) & np.isfinite(target)
        if int(finite.sum()) < MIN_TRAIN_EVENTS // 2:
            continue
        edges = np.unique(np.quantile(values[finite], np.linspace(0.0, 1.0, BIN_COUNT + 1)))
        if len(edges) < 3:
            continue
        train_bins = np.searchsorted(edges[1:-1], values[finite], side="right")
        scores: list[float] = []
        counts: list[int] = []
        for bin_idx in range(len(edges) - 1):
            in_bin = train_bins == bin_idx
            count = int(in_bin.sum())
            counts.append(count)
            if count:
                bin_sum = float(target[finite][in_bin].sum())
                scores.append((bin_sum + SHRINK * global_mean) / (count + SHRINK))
            else:
                scores.append(global_mean)
        model["features"][feature] = {
            "edges": edges.tolist(),
            "scores": scores,
            "counts": counts,
        }
    return model


def score_events(events: pd.DataFrame, model: dict[str, Any]) -> np.ndarray:
    scores = np.full(len(events), float(model["global_mean"]), dtype="float64")
    contributions = np.zeros(len(events), dtype="float64")
    used = np.zeros(len(events), dtype="float64")
    for feature, spec in model["features"].items():
        values = events[feature].to_numpy("float64")
        edges = np.array(spec["edges"], dtype="float64")
        bin_scores = np.array(spec["scores"], dtype="float64")
        finite = np.isfinite(values)
        if not len(bin_scores):
            continue
        bins = np.searchsorted(edges[1:-1], values[finite], side="right")
        contributions[finite] += bin_scores[np.clip(bins, 0, len(bin_scores) - 1)]
        used[finite] += 1.0
    valid = used > 0
    scores[valid] = contributions[valid] / used[valid]
    return scores


def apply_walk_forward_ranker(
    events: pd.DataFrame,
    *,
    feature_set_name: str,
    feature_cols: list[str],
    train_mode: str,
    accept_rate: float,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    audit = events.copy()
    audit["decision"] = "outside_walk_forward"
    audit["reject_reason"] = "outside_walk_forward"
    audit["score"] = np.nan
    audit["score_threshold"] = np.nan
    audit["score_rank_pct_train"] = np.nan
    audit["feature_set"] = feature_set_name
    audit["train_mode"] = train_mode
    audit["accept_rate"] = accept_rate
    audit["segment"] = ""
    for time_column in ("train_start", "train_end", "test_start", "test_end"):
        audit[time_column] = pd.Series(pd.NaT, index=audit.index, dtype="datetime64[ns, UTC]")
    segment_rows: list[dict[str, Any]] = []

    for segment in walk_forward_segments(events, train_mode):
        train_mask = (events["signal_ts"] >= segment["train_start"]) & (events["signal_ts"] < segment["train_end"])
        test_mask = (events["signal_ts"] >= segment["test_start"]) & (events["signal_ts"] < segment["test_end"])
        train = events.loc[train_mask].copy()
        test = events.loc[test_mask].copy()
        model = fit_binned_ranker(train, feature_cols)
        train_scores = score_events(train, model)
        test_scores = score_events(test, model)
        finite_train_scores = train_scores[np.isfinite(train_scores)]
        if len(finite_train_scores) == 0 or not model["features"]:
            threshold = np.inf
        else:
            threshold = float(np.quantile(finite_train_scores, 1.0 - accept_rate))
        accept = np.isfinite(test_scores) & (test_scores >= threshold)
        idx = test.index.to_numpy()
        audit.loc[idx, "score"] = test_scores
        audit.loc[idx, "score_threshold"] = threshold
        audit.loc[idx, "score_rank_pct_train"] = np.searchsorted(np.sort(finite_train_scores), test_scores, side="right") / max(len(finite_train_scores), 1)
        audit.loc[idx, "decision"] = np.where(accept, "accepted_by_ranker", "rejected_by_ranker")
        audit.loc[idx, "reject_reason"] = np.where(accept, "", "score_below_train_threshold")
        audit.loc[idx, "segment"] = segment["segment"]
        audit.loc[idx, "train_start"] = segment["train_start"]
        audit.loc[idx, "train_end"] = segment["train_end"]
        audit.loc[idx, "test_start"] = segment["test_start"]
        audit.loc[idx, "test_end"] = segment["test_end"]
        segment_rows.append(
            {
                **segment,
                "feature_set": feature_set_name,
                "train_mode": train_mode,
                "accept_rate": accept_rate,
                "model_features": len(model["features"]),
                "threshold": threshold,
                "accepted_events": int(accept.sum()),
                "rejected_events": int((~accept).sum()),
                "train_score_mean": float(np.nanmean(train_scores)) if len(train_scores) else 0.0,
                "test_score_mean": float(np.nanmean(test_scores)) if len(test_scores) else 0.0,
            }
        )
    return audit, segment_rows


def selected_signal_from_audit(signal: np.ndarray, audit: pd.DataFrame) -> np.ndarray:
    return filtered_signal(signal, audit, audit["decision"].eq("accepted_by_ranker").to_numpy())


def metric_spans(frame: pd.DataFrame) -> dict[str, tuple[pd.Timestamp, pd.Timestamp]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {
        "calendar_full": (start, end),
        "walk_forward": (WALK_FORWARD_START, end),
        "validation": (WALK_FORWARD_START, VAL_END),
        "forward": (VAL_END, end),
    }


def exact_metric_rows(
    frame: pd.DataFrame,
    selected_signal: np.ndarray,
    cfg: V5Config,
    spans: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    trades, _reason_stats = simulate_executable(frame, selected_signal, cfg)
    summary: dict[str, Any] = {}
    for name, (start, end) in spans.items():
        metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
        for key, value in metrics.items():
            summary[f"{name}_{key}"] = value

    month_rows: list[dict[str, Any]] = []
    current = WALK_FORWARD_START
    end = spans["walk_forward"][1]
    while current < end:
        next_month = min(current + pd.DateOffset(months=1), end)
        metrics = metric_with_sides(trades, LEVERAGE, start=current, end=next_month)
        month_rows.append({"month": current.strftime("%Y-%m"), "start": current, "end": next_month, **metrics})
        current = next_month

    trade_by_signal = {trade.signal_ts: trade for trade in trades}
    traded_signals = {
        int(pd.Timestamp(ts).value)
        for ts in trade_by_signal
    }
    status = {
        "trade_count": len(trades),
        "traded_signal_values": traded_signals,
    }
    return summary, status, month_rows


def static_v51_benchmark(
    frame: pd.DataFrame,
    signal: np.ndarray,
    events: pd.DataFrame,
    cfg: V5Config,
) -> dict[str, Any]:
    keep = (
        (events["opp_wick_atr"].to_numpy("float64") <= V51_STATIC_OPP_WICK_ATR)
        & (events["abs_ema_spread_bps"].to_numpy("float64") <= V51_STATIC_EMA_SPREAD_BPS)
    )
    selected_signal = filtered_signal(signal, events, keep)
    metrics, status, months = exact_metric_rows(frame, selected_signal, cfg, metric_spans(frame))
    return {
        "label": "v5_1_static_threshold_oracle",
        "note": "Fixed thresholds discovered in V5.1; included only as a non-walk-forward benchmark.",
        "selected_events": int(keep.sum()),
        "paper_trades": int(status["trade_count"]),
        "profitable_months": int(sum(float(month["total_return"]) > 0 for month in months)),
        "month_count": len(months),
        **metrics,
    }


def evaluate_config(
    frame: pd.DataFrame,
    cfg: V5Config,
    signal: np.ndarray,
    events: pd.DataFrame,
    *,
    feature_set_name: str,
    train_mode: str,
    accept_rate: float,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    feature_cols = finite_feature_columns(events, FEATURE_SETS[feature_set_name])
    audit, segment_rows = apply_walk_forward_ranker(
        events,
        feature_set_name=feature_set_name,
        feature_cols=feature_cols,
        train_mode=train_mode,
        accept_rate=accept_rate,
    )
    selected_signal = selected_signal_from_audit(signal, audit)
    spans = metric_spans(frame)
    metrics, status, month_rows = exact_metric_rows(frame, selected_signal, cfg, spans)
    accepted_count = int(audit["decision"].eq("accepted_by_ranker").sum())
    traded_values = status["traded_signal_values"]
    audit["paper_order_status"] = np.where(
        audit["decision"].eq("accepted_by_ranker"),
        np.where(audit["signal_ts"].map(lambda ts: int(pd.Timestamp(ts).value)).isin(traded_values), "paper_trade_opened", "blocked_existing_position"),
        "not_submitted",
    )
    row = {
        "label": f"{feature_set_name}_{train_mode}_top{accept_rate:g}",
        "feature_set": feature_set_name,
        "train_mode": train_mode,
        "accept_rate": accept_rate,
        "feature_count": len(feature_cols),
        "candidate_events": int(len(events)),
        "accepted_events": accepted_count,
        "paper_trades": int(status["trade_count"]),
        "accepted_to_trade_ratio": float(status["trade_count"] / max(accepted_count, 1)),
        **asdict(cfg),
        **metrics,
    }
    profitable_months = sum(float(month["total_return"]) > 0 for month in month_rows)
    traded_months = sum(int(month["trades"]) > 0 for month in month_rows)
    row["profitable_months"] = int(profitable_months)
    row["traded_months"] = int(traded_months)
    row["month_count"] = len(month_rows)
    row["min_month_profit_factor_with_trades"] = min(
        (float(month["profit_factor"]) for month in month_rows if int(month["trades"]) > 0),
        default=0.0,
    )
    row["passes_v52_gate"] = (
        int(row["walk_forward_trades"]) >= 100
        and float(row["walk_forward_profit_factor"]) >= 1.15
        and float(row["validation_profit_factor"]) >= 1.05
        and float(row["forward_profit_factor"]) >= 0.90
        and float(row["walk_forward_avg_trade"]) > 0
        and float(row["walk_forward_payoff_ratio"]) > 1.0
        and float(row["walk_forward_max_dd"]) >= -0.25
        and profitable_months >= max(5, len(month_rows) // 2)
    )
    row["watchlist"] = (
        int(row["walk_forward_trades"]) >= 60
        and float(row["walk_forward_profit_factor"]) >= 1.05
        and float(row["walk_forward_avg_trade"]) > 0
        and float(row["walk_forward_max_dd"]) >= -0.30
    )
    row["score"] = (
        min(float(row["walk_forward_profit_factor"]), 3.0) * 100.0
        + min(float(row["validation_profit_factor"]), 3.0) * 60.0
        + min(float(row["forward_profit_factor"]), 3.0) * 30.0
        + float(row["walk_forward_avg_trade"]) * 10000.0
        + min(int(row["walk_forward_trades"]), 240) * 0.25
        + float(row["walk_forward_max_dd"]) * 20.0
        + profitable_months * 3.0
    )
    month_rows = [
        {
            "label": row["label"],
            "feature_set": feature_set_name,
            "train_mode": train_mode,
            "accept_rate": accept_rate,
            **month,
        }
        for month in month_rows
    ]
    return row, audit, segment_rows, month_rows


def render_summary_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    if rows.empty:
        return ["No rows."]
    lines = [
        "| label | events/trades | WF PF | VAL PF | FWD PF | win | payoff | avg | DD | months | accepted->trade |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['accepted_events'])}/{int(row['walk_forward_trades'])}` | "
            f"`{num(float(row['walk_forward_profit_factor']))}` | `{num(float(row['validation_profit_factor']))}` | "
            f"`{num(float(row['forward_profit_factor']))}` | `{pct(float(row['walk_forward_win_rate']))}` | "
            f"`{num(float(row['walk_forward_payoff_ratio']))}` | `{pct(float(row['walk_forward_avg_trade']))}` | "
            f"`{pct(float(row['walk_forward_max_dd']))}` | `{int(row['profitable_months'])}/{int(row['month_count'])}` | "
            f"`{pct(float(row['accepted_to_trade_ratio']), digits=1)}` |"
        )
    return lines


def render_month_table(rows: pd.DataFrame, label: str) -> list[str]:
    selected = rows.loc[rows["label"].eq(label)]
    if selected.empty:
        return ["No month rows."]
    lines = [
        "| month | trades | PF | return | DD | win | payoff | avg |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in selected.to_dict(orient="records"):
        lines.append(
            f"| `{row['month']}` | `{int(row['trades'])}` | `{num(float(row['profit_factor']))}` | "
            f"`{pct(float(row['total_return']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['avg_trade']))}` |"
        )
    return lines


def render_markdown(
    summary: pd.DataFrame,
    month_rows: pd.DataFrame,
    audit: pd.DataFrame | None,
    static_benchmark: dict[str, Any],
) -> str:
    passed = summary.loc[summary["passes_v52_gate"]].sort_values("score", ascending=False)
    watch = summary.loc[summary["watchlist"] & ~summary["passes_v52_gate"]].sort_values("score", ascending=False)
    top = summary.sort_values("score", ascending=False)
    best_label = str(top.iloc[0]["label"]) if len(top) else ""
    lines = [
        "# HYPE-5M-PBTR-V5.2 Walk-Forward Event Ranking 2026-06-24",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "V5.2 keeps the V5.1 observation-confirmed trigger, but replaces fixed hand-picked thresholds with a live-feasible walk-forward ranker. Each monthly test segment is scored using only previous events. The acceptance threshold is the historical train-score quantile, so live execution does not need to know future event counts.",
        "",
        "## Method",
        "",
        "- Base state machine: `observe_then_enter`, EMA `21/96`, `observation_bars=3`, `min_favorable_bps=40`, `max_adverse_bps=100`, `stop_atr=2`, `trail_atr=3`, `time_exit_bars=24`.",
        "- Ranking model: quantile-bin event scorer with shrinkage toward the training mean return.",
        "- Train modes: expanding, trailing `180d`, trailing `120d`, trailing `90d`.",
        "- Acceptance rates: historical train-score top `5%`, `8%`, `10%`, `12%`, `15%`, `20%`.",
        "- Final evaluation: accepted events are converted back to signals and replayed through the exact executable state machine, including overlap blocking.",
        "",
        "## V5.2 Gate",
        "",
        "- Walk-forward trades `>=100`.",
        "- Walk-forward PF `>=1.15`.",
        "- Validation PF `>=1.05`.",
        "- Forward PF `>=0.90`.",
        "- Average trade `>0`, payoff `>1`, max drawdown no worse than `-25%`.",
        "- Profitable months at least half of walk-forward months.",
        "",
        "## Passing Rows",
        "",
        *render_summary_table(passed, limit=12),
        "",
        "## Watchlist",
        "",
        *render_summary_table(watch, limit=12),
        "",
        "## Top Rows",
        "",
        *render_summary_table(top, limit=12),
        "",
        "## Fixed V5.1 Benchmark",
        "",
        "This row uses the V5.1 fixed thresholds discovered with hindsight. It is not walk-forward-ranked, so it is a benchmark for edge decay rather than a deployable model-selection process.",
        "",
        "| label | events/trades | WF PF | VAL PF | FWD PF | win | payoff | avg | DD | months |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{static_benchmark['label']}` | `{int(static_benchmark['selected_events'])}/{int(static_benchmark['walk_forward_trades'])}` | "
        f"`{num(float(static_benchmark['walk_forward_profit_factor']))}` | `{num(float(static_benchmark['validation_profit_factor']))}` | "
        f"`{num(float(static_benchmark['forward_profit_factor']))}` | `{pct(float(static_benchmark['walk_forward_win_rate']))}` | "
        f"`{num(float(static_benchmark['walk_forward_payoff_ratio']))}` | `{pct(float(static_benchmark['walk_forward_avg_trade']))}` | "
        f"`{pct(float(static_benchmark['walk_forward_max_dd']))}` | `{int(static_benchmark['profitable_months'])}/{int(static_benchmark['month_count'])}` |",
        "",
        "## Best Row Monthly Breakdown",
        "",
        *render_month_table(month_rows, best_label),
        "",
        "## Paper Audit Output",
        "",
    ]
    if audit is not None and len(audit):
        accepted = int(audit["decision"].eq("accepted_by_ranker").sum())
        opened = int(audit["paper_order_status"].eq("paper_trade_opened").sum())
        blocked = int(audit["paper_order_status"].eq("blocked_existing_position").sum())
        rejected = int(audit["decision"].eq("rejected_by_ranker").sum())
        lines.extend(
            [
                f"The audit CSV logs every observation-confirmed event for the best row: `{accepted}` accepted, `{opened}` paper trades opened, `{blocked}` accepted events blocked by an existing paper position, and `{rejected}` rejected by score threshold.",
                "",
                "Required live paper-audit fields are present: `signal_ts`, `side`, `segment`, `train_start`, `train_end`, `test_start`, `test_end`, `score`, `score_threshold`, `score_rank_pct_train`, `decision`, `reject_reason`, and `paper_order_status`.",
            ]
        )
    else:
        lines.append("No audit rows were generated.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
        ]
    )
    if len(passed):
        best = passed.iloc[0]
        lines.extend(
            [
                f"`{best['label']}` passes the mechanical V5.2 gate. It is still a paper-audit candidate, not a real-money live spec, because the ranking approach is newly introduced and must prove online rejection/acceptance behavior without retrospective tuning.",
            ]
        )
    elif len(watch):
        best = watch.iloc[0]
        lines.extend(
            [
                f"No row passes the V5.2 gate. The closest watchlist row is `{best['label']}` with walk-forward PF `{num(float(best['walk_forward_profit_factor']))}`, validation PF `{num(float(best['validation_profit_factor']))}`, forward PF `{num(float(best['forward_profit_factor']))}`, and max DD `{pct(float(best['walk_forward_max_dd']))}`.",
                "",
                "This is evidence for continuing paper-audit research, not for live trading.",
            ]
        )
    else:
        lines.append("No row is strong enough for watchlist. V5.2 should not proceed to paper deployment without a different ranker or feature family.")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- Script: `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v52_walk_forward_ranking.py`",
            f"- JSON: `{REPORT_PATH}`",
            f"- Summary CSV: `{SUMMARY_PATH}`",
            f"- Segment CSV: `{SEGMENTS_PATH}`",
            f"- Paper audit CSV: `{AUDIT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = build_research_frame()
    _trigger, signal, events = prepare_events(frame, BASE_CFG)
    benchmark = static_v51_benchmark(frame, signal, events, BASE_CFG)
    summary_rows: list[dict[str, Any]] = []
    segment_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    audits: dict[str, pd.DataFrame] = {}
    for feature_set in FEATURE_SETS:
        for train_mode in ("expanding", "trailing_180d", "trailing_120d", "trailing_90d"):
            for accept_rate in (0.05, 0.08, 0.10, 0.12, 0.15, 0.20):
                row, audit, segments, months = evaluate_config(
                    frame,
                    BASE_CFG,
                    signal,
                    events,
                    feature_set_name=feature_set,
                    train_mode=train_mode,
                    accept_rate=accept_rate,
                )
                summary_rows.append(row)
                segment_rows.extend([{**item, "label": row["label"]} for item in segments])
                month_rows.extend(months)
                audits[row["label"]] = audit
                print(f"finished {row['label']} trades={row['walk_forward_trades']} pf={row['walk_forward_profit_factor']:.3f}", flush=True)

    summary = pd.DataFrame(summary_rows).sort_values("score", ascending=False)
    segments = pd.DataFrame(segment_rows)
    months = pd.DataFrame(month_rows)
    best_label = str(summary.iloc[0]["label"])
    best_audit = audits[best_label].copy()
    best_audit = best_audit.sort_values("signal_ts")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    segments.to_csv(SEGMENTS_PATH, index=False)
    best_audit.to_csv(AUDIT_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, months, best_audit, benchmark), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "base_config": asdict(BASE_CFG),
                "static_v51_benchmark": benchmark,
                "summary": summary_rows,
                "segments": segment_rows,
                "months": month_rows,
                "best_label": best_label,
                "outputs": {
                    "summary_csv": str(SUMMARY_PATH),
                    "segments_csv": str(SEGMENTS_PATH),
                    "paper_audit_csv": str(AUDIT_PATH),
                    "markdown": str(MARKDOWN_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"tested={len(summary)} passes={int(summary['passes_v52_gate'].sum())} watch={int(summary['watchlist'].sum())}")
    print(f"wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
