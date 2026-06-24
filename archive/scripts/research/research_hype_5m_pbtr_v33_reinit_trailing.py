from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LIVE_REALISTIC_PATH = Path(__file__).with_name("research_hype_5m_pbtr_live_realistic_trailing.py")

REPORT_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing_summary.csv")
TRADE_DIAG_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing_trade_diagnostics.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v33_reinit_trailing_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-reinit-trailing-2026-06-24.md"
)


def load_live_realistic_module() -> Any:
    spec = importlib.util.spec_from_file_location("v33_live_realistic", LIVE_REALISTIC_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {LIVE_REALISTIC_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


live_realistic = load_live_realistic_module()
v33 = live_realistic.v33


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def crossed_stop_at_open(open_price: float, stop_price: float, direction: int) -> bool:
    return bool(open_price <= stop_price if direction > 0 else open_price >= stop_price)


def touched_stop_in_bar(high_price: float, low_price: float, stop_price: float, direction: int) -> bool:
    return bool(low_price <= stop_price if direction > 0 else high_price >= stop_price)


def reinit_stop_price(
    *,
    direction: int,
    reference_price: float,
    atr_value: float,
    stop_atr: float,
    trail_atr: float,
    use_initial_stop: bool,
) -> float:
    distance_atr = min(stop_atr, trail_atr) if use_initial_stop else trail_atr
    return float(reference_price - direction * distance_atr * atr_value)


def trail_stop_from_reset_history(
    *,
    direction: int,
    reference_price: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    trail_atr: float,
    previous_stop: float,
) -> float:
    if direction > 0:
        peak = max(reference_price, float(np.nanmax(high_history))) if len(high_history) else reference_price
        return float(max(previous_stop, peak - trail_atr * atr_value))
    trough = min(reference_price, float(np.nanmin(low_history))) if len(low_history) else reference_price
    return float(min(previous_stop, trough + trail_atr * atr_value))


def simulate_reinit_trailing(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    label: str,
    reference_mode: str,
    use_initial_stop: bool,
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
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i >= n:
            break

        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        if direction > 0:
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
            lockout_mfe = float(np.nanmax(lockout_high / entry_price - 1.0)) if len(lockout_high) else 0.0
        else:
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0
            lockout_mfe = float(np.nanmax(direction * (lockout_low / entry_price - 1.0))) if len(lockout_low) else 0.0

        reference_price = float(open_[unlock_i] if reference_mode == "unlock_open" else close[unlock_i - 1])
        atr_value = float(atr[unlock_i - 1])
        active_stop = reinit_stop_price(
            direction=direction,
            reference_price=reference_price,
            atr_value=atr_value,
            stop_atr=cfg.stop_atr,
            trail_atr=cfg.trail_atr,
            use_initial_stop=use_initial_stop,
        )
        unlock_stop = active_stop
        unlock_stop_valid = not crossed_stop_at_open(float(open_[unlock_i]), active_stop, direction)

        if not unlock_stop_valid:
            exit_i = unlock_i
            reason = "unlock_market_exit"
            raw_exit_price = float(open_[unlock_i])
        else:
            exit_i = n - 1
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
                    active_stop = trail_stop_from_reset_history(
                        direction=direction,
                        reference_price=reference_price,
                        high_history=high[unlock_i : j + 1],
                        low_history=low[unlock_i : j + 1],
                        atr_value=float(atr[j]),
                        trail_atr=cfg.trail_atr,
                        previous_stop=active_stop,
                    )

        exit_price = float(raw_exit_price * (1.0 - direction * v33.EXIT_SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = v33.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
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
            mae_1x=float(mae - v33.FEE_RATE_PER_FILL),
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
                "reference_mode": reference_mode,
                "use_initial_stop": use_initial_stop,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "entry_price": entry_price,
                "reference_price": reference_price,
                "exit_price": exit_price,
                "unlock_active_stop": unlock_stop,
                "final_active_stop": active_stop,
                "unlock_active_stop_bps_from_ref": abs(reference_price - unlock_stop) / reference_price * 10000.0,
                "unlock_active_stop_bps_from_entry": abs(entry_price - unlock_stop) / entry_price * 10000.0,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_mfe_bps": lockout_mfe * 10000.0,
                "unlock_stop_valid": unlock_stop_valid,
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


def add_slices(strategy: str, frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
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
        stop_q = group["unlock_active_stop_bps_from_ref"].quantile([0.1, 0.5, 0.9]).to_dict()
        strategy_weekly = weekly[weekly["strategy"] == label]
        strategy_monthly = monthly[monthly["strategy"] == label]
        return [
            f"- `{display}` 解锁可正常挂 dormant stop `{pct(unlock_valid)}`；解锁即市价退出 `{pct(float(reasons.get('unlock_market_exit', 0.0)))}`；后续 stop-market `{pct(float(reasons.get('stop_market', 0.0)))}`；后续 gap 市价退出 `{pct(float(reasons.get('gap_market_exit', 0.0)))}`。",
            f"- `{display}` 解锁 stop 距离初始化锚点 bps：P10 `{num(float(stop_q[0.1]))}`，P50 `{num(float(stop_q[0.5]))}`，P90 `{num(float(stop_q[0.9]))}`；盈利周 `{int((strategy_weekly['total_return'] > 0).sum())}/{len(strategy_weekly)}`，盈利月 `{int((strategy_monthly['total_return'] > 0).sum())}/{len(strategy_monthly)}`。",
        ]

    lines = [
        "# HYPE-5M-PBTR-V3.3 解锁重置 trailing 回测 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试 V3.3 的方案 2：锁仓期只观察，不把锁仓期峰谷带入 trailing；第 `10` 根 5m K 开始重新初始化 stop，再按 reduce-only stop-market 继续管理。",
        "",
        "## 回测口径",
        "",
        "- 入场、成本、信号仍沿用 `HYPE-5M-PBTR-V3.3`：`EMA21/EMA96 + pullback_buffer=0.01 + stop_atr=0.5 + trail_atr=0.75 + min_hold_bars=9`。",
        "- 锁仓期内不挂策略 stop，本报告不额外模拟账户级 emergency stop。",
        "- `trail_only_unlock_open`：第 `10` 根 K 开盘用当前开盘价作为新 trailing 锚点，初始 stop 距离为 `0.75 ATR`。",
        "- `trail_only_prev_close`：第 `10` 根 K 开盘前用上一根已收盘 K 的 close 作为新 trailing 锚点，初始 stop 距离为 `0.75 ATR`。",
        "- `stop_and_trail_unlock_open`：第 `10` 根 K 开盘用当前开盘价作为锚点，同时重新启用 `0.5 ATR` 初始 stop 和 `0.75 ATR` trailing。",
        "",
        "## 结果对比",
        "",
        "| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("HYPE-5M-PBTR-V3.3-normal", "原始回测"),
        row("HYPE-5M-PBTR-V3.3-live-realistic", "严格 live-realistic"),
        row("V3.3-reinit-trail-only-unlock-open", "trail only / unlock open"),
        row("V3.3-reinit-trail-only-prev-close", "trail only / prev close"),
        row("V3.3-reinit-stop-and-trail-unlock-open", "stop + trail / unlock open"),
        "",
        "## 可执行性诊断",
        "",
    ]
    lines.extend(diag_line("V3.3-reinit-trail-only-unlock-open", "trail only / unlock open"))
    lines.extend(diag_line("V3.3-reinit-trail-only-prev-close", "trail only / prev close"))
    lines.extend(diag_line("V3.3-reinit-stop-and-trail-unlock-open", "stop + trail / unlock open"))
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "`unlock_open` 作为重新初始化锚点可以消除“解锁即 stop 已穿越”的不可挂单问题，但当前 V3.3 参数下，重新初始化后的 trailing 仍无法恢复原始回测优势。`trail_atr=0.75` 在解锁后独立运行时过于贴近噪声，结果仍为 PF 小于 1。",
            "",
            "`prev_close` 锚点更保守、更接近开盘前已知信息；本次样本中它同样没有产生解锁即市价退出，但表现仍不达标。`stop + trail / unlock open` 更紧，也没有改善。",
            "",
            "因此，方案 2 的机制方向是正确的：它修复了不可执行成交假设；但不能直接沿用 V3.3 的 `stop_atr=0.5 / trail_atr=0.75 / min_hold_bars=9` 参数。下一步应在该可执行状态机上重新搜索更宽的 `trail_atr`、可选的 emergency stop，以及更短的 `min_hold_bars`。",
            "",
            "## 产物",
            "",
            "- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_reinit_trailing.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
            f"- rolling CSV：`{ROLLING_PATH}`",
            f"- weekly CSV：`{WEEKLY_PATH}`",
            f"- monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    _ = rolling
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    cfg = v33.V33_CONFIG
    frame = v33.add_minimal_features(raw, cfg)
    signal = v33.build_signal(frame, cfg)
    normal_trades = v33.simulate_trades(frame, signal, cfg)
    live_trades, _live_diag = live_realistic.simulate_live_realistic_trailing(
        frame,
        signal,
        cfg,
        label="HYPE-5M-PBTR-V3.3-live-realistic",
        entry_slippage_rate=v33.ENTRY_SLIPPAGE_RATE,
        exit_slippage_rate=v33.EXIT_SLIPPAGE_RATE,
        fee_rate_per_fill=v33.FEE_RATE_PER_FILL,
    )

    variants = [
        ("V3.3-reinit-trail-only-unlock-open", "unlock_open", False),
        ("V3.3-reinit-trail-only-prev-close", "prev_close", False),
        ("V3.3-reinit-stop-and-trail-unlock-open", "unlock_open", True),
    ]
    summary_rows = [
        summarize("HYPE-5M-PBTR-V3.3-normal", normal_trades, frame, {"mode": "normal_backtest"}),
        summarize("HYPE-5M-PBTR-V3.3-live-realistic", live_trades, frame, {"mode": "strict_live_realistic"}),
    ]
    diag_frames: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    variant_defs: list[dict[str, Any]] = []

    for label, reference_mode, use_initial_stop in variants:
        trades, diag = simulate_reinit_trailing(frame, signal, cfg, label=label, reference_mode=reference_mode, use_initial_stop=use_initial_stop)
        summary_rows.append(
            summarize(
                label,
                trades,
                frame,
                {
                    "mode": "reinit_trailing",
                    "reference_mode": reference_mode,
                    "use_initial_stop": use_initial_stop,
                    "unlock_stop_valid_rate": float(diag["unlock_stop_valid"].mean()),
                    "unlock_market_exit_rate": float((diag["reason"] == "unlock_market_exit").mean()),
                    "stop_market_rate": float((diag["reason"] == "stop_market").mean()),
                    "gap_market_exit_rate": float((diag["reason"] == "gap_market_exit").mean()),
                },
            )
        )
        diag_frames.append(diag)
        rolling, weekly, monthly = add_slices(label, frame, trades)
        rolling_frames.append(rolling)
        weekly_frames.append(weekly)
        monthly_frames.append(monthly)
        variant_defs.append({"label": label, "reference_mode": reference_mode, "use_initial_stop": use_initial_stop, "trades": len(trades)})

    summary = pd.DataFrame(summary_rows)
    diag_all = pd.concat(diag_frames, ignore_index=True)
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
                "strategy": "HYPE-5M-PBTR-V3.3",
                "definition": asdict(cfg),
                "audit": "reinit_trailing_after_lockout",
                "variants": variant_defs,
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
