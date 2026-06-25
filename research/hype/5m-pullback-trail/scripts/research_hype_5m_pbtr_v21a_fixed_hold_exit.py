from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import SearchConfig, Trade, add_features, build_signal
from research_hype_5m_pbtr_v2_ablation_slices import (
    FINAL_FILTER_THRESHOLD,
    LEVERAGE,
    apply_final_filter,
    metric_with_sides,
)
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    REAL_TOTAL_FEE_USDT,
    REAL_TOTAL_TURNOVER_USDT,
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v21_live_cost_variants import variant_specs
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_fixed_hold_exit.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_summary.csv")
SLICE_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_slices.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_monthly.csv")
RECENT_TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_fixed_hold_exit_recent_trades.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v21a-fixed-hold-exit-2026-06-24.md"
)

HOLD_SWEEP = tuple(range(1, 25))


def v21a_spec() -> dict[str, Any]:
    for spec in variant_specs():
        if spec["version"] == "V2.1A":
            return spec
    raise RuntimeError("V2.1A spec not found")


def as_utc(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC") if pd.Timestamp(value).tzinfo else pd.Timestamp(value, tz="UTC")


def apply_entry_slippage(raw_price: float, direction: int) -> float:
    return float(raw_price * (1.0 + direction * ENTRY_SLIPPAGE_RATE))


def apply_exit_slippage(raw_price: float, direction: int) -> float:
    return float(raw_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))


def net_return(entry_price: float, exit_price: float, direction: int) -> float:
    gross = direction * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(gross - fee_cost)


def path_mae_mfe(
    *,
    high: np.ndarray,
    low: np.ndarray,
    entry_price: float,
    direction: int,
) -> tuple[float, float]:
    if direction > 0:
        mae = float(np.nanmin(low / entry_price - 1.0))
        mfe = float(np.nanmax(high / entry_price - 1.0))
    else:
        mae = float(np.nanmin(direction * (high / entry_price - 1.0)))
        mfe = float(np.nanmax(direction * (low / entry_price - 1.0)))
    return mae, mfe


def simulate_fixed_hold_exit(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: SearchConfig,
    *,
    hold_bars: int,
    exit_timing: str,
    label: str,
) -> list[Trade]:
    if hold_bars <= 0:
        raise ValueError("hold_bars must be positive")
    if exit_timing not in {"open_after_hold", "close_after_hold"}:
        raise ValueError(exit_timing)

    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    trades: list[Trade] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue

        if exit_timing == "open_after_hold":
            exit_i = entry_i + hold_bars
            if exit_i >= n:
                continue
            raw_exit_price = float(open_[exit_i])
            path_sl = slice(entry_i, exit_i)
            exit_ts = pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC")
            reason = f"fixed_hold_{hold_bars}_open"
        else:
            exit_i = entry_i + hold_bars - 1
            if exit_i >= n:
                continue
            raw_exit_price = float(close[exit_i])
            path_sl = slice(entry_i, exit_i + 1)
            exit_ts = pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC") + pd.Timedelta(minutes=5)
            reason = f"fixed_hold_{hold_bars}_close"

        if path_sl.stop <= path_sl.start:
            continue

        entry_price = apply_entry_slippage(float(open_[entry_i]), direction)
        exit_price = apply_exit_slippage(raw_exit_price, direction)
        mae, mfe = path_mae_mfe(
            high=high[path_sl],
            low=low[path_sl],
            entry_price=entry_price,
            direction=direction,
        )

        trades.append(
            Trade(
                config=label,
                signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
                entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
                exit_ts=exit_ts,
                side=direction,
                entry_price=entry_price,
                exit_price=exit_price,
                reason=reason,
                bars_held=int(hold_bars),
                net_ret_1x=net_return(entry_price, exit_price, direction),
                mae_1x=float(mae - FEE_RATE_PER_FILL),
                mfe_1x=float(mfe),
            )
        )
        blocked_until = exit_i + cfg.cooldown_bars

    return trades


