from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v6 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_full_ablation.py", "hype_pbtr_v6_full_for_tp_trailing")
v6_search = load_module(
    SCRIPT_DIR / "research_hype_5m_pbtr_v6_live_executable_search.py",
    "hype_pbtr_v6_search_for_tp_trailing",
)

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_tp_trigger_trailing_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_tp_trigger_trailing_trades_{RUN_DATE}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_tp_trigger_trailing_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-1-tp-trigger-trailing-{RUN_DATE}.md"

LEVERAGE = 3.0


@dataclass(frozen=True, slots=True)
class TrailOverlay:
    trigger_atr: float = 2.5
    lock_atr: float = 1.0
    trail_atr: float = 2.0
    max_hold_bars: int = 72

    @property
    def label(self) -> str:
        return f"trigger{self.trigger_atr:g}_lock{self.lock_atr:g}_trail{self.trail_atr:g}_max{self.max_hold_bars}"


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def price_with_exit_cost(raw_exit_price: float, side: int) -> float:
    return float(raw_exit_price * (1.0 - side * v6.EXIT_SLIPPAGE_RATE))


def net_return(side: int, entry_price: float, raw_exit_price: float) -> float:
    exit_price = price_with_exit_cost(raw_exit_price, side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = v6.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    return float(gross - fee_cost)


def simulate_trigger_trailing(frame: pd.DataFrame, signal: np.ndarray, overlay: TrailOverlay) -> list[Any]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Any] = []
    blocked_until = -1
    n = len(frame)

    for sig_i in np.flatnonzero(signal):
        side = int(signal[sig_i])
        entry_i = sig_i + 1
        if side == 0 or entry_i >= n or entry_i <= blocked_until:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + side * v6.ENTRY_SLIPPAGE_RATE))
        trigger_price = entry_price + side * overlay.trigger_atr * signal_atr
        initial_stop = entry_price - side * v6.BASELINE.sl_atr * signal_atr
        lock_stop = entry_price + side * overlay.lock_atr * signal_atr
        active_stop = initial_stop
        peak = entry_price
        triggered = False
        exit_i = min(n - 1, entry_i + overlay.max_hold_bars)
        raw_exit_price = float(open_[exit_i] if exit_i < n else close[-1])
        reason = "time_open"

        for bar_i in range(entry_i, min(n, entry_i + overlay.max_hold_bars + 1)):
            if not triggered:
                if v6_search.crossed_stop(float(open_[bar_i]), initial_stop, side):
                    exit_i = bar_i
                    raw_exit_price = float(open_[bar_i])
                    reason = "stop_gap_open"
                    break
                if v6_search.crossed_target(float(open_[bar_i]), trigger_price, side):
                    triggered = True
                    peak = max(peak, float(open_[bar_i]), float(high[bar_i]))
                    active_stop = max(initial_stop, lock_stop, peak - overlay.trail_atr * signal_atr)
                    continue
                if bar_i == entry_i + overlay.max_hold_bars:
                    exit_i = bar_i
                    raw_exit_price = float(open_[bar_i])
                    reason = "time_open_untriggered"
                    break
                stop_hit = v6_search.touched_stop(float(high[bar_i]), float(low[bar_i]), initial_stop, side)
                target_hit = v6_search.touched_target(float(high[bar_i]), float(low[bar_i]), trigger_price, side)
                if stop_hit and target_hit:
                    exit_i = bar_i
                    raw_exit_price = float(initial_stop)
                    reason = "both_hit_stop_first"
                    break
                if stop_hit:
                    exit_i = bar_i
                    raw_exit_price = float(initial_stop)
                    reason = "stop_market"
                    break
                if target_hit:
                    triggered = True
                    peak = max(peak, float(high[bar_i]))
                    active_stop = max(initial_stop, lock_stop, peak - overlay.trail_atr * signal_atr)
                    continue
                continue

            if v6_search.crossed_stop(float(open_[bar_i]), active_stop, side):
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "trail_gap_open"
                break
            if bar_i == entry_i + overlay.max_hold_bars:
                exit_i = bar_i
                raw_exit_price = float(open_[bar_i])
                reason = "time_open_triggered"
                break
            if v6_search.touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side):
                exit_i = bar_i
                raw_exit_price = float(active_stop)
                reason = "trail_stop"
                break
            peak = max(peak, float(high[bar_i]))
            active_stop = max(active_stop, lock_stop, peak - overlay.trail_atr * signal_atr)

        path_high = high[entry_i : exit_i + 1]
        path_low = low[entry_i : exit_i + 1]
        mae = float(np.nanmin(path_low / entry_price - 1.0)) if len(path_low) else 0.0
        mfe = float(np.nanmax(path_high / entry_price - 1.0)) if len(path_high) else 0.0
        net = net_return(side, entry_price, raw_exit_price)
        trade = v6_search.Trade(
            config=overlay.label,
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=side,
            entry_price=entry_price,
            exit_price=price_with_exit_cost(raw_exit_price, side),
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=net,
            mae_1x=float(mae - v6.FEE_RATE_PER_FILL),
            mfe_1x=mfe,
        )
        trades.append(trade)
        blocked_until = exit_i
    return trades


