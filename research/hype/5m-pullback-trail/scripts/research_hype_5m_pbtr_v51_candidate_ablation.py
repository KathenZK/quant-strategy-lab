from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v5_executable_search import END_TS, V5Config, add_features
from research_hype_5m_pbtr_v51_event_quality import (
    add_quality_features,
    build_signal,
    exact_metrics,
    filtered_signal,
    num,
    pct,
    spans,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v51_candidate_ablation.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v51_candidate_ablation_summary.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v5-1-candidate-ablation-2026-06-24.md"
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
BASE_EMA_SPREAD_BPS = 92.9084
BASE_OPP_WICK_ATR = 0.0


def build_event_frame(frame: pd.DataFrame, cfg: V5Config, signal: np.ndarray) -> pd.DataFrame:
    sig_idx = np.flatnonzero(signal)
    side = signal[sig_idx].astype("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    spread = ema_fast - ema_slow
    return pd.DataFrame(
        {
            "idx": sig_idx,
            "side": side,
            "ema_spread_bps": side * spread[sig_idx] / close[sig_idx] * 10000.0,
            "abs_ema_spread_bps": np.abs(spread[sig_idx] / close[sig_idx] * 10000.0),
            "opp_wick_atr": np.where(
                side > 0,
                frame["lower_wick_atr"].to_numpy("float64")[sig_idx],
                frame["upper_wick_atr"].to_numpy("float64")[sig_idx],
            ),
        }
    )


def make_mask(events: pd.DataFrame, ema_spread_bps: float | None, opp_wick_atr: float | None) -> np.ndarray:
    mask = np.ones(len(events), dtype=bool)
    if ema_spread_bps is not None:
        mask &= events["abs_ema_spread_bps"].to_numpy("float64") <= ema_spread_bps
    if opp_wick_atr is not None:
        mask &= events["opp_wick_atr"].to_numpy("float64") <= opp_wick_atr
    return mask


def prepare_config(frame: pd.DataFrame, cfg: V5Config) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    trigger, signal = build_signal(frame, cfg)
    events = build_event_frame(frame, cfg, signal)
    return trigger, signal, events


def classify(row: dict[str, Any]) -> tuple[bool, bool]:
    candidate = (
        int(row["full_trades"]) >= 180
        and int(row["is_trades"]) >= 80
        and int(row["val_trades"]) >= 30
        and int(row["fwd_trades"]) >= 8
        and float(row["full_profit_factor"]) >= 1.25
        and float(row["is_profit_factor"]) >= 1.15
        and float(row["val_profit_factor"]) >= 1.05
        and float(row["fwd_profit_factor"]) >= 1.0
        and float(row["full_avg_trade"]) > 0
        and float(row["full_payoff_ratio"]) > 1.0
        and float(row["full_max_dd"]) >= -0.25
    )
    watch = (
        int(row["full_trades"]) >= 120
        and int(row["is_trades"]) >= 60
        and int(row["val_trades"]) >= 20
        and float(row["full_profit_factor"]) >= 1.15
        and float(row["is_profit_factor"]) >= 1.10
        and float(row["val_profit_factor"]) >= 1.0
        and float(row["full_avg_trade"]) > 0
        and float(row["full_max_dd"]) >= -0.20
    )
    return candidate, watch


def eval_prepared(
    frame: pd.DataFrame,
    span_items: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
    cfg: V5Config,
    trigger: np.ndarray,
    signal: np.ndarray,
    events: pd.DataFrame,
    ema_spread_bps: float | None,
    opp_wick_atr: float | None,
    label: str,
) -> dict[str, Any]:
    mask = make_mask(events, ema_spread_bps, opp_wick_atr)
    selected = filtered_signal(signal, events, mask)
    row: dict[str, Any] = {
        "label": label,
        "config_label": cfg.label,
        "ema_spread_bps_threshold": ema_spread_bps,
        "opp_wick_atr_threshold": opp_wick_atr,
        "trigger_count": int(np.count_nonzero(trigger)),
        "signal_count": int(np.count_nonzero(signal)),
        "selected_event_count": int(mask.sum()),
        **asdict(cfg),
        **exact_metrics(frame, selected, cfg, span_items),
    }
    row["full_trades_per_month"] = float(row["full_trades"]) / max(
        (span_items["full"][1] - span_items["full"][0]).days / 30.4375,
        1.0,
    )
    row["passes_candidate_gate"], row["watchlist"] = classify(row)
    row["score"] = (
        min(float(row["full_profit_factor"]), 3.0) * 80.0
        + min(float(row["val_profit_factor"]), 3.0) * 60.0
        + min(float(row["fwd_profit_factor"]), 3.0) * 25.0
        + float(row["full_avg_trade"]) * 10000.0
        + min(int(row["full_trades"]), 260) * 0.2
        + float(row["full_max_dd"]) * 20.0
    )
    return row


def eval_variant(
    frame: pd.DataFrame,
    span_items: dict[str, tuple[pd.Timestamp, pd.Timestamp]],
    cfg: V5Config,
    ema_spread_bps: float | None,
    opp_wick_atr: float | None,
    label: str,
) -> dict[str, Any]:
    trigger, signal, events = prepare_config(frame, cfg)
    return eval_prepared(frame, span_items, cfg, trigger, signal, events, ema_spread_bps, opp_wick_atr, label)


def ablation_rows(frame: pd.DataFrame, span_items: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> list[dict[str, Any]]:
    rows = [
        eval_variant(frame, span_items, BASE_CFG, BASE_EMA_SPREAD_BPS, BASE_OPP_WICK_ATR, "base_full_rule"),
        eval_variant(frame, span_items, BASE_CFG, None, BASE_OPP_WICK_ATR, "remove_ema_spread_filter"),
        eval_variant(frame, span_items, BASE_CFG, BASE_EMA_SPREAD_BPS, None, "remove_opp_wick_filter"),
        eval_variant(frame, span_items, BASE_CFG, None, None, "remove_both_filters"),
    ]
    for ema_threshold in (68.2164, 82.0, 92.9084, 102.193, 112.688, 127.3):
        rows.append(eval_variant(frame, span_items, BASE_CFG, ema_threshold, BASE_OPP_WICK_ATR, f"ema_{ema_threshold:g}_opp_base"))
    for wick_threshold in (0.0, 0.0133374, 0.05, 0.10, 0.190384, 0.4439):
        rows.append(eval_variant(frame, span_items, BASE_CFG, BASE_EMA_SPREAD_BPS, wick_threshold, f"ema_base_opp_{wick_threshold:g}"))
    return rows


def grid_rows(frame: pd.DataFrame, span_items: dict[str, tuple[pd.Timestamp, pd.Timestamp]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation_bars in (1, 3, 6):
        for min_favorable_bps in (20.0, 40.0, 60.0):
            for max_adverse_bps in (100.0, 200.0):
                for stop_atr in (1.5, 2.0, 2.5):
                    for trail_atr in (2.0, 3.0, 4.0):
                        for time_exit_bars in (24, 48):
                            cfg = replace(
                                BASE_CFG,
                                observation_bars=observation_bars,
                                min_favorable_bps=min_favorable_bps,
                                max_adverse_bps=max_adverse_bps,
                                stop_atr=stop_atr,
                                trail_atr=trail_atr,
                                time_exit_bars=time_exit_bars,
                            )
                            trigger, signal, events = prepare_config(frame, cfg)
                            for ema_threshold in (68.2164, 82.0, 92.9084, 102.193, 112.688, 127.3):
                                for wick_threshold in (0.0, 0.0133374, 0.05, 0.10, 0.190384):
                                    label = (
                                        f"grid_obs{observation_bars}_fav{min_favorable_bps:g}_adv{max_adverse_bps:g}"
                                        f"_sl{stop_atr:g}_tr{trail_atr:g}_tx{time_exit_bars}"
                                        f"_ema{ema_threshold:g}_opp{wick_threshold:g}"
                                    )
                                    rows.append(
                                        eval_prepared(
                                            frame,
                                            span_items,
                                            cfg,
                                            trigger,
                                            signal,
                                            events,
                                            ema_threshold,
                                            wick_threshold,
                                            label,
                                        )
                                    )
    return rows


def render_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    if rows.empty:
        return ["No rows."]
    lines = [
        "| label | obs/fav/stop/trail/time | filters | trades | PF | IS | VAL | FWD | win | payoff | avg | DD | freq/mo |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        ema = "none" if pd.isna(row["ema_spread_bps_threshold"]) else f"{float(row['ema_spread_bps_threshold']):g}"
        wick = "none" if pd.isna(row["opp_wick_atr_threshold"]) else f"{float(row['opp_wick_atr_threshold']):g}"
        lines.append(
            f"| `{row['label']}` | `{int(row['observation_bars'])}/{float(row['min_favorable_bps']):g}/"
            f"{float(row['stop_atr']):g}/{float(row['trail_atr']):g}/{int(row['time_exit_bars'])}` | "
            f"`ema<={ema}, wick<={wick}` | `{int(row['full_trades'])}` | "
            f"`{num(float(row['full_profit_factor']))}` | `{num(float(row['is_profit_factor']))}` | "
            f"`{num(float(row['val_profit_factor']))}` | `{num(float(row['fwd_profit_factor']))}` | "
            f"`{pct(float(row['full_win_rate']))}` | `{num(float(row['full_payoff_ratio']))}` | "
            f"`{pct(float(row['full_avg_trade']))}` | `{pct(float(row['full_max_dd']))}` | "
            f"`{float(row['full_trades_per_month']):.1f}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame) -> str:
    ablation = summary.loc[summary["label"].str.startswith(("base_", "remove_", "ema_"))].copy()
    passed = summary.loc[summary["passes_candidate_gate"]].sort_values("score", ascending=False)
    watch = summary.loc[summary["watchlist"] & ~summary["passes_candidate_gate"]].sort_values("score", ascending=False)
    top = summary.sort_values("score", ascending=False)
    lines = [
        "# HYPE-5M-PBTR-V5.1 Candidate Ablation 2026-06-24",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "This report stress-tests the first V5.1 event-quality candidate instead of promoting it directly. The candidate keeps the pullback trigger, uses observation-then-entry, and filters confirmed signals by no adverse wick plus moderate EMA spread.",
        "",
        "## Base Rule",
        "",
        "- State machine: `observe_then_enter`, EMA `21/96`, `observation_bars=3`, `min_favorable_bps=40`, `max_adverse_bps=100`, `stop_atr=2`, `trail_atr=3`, `time_exit_bars=24`.",
        f"- Quality filter: `opp_wick_atr <= {BASE_OPP_WICK_ATR:g}` and `abs_ema_spread_bps <= {BASE_EMA_SPREAD_BPS:g}`.",
        "",
        "## Candidate Gate Results",
        "",
        f"- Tested rows: `{len(summary)}`.",
        f"- Passing rows: `{int(summary['passes_candidate_gate'].sum())}`.",
        f"- Watchlist rows: `{int(summary['watchlist'].sum())}`.",
        "",
        "## Direct Ablation",
        "",
        *render_table(ablation.sort_values("score", ascending=False), limit=20),
        "",
        "## Passing Rows",
        "",
        *render_table(passed, limit=20),
        "",
        "## Watchlist Rows",
        "",
        *render_table(watch, limit=20),
        "",
        "## Top Rows By Inspection Score",
        "",
        *render_table(top, limit=20),
        "",
        "## Interpretation",
        "",
    ]
    if len(passed):
        best = passed.iloc[0]
        lines.extend(
            [
                "The V5.1 signal-quality idea survives the first ablation pass, but only with a narrow edge. The pass set is clustered around the same feature family: moderate EMA spread and very small/no adverse wick after observation confirmation.",
                "",
                f"The top passing row is `{best['label']}` with PF `{num(float(best['full_profit_factor']))}`, validation PF `{num(float(best['val_profit_factor']))}`, forward PF `{num(float(best['fwd_profit_factor']))}`, average trade `{pct(float(best['full_avg_trade']))}`, and max drawdown `{pct(float(best['full_max_dd']))}`.",
            ]
        )
    else:
        lines.append("The base candidate did not survive ablation. It should be treated as a mined artifact, not a strategy.")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Do not send V5.1 to real-money execution yet. It is now a legitimate research candidate, not a live strategy. The next required step is rolling-window / month-by-month diagnostics and a paper-live spec that records every rejected trigger so the quality filter can be audited online.",
            "",
            "## Outputs",
            "",
            "- Script: `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v51_candidate_ablation.py`",
            f"- JSON: `{REPORT_PATH}`",
            f"- Summary CSV: `{SUMMARY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_quality_features(add_features(raw))
    span_items = spans(frame)
    rows = ablation_rows(frame, span_items)
    rows.extend(grid_rows(frame, span_items))
    summary = pd.DataFrame(rows).sort_values("score", ascending=False)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "rows": rows,
                "outputs": {
                    "summary_csv": str(SUMMARY_PATH),
                    "markdown": str(MARKDOWN_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"tested={len(summary)} passes={int(summary['passes_candidate_gate'].sum())} watch={int(summary['watchlist'].sum())}")
    print(f"wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
