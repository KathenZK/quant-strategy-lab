from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-event-quality-scoring")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

CANDIDATE_ID = "no_wick_no_breakout__cfg_side_88_12__q80"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v01_full_ablation_trades_{RUN_DATE}.csv"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v1_live_feasibility_stress_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v1_live_feasibility_monthly_{RUN_DATE}.csv"
STYLE_PATH = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v1_live_feasibility_style_{RUN_DATE}.csv"
REASON_PATH = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v1_live_feasibility_reasons_{RUN_DATE}.csv"
REPORT_JSON = ARTIFACT_ROOT / f"hype_5m_seeded_event_quality_v1_live_feasibility_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-seeded-v1-live-feasibility-{RUN_DATE}.md"


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def max_drawdown(returns: np.ndarray) -> float:
    if len(returns) == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(np.r_[1.0, equity])[:-1]
    return float(min(0.0, (equity / peak - 1.0).min()))


def metrics(returns: np.ndarray, days: float) -> dict[str, Any]:
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
            "worst_trade_1x": 0.0,
            "best_trade_1x": 0.0,
            "trade_sharpe": 0.0,
        }
    total_return = float(np.prod(1.0 + returns) - 1.0)
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = float(-losses.sum())
    trade_std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    trades_per_year = len(returns) / max(days / 365.0, 1e-9)
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
        "worst_trade_1x": float(returns.min()),
        "best_trade_1x": float(returns.max()),
        "trade_sharpe": float(returns.mean() / trade_std * math.sqrt(trades_per_year)) if trade_std > 0 else 0.0,
    }


