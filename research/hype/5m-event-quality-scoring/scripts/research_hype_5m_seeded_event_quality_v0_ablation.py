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

from research_hype_5m_seeded_event_quality_v0 import (
    ARTIFACT_ROOT,
    DIAGNOSTIC_ROOT,
    QUANTILES,
    RUN_DATE,
    build_seed_events,
    pct,
    select_seed_configs,
    serializable,
    validate_and_load,
)
from research_hype_5m_micro_scalp_search import add_features  # type: ignore[reportMissingImports]


LOOKBACK_DAYS = 365
PURGE = pd.Timedelta(hours=12)

SCORE_VARIANTS: dict[str, tuple[float, float, float]] = {
    "current_70_20_10": (0.70, 0.20, 0.10),
    "cfg_only": (1.00, 0.00, 0.00),
    "style_only": (0.00, 1.00, 0.00),
    "side_only": (0.00, 0.00, 1.00),
    "cfg_style_78_22": (0.70 / 0.90, 0.20 / 0.90, 0.00),
    "cfg_side_88_12": (0.70 / 0.80, 0.00, 0.10 / 0.80),
    "equal_weight": (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
}

REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_ablation_{RUN_DATE}.json"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_ablation_summary_{RUN_DATE}.csv"
WINDOWS_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_ablation_windows_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_ablation_monthly_{RUN_DATE}.csv"
TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_ablation_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-event-quality-v0-ablation-{RUN_DATE}.md"


def segment_bounds(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    rows: list[tuple[str, pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    while cursor < end:
        next_month = (cursor + pd.offsets.MonthBegin(1)).normalize()
        if next_month <= cursor:
            next_month = cursor + pd.offsets.MonthBegin(1)
        segment_end = min(pd.Timestamp(next_month), end)
        label = cursor.strftime("%Y_%m")
        if cursor.day != 1 or cursor.hour or cursor.minute:
            label = f"{label}_partial"
        if segment_end > cursor:
            rows.append((label, cursor, segment_end))
        cursor = segment_end
    return rows


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


def score_segments(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    scored_rows: list[pd.DataFrame] = []
    for label, segment_start, segment_end in segment_bounds(start, end):
        train = events[events["signal_ts"] < segment_start - PURGE]
        test = events[(events["signal_ts"] >= segment_start) & (events["signal_ts"] < segment_end)]
        if len(train) < 50 or test.empty:
            continue
        cfg_mean = train.groupby("cfg_name")["net_ret_1x"].mean()
        style_mean = train.groupby("style")["net_ret_1x"].mean()
        side_mean = train.groupby("side")["net_ret_1x"].mean()
        global_mean = float(train["net_ret_1x"].mean())
        scored = test.copy()
        scored["segment"] = label
        scored["segment_start"] = segment_start
        scored["segment_end"] = segment_end
        scored["train_events"] = int(len(train))
        for variant, weights in SCORE_VARIANTS.items():
            scored[f"score__{variant}"] = weighted_score(scored, cfg_mean, style_mean, side_mean, global_mean, weights)
            train_score = weighted_score(train, cfg_mean, style_mean, side_mean, global_mean, weights)
            for quantile in QUANTILES:
                suffix = int(round(quantile * 100))
                scored[f"threshold__{variant}__q{suffix:02d}"] = float(np.quantile(train_score, quantile))
        scored_rows.append(scored)
    if not scored_rows:
        raise RuntimeError("no scored segments")
    return pd.concat(scored_rows, ignore_index=True)


def replay_candidate(scored: pd.DataFrame, variant: str, quantile: float) -> pd.DataFrame:
    suffix = int(round(quantile * 100))
    candidate_id = f"{variant}__q{suffix:02d}"
    score_col = f"score__{variant}"
    threshold_col = f"threshold__{variant}__q{suffix:02d}"
    selected = scored[scored[score_col] >= scored[threshold_col]].copy()
    selected = selected.sort_values(["signal_idx", score_col], ascending=[True, False])
    selected = selected.drop_duplicates("signal_idx", keep="first").sort_values("signal_idx")

    rows: list[dict[str, Any]] = []
    blocked_until = -1
    for row in selected.itertuples(index=False):
        if int(row.entry_idx) <= blocked_until:
            continue
        exit_idx = int(row.exit_idx)
        rows.append(
            {
                "candidate_id": candidate_id,
                "variant": variant,
                "quantile": quantile,
                "event_id": int(row.event_id),
                "signal_ts": pd.Timestamp(row.signal_ts),
                "entry_ts": pd.Timestamp(row.entry_ts),
                "exit_ts": pd.Timestamp(row.exit_ts),
                "side": int(row.side),
                "cfg_name": str(row.cfg_name),
                "style": str(row.style),
                "score": float(getattr(row, score_col)),
                "reason": str(row.reason),
                "bars_held": int(exit_idx - int(row.entry_idx) + 1),
                "net_ret_1x": float(row.net_ret_1x),
            }
        )
        blocked_until = exit_idx + int(row.cooldown_bars)
    return pd.DataFrame(rows)


def max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    return float((equity / peak - 1.0).min())


def return_stats(returns: np.ndarray, days: float) -> dict[str, float | int]:
    if len(returns) == 0:
        return {
            "trades": 0,
            "days": float(days),
            "trades_per_day": 0.0,
            "total_return_1x": 0.0,
            "annualized_1x": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_bps": 0.0,
            "max_drawdown_1x": 0.0,
            "trade_sharpe": 0.0,
        }
    total_return = float(np.prod(1.0 + returns) - 1.0)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    trades_per_year = len(returns) / max(days / 365.0, 1e-9)
    trade_std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {
        "trades": int(len(returns)),
        "days": float(days),
        "trades_per_day": float(len(returns) / max(days, 1e-9)),
        "total_return_1x": total_return,
        "annualized_1x": float((1.0 + total_return) ** (365.0 / max(days, 1e-9)) - 1.0) if total_return > -1 else -1.0,
        "win_rate": float((returns > 0).mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else math.inf,
        "avg_trade_bps": float(returns.mean() * 10000.0),
        "max_drawdown_1x": max_drawdown(returns),
        "trade_sharpe": float(returns.mean() / trade_std * math.sqrt(trades_per_year)) if trade_std > 0 else 0.0,
    }


def interval_metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)]
    returns = selected["net_ret_1x"].to_numpy("float64") if not selected.empty else np.array([], dtype="float64")
    row: dict[str, Any] = {"start": start, "end": end}
    row.update(return_stats(returns, (end - start).total_seconds() / 86400.0))
    return row


def candidate_metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    windows = [
        ("recent_1w", end - pd.Timedelta(days=7)),
        ("recent_1m", end - pd.Timedelta(days=30)),
        ("recent_3m", end - pd.Timedelta(days=90)),
        ("recent_6m", end - pd.Timedelta(days=183)),
        ("full_year", start),
    ]
    window_rows = []
    for label, window_start in windows:
        row = {"window": label}
        row.update(interval_metrics(trades, max(start, window_start), end))
        window_rows.append(row)
    windows_df = pd.DataFrame(window_rows)

    monthly_rows = []
    for label, segment_start, segment_end in segment_bounds(start, end):
        row = {"month": label}
        row.update(interval_metrics(trades, segment_start, segment_end))
        monthly_rows.append(row)
    monthly_df = pd.DataFrame(monthly_rows)

    full = windows_df.loc[windows_df["window"].eq("full_year")].iloc[0].to_dict()
    active = monthly_df[monthly_df["trades"] > 0]
    negative = int((active["total_return_1x"] < 0).sum()) if not active.empty else 0
    full["active_months"] = int(len(active))
    full["negative_active_months"] = negative
    full["recent_1m_total_return_1x"] = float(windows_df.loc[windows_df["window"].eq("recent_1m"), "total_return_1x"].iloc[0])
    full["recent_3m_total_return_1x"] = float(windows_df.loc[windows_df["window"].eq("recent_3m"), "total_return_1x"].iloc[0])
    full["recent_6m_total_return_1x"] = float(windows_df.loc[windows_df["window"].eq("recent_6m"), "total_return_1x"].iloc[0])
    return full, windows_df, monthly_df


def paper_gate(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 80
        and row["total_return_1x"] > 0
        and row["profit_factor"] >= 1.10
        and row["avg_trade_bps"] >= 5.0
        and row["max_drawdown_1x"] >= -0.30
        and row["recent_3m_total_return_1x"] > 0
        and row["negative_active_months"] <= row["active_months"] // 2
    )


def render_markdown(
    quality: dict[str, Any],
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    monthly: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    selected_events: int,
) -> str:
    top = summary.iloc[0]
    high_return = summary.sort_values("total_return_1x", ascending=False).iloc[0]
    baseline = summary[summary["candidate_id"].eq("current_70_20_10__q80")].iloc[0]
    by_variant = summary.sort_values(["variant", "total_return_1x"], ascending=[True, False]).groupby("variant").head(1)
    top_monthly = monthly[monthly["candidate_id"].eq(top["candidate_id"])]
    top_windows = windows[windows["candidate_id"].eq(top["candidate_id"])]

    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V0 Ablation",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
        f"- 诊断窗口：`{start}` 到 `{end}`。",
        f"- 消融维度：`{len(SCORE_VARIANTS)}` 个打分公式 × `{len(QUANTILES)}` 个分位数门槛。",
        f"- scored selected-event rows：`{selected_events}`。",
        f"- 稳定性门槛排序首位：`{top['candidate_id']}`，全年收益 `{pct(float(top['total_return_1x']))}`，PF `{float(top['profit_factor']):.3f}`，最大回撤 `{pct(float(top['max_drawdown_1x']))}`。",
        f"- 全年收益最高行：`{high_return['candidate_id']}`，全年收益 `{pct(float(high_return['total_return_1x']))}`，PF `{float(high_return['profit_factor']):.3f}`，最大回撤 `{pct(float(high_return['max_drawdown_1x']))}`，gate `{bool(high_return['paper_gate'])}`。",
        f"- 当前基准 `current_70_20_10__q80`：全年收益 `{pct(float(baseline['total_return_1x']))}`，PF `{float(baseline['profit_factor']):.3f}`，最大回撤 `{pct(float(baseline['max_drawdown_1x']))}`。",
        "",
        "注意：这是固定 seed universe 的回溯分段消融，不是严格无前视 OOS。seed configs 仍来自 `HYPE-5M-Micro-Scalp` relaxed summary，并按 `train_2025_05_30_to_2026_03_01` 指标筛选；因此 `2026-03-01` 之前的分段有 seed 选择前视风险。",
        "",
        "## 数据质量",
        "",
        f"- 数据范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 行数：`{quality['rows']}`，缺口：`{quality['missing_bars']}`。",
        f"- raw/normalized 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
        f"- raw/normalized 最大差异：`{quality['raw_alignment']['max_abs_diff']}`。",
        "",
        "## Top Candidates",
        "",
        "| rank | candidate | trades | ret | PF | win | avg bps | DD | Sharpe | neg months | gate |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, (_, row) in enumerate(summary.head(15).iterrows(), start=1):
        lines.append(
            f"| {rank} | `{row['candidate_id']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {pct(float(row['win_rate']))} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} | {float(row['trade_sharpe']):.2f} | "
            f"{int(row['negative_active_months'])}/{int(row['active_months'])} | {bool(row['paper_gate'])} |"
        )

    lines.extend(
        [
            "",
            "## Best By Score Variant",
            "",
            "| variant | best candidate | trades | ret | PF | avg bps | DD | neg months |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in by_variant.iterrows():
        lines.append(
            f"| `{row['variant']}` | `{row['candidate_id']}` | {int(row['trades'])} | "
            f"{pct(float(row['total_return_1x']))} | {float(row['profit_factor']):.3f} | "
            f"{float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} | "
            f"{int(row['negative_active_months'])}/{int(row['active_months'])} |"
        )

    lines.extend(
        [
            "",
            f"## Top Candidate Windows: `{top['candidate_id']}`",
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
            f"## Top Candidate Monthly: `{top['candidate_id']}`",
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

    scored = score_segments(events, start, end)
    summary_rows: list[dict[str, Any]] = []
    window_rows_all: list[pd.DataFrame] = []
    monthly_rows_all: list[pd.DataFrame] = []
    trades_all: list[pd.DataFrame] = []

    for variant in SCORE_VARIANTS:
        for quantile in QUANTILES:
            trades = replay_candidate(scored, variant, quantile)
            if not trades.empty:
                trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
            candidate_id = f"{variant}__q{int(round(quantile * 100)):02d}"
            metrics, candidate_windows, candidate_monthly = candidate_metrics(trades, start, end)
            row = {
                "candidate_id": candidate_id,
                "variant": variant,
                "quantile": quantile,
                **metrics,
            }
            row["paper_gate"] = paper_gate(row)
            summary_rows.append(row)
            candidate_windows.insert(0, "candidate_id", candidate_id)
            candidate_windows.insert(1, "variant", variant)
            candidate_windows.insert(2, "quantile", quantile)
            candidate_monthly.insert(0, "candidate_id", candidate_id)
            candidate_monthly.insert(1, "variant", variant)
            candidate_monthly.insert(2, "quantile", quantile)
            window_rows_all.append(candidate_windows)
            monthly_rows_all.append(candidate_monthly)
            trades_all.append(trades)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["paper_gate", "total_return_1x", "profit_factor", "recent_3m_total_return_1x"],
        ascending=[False, False, False, False],
    )
    windows = pd.concat(window_rows_all, ignore_index=True)
    monthly = pd.concat(monthly_rows_all, ignore_index=True)
    trades_frame = pd.concat(trades_all, ignore_index=True) if trades_all else pd.DataFrame()

    summary.to_csv(SUMMARY_CSV, index=False)
    windows.to_csv(WINDOWS_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)
    trades_frame.to_csv(TRADES_CSV, index=False)

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "mode": "seeded_v0_score_quantile_ablation",
        "warning": (
            "Fixed seed-universe retrospective ablation, not strict anti-leakage OOS before 2026-03-01; "
            "seed configs were selected using train_2025_05_30_to_2026_03_01 metrics."
        ),
        "quality": quality,
        "lookback_days": LOOKBACK_DAYS,
        "start": start,
        "end": end,
        "score_variants": SCORE_VARIANTS,
        "quantiles": QUANTILES,
        "seed_configs": int(len(seed_pool)),
        "event_count": int(len(events)),
        "scored_event_rows": int(len(scored)),
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
    MARKDOWN_PATH.write_text(
        render_markdown(quality, summary, windows, monthly, start, end, int(len(scored))),
        encoding="utf-8",
    )
    print(json.dumps(summary.head(15).to_dict(orient="records"), ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
