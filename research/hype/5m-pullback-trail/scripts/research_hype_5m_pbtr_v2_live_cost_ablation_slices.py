from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal, first_event_offset
from research_hype_5m_pbtr_v2_ablation_slices import (
    FINAL_FILTER_THRESHOLD,
    LEVERAGE,
    V2_BASE_CONFIG,
    apply_final_filter,
    build_variants,
    metric_with_sides,
    rolling_windows,
    weekly_slices,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m, metric_from_trades, validation_slices


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v2_live_cost_ablation_slices.json")
ABLATION_SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v2_live_cost_ablation_summary.csv")
ABLATION_SLICE_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v2_live_cost_ablation_validation_slices.csv")
WEEKLY_SLICE_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v2_live_cost_weekly_slices.csv")
ROLLING_WINDOW_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v2_live_cost_rolling_windows.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/ablations/"
    "hype-5m-pullback-trail-v2-live-cost-ablation-slices-2026-06-23.md"
)

REAL_TOTAL_TURNOVER_USDT = 7374.2110
REAL_TOTAL_FEE_USDT = 3.0578
REAL_ENTRY_FEE_USDT = 1.8451
REAL_EXIT_FEE_USDT = 1.2128
REAL_ENTRY_SLIPPAGE_USDT = 3.9547
REAL_EXIT_SLIPPAGE_USDT = -0.9719
REAL_NET_SLIPPAGE_USDT = 2.9828

FEE_RATE_PER_FILL = REAL_TOTAL_FEE_USDT / REAL_TOTAL_TURNOVER_USDT
ENTRY_SLIPPAGE_RATE = 10.73 / 10000.0
EXIT_SLIPPAGE_RATE = -2.64 / 10000.0
NET_SLIPPAGE_RATE_ON_TURNOVER = REAL_NET_SLIPPAGE_USDT / REAL_TOTAL_TURNOVER_USDT


