from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides
from research_hype_5m_pbtr_v6_live_executable_search import (
    ExitSpec,
    RuleSpec,
    SignalSpec,
    add_features,
    add_search_features,
    apply_rule,
    build_signal,
    event_features,
    filtered_signal,
    load_closed_frame,
    month_slices,
    pct,
    simulate_live_orders,
    validation_slices,
)


SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_candidate_robustness.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_candidate_robustness_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v6-candidate-robustness-2026-06-25.md"
)

BASE_SIGNAL = SignalSpec(
    style="pullback_reclaim",
    ema_fast=21,
    ema_slow=55,
    pullback_buffer=0.01,
    side_mode="long",
    require_candle=False,
    htf_threshold=0.5,
)

REFERENCE_ATR_RATIO = 1.403629125454497


def num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def rule_specs() -> list[RuleSpec]:
    specs = [RuleSpec(label="none", conditions=())]
    for threshold in (1.0, 1.1, 1.2, 1.3, 1.35, 1.4, REFERENCE_ATR_RATIO, 1.45, 1.5, 1.6, 1.7, 1.8):
        specs.append(
            RuleSpec(
                label=f"atr_ratio_14_96>={threshold:.6g}",
                conditions=(("atr_ratio_14_96", ">=", float(threshold)),),
            )
        )
    for threshold in (-10.0, -20.0, -25.434545153837803, -30.0, -40.0, -50.0):
        specs.append(
            RuleSpec(
                label=f"dir_body_bps<={threshold:.6g}",
                conditions=(("dir_body_bps", "<=", float(threshold)),),
            )
        )
    for threshold in (200.0, 250.0, 300.0, 322.149, 350.0, 400.0):
        specs.append(
            RuleSpec(
                label=f"dir_ret48_bps>={threshold:.6g}",
                conditions=(("dir_ret48_bps", ">=", float(threshold)),),
            )
        )
    specs.append(RuleSpec(label="hour>=19", conditions=(("hour", ">=", 19.0),)))
    for threshold in (500.0, 600.0, 660.015, 700.0, 788.123):
        specs.append(
            RuleSpec(
                label=f"dir_ret192_bps>={threshold:.6g}",
                conditions=(("dir_ret192_bps", ">=", float(threshold)),),
            )
        )
    return specs


def exit_specs() -> list[ExitSpec]:
    specs: list[ExitSpec] = []
    for time_exit_bars in (24, 36, 48, 72):
        for tp_atr in (3.0, 4.0, 5.0, 6.0):
            for sl_atr in (4.0, 5.0, 6.0, 7.0, 8.0):
                specs.append(ExitSpec(tp_atr=tp_atr, sl_atr=sl_atr, trail_atr=0.0, time_exit_bars=time_exit_bars))
    for time_exit_bars in (24, 48):
        for trail_atr in (3.0, 4.0, 5.0, 6.0):
            specs.append(ExitSpec(tp_atr=5.0, sl_atr=4.0, trail_atr=trail_atr, time_exit_bars=time_exit_bars))
    return specs


def attach_slices(row: dict[str, Any], trades: list[Any], frame: pd.DataFrame) -> dict[str, Any]:
    result = dict(row)
    for item in validation_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            result[f"{item['name']}_{key}"] = value
    return result


def robust_pass(row: dict[str, Any]) -> bool:
    return bool(
        row["trade_count"] >= 100
        and row["profit_factor"] >= 1.2
        and row["avg_trade"] > 0.002
        and row["payoff_ratio"] > 1.0
        and row["max_dd"] > -0.25
        and row["is_2025_05_30_to_2026_03_01_trades"] >= 50
        and row["is_2025_05_30_to_2026_03_01_profit_factor"] >= 1.1
        and row["val_2026_03_01_to_2026_06_01_trades"] >= 20
        and row["val_2026_03_01_to_2026_06_01_profit_factor"] >= 1.0
        and row["oos_2026_06_01_to_latest_trades"] >= 10
        and row["oos_2026_06_01_to_latest_profit_factor"] >= 1.0
    )


def robust_score(row: dict[str, Any]) -> float:
    factors = [
        float(row["profit_factor"]),
        float(row["is_2025_05_30_to_2026_03_01_profit_factor"]),
        float(row["val_2026_03_01_to_2026_06_01_profit_factor"]),
        float(row["oos_2026_06_01_to_latest_profit_factor"]),
    ]
    if any(value <= 0 or not np.isfinite(value) for value in factors):
        return 0.0
    return float(np.prod(factors) ** (1.0 / len(factors)))


