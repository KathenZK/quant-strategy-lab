from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade, add_features, build_signal
from research_hype_5m_pbtr_v2_ablation_slices import FINAL_FILTER_THRESHOLD, LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v3_ablation_audit import month_slices
from research_hype_5m_pbtr_v32_clean_entry_filters import V32_CONFIG
from research_hype_5m_positive_payoff_search import load_all_hype_5m, validation_slices


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation_summary.csv")
SLICES_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation_validation_slices.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v32_full_ablation_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/ablations/"
    "hype-5m-pbtr-v32-full-parameter-ablation-2026-06-24.md"
)


def filtered_signal(frame: pd.DataFrame, cfg: Any, *, final_filter: bool, threshold: float | None = None) -> np.ndarray:
    signal = build_signal(frame, cfg)
    if not final_filter:
        return signal.copy()
    sig_idx = np.flatnonzero(signal)
    if len(sig_idx) == 0:
        return signal.copy()
    threshold = FINAL_FILTER_THRESHOLD if threshold is None else float(threshold)
    side = signal[sig_idx].astype(float)
    dir_htf = side * frame["htf_spread"].to_numpy("float64")[sig_idx]
    keep = dir_htf >= threshold
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline_v32",
            "family": "baseline",
            "parameter": "baseline",
            "value": "V3.2_clean_entry_filters",
            "cfg": V32_CONFIG,
            "final_filter": False,
            "final_threshold": None,
        }
    ]

    def add(
        label: str,
        family: str,
        parameter: str,
        value: Any,
        *,
        final_filter: bool = False,
        final_threshold: float | None = None,
        **changes: Any,
    ) -> None:
        variants.append(
            {
                "label": label,
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(V32_CONFIG, **changes),
                "final_filter": final_filter,
                "final_threshold": final_threshold,
            }
        )

    for threshold in (-0.5, 0.0, 0.25, 0.5, 0.688442, 1.0):
        label = str(threshold).replace(".", "p").replace("-", "neg")
        add(f"restore_final_htf_ge_{label}", "restore_entry_filter", "final_filter_threshold", threshold, final_filter=True, final_threshold=threshold)

    add("side_long_only", "direction", "side_mode", "long", side_mode="long")
    add("side_short_only", "direction", "side_mode", "short", side_mode="short")

    for fast, slow in ((9, 55), (12, 96), (34, 144), (55, 192), (96, 384)):
        add(f"ema_pair_{fast}_{slow}", "trend_definition", "ema_pair", f"{fast}/{slow}", ema_fast=fast, ema_slow=slow)

    for style in ("breakout", "momentum", "squeeze_breakout", "channel_reclaim", "trend_rsi_rebound", "bb_reversion", "ema_deviation_revert"):
        add(f"entry_style_{style}", "entry_logic", "entry_style", style, entry_style=style)

    for value in (0.0, 0.0025, 0.005, 0.02, 99.0):
        label = str(value).replace(".", "p")
        add(f"pullback_buffer_{label}", "entry_logic", "pullback_buffer", value, pullback_buffer=value)

    for window in (24, 48, 192):
        add(f"roc_window_{window}", "inactive_parameter_probe", "roc_window", window, roc_window=window)

    # Restore filters removed in V3.2.
    add("restore_min_regime_age_3", "restore_entry_filter", "min_regime_age", 3, min_regime_age=3)
    add("restore_min_dir_roc_neg0p01", "restore_entry_filter", "min_dir_roc", -0.01, min_dir_roc=-0.01)
    add("restore_max_chop_62", "restore_entry_filter", "max_chop", 62.0, max_chop=62.0)
    add("restore_all_removed_entry_filters", "restore_entry_filter", "regime_roc_chop", "3/-0.01/62", min_regime_age=3, min_dir_roc=-0.01, max_chop=62.0)
    add("restore_max_dist_ema_0p06", "restore_entry_filter", "max_dist_ema", 0.06, max_dist_ema=0.06)
    add("restore_min_dir_cmf_neg0p30", "restore_entry_filter", "min_dir_cmf", -0.30, min_dir_cmf=-0.30)
    add("restore_rsi_55_72", "restore_entry_filter", "minmax_dir_rsi", "55/72", min_dir_rsi=55.0, max_dir_rsi=72.0)
    add("restore_min_efficiency_0p025", "restore_entry_filter", "min_efficiency", 0.025, min_efficiency=0.025)
    add("enable_min_adx_14", "restore_entry_filter", "min_adx", 14.0, min_adx=14.0)
    add("tighten_max_atr_ratio_2", "restore_entry_filter", "max_atr_ratio", 2.0, max_atr_ratio=2.0)
    add("enable_min_rvol_1", "restore_entry_filter", "min_rvol", 1.0, min_rvol=1.0)
    add("enable_require_macd", "restore_entry_filter", "require_macd", True, require_macd=True)
    add("enable_require_obv", "restore_entry_filter", "require_obv", True, require_obv=True)
    add("enable_require_htf", "restore_entry_filter", "require_htf", True, require_htf=True)

    for stop_atr in (0.25, 0.75, 1.5, 99.0):
        label = str(stop_atr).replace(".", "p")
        add(f"stop_atr_{label}", "exit_risk", "stop_atr", stop_atr, stop_atr=stop_atr)
    for tp_atr in (1.25, 1.875, 3.0, 6.0):
        label = str(tp_atr).replace(".", "p")
        add(f"tp_atr_{label}", "exit_risk", "tp_atr", tp_atr, tp_atr=tp_atr)
    for trail_atr in (0.0, 0.5, 1.0, 1.5):
        label = str(trail_atr).replace(".", "p")
        add(f"trail_atr_{label}", "exit_risk", "trail_atr", trail_atr, trail_atr=trail_atr)
    for min_hold in (0, 3, 6, 12):
        add(f"min_hold_{min_hold}", "exit_risk", "min_hold_bars", min_hold, min_hold_bars=min_hold)
    add("max_hold_48", "exit_risk", "max_hold_bars", 48, max_hold_bars=48)
    add("max_hold_576", "exit_risk", "max_hold_bars", 576, max_hold_bars=576)
    add("enable_exit_ema_21", "inactive_exit_probe", "exit_ema", 21, exit_ema=21)
    add("enable_cooldown_6", "execution_probe", "cooldown_bars", 6, cooldown_bars=6)
    return variants


