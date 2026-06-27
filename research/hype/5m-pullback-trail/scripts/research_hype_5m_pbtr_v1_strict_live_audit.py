from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ablate_hype_5m_r05732 import BASE_CONFIG as V1_BASE_CONFIG  # noqa: E402
from research_hype_5m_filter_refinement import feature_values  # noqa: E402
from research_hype_5m_indicator_search import Trade, add_features, build_signal  # noqa: E402
from research_hype_5m_pbtr_v2_ablation_slices import LEVERAGE, metric_with_sides, rolling_windows, weekly_slices  # noqa: E402
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (  # noqa: E402
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    simulate_trades_live_cost,
)
from research_hype_5m_pbtr_v3_ablation_audit import month_slices  # noqa: E402
from research_hype_5m_positive_payoff_search import load_all_hype_5m  # noqa: E402

RUN_DATE = "2026-06-27"
FINAL_FILTER_THRESHOLD = 0.688442

FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_summary_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_trade_diag_{RUN_DATE}.csv"
ROLLING_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_rolling_{RUN_DATE}.csv"
WEEKLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_weekly_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v1_strict_live_audit_monthly_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v1-strict-live-audit-{RUN_DATE}.md"


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def apply_v1_final_filter(frame: pd.DataFrame, signal: np.ndarray) -> np.ndarray:
    sig_idx = np.flatnonzero(signal)
    if len(sig_idx) == 0:
        return signal.copy()
    values = feature_values(frame, V1_BASE_CONFIG, signal, sig_idx)
    keep = values["dir_htf"] >= FINAL_FILTER_THRESHOLD
    filtered = np.zeros_like(signal)
    filtered[sig_idx[keep]] = signal[sig_idx[keep]]
    previous_same = np.r_[False, (filtered[1:] != 0) & (filtered[1:] == filtered[:-1])]
    filtered[previous_same] = 0
    return filtered


def active_stop(
    *,
    direction: int,
    entry_price: float,
    initial_stop: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous_stop: float | None = None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history))) if len(high_history) else entry_price
        value = max(initial_stop, peak - V1_BASE_CONFIG.trail_atr * atr_value)
        if previous_stop is not None:
            value = max(previous_stop, value)
    else:
        trough = min(entry_price, float(np.nanmin(low_history))) if len(low_history) else entry_price
        value = min(initial_stop, trough + V1_BASE_CONFIG.trail_atr * atr_value)
        if previous_stop is not None:
            value = min(previous_stop, value)
    return float(value)


def stop_crossed_or_touched(high_price: float, low_price: float, stop_price: float, direction: int) -> bool:
    return bool(low_price <= stop_price if direction > 0 else high_price >= stop_price)


def stop_crossed_at_open(open_price: float, stop_price: float, direction: int) -> bool:
    return bool(open_price <= stop_price if direction > 0 else open_price >= stop_price)


def target_crossed_or_touched(high_price: float, low_price: float, target_price: float, direction: int) -> bool:
    return bool(high_price >= target_price if direction > 0 else low_price <= target_price)


def target_crossed_at_open(open_price: float, target_price: float, direction: int) -> bool:
    return bool(open_price >= target_price if direction > 0 else open_price <= target_price)


