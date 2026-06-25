from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v33_no_stop_atr_old_fill import (
    END_TS,
    V33BaselineConfig,
    V33NoStopConfig,
    add_features,
    build_signal,
    mult,
    num,
    pct,
    simulate_old_fill,
    summarize,
    time_slice_rows,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_summary.csv")
DIAGNOSTICS_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_trade_diagnostics.csv")
CROSSED_SUMMARY_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_crossed_summary.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v4-trail1-no-stop-atr-old-fill-2026-06-25.md"
)


V4_BASELINE_CONFIG = V33BaselineConfig(
    strategy_name="HYPE-5M-PBTR-V4-baseline-old-fill",
    ema_fast=9,
    ema_slow=96,
    pullback_buffer=0.01,
    stop_atr=0.25,
    trail_atr=0.5,
    min_hold_bars=18,
)
V4_NO_STOP_CONFIG = V33NoStopConfig(
    strategy_name="HYPE-5M-PBTR-V4-no-stop-atr-old-fill",
    ema_fast=9,
    ema_slow=96,
    pullback_buffer=0.01,
    trail_atr=0.5,
    min_hold_bars=18,
)
V4_TRAIL1_BASELINE_CONFIG = V33BaselineConfig(
    strategy_name="HYPE-5M-PBTR-V4-trail1-baseline-old-fill",
    ema_fast=9,
    ema_slow=96,
    pullback_buffer=0.01,
    stop_atr=0.25,
    trail_atr=1.0,
    min_hold_bars=18,
)
V4_TRAIL1_NO_STOP_CONFIG = V33NoStopConfig(
    strategy_name="HYPE-5M-PBTR-V4-trail1-no-stop-atr-old-fill",
    ema_fast=9,
    ema_slow=96,
    pullback_buffer=0.01,
    trail_atr=1.0,
    min_hold_bars=18,
)


