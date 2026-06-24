from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade, add_features, build_signal
from research_hype_5m_pbtr_v21_live_cost_variants import variant_specs
from research_hype_5m_pbtr_v2_ablation_slices import (
    FINAL_FILTER_THRESHOLD,
    LEVERAGE,
    apply_final_filter,
    metric_with_sides,
    rolling_windows,
    weekly_slices,
)
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    EXIT_SLIPPAGE_RATE,
    FEE_RATE_PER_FILL,
    simulate_trades_live_cost,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("reports/hype_5m_pbtr_v21a_live_realistic_audit.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v21a_live_realistic_audit_summary.csv")
TRADE_DIAG_PATH = Path("reports/hype_5m_pbtr_v21a_live_realistic_audit_trade_diagnostics.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v21a_live_realistic_audit_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v21a_live_realistic_audit_weekly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v21a-live-realistic-audit-2026-06-24.md"
)


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def v21a_spec() -> dict[str, Any]:
    for spec in variant_specs():
        if spec["version"] == "V2.1A":
            return spec
    raise RuntimeError("V2.1A spec not found")


def active_stop(
    *,
    direction: int,
    entry_price: float,
    initial_stop: float,
    trail_atr: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous_stop: float | None = None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history))) if len(high_history) else entry_price
        value = max(initial_stop, peak - trail_atr * atr_value)
        if previous_stop is not None:
            value = max(previous_stop, value)
    else:
        trough = min(entry_price, float(np.nanmin(low_history))) if len(low_history) else entry_price
        value = min(initial_stop, trough + trail_atr * atr_value)
        if previous_stop is not None:
            value = min(previous_stop, value)
    return float(value)


def stop_crossed_at_open(open_price: float, stop_price: float, direction: int) -> bool:
    return bool(open_price <= stop_price if direction > 0 else open_price >= stop_price)


def stop_touched_in_bar(high_price: float, low_price: float, stop_price: float, direction: int) -> bool:
    return bool(low_price <= stop_price if direction > 0 else high_price >= stop_price)


def exit_price_with_cost(raw_exit_price: float, direction: int) -> float:
    return float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))


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
    exit_price = exit_price_with_cost(raw_exit_price, direction)
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