def broad_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = as_utc(frame["ts"].iloc[0])
    end = as_utc(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    candidates = [
        ("full", start, end),
        ("slice_2025_05_30_2025_09_01", start, pd.Timestamp("2025-09-01T00:00:00Z")),
        ("slice_2025_09_01_2025_12_01", pd.Timestamp("2025-09-01T00:00:00Z"), pd.Timestamp("2025-12-01T00:00:00Z")),
        ("slice_2025_12_01_2026_03_01", pd.Timestamp("2025-12-01T00:00:00Z"), pd.Timestamp("2026-03-01T00:00:00Z")),
        ("slice_2026_03_01_2026_06_01", pd.Timestamp("2026-03-01T00:00:00Z"), pd.Timestamp("2026-06-01T00:00:00Z")),
        ("forward_2026_06_01_latest", pd.Timestamp("2026-06-01T00:00:00Z"), end),
        ("recent_7d", end - pd.Timedelta(days=7), end),
        ("recent_2d", end - pd.Timedelta(days=2), end),
        ("recent_1d", end - pd.Timedelta(days=1), end),
    ]

    result: list[dict[str, Any]] = []
    for name, raw_start, raw_end in candidates:
        slice_start = max(start, raw_start)
        slice_end = min(end, raw_end)
        if slice_start < slice_end:
            result.append({"name": name, "start": slice_start, "end": slice_end})
    return result


def month_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = as_utc(frame["ts"].iloc[0])
    end = as_utc(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    first_month = start.tz_convert(None).to_period("M")
    last_month = (end - pd.Timedelta(minutes=5)).tz_convert(None).to_period("M")
    result: list[dict[str, Any]] = []
    for period in pd.period_range(first_month, last_month, freq="M"):
        month_start = pd.Timestamp(period.start_time, tz="UTC")
        month_end = pd.Timestamp((period + 1).start_time, tz="UTC")
        slice_start = max(start, month_start)
        slice_end = min(end, month_end)
        if slice_start < slice_end:
            result.append({"name": str(period), "start": slice_start, "end": slice_end})
    return result


def summarize_trades(
    *,
    label: str,
    exit_model: str,
    hold_bars: int | None,
    signal_count: int,
    trades: list[Trade],
    frame: pd.DataFrame,
) -> dict[str, Any]:
    start = as_utc(frame["ts"].iloc[0])
    end = as_utc(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    metrics = metric_with_sides(trades, LEVERAGE, start=start, end=end)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return {
        "label": label,
        "exit_model": exit_model,
        "hold_bars": hold_bars,
        "signal_count": signal_count,
        "trade_count": len(trades),
        "trades_per_day": len(trades) / days,
        **metrics,
    }


def slice_rows(label: str, trades: list[Trade], frame: pd.DataFrame, slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in slices:
        metrics = metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])
        rows.append({"label": label, "slice": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metrics})
    return rows


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "config": trade.config,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": "long" if trade.side > 0 else "short",
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
            }
            for trade in trades
        ]
    )


def distribution(series: pd.Series) -> dict[str, int]:
    if series.empty:
        return {}
    return {str(key): int(value) for key, value in series.value_counts(dropna=False).sort_index().items()}


