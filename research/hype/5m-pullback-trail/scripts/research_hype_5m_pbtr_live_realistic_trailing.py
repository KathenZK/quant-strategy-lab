from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v4_live_viability_audit.py")

REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing_summary.csv")
TRADE_DIAG_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing_trade_diagnostics.csv")
ROLLING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing_rolling.csv")
WEEKLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing_weekly.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_live_realistic_trailing_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-live-realistic-trailing-2026-06-24.md"
)


def load_v4_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_live_viability_audit", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v4_audit = load_v4_audit_module()
v33 = v4_audit.v33


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def apply_exit_cost(raw_exit_price: float, direction: int, exit_slippage_rate: float, extra_slippage_rate: float = 0.0) -> float:
    return float(raw_exit_price * (1.0 - direction * exit_slippage_rate) * (1.0 - direction * extra_slippage_rate))


def crossed_stop_at_open(open_price: float, active_stop: float, direction: int) -> bool:
    return bool(open_price <= active_stop if direction > 0 else open_price >= active_stop)


def touched_stop_in_bar(high_price: float, low_price: float, active_stop: float, direction: int) -> bool:
    return bool(low_price <= active_stop if direction > 0 else high_price >= active_stop)


def active_stop_from_history(
    *,
    direction: int,
    entry_price: float,
    initial_stop: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    trail_atr: float,
    previous_active_stop: float | None = None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history))) if len(high_history) else entry_price
        candidate = max(initial_stop, peak - trail_atr * atr_value)
        if previous_active_stop is not None:
            candidate = max(previous_active_stop, candidate)
    else:
        trough = min(entry_price, float(np.nanmin(low_history))) if len(low_history) else entry_price
        candidate = min(initial_stop, trough + trail_atr * atr_value)
        if previous_active_stop is not None:
            candidate = min(previous_active_stop, candidate)
    return float(candidate)