def simulate_initial_stop_from_entry(frame: pd.DataFrame, signal: np.ndarray, cfg: Any) -> tuple[list[Trade], pd.DataFrame]:
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
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        lockout_end = min(end_i + 1, entry_i + cfg.min_hold_bars)
        lockout_high = high[entry_i:lockout_end]
        lockout_low = low[entry_i:lockout_end]
        if direction > 0:
            initial_hit = low[entry_i:lockout_end] <= initial_stop
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
        else:
            initial_hit = high[entry_i:lockout_end] >= initial_stop
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0

        hit_offsets = np.flatnonzero(initial_hit)
        if len(hit_offsets):
            exit_i = entry_i + int(hit_offsets[0])
            reason = "protective_stop"
            raw_exit_price = float(initial_stop)
        else:
            exit_i = end_i
            reason = "time"
            raw_exit_price = float(close[end_i])
            for j in range(entry_i + cfg.min_hold_bars, end_i + 1):
                stop_price = active_stop(
                    direction=direction,
                    entry_price=entry_price,
                    initial_stop=initial_stop,
                    trail_atr=cfg.trail_atr,
                    high_history=high[entry_i:j],
                    low_history=low[entry_i:j],
                    atr_value=float(atr[j]),
                )
                if stop_touched_in_bar(float(high[j]), float(low[j]), stop_price, direction):
                    exit_i = j
                    reason = "stop"
                    raw_exit_price = float(stop_price)
                    break

        trade = make_trade(
            label="HYPE-5M-PBTR-V2.1A-initial-stop-from-entry",
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
                "lockout_initial_stop_breached": bool(len(hit_offsets)),
                "lockout_mae_bps": lockout_mae * 10000.0,
                "unlock_stop_valid": np.nan,
            }
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def simulate_live_realistic(frame: pd.DataFrame, signal: np.ndarray, cfg: Any) -> tuple[list[Trade], pd.DataFrame]:
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
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i > end_i:
            break

        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        if direction > 0:
            lockout_initial_stop_breached = bool(np.any(lockout_low <= initial_stop)) if len(lockout_low) else False
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
        else:
            lockout_initial_stop_breached = bool(np.any(lockout_high >= initial_stop)) if len(lockout_high) else False
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0

        stop_price = active_stop(
            direction=direction,
            entry_price=entry_price,
            initial_stop=initial_stop,
            trail_atr=cfg.trail_atr,
            high_history=lockout_high,
            low_history=lockout_low,
            atr_value=float(atr[unlock_i - 1]),
        )
        unlock_stop = stop_price
        if stop_crossed_at_open(float(open_[unlock_i]), stop_price, direction):
            exit_i = unlock_i
            reason = "unlock_market_exit"
            raw_exit_price = float(open_[unlock_i])
            unlock_stop_valid = False
        else:
            exit_i = end_i
            reason = "time"
            raw_exit_price = float(close[end_i])
            unlock_stop_valid = True
            for j in range(unlock_i, end_i + 1):
                if stop_crossed_at_open(float(open_[j]), stop_price, direction):
                    exit_i = j
                    reason = "gap_market_exit"
                    raw_exit_price = float(open_[j])
                    break
                if stop_touched_in_bar(float(high[j]), float(low[j]), stop_price, direction):
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = float(stop_price)
                    break
                if j + 1 <= end_i:
                    stop_price = active_stop(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        trail_atr=cfg.trail_atr,
                        high_history=high[entry_i : j + 1],
                        low_history=low[entry_i : j + 1],
                        atr_value=float(atr[j]),
                        previous_stop=stop_price,
                    )

        trade = make_trade(
            label="HYPE-5M-PBTR-V2.1A-live-realistic",
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
                "lockout_initial_stop_breached": lockout_initial_stop_breached,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "unlock_stop_valid": unlock_stop_valid,
                "unlock_active_stop_bps": abs(entry_price - unlock_stop) / entry_price * 10000.0,
            }
        )
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Trade], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **metric_with_sides(trades, LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def time_slices(label: str, frame: pd.DataFrame, trades: list[Trade]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rolling_rows: list[dict[str, Any]] = []
    for item in rolling_windows(frame):
        rolling_rows.append({"label": label, "window": item["name"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    weekly_rows: list[dict[str, Any]] = []
    for item in weekly_slices(frame):
        weekly_rows.append({"label": label, "window": item["name"], **metric_with_sides(trades, LEVERAGE, start=item["start"], end=item["end"])})
    return pd.DataFrame(rolling_rows), pd.DataFrame(weekly_rows)


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, cfg: Any) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    live_diag = diag[diag["label"] == "HYPE-5M-PBTR-V2.1A-live-realistic"]
    protective_diag = diag[diag["label"] == "HYPE-5M-PBTR-V2.1A-initial-stop-from-entry"]
    reasons = live_diag["reason"].value_counts(normalize=True).to_dict()
    protective_reasons = protective_diag["reason"].value_counts(normalize=True).to_dict()
    lockout_q = live_diag["lockout_mae_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    unlock_q = live_diag["unlock_active_stop_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    live_weekly = weekly[weekly["label"] == "HYPE-5M-PBTR-V2.1A-live-realistic"]

    def row(label: str, display: str) -> str:
        item = rows[label]
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['win_rate']))}` | `{num(float(item['profit_factor']))}` | "
            f"`{num(float(item['payoff_ratio']))}` | `{pct(float(item['max_dd']))}` |"
        )

    lines = [
        "# HYPE-5M-PBTR-V2.1A live-realistic 退出审计 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告复核已经进入实盘/实盘 dry-run 的 `HYPE-5M-PBTR-V2.1A` 是否存在与 V3.3/V4 同类的锁仓期 stop 可执行性问题。",
        "",
        "## V2.1A 参数",
        "",
        "| 参数 | 值 |",
        "| --- | ---: |",
        f"| `ema_fast` | `{cfg.ema_fast}` |",
        f"| `ema_slow` | `{cfg.ema_slow}` |",
        f"| `pullback_buffer` | `{cfg.pullback_buffer}` |",
        f"| `stop_atr` | `{cfg.stop_atr}` |",
        f"| `trail_atr` | `{cfg.trail_atr}` |",
        f"| `min_hold_bars` | `{cfg.min_hold_bars}` |",
        f"| `max_hold_bars` | `{cfg.max_hold_bars}` |",
        f"| `final_dir_htf_threshold` | `{FINAL_FILTER_THRESHOLD}` |",
        "",
        "## 审计口径",
        "",
        "- `原始实盘成本回测`：沿用既有 V2.1A 报告口径，锁仓期内不触发 stop，解锁后按回测 stop 价成交。",
        "- `开仓即初始保护止损`：锁仓期只激活 `0.5 ATR` 初始 stop，不激活 trailing，用于模拟一开仓就挂紧保护止损。",
        "- `live-realistic`：锁仓期不挂策略止损；解锁时若 `active_stop` 已被开盘价穿越，则按开盘市价退出，否则挂 reduce-only stop-market 并继续只收紧 trailing。",
        "",
        "## 结果对比",
        "",
        "| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("HYPE-5M-PBTR-V2.1A-normal", "原始实盘成本回测"),
        row("HYPE-5M-PBTR-V2.1A-initial-stop-from-entry", "开仓即初始保护止损"),
        row("HYPE-5M-PBTR-V2.1A-live-realistic", "live-realistic"),
        "",
        "## 可执行性诊断",
        "",
        f"- 锁仓期内触及初始 `0.5 ATR` stop 的比例 `{pct(float(live_diag['lockout_initial_stop_breached'].mean()))}`；若开仓即挂初始保护止损，`{pct(float(protective_reasons.get('protective_stop', 0.0)))}` 的交易会在锁仓期内被保护止损打掉。",
        f"- live-realistic 口径下，解锁时可正常挂 dormant stop 的比例 `{pct(float(live_diag['unlock_stop_valid'].mean()))}`；解锁即市价退出 `{pct(float(reasons.get('unlock_market_exit', 0.0)))}`；后续 stop-market `{pct(float(reasons.get('stop_market', 0.0)))}`；后续 gap 市价退出 `{pct(float(reasons.get('gap_market_exit', 0.0)))}`。",
        f"- 锁仓期 MAE bps：P10 `{num(float(lockout_q[0.1]))}`，P50 `{num(float(lockout_q[0.5]))}`，P90 `{num(float(lockout_q[0.9]))}`；解锁 active stop 距离 entry bps：P10 `{num(float(unlock_q[0.1]))}`，P50 `{num(float(unlock_q[0.5]))}`，P90 `{num(float(unlock_q[0.9]))}`。",
        f"- live-realistic 周切片：盈利周 `{int((live_weekly['total_return'] > 0).sum())}/{len(live_weekly)}`，中位周收益 `{pct(float(live_weekly['total_return'].median()))}`。",
        "",
        "## 结论",
        "",
        "`HYPE-5M-PBTR-V2.1A` 也存在同类结构性问题。它的 `min_hold_bars=6` 比 V3.3/V4 短，最终 HTF 过滤也降低了频率，但原始收益仍高度依赖一个不够实盘化的退出假设：解锁后 stop 已被价格穿越时，回测按 stop 价成交，而实盘只能按市价退出。",
        "",
        "如果当前实盘 runner 是“前 6 根 K 不挂策略止损、解锁后才挂 trailing stop”，则历史回测指标不能作为真实预期，必须把 live-realistic 口径作为风险基线。如果当前 runner 开仓即挂 `0.5 ATR` 初始保护止损，则也与原始回测不等价，反事实回测已经坍缩为 PF 小于 1。",
        "",
        "建议：不要立刻扩大 V2.1A 仓位。当前实盘可以作为极小资金监控样本继续跑，但验收应改为真实成交日志驱动：记录锁仓期 MAE、解锁即市价退出比例、实际 stop 滑点、订单失败率，以及前 300-500 笔的真实 PF/payoff。下一轮研究应重做退出路径，而不是继续基于当前 `min_hold_bars + trailing` 回测指标做版本升级。",
        "",
        "## 产物",
        "",
        "- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v21a_live_realistic_audit.py`",
        f"- JSON：`{REPORT_PATH}`",
        f"- 汇总 CSV：`{SUMMARY_PATH}`",
        f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
        f"- rolling CSV：`{ROLLING_PATH}`",
        f"- weekly CSV：`{WEEKLY_PATH}`",
    ]
    _ = rolling
    return "\n".join(lines) + "\n"


def main() -> None:
    spec = v21a_spec()
    cfg = spec["cfg"]
    raw = load_all_hype_5m()
    frame = add_features(raw)
    frame["_ts_ns"] = frame["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    signal = build_signal(frame, cfg)
    filtered_signal = apply_final_filter(frame, cfg, signal, enabled=True, threshold=FINAL_FILTER_THRESHOLD)

    normal_trades = simulate_trades_live_cost(frame, filtered_signal, cfg)
    protective_trades, protective_diag = simulate_initial_stop_from_entry(frame, filtered_signal, cfg)
    live_trades, live_diag = simulate_live_realistic(frame, filtered_signal, cfg)

    summary = pd.DataFrame(
        [
            summarize("HYPE-5M-PBTR-V2.1A-normal", normal_trades, frame),
            summarize("HYPE-5M-PBTR-V2.1A-initial-stop-from-entry", protective_trades, frame),
            summarize(
                "HYPE-5M-PBTR-V2.1A-live-realistic",
                live_trades,
                frame,
                {
                    "unlock_stop_valid_rate": float(live_diag["unlock_stop_valid"].mean()),
                    "unlock_market_exit_rate": float((live_diag["reason"] == "unlock_market_exit").mean()),
                    "stop_market_rate": float((live_diag["reason"] == "stop_market").mean()),
                    "gap_market_exit_rate": float((live_diag["reason"] == "gap_market_exit").mean()),
                },
            ),
        ]
    )
    diag = pd.concat([protective_diag, live_diag], ignore_index=True)
    rolling_live, weekly_live = time_slices("HYPE-5M-PBTR-V2.1A-live-realistic", frame, live_trades)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag.to_csv(TRADE_DIAG_PATH, index=False)
    rolling_live.to_csv(ROLLING_PATH, index=False)
    weekly_live.to_csv(WEEKLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, diag, rolling_live, weekly_live, cfg), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V2.1A",
                "definition": asdict(cfg),
                "final_filter_threshold": FINAL_FILTER_THRESHOLD,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trade_diagnostics": str(TRADE_DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
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
    print(summary[["label", "trades", "annualized_multiple", "win_rate", "profit_factor", "payoff_ratio", "max_dd"]].to_string(index=False))
    print(diag.groupby("label")["reason"].value_counts(normalize=True).to_string())


if __name__ == "__main__":
    main()
