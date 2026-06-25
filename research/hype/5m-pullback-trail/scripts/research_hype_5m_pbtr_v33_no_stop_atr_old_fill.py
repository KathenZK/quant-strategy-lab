from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    NET_SLIPPAGE_RATE_ON_TURNOVER,
)
from research_hype_5m_pbtr_v3_ablation_audit import month_slices
from research_hype_5m_positive_payoff_search import load_all_hype_5m


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_summary.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_weekly.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_monthly.csv")
DIAGNOSTICS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_trade_diagnostics.csv")
CROSSED_BREAKDOWN_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_stop_atr_old_fill_crossed_breakdown.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-no-stop-atr-old-fill-2026-06-25.md"
)


@dataclass(frozen=True, slots=True)
class V33NoStopConfig:
    strategy_name: str = "HYPE-5M-PBTR-V3.3-no-stop-atr-old-fill"
    timeframe: str = "5m"
    ema_fast: int = 21
    ema_slow: int = 96
    pullback_buffer: float = 0.01
    trail_atr: float = 0.75
    min_hold_bars: int = 9


@dataclass(frozen=True, slots=True)
class V33BaselineConfig:
    strategy_name: str = "HYPE-5M-PBTR-V3.3-baseline-old-fill"
    timeframe: str = "5m"
    ema_fast: int = 21
    ema_slow: int = 96
    pullback_buffer: float = 0.01
    stop_atr: float = 0.5
    trail_atr: float = 0.75
    min_hold_bars: int = 9


NO_STOP_CONFIG = V33NoStopConfig()
BASELINE_CONFIG = V33BaselineConfig()


def add_features(frame: pd.DataFrame, ema_fast: int, ema_slow: int) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    result[f"ema{ema_fast}"] = close.ewm(span=ema_fast, adjust=False, min_periods=ema_fast).mean()
    result[f"ema{ema_slow}"] = close.ewm(span=ema_slow, adjust=False, min_periods=ema_slow).mean()
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    return result


def build_signal(frame: pd.DataFrame, cfg: V33NoStopConfig | V33BaselineConfig) -> np.ndarray:
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    ema_fast = frame[f"ema{cfg.ema_fast}"].to_numpy("float64")
    ema_slow = frame[f"ema{cfg.ema_slow}"].to_numpy("float64")
    atr14 = frame["atr14"].to_numpy("float64")
    spread = ema_fast - ema_slow
    direction = np.where(np.isfinite(spread), np.sign(spread), 0).astype(np.int8)
    touched = np.where(direction > 0, low <= ema_fast * (1.0 + cfg.pullback_buffer), high >= ema_fast * (1.0 - cfg.pullback_buffer))
    reclaimed = np.where(direction > 0, close > ema_fast, close < ema_fast)
    candle = np.where(direction > 0, close > open_, close < open_)
    mask = (direction != 0) & touched & reclaimed & candle & np.isfinite(atr14)
    mask = np.nan_to_num(mask, nan=False).astype(bool)
    signal = np.zeros(len(frame), dtype=np.int8)
    signal[mask] = direction[mask]
    previous_same = np.r_[False, (signal[1:] != 0) & (signal[1:] == signal[:-1])]
    signal[previous_same] = 0
    return signal


def old_fill_exit_price(raw_exit_price: float, direction: int) -> float:
    return float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))


def net_return(entry_price: float, exit_price: float, direction: int) -> float:
    gross = direction * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(gross - fee_cost)