def make_trade(
    *,
    label: str,
    ts_ns: np.ndarray,
    sig_i: int,
    entry_i: int,
    exit_i: int,
    direction: int,
    entry_price: float,
    raw_exit_price: float,
    reason: str,
    high: np.ndarray,
    low: np.ndarray,
) -> Trade:
    exit_price = float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))
    gross = direction * (exit_price / entry_price - 1.0)
    fee_cost = FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    net = gross - fee_cost
    path_high = high[entry_i : exit_i + 1]
    path_low = low[entry_i : exit_i + 1]
    if direction > 0:
        mae = float(np.nanmin(path_low / entry_price - 1.0))
        mfe = float(np.nanmax(path_high / entry_price - 1.0))
    else:
        mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
        mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))
    return Trade(
        config=label,
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


def simulate_v1_live_realistic(frame: pd.DataFrame, signal: np.ndarray) -> tuple[list[Trade], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    diag: list[dict[str, Any]] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * V1_BASE_CONFIG.stop_atr * signal_atr
        target_price = entry_price + direction * V1_BASE_CONFIG.tp_atr * signal_atr
        end_i = min(n - 1, entry_i + V1_BASE_CONFIG.max_hold_bars)
        unlock_i = entry_i + V1_BASE_CONFIG.min_hold_bars
        if unlock_i > end_i:
            break

        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        if direction > 0:
            lockout_stop_breached = bool(np.any(lockout_low <= initial_stop))
            lockout_target_touched = bool(np.any(lockout_high >= target_price))
        else:
            lockout_stop_breached = bool(np.any(lockout_high >= initial_stop))
            lockout_target_touched = bool(np.any(lockout_low <= target_price))
        if direction > 0:
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
        else:
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0

        stop_price = active_stop(
            direction=direction,
            entry_price=entry_price,
            initial_stop=initial_stop,
            high_history=lockout_high,
            low_history=lockout_low,
            atr_value=float(atr[unlock_i - 1]),
        )
        unlock_stop = stop_price
        unlock_open = float(open_[unlock_i])
        if stop_crossed_at_open(unlock_open, stop_price, direction):
            exit_i = unlock_i
            reason = "unlock_stop_market_exit"
            raw_exit_price = unlock_open
            unlock_stop_valid = False
            unlock_target_marketable = False
        elif target_crossed_at_open(unlock_open, target_price, direction):
            exit_i = unlock_i
            reason = "unlock_target_market_exit"
            raw_exit_price = unlock_open
            unlock_stop_valid = True
            unlock_target_marketable = True
        else:
            exit_i = end_i
            reason = "time"
            raw_exit_price = float(close[end_i])
            unlock_stop_valid = True
            unlock_target_marketable = False
            for j in range(unlock_i, end_i + 1):
                open_j = float(open_[j])
                if stop_crossed_at_open(open_j, stop_price, direction):
                    exit_i = j
                    reason = "gap_stop_market_exit"
                    raw_exit_price = open_j
                    break
                if target_crossed_at_open(open_j, target_price, direction):
                    exit_i = j
                    reason = "gap_target_market_exit"
                    raw_exit_price = open_j
                    break
                stop_hit = stop_crossed_or_touched(float(high[j]), float(low[j]), stop_price, direction)
                target_hit = target_crossed_or_touched(float(high[j]), float(low[j]), target_price, direction)
                if stop_hit:
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = stop_price
                    break
                if target_hit:
                    exit_i = j
                    reason = "target_limit"
                    raw_exit_price = target_price
                    break
                if j + 1 <= end_i:
                    stop_price = active_stop(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        high_history=high[entry_i : j + 1],
                        low_history=low[entry_i : j + 1],
                        atr_value=float(atr[j]),
                        previous_stop=stop_price,
                    )

        trade = make_trade(
            label="HYPE-5M-PBTR-V1-live-realistic",
            ts_ns=ts_ns,
            sig_i=sig_i,
            entry_i=entry_i,
            exit_i=exit_i,
            direction=direction,
            entry_price=entry_price,
            raw_exit_price=raw_exit_price,
            reason=reason,
            high=high,
            low=low,
        )
        trades.append(trade)
        diag.append(
            {
                "label": trade.config,
                "reason": reason,
                "bars_held": trade.bars_held,
                "lockout_initial_stop_breached": lockout_stop_breached,
                "lockout_target_touched": lockout_target_touched,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "unlock_stop_valid": unlock_stop_valid,
                "unlock_target_marketable": unlock_target_marketable,
                "unlock_active_stop_bps": abs(entry_price - unlock_stop) / entry_price * 10000.0,
            }
        )
        blocked_until = exit_i + V1_BASE_CONFIG.cooldown_bars
    return trades, pd.DataFrame(diag)


def simulate_v1_entry_protective_stop(frame: pd.DataFrame, signal: np.ndarray) -> tuple[list[Trade], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    diag: list[dict[str, Any]] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= n or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * V1_BASE_CONFIG.stop_atr * signal_atr
        target_price = entry_price + direction * V1_BASE_CONFIG.tp_atr * signal_atr
        end_i = min(n - 1, entry_i + V1_BASE_CONFIG.max_hold_bars)
        unlock_i = min(end_i + 1, entry_i + V1_BASE_CONFIG.min_hold_bars)

        exit_i = end_i
        reason = "time"
        raw_exit_price = float(close[end_i])
        initial_stop_hit = False
        for j in range(entry_i, unlock_i):
            if stop_crossed_at_open(float(open_[j]), initial_stop, direction):
                exit_i = j
                reason = "gap_protective_stop"
                raw_exit_price = float(open_[j])
                initial_stop_hit = True
                break
            if stop_crossed_or_touched(float(high[j]), float(low[j]), initial_stop, direction):
                exit_i = j
                reason = "protective_stop"
                raw_exit_price = initial_stop
                initial_stop_hit = True
                break

        if not initial_stop_hit:
            stop_price = active_stop(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                high_history=high[entry_i:unlock_i],
                low_history=low[entry_i:unlock_i],
                atr_value=float(atr[max(entry_i, unlock_i - 1)]),
            )
            for j in range(unlock_i, end_i + 1):
                open_j = float(open_[j])
                if stop_crossed_at_open(open_j, stop_price, direction):
                    exit_i = j
                    reason = "gap_stop_market_exit"
                    raw_exit_price = open_j
                    break
                if target_crossed_at_open(open_j, target_price, direction):
                    exit_i = j
                    reason = "gap_target_market_exit"
                    raw_exit_price = open_j
                    break
                stop_hit = stop_crossed_or_touched(float(high[j]), float(low[j]), stop_price, direction)
                target_hit = target_crossed_or_touched(float(high[j]), float(low[j]), target_price, direction)
                if stop_hit:
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = stop_price
                    break
                if target_hit:
                    exit_i = j
                    reason = "target_limit"
                    raw_exit_price = target_price
                    break
                if j + 1 <= end_i:
                    stop_price = active_stop(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        high_history=high[entry_i : j + 1],
                        low_history=low[entry_i : j + 1],
                        atr_value=float(atr[j]),
                        previous_stop=stop_price,
                    )

        trade = make_trade(
            label="HYPE-5M-PBTR-V1-entry-protective-stop",
            ts_ns=ts_ns,
            sig_i=sig_i,
            entry_i=entry_i,
            exit_i=exit_i,
            direction=direction,
            entry_price=entry_price,
            raw_exit_price=raw_exit_price,
            reason=reason,
            high=high,
            low=low,
        )
        trades.append(trade)
        diag.append(
            {
                "label": trade.config,
                "reason": reason,
                "bars_held": trade.bars_held,
                "lockout_initial_stop_breached": initial_stop_hit,
                "lockout_target_touched": np.nan,
                "lockout_mae_bps": trade.mae_1x * 10000.0,
                "unlock_stop_valid": np.nan,
                "unlock_target_marketable": np.nan,
                "unlock_active_stop_bps": np.nan,
            }
        )
        blocked_until = exit_i + V1_BASE_CONFIG.cooldown_bars
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Trade], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **metric_with_sides(trades, LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def slice_rows(label: str, frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling = pd.DataFrame(
        [{"label": label, "window": item["name"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in rolling_windows(frame)]
    )
    weekly = pd.DataFrame(
        [{"label": label, "window": item["name"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in weekly_slices(frame)]
    )
    monthly = pd.DataFrame(
        [{"label": label, "window": item["name"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])} for item in month_slices(frame)]
    )
    return rolling, weekly, monthly


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame, signal_count: int, frame: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    live_diag = diag.loc[diag["label"].eq("HYPE-5M-PBTR-V1-live-realistic")]
    protective_diag = diag.loc[diag["label"].eq("HYPE-5M-PBTR-V1-entry-protective-stop")]
    reasons = live_diag["reason"].value_counts(normalize=True).to_dict()
    lockout_q = live_diag["lockout_mae_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    unlock_q = live_diag["unlock_active_stop_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    live_weekly = weekly.loc[weekly["label"].eq("HYPE-5M-PBTR-V1-live-realistic")]
    live_monthly = monthly.loc[monthly["label"].eq("HYPE-5M-PBTR-V1-live-realistic")]

    def metric_row(label: str, display: str) -> str:
        row = rows[label]
        return (
            f"| `{display}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
            f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['profit_factor']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` |"
        )

    lines = [
        "# HYPE-5M-PBTR-V1 strict live audit 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告复核 `HYPE-5M-PBTR-V1` 是否在严格可实盘成交口径下仍赚钱，避免用后续 V2/V3 修改结果倒推 V1。",
        "",
        f"数据区间：`{frame['ts'].iloc[0]}` 到 `{frame['ts'].iloc[-1]}`；过滤后信号数 `{signal_count}`。",
        "",
        "## V1 参数",
        "",
        "| 参数 | 值 |",
        "| --- | ---: |",
        f"| `ema_fast / ema_slow` | `{V1_BASE_CONFIG.ema_fast}/{V1_BASE_CONFIG.ema_slow}` |",
        f"| `pullback_buffer` | `{V1_BASE_CONFIG.pullback_buffer}` |",
        f"| `stop_atr` | `{V1_BASE_CONFIG.stop_atr}` |",
        f"| `tp_atr` | `{V1_BASE_CONFIG.tp_atr}` |",
        f"| `trail_atr` | `{V1_BASE_CONFIG.trail_atr}` |",
        f"| `min_hold_bars` | `{V1_BASE_CONFIG.min_hold_bars}` |",
        f"| `final_filter dir_htf >=` | `{FINAL_FILTER_THRESHOLD}` |",
        "",
        "## 审计口径",
        "",
        "- `legacy stop-price fill`：旧回测口径，前 6 根不触发 stop/target，第 7 根后若 bar 内触及 stop/target，按 stop/target 价成交。",
        "- `live-realistic`：前 6 根不挂策略 stop/target；第 7 根解锁时，如果 active stop 已被 open 穿越，则按 open 市价平；如果 target 已变成 marketable，也按 open 平；之后 stop-market / target-limit 只按从当时开始可挂的订单成交。",
        "- `entry protective stop`：反事实保护口径，开仓即挂 `0.75 ATR` 初始保护止损；不代表 V1 原始策略，只用于看加保护后是否还赚钱。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 总收益 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        metric_row("HYPE-5M-PBTR-V1-legacy-stop-fill", "legacy stop-price fill"),
        metric_row("HYPE-5M-PBTR-V1-live-realistic", "live-realistic"),
        metric_row("HYPE-5M-PBTR-V1-entry-protective-stop", "entry protective stop"),
        "",
        "## 可执行性诊断",
        "",
        f"- live-realistic 下，解锁时 stop 可正常挂上的比例 `{pct(float(live_diag['unlock_stop_valid'].mean()))}`；解锁即 stop 市价退出 `{pct(float(reasons.get('unlock_stop_market_exit', 0.0)))}`；后续 stop-market `{pct(float(reasons.get('stop_market', 0.0)))}`；target-limit `{pct(float(reasons.get('target_limit', 0.0)))}`。",
        f"- 锁仓期曾触及初始 stop 的比例 `{pct(float(live_diag['lockout_initial_stop_breached'].mean()))}`；锁仓期曾触及 target 但无订单可成交的比例 `{pct(float(live_diag['lockout_target_touched'].mean()))}`；若开仓即保护，保护止损/跳空保护止损退出比例 `{pct(float(protective_diag['reason'].isin(['protective_stop', 'gap_protective_stop']).mean()))}`。",
        f"- 锁仓期 MAE bps：P10 `{num(float(lockout_q[0.1]))}`，P50 `{num(float(lockout_q[0.5]))}`，P90 `{num(float(lockout_q[0.9]))}`；解锁 active stop 距离 entry bps：P10 `{num(float(unlock_q[0.1]))}`，P50 `{num(float(unlock_q[0.5]))}`，P90 `{num(float(unlock_q[0.9]))}`。",
        f"- live-realistic 周切片：盈利周 `{int((live_weekly['total_return'] > 0).sum())}/{len(live_weekly)}`，中位周收益 `{pct(float(live_weekly['total_return'].median()))}`；盈利月 `{int((live_monthly['total_return'] > 0).sum())}/{len(live_monthly)}`，中位月收益 `{pct(float(live_monthly['total_return'].median()))}`。",
        "",
        "## 结论",
        "",
        "`HYPE-5M-PBTR-V1` 的旧口径确实赚钱，但严格 live-realistic 口径不赚钱。问题不是后续简单“改坏了”，而是 V1 已经依赖同一类不可实盘化假设：锁仓期结束后，旧回测允许按已经被价格穿越的 stop/target 价成交；实盘只能从解锁时开始挂单或市价退出。",
        "",
        "因此 V1 不能作为回退上线版本。后续 V2/V3 的确把交易频率和样本内收益推高，放大了这个缺陷；但缺陷在 V1 机制里已经存在。若要恢复这条线，应从 executable-first 状态机重新设计，而不是退回 V1 参数。",
        "",
        "## 产物",
        "",
        f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
        f"- JSON：`{REPORT_PATH}`",
        f"- summary CSV：`{SUMMARY_PATH}`",
        f"- trade diagnostics CSV：`{DIAG_PATH}`",
        f"- rolling CSV：`{ROLLING_PATH}`",
        f"- weekly CSV：`{WEEKLY_PATH}`",
        f"- monthly CSV：`{MONTHLY_PATH}`",
    ]
    _ = rolling
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = load_all_hype_5m()
    frame = add_features(raw)
    frame["_ts_ns"] = frame["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    signal = build_signal(frame, V1_BASE_CONFIG)
    filtered_signal = apply_v1_final_filter(frame, signal)
    signal_count = int(np.count_nonzero(filtered_signal))

    legacy_trades = simulate_trades_live_cost(frame, filtered_signal, V1_BASE_CONFIG)
    live_trades, live_diag = simulate_v1_live_realistic(frame, filtered_signal)
    protective_trades, protective_diag = simulate_v1_entry_protective_stop(frame, filtered_signal)

    summary = pd.DataFrame(
        [
            summarize("HYPE-5M-PBTR-V1-legacy-stop-fill", legacy_trades, frame),
            summarize(
                "HYPE-5M-PBTR-V1-live-realistic",
                live_trades,
                frame,
                {
                    "unlock_stop_valid_rate": float(live_diag["unlock_stop_valid"].mean()),
                    "unlock_stop_market_exit_rate": float((live_diag["reason"] == "unlock_stop_market_exit").mean()),
                    "target_limit_rate": float((live_diag["reason"] == "target_limit").mean()),
                    "lockout_target_touched_rate": float(live_diag["lockout_target_touched"].mean()),
                },
            ),
            summarize("HYPE-5M-PBTR-V1-entry-protective-stop", protective_trades, frame),
        ]
    )
    diag = pd.concat([live_diag, protective_diag], ignore_index=True)
    rolling_live, weekly_live, monthly_live = slice_rows("HYPE-5M-PBTR-V1-live-realistic", frame, live_trades)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag.to_csv(DIAG_PATH, index=False)
    rolling_live.to_csv(ROLLING_PATH, index=False)
    weekly_live.to_csv(WEEKLY_PATH, index=False)
    monthly_live.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(summary, diag, rolling_live, weekly_live, monthly_live, signal_count, frame),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V1",
                "audit": "strict_live_audit",
                "definition": asdict(V1_BASE_CONFIG),
                "final_filter_threshold": FINAL_FILTER_THRESHOLD,
                "data_start": str(frame["ts"].iloc[0]),
                "data_end": str(frame["ts"].iloc[-1]),
                "signal_count": signal_count,
                "summary": summary.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trade_diagnostics": str(DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary[["label", "trades", "total_return", "win_rate", "profit_factor", "payoff_ratio", "max_dd"]].to_string(index=False))


if __name__ == "__main__":
    main()
