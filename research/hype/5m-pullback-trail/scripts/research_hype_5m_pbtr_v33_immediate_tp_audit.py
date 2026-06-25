from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_5m_pbtr_live_realistic_trailing as live_trailing
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE, FEE_RATE_PER_FILL
from research_hype_5m_positive_payoff_search import load_all_hype_5m


v33 = live_trailing.v33

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_immediate_tp_audit.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_immediate_tp_audit_summary.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-immediate-tp-audit-2026-06-25.md"
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


def target_touched(high_price: float, low_price: float, target_price: float, direction: int) -> bool:
    return bool(high_price >= target_price if direction > 0 else low_price <= target_price)


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
) -> Any:
    exit_price = live_trailing.apply_exit_cost(raw_exit_price, direction, EXIT_SLIPPAGE_RATE)
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
    return v33.Trade(
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


def simulate_immediate_tp_old_stop(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    tp_atr: float = 1.0,
) -> tuple[list[Any], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Any] = []
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
        exit_i = n - 1
        reason = "time"
        raw_exit_price = float(close[-1])
        active_stop: float | None = None

        for i in range(entry_i, n):
            target_hit = target_touched(float(high[i]), float(low[i]), target_price, direction)
            if i < entry_i + cfg.min_hold_bars:
                if target_hit:
                    exit_i = i
                    reason = "target_lockout"
                    raw_exit_price = float(target_price)
                    break
                continue

            active_stop = live_trailing.active_stop_from_history(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                high_history=high[entry_i:i],
                low_history=low[entry_i:i],
                atr_value=float(atr[i]),
                trail_atr=cfg.trail_atr,
                previous_active_stop=active_stop,
            )
            if live_trailing.touched_stop_in_bar(float(high[i]), float(low[i]), active_stop, direction):
                exit_i = i
                reason = "stop_old_price"
                raw_exit_price = float(active_stop)
                break
            if target_hit:
                exit_i = i
                reason = "target_after_unlock"
                raw_exit_price = float(target_price)
                break

        trade = make_trade(
            label="HYPE-5M-PBTR-V3.3-immediate-tp-old-stop",
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
        blocked_until = exit_i
    return trades, pd.DataFrame(diag)


def simulate_immediate_tp_live_realistic(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    tp_atr: float = 1.0,
) -> tuple[list[Any], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Any] = []
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
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i >= n:
            break

        exit_i = n - 1
        reason = "time"
        raw_exit_price = float(close[-1])
        exited = False
        for i in range(entry_i, min(unlock_i, n)):
            if target_touched(float(high[i]), float(low[i]), target_price, direction):
                exit_i = i
                reason = "target_lockout"
                raw_exit_price = float(target_price)
                exited = True
                break

        if not exited:
            active_stop = live_trailing.active_stop_from_history(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                high_history=high[entry_i:unlock_i],
                low_history=low[entry_i:unlock_i],
                atr_value=float(atr[unlock_i - 1]),
                trail_atr=cfg.trail_atr,
            )
            for i in range(unlock_i, n):
                target_hit = target_touched(float(high[i]), float(low[i]), target_price, direction)
                if live_trailing.crossed_stop_at_open(float(open_[i]), active_stop, direction):
                    exit_i = i
                    reason = "gap_or_unlock_market_exit"
                    raw_exit_price = float(open_[i])
                    break
                if live_trailing.touched_stop_in_bar(float(high[i]), float(low[i]), active_stop, direction):
                    exit_i = i
                    reason = "stop_market"
                    raw_exit_price = float(active_stop)
                    break
                if target_hit:
                    exit_i = i
                    reason = "target_after_unlock"
                    raw_exit_price = float(target_price)
                    break
                if i + 1 < n:
                    active_stop = live_trailing.active_stop_from_history(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        high_history=high[entry_i : i + 1],
                        low_history=low[entry_i : i + 1],
                        atr_value=float(atr[i]),
                        trail_atr=cfg.trail_atr,
                        previous_active_stop=active_stop,
                    )

        trade = make_trade(
            label="HYPE-5M-PBTR-V3.3-immediate-tp-live-realistic",
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
        blocked_until = exit_i
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, diag: pd.DataFrame | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}
    if diag is not None and not diag.empty:
        row["target_lockout_rate"] = float((diag["reason"] == "target_lockout").mean())
        row["target_total_rate"] = float(diag["reason"].str.startswith("target").mean())
        row["median_bars_held"] = float(diag["bars_held"].median())
        row["reason_counts"] = diag["reason"].value_counts().to_dict()
    return row


def render_markdown(summary: pd.DataFrame, cfg: Any) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}

    def table_row(label: str, display: str) -> str:
        item = rows[label]
        lockout_target = item.get("target_lockout_rate", np.nan)
        total_target = item.get("target_total_rate", np.nan)
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['total_return']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['profit_factor']))}` | `{num(float(item['payoff_ratio']))}` | "
            f"`{pct(float(item['max_dd']))}` | `{pct(float(lockout_target))}` | `{pct(float(total_target))}` |"
        )

    old_reasons = rows["tp1_old_stop_price"].get("reason_counts", {})
    live_reasons = rows["tp1_live_realistic"].get("reason_counts", {})
    lines = [
        "# HYPE-5M-PBTR-V3.3 immediate TP 审计 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告把 V2.1A 的即时止盈补救想法迁移到 `HYPE-5M-PBTR-V3.3`：开仓后立即挂 `1 * ATR14` 固定止盈，不挂初始止损；锁仓期只允许止盈，`min_hold_bars` 结束后再启用原始 ATR trailing stop。",
        "",
        "## V3.3 参数",
        "",
        f"- `ema_fast={cfg.ema_fast}`，`ema_slow={cfg.ema_slow}`，`pullback_buffer={cfg.pullback_buffer}`",
        f"- `stop_atr={cfg.stop_atr}`，`trail_atr={cfg.trail_atr}`，`min_hold_bars={cfg.min_hold_bars}`",
        "- `1 * ATR14` 使用信号 K 上已经闭合可见的 `ATR14`。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 | 锁仓期止盈率 | 总止盈率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        table_row("original_old_no_tp", "V3.3 原始旧口径，无即时 TP"),
        table_row("live_realistic_no_tp", "V3.3 live-realistic，无即时 TP"),
        table_row("tp1_old_stop_price", "即时 1ATR TP + 旧 stop 价成交"),
        table_row("tp1_live_realistic", "即时 1ATR TP + live-realistic stop"),
        "",
        "## 退出原因",
        "",
        f"- 旧 stop 价成交口径：`{old_reasons}`",
        f"- live-realistic 口径：`{live_reasons}`",
        "",
        "## 结论",
        "",
        f"即时 `1 * ATR14` 止盈在 V3.3 上比 V2.1A 更频繁触发，约 `{pct(float(rows['tp1_live_realistic']['target_lockout_rate']))}` 的交易在锁仓期内先止盈。",
        "",
        f"但它仍没有修复核心问题：剩余交易解锁后大量进入 stop 已穿越/市价退出路径。旧 stop 价成交口径仍显著赚钱，但 live-realistic 口径 PF 只有约 `{num(float(rows['tp1_live_realistic']['profit_factor']))}`，仍是亏损结构。因此，V3.3 也不能靠入场即挂 1ATR 止盈修复。",
        "",
        "## 产物",
        "",
        "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_immediate_tp_audit.py`",
        f"- JSON：`{REPORT_PATH}`",
        f"- 汇总 CSV：`{SUMMARY_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    cfg = v33.V33_CONFIG
    raw = load_all_hype_5m()
    frame = v33.add_minimal_features(raw, cfg)
    signal = v33.build_signal(frame, cfg)

    original = v33.simulate_trades(frame, signal, cfg)
    live_no_tp, live_no_tp_diag = live_trailing.simulate_live_realistic_trailing(
        frame,
        signal,
        cfg,
        label="HYPE-5M-PBTR-V3.3-live-realistic",
        entry_slippage_rate=ENTRY_SLIPPAGE_RATE,
        exit_slippage_rate=EXIT_SLIPPAGE_RATE,
        fee_rate_per_fill=FEE_RATE_PER_FILL,
    )
    old_tp, old_tp_diag = simulate_immediate_tp_old_stop(frame, signal, cfg, tp_atr=1.0)
    live_tp, live_tp_diag = simulate_immediate_tp_live_realistic(frame, signal, cfg, tp_atr=1.0)

    summary = pd.DataFrame(
        [
            summarize("original_old_no_tp", original, frame),
            summarize("live_realistic_no_tp", live_no_tp, frame, live_no_tp_diag.rename(columns={"reason": "reason", "bars_held": "bars_held"})),
            summarize("tp1_old_stop_price", old_tp, frame, old_tp_diag),
            summarize("tp1_live_realistic", live_tp, frame, live_tp_diag),
        ]
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, cfg), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3",
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
    print(
        summary[
            [
                "label",
                "trades",
                "annualized_multiple",
                "total_return",
                "win_rate",
                "profit_factor",
                "payoff_ratio",
                "max_dd",
                "target_lockout_rate",
                "target_total_rate",
            ]
        ].to_string(index=False)
    )
    print(f"markdown={MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
