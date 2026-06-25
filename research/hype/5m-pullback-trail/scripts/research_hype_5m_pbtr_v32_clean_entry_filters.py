from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v3_ablation_audit import V3_CONFIG, filtered_signal, month_slices
from research_hype_5m_pbtr_v31_min_hold_9 import V31_CONFIG
from research_hype_5m_positive_payoff_search import load_all_hype_5m
from research_hype_5m_indicator_search import Trade, add_features


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters_summary.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters_weekly.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters_monthly.csv")
TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v32_clean_entry_filters_trades.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v32-clean-entry-filters-2026-06-24.md"
)


V32_CONFIG = replace(
    V31_CONFIG,
    name="HYPE-5M-PBTR-V3.2",
    min_regime_age=0,
    max_regime_age=100000,
    max_dist_ema=99.0,
    min_dir_roc=-99.0,
    min_dir_rsi=0.0,
    max_dir_rsi=100.0,
    max_chop=100.0,
    min_dir_cmf=-99.0,
    require_htf=False,
)


def evaluate(frame: pd.DataFrame, label: str, cfg: Any) -> tuple[dict[str, Any], list[Trade], np.ndarray]:
    signal = filtered_signal(frame, cfg, final_filter=False)
    trades = simulate_trades_live_cost(frame, signal, cfg)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    return {"label": label, "signal_count": int(np.count_nonzero(signal)), **metrics, **{f"cfg_{k}": v for k, v in asdict(cfg).items()}}, trades, signal


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def trades_frame(label: str, trades: list[Trade]) -> pd.DataFrame:
    equity = 1.0
    peak = 1.0
    rows: list[dict[str, Any]] = []
    for idx, trade in enumerate(trades, start=1):
        equity *= max(0.001, 1.0 + float(trade.net_ret_1x))
        peak = max(peak, equity)
        rows.append(
            {
                "label": label,
                "trade_no": idx,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": int(trade.side),
                "bars_held": int(trade.bars_held),
                "entry_price": float(trade.entry_price),
                "exit_price": float(trade.exit_price),
                "net_ret_1x": float(trade.net_ret_1x),
                "mae_1x": float(trade.mae_1x),
                "mfe_1x": float(trade.mfe_1x),
                "equity_after": float(equity),
                "drawdown_after": float(equity / peak - 1.0),
                "reason": trade.reason,
            }
        )
    return pd.DataFrame(rows)


