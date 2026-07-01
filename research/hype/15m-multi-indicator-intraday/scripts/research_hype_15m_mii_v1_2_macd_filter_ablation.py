from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_15m_mii_v1_2_atr_rvol_filter_ablation as base
import research_hype_15m_mii_v1_full_ablation as v1


RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_2_macd_filter_ablation.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_macd_filter_ablation_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_macd_filter_ablation_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-2-macd-filter-ablation-2026-06-30.md"


def filter_variants() -> list[dict[str, Any]]:
    baseline = base.v12.BASE_CONFIG.filter
    return [
        {
            "variant": "baseline",
            "description": "保留 MACD 方向过滤、ATR96 0.75%-2.80%、RVOL96 >= 1.0",
            "filter_spec": baseline,
        },
        {
            "variant": "remove_macd",
            "description": "去掉 MACD 方向过滤，保留 ATR96 0.75%-2.80% 与 RVOL96 >= 1.0",
            "filter_spec": replace(baseline, min_dir_macd=-99.0),
        },
    ]


def raw_pass_count(
    trades: list[base.v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> int:
    window = base.window_trades(trades, start_ts, end_ts)
    return sum(1 for trade in window if v1.passes_filter(trade, filter_spec))


def render_markdown(summary: pd.DataFrame, quality: dict[str, Any]) -> str:
    baseline_k1 = summary.loc[
        summary["variant"].eq("baseline") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    no_macd_k1 = summary.loc[
        summary["variant"].eq("remove_macd") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    baseline_k2 = summary.loc[
        summary["variant"].eq("baseline") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    no_macd_k2 = summary.loc[
        summary["variant"].eq("remove_macd") & summary["entry_timing"].eq("K+2")
    ].iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.2 MACD 方向过滤消融 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "`MACD(12,26,9)` 方向过滤会明显减少信号，但它不是无用噪音过滤；去掉后开单数大幅增加，收益和回撤形状直接崩坏。",
        "",
        (
            f"- K+1：过滤前通过信号从 `{int(baseline_k1['raw_pass_before_single_position'])}` 增至 "
            f"`{int(no_macd_k1['raw_pass_before_single_position'])}`，最终成交从 `{int(baseline_k1['trades'])}` 增至 "
            f"`{int(no_macd_k1['trades'])}`；总收益从 `{base.fmt(baseline_k1['total_return_pct'])}%` "
            f"变为 `{base.fmt(no_macd_k1['total_return_pct'])}%`，最大回撤从 "
            f"`{base.fmt(baseline_k1['max_drawdown_pct'])}%` 恶化到 `{base.fmt(no_macd_k1['max_drawdown_pct'])}%`。"
        ),
        (
            f"- K+2：最终成交从 `{int(baseline_k2['trades'])}` 增至 `{int(no_macd_k2['trades'])}`；"
            f"总收益从 `{base.fmt(baseline_k2['total_return_pct'])}%` 变为 "
            f"`{base.fmt(no_macd_k2['total_return_pct'])}%`，最大回撤恶化到 "
            f"`{base.fmt(no_macd_k2['max_drawdown_pct'])}%`。"
        ),
        "",
        "解释：当前策略是 RSI 反转信号，MACD 方向过滤要求反转发生时仍站在短周期动量方向一侧。放开 MACD 会把大量逆短周期动量的 RSI 交叉也放进来，这些交易在 ATR bracket 出场下没有正期望。",
        "",
        "状态：本消融只用于解释低频原因，不改变 `NO-GO`。",
        "",
        "## 数据质量",
        "",
        f"- 覆盖：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 全样本对比",
        "",
        "| 变体 | 入场 | 单仓前通过信号 | 最终交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe | 平均单笔 | 最差单笔 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{row['entry_timing']}` | `{int(row['raw_pass_before_single_position'])}` | "
            f"`{int(row['trades'])}` | `{base.fmt(row['total_return_pct'])}%` | "
            f"`{base.fmt(row['annual_return_pct'])}%` | `{base.fmt(row['max_drawdown_pct'])}%` | "
            f"`{base.fmt(row['win_rate_pct'])}%` | `{base.fmt(row['profit_factor'], 3)}` | "
            f"`{base.fmt(row['trade_sharpe'])}` | `{base.fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{base.fmt(row['worst_trade_pct'], 3)}%` |"
        )
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    context, metadata, quality = base.v12.build_context()
    exit_spec = base.v12.candidate_exit_spec(base.V12_CANDIDATE)
    rows: list[dict[str, Any]] = []
    for entry_delay_bars, entry_label in base.ENTRY_DELAYS:
        trades = base.v12.simulate_atr_bracket_trades(context, base.V12_CANDIDATE, entry_delay_bars)
        for item in filter_variants():
            row = base.evaluate_row(
                variant=str(item["variant"]),
                description=str(item["description"]),
                filter_spec=item["filter_spec"],
                trades=trades,
                exit_spec=exit_spec,
                entry_label=entry_label,
                entry_delay_bars=entry_delay_bars,
                window_name="全样本",
                start_ts=context.start_ts,
                end_ts=context.end_ts,
            )
            row["raw_pass_before_single_position"] = raw_pass_count(
                trades,
                item["filter_spec"],
                context.start_ts,
                context.end_ts,
            )
            rows.append(row)

    summary = pd.DataFrame(rows)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    payload = {
        "family": base.FAMILY,
        "alias": base.ALIAS,
        "version": base.VERSION,
        "run_date": RUN_DATE,
        "status": "macd_filter_ablation_diagnostic_not_promoted",
        "metadata": metadata,
        "data_quality": quality,
        "base_config": asdict(base.v12.BASE_CONFIG),
        "v12_exit": asdict(base.V12_CANDIDATE),
        "filter_variants": [
            {
                "variant": item["variant"],
                "description": item["description"],
                "filter_spec": asdict(item["filter_spec"]),
            }
            for item in filter_variants()
        ],
        "summary": summary.to_dict(orient="records"),
        "outputs": {
            "script": str(SCRIPT_PATH),
            "summary_csv": str(SUMMARY_CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(
        json.dumps(base.json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(summary, quality), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote {SUMMARY_CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