def interval_metrics(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    selected = frame[(frame["entry_ts"] >= start) & (frame["entry_ts"] < end)]
    row = {"start": start, "end": end}
    row.update(metrics(selected["net_ret_1x"].to_numpy("float64"), (end - start).total_seconds() / 86400.0))
    return row


def month_rows(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        next_month = min(pd.Timestamp((cursor + pd.offsets.MonthBegin(1)).normalize()), end)
        if next_month <= cursor:
            next_month = min(cursor + pd.offsets.MonthBegin(1), end)
        label = cursor.strftime("%Y_%m")
        if cursor.day != 1 or cursor.hour or cursor.minute:
            label = f"{label}_partial"
        row = {"month": label}
        row.update(interval_metrics(frame, cursor, next_month))
        rows.append(row)
        cursor = next_month
    return pd.DataFrame(rows)


def grouped_metrics(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(column):
        row = {column: key}
        row.update(metrics(group["net_ret_1x"].to_numpy("float64"), max(float(len(group)), 1.0)))
        rows.append(row)
    return pd.DataFrame(rows).sort_values("total_return_1x", ascending=False)


def stress_rows(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base = frame["net_ret_1x"].to_numpy("float64")
    days = (end - start).total_seconds() / 86400.0
    for extra_cost_bps in (0, 2.5, 5, 10, 15, 20, 30, 50, 75):
        stressed = base - extra_cost_bps / 10000.0
        row = {"extra_roundtrip_cost_bps": float(extra_cost_bps)}
        row.update(metrics(stressed, days))
        rows.append(row)
    return pd.DataFrame(rows)


def render_markdown(
    start: pd.Timestamp,
    end: pd.Timestamp,
    full: dict[str, Any],
    recent_90: dict[str, Any],
    recent_30: dict[str, Any],
    stress: pd.DataFrame,
    monthly: pd.DataFrame,
    styles: pd.DataFrame,
    reasons: pd.DataFrame,
    trades: pd.DataFrame,
) -> str:
    hold = trades["bars_held"].astype(float)
    lines = [
        "# HYPE-5M-Event-Quality-Scoring Seeded V1 Live Feasibility Audit",
        "",
        f"生成日期：`{RUN_DATE}`",
        "",
        "## 结论",
        "",
        f"- V1 candidate：`{CANDIDATE_ID}`。",
        f"- 诊断窗口：`{start}` 到 `{end}`。",
        f"- 固定 seed universe 回放：`{int(full['trades'])}` 笔，收益 `{pct(float(full['total_return_1x']))}`，PF `{float(full['profit_factor']):.3f}`，单笔 `{float(full['avg_trade_bps']):.2f} bps`，最大回撤 `{pct(float(full['max_drawdown_1x']))}`。",
        f"- 近 90 天：`{int(recent_90['trades'])}` 笔，收益 `{pct(float(recent_90['total_return_1x']))}`，PF `{float(recent_90['profit_factor']):.3f}`，最大回撤 `{pct(float(recent_90['max_drawdown_1x']))}`。",
        f"- 近 30 天：`{int(recent_30['trades'])}` 笔，收益 `{pct(float(recent_30['total_return_1x']))}`，PF `{float(recent_30['profit_factor']):.3f}`，最大回撤 `{pct(float(recent_30['max_drawdown_1x']))}`。",
        "",
        "结论：`Seeded V1` 可以登记为当前 research lead / paper-audit lead，但**不能直接实盘，也不应直接 paper-live**。原因不是回放指标差，而是 seed-selection 前视、paper-runner 缺失、真实下单保护窗口、成本压力和重启恢复还没有完成审计。",
        "",
        "## V1 仍然依赖打分系统",
        "",
        "- 事件源集合：`bb_revert`、`macd_flip`、`trend_rsi_snapback`、`vwap_revert`。",
        "- 移除事件源：`wick_reject`、`micro_breakout`。",
        "- score：`0.875 * cfg_mean + 0.125 * side_mean`。",
        "- 分位门槛：`q80`，每个月只交易当月测试事件中高于历史训练 score 第 80 分位的事件。",
        "- 同一 signal bar 多事件冲突时只保留最高分；持仓期间和 cooldown 内跳过后续事件。",
        "",
        "## 成本压力",
        "",
        "| extra roundtrip cost | trades | ret | PF | avg bps | DD |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in stress.iterrows():
        lines.append(
            f"| `{float(row['extra_roundtrip_cost_bps']):.1f} bps` | {int(row['trades'])} | "
            f"{pct(float(row['total_return_1x']))} | {float(row['profit_factor']):.3f} | "
            f"{float(row['avg_trade_bps']):.2f} | {pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 执行路径特征",
            "",
            f"- 持仓 bars：mean `{hold.mean():.2f}`，median `{hold.median():.1f}`，p90 `{hold.quantile(0.90):.1f}`，max `{hold.max():.0f}`。",
            f"- 单笔最差：`{pct(float(full['worst_trade_1x']))}`；单笔最好：`{pct(float(full['best_trade_1x']))}`。",
            "",
            "### Exit Reasons",
            "",
            "| reason | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in reasons.iterrows():
        lines.append(
            f"| `{row['reason']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "### Styles",
            "",
            "| style | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in styles.iterrows():
        lines.append(
            f"| `{row['style']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## 月度",
            "",
            "| month | trades | ret | PF | avg bps | DD |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for _, row in monthly.iterrows():
        lines.append(
            f"| `{row['month']}` | {int(row['trades'])} | {pct(float(row['total_return_1x']))} | "
            f"{float(row['profit_factor']):.3f} | {float(row['avg_trade_bps']):.2f} | "
            f"{pct(float(row['max_drawdown_1x']))} |"
        )
    lines.extend(
        [
            "",
            "## Live-Feasibility Gate",
            "",
            "- Data quality：通过已有数据湖检查；但本审计使用固定历史 seed universe，不是从零滚动生成 seed 的严格 OOS。",
            "- Signal timing：回测使用 closed-bar signal + next-open entry，方向正确；实盘需要验证 K 线 close 后计算、下 market order 的延迟是否仍被 `10.73 bps` entry slippage 覆盖。",
            "- Entry fill：回测按 next open 加 entry slippage；真实成交不是保证 next open，必须 paper-runner 对账。",
            "- Protection：回测假设入场后立即存在固定 TP/SL bracket；真实系统存在 entry fill 到 bracket 下单确认之间的无保护窗口，尚未审计。",
            "- Stop behavior：回测使用 stop-first 和 open 穿越按 open 成交，这是保守方向；但真实 stop-market 滑点和 Binance 触发语义仍需实测。",
            "- Fees/slippage：当前 edge 能承受一定额外成本，但额外 `30-50 bps` roundtrip 成本会显著降低收益；仓位放大后 slippage 未建模。",
            "- Restart recovery：未实现/未验证 live runner 状态恢复、已挂订单查询、孤儿单撤单、重复入场保护。",
            "- Missing data：数据湖历史无缺口；实盘缺 K、延迟 K、WebSocket/API 不一致处理未验证。",
            "- Kill switch：尚未定义 max daily loss、max drawdown stop、连续亏损冷却、仓位降档。",
            "",
            "## Decision",
            "",
            "- 记录为：`HYPE-5M-Event-Quality-Scoring-Seeded-V1`。",
            "- 当前状态：`research lead / paper-audit lead`。",
            "- 不允许状态：`live-ready`、`paper-live-ready`、`dry-run handoff`。",
            "- 下一步必须完成：seed-generation anti-leakage、paper-runner dry-run 对账、真实 order-maintenance 审计、成本/滑点压力、drawdown-control ablation。",
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_JSON}`",
            f"- Stress：`{SUMMARY_PATH}`",
            f"- Monthly：`{MONTHLY_PATH}`",
            f"- Style：`{STYLE_PATH}`",
            f"- Reasons：`{REASON_PATH}`",
            "",
        ]
    )
    return "\n".join(lines)


def serializable(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return "inf" if value > 0 else "-inf"
    return value


def main() -> None:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(TRADES_PATH)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)

    all_trades = pd.read_csv(TRADES_PATH)
    trades = all_trades[all_trades["candidate_id"].eq(CANDIDATE_ID)].copy()
    if trades.empty:
        raise RuntimeError(f"no trades for {CANDIDATE_ID}")
    trades["entry_ts"] = pd.to_datetime(trades["entry_ts"], utc=True)
    trades["exit_ts"] = pd.to_datetime(trades["exit_ts"], utc=True)
    trades = trades.sort_values("entry_ts").reset_index(drop=True)

    start = pd.Timestamp("2025-06-26 04:20:00+00:00")
    end = pd.Timestamp("2026-06-26 04:20:00+00:00")
    full = interval_metrics(trades, start, end)
    recent_90 = interval_metrics(trades, end - pd.Timedelta(days=90), end)
    recent_30 = interval_metrics(trades, end - pd.Timedelta(days=30), end)
    monthly = month_rows(trades, start, end)
    styles = grouped_metrics(trades, "style")
    reasons = grouped_metrics(trades, "reason")
    stress = stress_rows(trades, start, end)

    stress.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    styles.to_csv(STYLE_PATH, index=False)
    reasons.to_csv(REASON_PATH, index=False)

    report = {
        "run_date": RUN_DATE,
        "family": "HYPE-5M-Event-Quality-Scoring",
        "version": "HYPE-5M-Event-Quality-Scoring-Seeded-V1",
        "candidate_id": CANDIDATE_ID,
        "status": "research lead / paper-audit lead; not live-ready",
        "start": start,
        "end": end,
        "full": full,
        "recent_90d": recent_90,
        "recent_30d": recent_30,
        "stress": stress.to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
        "styles": styles.to_dict(orient="records"),
        "reasons": reasons.to_dict(orient="records"),
        "artifact_paths": {
            "markdown": str(MARKDOWN_PATH),
            "json": str(REPORT_JSON),
            "stress": str(SUMMARY_PATH),
            "monthly": str(MONTHLY_PATH),
            "style": str(STYLE_PATH),
            "reasons": str(REASON_PATH),
        },
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=serializable), encoding="utf-8")
    MARKDOWN_PATH.write_text(
        render_markdown(start, end, full, recent_90, recent_30, stress, monthly, styles, reasons, trades),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=serializable))


if __name__ == "__main__":
    main()