def simulate_old_fill(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: V33NoStopConfig | V33BaselineConfig,
    *,
    use_initial_stop: bool,
) -> tuple[list[Trade], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    diagnostics: list[dict[str, Any]] = []
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
        end_i = n - 1
        sl = slice(entry_i, end_i + 1)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        open_seg = open_[sl]
        atr_seg = atr[sl]
        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            trail_levels = prev_peak - cfg.trail_atr * atr_seg
            if use_initial_stop:
                initial_stop = entry_price - getattr(cfg, "stop_atr") * atr_value
                stop_levels = np.maximum(np.full(len(high_seg), initial_stop), trail_levels)
            else:
                initial_stop = np.nan
                stop_levels = trail_levels
            stop_hit = low_seg <= stop_levels
            crossed_at_open = open_seg <= stop_levels
            market_exit_raw = np.where(crossed_at_open, open_seg, stop_levels)
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            trail_levels = prev_trough + cfg.trail_atr * atr_seg
            if use_initial_stop:
                initial_stop = entry_price + getattr(cfg, "stop_atr") * atr_value
                stop_levels = np.minimum(np.full(len(low_seg), initial_stop), trail_levels)
            else:
                initial_stop = np.nan
                stop_levels = trail_levels
            stop_hit = high_seg >= stop_levels
            crossed_at_open = open_seg >= stop_levels
            market_exit_raw = np.where(crossed_at_open, open_seg, stop_levels)

        stop_hit[: cfg.min_hold_bars] = False
        crossed_at_open[: cfg.min_hold_bars] = False
        hit_idx = np.flatnonzero(stop_hit)
        if len(hit_idx):
            offset = int(hit_idx[0])
            reason = "stop"
            raw_exit_price = float(stop_levels[offset])
            live_raw_exit_price = float(market_exit_raw[offset])
        else:
            offset = len(close_seg) - 1
            reason = "time"
            raw_exit_price = float(close_seg[offset])
            live_raw_exit_price = raw_exit_price
        path_high = high_seg[: offset + 1]
        path_low = low_seg[: offset + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))
        exit_i = entry_i + offset
        exit_price = old_fill_exit_price(raw_exit_price, direction)
        live_exit_price = old_fill_exit_price(live_raw_exit_price, direction)
        old_net = net_return(entry_price, exit_price, direction)
        live_open_net = net_return(entry_price, live_exit_price, direction)
        trade = Trade(
            config=cfg.strategy_name,
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=old_net,
            mae_1x=float(mae - FEE_RATE_PER_FILL),
            mfe_1x=float(mfe),
        )
        trades.append(trade)
        diagnostics.append(
            {
                "config": cfg.strategy_name,
                "trade_no": len(trades),
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "bars_held": trade.bars_held,
                "entry_price": entry_price,
                "raw_exit_price_old_fill": raw_exit_price,
                "exit_price_old_fill": exit_price,
                "net_ret_1x_old_fill": old_net,
                "raw_exit_price_open_if_crossed": live_raw_exit_price,
                "exit_price_open_if_crossed": live_exit_price,
                "net_ret_1x_open_if_crossed": live_open_net,
                "open_crossed_stop_at_exit_bar": bool(crossed_at_open[offset]) if reason == "stop" else False,
                "exit_bar_open": float(open_seg[offset]),
                "exit_stop_level": float(stop_levels[offset]) if reason == "stop" else np.nan,
                "initial_stop": float(initial_stop) if np.isfinite(initial_stop) else np.nan,
                "trail_stop": float(trail_levels[offset]) if reason == "stop" else np.nan,
                "reason": reason,
                "old_minus_open_if_crossed_ret": float(old_net - live_open_net),
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diagnostics)


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def summarize(label: str, signal_count: int, trades: list[Trade], frame: pd.DataFrame) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {"label": label, "signal_count": signal_count, **metric_with_sides(trades, LEVERAGE, start=start, end=end)}


def time_slice_rows(frame: pd.DataFrame, label: str, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling = pd.DataFrame([{"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in rolling_windows(frame)])
    weekly = pd.DataFrame([{"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in weekly_slices(frame)])
    monthly = pd.DataFrame([{"label": label, "window": item["name"], "slice_start": item["start"], "slice_end": item["end"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in month_slices(frame)])
    return rolling, weekly, monthly


def subset_metrics(label: str, diagnostics: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    subset = diagnostics.loc[mask].copy()
    if subset.empty:
        return {"label": label, "trades": 0}
    wins_old = subset["net_ret_1x_old_fill"] > 0
    wins_open = subset["net_ret_1x_open_if_crossed"] > 0
    gross_win_old = subset.loc[wins_old, "net_ret_1x_old_fill"].sum()
    gross_loss_old = -subset.loc[~wins_old, "net_ret_1x_old_fill"].sum()
    gross_win_open = subset.loc[wins_open, "net_ret_1x_open_if_crossed"].sum()
    gross_loss_open = -subset.loc[~wins_open, "net_ret_1x_open_if_crossed"].sum()
    return {
        "label": label,
        "trades": int(len(subset)),
        "old_fill_win_rate": float(wins_old.mean()),
        "old_fill_avg_ret": float(subset["net_ret_1x_old_fill"].mean()),
        "old_fill_pf": float(gross_win_old / gross_loss_old) if gross_loss_old > 0 else np.inf,
        "open_if_crossed_win_rate": float(wins_open.mean()),
        "open_if_crossed_avg_ret": float(subset["net_ret_1x_open_if_crossed"].mean()),
        "open_if_crossed_pf": float(gross_win_open / gross_loss_open) if gross_loss_open > 0 else np.inf,
        "old_minus_open_if_crossed_avg": float(subset["old_minus_open_if_crossed_ret"].mean()),
    }


def crossed_breakdown(diagnostics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for config in (BASELINE_CONFIG.strategy_name, NO_STOP_CONFIG.strategy_name):
        crossed = diagnostics.loc[
            diagnostics["config"].eq(config) & diagnostics["open_crossed_stop_at_exit_bar"].astype(bool)
        ].copy()
        for bucket, mask in (
            ("bars_held_10", crossed["bars_held"].eq(10)),
            ("bars_held_gt10", crossed["bars_held"].gt(10)),
            ("old_fill_positive", crossed["net_ret_1x_old_fill"].gt(0)),
            ("open_if_crossed_positive", crossed["net_ret_1x_open_if_crossed"].gt(0)),
        ):
            subset = crossed.loc[mask].copy()
            if subset.empty:
                rows.append({"config": config, "bucket": bucket, "trades": 0})
                continue
            rows.append(
                {
                    "config": config,
                    "bucket": bucket,
                    "trades": int(len(subset)),
                    "old_fill_win_rate": float((subset["net_ret_1x_old_fill"] > 0).mean()),
                    "old_fill_avg_ret": float(subset["net_ret_1x_old_fill"].mean()),
                    "open_if_crossed_win_rate": float((subset["net_ret_1x_open_if_crossed"] > 0).mean()),
                    "open_if_crossed_avg_ret": float(subset["net_ret_1x_open_if_crossed"].mean()),
                    "old_minus_open_if_crossed_avg": float(subset["old_minus_open_if_crossed_ret"].mean()),
                }
            )
    return pd.DataFrame(rows)


def render_markdown(
    summary: pd.DataFrame,
    subset_summary: pd.DataFrame,
    crossed_breakdown_summary: pd.DataFrame,
    rolling: pd.DataFrame,
) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    base = rows[BASELINE_CONFIG.strategy_name]
    no_stop = rows[NO_STOP_CONFIG.strategy_name]
    subset_rows = {row["label"]: row for row in subset_summary.to_dict(orient="records")}
    no_stop_crossed = subset_rows["no_stop_exit_open_crossed"]
    recent = rolling.loc[rolling["label"].eq(NO_STOP_CONFIG.strategy_name)].copy()
    lines = [
        "# HYPE-5M-PBTR-V3.3 去掉 stop_atr 旧口径诊断 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本诊断只回答一个问题：在保留 V3.3 旧回测口径的前提下，把 `stop_atr` / `initial_stop` 从退出状态机里移除，结果是否明显变化。",
        "",
        "旧口径定义：信号 K 收盘确认、下一根 5m K 开盘入场；前 `9` 根 K 不触发策略退出；第 `10` 根 K 起按已计算的 stop level 成交。若 stop level 已被市场穿越，仍按 stop level 填价。这是原始研究口径，不是严格实盘成交口径。",
        "",
        "## 参数变化",
        "",
        "| 版本 | EMA | pullback_buffer | stop_atr | trail_atr | min_hold_bars |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
        f"| `baseline` | `{BASELINE_CONFIG.ema_fast}/{BASELINE_CONFIG.ema_slow}` | `{BASELINE_CONFIG.pullback_buffer}` | `{BASELINE_CONFIG.stop_atr}` | `{BASELINE_CONFIG.trail_atr}` | `{BASELINE_CONFIG.min_hold_bars}` |",
        f"| `no_stop_atr` | `{NO_STOP_CONFIG.ema_fast}/{NO_STOP_CONFIG.ema_slow}` | `{NO_STOP_CONFIG.pullback_buffer}` | 删除 | `{NO_STOP_CONFIG.trail_atr}` | `{NO_STOP_CONFIG.min_hold_bars}` |",
        "",
        "## 全样本结果",
        "",
        "| 版本 | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `baseline` | `{int(base['signal_count'])}` | `{int(base['trades'])}` | `{mult(float(base['annualized_multiple']))}` | `{pct(float(base['total_return']))}` | `{pct(float(base['win_rate']))}` | `{num(float(base['payoff_ratio']))}` | `{num(float(base['profit_factor']))}` | `{pct(float(base['max_dd']))}` |",
        f"| `no_stop_atr` | `{int(no_stop['signal_count'])}` | `{int(no_stop['trades'])}` | `{mult(float(no_stop['annualized_multiple']))}` | `{pct(float(no_stop['total_return']))}` | `{pct(float(no_stop['win_rate']))}` | `{num(float(no_stop['payoff_ratio']))}` | `{num(float(no_stop['profit_factor']))}` | `{pct(float(no_stop['max_dd']))}` |",
        "",
        "## 穿越子集排查",
        "",
        "| 子集 | 交易数 | 旧口径胜率 | 旧口径均值 | 旧口径 PF | 若穿越按开盘胜率 | 若穿越按开盘均值 | 若穿越按开盘 PF | 旧价相对开盘均值差 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset_summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | "
            f"`{pct(float(row.get('old_fill_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('old_fill_avg_ret', np.nan)))}` | "
            f"`{num(float(row.get('old_fill_pf', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_avg_ret', np.nan)))}` | "
            f"`{num(float(row.get('open_if_crossed_pf', np.nan)))}` | "
            f"`{pct(float(row.get('old_minus_open_if_crossed_avg', np.nan)))}` |"
        )
    lines.extend(
        [
            "",
            "说明：`若穿越按开盘` 只在 exit bar 开盘已经穿越 stop 时把成交价替换为该根 K 开盘价；未穿越的 stop 仍按旧 stop level。它不是完整 live-realistic replay，只用于估计“穿越后按旧价成交”贡献了多少。",
            "",
            "## 穿越子集按持仓长度拆分",
            "",
            "| 版本 | 子集 | 交易数 | 旧口径胜率 | 旧口径均值 | 若穿越按开盘胜率 | 若穿越按开盘均值 | 旧价相对开盘均值差 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in crossed_breakdown_summary.to_dict(orient="records"):
        label = "baseline" if row["config"] == BASELINE_CONFIG.strategy_name else "no_stop_atr"
        lines.append(
            f"| `{label}` | `{row['bucket']}` | `{int(row['trades'])}` | "
            f"`{pct(float(row.get('old_fill_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('old_fill_avg_ret', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_win_rate', np.nan)))}` | "
            f"`{pct(float(row.get('open_if_crossed_avg_ret', np.nan)))}` | "
            f"`{pct(float(row.get('old_minus_open_if_crossed_avg', np.nan)))}` |"
        )
    lines.extend(
        [
            "",
            "拆分结果显示，刚解锁的 `bars_held_10` 穿越子集是主要问题来源；更晚触发的 `bars_held_gt10` 子集即使按开盘替代仍保持正收益。这意味着若实盘看到“穿越也赚钱”，需要先确认这些样本是否主要不是刚解锁穿越，或 runner 的 bars 计数/解锁时刻与回测不同。",
            "",
            "## no_stop_atr 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in recent.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "## 初步结论",
            "",
            f"去掉 `stop_atr` 后，旧口径仍是高正收益：PF 从 `{num(float(base['profit_factor']))}` 降到 `{num(float(no_stop['profit_factor']))}`，最大回撤从 `{pct(float(base['max_dd']))}` 扩到 `{pct(float(no_stop['max_dd']))}`。这说明 `initial_stop` 有解锁后锚点贡献，但不是收益结构的唯一来源；核心仍是 `min_hold_bars + trail_atr` 的旧填价路径。",
            "",
            f"穿越子集是下一步排查重点：`no_stop_atr` 的 exit bar 开盘已穿越 stop 子集有 `{int(no_stop_crossed['trades'])}` 笔，旧口径 PF `{num(float(no_stop_crossed['old_fill_pf']))}`、均值 `{pct(float(no_stop_crossed['old_fill_avg_ret']))}`；若这些穿越都按 exit bar 开盘价处理，PF 只有 `{num(float(no_stop_crossed['open_if_crossed_pf']))}`、均值 `{pct(float(no_stop_crossed['open_if_crossed_avg_ret']))}`。如果实盘穿越样本仍赚钱，最可能不是 `stop_atr` 本身的问题，而是实盘 runner 的“穿越定义、下单时刻、成交价、bars_held 计数或样本分布”与这里的 exit-bar-open 替代口径不一致。",
            "",
            "本报告用于排查，不作为实盘交接规格。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_no_stop_atr_old_fill.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{DIAGNOSTICS_PATH}`",
            f"- 穿越拆分 CSV：`{CROSSED_BREAKDOWN_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame = add_features(raw, BASELINE_CONFIG.ema_fast, BASELINE_CONFIG.ema_slow)
    signal = build_signal(frame, BASELINE_CONFIG)
    baseline_trades, baseline_diag = simulate_old_fill(frame, signal, BASELINE_CONFIG, use_initial_stop=True)
    no_stop_trades, no_stop_diag = simulate_old_fill(frame, signal, NO_STOP_CONFIG, use_initial_stop=False)

    summary = pd.DataFrame(
        [
            summarize(BASELINE_CONFIG.strategy_name, int(np.count_nonzero(signal)), baseline_trades, frame),
            summarize(NO_STOP_CONFIG.strategy_name, int(np.count_nonzero(signal)), no_stop_trades, frame),
        ]
    )
    rolling_parts = []
    weekly_parts = []
    monthly_parts = []
    for label, trades in [(BASELINE_CONFIG.strategy_name, baseline_trades), (NO_STOP_CONFIG.strategy_name, no_stop_trades)]:
        rolling, weekly, monthly = time_slice_rows(frame, label, trades)
        rolling_parts.append(rolling)
        weekly_parts.append(weekly)
        monthly_parts.append(monthly)
    rolling_out = pd.concat(rolling_parts, ignore_index=True)
    weekly_out = pd.concat(weekly_parts, ignore_index=True)
    monthly_out = pd.concat(monthly_parts, ignore_index=True)

    diagnostics = pd.concat([baseline_diag, no_stop_diag], ignore_index=True)
    subset_summary = pd.DataFrame(
        [
            subset_metrics(
                "baseline_exit_open_crossed",
                baseline_diag,
                baseline_diag["open_crossed_stop_at_exit_bar"].astype(bool),
            ),
            subset_metrics(
                "no_stop_exit_open_crossed",
                no_stop_diag,
                no_stop_diag["open_crossed_stop_at_exit_bar"].astype(bool),
            ),
            subset_metrics("baseline_all_stops", baseline_diag, baseline_diag["reason"].eq("stop")),
            subset_metrics("no_stop_all_stops", no_stop_diag, no_stop_diag["reason"].eq("stop")),
        ]
    )
    crossed_breakdown_summary = crossed_breakdown(diagnostics)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    rolling_out.to_csv(ROLLING_PATH, index=False)
    weekly_out.to_csv(WEEKLY_PATH, index=False)
    monthly_out.to_csv(MONTHLY_PATH, index=False)
    diagnostics.to_csv(DIAGNOSTICS_PATH, index=False)
    crossed_breakdown_summary.to_csv(CROSSED_BREAKDOWN_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, subset_summary, crossed_breakdown_summary, rolling_out), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3 no stop_atr old fill diagnostic",
                "baseline_definition": asdict(BASELINE_CONFIG),
                "no_stop_definition": asdict(NO_STOP_CONFIG),
                "cost_model": {
                    "fee_rate_per_fill": FEE_RATE_PER_FILL,
                    "entry_slippage_rate": ENTRY_SLIPPAGE_RATE,
                    "exit_slippage_rate": EXIT_SLIPPAGE_RATE,
                    "net_slippage_rate_on_turnover": NET_SLIPPAGE_RATE_ON_TURNOVER,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "diagnostics": str(DIAGNOSTICS_PATH),
                    "crossed_breakdown": str(CROSSED_BREAKDOWN_PATH),
                },
                "summary": summary.to_dict(orient="records"),
                "subset_summary": subset_summary.to_dict(orient="records"),
                "crossed_breakdown": crossed_breakdown_summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))
    print(subset_summary.to_string(index=False))


if __name__ == "__main__":
    main()