def original_trailing_unlock_diagnostics(frame: pd.DataFrame, cfg: SearchConfig, trades: list[Trade]) -> dict[str, Any]:
    if not trades:
        return {}

    index_by_ts = {pd.Timestamp(ts): i for i, ts in enumerate(frame["ts"])}
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    rows: list[dict[str, Any]] = []

    for trade in trades:
        sig_i = index_by_ts[pd.Timestamp(trade.signal_ts)]
        entry_i = index_by_ts[pd.Timestamp(trade.entry_ts)]
        exit_i = index_by_ts[pd.Timestamp(trade.exit_ts)]
        direction = int(trade.side)
        entry_price = apply_entry_slippage(float(open_[entry_i]), direction)
        initial_stop = entry_price - direction * cfg.stop_atr * float(atr[sig_i])

        if direction > 0:
            prev_extreme = max(entry_price, float(np.nanmax(high[entry_i:exit_i])) if exit_i > entry_i else entry_price)
            stop_current_atr = max(initial_stop, prev_extreme - cfg.trail_atr * float(atr[exit_i]))
            stop_prev_closed_atr = (
                max(initial_stop, prev_extreme - cfg.trail_atr * float(atr[exit_i - 1])) if exit_i > 0 else stop_current_atr
            )
            hit_current_atr = bool(low[exit_i] <= stop_current_atr)
            hit_prev_closed_atr = bool(low[exit_i] <= stop_prev_closed_atr)
            open_cross_current_atr = bool(open_[exit_i] <= stop_current_atr)
            open_cross_prev_closed_atr = bool(open_[exit_i] <= stop_prev_closed_atr)
            stop_dist_entry_bps = float((stop_current_atr / entry_price - 1.0) * 10000.0)
            open_vs_stop_bps = float((open_[exit_i] / stop_current_atr - 1.0) * 10000.0)
        else:
            prev_extreme = min(entry_price, float(np.nanmin(low[entry_i:exit_i])) if exit_i > entry_i else entry_price)
            stop_current_atr = min(initial_stop, prev_extreme + cfg.trail_atr * float(atr[exit_i]))
            stop_prev_closed_atr = (
                min(initial_stop, prev_extreme + cfg.trail_atr * float(atr[exit_i - 1])) if exit_i > 0 else stop_current_atr
            )
            hit_current_atr = bool(high[exit_i] >= stop_current_atr)
            hit_prev_closed_atr = bool(high[exit_i] >= stop_prev_closed_atr)
            open_cross_current_atr = bool(open_[exit_i] >= stop_current_atr)
            open_cross_prev_closed_atr = bool(open_[exit_i] >= stop_prev_closed_atr)
            stop_dist_entry_bps = float((entry_price / stop_current_atr - 1.0) * 10000.0)
            open_vs_stop_bps = float((stop_current_atr / open_[exit_i] - 1.0) * 10000.0)

        rows.append(
            {
                "bars_held": int(trade.bars_held),
                "reason": trade.reason,
                "side": direction,
                "net_ret_1x": trade.net_ret_1x,
                "hit_current_atr": hit_current_atr,
                "hit_prev_closed_atr": hit_prev_closed_atr,
                "open_cross_current_atr": open_cross_current_atr,
                "open_cross_prev_closed_atr": open_cross_prev_closed_atr,
                "stop_dist_entry_bps": stop_dist_entry_bps,
                "open_vs_stop_bps": open_vs_stop_bps,
                "entry_ts": trade.entry_ts,
            }
        )

    df = pd.DataFrame(rows)
    bar7 = df.loc[df["bars_held"] == 7].copy()
    bar7_stop = bar7.loc[bar7["reason"] == "stop"].copy()
    recent = df.loc[pd.to_datetime(df["entry_ts"]) >= pd.Timestamp("2026-06-01T00:00:00Z")].copy()
    recent_bar7 = recent.loc[recent["bars_held"] == 7].copy()

    def stats(series: pd.Series) -> dict[str, float]:
        if series.empty:
            return {}
        return {
            "mean": float(series.mean()),
            "p10": float(series.quantile(0.10)),
            "p25": float(series.quantile(0.25)),
            "p50": float(series.quantile(0.50)),
            "p75": float(series.quantile(0.75)),
            "p90": float(series.quantile(0.90)),
            "min": float(series.min()),
            "max": float(series.max()),
        }

    return {
        "trade_count": int(len(df)),
        "reason_distribution": distribution(df["reason"]),
        "bars_distribution": distribution(df["bars_held"]),
        "bar7_count": int(len(bar7)),
        "bar7_share": float(len(bar7) / len(df)) if len(df) else 0.0,
        "bar7_reason_distribution": distribution(bar7["reason"]),
        "bar7_stop_count": int(len(bar7_stop)),
        "bar7_stop_share_of_bar7": float(len(bar7_stop) / len(bar7)) if len(bar7) else 0.0,
        "bar7_stop_hit_current_atr_share": float(bar7_stop["hit_current_atr"].mean()) if len(bar7_stop) else 0.0,
        "bar7_stop_hit_prev_closed_atr_share": float(bar7_stop["hit_prev_closed_atr"].mean()) if len(bar7_stop) else 0.0,
        "bar7_stop_open_cross_current_atr_share": float(bar7_stop["open_cross_current_atr"].mean()) if len(bar7_stop) else 0.0,
        "bar7_stop_open_cross_prev_closed_atr_share": float(bar7_stop["open_cross_prev_closed_atr"].mean()) if len(bar7_stop) else 0.0,
        "bar7_stop_net_ret_stats": stats(bar7_stop["net_ret_1x"]),
        "bar7_stop_dist_entry_bps_stats": stats(bar7_stop["stop_dist_entry_bps"]),
        "bar7_stop_open_vs_stop_bps_stats": stats(bar7_stop["open_vs_stop_bps"]),
        "recent_trade_count": int(len(recent)),
        "recent_bar7_count": int(len(recent_bar7)),
        "recent_bar7_share": float(len(recent_bar7) / len(recent)) if len(recent) else 0.0,
        "recent_bar7_reason_distribution": distribution(recent_bar7["reason"]),
    }


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}x"