def reason_counts(trades: list[Any]) -> str:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.reason] = counts.get(trade.reason, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def main() -> None:
    raw = load_closed_frame()
    frame = add_search_features(add_features(raw))
    base_signal = build_signal(frame, BASE_SIGNAL)
    events = event_features(frame, base_signal, BASE_SIGNAL)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    print(f"data {frame['ts'].iloc[0]} -> {frame['ts'].iloc[-1]} rows={len(frame)}")
    print(f"base_signal_count={int(np.count_nonzero(base_signal))}")

    rows: list[dict[str, Any]] = []
    trade_by_label: dict[str, list[Any]] = {}
    rules = rule_specs()
    exits = exit_specs()
    for r_idx, rule in enumerate(rules, start=1):
        keep = np.ones(len(events), dtype=bool) if not rule.conditions else apply_rule(events, rule)
        signal = filtered_signal(base_signal, events, keep)
        signal_count = int(np.count_nonzero(signal))
        if signal_count < 80:
            continue
        for exit_spec in exits:
            label = f"{BASE_SIGNAL.label}__{exit_spec.label}__{rule.label}"
            trades = simulate_live_orders(frame, signal, BASE_SIGNAL, exit_spec, label=label)
            if len(trades) < 50:
                continue
            metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
            row: dict[str, Any] = {
                "label": label,
                "trade_count": len(trades),
                "trades_per_day": len(trades) / max((end - start).total_seconds() / 86400.0, 1.0),
                "reason_counts": reason_counts(trades),
                "signal_label": BASE_SIGNAL.label,
                "exit_label": exit_spec.label,
                "rule_label": rule.label,
                "rule_conditions": json.dumps(rule.conditions, ensure_ascii=False),
                "signal_count": signal_count,
                **{f"signal_{key}": value for key, value in asdict(BASE_SIGNAL).items()},
                **{f"exit_{key}": value for key, value in asdict(exit_spec).items()},
                **metrics,
            }
            row = attach_slices(row, trades, frame)
            row["robust_pass"] = robust_pass(row)
            row["robust_score"] = robust_score(row)
            rows.append(row)
            trade_by_label[label] = trades
        if r_idx % 5 == 0:
            print(f"rule {r_idx}/{len(rules)} rows={len(rows)}", flush=True)

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["robust_pass", "robust_score", "oos_2026_06_01_to_latest_trades", "avg_trade"],
            ascending=False,
        ).reset_index(drop=True)

    monthly_rows: list[dict[str, Any]] = []
    for label in summary.head(20)["label"].to_list() if not summary.empty else []:
        trades = trade_by_label[label]
        for item in month_slices(frame):
            monthly_rows.append(
                {
                    "label": label,
                    "slice": item["name"],
                    "slice_start": item["start"],
                    "slice_end": item["end"],
                    **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"]),
                }
            )
    monthly = pd.DataFrame(monthly_rows)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(frame, summary, monthly), encoding="utf-8")
    print(f"wrote {SUMMARY_PATH}")
    print(f"wrote {MONTHLY_PATH}")
    print(f"wrote {MARKDOWN_PATH}")


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame, monthly: pd.DataFrame) -> str:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    robust_count = int(summary["robust_pass"].sum()) if "robust_pass" in summary else 0
    lines = [
        "# HYPE-5M-PBTR-V6 候选稳健性复核 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本复核只围绕 V6 搜索中出现的最强基座做邻域测试，不再重新发明信号：`EMA21/EMA55` 多头趋势内回踩恢复、`pullback_buffer=0.01`、无 K 线方向过滤、`dir_htf >= 0.5`。",
        "",
        "## 实盘边界",
        "",
        f"- 数据：Binance HYPE USDT 永续 `5m`，闭合 K 范围 `{start}` 到 `{end - pd.Timedelta(minutes=5)}`，共 `{len(frame)}` 根。",
        "- 交易：闭合 K 触发、下一根 open 入场；入场后立即挂固定 TP/SL；时间退出按到期 open；trailing 若存在只在 K 收盘后更新到下一根。",
        "",
        "## 邻域规模",
        "",
        f"- 复核行数：`{len(summary)}`。",
        f"- 严格 robust pass 行数：`{robust_count}`。",
        "- 严格口径：全样本 `>=100` 笔、PF `>=1.2`、平均每笔 `>0.2%`、payoff `>1`、最大回撤 `>-25%`，且 IS/VAL/OOS 均为正，其中 OOS 至少 `10` 笔。",
        "",
        "## Top 15",
        "",
        "| 排名 | 规则 | 出口 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | IS PF | VAL PF | OOS 笔数 | OOS PF | robust |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(summary.head(15).to_dict(orient="records"), start=1):
        lines.append(
            f"| `{rank}` | `{row['rule_label']}` | `{row['exit_label']}` | `{int(row['trade_count'])}` | "
            f"`{pct(float(row['total_return']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{num(float(row['is_2025_05_30_to_2026_03_01_profit_factor']))}` | "
            f"`{num(float(row['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{int(row['oos_2026_06_01_to_latest_trades'])}` | "
            f"`{num(float(row['oos_2026_06_01_to_latest_profit_factor']))}` | "
            f"`{'yes' if bool(row['robust_pass']) else 'no'}` |"
        )

    if not summary.empty:
        best_label = str(summary.iloc[0]["label"])
        best_monthly = monthly.loc[monthly["label"].eq(best_label)]
        lines.extend(
            [
                "",
                "## 第一候选月度",
                "",
                f"第一候选：`{best_label}`",
                "",
                "| 月份 | 交易数 | 总收益 | PF | 平均每笔 | 最大回撤 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in best_monthly.to_dict(orient="records"):
            if int(row["trades"]) == 0:
                continue
            lines.append(
                f"| `{row['slice']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
                f"`{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | `{pct(float(row['max_dd']))}` |"
            )

    verdict = (
        "存在可实盘表达、全样本和 OOS 均为正的 V6 paper 候选，但月度仍有亏损段，不能直接升为真钱生产。"
        if robust_count
        else "邻域复核没有找到足够稳健的 V6 paper 候选。"
    )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            verdict,
            "",
            "可继续的路线是把第一候选转为 paper audit runner：记录全部原始触发、过滤器接受/拒绝原因、虚拟订单和真实盘口可成交性；真钱只应在 paper 连续验证后再讨论。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_candidate_robustness.py`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 月度 CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
