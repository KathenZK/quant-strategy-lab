from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v3-3_full_ablation.py")

REPORT_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_audit.json")
SUMMARY_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_summary.csv")
COST_STRESS_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_cost_stress.csv")
TRADE_DIAG_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_trade_diagnostics.csv")
ROLLING_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_rolling.csv")
WEEKLY_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_weekly.csv")
MONTHLY_PATH = Path("reports/hype_5m_pbtr_v4_live_viability_monthly.csv")
MARKDOWN_PATH = Path(
    "docs/research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v4-live-viability-audit-2026-06-24.md"
)


def load_v33_module() -> Any:
    spec = importlib.util.spec_from_file_location("v33_full_ablation", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v33 = load_v33_module()

V4_CONFIG = replace(
    v33.V33_CONFIG,
    strategy_name="HYPE-5M-PBTR-V4",
    ema_fast=9,
    ema_slow=96,
    pullback_buffer=0.01,
    stop_atr=0.25,
    trail_atr=0.5,
    min_hold_bars=18,
)


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def simulate_with_cost(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    label: str,
    entry_slippage_rate: float,
    exit_slippage_rate: float,
    fee_rate_per_fill: float,
    extra_stop_slippage_rate: float = 0.0,
    initial_stop_active_during_lockout: bool = False,
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
        atr_value = float(atr[sig_i])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * entry_slippage_rate))
        initial_stop = entry_price - direction * cfg.stop_atr * atr_value
        sl = slice(entry_i, n)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]

        if direction > 0:
            prev_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            trail_levels = prev_peak - cfg.trail_atr * atr_seg
            active_stop = np.maximum(np.full(len(high_seg), initial_stop), trail_levels)
            initial_hit = low_seg <= initial_stop
            stop_hit = low_seg <= active_stop
        else:
            prev_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            trail_levels = prev_trough + cfg.trail_atr * atr_seg
            active_stop = np.minimum(np.full(len(low_seg), initial_stop), trail_levels)
            initial_hit = high_seg >= initial_stop
            stop_hit = high_seg >= active_stop

        lockout_len = min(cfg.min_hold_bars, len(stop_hit))
        lockout_initial_hit = bool(np.any(initial_hit[:lockout_len]))
        if direction > 0:
            lockout_mae = float(np.nanmin(low_seg[: max(1, lockout_len)] / entry_price - 1.0))
        else:
            lockout_mae = float(np.nanmin(direction * (high_seg[: max(1, lockout_len)] / entry_price - 1.0)))

        if cfg.min_hold_bars > 0:
            if initial_stop_active_during_lockout:
                stop_hit[: cfg.min_hold_bars] = initial_hit[: cfg.min_hold_bars]
            else:
                stop_hit[: cfg.min_hold_bars] = False

        hit_idx = np.flatnonzero(stop_hit)
        if len(hit_idx):
            offset = int(hit_idx[0])
            reason = "stop"
            raw_exit_price = float(active_stop[offset])
            if initial_stop_active_during_lockout and offset < cfg.min_hold_bars:
                reason = "protective_stop"
                raw_exit_price = float(initial_stop)
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
        stop_extra = extra_stop_slippage_rate if reason in {"stop", "protective_stop"} else 0.0
        exit_price = float(raw_exit_price * (1.0 - direction * exit_slippage_rate) * (1.0 - direction * stop_extra))
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = fee_rate_per_fill * (1.0 + exit_price / entry_price)
        net = gross - fee_cost
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
        initial_stop_bps = abs(entry_price - initial_stop) / entry_price * 10000.0
        trail_gap_bps = float(cfg.trail_atr * atr_seg[offset] / raw_exit_price * 10000.0) if np.isfinite(atr_seg[offset]) and raw_exit_price > 0 else np.nan
        diag_rows.append(
            {
                "label": label,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_stop_bps": initial_stop_bps,
                "trail_gap_bps_at_exit": trail_gap_bps,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_initial_stop_breached": lockout_initial_hit,
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


def render_markdown(summary: pd.DataFrame, stress: pd.DataFrame, diag: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame, monthly: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    v33_row = rows["HYPE-5M-PBTR-V3.3"]
    v4_row = rows["HYPE-5M-PBTR-V4"]
    protect_row = rows["V4_protective_stop_from_entry"]
    lockout_breach_rate = float(diag["lockout_initial_stop_breached"].mean())
    stop_reasons = diag["reason"].value_counts(normalize=True).to_dict()
    initial_q = diag["initial_stop_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    trail_q = diag["trail_gap_bps_at_exit"].quantile([0.1, 0.5, 0.9]).to_dict()
    lockout_q = diag["lockout_mae_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
    worst_week = weekly.sort_values("total_return").iloc[0]
    best_week = weekly.sort_values("total_return", ascending=False).iloc[0]
    worst_month = monthly.sort_values("total_return").iloc[0]
    best_month = monthly.sort_values("total_return", ascending=False).iloc[0]

    lines = [
        "# HYPE-5M-PBTR-V4 实盘可行性审计 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告将原 `HYPE-5M-PBTR-V3.4-candidate` 记录为 `HYPE-5M-PBTR-V4`，并专门审计它是否只是回测漂亮、实盘难以复现。",
        "",
        "## V4 参数",
        "",
        "| 参数 | 值 |",
        "| --- | ---: |",
    ]
    for key, value in asdict(V4_CONFIG).items():
        if key in {"strategy_name", "timeframe"}:
            continue
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "## V3.3 vs V4",
            "",
            "| 版本 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            f"| `HYPE-5M-PBTR-V3.3` | `{int(v33_row['trades'])}` | `{mult(float(v33_row['annualized_multiple']))}` | `{pct(float(v33_row['win_rate']))}` | `{num(float(v33_row['profit_factor']))}` | `{num(float(v33_row['payoff_ratio']))}` | `{pct(float(v33_row['max_dd']))}` |",
            f"| `HYPE-5M-PBTR-V4` | `{int(v4_row['trades'])}` | `{mult(float(v4_row['annualized_multiple']))}` | `{pct(float(v4_row['win_rate']))}` | `{num(float(v4_row['profit_factor']))}` | `{num(float(v4_row['payoff_ratio']))}` | `{pct(float(v4_row['max_dd']))}` |",
            f"| `V4 protective stop from entry` | `{int(protect_row['trades'])}` | `{mult(float(protect_row['annualized_multiple']))}` | `{pct(float(protect_row['win_rate']))}` | `{num(float(protect_row['profit_factor']))}` | `{num(float(protect_row['payoff_ratio']))}` | `{pct(float(protect_row['max_dd']))}` |",
            "",
            "第三行表示：如果实盘从开仓就挂 `0.25 ATR` 保护止损，而不是等待 `min_hold_bars=18` 后才允许策略 stop，回测表现会如何变化。",
            "",
            "## 成本与 stop 成交压力",
            "",
            "| 场景 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in stress.to_dict(orient="records"):
        lines.append(f"| `{row['label']}` | `{int(row['trades'])}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['profit_factor']))}` | `{num(float(row['payoff_ratio']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "## 交易路径与执行风险",
            "",
            f"- 退出原因中 stop 占比约 `{pct(float(stop_reasons.get('stop', 0.0)))}`，说明 V4 几乎完全依赖 stop/trailing stop 成交质量。",
            f"- 初始止损距离分位数 bps：P10 `{num(float(initial_q[0.1]))}`，P50 `{num(float(initial_q[0.5]))}`，P90 `{num(float(initial_q[0.9]))}`。",
            f"- trailing gap 出场处分位数 bps：P10 `{num(float(trail_q[0.1]))}`，P50 `{num(float(trail_q[0.5]))}`，P90 `{num(float(trail_q[0.9]))}`。",
            f"- 前 `18` 根 K 的锁仓期 MAE 分位数 bps：P10 `{num(float(lockout_q[0.1]))}`，P50 `{num(float(lockout_q[0.5]))}`，P90 `{num(float(lockout_q[0.9]))}`。",
            f"- 锁仓期内曾触及 `0.25 ATR` 初始止损的交易占比 `{pct(lockout_breach_rate)}`。",
            "",
            "这意味着 V4 的漂亮回测不是来自不可计算指标，但它确实依赖一个关键执行选择：前 18 根 K 是否允许保护止损。如果严格从开仓即挂 `0.25 ATR` 保护止损，策略结构会被明显改变。",
            "",
            "## V4 时间切片",
            "",
            "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rolling.to_dict(orient="records"):
        lines.append(f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | `{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |")
    lines.extend(
        [
            "",
            "周/月摘要：",
            "",
            f"- 周数：`{len(weekly)}`，盈利周 `{int((weekly['total_return'] > 0).sum())}/{len(weekly)}`，中位周收益 `{pct(float(weekly['total_return'].median()))}`。",
            f"- 最差周：`{worst_week['window']}`，收益 `{pct(float(worst_week['total_return']))}`，最大回撤 `{pct(float(worst_week['max_dd']))}`；最好周：`{best_week['window']}`，收益 `{pct(float(best_week['total_return']))}`。",
            f"- 月数：`{len(monthly)}`，盈利月 `{int((monthly['total_return'] > 0).sum())}/{len(monthly)}`，中位月收益 `{pct(float(monthly['total_return'].median()))}`。",
            f"- 最差月：`{worst_month['window']}`，收益 `{pct(float(worst_month['total_return']))}`；最好月：`{best_month['window']}`，收益 `{pct(float(best_month['total_return']))}`。",
            "",
            "## 审计结论",
            "",
            "V4 不是明显的代码错误或不可计算策略：入场只用 EMA、K 线和 ATR，退出也能用程序维护 reduce-only stop-market 复现。因此它可以进入 paper-live。",
            "",
            "但 V4 不能直接当作生产策略。它比 V3.3 更依赖紧止损、trailing stop 和 `18` 根 K 锁仓期，尤其要先解决锁仓期保护止损政策：如果实盘挂很紧的保护止损，回测不再等价；如果完全不挂保护止损，则需要接受尾部风险。",
            "",
            "建议：只允许 paper-live / 极小资金 dry-run。验收重点不是年化，而是真实 stop 滑点、锁仓期 MAE、保护止损触发率、订单失败率，以及前 300-500 笔的 PF/payoff 是否仍然接近回测。",
            "",
            "## 产物",
            "",
            f"- 脚本：`archive/scripts/research/research_hype_5m_pbtr_v4_live_viability_audit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 成本压力 CSV：`{COST_STRESS_PATH}`",
            f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    frame_v4 = v33.add_minimal_features(raw, V4_CONFIG)
    signal_v4 = v33.build_signal(frame_v4, V4_CONFIG)
    trades_v4, diag = simulate_with_cost(
        frame_v4,
        signal_v4,
        V4_CONFIG,
        label="HYPE-5M-PBTR-V4",
        entry_slippage_rate=v33.ENTRY_SLIPPAGE_RATE,
        exit_slippage_rate=v33.EXIT_SLIPPAGE_RATE,
        fee_rate_per_fill=v33.FEE_RATE_PER_FILL,
    )

    frame_v33 = v33.add_minimal_features(raw, v33.V33_CONFIG)
    signal_v33 = v33.build_signal(frame_v33, v33.V33_CONFIG)
    trades_v33 = v33.simulate_trades(frame_v33, signal_v33, v33.V33_CONFIG)

    protective_trades, _protective_diag = simulate_with_cost(
        frame_v4,
        signal_v4,
        V4_CONFIG,
        label="V4_protective_stop_from_entry",
        entry_slippage_rate=v33.ENTRY_SLIPPAGE_RATE,
        exit_slippage_rate=v33.EXIT_SLIPPAGE_RATE,
        fee_rate_per_fill=v33.FEE_RATE_PER_FILL,
        initial_stop_active_during_lockout=True,
    )
    summary = pd.DataFrame(
        [
            summarize("HYPE-5M-PBTR-V3.3", trades_v33, frame_v33),
            summarize("HYPE-5M-PBTR-V4", trades_v4, frame_v4),
            summarize("V4_protective_stop_from_entry", protective_trades, frame_v4),
        ]
    )

    stress_specs = [
        ("base", 1.0, 1.0, 0.0),
        ("entry_slippage_2x", 2.0, 1.0, 0.0),
        ("entry_slippage_3x", 3.0, 1.0, 0.0),
        ("fee_2x", 1.0, 2.0, 0.0),
        ("stop_extra_5bps", 1.0, 1.0, 0.0005),
        ("stop_extra_10bps", 1.0, 1.0, 0.0010),
        ("stop_extra_20bps", 1.0, 1.0, 0.0020),
        ("combined_entry2x_fee2x_stop10bps", 2.0, 2.0, 0.0010),
        ("severe_entry3x_fee2x_stop20bps", 3.0, 2.0, 0.0020),
    ]
    stress_rows: list[dict[str, Any]] = []
    for label, entry_mult, fee_mult, stop_extra in stress_specs:
        trades, _ = simulate_with_cost(
            frame_v4,
            signal_v4,
            V4_CONFIG,
            label=label,
            entry_slippage_rate=v33.ENTRY_SLIPPAGE_RATE * entry_mult,
            exit_slippage_rate=v33.EXIT_SLIPPAGE_RATE,
            fee_rate_per_fill=v33.FEE_RATE_PER_FILL * fee_mult,
            extra_stop_slippage_rate=stop_extra,
        )
        stress_rows.append(
            summarize(
                label,
                trades,
                frame_v4,
                {"entry_slippage_mult": entry_mult, "fee_mult": fee_mult, "extra_stop_slippage_bps": stop_extra * 10000},
            )
        )
    stress = pd.DataFrame(stress_rows)
    rolling, weekly, monthly = v33.baseline_time_slices(frame_v4, trades_v4)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    stress.to_csv(COST_STRESS_PATH, index=False)
    diag.to_csv(TRADE_DIAG_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, stress, diag, rolling, weekly, monthly), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V4",
                "definition": asdict(V4_CONFIG),
                "source_candidate": "HYPE-5M-PBTR-V3.4-candidate/C001",
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "cost_stress": str(COST_STRESS_PATH),
                    "trade_diagnostics": str(TRADE_DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
                "summary": summary.to_dict(orient="records"),
                "cost_stress": stress.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.to_string(index=False))
    print(stress[["label", "trades", "annualized_multiple", "win_rate", "profit_factor", "max_dd"]].to_string(index=False))


if __name__ == "__main__":
    main()