def evaluate_variant(frame: pd.DataFrame, slices: list[dict[str, Any]], spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade]]:
    cfg = spec["cfg"]
    signal = filtered_signal(frame, cfg, final_filter=bool(spec["final_filter"]), threshold=spec["final_threshold"])
    trades = simulate_trades_live_cost(frame, signal, cfg)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    full_metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    summary = {
        "label": spec["label"],
        "family": spec["family"],
        "parameter": spec["parameter"],
        "value": spec["value"],
        "signal_count": int(np.count_nonzero(signal)),
        "trade_count": int(len(trades)),
        "final_filter_enabled": bool(spec["final_filter"]),
        "final_filter_threshold": spec["final_threshold"] if spec["final_filter"] else None,
        **{f"full_{k}": v for k, v in full_metrics.items()},
        **{f"cfg_{k}": v for k, v in asdict(cfg).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    min_win = 1.0
    min_pf = float("inf")
    worst_dd = 0.0
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        slice_rows.append({"label": spec["label"], "family": spec["family"], "parameter": spec["parameter"], "value": spec["value"], "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
        min_win = min(min_win, float(metrics["win_rate"]))
        min_pf = min(min_pf, float(metrics["profit_factor"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
    summary["min_slice_win_rate"] = min_win
    summary["min_slice_profit_factor"] = min_pf
    summary["worst_slice_max_dd"] = worst_dd
    return summary, slice_rows, trades


def time_slices(frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in rolling_windows(frame)])
    weekly = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in weekly_slices(frame)])
    monthly = pd.DataFrame([{"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in month_slices(frame)])
    return rolling, weekly, monthly


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("baseline_v32")].iloc[0]
    ranked_bad = summary.sort_values("delta_full_total_return").head(14)
    ranked_good = summary.sort_values("delta_full_total_return", ascending=False).head(14)
    restore = summary.loc[summary["family"].eq("restore_entry_filter")].sort_values("delta_full_total_return", ascending=False)
    worst_week = weekly.sort_values("total_return").iloc[0]
    best_week = weekly.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly.sort_values("total_return").iloc[0]
    best_month = monthly.sort_values("total_return", ascending=False).iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V3.2 全参数消融 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告以 `HYPE-5M-PBTR-V3.2` 为 baseline，沿用线上实盘成本，重新测试方向、EMA、入场形态、恢复已删除过滤器、退出参数和执行保护。",
        "",
        "## 基线",
        "",
        "| 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{int(baseline['full_trades'])}` | `{mult(float(baseline['full_annualized_multiple']))}` | `{pct(float(baseline['full_total_return']))}` | `{pct(float(baseline['full_win_rate']))}` | `{num(float(baseline['full_payoff_ratio']))}` | `{num(float(baseline['full_profit_factor']))}` | `{pct(float(baseline['full_max_dd']))}` |",
        "",
        "## 伤害最大的改动",
        "",
        "| 变体 | 参数 | 交易数 | 年化 | 胜率 | PF | 最大回撤 | Δ累计收益 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ranked_bad.to_dict(orient="records"):
        lines.append(f"| `{row['label']}` | `{row['parameter']}` | `{int(row['full_trades'])}` | `{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | `{pct(float(row['full_max_dd']))}` | `{pct(float(row['delta_full_total_return']))}` |")
    lines.extend([
        "",
        "## 样本内改善最大的改动",
        "",
        "| 变体 | 参数 | 交易数 | 年化 | 胜率 | PF | 最大回撤 | Δ累计收益 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in ranked_good.to_dict(orient="records"):
        lines.append(f"| `{row['label']}` | `{row['parameter']}` | `{int(row['full_trades'])}` | `{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | `{pct(float(row['full_max_dd']))}` | `{pct(float(row['delta_full_total_return']))}` |")
    lines.extend([
        "",
        "## 恢复已删除入场过滤器",
        "",
        "| 变体 | 恢复内容 | 交易数 | 年化 | 胜率 | PF | 最大回撤 | Δ累计收益 | 结论 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in restore.to_dict(orient="records"):
        verdict = "不恢复"
        if float(row["delta_full_total_return"]) > 0 and float(row["full_max_dd"]) >= float(baseline["full_max_dd"]) * 1.2:
            verdict = "可研究"
        lines.append(f"| `{row['label']}` | `{row['parameter']}` | `{int(row['full_trades'])}` | `{mult(float(row['full_annualized_multiple']))}` | `{pct(float(row['full_win_rate']))}` | `{num(float(row['full_profit_factor']))}` | `{pct(float(row['full_max_dd']))}` | `{pct(float(row['delta_full_total_return']))}` | {verdict} |")
    lines.extend([
        "",
        "## 时间切片",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in rolling.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend([
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
        "V3.2 全参数消融的核心判断：如果恢复被删过滤器普遍降低收益或仅改善很小，则继续保持 clean entry；如果改动 `min_hold_bars`、`trail_atr` 或 `entry_style` 会显著伤害表现，则确认 V3.2 的 alpha 仍来自 pullback/resume + min-hold + ATR trailing 的路径管理，而不是多层入场过滤。",
        "",
        "## 产物",
        "",
        f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v32_full_ablation.py`",
        f"- JSON：`{REPORT_PATH}`",
        f"- 汇总 CSV：`{SUMMARY_PATH}`",
        f"- 消融切片：`{SLICES_PATH}`",
        f"- 滚动切片：`{ROLLING_PATH}`",
        f"- 周切片：`{WEEKLY_PATH}`",
        f"- 月切片：`{MONTHLY_PATH}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    frame = frame.loc[frame["ts"] <= END_TS].reset_index(drop=True)
    args = type("Args", (), {"min_full_trades": 80, "min_slice_trades": 12, "min_forward_trades": 5})()
    slices = validation_slices(frame, args)
    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    baseline_trades: list[Trade] | None = None
    for spec in build_variants():
        summary, rows, trades = evaluate_variant(frame, slices, spec)
        summary_rows.append(summary)
        slice_rows.extend(rows)
        if spec["label"] == "baseline_v32":
            baseline_trades = trades
    if baseline_trades is None:
        raise RuntimeError("baseline_v32 missing")
    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"].eq("baseline_v32")].iloc[0]
    for key in ("annualized_multiple", "total_return", "win_rate", "payoff_ratio", "profit_factor", "max_dd", "trades"):
        summary[f"delta_full_{key}"] = summary[f"full_{key}"] - baseline[f"full_{key}"]
    rolling, weekly, monthly = time_slices(frame, baseline_trades)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    pd.DataFrame(slice_rows).to_csv(SLICES_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, rolling, weekly, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.2",
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "base_config": asdict(V32_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICES_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
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
    print(summary[["label", "family", "parameter", "value", "full_trades", "full_annualized_multiple", "full_total_return", "full_win_rate", "full_payoff_ratio", "full_profit_factor", "full_max_dd", "delta_full_total_return"]].sort_values("delta_full_total_return").to_string(index=False))


if __name__ == "__main__":
    main()
