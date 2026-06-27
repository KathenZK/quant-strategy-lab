from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
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
    RUN_DATE,
    build_seed_events,
    metrics,
    pct,
    replay_selected,
    score_month,
    select_seed_configs,
    serializable,
    validate_and_load,
)
from research_hype_5m_micro_scalp_search import add_features  # type: ignore[reportMissingImports]


TARGET_QUANTILE = 0.80
LOOKBACK_DAYS = 365
PURGE = pd.Timedelta(hours=12)

REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_q80_full_year_segments_{RUN_DATE}.json"
SUMMARY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_q80_full_year_segments_summary_{RUN_DATE}.csv"
MONTHLY_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_q80_full_year_segments_monthly_{RUN_DATE}.csv"
TRADES_CSV = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_q80_full_year_segments_trades_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-event-quality-v0-q80-full-year-segments-{RUN_DATE}.md"


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


def score_segments(events: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for label, segment_start, segment_end in segment_bounds(start, end):
        train = events[events["signal_ts"] < segment_start - PURGE]
        test = events[(events["signal_ts"] >= segment_start) & (events["signal_ts"] < segment_end)]
        if len(train) < 50 or test.empty:
            continue
        scored = score_month(events, train, test)
        scored["segment"] = label
        scored["segment_start"] = segment_start
        scored["segment_end"] = segment_end
        scored["train_events"] = int(len(train))
        rows.append(scored)
    if not rows:
        raise RuntimeError("no scored segments")
    return pd.concat(rows, ignore_index=True)


def return_stats(returns: np.ndarray, days: float) -> dict[str, float | int]:
    if len(returns) == 0:
        return {
            "trades": 0,
            "days": float(days),
            "total_return_1x": 0.0,
            "annualized_1x": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "avg_trade_bps": 0.0,
            "max_drawdown_1x": 0.0,
        }
    total_return = float(np.prod(1.0 + returns) - 1.0)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    max_dd = float((equity / peak - 1.0).min())
    return {
        "trades": int(len(returns)),
        "days": float(days),
        "total_return_1x": total_return,
        "annualized_1x": float((1.0 + total_return) ** (365.0 / max(days, 1e-9)) - 1.0) if total_return > -1 else -1.0,
        "win_rate": float((returns > 0).mean()),
        "profit_factor": float(wins.sum() / gross_loss) if gross_loss > 0 else math.inf,
        "avg_trade_bps": float(returns.mean() * 10000.0),
        "max_drawdown_1x": max_dd,
    }


def trade_frame(trades: list[Any]) -> pd.DataFrame:
    return pd.DataFrame([asdict(trade) for trade in trades])


def interval_metrics(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = trades[(trades["entry_ts"] >= start) & (trades["entry_ts"] < end)]
    returns = selected["net_ret_1x"].to_numpy("float64") if not selected.empty else np.array([], dtype="float64")
    days = (end - start).total_seconds() / 86400.0
    row: dict[str, Any] = {"start": start, "end": end}
    row.update(return_stats(returns, days))
    return row


def window_rows(trades: pd.DataFrame, end: pd.Timestamp, full_start: pd.Timestamp) -> pd.DataFrame:
    windows = [
        ("recent_1w", end - pd.Timedelta(days=7)),
        ("recent_1m", end - pd.Timedelta(days=30)),
        ("recent_3m", end - pd.Timedelta(days=90)),
        ("recent_6m", end - pd.Timedelta(days=183)),
        ("recent_12m", end - pd.Timedelta(days=365)),
        ("full_year", full_start),
    ]
    rows = []
    for label, start in windows:
        row = {"window": label}
        row.update(interval_metrics(trades, max(start, full_start), end))
        rows.append(row)
    return pd.DataFrame(rows)


def monthly_rows(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, segment_start, segment_end in segment_bounds(start, end):
        row = {"month": label}
        row.update(interval_metrics(trades, segment_start, segment_end))
        rows.append(row)
    return pd.DataFrame(rows)


def render_markdown(
    quality: dict[str, Any],
    windows: pd.DataFrame,
    monthly: pd.DataFrame,
    selected_events: int,
    trade_count: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> str:
    full = windows.loc[windows["window"].eq("full_year")].iloc[0]
    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V0 Q80 Full-Year Segments",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
        f"- 诊断窗口：`{start}` 到 `{end}`。",
        f"- 使用固定 seed universe 与 `seeded_source_mean_q80` 规则，选中事件 `{selected_events}` 个，回放交易 `{trade_count}` 笔。",
        f"- 过去一年分段回放总收益：`{pct(float(full['total_return_1x']))}`，年化 `"
        f"{pct(float(full['annualized_1x']))}`，PF `{float(full['profit_factor']):.3f}`，最大回撤 `"
        f"{pct(float(full['max_drawdown_1x']))}`。",
        "",
        "注意：这是固定 seed universe 的回溯分段诊断，不是严格无前视 OOS。seed configs 仍来自 `HYPE-5M-Micro-Scalp` relaxed summary，并按 `train_2025_05_30_to_2026_03_01` 指标筛选；因此 `2026-03-01` 之前的分段会受到 seed 选择前视影响。",
        "",
        "## 数据质量",
        "",
        f"- 数据范围：`{quality['start_ts']}` 到 `{quality['end_ts']}`。",
        f"- 行数：`{quality['rows']}`，缺口：`{quality['missing_bars']}`。",
        f"- raw/normalized 对齐：`{quality['raw_alignment']['same_ts_sequence']}`。",
        f"- raw/normalized 最大差异：`{quality['raw_alignment']['max_abs_diff']}`。",
        "",
        "## 滚动窗口",
        "",
        "| window | trades | total return | annualized | PF | win | avg bps | max DD |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in windows.iterrows():
        pf = "inf" if not np.isfinite(float(row["profit_factor"])) else f"{float(row['profit_factor']):.3f}"
        lines.append(
            f"| `{row['window']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{pct(float(row['annualized_1x']))} | {pf} | {pct(float(row['win_rate']))} | "
            f"{float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 月度分段",
            "",
            "| month | trades | total return | PF | win | avg bps | max DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in monthly.iterrows():
        pf = "inf" if not np.isfinite(float(row["profit_factor"])) else f"{float(row['profit_factor']):.3f}"
        lines.append(
            f"| `{row['month']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{pf} | {pct(float(row['win_rate']))} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- Summary：`{SUMMARY_CSV}`",
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
    candidate_id = f"seeded_source_mean_q{int(round(TARGET_QUANTILE * 100)):02d}_full_year_segments"
    trades, selected = replay_selected(scored, TARGET_QUANTILE, candidate_id)
    trades_df = trade_frame(trades)
    if not trades_df.empty:
        trades_df["entry_ts"] = pd.to_datetime(trades_df["entry_ts"], utc=True)

    windows = window_rows(trades_df, end, start)
    monthly = monthly_rows(trades_df, start, end)

    selected.to_csv(ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v0_q80_full_year_segments_selected_{RUN_DATE}.csv", index=False)
    trades_df.to_csv(TRADES_CSV, index=False)
    windows.to_csv(SUMMARY_CSV, index=False)
    monthly.to_csv(MONTHLY_CSV, index=False)

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "mode": "seeded_v0_q80_full_year_segments",
        "warning": (
            "Fixed seed-universe retrospective diagnostic, not strict anti-leakage OOS before 2026-03-01; "
            "seed configs were selected using train_2025_05_30_to_2026_03_01 metrics."
        ),
        "quality": quality,
        "lookback_days": LOOKBACK_DAYS,
        "start": start,
        "end": end,
        "seed_configs": int(len(seed_pool)),
        "event_count": int(len(events)),
        "selected_events": int(len(selected)),
        "trade_count": int(len(trades_df)),
        "windows": windows.to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
        "artifact_paths": {
            "summary": str(SUMMARY_CSV),
            "monthly": str(MONTHLY_CSV),
            "trades": str(TRADES_CSV),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    MARKDOWN_PATH.write_text(
        render_markdown(quality, windows, monthly, int(len(selected)), int(len(trades_df)), start, end),
        encoding="utf-8",
    )
    print(json.dumps({"windows": report["windows"], "monthly": report["monthly"]}, ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