def simulate_trades_live_cost(frame: pd.DataFrame, signal: np.ndarray, cfg: SearchConfig) -> list[Trade]:
    if "_ts_ns" in frame.columns:
        ts_ns = frame["_ts_ns"].to_numpy("int64")
    else:
        ts_ns = frame["ts"].map(lambda value: pd.Timestamp(value).value).to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    exit_ema = frame[f"ema{cfg.exit_ema}"].to_numpy("float64") if cfg.exit_ema else np.full(len(frame), np.nan)
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        atr_value = float(atr[sig_i])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        stop_price = entry_price - direction * cfg.stop_atr * atr_value
        target_price = entry_price + direction * cfg.tp_atr * atr_value
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        sl = slice(entry_i, end_i + 1)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]

        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.full(len(high_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.maximum(stop_levels, prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
            target_hit = high_seg >= target_price
            ema_exit = close_seg < exit_ema[sl] if cfg.exit_ema else np.zeros(len(high_seg), dtype=bool)
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.full(len(low_seg), stop_price)
            if cfg.trail_atr > 0:
                stop_levels = np.minimum(stop_levels, prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
            target_hit = low_seg <= target_price
            ema_exit = close_seg > exit_ema[sl] if cfg.exit_ema else np.zeros(len(low_seg), dtype=bool)

        if cfg.min_hold_bars > 0:
            stop_hit[: cfg.min_hold_bars] = False
            target_hit[: cfg.min_hold_bars] = False
            ema_exit[: cfg.min_hold_bars] = False
        event_mask = stop_hit | target_hit | ema_exit
        offset = first_event_offset(event_mask)
        reason = "time"
        if offset is None:
            offset = len(close_seg) - 1
            raw_exit_price = float(close_seg[offset])
        elif stop_hit[offset]:
            reason = "stop"
            raw_exit_price = float(stop_levels[offset])
        elif target_hit[offset]:
            reason = "target"
            raw_exit_price = float(target_price)
        else:
            reason = "ema_exit"
            raw_exit_price = float(close_seg[offset])

        path_high = high_seg[: offset + 1]
        path_low = low_seg[: offset + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))

        exit_i = entry_i + offset
        exit_price = float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
        trades.append(
            Trade(
                config=cfg.name,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(exit_i - entry_i + 1),
                net_ret_1x=float(net),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades


def evaluate_variant_live_cost(
    frame: pd.DataFrame,
    slices: list[dict[str, Any]],
    *,
    label: str,
    family: str,
    parameter: str,
    value: Any,
    cfg: SearchConfig,
    final_filter: bool,
    final_threshold: float = FINAL_FILTER_THRESHOLD,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[Trade]]:
    signal = build_signal(frame, cfg)
    filtered_signal = apply_final_filter(
        frame,
        cfg,
        signal,
        enabled=final_filter,
        threshold=final_threshold,
    )
    trades = simulate_trades_live_cost(frame, filtered_signal, cfg)
    summary: dict[str, Any] = {
        "label": label,
        "family": family,
        "parameter": parameter,
        "value": value,
        "final_filter_enabled": final_filter,
        "final_filter_threshold": final_threshold if final_filter else None,
        "signal_count": int(np.count_nonzero(filtered_signal)),
        "trade_count": int(len(trades)),
        **{f"cfg_{key}": item for key, item in asdict(cfg).items()},
    }
    slice_rows: list[dict[str, Any]] = []
    min_win = 1.0
    min_payoff = float("inf")
    min_ann = float("inf")
    worst_dd = 0.0
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        row = {
            "label": label,
            "family": family,
            "parameter": parameter,
            "value": value,
            "slice": item["name"],
            "slice_start": item["start"],
            "slice_end": item["end"],
            **metrics,
        }
        slice_rows.append(row)
        min_win = min(min_win, float(metrics["win_rate"]))
        min_payoff = min(min_payoff, float(metrics["payoff_ratio"]))
        min_ann = min(min_ann, float(metrics["annualized_multiple"]))
        worst_dd = min(worst_dd, float(metrics["max_dd"]))
        for key, metric_value in metrics.items():
            summary[f"{item['name']}_{key}"] = metric_value
    summary["min_slice_win_rate"] = min_win
    summary["min_slice_payoff_ratio"] = min_payoff
    summary["min_slice_annualized_multiple"] = min_ann
    summary["worst_slice_max_dd"] = worst_dd
    return summary, slice_rows, trades


def run_baseline_time_slices(frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame]:
    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        weekly_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})

    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        rolling_rows.append({"window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
    return pd.DataFrame(weekly_rows), pd.DataFrame(rolling_rows)


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


def fmt_ratio(value: float) -> str:
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


def short_date(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def render_markdown(summary: pd.DataFrame, weekly_df: pd.DataFrame, rolling_df: pd.DataFrame, frame: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"] == "baseline"].iloc[0]
    lines: list[str] = [
        "# HYPE-5M-PBTR-V2 实盘成本全参数消融与时间切片报告",
        "",
        "Family id: `HYPE-5M-PBTR`",
        "",
        "版本: `HYPE-5M-PBTR-V2`",
        "",
        "报告日期: 2026-06-23",
        "",
        "脚本:",
        "",
        "- `research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v2_live_cost_ablation_slices.py`",
        "",
        "## 成本口径",
        "",
        "本报告使用用户提供的实盘成交成本，而不是旧研究默认成本。",
        "",
        "| 项目 | 数值 | 回测换算 |",
        "| --- | ---: | ---: |",
        f"| 总成交额 | `{REAL_TOTAL_TURNOVER_USDT:.4f} USDT` | - |",
        f"| 总手续费 | `{REAL_TOTAL_FEE_USDT:.4f} USDT` | `{FEE_RATE_PER_FILL * 10000:.4f} bps/成交额` |",
        f"| 入场手续费 | `{REAL_ENTRY_FEE_USDT:.4f} USDT` | 记录值 |",
        f"| 出场手续费 | `{REAL_EXIT_FEE_USDT:.4f} USDT` | 记录值 |",
        f"| 入场滑点 | `{REAL_ENTRY_SLIPPAGE_USDT:+.4f} USDT` | `{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps` |",
        f"| 出场滑点 | `{REAL_EXIT_SLIPPAGE_USDT:+.4f} USDT` | `{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps` |",
        f"| 净滑点成本 | `{REAL_NET_SLIPPAGE_USDT:+.4f} USDT` | `{NET_SLIPPAGE_RATE_ON_TURNOVER * 10000:+.4f} bps/总成交额` |",
        "",
        "实现方式：开仓成交价按 `+10.73 bps` 的不利滑点处理，平仓成交价按 `-2.64 bps` 的有利滑点处理；手续费按每次成交额的 `4.1465 bps` 扣除，单笔交易费用按 `fee_rate * (entry_notional + exit_notional)` 计入。",
        "",
        "## 摘要",
        "",
        f"- 数据范围：`{pd.Timestamp(frame['ts'].iloc[0])}` → `{pd.Timestamp(frame['ts'].iloc[-1])}`，Binance HYPE USDT 永续 `5m`。",
        f"- V2 基线信号数 `{int(baseline['signal_count'])}`，交易数 `{int(baseline['trade_count'])}`。",
        f"- 实盘成本后全样本权益倍数 `{mult(float(baseline['full_equity_multiple']), 4)}`，累计收益 `{pct(float(baseline['full_total_return']))}`，胜率 `{pct(float(baseline['full_win_rate']))}`，盈亏比 `{num(float(baseline['full_payoff_ratio']), 2)}`，最大回撤 `{pct(float(baseline['full_max_dd']))}`。",
        f"- 相比旧 `0.04% fee + 0.01% slip` 口径，手续费接近，但开仓滑点显著更重；收益仍为正，不过高频版本对开仓滑点非常敏感。",
        "",
        "## 1. 最近窗口表现",
        "",
        "| 窗口 | 区间 | 交易数 | 多/空 | 多空比 | 多仓占比 | 空仓占比 | 累计收益 | 年化倍数 | 胜率 | 盈亏比 | 多胜率 | 空胜率 | 最大回撤 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rolling_df.to_dict(orient="records"):
        lines.append(
            "| "
            f"{window_label(str(row['window']))} | "
            f"{short_date(row['slice_start'])} → {short_date(pd.Timestamp(row['slice_end']) - pd.Timedelta(minutes=5))} | "
            f"{int(row['trades'])} | "
            f"{int(row['long_trades'])}/{int(row['short_trades'])} | "
            f"{fmt_ratio(float(row['long_short_ratio']))} | "
            f"{pct(float(row['long_share']), 1)} | "
            f"{pct(float(row['short_share']), 1)} | "
            f"{pct(float(row['total_return']))} | "
            f"{mult(float(row['annualized_multiple']), 2)} | "
            f"{pct(float(row['win_rate']))} | "
            f"{num(float(row['payoff_ratio']), 2)} | "
            f"{pct(float(row['long_win_rate']))} | "
            f"{pct(float(row['short_win_rate']))} | "
            f"{pct(float(row['max_dd']))} |"
        )

    profitable_weeks = int((weekly_df["total_return"] > 0).sum())
    worst_week = weekly_df.sort_values("total_return").iloc[0]
    best_week = weekly_df.sort_values("total_return", ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## 2. 按周切片表现",
            "",
            f"共切出 `{len(weekly_df)}` 个 7 天窗口，盈利周 `{profitable_weeks}/{len(weekly_df)}`。",
            "",
            "| 指标 | 数值 |",
            "| --- | ---: |",
            f"| 平均交易数/周 | `{weekly_df['trades'].mean():.1f}` |",
            f"| 平均胜率 | `{pct(float(weekly_df['win_rate'].mean()))}` |",
            f"| 中位周收益 | `{pct(float(weekly_df['total_return'].median()))}` |",
            f"| 盈利周占比 | `{pct(profitable_weeks / len(weekly_df))}` |",
            f"| 最大单周收益 | `{pct(float(best_week['total_return']))}`（{short_date(best_week['slice_start'])} → {short_date(pd.Timestamp(best_week['slice_end']) - pd.Timedelta(minutes=5))}，{int(best_week['trades'])} 笔） |",
            f"| 最小单周收益 | `{pct(float(worst_week['total_return']))}`（{short_date(worst_week['slice_start'])} → {short_date(pd.Timestamp(worst_week['slice_end']) - pd.Timedelta(minutes=5))}，{int(worst_week['trades'])} 笔） |",
            "",
            "### 全部周明细",
            "",
            "| 周窗口 | 交易数 | 多/空 | 多空比 | 多占比 | 空占比 | 周收益 | 胜率 | 盈亏比 | 多胜率 | 空胜率 | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for idx, row in enumerate(weekly_df.to_dict(orient="records"), start=1):
        lines.append(
            "| "
            f"{idx:03d} {short_date(row['slice_start'])} → {short_date(pd.Timestamp(row['slice_end']) - pd.Timedelta(minutes=5))} | "
            f"{int(row['trades'])} | "
            f"{int(row['long_trades'])}/{int(row['short_trades'])} | "
            f"{fmt_ratio(float(row['long_short_ratio']))} | "
            f"{pct(float(row['long_share']), 1)} | "
            f"{pct(float(row['short_share']), 1)} | "
            f"{pct(float(row['total_return']))} | "
            f"{pct(float(row['win_rate']))} | "
            f"{num(float(row['payoff_ratio']), 2)} | "
            f"{pct(float(row['long_win_rate']))} | "
            f"{pct(float(row['short_win_rate']))} | "
            f"{pct(float(row['max_dd']))} |"
        )

    sort_cols = [
        "label",
        "family",
        "parameter",
        "value",
        "trade_count",
        "full_total_return",
        "full_annualized_multiple",
        "full_win_rate",
        "full_payoff_ratio",
        "full_profit_factor",
        "full_max_dd",
        "min_slice_win_rate",
        "min_slice_payoff_ratio",
        "worst_slice_max_dd",
        "delta_full_total_return",
        "delta_full_win_rate",
        "delta_full_payoff_ratio",
        "delta_full_max_dd",
    ]
    ablation = summary[sort_cols].copy()
    ablation = ablation.sort_values(["family", "parameter", "label"]).reset_index(drop=True)
    lines.extend(
        [
            "",
            "## 3. 全参数消融",
            "",
            f"共评估 `{len(ablation)}` 个变体，含 V2 baseline。`Δ` 列均相对 baseline。",
            "",
            "| 变体 | 参数 | 值 | 交易数 | 累计收益 | 年化 | 胜率 | 盈亏比 | PF | 最大回撤 | 最差切片胜率 | 最差切片盈亏比 | Δ收益 | Δ胜率 | Δ盈亏比 | Δ回撤 |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in ablation.to_dict(orient="records"):
        lines.append(
            "| "
            f"`{row['label']}` | "
            f"`{row['parameter']}` | "
            f"`{row['value']}` | "
            f"{int(row['trade_count'])} | "
            f"{pct(float(row['full_total_return']))} | "
            f"{mult(float(row['full_annualized_multiple']), 2)} | "
            f"{pct(float(row['full_win_rate']))} | "
            f"{num(float(row['full_payoff_ratio']), 2)} | "
            f"{num(float(row['full_profit_factor']), 2)} | "
            f"{pct(float(row['full_max_dd']))} | "
            f"{pct(float(row['min_slice_win_rate']))} | "
            f"{num(float(row['min_slice_payoff_ratio']), 2)} | "
            f"{pct(float(row['delta_full_total_return']))} | "
            f"{pct(float(row['delta_full_win_rate']))} | "
            f"{num(float(row['delta_full_payoff_ratio']), 2)} | "
            f"{pct(float(row['delta_full_max_dd']))} |"
        )

    lines.extend(
        [
            "",
            "## 4. 本轮结论",
            "",
            "- 实盘成本口径下，`HYPE-5M-PBTR-V2` 仍保持正收益和正盈亏比，但开仓滑点从旧研究的 `1 bps` 抬升到 `10.73 bps`，明显压缩高频策略的复利表现。",
            "- 最近 `1w/1m/3m/6m/full` 均为正收益；需要重点关注最近窗口的多空结构漂移，因为部分周会高度偏多或偏空。",
            "- 如果后续实盘滑点继续维持当前水平，下一步比继续放宽信号更重要的是做执行侧优化：降低开仓冲击、提高限价成交率，并单独记录 maker/taker、开平仓方向和行情波动状态。",
            "",
            "## 产物",
            "",
            f"- JSON：`{REPORT_PATH}`",
            f"- 消融汇总 CSV：`{ABLATION_SUMMARY_PATH}`",
            f"- 验证切片 CSV：`{ABLATION_SLICE_PATH}`",
            f"- 周切片 CSV：`{WEEKLY_SLICE_PATH}`",
            f"- 最近窗口 CSV：`{ROLLING_WINDOW_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    frame = add_features(load_all_hype_5m())
    args = SimpleNamespace(min_full_trades=80, min_slice_trades=12, min_forward_trades=5)
    validation = validation_slices(frame, args)

    summary_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    baseline_trades: list[Trade] | None = None

    for variant in build_variants():
        final_threshold = float(variant.get("final_threshold", FINAL_FILTER_THRESHOLD))
        summary, slices_for_variant, trades = evaluate_variant_live_cost(
            frame,
            validation,
            label=variant["label"],
            family=variant["family"],
            parameter=variant["parameter"],
            value=variant["value"],
            cfg=variant["cfg"],
            final_filter=variant["final_filter"],
            final_threshold=final_threshold,
        )
        summary_rows.append(summary)
        validation_rows.extend(slices_for_variant)
        if variant["label"] == "baseline":
            baseline_trades = trades

    if baseline_trades is None:
        raise RuntimeError("baseline trades missing")

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"] == "baseline"].iloc[0]
    summary["delta_full_annualized_multiple"] = summary["full_annualized_multiple"] - float(
        baseline["full_annualized_multiple"]
    )
    summary["delta_full_total_return"] = summary["full_total_return"] - float(baseline["full_total_return"])
    summary["delta_full_win_rate"] = summary["full_win_rate"] - float(baseline["full_win_rate"])
    summary["delta_full_payoff_ratio"] = summary["full_payoff_ratio"] - float(baseline["full_payoff_ratio"])
    summary["delta_full_max_dd"] = summary["full_max_dd"] - float(baseline["full_max_dd"])
    summary["delta_full_trades"] = summary["full_trades"] - int(baseline["full_trades"])
    summary["delta_min_slice_annualized_multiple"] = summary["min_slice_annualized_multiple"] - float(
        baseline["min_slice_annualized_multiple"]
    )
    summary["delta_min_slice_win_rate"] = summary["min_slice_win_rate"] - float(baseline["min_slice_win_rate"])
    summary["delta_min_slice_payoff_ratio"] = summary["min_slice_payoff_ratio"] - float(
        baseline["min_slice_payoff_ratio"]
    )
    summary["delta_worst_slice_max_dd"] = summary["worst_slice_max_dd"] - float(baseline["worst_slice_max_dd"])

    weekly_df, rolling_df = run_baseline_time_slices(frame, baseline_trades)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(ABLATION_SUMMARY_PATH, index=False)
    pd.DataFrame(validation_rows).to_csv(ABLATION_SLICE_PATH, index=False)
    weekly_df.to_csv(WEEKLY_SLICE_PATH, index=False)
    rolling_df.to_csv(ROLLING_WINDOW_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, weekly_df, rolling_df, frame), encoding="utf-8")

    top_negative = summary.sort_values("delta_full_total_return").head(12)
    top_positive = summary.sort_values("delta_full_total_return", ascending=False).head(12)

    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V2",
                "cost_model": {
                    "real_total_turnover_usdt": REAL_TOTAL_TURNOVER_USDT,
                    "real_total_fee_usdt": REAL_TOTAL_FEE_USDT,
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "leverage": LEVERAGE,
                "final_filter_threshold": FINAL_FILTER_THRESHOLD,
                "base_config": asdict(V2_BASE_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ablation_summary_csv": str(ABLATION_SUMMARY_PATH),
                    "ablation_validation_slices_csv": str(ABLATION_SLICE_PATH),
                    "weekly_slices_csv": str(WEEKLY_SLICE_PATH),
                    "rolling_windows_csv": str(ROLLING_WINDOW_PATH),
                },
                "baseline": baseline.to_dict(),
                "rolling_windows": rolling_df.to_dict(orient="records"),
                "weekly_slice_count": int(len(weekly_df)),
                "top_negative_full_return_deltas": top_negative.to_dict(orient="records"),
                "top_positive_full_return_deltas": top_positive.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"wrote={REPORT_PATH}")
    print(f"markdown={MARKDOWN_PATH}")
    print(f"summary={ABLATION_SUMMARY_PATH}")
    print(f"weekly={WEEKLY_SLICE_PATH}")
    print(f"rolling={ROLLING_WINDOW_PATH}")
    print("\nRolling windows:")
    print(
        rolling_df[
            [
                "window",
                "slice_start",
                "slice_end",
                "trades",
                "long_trades",
                "short_trades",
                "long_short_ratio",
                "long_share",
                "short_share",
                "total_return",
                "annualized_multiple",
                "win_rate",
                "payoff_ratio",
                "long_win_rate",
                "short_win_rate",
                "max_dd",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