def time_slice_rows(frame: pd.DataFrame, label: str, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        rolling_rows.append({"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        weekly_rows.append({"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    monthly_rows: list[dict[str, Any]] = []
    for item in month_slices(frame):
        monthly_rows.append({"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    return pd.DataFrame(rolling_rows), pd.DataFrame(weekly_rows), pd.DataFrame(monthly_rows)


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    v32 = rows["HYPE-5M-PBTR-V3.2"]
    v31 = rows["HYPE-5M-PBTR-V3.1"]
    rolling_v32 = rolling.loc[rolling["label"].eq("HYPE-5M-PBTR-V3.2")].copy()
    weekly_v32 = weekly.loc[weekly["label"].eq("HYPE-5M-PBTR-V3.2")].copy()
    monthly_v32 = monthly.loc[monthly["label"].eq("HYPE-5M-PBTR-V3.2")].copy()
    worst_week = weekly_v32.sort_values("total_return").iloc[0]
    best_week = weekly_v32.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly_v32.sort_values("total_return").iloc[0]
    best_month = monthly_v32.sort_values("total_return", ascending=False).iloc[0]

    lines = [
        "# HYPE-5M-PBTR-V3.2 Clean Entry Filters 回测 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "V3.2 定义：在 `HYPE-5M-PBTR-V3.1` 基础上，删除审计报告中无贡献或负贡献的剩余入场过滤器，保留方向、回踩恢复、`min_hold_bars=9` 和 ATR trailing exit。",
        "",
        "## 参数变化",
        "",
        "| 参数 | V3.1 | V3.2 | 处理 |",
        "| --- | ---: | ---: | --- |",
        "| `min_regime_age` | `3` | `0` | 删除 regime age 入场过滤 |",
        "| `min_dir_roc` | `-0.01` | `-99` | 删除方向 ROC 入场过滤 |",
        "| `max_chop` | `62` | `100` | 删除 CHOP 入场过滤 |",
        "| `final dir_htf` | disabled | disabled | 已在 V3 中删除 |",
        "| `dir_rsi` | `0/100` | `0/100` | 已在 V2.1A/V3 中删除 |",
        "| `max_dist_ema` | `99` | `99` | 已失活 |",
        "| `min_dir_cmf` | `-99` | `-99` | 已失活 |",
        "",
        "## 成本与数据",
        "",
        "- 成本口径：线上实盘统计成本。",
        f"- 手续费：`{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`。",
        f"- 开仓滑点：`{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 平仓滑点：`{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 净滑点：`{NET_SLIPPAGE_RATE_ON_TURNOVER * 10000:+.4f} bps/总成交额`。",
        "- 数据：Binance HYPEUSDT 永续 `5m`，截至 `2026-06-23 04:20 UTC`。",
        "",
        "## V3 / V3.1 / V3.2 对比",
        "",
        "| 版本 | 交易数 | 权益倍数 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label in ["HYPE-5M-PBTR-V3", "HYPE-5M-PBTR-V3.1", "HYPE-5M-PBTR-V3.2"]:
        row = rows[label]
        lines.append(f"| `{label}` | `{int(row['trades'])}` | `{mult(float(row['equity_multiple']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")

    delta_trade = int(v32["trades"]) - int(v31["trades"])
    lines.extend(
        [
            "",
            f"相对 V3.1，V3.2 交易数变化 `{delta_trade:+d}`，胜率从 `{pct(float(v31['win_rate']))}` 到 `{pct(float(v32['win_rate']))}`，PF 从 `{num(float(v31['profit_factor']))}` 到 `{num(float(v32['profit_factor']))}`，最大回撤从 `{pct(float(v31['max_dd']))}` 到 `{pct(float(v32['max_dd']))}`。",
            "",
            "## 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling_v32.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly_v32)}`，盈利周 `{int((weekly_v32['total_return'] > 0).sum())}/{len(weekly_v32)}`，中位周收益 `{pct(float(weekly_v32['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly_v32)}`，盈利月 `{int((monthly_v32['total_return'] > 0).sum())}/{len(monthly_v32)}`，中位月收益 `{pct(float(monthly_v32['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 审计结论",
            "",
            "V3.2 达到了“参数更简洁”的目标：入场侧只保留方向和 pullback/resume 结构，不再保留 regime age、ROC、CHOP、RSI、CMF、HTF、dist EMA 等过滤器。样本内结果若不显著恶化，说明这些过滤器确实更像历史搜索残留，而不是当前 V3 系列的必要 alpha 来源。",
            "",
        ]
    )
    if float(v32["profit_factor"]) >= float(v31["profit_factor"]) and float(v32["max_dd"]) >= float(v31["max_dd"]) * 1.15:
        lines.append("V3.2 相对 V3.1 没有明显恶化，可作为更简洁的首选表达进入 paper/dry-run。")
    else:
        lines.append("V3.2 虽更简洁，但相对 V3.1 出现收益、PF 或回撤劣化，应先作为对照候选，不应直接替代 V3.1。")
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v32_clean_entry_filters.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 滚动切片：`{ROLLING_PATH}`",
            f"- 周切片：`{WEEKLY_PATH}`",
            f"- 月切片：`{MONTHLY_PATH}`",
            f"- 交易明细：`{TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    frame = frame.loc[frame["ts"] <= END_TS].reset_index(drop=True)

    specs = [
        ("HYPE-5M-PBTR-V3", V3_CONFIG),
        ("HYPE-5M-PBTR-V3.1", V31_CONFIG),
        ("HYPE-5M-PBTR-V3.2", V32_CONFIG),
    ]
    summary_rows: list[dict[str, Any]] = []
    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    for label, cfg in specs:
        summary, trades, _ = evaluate(frame, label, cfg)
        summary_rows.append(summary)
        rolling, weekly, monthly = time_slice_rows(frame, label, trades)
        rolling_frames.append(rolling)
        weekly_frames.append(weekly)
        monthly_frames.append(monthly)
        if label == "HYPE-5M-PBTR-V3.2":
            trade_frames.append(trades_frame(label, trades))

    summary = pd.DataFrame(summary_rows)
    rolling = pd.concat(rolling_frames, ignore_index=True)
    weekly = pd.concat(weekly_frames, ignore_index=True)
    monthly = pd.concat(monthly_frames, ignore_index=True)
    trades_out = pd.concat(trade_frames, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trades_out.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, rolling, weekly, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.2",
                "definition": {
                    "base": "HYPE-5M-PBTR-V3.1",
                    "change": "remove inactive/noncontributing entry filters: min_regime_age, min_dir_roc, max_chop; keep already disabled final_htf/rsi/cmf/dist filters disabled",
                    "config": asdict(V32_CONFIG),
                },
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "trades": str(TRADES_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary[["label", "signal_count", "trades", "equity_multiple", "annualized_multiple", "total_return", "win_rate", "payoff_ratio", "profit_factor", "max_dd", "long_trades", "short_trades"]].to_string(index=False))


if __name__ == "__main__":
    main()