def simulate_live_realistic_trailing(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    label: str,
    entry_slippage_rate: float,
    exit_slippage_rate: float,
    fee_rate_per_fill: float,
) -> tuple[list[Any], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Any] = []
    diag_rows: list[dict[str, Any]] = []
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

        entry_price = float(open_[entry_i] * (1.0 + direction * entry_slippage_rate))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i >= n:
            break

        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        if direction > 0:
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
            lockout_mfe = float(np.nanmax(lockout_high / entry_price - 1.0)) if len(lockout_high) else 0.0
        else:
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0
            lockout_mfe = float(np.nanmax(direction * (lockout_low / entry_price - 1.0))) if len(lockout_low) else 0.0

        active_stop = active_stop_from_history(
            direction=direction,
            entry_price=entry_price,
            initial_stop=initial_stop,
            high_history=lockout_high,
            low_history=lockout_low,
            atr_value=float(atr[unlock_i - 1]),
            trail_atr=cfg.trail_atr,
        )
        unlock_active_stop = active_stop

        exit_i = unlock_i
        raw_exit_price: float
        reason: str
        unlock_stop_valid = not crossed_stop_at_open(float(open_[unlock_i]), active_stop, direction)
        stop_order_placed = unlock_stop_valid

        if not unlock_stop_valid:
            reason = "unlock_market_exit"
            raw_exit_price = float(open_[unlock_i])
        else:
            reason = "time"
            raw_exit_price = float(close[-1])
            for j in range(unlock_i, n):
                if crossed_stop_at_open(float(open_[j]), active_stop, direction):
                    exit_i = j
                    reason = "gap_market_exit"
                    raw_exit_price = float(open_[j])
                    break
                if touched_stop_in_bar(float(high[j]), float(low[j]), active_stop, direction):
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = float(active_stop)
                    break
                if j + 1 < n:
                    active_stop = active_stop_from_history(
                        direction=direction,
                        entry_price=entry_price,
                        initial_stop=initial_stop,
                        high_history=high[entry_i : j + 1],
                        low_history=low[entry_i : j + 1],
                        atr_value=float(atr[j]),
                        trail_atr=cfg.trail_atr,
                        previous_active_stop=active_stop,
                    )
                    stop_order_placed = True
            else:
                exit_i = n - 1

        stop_like = reason in {"stop_market", "gap_market_exit", "unlock_market_exit"}
        exit_price = apply_exit_cost(raw_exit_price, direction, exit_slippage_rate)
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = fee_rate_per_fill * (1.0 + exit_price / entry_price)
        net = gross - fee_cost

        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))

        trade = v33.Trade(
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
            mae_1x=float(mae - fee_rate_per_fill),
            mfe_1x=float(mfe),
        )
        trades.append(trade)
        diag_rows.append(
            {
                "label": label,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "unlock_ts": pd.Timestamp(ts_ns[unlock_i], unit="ns", tz="UTC"),
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "stop_like_exit": stop_like,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_stop": initial_stop,
                "unlock_active_stop": unlock_active_stop,
                "final_active_stop": active_stop,
                "initial_stop_bps": abs(entry_price - initial_stop) / entry_price * 10000.0,
                "unlock_active_stop_bps": abs(entry_price - unlock_active_stop) / entry_price * 10000.0,
                "final_active_stop_bps": abs(entry_price - active_stop) / entry_price * 10000.0,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_mfe_bps": lockout_mfe * 10000.0,
                "unlock_stop_valid": unlock_stop_valid,
                "stop_order_placed": stop_order_placed,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag_rows)


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def add_prefixed_slices(strategy: str, frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling, weekly, monthly = v33.baseline_time_slices(frame, trades)
    rolling.insert(0, "strategy", strategy)
    weekly.insert(0, "strategy", strategy)
    monthly.insert(0, "strategy", strategy)
    return rolling, weekly, monthly


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    diag_groups = {label: group for label, group in diag.groupby("label")}

    def row(label: str, display: str) -> str:
        item = rows[label]
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['win_rate']))}` | `{num(float(item['profit_factor']))}` | "
            f"`{num(float(item['payoff_ratio']))}` | `{pct(float(item['max_dd']))}` |"
        )

    def diag_line(label: str, display: str) -> list[str]:
        group = diag_groups[label]
        reasons = group["reason"].value_counts(normalize=True).to_dict()
        unlock_valid = float(group["unlock_stop_valid"].mean())
        lockout_q = group["lockout_mae_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
        unlock_q = group["unlock_active_stop_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
        return [
            f"- `{display}` 解锁时可正常挂 dormant stop 的比例 `{pct(unlock_valid)}`；解锁即市价退出 `{pct(float(reasons.get('unlock_market_exit', 0.0)))}`；后续 stop-market `{pct(float(reasons.get('stop_market', 0.0)))}`；后续 gap 市价退出 `{pct(float(reasons.get('gap_market_exit', 0.0)))}`。",
            f"- `{display}` 锁仓期 MAE bps：P10 `{num(float(lockout_q[0.1]))}`，P50 `{num(float(lockout_q[0.5]))}`，P90 `{num(float(lockout_q[0.9]))}`；解锁 active stop 距离 entry bps：P10 `{num(float(unlock_q[0.1]))}`，P50 `{num(float(unlock_q[0.5]))}`，P90 `{num(float(unlock_q[0.9]))}`。",
        ]

    v33_weekly = weekly[weekly["strategy"] == "HYPE-5M-PBTR-V3.3-live-realistic"]
    v4_weekly = weekly[weekly["strategy"] == "HYPE-5M-PBTR-V4-live-realistic"]
    v33_monthly = monthly[monthly["strategy"] == "HYPE-5M-PBTR-V3.3-live-realistic"]
    v4_monthly = monthly[monthly["strategy"] == "HYPE-5M-PBTR-V4-live-realistic"]

    lines = [
        "# HYPE-5M-PBTR live-realistic trailing 回测 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告按更接近实盘订单时序的退出口径，复核 `HYPE-5M-PBTR-V3.3` 与 `HYPE-5M-PBTR-V4`：锁仓期不挂策略止损；锁仓结束时若 `active_stop` 已被当前价格穿越，则直接 reduce-only 市价平仓；否则挂 reduce-only stop-market，之后每根已收盘 K 线只收紧 trailing stop。",
        "",
        "## 回测口径",
        "",
        "- 入场仍为信号 K 收盘确认，下一根 5m K 开盘成交，并使用既有实盘成本：手续费 `4.1466 bps/turnover`、开仓滑点 `10.73 bps`、平仓滑点 `2.64 bps`。",
        "- 锁仓期内不挂 `stop_atr` 或 trailing 策略止损；这里只复核策略退出，不额外模拟账户级 emergency stop。",
        "- 解锁前的 trailing 参考峰谷只用已完成的锁仓 K 线；第一个可退出 K 开盘前计算 `active_stop`。",
        "- 若 stop 价已被开盘价穿越，按该根 K 开盘市价退出；若未穿越，则在该根 K 期间按 stop-market 触发。",
        "",
        "## 结果对比",
        "",
        "| 版本 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("HYPE-5M-PBTR-V3.3-normal", "V3.3 原始回测"),
        row("HYPE-5M-PBTR-V3.3-live-realistic", "V3.3 live-realistic"),
        row("HYPE-5M-PBTR-V4-normal", "V4 原始回测"),
        row("HYPE-5M-PBTR-V4-live-realistic", "V4 live-realistic"),
        "",
        "## 订单可执行性诊断",
        "",
    ]
    lines.extend(diag_line("HYPE-5M-PBTR-V3.3-live-realistic", "V3.3 live-realistic"))
    lines.extend(diag_line("HYPE-5M-PBTR-V4-live-realistic", "V4 live-realistic"))
    lines.extend(
        [
            "",
            "## 时间切片摘要",
            "",
            f"- `V3.3 live-realistic` 周数 `{len(v33_weekly)}`，盈利周 `{int((v33_weekly['total_return'] > 0).sum())}/{len(v33_weekly)}`，中位周收益 `{pct(float(v33_weekly['total_return'].median()))}`；月数 `{len(v33_monthly)}`，盈利月 `{int((v33_monthly['total_return'] > 0).sum())}/{len(v33_monthly)}`。",
            f"- `V4 live-realistic` 周数 `{len(v4_weekly)}`，盈利周 `{int((v4_weekly['total_return'] > 0).sum())}/{len(v4_weekly)}`，中位周收益 `{pct(float(v4_weekly['total_return'].median()))}`；月数 `{len(v4_monthly)}`，盈利月 `{int((v4_monthly['total_return'] > 0).sum())}/{len(v4_monthly)}`。",
            "",
            "## 结论",
            "",
            "`live-realistic` 口径没有把策略变成固定持仓后直接平仓，而是保留 trailing stop 的状态机；但结果显示两个版本都从原始回测的高 PF 结构坍缩为亏损结构。主要原因是大量交易在解锁当刻 `active_stop` 已经被当前价格穿越，实盘只能市价退出，而不能按已经穿越的 stop 价成交。",
            "",
            "因此，`HYPE-5M-PBTR-V3.3` 和 `HYPE-5M-PBTR-V4` 都不能按当前参数直接作为实盘交接版本。真正可执行的后续方向应重新设计退出：例如缩短或取消 `min_hold_bars`、解锁时重新初始化 trailing stop、或把锁仓期内的风险约束改为明确的宽 emergency stop 后重新搜索参数。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_live_realistic_trailing.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
            f"- rolling CSV：`{ROLLING_PATH}`",
            f"- weekly CSV：`{WEEKLY_PATH}`",
            f"- monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    configs = [
        ("HYPE-5M-PBTR-V3.3", v33.V33_CONFIG),
        ("HYPE-5M-PBTR-V4", v4_audit.V4_CONFIG),
    ]

    summary_rows: list[dict[str, Any]] = []
    all_diag: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    report_strategies: dict[str, Any] = {}

    for strategy, cfg in configs:
        frame = v33.add_minimal_features(raw, cfg)
        signal = v33.build_signal(frame, cfg)
        normal_trades = v33.simulate_trades(frame, signal, cfg)
        live_label = f"{strategy}-live-realistic"
        normal_label = f"{strategy}-normal"
        live_trades, diag = simulate_live_realistic_trailing(
            frame,
            signal,
            cfg,
            label=live_label,
            entry_slippage_rate=v33.ENTRY_SLIPPAGE_RATE,
            exit_slippage_rate=v33.EXIT_SLIPPAGE_RATE,
            fee_rate_per_fill=v33.FEE_RATE_PER_FILL,
        )

        summary_rows.append(summarize(normal_label, normal_trades, frame, {"mode": "normal_backtest"}))
        summary_rows.append(
            summarize(
                live_label,
                live_trades,
                frame,
                {
                    "mode": "live_realistic_trailing",
                    "unlock_stop_valid_rate": float(diag["unlock_stop_valid"].mean()),
                    "unlock_market_exit_rate": float((diag["reason"] == "unlock_market_exit").mean()),
                    "stop_market_rate": float((diag["reason"] == "stop_market").mean()),
                    "gap_market_exit_rate": float((diag["reason"] == "gap_market_exit").mean()),
                },
            )
        )
        all_diag.append(diag)
        rolling, weekly, monthly = add_prefixed_slices(live_label, frame, live_trades)
        rolling_frames.append(rolling)
        weekly_frames.append(weekly)
        monthly_frames.append(monthly)
        report_strategies[strategy] = {
            "definition": asdict(cfg),
            "normal_trade_count": len(normal_trades),
            "live_realistic_trade_count": len(live_trades),
        }

    summary = pd.DataFrame(summary_rows)
    diag_all = pd.concat(all_diag, ignore_index=True)
    rolling_all = pd.concat(rolling_frames, ignore_index=True)
    weekly_all = pd.concat(weekly_frames, ignore_index=True)
    monthly_all = pd.concat(monthly_frames, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag_all.to_csv(TRADE_DIAG_PATH, index=False)
    rolling_all.to_csv(ROLLING_PATH, index=False)
    weekly_all.to_csv(WEEKLY_PATH, index=False)
    monthly_all.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, diag_all, rolling_all, weekly_all, monthly_all), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "audit": "live_realistic_trailing",
                "strategies": report_strategies,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trade_diagnostics": str(TRADE_DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
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
    print(diag_all.groupby("label")["reason"].value_counts(normalize=True).to_string())


if __name__ == "__main__":
    main()
