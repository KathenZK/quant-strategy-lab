from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import add_features
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
)
from research_hype_5m_pbtr_v6_live_executable_search import (
    ExitSpec,
    SignalSpec,
    add_search_features,
    build_signal,
    event_features,
    filtered_signal,
    load_closed_frame,
    month_slices,
    simulate_live_orders,
    validation_slices,
)


REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation_summary.csv")
SLICES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation_validation_slices.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation_weekly.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v6_full_ablation_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/ablations/"
    "hype-5m-pbtr-v6-full-parameter-ablation-2026-06-25.md"
)


@dataclass(frozen=True, slots=True)
class V6Config:
    strategy_name: str = "HYPE-5M-PBTR-V6"
    style: str = "pullback_reclaim"
    ema_fast: int = 21
    ema_slow: int = 55
    pullback_buffer: float = 0.01
    side_mode: str = "long"
    require_candle: bool = False
    htf_threshold: float | None = 0.5
    quality_feature: str = "dir_ret_bps"
    quality_window: int | None = 192
    quality_threshold: float | None = 788.123
    tp_atr: float = 3.0
    sl_atr: float = 7.0
    trail_atr: float = 0.0
    time_exit_bars: int = 36


BASELINE = V6Config()


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def label_value(value: Any) -> str:
    return str(value).replace(".", "p").replace("-", "neg").replace("/", "_").replace(" ", "")


def signal_spec(cfg: V6Config) -> SignalSpec:
    return SignalSpec(
        style=cfg.style,
        ema_fast=cfg.ema_fast,
        ema_slow=cfg.ema_slow,
        pullback_buffer=cfg.pullback_buffer,
        side_mode=cfg.side_mode,
        require_candle=cfg.require_candle,
        htf_threshold=cfg.htf_threshold,
    )


def exit_spec(cfg: V6Config) -> ExitSpec:
    return ExitSpec(tp_atr=cfg.tp_atr, sl_atr=cfg.sl_atr, trail_atr=cfg.trail_atr, time_exit_bars=cfg.time_exit_bars)


def quality_label(cfg: V6Config) -> str:
    if cfg.quality_window is None or cfg.quality_threshold is None:
        return "none"
    return f"dir_ret{cfg.quality_window}_bps>={cfg.quality_threshold:.6g}"


def config_label(cfg: V6Config) -> str:
    return f"{signal_spec(cfg).label}__{exit_spec(cfg).label}__{quality_label(cfg)}"


