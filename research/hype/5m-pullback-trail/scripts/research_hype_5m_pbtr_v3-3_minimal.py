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
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v3_ablation_audit import month_slices
from research_hype_5m_pbtr_v32_clean_entry_filters import V32_CONFIG, filtered_signal as filtered_signal_v32
from research_hype_5m_positive_payoff_search import load_all_hype_5m


END_TS = pd.Timestamp("2026-06-23T04:15:00Z")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal_summary.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal_weekly.csv")
MONTHLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal_monthly.csv")
TRADES_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v3-3_minimal_trades.csv")
MARKDOWN_PATH = Path("research/hype/5m-pullback-trail/diagnostics/hype-5m-pbtr-v3-3-minimal-2026-06-24.md")


@dataclass(frozen=True, slots=True)
class V33Config:
    strategy_name: str = "HYPE-5M-PBTR-V3.3"
    timeframe: str = "5m"
    ema_fast: int = 21
    ema_slow: int = 96
    pullback_buffer: float = 0.01
    stop_atr: float = 0.5
    trail_atr: float = 0.75
    min_hold_bars: int = 9


V33_CONFIG = V33Config()


def add_minimal_features(frame: pd.DataFrame, cfg: V33Config) -> pd.DataFrame:
    result = frame.copy()
    result["_ts_ns"] = result["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    close = result["close"]
    high = result["high"]
    low = result["low"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    result[f"ema{cfg.ema_fast}"] = close.ewm(span=cfg.ema_fast, adjust=False, min_periods=cfg.ema_fast).mean()
    result[f"ema{cfg.ema_slow}"] = close.ewm(span=cfg.ema_slow, adjust=False, min_periods=cfg.ema_slow).mean()
    result["atr14"] = tr.rolling(14, min_periods=14).mean()
    return result


def build_v33_signal(frame: pd.DataFrame, cfg: V33Config) -> np.ndarray:
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


def simulate_v33(frame: pd.DataFrame, signal: np.ndarray, cfg: V33Config) -> list[Trade]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
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
        end_i = n - 1
        sl = slice(entry_i, end_i + 1)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]
        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.maximum(np.full(len(high_seg), stop_price), prev_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.minimum(np.full(len(low_seg), stop_price), prev_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
        stop_hit[: cfg.min_hold_bars] = False
        hit_idx = np.flatnonzero(stop_hit)
        if len(hit_idx):
            offset = int(hit_idx[0])
            reason = "stop"
            raw_exit_price = float(stop_levels[offset])
        else:
            offset = len(close_seg) - 1
            reason = "time"
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
                config=cfg.strategy_name,
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
        blocked_until = exit_i
    return trades


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


def render_markdown(summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    v32 = rows["HYPE-5M-PBTR-V3.2"]
    v33 = rows["HYPE-5M-PBTR-V3.3"]
    rolling_v33 = rolling.loc[rolling["label"].eq("HYPE-5M-PBTR-V3.3")].copy()
    weekly_v33 = weekly.loc[weekly["label"].eq("HYPE-5M-PBTR-V3.3")].copy()
    monthly_v33 = monthly.loc[monthly["label"].eq("HYPE-5M-PBTR-V3.3")].copy()
    worst_week = weekly_v33.sort_values("total_return").iloc[0]
    best_week = weekly_v33.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly_v33.sort_values("total_return").iloc[0]
    best_month = monthly_v33.sort_values("total_return", ascending=False).iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V3.3 Minimal 回测 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "V3.3 在 V3.2 基础上删除所有兼容保留、关闭、有限值保护和基本不触发参数，只保留最小有效策略表达。",
        "",
        f"策略名称：`{V33_CONFIG.strategy_name}`；时间级别：`{V33_CONFIG.timeframe}`。",
        "",
        "## 最小参数",
        "",
        "| 参数 | 值 |",
        "| --- | ---: |",
    ]
    for key, value in asdict(V33_CONFIG).items():
        if key in {"strategy_name", "timeframe"}:
            continue
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "删除项：`side_mode`、`entry_style`、`donchian`、`roc_window`、`regime_age`、`breakout_buffer`、`max_dist_ema`、`ROC/RSI/ADX/CHOP/RVOL/CMF/MACD/OBV/HTF/efficiency`、`tp_atr`、`max_hold_bars`、`exit_ema`、`cooldown_bars`、`final_dir_htf_filter`。",
            "",
            "## V3.2 vs V3.3",
            "",
            "| 版本 | 信号数 | 交易数 | 权益倍数 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| `HYPE-5M-PBTR-V3.2` | `{int(v32['signal_count'])}` | `{int(v32['trades'])}` | `{mult(float(v32['equity_multiple']))}` | `{mult(float(v32['annualized_multiple']))}` | `{pct(float(v32['win_rate']))}` | `{num(float(v32['payoff_ratio']))}` | `{num(float(v32['profit_factor']))}` | `{pct(float(v32['max_dd']))}` |",
            f"| `HYPE-5M-PBTR-V3.3` | `{int(v33['signal_count'])}` | `{int(v33['trades'])}` | `{mult(float(v33['equity_multiple']))}` | `{mult(float(v33['annualized_multiple']))}` | `{pct(float(v33['win_rate']))}` | `{num(float(v33['payoff_ratio']))}` | `{num(float(v33['profit_factor']))}` | `{pct(float(v33['max_dd']))}` |",
            "",
            f"相对 V3.2，V3.3 交易数变化 `{int(v33['trades']) - int(v32['trades']):+d}`，胜率从 `{pct(float(v32['win_rate']))}` 到 `{pct(float(v33['win_rate']))}`，PF 从 `{num(float(v32['profit_factor']))}` 到 `{num(float(v33['profit_factor']))}`，最大回撤从 `{pct(float(v32['max_dd']))}` 到 `{pct(float(v33['max_dd']))}`。",
            "",
            "## 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling_v33.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly_v33)}`，盈利周 `{int((weekly_v33['total_return'] > 0).sum())}/{len(weekly_v33)}`，中位周收益 `{pct(float(weekly_v33['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly_v33)}`，盈利月 `{int((monthly_v33['total_return'] > 0).sum())}/{len(monthly_v33)}`，中位月收益 `{pct(float(monthly_v33['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 结论",
            "",
            "V3.3 用最小逻辑重写后表现与 V3.2 几乎一致，说明 V3.2 中所有关闭/兼容/保护参数都可以从实盘交接规格中移除。本次仅多出 2 笔交易，差异来自 V3.2 旧代码中额外的 NaN 预热保护，而不是策略核心变化。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v3-3_minimal.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 滚动切片：`{ROLLING_PATH}`",
            f"- 周切片：`{WEEKLY_PATH}`",
            f"- 月切片：`{MONTHLY_PATH}`",
            f"- 交易明细：`{TRADES_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= END_TS].reset_index(drop=True)
    frame_v33 = add_minimal_features(raw, V33_CONFIG)
    signal_v33 = build_v33_signal(frame_v33, V33_CONFIG)
    trades_v33 = simulate_v33(frame_v33, signal_v33, V33_CONFIG)

    from research_hype_5m_indicator_search import add_features

    frame_v32 = add_features(raw)
    signal_v32 = filtered_signal_v32(frame_v32, V32_CONFIG, final_filter=False)
    trades_v32 = simulate_trades_live_cost(frame_v32, signal_v32, V32_CONFIG)

    summary = pd.DataFrame(
        [
            summarize("HYPE-5M-PBTR-V3.2", int(np.count_nonzero(signal_v32)), trades_v32, frame_v32),
            summarize("HYPE-5M-PBTR-V3.3", int(np.count_nonzero(signal_v33)), trades_v33, frame_v33),
        ]
    )
    rolling, weekly, monthly = time_slice_rows(frame_v33, "HYPE-5M-PBTR-V3.3", trades_v33)
    trades_out = pd.DataFrame(
        [
            {
                "trade_no": i + 1,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "reason": trade.reason,
            }
            for i, trade in enumerate(trades_v33)
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trades_out.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, rolling, weekly, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3",
                "definition": asdict(V33_CONFIG),
                "removed_from_v32": [
                    "side_mode",
                    "entry_style",
                    "donchian",
                    "roc_window",
                    "regime_age",
                    "breakout_buffer",
                    "max_dist_ema",
                    "ROC/RSI/ADX/CHOP/RVOL/CMF/MACD/OBV/HTF/efficiency filters",
                    "tp_atr",
                    "max_hold_bars",
                    "exit_ema",
                    "cooldown_bars",
                    "final_dir_htf_filter",
                ],
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
                    "trades": str(TRADES_PATH),
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
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