def crossed_metrics(label: str, diagnostics: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    subset = diagnostics.loc[mask].copy()
    if subset.empty:
        return {"label": label, "trades": 0}
    old_wins = subset["net_ret_1x_old_fill"] > 0
    open_wins = subset["net_ret_1x_open_if_crossed"] > 0
    old_losses = subset.loc[~old_wins, "net_ret_1x_old_fill"]
    open_losses = subset.loc[~open_wins, "net_ret_1x_open_if_crossed"]
    old_pf = subset.loc[old_wins, "net_ret_1x_old_fill"].sum() / abs(old_losses.sum()) if len(old_losses) and old_losses.sum() < 0 else np.inf
    open_pf = subset.loc[open_wins, "net_ret_1x_open_if_crossed"].sum() / abs(open_losses.sum()) if len(open_losses) and open_losses.sum() < 0 else np.inf
    return {
        "label": label,
        "trades": int(len(subset)),
        "old_fill_win_rate": float(old_wins.mean()),
        "old_fill_avg_ret": float(subset["net_ret_1x_old_fill"].mean()),
        "old_fill_pf": float(old_pf),
        "open_if_crossed_win_rate": float(open_wins.mean()),
        "open_if_crossed_avg_ret": float(subset["net_ret_1x_open_if_crossed"].mean()),
        "open_if_crossed_pf": float(open_pf),
        "old_minus_open_if_crossed_avg": float(subset["old_minus_open_if_crossed_ret"].mean()),
    }


def build_crossed_summary(diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for config in diagnostics["config"].drop_duplicates().tolist():
        cfg_df = diagnostics.loc[diagnostics["config"].eq(config)].copy()
        crossed = cfg_df["open_crossed_stop_at_exit_bar"].astype(bool)
        rows.append(crossed_metrics(f"{config}:crossed_all", cfg_df, crossed))
        rows.append(crossed_metrics(f"{config}:crossed_bars_held_19", cfg_df, crossed & cfg_df["bars_held"].eq(19)))
        rows.append(crossed_metrics(f"{config}:crossed_bars_held_gt19", cfg_df, crossed & cfg_df["bars_held"].gt(19)))
        rows.append(crossed_metrics(f"{config}:all_stops", cfg_df, cfg_df["reason"].eq("stop")))
    return pd.DataFrame(rows)


def render_markdown(summary: pd.DataFrame, crossed_summary: pd.DataFrame, rolling: pd.DataFrame) -> str:
    short_labels = {
        V4_BASELINE_CONFIG.strategy_name: "v4_baseline_0p5",
        V4_NO_STOP_CONFIG.strategy_name: "v4_no_stop_0p5",
        V4_TRAIL1_BASELINE_CONFIG.strategy_name: "v4_baseline_trail1",
        V4_TRAIL1_NO_STOP_CONFIG.strategy_name: "v4_no_stop_trail1",
    }
    stop_labels = {
        V4_BASELINE_CONFIG.strategy_name: "0.25",
        V4_NO_STOP_CONFIG.strategy_name: "删除",
        V4_TRAIL1_BASELINE_CONFIG.strategy_name: "0.25",
        V4_TRAIL1_NO_STOP_CONFIG.strategy_name: "删除",
    }
    trail_labels = {
        V4_BASELINE_CONFIG.strategy_name: "0.5",
        V4_NO_STOP_CONFIG.strategy_name: "0.5",
        V4_TRAIL1_BASELINE_CONFIG.strategy_name: "1.0",
        V4_TRAIL1_NO_STOP_CONFIG.strategy_name: "1.0",
    }
    lines = [
        "# HYPE-5M-PBTR-V4 trail_atr=1.0 去 stop_atr 旧口径诊断 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本诊断把 V3.3 上一轮操作迁移到 V4：测试 V4 原参数、去掉 `initial_stop/stop_atr`、把 `trail_atr` 放宽到 `1.0`，以及二者同时启用。旧口径仍按 stop level 填价，不代表严格实盘成交。",
        "",
        "V4 基准参数：`ema_fast=9`、`ema_slow=96`、`pullback_buffer=0.01`、`stop_atr=0.25`、`trail_atr=0.5`、`min_hold_bars=18`。",
        "",
        "## 全样本结果",
        "",
        "| 版本 | stop_atr | trail_atr | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        label = row["label"]
        lines.append(
            f"| `{short_labels[label]}` | `{stop_labels[label]}` | `{trail_labels[label]}` | "
            f"`{int(row['signal_count'])}` | `{int(row['trades'])}` | `{mult(float(row['annualized_multiple']))}` | "
            f"`{pct(float(row['total_return']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 穿越子集",
            "",
            "| 子集 | 交易数 | 旧口径胜率 | 旧口径均值 | 旧口径 PF | 若穿越按开盘胜率 | 若穿越按开盘均值 | 若穿越按开盘 PF | 旧价相对开盘均值差 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in crossed_summary.to_dict(orient="records"):
        label = str(row["label"])
        for full, short in short_labels.items():
            label = label.replace(full, short)
        lines.append(
            f"| `{label}` | `{int(row['trades'])}` | `{pct(float(row.get('old_fill_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('old_fill_avg_ret', np.nan)))}` | `{num(float(row.get('old_fill_pf', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_avg_ret', np.nan)))}` | "
            f"`{num(float(row.get('open_if_crossed_pf', np.nan)))}` | "
            f"`{pct(float(row.get('old_minus_open_if_crossed_avg', np.nan)))}` |"
        )
    no_stop_05 = summary.loc[summary["label"].eq(V4_NO_STOP_CONFIG.strategy_name)].iloc[0]
    no_stop_1 = summary.loc[summary["label"].eq(V4_TRAIL1_NO_STOP_CONFIG.strategy_name)].iloc[0]
    crossed_05 = crossed_summary.loc[crossed_summary["label"].eq(f"{V4_NO_STOP_CONFIG.strategy_name}:crossed_all")].iloc[0]
    crossed_1 = crossed_summary.loc[crossed_summary["label"].eq(f"{V4_TRAIL1_NO_STOP_CONFIG.strategy_name}:crossed_all")].iloc[0]
    trail1_rolling = rolling.loc[rolling["label"].eq(V4_TRAIL1_NO_STOP_CONFIG.strategy_name)].copy()
    lines.extend(
        [
            "",
            "## v4_no_stop_trail1 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in trail1_rolling.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
            f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 初步结论",
            "",
            f"V4 去掉 `stop_atr` 后旧口径仍很强：PF 从基准行降到 `{num(float(no_stop_05['profit_factor']))}`，但明显弱于原 V4。这说明 `0.25 ATR initial_stop` 在 V4 里贡献更大，因为 V4 本来就是靠更紧 stop 与更长锁仓组合获得样本内收益。",
            "",
            f"在 V4 去掉 `stop_atr` 后，把 `trail_atr` 从 `0.5` 放宽到 `1.0` 会让 PF 从 `{num(float(no_stop_05['profit_factor']))}` 降到 `{num(float(no_stop_1['profit_factor']))}`，胜率从 `{pct(float(no_stop_05['win_rate']))}` 降到 `{pct(float(no_stop_1['win_rate']))}`，最大回撤从 `{pct(float(no_stop_05['max_dd']))}` 扩到 `{pct(float(no_stop_1['max_dd']))}`。",
            "",
            f"穿越数量减少但没有解决：`v4_no_stop_0p5` crossed_all 为 `{int(crossed_05['trades'])}` 笔，`v4_no_stop_trail1` 为 `{int(crossed_1['trades'])}` 笔；按 exit bar 开盘替代时，`v4_no_stop_trail1` crossed_all PF 为 `{num(float(crossed_1['open_if_crossed_pf']))}`、均值 `{pct(float(crossed_1['open_if_crossed_avg_ret']))}`，仍不是可交接口径。",
            "",
            "结论：V4 上单纯去 `stop_atr`、或再把 `trail_atr` 放宽到 `1.0`，都不能修复旧回测对穿越 stop level 填价的依赖。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v4_trail1_no_stop_atr_old_fill.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{DIAGNOSTICS_PATH}`",
            f"- 穿越摘要 CSV：`{CROSSED_SUMMARY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_features(raw, V4_BASELINE_CONFIG.ema_fast, V4_BASELINE_CONFIG.ema_slow)
    signal = build_signal(frame, V4_BASELINE_CONFIG)
    variants = [
        (V4_BASELINE_CONFIG, True),
        (V4_NO_STOP_CONFIG, False),
        (V4_TRAIL1_BASELINE_CONFIG, True),
        (V4_TRAIL1_NO_STOP_CONFIG, False),
    ]
    summary_rows: list[dict[str, Any]] = []
    diagnostics_parts: list[pd.DataFrame] = []
    rolling_parts: list[pd.DataFrame] = []
    weekly_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    for cfg, use_initial_stop in variants:
        trades, diagnostics = simulate_old_fill(frame, signal, cfg, use_initial_stop=use_initial_stop)
        summary_rows.append(summarize(cfg.strategy_name, int(np.count_nonzero(signal)), trades, frame))
        diagnostics_parts.append(diagnostics)
        rolling, weekly, monthly = time_slice_rows(frame, cfg.strategy_name, trades)
        rolling_parts.append(rolling)
        weekly_parts.append(weekly)
        monthly_parts.append(monthly)

    summary = pd.DataFrame(summary_rows)
    diagnostics = pd.concat(diagnostics_parts, ignore_index=True)
    crossed_summary = build_crossed_summary(diagnostics)
    rolling_out = pd.concat(rolling_parts, ignore_index=True)
    weekly_out = pd.concat(weekly_parts, ignore_index=True)
    monthly_out = pd.concat(monthly_parts, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)
    crossed_summary.to_csv(CROSSED_SUMMARY_PATH, index=False)
    rolling_out.to_csv(ROLLING_PATH, index=False)
    weekly_out.to_csv(WEEKLY_PATH, index=False)
    monthly_out.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, crossed_summary, rolling_out), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V4 trail_atr=1 no stop_atr old fill diagnostic",
                "variants": [
                    {"definition": asdict(cfg), "use_initial_stop": use_initial_stop}
                    for cfg, use_initial_stop in variants
                ],
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "diagnostics": str(DIAGNOSTICS_PATH),
                    "crossed_summary": str(CROSSED_SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary.to_dict(orient="records"),
                "crossed_summary": crossed_summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))
    print(crossed_summary.to_string(index=False))


if __name__ == "__main__":
    main()
