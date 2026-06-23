from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal
from research_hype_5m_pbtr_v2_ablation_slices import (
    FINAL_FILTER_THRESHOLD,
    LEVERAGE,
    V2_BASE_CONFIG,
    apply_final_filter,
    metric_with_sides,
    rolling_windows,
    weekly_slices,
)
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    MARKDOWN_PATH as V2_LIVE_COST_MARKDOWN_PATH,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
    REAL_TOTAL_FEE_USDT,
    REAL_TOTAL_TURNOVER_USDT,
    simulate_trades_live_cost,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("reports/hype_5m_pbtr_v21_live_cost_variants.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v21_live_cost_variant_summary.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v21_live_cost_variant_rolling_windows.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v21_live_cost_variant_weekly_slices.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/ablations/"
    "hype-5m-pullback-trail-v21-live-cost-variants-2026-06-23.md"
)


V21_CLEAN_CONFIG = replace(
    V2_BASE_CONFIG,
    name="HYPE-5M-PBTR-V2.1-clean",
    max_regime_age=100000,
    max_dist_ema=99.0,
    min_dir_cmf=-99.0,
    require_htf=False,
    max_hold_bars=96,
    exit_ema=0,
)


def variant_specs() -> list[dict[str, Any]]:
    return [
        {
            "label": "V2.0-baseline",
            "version": "V2.0",
            "purpose": "原 V2 实盘成本基线",
            "cfg": V2_BASE_CONFIG,
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
        {
            "label": "V2.1-clean",
            "version": "V2.1",
            "purpose": "删除/固定无效参数后的简化基线",
            "cfg": V21_CLEAN_CONFIG,
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
        {
            "label": "V2.1A-return-rsi-open",
            "version": "V2.1A",
            "purpose": "在 V2.1 上放开 RSI 下界和上界，测试收益增强",
            "cfg": replace(V21_CLEAN_CONFIG, name="HYPE-5M-PBTR-V2.1A-return", min_dir_rsi=0.0, max_dir_rsi=100.0),
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
        {
            "label": "V2.1B-clean-plus-remove-roc",
            "version": "V2.1B",
            "purpose": "在 V2.1 上去掉 min_dir_roc，测试进一步简化",
            "cfg": replace(V21_CLEAN_CONFIG, name="HYPE-5M-PBTR-V2.1B-clean-plus", min_dir_roc=-99.0),
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
        {
            "label": "V2.1C-stable-htf-0p688442",
            "version": "V2.1C-HTF",
            "purpose": "在 V2.1 上提高最终 HTF 阈值，测试胜率体验",
            "cfg": replace(V21_CLEAN_CONFIG, name="HYPE-5M-PBTR-V2.1C-stable-htf"),
            "final_threshold": 0.688442,
        },
        {
            "label": "V2.1C-stable-adx14",
            "version": "V2.1C-ADX",
            "purpose": "在 V2.1 上加入 ADX14 下界，测试胜率体验",
            "cfg": replace(V21_CLEAN_CONFIG, name="HYPE-5M-PBTR-V2.1C-stable-adx", min_adx=14.0),
            "final_threshold": FINAL_FILTER_THRESHOLD,
        },
    ]


def evaluate_variant(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, list[Trade]]:
    cfg = spec["cfg"]
    signal = build_signal(frame, cfg)
    final_signal = apply_final_filter(
        frame,
        cfg,
        signal,
        enabled=True,
        threshold=float(spec["final_threshold"]),
    )
    trades = simulate_trades_live_cost(frame, final_signal, cfg)

    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    start = pd.Timestamp(frame["ts"].iloc[0])
    full_metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    summary = {
        "label": spec["label"],
        "version": spec["version"],
        "purpose": spec["purpose"],
        "final_filter_threshold": float(spec["final_threshold"]),
        "signal_count": int(np.count_nonzero(final_signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
        **{f"full_{key}": value for key, value in full_metrics.items()},
    }

    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        rolling_rows.append(
            {
                "label": spec["label"],
                "version": spec["version"],
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics,
            }
        )

    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        weekly_rows.append(
            {
                "label": spec["label"],
                "version": spec["version"],
                "window": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics,
            }
        )
    return summary, pd.DataFrame(rolling_rows), pd.DataFrame(weekly_rows), trades


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "∞"
    return f"{value:.{digits}f}x"


def ratio(value: float) -> str:
    if np.isposinf(value):
        return "∞"
    return f"{value:.2f}"


def window_label(name: str) -> str:
    return {
        "recent_1w": "最近 1 周",
        "recent_1m": "最近 1 月",
        "recent_3m": "最近 3 月",
        "recent_6m": "最近 6 月",
        "full": "全部",
    }.get(name, name)


def date_range(row: dict[str, Any]) -> str:
    start = pd.Timestamp(row["slice_start"]).strftime("%Y-%m-%d")
    end = (pd.Timestamp(row["slice_end"]) - pd.Timedelta(minutes=5)).strftime("%Y-%m-%d")
    return f"{start} → {end}"


def add_deltas(summary: pd.DataFrame) -> pd.DataFrame:
    result = summary.copy()
    base = result.loc[result["label"] == "V2.1-clean"].iloc[0]
    for key in (
        "full_total_return",
        "full_win_rate",
        "full_payoff_ratio",
        "full_profit_factor",
        "full_max_dd",
        "full_trades",
        "full_long_share",
        "full_short_share",
    ):
        result[f"delta_vs_v21_{key}"] = result[key] - base[key]
    v2 = result.loc[result["label"] == "V2.0-baseline"].iloc[0]
    for key in ("full_total_return", "full_win_rate", "full_payoff_ratio", "full_max_dd", "full_trades"):
        result[f"delta_vs_v20_{key}"] = result[key] - v2[key]
    return result


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, frame: pd.DataFrame) -> str:
    ordered = summary.set_index("label").loc[[spec["label"] for spec in variant_specs()]].reset_index()
    v21 = ordered.loc[ordered["label"] == "V2.1-clean"].iloc[0]
    v20 = ordered.loc[ordered["label"] == "V2.0-baseline"].iloc[0]

    lines: list[str] = [
        "# HYPE-5M-PBTR-V2.1 实盘成本参数简化与候选测试",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "报告日期: 2026-06-23",
        "",
        "## 目的",
        "",
        "本报告按上一轮实盘成本消融结论执行两步：",
        "",
        "1. 先把无效或可固定参数收敛为 `HYPE-5M-PBTR-V2.1-clean`。",
        "2. 再在 V2.1-clean 上测试收益增强、进一步简化、稳定性增强三类候选。",
        "",
        "成本口径沿用实盘统计：",
        "",
        f"- 手续费：`{REAL_TOTAL_FEE_USDT:.4f} / {REAL_TOTAL_TURNOVER_USDT:.4f} = {FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`。",
        f"- 开仓滑点：`{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 平仓滑点：`{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        f"- 净滑点：`{NET_SLIPPAGE_RATE_ON_TURNOVER * 10000:+.4f} bps/总成交额`。",
        "",
        "## V2.1-clean 定义",
        "",
        "相对 V2.0，V2.1-clean 只做参数简化，不改变核心机制：",
        "",
        "- 固定/移除 `max_regime_age`：设为 `100000`，不再作为真实约束。",
        "- 固定/移除 `max_dist_ema`：设为 `99.0`，不再作为真实约束。",
        "- 固定/移除 `min_dir_cmf`：设为 `-99.0`，不再作为真实约束。",
        "- 固定 `max_hold_bars=96`：上一轮显示 `96`、`576`、`100000` 结果相同。",
        "- 保持 `exit_ema=0`，不引入 EMA 退出。",
        "- 保持内部 `require_htf=false`，只使用最终 `dir_htf >= threshold`。",
        "",
        "仍保留的核心参数：`EMA21/EMA96`、`pullback_resume`、`pullback_buffer=0.01`、`stop_atr=0.5`、`trail_atr=0.75`、`min_hold_bars=6`、最终 `dir_htf>=0.5`。",
        "",
        "## 核心结论",
        "",
        f"- V2.1-clean 与 V2.0 基线表现几乎完全一致：交易数 `{int(v21['full_trades'])}` vs `{int(v20['full_trades'])}`，累计收益 `{pct(float(v21['full_total_return']))}` vs `{pct(float(v20['full_total_return']))}`。",
        "- 这说明上述参数可以从策略解释层删除或固定为常量，不影响当前实盘成本口径回测。",
        "- 收益增强分支中，放开 RSI 上下界收益最高，但胜率下降，适合作为 V2.1A 继续验证。",
        "- 稳定性分支中，提高 `dir_htf` 阈值能提高胜率和盈亏比，但会显著牺牲收益；`min_adx=14` 是更温和的胜率增强。",
        "",
        "## 全样本对比",
        "",
        "| 版本 | 说明 | 交易数 | 多/空 | 多空比 | 累计收益 | 年化倍数 | 胜率 | 盈亏比 | PF | 最大回撤 | Δ收益 vs V2.1 | Δ胜率 vs V2.1 | Δ回撤 vs V2.1 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in ordered.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['label']}` | "
            f"{row['purpose']} | "
            f"{int(row['full_trades'])} | "
            f"{int(row['full_long_trades'])}/{int(row['full_short_trades'])} | "
            f"{ratio(float(row['full_long_short_ratio']))} | "
            f"{pct(float(row['full_total_return']))} | "
            f"{mult(float(row['full_annualized_multiple']))} | "
            f"{pct(float(row['full_win_rate']))} | "
            f"{num(float(row['full_payoff_ratio']))} | "
            f"{num(float(row['full_profit_factor']))} | "
            f"{pct(float(row['full_max_dd']))} | "
            f"{pct(float(row['delta_vs_v21_full_total_return']))} | "
            f"{pct(float(row['delta_vs_v21_full_win_rate']))} | "
            f"{pct(float(row['delta_vs_v21_full_max_dd']))} |"
        )

    lines.extend(
        [
            "",
            "## 最近窗口对比",
            "",
            "| 版本 | 窗口 | 区间 | 交易数 | 多/空 | 多空比 | 累计收益 | 胜率 | 盈亏比 | 多胜率 | 空胜率 | 最大回撤 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['label']}` | "
            f"{window_label(str(row['window']))} | "
            f"{date_range(row)} | "
            f"{int(row['trades'])} | "
            f"{int(row['long_trades'])}/{int(row['short_trades'])} | "
            f"{ratio(float(row['long_short_ratio']))} | "
            f"{pct(float(row['total_return']))} | "
            f"{pct(float(row['win_rate']))} | "
            f"{num(float(row['payoff_ratio']))} | "
            f"{pct(float(row['long_win_rate']))} | "
            f"{pct(float(row['short_win_rate']))} | "
            f"{pct(float(row['max_dd']))} |"
        )

    weekly_summary_rows: list[dict[str, Any]] = []
    for label, group in weekly.groupby("label", sort=False):
        profitable = int((group["total_return"] > 0).sum())
        worst = group.sort_values("total_return").iloc[0]
        best = group.sort_values("total_return", ascending=False).iloc[0]
        weekly_summary_rows.append(
            {
                "label": label,
                "weeks": len(group),
                "avg_trades": float(group["trades"].mean()),
                "avg_win_rate": float(group["win_rate"].mean()),
                "median_return": float(group["total_return"].median()),
                "profitable_share": profitable / len(group),
                "best_return": float(best["total_return"]),
                "best_window": date_range(best.to_dict()),
                "worst_return": float(worst["total_return"]),
                "worst_window": date_range(worst.to_dict()),
            }
        )

    lines.extend(
        [
            "",
            "## 周切片摘要",
            "",
            "| 版本 | 周数 | 平均交易/周 | 平均胜率 | 中位周收益 | 盈利周占比 | 最大周收益 | 最小周收益 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in weekly_summary_rows:
        lines.append(
            "| "
            f"`{row['label']}` | "
            f"{int(row['weeks'])} | "
            f"{row['avg_trades']:.1f} | "
            f"{pct(row['avg_win_rate'])} | "
            f"{pct(row['median_return'])} | "
            f"{pct(row['profitable_share'])} | "
            f"{pct(row['best_return'])} ({row['best_window']}) | "
            f"{pct(row['worst_return'])} ({row['worst_window']}) |"
        )

    lines.extend(
        [
            "",
            "## 判断",
            "",
            "### V2.1-clean",
            "",
            "可以作为新的解释与实现基线。它把当前样本中不生效的参数固定掉，同时保留核心入场/退出机制。后续 live spec 可以用 V2.1 表达，减少误解和调参维度。",
            "",
            "### V2.1A-return-rsi-open",
            "",
            "收益最高，适合进入下一轮重点测试。但它用胜率换收益，必须继续看最近周切片和真实滑点是否稳定；若实盘胜率体验是主要目标，不应直接替换 V2.1。",
            "",
            "### V2.1B-clean-plus-remove-roc",
            "",
            "属于低风险简化：收益略增，指标几乎不变。可以和 V2.1-clean 合并，作为更干净的 V2.1B 候选。",
            "",
            "### V2.1C-stable",
            "",
            "`dir_htf>=0.688442` 更像稳定胜率版，牺牲收益较多；`min_adx=14` 更温和，胜率有所提升且仍保留较高收益。若要做实盘体验优化，优先测 `min_adx=14`，再测更高 HTF 阈值。",
            "",
            "## 产物",
            "",
            f"- 上一轮 V2 实盘成本消融：`{V2_LIVE_COST_MARKDOWN_PATH}`",
            f"- 本报告：`{MARKDOWN_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 最近窗口 CSV：`{ROLLING_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())

    summary_rows: list[dict[str, Any]] = []
    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    trade_counts: dict[str, int] = {}
    for spec in variant_specs():
        summary, rolling_df, weekly_df, trades = evaluate_variant(frame, spec)
        summary_rows.append(summary)
        rolling_frames.append(rolling_df)
        weekly_frames.append(weekly_df)
        trade_counts[spec["label"]] = len(trades)

    summary_df = add_deltas(pd.DataFrame(summary_rows))
    rolling_df = pd.concat(rolling_frames, ignore_index=True)
    weekly_df = pd.concat(weekly_frames, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(SUMMARY_PATH, index=False)
    rolling_df.to_csv(ROLLING_PATH, index=False)
    weekly_df.to_csv(WEEKLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary_df, rolling_df, weekly_df, frame), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy_family": "HYPE-5M-PBTR",
                "variants": [spec["label"] for spec in variant_specs()],
                "trade_counts": trade_counts,
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary_csv": str(SUMMARY_PATH),
                    "rolling_csv": str(ROLLING_PATH),
                    "weekly_csv": str(WEEKLY_PATH),
                },
                "summary": summary_df.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"wrote={REPORT_PATH}")
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={SUMMARY_PATH}")
    print(f"rolling={ROLLING_PATH}")
    print(f"weekly={WEEKLY_PATH}")
    print(
        summary_df[
            [
                "label",
                "full_trades",
                "full_total_return",
                "full_win_rate",
                "full_payoff_ratio",
                "full_profit_factor",
                "full_max_dd",
                "delta_vs_v21_full_total_return",
                "delta_vs_v21_full_win_rate",
                "delta_vs_v21_full_max_dd",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