def equity_metrics(returns: np.ndarray) -> dict[str, float]:
    equity = np.cumprod(1.0 + returns)
    equity_with_start = np.r_[1.0, equity]
    peak = np.maximum.accumulate(equity_with_start)
    dd = equity_with_start / peak - 1.0
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    return {
        "trades": float(len(returns)),
        "total_return": float(equity[-1] - 1.0) if len(equity) else 0.0,
        "max_dd": float(dd.min()) if len(dd) else 0.0,
        "avg_trade": float(returns.mean()) if len(returns) else 0.0,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else np.inf,
        "payoff_ratio": float(wins.mean() / -losses.mean()) if len(wins) and len(losses) else np.inf,
        "worst_trade": float(returns.min()) if len(returns) else 0.0,
        "best_trade": float(returns.max()) if len(returns) else 0.0,
    }


def reason_counts(trades: list[Any]) -> str:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.reason] = counts.get(trade.reason, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def row_for(label: str, trades: list[Any], overlay: TrailOverlay | None = None) -> dict[str, Any]:
    returns_1x = np.array([float(trade.net_ret_1x) for trade in trades], dtype="float64")
    returns_3x = returns_1x * LEVERAGE
    row = {
        "label": label,
        "reason_counts": reason_counts(trades),
        **equity_metrics(returns_3x),
    }
    if overlay is not None:
        row.update(asdict(overlay))
    return row


def trade_rows(label: str, trades: list[Any], overlay: TrailOverlay | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    overlay_data = {} if overlay is None else asdict(overlay)
    for i, trade in enumerate(trades, start=1):
        rows.append(
            {
                "label": label,
                "trade_no": i,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "net_ret_1x": trade.net_ret_1x,
                "net_ret_3x": trade.net_ret_1x * LEVERAGE,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                **overlay_data,
            }
        )
    return rows


def render_markdown(summary: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("fixed_tp25_3x")].iloc[0]
    top = summary.loc[~summary["label"].eq("fixed_tp25_3x")].sort_values(["total_return", "max_dd"], ascending=[False, False]).head(15)
    dd_top = summary.loc[~summary["label"].eq("fixed_tp25_3x")].sort_values(["max_dd", "total_return"], ascending=[False, False]).head(10)
    lines = [
        "# HYPE-5M-PBTR-V6.1 TP trigger trailing 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试“触发止盈后不直接平仓，而是改为 trailing stop 让利润奔跑”。基线为 V6.1：`TP=2.5ATR`、`SL=7ATR`、`timeout=36`、fixed `3x`。",
        "",
        "## 近似口径",
        "",
        "- 价格触及 `2.5ATR` trigger 前，仍按原始 SL 保护。",
        "- trigger 被触及时不平仓；从下一根 5m K 开始使用 trailing stop。",
        "- trailing stop = `max(initial_stop, entry + lock_atr * ATR, peak - trail_atr * ATR)`。",
        "- 为避免 5m OHLC 中同一根 K 的高低点顺序造成 lookahead，本轮不假设 trigger 当根内能同时完成最优 trailing 保护。",
        "- 所有收益按 fixed `3x` sizing 统计。",
        "",
        "## 固定止盈基线",
        "",
        "| config | trades | total | max DD | win | PF | payoff | worst | best |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `fixed_tp25_3x` | `{int(baseline['trades'])}` | `{fmt_pct(float(baseline['total_return']))}` | `{fmt_pct(float(baseline['max_dd']))}` | `{fmt_pct(float(baseline['win_rate']))}` | `{fmt_num(float(baseline['profit_factor']))}` | `{fmt_num(float(baseline['payoff_ratio']))}` | `{fmt_pct(float(baseline['worst_trade']))}` | `{fmt_pct(float(baseline['best_trade']))}` |",
        "",
        "## 收益 Top",
        "",
        "| config | trades | total | max DD | win | PF | payoff | worst | best | reasons |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in top.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | `{fmt_num(float(row['payoff_ratio']))}` | "
            f"`{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` | `{row['reason_counts']}` |"
        )
    lines.extend(["", "## 回撤 Top", ""])
    lines.append("| config | trades | total | max DD | win | PF | worst | best |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in dd_top.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` |"
        )
    best = top.iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"本轮最高收益 trailing overlay 为 `{best['label']}`，总收益 `{fmt_pct(float(best['total_return']))}`、最大回撤 `{fmt_pct(float(best['max_dd']))}`。固定止盈 V6.1 基线为总收益 `{fmt_pct(float(baseline['total_return']))}`、最大回撤 `{fmt_pct(float(baseline['max_dd']))}`。",
            "",
            "若 trailing overlay 没有明显超过 fixed TP，说明 V6.1 的 edge 更像是“强动量后吃一段 2.5ATR 目标”，而不是持续持有趋势右尾；此时强行让利润奔跑会降低胜率并增加回撤。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary CSV：`{SUMMARY_PATH}`",
            f"- trades CSV：`{TRADES_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_required_features(raw)
    cfg = replace(v6.BASELINE, tp_atr=2.5)
    signal, raw_count = v6.build_filtered_signal(frame, cfg)
    baseline_trades = v6.simulate_live_orders(frame, signal, v6.signal_spec(cfg), v6.exit_spec(cfg), label="fixed_tp25")

    overlays = [
        TrailOverlay(trigger_atr=2.5, lock_atr=lock, trail_atr=trail, max_hold_bars=max_hold)
        for lock in (0.0, 1.0, 1.5, 2.0, 2.5)
        for trail in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0)
        for max_hold in (36, 72, 144)
    ]
    rows = [row_for("fixed_tp25_3x", baseline_trades)]
    all_trade_rows = trade_rows("fixed_tp25_3x", baseline_trades)
    for overlay in overlays:
        trades = simulate_trigger_trailing(frame, signal, overlay)
        label = overlay.label
        rows.append(row_for(label, trades, overlay))
        all_trade_rows.extend(trade_rows(label, trades, overlay))

    summary = pd.DataFrame(rows)
    trades_out = pd.DataFrame(all_trade_rows)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    trades_out.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.1",
                "audit": "tp_trigger_trailing",
                "definition": {
                    "base": asdict(cfg),
                    "leverage": LEVERAGE,
                    "raw_signal_count": raw_count,
                    "filtered_signal_count": int(np.count_nonzero(signal)),
                },
                "top": summary.sort_values(["total_return", "max_dd"], ascending=[False, False]).head(20).to_dict(orient="records"),
                "outputs": {"markdown": str(MARKDOWN_PATH), "summary": str(SUMMARY_PATH), "trades": str(TRADES_PATH)},
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.sort_values(["total_return", "max_dd"], ascending=[False, False]).head(20).to_string(index=False))


if __name__ == "__main__":
    main()