def ratio(value: float, digits: int = 2) -> str:
    if np.isposinf(value):
        return "inf"
    if not np.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def label_cn(label: str) -> str:
    return {
        "original_min_hold_trailing": "原始 V2.1A trailing",
        "fixed_open_hold_6": "固定持有 6 根，第 7 根开盘平仓",
        "fixed_close_hold_6": "固定持有 6 根，第 6 根收盘平仓",
    }.get(label, label)


def slice_cn(name: str) -> str:
    return {
        "full": "全样本",
        "slice_2025_05_30_2025_09_01": "2025-05-30 至 2025-09-01",
        "slice_2025_09_01_2025_12_01": "2025-09-01 至 2025-12-01",
        "slice_2025_12_01_2026_03_01": "2025-12-01 至 2026-03-01",
        "slice_2026_03_01_2026_06_01": "2026-03-01 至 2026-06-01",
        "forward_2026_06_01_latest": "2026-06-01 至本地最新",
        "recent_7d": "最近 7 天",
        "recent_2d": "最近 2 天",
        "recent_1d": "最近 1 天",
    }.get(name, name)


def metrics_table(rows: pd.DataFrame, labels: list[str]) -> list[str]:
    lines = [
        "| 口径 | 交易数 | 日均交易 | 总收益 | 年化 | 胜率 | PF | payoff | 平均每笔 | 最大回撤 | 多/空 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    indexed = rows.set_index("label")
    for label in labels:
        row = indexed.loc[label]
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{label_cn(label)}`",
                    f"`{int(row['trades'])}`",
                    f"`{row['trades_per_day']:.2f}`",
                    f"`{pct(float(row['total_return']))}`",
                    f"`{mult(float(row['annualized_multiple']))}`",
                    f"`{pct(float(row['win_rate']))}`",
                    f"`{ratio(float(row['profit_factor']))}`",
                    f"`{ratio(float(row['payoff_ratio']))}`",
                    f"`{pct(float(row['avg_trade']))}`",
                    f"`{pct(float(row['max_dd']))}`",
                    f"`{int(row['long_trades'])}/{int(row['short_trades'])}`",
                ]
            )
            + " |"
        )
    return lines


def hold_sweep_table(summary: pd.DataFrame, exit_model: str, *, top_n: int | None = None) -> list[str]:
    selected = summary.loc[summary["exit_model"] == exit_model].sort_values("hold_bars")
    if top_n is not None:
        selected = selected.sort_values("profit_factor", ascending=False).head(top_n).sort_values("hold_bars")
    title = "第 7 根开盘类" if exit_model == "fixed_open_after_hold" else "第 6 根收盘类"
    lines = [
        f"### {title}持有长度扫描",
        "",
        "| 持有根数 | 交易数 | 总收益 | 年化 | 胜率 | PF | payoff | 平均每笔 | 最大回撤 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in selected.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{int(row['hold_bars'])}`",
                    f"`{int(row['trades'])}`",
                    f"`{pct(float(row['total_return']))}`",
                    f"`{mult(float(row['annualized_multiple']))}`",
                    f"`{pct(float(row['win_rate']))}`",
                    f"`{ratio(float(row['profit_factor']))}`",
                    f"`{ratio(float(row['payoff_ratio']))}`",
                    f"`{pct(float(row['avg_trade']))}`",
                    f"`{pct(float(row['max_dd']))}`",
                ]
            )
            + " |"
        )
    return lines


