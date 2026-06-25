from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v3-3_full_ablation.py")
REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates_summary.csv")
SLICES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates_validation_slices.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates_weekly.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-4_combo_candidates_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v3-4-combo-candidates-2026-06-24.md"
)


def load_v33_module() -> Any:
    spec = importlib.util.spec_from_file_location("v33_full_ablation", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v33 = load_v33_module()


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "neg").replace("/", "_")


def build_combo_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = [
        {
            "label": "baseline_v33",
            "family": "baseline",
            "parameter": "baseline",
            "value": "V3.3",
            "cfg": v33.V33_CONFIG,
            "notes": "V3.3 baseline",
        }
    ]

    trend_options = [
        ("ema21_96", 21, 96),
        ("ema9_96", 9, 96),
        ("ema13_96", 13, 96),
        ("ema13_72", 13, 72),
        ("ema21_55", 21, 55),
        ("ema21_72", 21, 72),
    ]
    pullback_options = [0.01, 0.02]
    stop_options = [0.5, 0.25]
    trail_options = [0.75, 0.5]
    hold_options = [9, 12, 18]

    seen: set[tuple[int, int, float, float, float, int]] = set()
    for trend_label, ema_fast, ema_slow in trend_options:
        for pullback_buffer in pullback_options:
            for stop_atr in stop_options:
                for trail_atr in trail_options:
                    for min_hold_bars in hold_options:
                        key = (ema_fast, ema_slow, pullback_buffer, stop_atr, trail_atr, min_hold_bars)
                        if key in seen:
                            continue
                        seen.add(key)
                        label = (
                            f"combo_{trend_label}_pb{label_value(pullback_buffer)}"
                            f"_sl{label_value(stop_atr)}_tr{label_value(trail_atr)}_mh{min_hold_bars}"
                        )
                        specs.append(
                            {
                                "label": label,
                                "family": "v3_4_combo_candidate",
                                "parameter": "combo",
                                "value": f"{trend_label}/pb={pullback_buffer}/sl={stop_atr}/trail={trail_atr}/hold={min_hold_bars}",
                                "cfg": replace(
                                    v33.V33_CONFIG,
                                    ema_fast=ema_fast,
                                    ema_slow=ema_slow,
                                    pullback_buffer=pullback_buffer,
                                    stop_atr=stop_atr,
                                    trail_atr=trail_atr,
                                    min_hold_bars=min_hold_bars,
                                ),
                                "notes": "",
                            }
                        )
    return specs