def reason_counts(trades: list[Any]) -> str:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.reason] = counts.get(trade.reason, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def add_required_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = add_search_features(add_features(frame))
    close = result["close"]
    for span in (13, 72):
        column = f"ema{span}"
        if column not in result:
            result[column] = close.ewm(span=span, adjust=False, min_periods=span).mean()
    return result


def build_filtered_signal(frame: pd.DataFrame, cfg: V6Config) -> tuple[np.ndarray, int]:
    spec = signal_spec(cfg)
    raw_signal = build_signal(frame, spec)
    raw_count = int(np.count_nonzero(raw_signal))
    if cfg.quality_window is None or cfg.quality_threshold is None:
        return raw_signal, raw_count
    events = event_features(frame, raw_signal, spec)
    column = f"dir_ret{cfg.quality_window}_bps"
    if column not in events:
        raise ValueError(f"missing quality feature {column}")
    keep = np.isfinite(events[column].to_numpy("float64")) & (events[column].to_numpy("float64") >= float(cfg.quality_threshold))
    return filtered_signal(raw_signal, events, keep), raw_count


def robust_pass(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 100
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


def attach_key_slices(row: dict[str, Any], trades: list[Any], frame: pd.DataFrame) -> dict[str, Any]:
    result = dict(row)
    for item in validation_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            result[f"{item['name']}_{key}"] = value
    return result


def evaluate_variant(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[Any]]:
    cfg: V6Config = spec["cfg"]
    signal, raw_signal_count = build_filtered_signal(frame, cfg)
    label = config_label(cfg)
    trades = simulate_live_orders(frame, signal, signal_spec(cfg), exit_spec(cfg), label=label)
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    full_metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    row: dict[str, Any] = {
        "label": spec["label"],
        "config_label": label,
        "family": spec["family"],
        "parameter": spec["parameter"],
        "value": spec["value"],
        "raw_signal_count": raw_signal_count,
        "filtered_signal_count": int(np.count_nonzero(signal)),
        "reason_counts": reason_counts(trades),
        **{f"cfg_{key}": value for key, value in asdict(cfg).items()},
        **full_metrics,
    }
    row = attach_key_slices(row, trades, frame)
    row["robust_pass"] = robust_pass(row)
    row["robust_score"] = robust_score(row)

    slice_rows: list[dict[str, Any]] = []
    for item in validation_slices(frame):
        slice_rows.append(
            {
                "label": spec["label"],
                "config_label": label,
                "family": spec["family"],
                "parameter": spec["parameter"],
                "value": spec["value"],
                "slice": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"]),
            }
        )
    return row, slice_rows, trades


def build_variants() -> list[dict[str, Any]]:
    variants: list[dict[str, Any]] = [
        {
            "label": "baseline_v6",
            "family": "baseline",
            "parameter": "baseline",
            "value": "V6",
            "cfg": BASELINE,
        }
    ]

    def add(parameter: str, value: Any, *, family: str = "single_parameter", **changes: Any) -> None:
        variants.append(
            {
                "label": f"{parameter}_{label_value(value)}",
                "family": family,
                "parameter": parameter,
                "value": value,
                "cfg": replace(BASELINE, **changes),
            }
        )

    for value in (9, 13, 34):
        add("ema_fast", value, family="entry_trend", ema_fast=value)
    for value in (72, 96, 144):
        add("ema_slow", value, family="entry_trend", ema_slow=value)
    for fast, slow in ((9, 55), (13, 55), (13, 96), (21, 96), (34, 144)):
        add("ema_pair", f"{fast}/{slow}", family="entry_trend", ema_fast=fast, ema_slow=slow)
    for value in (0.0, 0.005, 0.015, 0.02):
        add("pullback_buffer", value, family="entry_trigger", pullback_buffer=value)
    for value in ("both", "short"):
        add("side_mode", value, family="entry_direction", side_mode=value)
    add("require_candle", True, family="entry_trigger", require_candle=True)
    for value in (None, 0.0, 0.25, 0.75, 1.0):
        add("htf_threshold", value, family="entry_filter", htf_threshold=value)
    add("quality_filter", "none", family="event_quality", quality_window=None, quality_threshold=None)
    for value in (48, 96, 384):
        add("quality_window", value, family="event_quality", quality_window=value)
    for value in (500.0, 600.0, 660.015, 700.0, 850.0, 1000.0):
        add("quality_threshold", value, family="event_quality", quality_threshold=value)
    for value in (2.0, 2.5, 4.0, 5.0, 6.0):
        add("tp_atr", value, family="exit_bracket", tp_atr=value)
    for value in (3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        add("sl_atr", value, family="exit_bracket", sl_atr=value)
    for value in (3.0, 4.0, 6.0):
        add("trail_atr", value, family="exit_bracket", trail_atr=value)
    for value in (12, 24, 48, 72):
        add("time_exit_bars", value, family="exit_time", time_exit_bars=value)
    return variants


def time_slices(frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling = pd.DataFrame(
        [
            {"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])}
            for item in rolling_windows(frame)
        ]
    )
    weekly = pd.DataFrame(
        [
            {"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])}
            for item in weekly_slices(frame)
        ]
    )
    monthly = pd.DataFrame(
        [
            {"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])}
            for item in month_slices(frame)
        ]
    )
    return rolling, weekly, monthly


def row_for(summary: pd.DataFrame, label: str) -> pd.Series:
    return summary.loc[summary["label"].eq(label)].iloc[0]


def table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | IS PF | VAL PF | OOS 笔数 | OOS PF | Δ收益 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | `{int(row['trades'])}` | "
            f"`{pct(float(row['total_return']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{num(float(row['is_2025_05_30_to_2026_03_01_profit_factor']))}` | "
            f"`{num(float(row['val_2026_03_01_to_2026_06_01_profit_factor']))}` | "
            f"`{int(row['oos_2026_06_01_to_latest_trades'])}` | "
            f"`{num(float(row['oos_2026_06_01_to_latest_profit_factor']))}` | "
            f"`{pct(float(row['delta_total_return']))}` |"
        )
    return lines


def render_markdown(frame: pd.DataFrame, summary: pd.DataFrame, slices: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = row_for(summary, "baseline_v6")
    variants = summary.loc[~summary["label"].eq("baseline_v6")].copy()
    ranked_bad = variants.sort_values(["delta_total_return", "robust_score"], ascending=[True, True]).head(15)
    ranked_good = variants.loc[variants["robust_pass"]].sort_values(["delta_total_return", "robust_score"], ascending=False).head(15)
    grouped_best = (
        variants.loc[variants["robust_pass"]]
        .sort_values(["robust_score", "delta_total_return"], ascending=False)
        .groupby("parameter", sort=False)
        .head(1)
    )
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    worst_week = weekly.sort_values("total_return").iloc[0]
    best_week = weekly.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly.sort_values("total_return").iloc[0]
    best_month = monthly.sort_values("total_return", ascending=False).iloc[0]

    lines = [
        "# HYPE-5M-PBTR-V6 全参数消融 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告把上一轮 paper 候选正式记录为 `HYPE-5M-PBTR-V6`，并对所有有效参数做单因子消融。所有结果继续使用真实可执行口径：闭合 K 触发、下一根 open 入场、入场即 bracket、同根 TP/SL 保守按 stop first、时间退出按到期 open。",
        "",
        "## V6 基线",
        "",
        f"- 数据：Binance HYPE USDT 永续 `5m`，闭合 K 范围 `{start}` 到 `{end - pd.Timedelta(minutes=5)}`，共 `{len(frame)}` 根。",
        "- 信号：`EMA21/EMA55` 多头趋势内回踩恢复，`pullback_buffer=0.01`，无 K 线方向过滤，`dir_htf >= 0.5`。",
        "- 质量过滤：`dir_ret192_bps >= 788.123`，即过去 `192` 根 5m K 的方向收益至少约 `7.88%`。",
        "- 出口：`TP=3ATR14`、`SL=7ATR14`、不使用 trailing，`36` 根 K 超时 open 平仓。",
        "",
        "| 交易数 | 信号数 | 总收益 | 年化倍数 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 | OOS 笔数 | OOS PF |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{int(baseline['trades'])}` | `{int(baseline['filtered_signal_count'])}` | `{pct(float(baseline['total_return']))}` | `{mult(float(baseline['annualized_multiple']))}` | `{num(float(baseline['profit_factor']))}` | `{pct(float(baseline['avg_trade']))}` | `{pct(float(baseline['win_rate']))}` | `{num(float(baseline['payoff_ratio']))}` | `{pct(float(baseline['max_dd']))}` | `{int(baseline['oos_2026_06_01_to_latest_trades'])}` | `{num(float(baseline['oos_2026_06_01_to_latest_profit_factor']))}` |",
        "",
        "## 消融规模",
        "",
        f"- 单因子变体：`{len(summary) - 1}`。",
        f"- 通过 V6 robust gate 的变体：`{int(variants['robust_pass'].sum())}`。",
        "- robust gate：全样本 `>=100` 笔、PF `>=1.2`、平均每笔 `>0.2%`、payoff `>1`、最大回撤 `>-25%`，且 IS/VAL/OOS 均为正，其中 OOS 至少 `10` 笔。",
        "",
        "## 伤害最大的改动",
        "",
        *table(ranked_bad),
        "",
        "## 通过 robust gate 且改善最大的改动",
        "",
    ]
    if ranked_good.empty:
        lines.append("无。")
    else:
        lines.extend(table(ranked_good))
    lines.extend(["", "## 每个参数的最佳通过项", ""])
    if grouped_best.empty:
        lines.append("无。")
    else:
        lines.extend(table(grouped_best))

    lines.extend(
        [
            "",
            "## V6 基线时间切片",
            "",
            "| 切片 | 交易数 | 总收益 | PF | 平均每笔 | 胜率 | payoff | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    baseline_slices = slices.loc[slices["label"].eq("baseline_v6")]
    for row in baseline_slices.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
            f"`{num(float(row['profit_factor']))}` | `{pct(float(row['avg_trade']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 周/月摘要",
            "",
            f"- 周数：`{len(weekly)}`，盈利周 `{int((weekly['total_return'] > 0).sum())}/{len(weekly)}`，中位周收益 `{pct(float(weekly['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly)}`，盈利月 `{int((monthly['total_return'] > 0).sum())}/{len(monthly)}`，中位月收益 `{pct(float(monthly['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 结论",
            "",
            "V6 的核心不是旧 V3.3/V4 的 `min_hold_bars + trailing`，而是强动量环境中的多头回踩恢复事件，再配合可立即挂单表达的固定 bracket 和时间退出。",
            "",
            "消融应优先看两件事：第一，删除或放宽事件质量过滤后是否失效；第二，TP/SL/timeout 邻域是否仍有同类可行点。若一个参数只有单点有效，就不能交给 paper runner。若多个邻域仍通过 robust gate，才说明它可能是真实结构。",
            "",
            "本轮消融结果只用于确认 V6 参数脆弱性和下一步 paper runner 配置，不应把任何样本内增强项直接升为 V7。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v6_full_ablation.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 验证切片 CSV：`{SLICES_PATH}`",
            f"- 滚动切片 CSV：`{ROLLING_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_PATH}`",
            f"- 月切片 CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def main() -> None:
    raw = load_closed_frame()
    frame = add_required_features(raw)
    summary_rows: list[dict[str, Any]] = []
    slice_rows_all: list[dict[str, Any]] = []
    baseline_trades: list[Any] | None = None

    variants = build_variants()
    print(f"data {frame['ts'].iloc[0]} -> {frame['ts'].iloc[-1]} rows={len(frame)} variants={len(variants)}")
    for idx, spec in enumerate(variants, start=1):
        row, slice_rows, trades = evaluate_variant(frame, spec)
        summary_rows.append(row)
        slice_rows_all.extend(slice_rows)
        if spec["label"] == "baseline_v6":
            baseline_trades = trades
        if idx % 10 == 0 or idx == len(variants):
            print(f"variant {idx}/{len(variants)} rows={len(summary_rows)}", flush=True)

    if baseline_trades is None:
        raise RuntimeError("baseline trades not captured")

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"].eq("baseline_v6")].iloc[0]
    for column in ("total_return", "annualized_multiple", "equity_multiple", "profit_factor", "avg_trade", "win_rate", "payoff_ratio", "max_dd"):
        summary[f"delta_{column}"] = summary[column] - baseline[column]
    summary = summary.sort_values(["robust_pass", "robust_score", "delta_total_return"], ascending=False).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows_all)
    rolling, weekly, monthly = time_slices(frame, baseline_trades)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICES_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(frame, summary, slices, rolling, weekly, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V6",
                "definition": asdict(BASELINE),
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "validation_slices": str(SLICES_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(summary.head(15)[["label", "trades", "total_return", "profit_factor", "avg_trade", "win_rate", "payoff_ratio", "max_dd", "robust_pass", "robust_score"]].to_string(index=False))


if __name__ == "__main__":
    main()
