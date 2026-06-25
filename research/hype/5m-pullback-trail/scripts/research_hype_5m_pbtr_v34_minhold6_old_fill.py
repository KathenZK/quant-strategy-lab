from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_pbtr_v33_no_stop_atr_old_fill import (
    BASELINE_CONFIG,
    END_TS,
    V33BaselineConfig,
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


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_summary.csv")
DIAGNOSTICS_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_trade_diagnostics.csv")
CROSSED_SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_crossed_summary.csv")
ROLLING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_rolling.csv")
WEEKLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_weekly.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v34_minhold6_old_fill_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v3-4-minhold6-old-fill-2026-06-25.md"
)


V34_MINHOLD6_CONFIG = V33BaselineConfig(
    strategy_name="HYPE-5M-PBTR-V3.4-minhold6-old-fill",
    ema_fast=21,
    ema_slow=96,
    pullback_buffer=0.01,
    stop_atr=0.5,
    trail_atr=0.75,
    min_hold_bars=6,
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


def build_crossed_summary(diagnostics: pd.DataFrame, unlock_bar_by_config: dict[str, int]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for config in diagnostics["config"].drop_duplicates().tolist():
        cfg_df = diagnostics.loc[diagnostics["config"].eq(config)].copy()
        crossed = cfg_df["open_crossed_stop_at_exit_bar"].astype(bool)
        unlock_bar = unlock_bar_by_config[config]
        rows.append(crossed_metrics(f"{config}:crossed_all", cfg_df, crossed))
        rows.append(crossed_metrics(f"{config}:crossed_unlock_bar_{unlock_bar}", cfg_df, crossed & cfg_df["bars_held"].eq(unlock_bar)))
        rows.append(crossed_metrics(f"{config}:crossed_after_unlock", cfg_df, crossed & cfg_df["bars_held"].gt(unlock_bar)))
        rows.append(crossed_metrics(f"{config}:all_stops", cfg_df, cfg_df["reason"].eq("stop")))
    return pd.DataFrame(rows)


def render_markdown(summary: pd.DataFrame, crossed_summary: pd.DataFrame, rolling: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    v33 = rows[BASELINE_CONFIG.strategy_name]
    v34 = rows[V34_MINHOLD6_CONFIG.strategy_name]
    crossed_v34 = crossed_summary.loc[
        crossed_summary["label"].eq(f"{V34_MINHOLD6_CONFIG.strategy_name}:crossed_all")
    ].iloc[0]
    unlock_v34 = crossed_summary.loc[
        crossed_summary["label"].eq(
            f"{V34_MINHOLD6_CONFIG.strategy_name}:crossed_unlock_bar_{V34_MINHOLD6_CONFIG.min_hold_bars + 1}"
        )
    ].iloc[0]
    rolling_v34 = rolling.loc[rolling["label"].eq(V34_MINHOLD6_CONFIG.strategy_name)].copy()
    lines = [
        "# HYPE-5M-PBTR-V3.4-minhold6 旧口径回测 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本诊断按用户要求，在 `HYPE-5M-PBTR-V3.3` 基础上只把 `min_hold_bars` 从 `9` 改回 `6`，其余参数保持不变，并沿用旧回测口径：锁仓期不触发策略退出，解锁后若 stop level 被触发则按 stop level 填价。",
        "",
        "说明：仓库历史中已有 `V3.4 combo candidates` 作为 V4 来源记录；为避免覆盖历史含义，本文将本次版本暂记为 `V3.4-minhold6`。",
        "",
        "## 参数对比",
        "",
        "| 版本 | ema_fast | ema_slow | pullback_buffer | stop_atr | trail_atr | min_hold_bars |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `V3.3` | `{BASELINE_CONFIG.ema_fast}` | `{BASELINE_CONFIG.ema_slow}` | `{BASELINE_CONFIG.pullback_buffer}` | `{BASELINE_CONFIG.stop_atr}` | `{BASELINE_CONFIG.trail_atr}` | `{BASELINE_CONFIG.min_hold_bars}` |",
        f"| `V3.4-minhold6` | `{V34_MINHOLD6_CONFIG.ema_fast}` | `{V34_MINHOLD6_CONFIG.ema_slow}` | `{V34_MINHOLD6_CONFIG.pullback_buffer}` | `{V34_MINHOLD6_CONFIG.stop_atr}` | `{V34_MINHOLD6_CONFIG.trail_atr}` | `{V34_MINHOLD6_CONFIG.min_hold_bars}` |",
        "",
        "## 全样本结果",
        "",
        "| 版本 | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `V3.3` | `{int(v33['signal_count'])}` | `{int(v33['trades'])}` | `{mult(float(v33['annualized_multiple']))}` | `{pct(float(v33['total_return']))}` | `{pct(float(v33['win_rate']))}` | `{num(float(v33['payoff_ratio']))}` | `{num(float(v33['profit_factor']))}` | `{pct(float(v33['max_dd']))}` |",
        f"| `V3.4-minhold6` | `{int(v34['signal_count'])}` | `{int(v34['trades'])}` | `{mult(float(v34['annualized_multiple']))}` | `{pct(float(v34['total_return']))}` | `{pct(float(v34['win_rate']))}` | `{num(float(v34['payoff_ratio']))}` | `{num(float(v34['profit_factor']))}` | `{pct(float(v34['max_dd']))}` |",
        "",
        "## 穿越子集",
        "",
        "| 子集 | 交易数 | 旧口径胜率 | 旧口径均值 | 旧口径 PF | 若穿越按开盘胜率 | 若穿越按开盘均值 | 若穿越按开盘 PF | 旧价相对开盘均值差 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in crossed_summary.to_dict(orient="records"):
        label = str(row["label"])
        label = label.replace(BASELINE_CONFIG.strategy_name, "V3.3")
        label = label.replace(V34_MINHOLD6_CONFIG.strategy_name, "V3.4-minhold6")
        lines.append(
            f"| `{label}` | `{int(row['trades'])}` | `{pct(float(row.get('old_fill_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('old_fill_avg_ret', np.nan)))}` | `{num(float(row.get('old_fill_pf', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_avg_ret', np.nan)))}` | "
            f"`{num(float(row.get('open_if_crossed_pf', np.nan)))}` | "
            f"`{pct(float(row.get('old_minus_open_if_crossed_avg', np.nan)))}` |"
        )
    lines.extend(
        [
            "",
            "## V3.4-minhold6 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling_v34.to_dict(orient="records"):
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
            f"把 `min_hold_bars` 从 `9` 改回 `6` 后，旧口径交易数从 `{int(v33['trades'])}` 增至 `{int(v34['trades'])}`，但 PF 从 `{num(float(v33['profit_factor']))}` 降至 `{num(float(v34['profit_factor']))}`，胜率从 `{pct(float(v33['win_rate']))}` 降至 `{pct(float(v34['win_rate']))}`，最大回撤从 `{pct(float(v33['max_dd']))}` 到 `{pct(float(v34['max_dd']))}`。",
            "",
            f"穿越问题仍明显：`V3.4-minhold6` crossed_all 有 `{int(crossed_v34['trades'])}` 笔；若穿越按 exit bar 开盘替代，PF 为 `{num(float(crossed_v34['open_if_crossed_pf']))}`、均值 `{pct(float(crossed_v34['open_if_crossed_avg_ret']))}`。刚解锁 bar 的穿越子集有 `{int(unlock_v34['trades'])}` 笔，是主要风险点。",
            "",
            "因此，`min_hold_bars=6` 更接近 V2.1A 的锁仓长度，但在 V3.3 高频无 HTF 过滤框架下，旧口径质量弱于 V3.3；它可以作为 paper 对账版本，不应直接按旧回测指标交接实盘。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v34_minhold6_old_fill.py`",
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
    frame = add_features(raw, BASELINE_CONFIG.ema_fast, BASELINE_CONFIG.ema_slow)
    signal = build_signal(frame, BASELINE_CONFIG)
    variants = [
        (BASELINE_CONFIG, True),
        (V34_MINHOLD6_CONFIG, True),
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
    crossed_summary = build_crossed_summary(
        diagnostics,
        {cfg.strategy_name: cfg.min_hold_bars + 1 for cfg, _use_initial_stop in variants},
    )
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
                "strategy": "HYPE-5M-PBTR-V3.4-minhold6 old fill diagnostic",
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
