from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research_hype_5m_indicator_search import Trade, add_features, build_signal
from research_hype_5m_pbtr_v21_live_cost_variants import variant_specs
from research_hype_5m_pbtr_v21a_live_realistic_audit import (
    active_stop,
    make_trade,
    simulate_live_realistic,
    stop_crossed_at_open,
    stop_touched_in_bar,
)
from research_hype_5m_pbtr_v2_ablation_slices import (
    FINAL_FILTER_THRESHOLD,
    LEVERAGE,
    apply_final_filter,
    metric_with_sides,
)
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import (
    ENTRY_SLIPPAGE_RATE,
    simulate_trades_live_cost,
)
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_immediate_tp_audit.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_immediate_tp_audit_summary.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v21a-immediate-tp-audit-2026-06-25.md"
)


def pct(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    if np.isnan(value):
        return "n/a"
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def v21a_config() -> Any:
    for spec in variant_specs():
        if spec["version"] == "V2.1A":
            return spec["cfg"]
    raise RuntimeError("V2.1A spec not found")


def target_touched(high_price: float, low_price: float, target_price: float, direction: int) -> bool:
    return bool(high_price >= target_price if direction > 0 else low_price <= target_price)


def simulate_immediate_tp_old_stop(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    tp_atr: float = 1.0,
) -> tuple[list[Trade], pd.DataFrame]:
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
        if direction == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        target_price = entry_price + direction * tp_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        exit_i = end_i
        reason = "time"
        raw_exit_price = float(close[end_i])
        stop_price: float | None = None

        for i in range(entry_i, end_i + 1):
            target_hit = target_touched(float(high[i]), float(low[i]), target_price, direction)
            if i < entry_i + cfg.min_hold_bars:
                if target_hit:
                    exit_i = i
                    reason = "target_first_6"
                    raw_exit_price = float(target_price)
                    break
                continue

            stop_price = active_stop(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                trail_atr=cfg.trail_atr,
                high_history=high[entry_i:i],
                low_history=low[entry_i:i],
                atr_value=float(atr[i]),
                previous_stop=stop_price,
            )
            if stop_touched_in_bar(float(high[i]), float(low[i]), stop_price, direction):
                exit_i = i
                reason = "stop_old_price"
                raw_exit_price = float(stop_price)
                break
            if target_hit:
                exit_i = i
                reason = "target_after_unlock"
                raw_exit_price = float(target_price)
                break

        trade = make_trade(
            label="HYPE-5M-PBTR-V2.1A-immediate-tp-old-stop",
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
        diag.append({"label": trade.config, "reason": reason, "bars_held": trade.bars_held, "net_ret_1x": trade.net_ret_1x})
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def simulate_immediate_tp_live_realistic(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    tp_atr: float = 1.0,
) -> tuple[list[Trade], pd.DataFrame]:
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
        if direction == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        target_price = entry_price + direction * tp_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i > end_i:
            break

        exit_i = end_i
        reason = "time"
        raw_exit_price = float(close[end_i])
        exited = False
        for i in range(entry_i, min(unlock_i, end_i + 1)):
            if target_touched(float(high[i]), float(low[i]), target_price, direction):
                exit_i = i
                reason = "target_first_6"
                raw_exit_price = float(target_price)
                exited = True
                break

        if not exited:
            stop_price = active_stop(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                trail_atr=cfg.trail_atr,
                high_history=high[entry_i:unlock_i],
                low_history=low[entry_i:unlock_i],
                atr_value=float(atr[unlock_i - 1]),
            )
            for i in range(unlock_i, end_i + 1):
                target_hit = target_touched(float(high[i]), float(low[i]), target_price, direction)
                if stop_crossed_at_open(float(open_[i]), stop_price, direction):
                    exit_i = i
                    reason = "gap_or_unlock_market_exit"
                    raw_exit_price = float(open_[i])
                    break
                if stop_touched_in_bar(float(high[i]), float(low[i]), stop_price, direction):
                    exit_i = i
                    reason = "stop_market"
                    raw_exit_price = float(stop_price)
                    break
                if target_hit:
                    exit_i = i
                    reason = "target_after_unlock"
                    raw_exit_price = float(target_price)
                    break
                if i + 1 <= end_i:
                    stop_price = active_stop(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        trail_atr=cfg.trail_atr,
                        high_history=high[entry_i : i + 1],
                        low_history=low[entry_i : i + 1],
                        atr_value=float(atr[i]),
                        previous_stop=stop_price,
                    )

        trade = make_trade(
            label="HYPE-5M-PBTR-V2.1A-immediate-tp-live-realistic",
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
        diag.append({"label": trade.config, "reason": reason, "bars_held": trade.bars_held, "net_ret_1x": trade.net_ret_1x})
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Trade], frame: pd.DataFrame, diag: pd.DataFrame | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **metric_with_sides(trades, LEVERAGE, start=start, end=end)}
    if diag is not None and not diag.empty:
        row["target_first_6_rate"] = float((diag["reason"] == "target_first_6").mean())
        row["target_total_rate"] = float(diag["reason"].str.startswith("target").mean())
        row["median_bars_held"] = float(diag["bars_held"].median())
        row["reason_counts"] = diag["reason"].value_counts().to_dict()
    return row


def render_markdown(summary: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}

    def row(label: str, display: str) -> str:
        item = rows[label]
        first_6 = item.get("target_first_6_rate", np.nan)
        total_target = item.get("target_total_rate", np.nan)
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['total_return']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['profit_factor']))}` | `{num(float(item['payoff_ratio']))}` | "
            f"`{pct(float(item['max_dd']))}` | `{pct(float(first_6))}` | `{pct(float(total_target))}` |"
        )

    old_reasons = rows["tp1_old_stop_price"].get("reason_counts", {})
    live_reasons = rows["tp1_live_realistic"].get("reason_counts", {})
    lines = [
        "# HYPE-5M-PBTR-V2.1A immediate TP 审计 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试一个补救想法：开仓后立即挂 `1 * ATR14` 固定止盈，不挂初始止损；前 `6` 根 K 只允许止盈，`min_hold_bars` 结束后再启用原始 ATR trailing stop。",
        "",
        "## 口径",
        "",
        "- `1 * ATR14` 使用信号 K 上已经闭合可见的 `ATR14`。",
        "- 止盈从入场成交后立即生效，方向为多头 `entry + ATR14`、空头 `entry - ATR14`。",
        "- `旧 stop 价成交`：第 6 根后沿用原始回测，stop 被触发时按计算出的 stop price 成交。",
        "- `live-realistic`：第 6 根后如果 stop 已经被开盘价穿越，按开盘市价退出；否则再按 stop-market 管理。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 前6根止盈率 | 总止盈率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("original_old_no_tp", "原始旧口径，无即时 TP"),
        row("live_realistic_no_tp", "live-realistic，无即时 TP"),
        row("tp1_old_stop_price", "即时 1ATR TP + 旧 stop 价成交"),
        row("tp1_live_realistic", "即时 1ATR TP + live-realistic stop"),
        "",
        "## 退出原因",
        "",
        f"- 旧 stop 价成交口径：`{old_reasons}`",
        f"- live-realistic 口径：`{live_reasons}`",
        "",
        "## 结论",
        "",
        "即时 `1 * ATR14` 止盈确实能让约 `42.85%` 的交易在前 6 根 K 先止盈，明显减少一部分锁仓期风险。",
        "",
        "但它没有修复核心问题：剩余交易在第 6 根后仍大量落入 stop 已穿越/必须市价退出的路径。旧 stop 价成交口径下 PF 仍有 `1.86`，但 live-realistic 口径 PF 只有 `0.53`，总收益约 `-99.89%`。因此，入场即挂 1ATR 止盈不能把 V2.1A 修成可实盘策略。",
        "",
        "## 产物",
        "",
        "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_immediate_tp_audit.py`",
        f"- JSON：`{REPORT_PATH}`",
        f"- 汇总 CSV：`{SUMMARY_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    cfg = v21a_config()
    raw = load_all_hype_5m()
    frame = add_features(raw)
    frame["_ts_ns"] = frame["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    signal = apply_final_filter(frame, cfg, build_signal(frame, cfg), enabled=True, threshold=FINAL_FILTER_THRESHOLD)

    original = simulate_trades_live_cost(frame, signal, cfg)
    live_no_tp, live_no_tp_diag = simulate_live_realistic(frame, signal, cfg)
    old_tp, old_tp_diag = simulate_immediate_tp_old_stop(frame, signal, cfg, tp_atr=1.0)
    live_tp, live_tp_diag = simulate_immediate_tp_live_realistic(frame, signal, cfg, tp_atr=1.0)

    summary = pd.DataFrame(
        [
            summarize("original_old_no_tp", original, frame),
            summarize("live_realistic_no_tp", live_no_tp, frame, live_no_tp_diag),
            summarize("tp1_old_stop_price", old_tp, frame, old_tp_diag),
            summarize("tp1_live_realistic", live_tp, frame, live_tp_diag),
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V2.1A",
                "audit": "immediate_1atr_take_profit_with_delayed_stop",
                "summary": summary.to_dict(orient="records"),
                "outputs": {"markdown": str(MARKDOWN_PATH), "summary": str(SUMMARY_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(summary[["label", "trades", "annualized_multiple", "total_return", "win_rate", "profit_factor", "payoff_ratio", "max_dd", "target_first_6_rate", "target_total_rate"]].to_string(index=False))
    print(f"markdown={MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
