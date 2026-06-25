from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REINIT_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v33_reinit_trailing.py")

REPORT_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing_summary.csv")
TRADE_DIAG_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing_trade_diagnostics.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v33_blend_peak_open_trailing_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-blend-peak-open-trailing-2026-06-25.md"
)


def load_reinit_module() -> Any:
    spec = importlib.util.spec_from_file_location("v33_reinit_trailing", REINIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {REINIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


reinit = load_reinit_module()
v33 = reinit.v33
live_realistic = reinit.live_realistic


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def simulate_blend_peak_open_trailing(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    label: str,
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
        unlock_open = float(open_[unlock_i])
        if direction > 0:
            lockout_extreme = max(entry_price, float(np.nanmax(lockout_high))) if len(lockout_high) else entry_price
            reference_price = (lockout_extreme + unlock_open) / 2.0
            active_stop = reference_price - cfg.trail_atr * float(atr[unlock_i - 1])
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
            lockout_mfe = float(np.nanmax(lockout_high / entry_price - 1.0)) if len(lockout_high) else 0.0
        else:
            lockout_extreme = min(entry_price, float(np.nanmin(lockout_low))) if len(lockout_low) else entry_price
            reference_price = (lockout_extreme + unlock_open) / 2.0
            active_stop = reference_price + cfg.trail_atr * float(atr[unlock_i - 1])
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0
            lockout_mfe = float(np.nanmax(direction * (lockout_low / entry_price - 1.0))) if len(lockout_low) else 0.0

        unlock_stop = float(active_stop)
        unlock_stop_valid = not reinit.crossed_stop_at_open(unlock_open, active_stop, direction)
        if not unlock_stop_valid:
            exit_i = unlock_i
            reason = "unlock_market_exit"
            raw_exit_price = unlock_open
        else:
            exit_i = n - 1
            reason = "time"
            raw_exit_price = float(close[-1])
            for j in range(unlock_i, n):
                if reinit.crossed_stop_at_open(float(open_[j]), active_stop, direction):
                    exit_i = j
                    reason = "gap_market_exit"
                    raw_exit_price = float(open_[j])
                    break
                if reinit.touched_stop_in_bar(float(high[j]), float(low[j]), active_stop, direction):
                    exit_i = j
                    reason = "stop_market"
                    raw_exit_price = float(active_stop)
                    break
                if j + 1 < n:
                    active_stop = reinit.trail_stop_from_reset_history(
                        direction=direction,
                        reference_price=reference_price,
                        high_history=high[unlock_i : j + 1],
                        low_history=low[unlock_i : j + 1],
                        atr_value=float(atr[j]),
                        trail_atr=cfg.trail_atr,
                        previous_stop=float(active_stop),
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
                "bars_held": trade.bars_held,
                "entry_price": entry_price,
                "unlock_open": unlock_open,
                "lockout_extreme": lockout_extreme,
                "reference_price": reference_price,
                "unlock_active_stop": unlock_stop,
                "final_active_stop": float(active_stop),
                "unlock_stop_valid": unlock_stop_valid,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_mfe_bps": lockout_mfe * 10000.0,
                "net_ret_1x": trade.net_ret_1x,
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


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, rolling: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    diag_groups = {label: group for label, group in diag.groupby("label")}

    def row(label: str, display: str) -> str:
        item = rows[label]
        group = diag_groups[label]
        unlock_market = float(group["reason"].eq("unlock_market_exit").mean())
        stop_market = float(group["reason"].eq("stop_market").mean())
        gap_market = float(group["reason"].eq("gap_market_exit").mean())
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['win_rate']))}` | `{num(float(item['profit_factor']))}` | "
            f"`{num(float(item['payoff_ratio']))}` | `{pct(float(item['max_dd']))}` | "
            f"`{pct(unlock_market)}` | `{pct(stop_market)}` | `{pct(gap_market)}` |"
        )

    blend_rolling = rolling.loc[rolling["strategy"].eq("blend_peak_open")].copy()
    lines = [
        "# HYPE-5M-PBTR-V3.3 peak/open 均价 trailing 回测 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试一个折中解锁锚点：第 `10` 根 K 开始时，不直接用锁仓期 peak/trough，也不完全用 unlock open，而是使用二者均价作为 trailing 锚点。",
        "",
        "定义：",
        "",
        "- 多头：`reference = (lockout_peak + unlock_open) / 2`，`stop = reference - 0.75 * ATR`。",
        "- 空头：`reference = (lockout_trough + unlock_open) / 2`，`stop = reference + 0.75 * ATR`。",
        "- 如果该 stop 在 unlock open 仍已穿越，则按可执行口径市价退出。",
        "",
        "## 结果对比",
        "",
        "| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 解锁即市价 | stop-market | gap 市价 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("original_old_fill", "原始旧回测"),
        row("unlock_open", "unlock open 重置"),
        row("blend_peak_open", "peak/open 均价"),
        "",
        "## peak/open 均价时间切片",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in blend_rolling.to_dict(orient="records"):
        lines.append(
            f"| `{item['window']}` | `{int(item['trades'])}` | `{pct(float(item['total_return']))}` | "
            f"`{mult(float(item['annualized_multiple']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['payoff_ratio']))}` | `{num(float(item['profit_factor']))}` | `{pct(float(item['max_dd']))}` |"
        )
    blend = rows["blend_peak_open"]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"`peak/open` 均价锚点比纯 `unlock_open` 更保留锁仓期浮盈信息，但仍没有恢复旧 V3.3 优势：全样本 PF `{num(float(blend['profit_factor']))}`，最大回撤 `{pct(float(blend['max_dd']))}`。",
            "",
            "因此，均价锚点可以作为机制探索记录，但不是可交接的 V3.3 修复版本。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v33_blend_peak_open_trailing.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    frame = v33.add_minimal_features(raw, v33.V33_CONFIG)
    signal = v33.build_signal(frame, v33.V33_CONFIG)

    original_trades = v33.simulate_trades(frame, signal, v33.V33_CONFIG)
    unlock_trades, unlock_diag = reinit.simulate_reinit_trailing(
        frame,
        signal,
        v33.V33_CONFIG,
        label="unlock_open",
        reference_mode="unlock_open",
        use_initial_stop=False,
    )
    blend_trades, blend_diag = simulate_blend_peak_open_trailing(frame, signal, v33.V33_CONFIG, label="blend_peak_open")

    variants = [
        ("original_old_fill", original_trades, pd.DataFrame({"label": ["original_old_fill"] * len(original_trades), "reason": [trade.reason for trade in original_trades]})),
        ("unlock_open", unlock_trades, unlock_diag),
        ("blend_peak_open", blend_trades, blend_diag),
    ]
    summary_rows: list[dict[str, Any]] = []
    diag_parts: list[pd.DataFrame] = []
    rolling_parts: list[pd.DataFrame] = []
    weekly_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    for label, trades, diag in variants:
        summary_rows.append(summarize(label, trades, frame))
        diag_parts.append(diag)
        rolling, weekly, monthly = add_slices(label, frame, trades)
        rolling_parts.append(rolling)
        weekly_parts.append(weekly)
        monthly_parts.append(monthly)

    summary = pd.DataFrame(summary_rows)
    diag = pd.concat(diag_parts, ignore_index=True, sort=False)
    rolling = pd.concat(rolling_parts, ignore_index=True)
    weekly = pd.concat(weekly_parts, ignore_index=True)
    monthly = pd.concat(monthly_parts, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag.to_csv(TRADE_DIAG_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, diag, rolling), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3 blend peak/open trailing",
                "definition": asdict(v33.V33_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "diagnostics": str(TRADE_DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary.to_dict(orient="records"),
                "reason_counts": diag.groupby(["label", "reason"]).size().reset_index(name="count").to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))
    print(diag.groupby(["label", "reason"]).size().reset_index(name="count").to_string(index=False))


if __name__ == "__main__":
    main()