def render_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 编号 | EMA | pb | stop | trail | min_hold | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 最差切片 PF |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['candidate_id']}` | `{int(row['cfg_ema_fast'])}/{int(row['cfg_ema_slow'])}` | `{row['cfg_pullback_buffer']}` | `{row['cfg_stop_atr']}` | `{row['cfg_trail_atr']}` | `{int(row['cfg_min_hold_bars'])}` | `{int(row['full_trades'])}` | `{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | `{num(float(row['full_payoff_ratio']))}` | `{pct(float(row['full_max_dd']))}` | `{num(float(row['min_slice_profit_factor']))}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("baseline_v33")].iloc[0]
    combos = summary.loc[summary["family"].eq("v3_4_combo_candidate")].copy()
    practical = combos.loc[combos["is_practical_candidate"]].copy()
    top_raw = combos.sort_values("full_total_return", ascending=False).head(12)
    top_practical = practical.sort_values("full_total_return", ascending=False).head(12)
    top_by_pf = practical.sort_values(["full_profit_factor", "full_total_return"], ascending=False).head(12)
    top = top_practical.iloc[0] if len(top_practical) else combos.sort_values("full_total_return", ascending=False).iloc[0]
    worst_week = weekly.sort_values("total_return").iloc[0]
    best_week = weekly.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly.sort_values("total_return").iloc[0]
    best_month = monthly.sort_values("total_return", ascending=False).iloc[0]

    lines = [
        "# HYPE-5M-PBTR-V4 来源组合测试 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告基于 V3.3 全参数消融，把有效单因子增强项组合测试。最强组合已提升记录为 `HYPE-5M-PBTR-V4`。`trail_atr=0` 因不可实盘复现，`min_hold_bars=24` 因回撤过大，均不进入组合候选网格。",
        "",
        "表格使用短编号（如 `C001`）避免 Markdown 预览挤压；完整组合 label 保留在 CSV/JSON 产物中。",
        "",
        "组合网格：",
        "",
        "- EMA：`21/96`、`9/96`、`13/96`、`13/72`、`21/55`、`21/72`。",
        "- `pullback_buffer`：`0.01`、`0.02`。",
        "- `stop_atr`：`0.5`、`0.25`。",
        "- `trail_atr`：`0.75`、`0.5`。",
        "- `min_hold_bars`：`9`、`12`、`18`。",
        "",
        "## V3.3 基线",
        "",
        "| 交易数 | 年化 | 累计收益 | 胜率 | PF | payoff | 最大回撤 | 最差切片 PF |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{int(baseline['full_trades'])}` | `{mult(float(baseline['full_annualized_multiple']))}` | `{pct(float(baseline['full_total_return']))}` | `{pct(float(baseline['full_win_rate']))}` | `{num(float(baseline['full_profit_factor']))}` | `{num(float(baseline['full_payoff_ratio']))}` | `{pct(float(baseline['full_max_dd']))}` | `{num(float(baseline['min_slice_profit_factor']))}` |",
        "",
        "## 最强实用候选",
        "",
        *render_table(top_practical),
        "",
        "实用候选筛选条件：最大回撤不劣于 `-12%`，最差验证切片 PF `>= 3.0`，且交易数不少于 `3000`。这是为了先排除明显过度延迟退出或样本切片失衡的组合。",
        "",
        "## 原始收益排名",
        "",
        *render_table(top_raw),
        "",
        "## PF 排名",
        "",
        *render_table(top_by_pf),
        "",
        "## 当前最佳候选",
        "",
        f"- 暂定候选：`{top['candidate_id']}`。",
        f"- 参数：`ema_fast={int(top['cfg_ema_fast'])}`，`ema_slow={int(top['cfg_ema_slow'])}`，`pullback_buffer={top['cfg_pullback_buffer']}`，`stop_atr={top['cfg_stop_atr']}`，`trail_atr={top['cfg_trail_atr']}`，`min_hold_bars={int(top['cfg_min_hold_bars'])}`。",
        f"- 表现：交易 `{int(top['full_trades'])}` 笔，年化 `{mult(float(top['full_annualized_multiple']))}`，胜率 `{pct(float(top['full_win_rate']))}`，PF `{num(float(top['full_profit_factor']))}`，payoff `{num(float(top['full_payoff_ratio']))}`，最大回撤 `{pct(float(top['full_max_dd']))}`。",
        f"- 相对 V3.3：累计收益差 `{pct(float(top['delta_full_total_return']))}`，PF 差 `{num(float(top['delta_full_profit_factor']))}`，最大回撤差 `{pct(float(top['delta_full_max_dd']))}`。",
        "",
        "## 最佳候选时间切片",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rolling.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly)}`，盈利周 `{int((weekly['total_return'] > 0).sum())}/{len(weekly)}`，中位周收益 `{pct(float(weekly['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly)}`，盈利月 `{int((monthly['total_return'] > 0).sum())}/{len(monthly)}`，中位月收益 `{pct(float(monthly['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 结论",
            "",
            "组合测试确实找到了样本内显著优于 V3.3 的候选。最强实用候选主要来自 `trail_atr=0.5`、更长 `min_hold_bars` 和更紧 `stop_atr=0.25` 的组合，说明 V3.3 的收益核心仍集中在退出路径管理，而不是增加新入场过滤器。",
            "",
            "但这些组合更依赖止损/追踪止损成交质量，且比 V3.3 更激进。最强组合已记录为 `HYPE-5M-PBTR-V4`，需要继续看实盘可行性审计、成本压力、成交路径审计和 paper-live 对照，不应直接替代 V3.3。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-4_combo_candidates.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 验证切片 CSV：`{SLICES_PATH}`",
            f"- 滚动切片 CSV：`{ROLLING_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_PATH}`",
            f"- 月切片 CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    slices = v33.validation_slices(raw)
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    trades_by_label: dict[str, list[Any]] = {}
    frame_by_label: dict[str, pd.DataFrame] = {}

    for spec in build_combo_specs():
        summary, rows, trades, _signal, frame = v33.evaluate_variant(raw, slices, spec)
        summary_rows.append({**summary, "notes": spec.get("notes", "")})
        slice_rows.extend(rows)
        trades_by_label[spec["label"]] = trades
        frame_by_label[spec["label"]] = frame

    summary_df = pd.DataFrame(summary_rows)
    baseline = summary_df.loc[summary_df["label"].eq("baseline_v33")].iloc[0]
    for column in ("full_total_return", "full_annualized_multiple", "full_equity_multiple", "full_max_dd", "full_win_rate", "full_profit_factor", "full_payoff_ratio"):
        summary_df[f"delta_{column}"] = summary_df[column] - baseline[column]
    summary_df["is_practical_candidate"] = (
        summary_df["family"].eq("v3_4_combo_candidate")
        & summary_df["full_max_dd"].ge(-0.12)
        & summary_df["min_slice_profit_factor"].ge(3.0)
        & summary_df["full_trades"].ge(3000)
    )
    summary_df["candidate_id"] = "BASE"
    combo_labels = summary_df.loc[summary_df["family"].eq("v3_4_combo_candidate")].sort_values("full_total_return", ascending=False)["label"].tolist()
    for idx, label in enumerate(combo_labels, start=1):
        summary_df.loc[summary_df["label"].eq(label), "candidate_id"] = f"C{idx:03d}"
    slices_df = pd.DataFrame(slice_rows)

    practical = summary_df.loc[summary_df["is_practical_candidate"]].copy()
    top_label = practical.sort_values("full_total_return", ascending=False).iloc[0]["label"] if len(practical) else summary_df.loc[summary_df["family"].eq("v3_4_combo_candidate")].sort_values("full_total_return", ascending=False).iloc[0]["label"]
    rolling_df, weekly_df, monthly_df = v33.baseline_time_slices(frame_by_label[top_label], trades_by_label[top_label])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_PATH, index=False)
    slices_df.to_csv(SLICES_PATH, index=False)
    rolling_df.to_csv(ROLLING_PATH, index=False)
    weekly_df.to_csv(WEEKLY_PATH, index=False)
    monthly_df.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary_df, rolling_df, weekly_df, monthly_df), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V4-source-combos",
                "source": str(SOURCE_PATH),
                "baseline": asdict(v33.V33_CONFIG),
                "top_label": top_label,
                "cost_model": {
                    "fee_rate_per_fill": v33.FEE_RATE_PER_FILL,
                    "entry_slippage_rate": v33.ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": v33.EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": v33.NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "validation_slices": str(SLICES_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary_df.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(f"top_label={top_label}")
    printable = summary_df.loc[summary_df["is_practical_candidate"]].sort_values("full_total_return", ascending=False).head(12)
    print(printable[["label", "full_trades", "full_annualized_multiple", "full_win_rate", "full_profit_factor", "full_max_dd", "min_slice_profit_factor"]].to_string(index=False))


if __name__ == "__main__":
    main()
