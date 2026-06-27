from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
MICRO_SCRIPT_DIR = THIS_DIR.parent.parent / "5m-micro-scalp" / "scripts"
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(MICRO_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(MICRO_SCRIPT_DIR))

from research_hype_5m_seeded_event_quality_v0 import (  # noqa: E402
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    RUN_DATE,
    build_seed_events,
    pct,
    select_seed_configs,
    serializable,
    validate_and_load,
)
from research_hype_5m_seeded_event_quality_v01_style_prune import (  # noqa: E402
    LOOKBACK_DAYS,
    PURGE,
    STYLE_SETS,
    candidate_metrics,
    segment_bounds,
)
from research_hype_5m_micro_scalp_search import add_features  # type: ignore[reportMissingImports]  # noqa: E402


QUANTILES = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95)
SCORE_VARIANTS: dict[str, tuple[float, float, float]] = {
    "current_70_20_10": (0.70, 0.20, 0.10),
    "cfg_only": (1.00, 0.00, 0.00),
    "style_only": (0.00, 1.00, 0.00),
    "side_only": (0.00, 0.00, 1.00),
    "cfg_style_78_22": (0.70 / 0.90, 0.20 / 0.90, 0.00),
    "cfg_side_88_12": (0.70 / 0.80, 0.00, 0.10 / 0.80),
    "equal_weight": (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
}

REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_{RUN_DATE}.json"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_summary_{RUN_DATE}.csv"
WINDOWS_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_windows_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_monthly_{RUN_DATE}.csv"
TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-event-quality-v01-full-ablation-{RUN_DATE}.md"


def weighted_score(
    frame: pd.DataFrame,
    cfg_mean: pd.Series,
    style_mean: pd.Series,
    side_mean: pd.Series,
    global_mean: float,
    weights: tuple[float, float, float],
) -> pd.Series:
    cfg_w, style_w, side_w = weights
    return (
        cfg_w * frame["cfg_name"].map(cfg_mean).fillna(global_mean)
        + style_w * frame["style"].map(style_mean).fillna(global_mean)
        + side_w * frame["side"].map(side_mean).fillna(global_mean)
    )


def score_style_set(events: pd.DataFrame, style_set: str, allowed_styles: tuple[str, ...], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    allowed = set(allowed_styles)
    for label, segment_start, segment_end in segment_bounds(start, end):
        train = events[(events["signal_ts"] < segment_start - PURGE) & (events["style"].isin(allowed))]
        test = events[
            (events["signal_ts"] >= segment_start)
            & (events["signal_ts"] < segment_end)
            & (events["style"].isin(allowed))
        ]
        if len(train) < 50 or test.empty:
            continue
        cfg_mean = train.groupby("cfg_name")["net_ret_1x"].mean()
        style_mean = train.groupby("style")["net_ret_1x"].mean()
        side_mean = train.groupby("side")["net_ret_1x"].mean()
        global_mean = float(train["net_ret_1x"].mean())
        scored = test.copy()
        scored["style_set"] = style_set
        scored["segment"] = label
        scored["segment_start"] = segment_start
        scored["segment_end"] = segment_end
        scored["train_events"] = int(len(train))
        for variant, weights in SCORE_VARIANTS.items():
            score_col = f"score__{variant}"
            scored[score_col] = weighted_score(scored, cfg_mean, style_mean, side_mean, global_mean, weights)
            train_score = weighted_score(train, cfg_mean, style_mean, side_mean, global_mean, weights)
            for quantile in QUANTILES:
                suffix = int(round(quantile * 100))
                scored[f"threshold__{variant}__q{suffix:02d}"] = float(np.quantile(train_score, quantile))
        rows.append(scored)
    if not rows:
        raise RuntimeError(f"no scored rows for {style_set}")
    return pd.concat(rows, ignore_index=True)


def replay_candidate(scored: pd.DataFrame, style_set: str, variant: str, quantile: float) -> pd.DataFrame:
    suffix = int(round(quantile * 100))
    score_col = f"score__{variant}"
    threshold_col = f"threshold__{variant}__q{suffix:02d}"
    candidate_id = f"{style_set}__{variant}__q{suffix:02d}"
    selected = scored[scored[score_col] >= scored[threshold_col]].copy()
    selected = selected.sort_values(["signal_idx", score_col], ascending=[True, False])
    selected = selected.drop_duplicates("signal_idx", keep="first").sort_values("signal_idx")

    rows: list[dict[str, Any]] = []
    blocked_until = -1
    for _, row in selected.iterrows():
        if int(row["entry_idx"]) <= blocked_until:
            continue
        exit_idx = int(row["exit_idx"])
        rows.append(
            {
                "candidate_id": candidate_id,
                "style_set": style_set,
                "variant": variant,
                "quantile": quantile,
                "event_id": int(row["event_id"]),
                "signal_ts": pd.Timestamp(row["signal_ts"]),
                "entry_ts": pd.Timestamp(row["entry_ts"]),
                "exit_ts": pd.Timestamp(row["exit_ts"]),
                "side": int(row["side"]),
                "cfg_name": str(row["cfg_name"]),
                "style": str(row["style"]),
                "score": float(row[score_col]),
                "reason": str(row["reason"]),
                "bars_held": int(exit_idx - int(row["entry_idx"]) + 1),
                "net_ret_1x": float(row["net_ret_1x"]),
            }
        )
        blocked_until = exit_idx + int(row["cooldown_bars"])
    return pd.DataFrame(rows)


def paper_gate(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 80
        and row["total_return_1x"] > 0
        and row["profit_factor"] >= 1.15
        and row["avg_trade_bps"] >= 8.0
        and row["max_drawdown_1x"] >= -0.20
        and row["recent_3m_total_return_1x"] > 0
        and row["negative_active_months"] <= row["active_months"] // 3
    )


def render_markdown(
    quality: dict[str, Any],
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    monthly: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> str:
    top = summary.iloc[0]
    target = summary[summary["candidate_id"].eq("no_wick_no_breakout__current_70_20_10__q80")].iloc[0]
    by_style_set = summary.sort_values(["style_set", "paper_gate", "total_return_1x"], ascending=[True, False, False]).groupby("style_set").head(1)
    by_variant = summary.sort_values(["variant", "paper_gate", "total_return_1x"], ascending=[True, False, False]).groupby("variant").head(1)
    top_windows = windows[windows["candidate_id"].eq(top["candidate_id"])]
    top_monthly = monthly[monthly["candidate_id"].eq(top["candidate_id"])]

    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V0.1 Full Ablation",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
        f"- 诊断窗口：`{start}` 到 `{end}`。",
        f"- 消融维度：`{len(STYLE_SETS)}` 个事件源集合 × `{len(SCORE_VARIANTS)}` 个打分公式 × `{len(QUANTILES)}` 个分位数门槛。",
        f"- 稳定性门槛排序首位：`{top['candidate_id']}`，全年收益 `{pct(float(top['total_return_1x']))}`，PF `{float(top['profit_factor']):.3f}`，最大回撤 `{pct(float(top['max_drawdown_1x']))}`。",
        f"- 目标精简版 `no_wick_no_breakout__current_70_20_10__q80`：全年收益 `{pct(float(target['total_return_1x']))}`，PF `{float(target['profit_factor']):.3f}`，最大回撤 `{pct(float(target['max_drawdown_1x']))}`，gate `{bool(target['paper_gate'])}`。",
        "",
        "注意：这是固定 seed universe 的全参数消融，不是严格无前视 OOS。`2026-03-01` 之前的分段仍受 seed-selection 前视影响。",
        "",
        "## 数据质量",
        "",
        f"- 数据范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 行数：`{quality['rows']}`，缺口：`{quality['missing_bars']}`。",
        f"- raw/normalized 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
        "",
        "## Top Candidates",
        "",
        "| rank | candidate | trades | ret | PF | win | avg bps | DD | recent3m | neg months | gate |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, (_, row) in enumerate(summary.head(25).iterrows(), start=1):
        lines.append(
            f"| {rank} | `{row['candidate_id']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {pct(float(row['win_rate']))} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} | {pct(float(row['recent_3m_total_return_1x']))} | "
            f"{int(row['negative_active_months'])}/{int(row['active_months'])} | {bool(row['paper_gate'])} |"
        )
    lines.extend(
        [
            "",
            "## Best By Style Set",
            "",
            "| style_set | best candidate | trades | ret | PF | avg bps | DD | recent3m | gate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for _, row in by_style_set.iterrows():
        lines.append(
            f"| `{row['style_set']}` | `{row['candidate_id']}` | {int(row['trades'])} | "
            f"{pct(float(row['total_return_1x']))} | {float(row['profit_factor']):.3f} | "
            f"{float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} | "
            f"{pct(float(row['recent_3m_total_return_1x']))} | {bool(row['paper_gate'])} |"
        )
    lines.extend(
        [
            "",
            "## Best By Score Variant",
            "",
            "| variant | best candidate | trades | ret | PF | avg bps | DD | recent3m | gate |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for _, row in by_variant.iterrows():
        lines.append(
            f"| `{row['variant']}` | `{row['candidate_id']}` | {int(row['trades'])} | "
            f"{pct(float(row['total_return_1x']))} | {float(row['profit_factor']):.3f} | "
            f"{float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} | "
            f"{pct(float(row['recent_3m_total_return_1x']))} | {bool(row['paper_gate'])} |"
        )
    lines.extend(
        [
            "",
            f"## Top Windows: `{top['candidate_id']}`",
            "",
            "| window | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in top_windows.iterrows():
        lines.append(
            f"| `{row['window']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            f"## Top Monthly: `{top['candidate_id']}`",
            "",
            "| month | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in top_monthly.iterrows():
        lines.append(
            f"| `{row['month']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- Summary：`{SUMMARY_CSV}`",
            f"- Windows：`{WINDOWS_CSV}`",
            f"- Monthly：`{MONTHLY_CSV}`",
            f"- Trades：`{TRADES_CSV}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)

    raw_frame, quality = validate_and_load()
    frame = add_features(raw_frame)
    seed_configs, seed_pool = select_seed_configs()
    events = build_seed_events(frame, seed_configs)

    data_end = pd.Timestamp(quality["end_ts"]) + pd.Timedelta(minutes=5)
    data_start = pd.Timestamp(quality["start_ts"])
    start = max(data_start, data_end - pd.Timedelta(days=LOOKBACK_DAYS))
    end = data_end

    summary_rows: list[dict[str, Any]] = []
    window_rows_all: list[pd.DataFrame] = []
    monthly_rows_all: list[pd.DataFrame] = []
    trades_all: list[pd.DataFrame] = []

    for style_set, allowed_styles in STYLE_SETS.items():
        scored = score_style_set(events, style_set, allowed_styles, start, end)
        for variant in SCORE_VARIANTS:
            for quantile in QUANTILES:
                trades = replay_candidate(scored, style_set, variant, quantile)
                if not trades.empty:
                    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
                candidate_id = f"{style_set}__{variant}__q{int(round(quantile * 100)):02d}"
                metrics, candidate_windows, candidate_monthly = candidate_metrics(trades, start, end)
                row = {
                    "candidate_id": candidate_id,
                    "style_set": style_set,
                    "allowed_styles": ",".join(allowed_styles),
                    "variant": variant,
                    "quantile": quantile,
                    **metrics,
                }
                row["paper_gate"] = paper_gate(row)
                summary_rows.append(row)
                candidate_windows.insert(0, "candidate_id", candidate_id)
                candidate_windows.insert(1, "style_set", style_set)
                candidate_windows.insert(2, "variant", variant)
                candidate_windows.insert(3, "quantile", quantile)
                candidate_monthly.insert(0, "candidate_id", candidate_id)
                candidate_monthly.insert(1, "style_set", style_set)
                candidate_monthly.insert(2, "variant", variant)
                candidate_monthly.insert(3, "quantile", quantile)
                window_rows_all.append(candidate_windows)
                monthly_rows_all.append(candidate_monthly)
                trades_all.append(trades)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["paper_gate", "total_return_1x", "max_drawdown_1x", "recent_3m_total_return_1x"],
        ascending=[False, False, False, False],
    )
    windows = pd.concat(window_rows_all, ignore_index=True)
    monthly = pd.concat(monthly_rows_all, ignore_index=True)
    trades_frame = pd.concat(trades_all, ignore_index=True)

    summary.to_csv(SUMMARY_CSV, index=False)
    windows.to_csv(WINDOWS_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)
    trades_frame.to_csv(TRADES_CSV, index=False)

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "mode": "seeded_v01_full_ablation",
        "warning": (
            "Fixed seed-universe full ablation, not strict anti-leakage OOS before 2026-03-01; "
            "seed configs were selected using train_2025_05_30_to_2026_03_01 metrics."
        ),
        "quality": quality,
        "lookback_days": LOOKBACK_DAYS,
        "start": start,
        "end": end,
        "style_sets": STYLE_SETS,
        "score_variants": SCORE_VARIANTS,
        "quantiles": QUANTILES,
        "seed_configs": int(len(seed_pool)),
        "event_count": int(len(events)),
        "summary": summary.to_dict(orient="records"),
        "artifact_paths": {
            "summary": str(SUMMARY_CSV),
            "windows": str(WINDOWS_CSV),
            "monthly": str(MONTHLY_CSV),
            "trades": str(TRADES_CSV),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    MARKDOWN_PATH.write_text(render_markdown(quality, summary, windows, monthly, start, end), encoding="utf-8")
    print(json.dumps(summary.head(20).to_dict(orient="records"), ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