def slice_table(slices: pd.DataFrame, label: str) -> list[str]:
    selected = slices.loc[slices["label"] == label]
    lines = [
        "| 切片 | 交易数 | 总收益 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in selected.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    slice_cn(str(row["slice"])),
                    f"`{int(row['trades'])}`",
                    f"`{pct(float(row['total_return']))}`",
                    f"`{mult(float(row['annualized_multiple']))}`",
                    f"`{pct(float(row['win_rate']))}`",
                    f"`{ratio(float(row['profit_factor']))}`",
                    f"`{ratio(float(row['payoff_ratio']))}`",
                    f"`{pct(float(row['max_dd']))}`",
                ]
            )
            + " |"
        )
    return lines


def monthly_table(monthly: pd.DataFrame, label: str) -> list[str]:
    selected = monthly.loc[monthly["label"] == label]
    lines = [
        "| 月份 | 交易数 | 总收益 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for _, row in selected.iterrows():
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['slice']}`",
                    f"`{int(row['trades'])}`",
                    f"`{pct(float(row['total_return']))}`",
                    f"`{pct(float(row['win_rate']))}`",
                    f"`{ratio(float(row['profit_factor']))}`",
                    f"`{ratio(float(row['payoff_ratio']))}`",
                    f"`{pct(float(row['max_dd']))}`",
                ]
            )
            + " |"
        )
    return lines


def render_markdown(
    *,
    frame: pd.DataFrame,
    cfg: SearchConfig,
    signal_count: int,
    summary: pd.DataFrame,
    slices: pd.DataFrame,
    monthly: pd.DataFrame,
    diagnostics: dict[str, Any],
) -> str:
    start = as_utc(frame["ts"].iloc[0])
    end = as_utc(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows = [
        "# HYPE-5M-PBTR-V2.1A 固定持有与第 7 根 trailing 诊断 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告专门回答两个线上 dry-run 观察：第一，`HYPE-5M-PBTR-V2.1A` 很多交易看起来都是 `min_hold_bars=6` 到期后结束；第二，同事判断这些交易并不是普通时间平仓，而是第 7 根第一次计算/启用 `trail_atr` 后触发 stop。这里同时验证原始 trailing 触发结构，并把它拆成可实盘复现的固定时间退出模型作为对照。",
        "",
        "## 口径",
        "",
        f"- 数据：Binance HYPE USDT 永续 `5m`，本地数据湖 `{start}` 至 `{end - pd.Timedelta(minutes=5)}`，共 `{len(frame)}` 根 K。",
        f"- 信号：沿用 `HYPE-5M-PBTR-V2.1A`，即 V2.1-clean 放开 RSI 上下界，最终过滤 `dir_htf >= {FINAL_FILTER_THRESHOLD}`。",
        f"- 信号数：`{signal_count}`。",
        f"- 成本：手续费 `{REAL_TOTAL_FEE_USDT:.4f} / {REAL_TOTAL_TURNOVER_USDT:.4f} = {FEE_RATE_PER_FILL * 10000:.4f} bps/成交额`，开仓滑点 `{ENTRY_SLIPPAGE_RATE * 10000:+.2f} bps`，平仓滑点 `{EXIT_SLIPPAGE_RATE * 10000:+.2f} bps`。",
        "- 入场：信号 K 收盘后，下一根 K 开盘成交。",
        "- `固定持有 6 根，第 7 根开盘平仓`：从入场 K 开始实际持有 6 根完整 5m K，下一根 K 开盘市价平仓。MAE/MFE 只统计实际持有的 6 根，不包含平仓 K 后续高低点。",
        "- `固定持有 6 根，第 6 根收盘平仓`：作为对照，入场后第 6 根 K 收盘平仓。",
        "- 单仓：沿用原研究的一次只持有一笔仓位；如果新信号入场时间不晚于上一笔退出 K，则保守跳过。",
        "",
        "## V2.1A 有效参数",
        "",
        "| 参数 | 值 |",
        "| --- | ---: |",
        f"| `ema_fast` | `{cfg.ema_fast}` |",
        f"| `ema_slow` | `{cfg.ema_slow}` |",
        f"| `entry_style` | `{cfg.entry_style}` |",
        f"| `pullback_buffer` | `{cfg.pullback_buffer}` |",
        f"| `roc_window` | `{cfg.roc_window}` |",
        f"| `min_dir_roc` | `{cfg.min_dir_roc}` |",
        f"| `max_chop` | `{cfg.max_chop}` |",
        f"| `stop_atr` | `{cfg.stop_atr}` |",
        f"| `trail_atr` | `{cfg.trail_atr}` |",
        f"| `min_hold_bars` | `{cfg.min_hold_bars}` |",
        f"| `max_hold_bars` | `{cfg.max_hold_bars}` |",
        f"| `final_dir_htf_threshold` | `{FINAL_FILTER_THRESHOLD}` |",
        "",
        "## 核心结果",
        "",
        *metrics_table(summary, ["original_min_hold_trailing", "fixed_open_hold_6", "fixed_close_hold_6"]),
        "",
        "解释：原始 trailing 口径仍是旧回测口径，会在解锁后把已经穿越的 stop 按 stop 价成交，所以只作为历史参照。真正可实盘的两个时间退出口径是后两行。",
        "",
        "## 原始 trailing 为什么看起来像 6 根结束",
        "",
        f"- 原始 V2.1A 回测交易数：`{diagnostics['original_trade_count']}`。",
        f"- 原始回测中 `bars_held == 7` 的交易：`{diagnostics['original_bars_held_eq_7']}`，占 `{pct(diagnostics['original_bars_held_eq_7_share'])}`。这里的 `7` 是因为 entry bar 也被计数；实盘语义接近“持有 6 根，解锁/第 7 根处理退出”。",
        f"- 原始回测最常见退出原因：`{diagnostics['original_reason_distribution']}`。",
        f"- 原始回测 bars_held 分布前几项：`{diagnostics['original_bars_distribution_head']}`。",
        f"- `bars_held == 7` 的交易里，`stop` 退出 `{diagnostics['bar7_stop_count']}` 笔，占第 7 根退出 `{pct(diagnostics['bar7_stop_share_of_bar7'])}`。",
        f"- 对这些第 7 根 stop 交易，按原回测口径使用当前 K 的 `ATR14` 时，stop 命中比例 `{pct(diagnostics['bar7_stop_hit_current_atr_share'])}`；改成只用上一根已收盘 K 的 `ATR14`，仍命中 `{pct(diagnostics['bar7_stop_hit_prev_closed_atr_share'])}`。",
        f"- 更关键的是，按原回测 stop 价看，第 7 根开盘时已经穿越 stop 的比例 `{pct(diagnostics['bar7_stop_open_cross_current_atr_share'])}`；使用上一根已收盘 ATR 后仍是 `{pct(diagnostics['bar7_stop_open_cross_prev_closed_atr_share'])}`。",
        f"- 第 7 根 stop 的单笔净收益分布：均值 `{pct(diagnostics['bar7_stop_net_ret_stats']['mean'])}`，P50 `{pct(diagnostics['bar7_stop_net_ret_stats']['p50'])}`，P90 `{pct(diagnostics['bar7_stop_net_ret_stats']['p90'])}`。",
        "",
        "这说明你的 dry-run 观察不是偶然：V2.1A 的原始 trailing 结果确实高度集中在最短解锁附近，而且几乎就是“第 7 根第一次允许 stop 后触发”。但这不等于旧 trailing 可执行；大量交易在第 7 根开盘时 stop 已经被穿越，实盘不能再按回测 stop 价成交。",
        "",
        "## 持有长度扫描",
        "",
        *hold_sweep_table(summary, "fixed_open_after_hold"),
        "",
        *hold_sweep_table(summary, "fixed_close_after_hold"),
        "",
        "## 固定持有 6 根，第 7 根开盘平仓：时间切片",
        "",
        *slice_table(slices, "fixed_open_hold_6"),
        "",
        "## 固定持有 6 根，第 7 根开盘平仓：月度稳定性",
        "",
        *monthly_table(monthly, "fixed_open_hold_6"),
        "",
        "## 结论",
        "",
    ]

    fixed_open_6 = summary.set_index("label").loc["fixed_open_hold_6"]
    fixed_close_6 = summary.set_index("label").loc["fixed_close_hold_6"]
    if float(fixed_open_6["profit_factor"]) > 1.0 and float(fixed_open_6["total_return"]) > 0:
        rows.extend(
            [
                f"`固定持有 6 根，第 7 根开盘平仓` 在全样本下是正期望：PF `{ratio(float(fixed_open_6['profit_factor']))}`，payoff `{ratio(float(fixed_open_6['payoff_ratio']))}`，平均每笔 `{pct(float(fixed_open_6['avg_trade']))}`，交易频率 `{float(fixed_open_6['trades_per_day']):.2f}` 笔/天。",
                "",
                "它比旧 trailing 口径少了不真实的 stop 成交假设，执行上也简单很多：只要记录 entry_ts / entry_bar_index，到期市价或限价容忍滑点平仓即可。",
                "",
            ]
        )
    else:
        rows.extend(
            [
                f"`固定持有 6 根，第 7 根开盘平仓` 全样本没有恢复正期望：PF `{ratio(float(fixed_open_6['profit_factor']))}`，平均每笔 `{pct(float(fixed_open_6['avg_trade']))}`。",
                "",
                "因此，线上看到的大量 `min_hold_bars=6` 附近退出，不应解释为“信号后固定持有 30 分钟就能赚钱”。更准确的解释是：原始回测大部分收益来自第 7 根首次允许 trailing stop 时按 stop 价退出，而这个 stop 价在多数交易的第 7 根开盘已经不可成交。",
                "",
            ]
        )

    rows.extend(
        [
            f"第 6 根收盘平仓作为更激进的退出对照，PF `{ratio(float(fixed_close_6['profit_factor']))}`，平均每笔 `{pct(float(fixed_close_6['avg_trade']))}`。若它明显弱于第 7 根开盘，说明完整持有 6 根 K 的等待很重要；若它相近，说明 alpha 更集中在入场后的更短窗口。",
            "",
            "但是否能实盘还要看两点：第一，月度表里是否有连续亏损月份；第二，真实 dry-run 成交日志是否能复现回测里的开/平仓滑点。你观察到一天 `14` 笔盈利是有价值的线索，但一天样本不能独立证明策略成立，应该用同一个固定持有 runner 继续积累 `200-300` 笔 paper/dry-run 订单。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_fixed_hold_exit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 切片 CSV：`{SLICE_PATH}`",
            f"- 月度 CSV：`{MONTHLY_PATH}`",
            f"- 最近交易 CSV：`{RECENT_TRADES_PATH}`",
        ]
    )
    return "\n".join(rows) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def main() -> None:
    raw = load_all_hype_5m()
    frame = add_features(raw)
    spec = v21a_spec()
    cfg: SearchConfig = spec["cfg"]
    signal = build_signal(frame, cfg)
    final_signal = apply_final_filter(frame, cfg, signal, enabled=True, threshold=float(spec["final_threshold"]))
    signal_count = int(np.count_nonzero(final_signal))

    all_trades: dict[str, list[Trade]] = {
        "original_min_hold_trailing": simulate_trades_live_cost(frame, final_signal, cfg),
    }

    for hold_bars in HOLD_SWEEP:
        all_trades[f"fixed_open_hold_{hold_bars}"] = simulate_fixed_hold_exit(
            frame,
            final_signal,
            cfg,
            hold_bars=hold_bars,
            exit_timing="open_after_hold",
            label=f"HYPE-5M-PBTR-V2.1A-fixed-open-hold-{hold_bars}",
        )
        all_trades[f"fixed_close_hold_{hold_bars}"] = simulate_fixed_hold_exit(
            frame,
            final_signal,
            cfg,
            hold_bars=hold_bars,
            exit_timing="close_after_hold",
            label=f"HYPE-5M-PBTR-V2.1A-fixed-close-hold-{hold_bars}",
        )

    summary_rows: list[dict[str, Any]] = [
        summarize_trades(
            label="original_min_hold_trailing",
            exit_model="original_min_hold_trailing",
            hold_bars=None,
            signal_count=signal_count,
            trades=all_trades["original_min_hold_trailing"],
            frame=frame,
        )
    ]
    for hold_bars in HOLD_SWEEP:
        summary_rows.append(
            summarize_trades(
                label=f"fixed_open_hold_{hold_bars}",
                exit_model="fixed_open_after_hold",
                hold_bars=hold_bars,
                signal_count=signal_count,
                trades=all_trades[f"fixed_open_hold_{hold_bars}"],
                frame=frame,
            )
        )
        summary_rows.append(
            summarize_trades(
                label=f"fixed_close_hold_{hold_bars}",
                exit_model="fixed_close_after_hold",
                hold_bars=hold_bars,
                signal_count=signal_count,
                trades=all_trades[f"fixed_close_hold_{hold_bars}"],
                frame=frame,
            )
        )
    summary = pd.DataFrame(summary_rows)

    selected_labels = ["original_min_hold_trailing", "fixed_open_hold_6", "fixed_close_hold_6"]
    slices = pd.DataFrame(
        [
            row
            for label in selected_labels
            for row in slice_rows(label, all_trades[label], frame, broad_slices(frame))
        ]
    )
    monthly = pd.DataFrame(
        [
            row
            for label in selected_labels
            for row in slice_rows(label, all_trades[label], frame, month_slices(frame))
        ]
    )

    original_df = trades_to_frame(all_trades["original_min_hold_trailing"])
    fixed_open_df = trades_to_frame(all_trades["fixed_open_hold_6"])
    recent_cutoff = as_utc(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5) - pd.Timedelta(days=7)
    recent_trades = fixed_open_df.loc[fixed_open_df["entry_ts"] >= recent_cutoff].copy()

    diagnostics = {
        "original_trade_count": int(len(original_df)),
        "original_reason_distribution": distribution(original_df["reason"]),
        "original_bars_distribution": distribution(original_df["bars_held"]),
        "original_bars_distribution_head": dict(list(distribution(original_df["bars_held"]).items())[:10]),
        "original_bars_held_eq_7": int((original_df["bars_held"] == 7).sum()),
        "original_bars_held_eq_7_share": float((original_df["bars_held"] == 7).mean()) if len(original_df) else 0.0,
    }
    diagnostics.update(original_trailing_unlock_diagnostics(frame, cfg, all_trades["original_min_hold_trailing"]))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICE_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    recent_trades.to_csv(RECENT_TRADES_PATH, index=False)

    report = {
        "family_id": "HYPE-5M-PBTR",
        "version": "V2.1A",
        "data_start": as_utc(frame["ts"].iloc[0]),
        "data_end": as_utc(frame["ts"].iloc[-1]),
        "bar_count": int(len(frame)),
        "cost_model": {
            "fee_rate_per_fill": FEE_RATE_PER_FILL,
            "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
            "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
            "real_total_fee_usdt": REAL_TOTAL_FEE_USDT,
            "real_total_turnover_usdt": REAL_TOTAL_TURNOVER_USDT,
        },
        "signal_count": signal_count,
        "cfg": asdict(cfg),
        "summary": summary.to_dict(orient="records"),
        "slices": slices.to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
        "diagnostics": diagnostics,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=json_default), encoding="utf-8")
    MARKDOWN_PATH.write_text(
        render_markdown(
            frame=frame,
            cfg=cfg,
            signal_count=signal_count,
            summary=summary,
            slices=slices,
            monthly=monthly,
            diagnostics=diagnostics,
        ),
        encoding="utf-8",
    )
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {SUMMARY_PATH}")
    print(f"wrote {SLICE_PATH}")
    print(f"wrote {MONTHLY_PATH}")
    print(f"wrote {RECENT_TRADES_PATH}")
    print(f"wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
