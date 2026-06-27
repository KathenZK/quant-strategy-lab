from __future__ import annotations

import importlib.util
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


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v6 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_live_executable_search.py", "hype_pbtr_v6_search_for_short_combo")

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SHORT_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_short_search_summary_{RUN_DATE}.csv"
COMBO_SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_short_combo_summary_{RUN_DATE}.csv"
COMBO_TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_short_combo_trades_{RUN_DATE}.csv"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-1_short_combo_search_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-1-short-combo-search-{RUN_DATE}.md"

LEVERAGE = 3.0


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


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


def signal_label(spec: Any) -> str:
    return spec.label


def exit_label(spec: Any) -> str:
    return spec.label


def fixed_exit_specs() -> list[Any]:
    specs: list[Any] = []
    for tx in (12, 24, 36, 48, 72):
        for tp, sl in ((1.5, 2.0), (2.0, 3.0), (2.5, 4.0), (3.0, 5.0), (4.0, 6.0), (5.0, 8.0), (6.0, 10.0)):
            specs.append(v6.ExitSpec(tp_atr=tp, sl_atr=sl, trail_atr=0.0, time_exit_bars=tx))
    return specs


def manual_rules() -> list[Any]:
    rules = [v6.RuleSpec(label="none", conditions=())]
    for threshold in (500.0, 700.0, 788.123, 1000.0, 1200.0, 1500.0, 2000.0):
        rules.append(v6.RuleSpec(label=f"dir_ret192_bps>={threshold:g}", conditions=(("dir_ret192_bps", ">=", threshold),)))
    for threshold in (200.0, 300.0, 400.0, 600.0):
        rules.append(v6.RuleSpec(label=f"dir_ret48_bps>={threshold:g}", conditions=(("dir_ret48_bps", ">=", threshold),)))
    for threshold in (0.5, 1.0, 1.3):
        rules.append(v6.RuleSpec(label=f"atr_ratio_14_96<={threshold:g}", conditions=(("atr_ratio_14_96", "<=", threshold),)))
    for threshold in (0.0, 0.5, 1.0):
        rules.append(v6.RuleSpec(label=f"opp_wick_atr<={threshold:g}", conditions=(("opp_wick_atr", "<=", threshold),)))
    for ret_threshold in (788.123, 1000.0, 1200.0):
        for wick_threshold in (0.5, 1.0):
            rules.append(
                v6.RuleSpec(
                    label=f"dir_ret192_bps>={ret_threshold:g}&opp_wick_atr<={wick_threshold:g}",
                    conditions=(("dir_ret192_bps", ">=", ret_threshold), ("opp_wick_atr", "<=", wick_threshold)),
                )
            )
        for atr_threshold in (1.0, 1.3):
            rules.append(
                v6.RuleSpec(
                    label=f"dir_ret192_bps>={ret_threshold:g}&atr_ratio_14_96<={atr_threshold:g}",
                    conditions=(("dir_ret192_bps", ">=", ret_threshold), ("atr_ratio_14_96", "<=", atr_threshold)),
                )
            )
    return rules


def short_signal_specs() -> list[Any]:
    specs: list[Any] = []
    for ema_fast, ema_slow in ((9, 55), (9, 96), (13, 55), (13, 96), (21, 55), (21, 96), (34, 144)):
        for pullback_buffer in (0.0, 0.005, 0.01, 0.015, 0.02):
            for require_candle in (False, True):
                for htf_threshold in (None, 0.0, 0.5, 1.0, 1.5):
                    specs.append(
                        v6.SignalSpec(
                            style="pullback_reclaim",
                            ema_fast=ema_fast,
                            ema_slow=ema_slow,
                            pullback_buffer=pullback_buffer,
                            side_mode="short",
                            require_candle=require_candle,
                            htf_threshold=htf_threshold,
                        )
                    )
    return specs


def robust_pass(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 50
        and row["profit_factor"] >= 1.2
        and row["avg_trade"] > 0.0
        and row["max_dd"] > -0.35
        and row["is_profit_factor"] >= 1.0
        and row["val_profit_factor"] >= 1.0
        and row["oos_trades"] >= 5
        and row["oos_profit_factor"] >= 1.0
    )


def attach_metrics(trades: list[Any], frame: pd.DataFrame) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    full = v6.metric_with_sides(trades, 1.0, start=start, end=end)
    is_m = v6.metric_with_sides(trades, 1.0, start=start, end=v6.IS_END)
    val_m = v6.metric_with_sides(trades, 1.0, start=v6.IS_END, end=v6.VAL_END)
    oos_m = v6.metric_with_sides(trades, 1.0, start=v6.VAL_END, end=end)
    result = dict(full)
    for prefix, metrics in (("is", is_m), ("val", val_m), ("oos", oos_m)):
        for key, value in metrics.items():
            result[f"{prefix}_{key}"] = value
    return result


def search_short(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    exits = fixed_exit_specs()
    rules = manual_rules()
    specs = short_signal_specs()
    for spec_idx, sig_spec in enumerate(specs, start=1):
        base_signal = v6.build_signal(frame, sig_spec)
        if int(np.count_nonzero(base_signal)) < 20:
            continue
        events = v6.event_features(frame, base_signal, sig_spec)
        for rule in rules:
            keep = np.ones(len(events), dtype=bool) if not rule.conditions else v6.apply_rule(events, rule)
            signal = v6.filtered_signal(base_signal, events, keep)
            signal_count = int(np.count_nonzero(signal))
            if signal_count < 20:
                continue
            for exit_spec in exits:
                trades = v6.simulate_live_orders(frame, signal, sig_spec, exit_spec, label="short_search")
                if len(trades) < 20:
                    continue
                metrics = attach_metrics(trades, frame)
                row: dict[str, Any] = {
                    "signal_label": signal_label(sig_spec),
                    "exit_label": exit_label(exit_spec),
                    "rule_label": rule.label,
                    "rule_conditions": json.dumps(rule.conditions, ensure_ascii=False),
                    "signal_count": signal_count,
                    **{f"signal_{key}": value for key, value in asdict(sig_spec).items()},
                    **{f"exit_{key}": value for key, value in asdict(exit_spec).items()},
                    **metrics,
                }
                row["robust_pass"] = robust_pass(row)
                rows.append(row)
        if spec_idx % 50 == 0:
            print(f"short spec {spec_idx}/{len(specs)} rows={len(rows)}", flush=True)
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    summary = summary.sort_values(["robust_pass", "profit_factor", "total_return", "trades"], ascending=[False, False, False, False]).reset_index(drop=True)
    return summary


def build_long_v61_signal(frame: pd.DataFrame) -> tuple[Any, Any, np.ndarray]:
    sig_spec = v6.SignalSpec(
        style="pullback_reclaim",
        ema_fast=21,
        ema_slow=55,
        pullback_buffer=0.01,
        side_mode="long",
        require_candle=False,
        htf_threshold=0.5,
    )
    exit_spec = v6.ExitSpec(tp_atr=2.5, sl_atr=7.0, trail_atr=0.0, time_exit_bars=36)
    base_signal = v6.build_signal(frame, sig_spec)
    events = v6.event_features(frame, base_signal, sig_spec)
    keep = events["dir_ret192_bps"].to_numpy("float64") >= 788.123
    return sig_spec, exit_spec, v6.filtered_signal(base_signal, events, keep)


def signal_from_candidate(frame: pd.DataFrame, row: pd.Series) -> tuple[Any, Any, np.ndarray]:
    sig_spec = v6.SignalSpec(
        style=str(row["signal_style"]),
        ema_fast=int(row["signal_ema_fast"]),
        ema_slow=int(row["signal_ema_slow"]),
        pullback_buffer=float(row["signal_pullback_buffer"]),
        side_mode=str(row["signal_side_mode"]),
        require_candle=bool(row["signal_require_candle"]),
        htf_threshold=None if pd.isna(row["signal_htf_threshold"]) else float(row["signal_htf_threshold"]),
    )
    exit_spec = v6.ExitSpec(
        tp_atr=float(row["exit_tp_atr"]),
        sl_atr=float(row["exit_sl_atr"]),
        trail_atr=float(row["exit_trail_atr"]),
        time_exit_bars=int(row["exit_time_exit_bars"]),
    )
    base_signal = v6.build_signal(frame, sig_spec)
    events = v6.event_features(frame, base_signal, sig_spec)
    conditions = tuple(tuple(item) for item in json.loads(str(row["rule_conditions"])))
    rule = v6.RuleSpec(label=str(row["rule_label"]), conditions=conditions)
    keep = np.ones(len(events), dtype=bool) if not rule.conditions else v6.apply_rule(events, rule)
    return sig_spec, exit_spec, v6.filtered_signal(base_signal, events, keep)


def simulate_one(frame: pd.DataFrame, sig_i: int, side: int, exit_spec: Any, label: str) -> tuple[Any | None, int]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    entry_i = sig_i + 1
    n = len(frame)
    if side == 0 or entry_i >= n:
        return None, sig_i
    signal_atr = float(atr[sig_i])
    if not np.isfinite(signal_atr) or signal_atr <= 0:
        return None, sig_i

    entry_price = float(open_[entry_i] * (1.0 + side * v6.ENTRY_SLIPPAGE_RATE))
    target_price = entry_price + side * exit_spec.tp_atr * signal_atr
    stop_price = entry_price - side * exit_spec.sl_atr * signal_atr
    active_stop = stop_price
    exit_i = min(n - 1, entry_i + exit_spec.time_exit_bars)
    raw_exit_price = float(open_[exit_i] if exit_i < n else close[-1])
    reason = "time_open"
    peak = entry_price
    trough = entry_price
    for bar_i in range(entry_i, min(n, entry_i + exit_spec.time_exit_bars + 1)):
        if v6.crossed_stop(float(open_[bar_i]), active_stop, side):
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "stop_gap_open"
            break
        if v6.crossed_target(float(open_[bar_i]), target_price, side):
            exit_i = bar_i
            raw_exit_price = float(target_price)
            reason = "target_gap_or_open"
            break
        if bar_i == entry_i + exit_spec.time_exit_bars:
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "time_open"
            break
        stop_hit = v6.touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side)
        target_hit = v6.touched_target(float(high[bar_i]), float(low[bar_i]), target_price, side)
        if stop_hit and target_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "both_hit_stop_first"
            break
        if stop_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "stop_market"
            break
        if target_hit:
            exit_i = bar_i
            raw_exit_price = float(target_price)
            reason = "target"
            break
        if side > 0:
            peak = max(peak, float(high[bar_i]))
            if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                active_stop = max(active_stop, peak - exit_spec.trail_atr * float(atr[bar_i]))
        else:
            trough = min(trough, float(low[bar_i]))
            if exit_spec.trail_atr > 0 and np.isfinite(atr[bar_i]):
                active_stop = min(active_stop, trough + exit_spec.trail_atr * float(atr[bar_i]))

    path_high = high[entry_i : exit_i + 1]
    path_low = low[entry_i : exit_i + 1]
    if side > 0:
        mae = float(np.nanmin(path_low / entry_price - 1.0))
        mfe = float(np.nanmax(path_high / entry_price - 1.0))
    else:
        mae = float(np.nanmin(side * (path_high / entry_price - 1.0)))
        mfe = float(np.nanmax(side * (path_low / entry_price - 1.0)))
    exit_price = v6.exit_price_with_cost(raw_exit_price, side)
    gross = side * (exit_price / entry_price - 1.0)
    fee_cost = v6.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
    net = gross - fee_cost
    return (
        v6.Trade(
            config=label,
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=side,
            entry_price=entry_price,
            exit_price=exit_price,
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=float(net),
            mae_1x=float(mae - v6.FEE_RATE_PER_FILL),
            mfe_1x=float(mfe),
        ),
        exit_i,
    )


def simulate_combo(frame: pd.DataFrame, long_signal: np.ndarray, long_exit: Any, short_signal: np.ndarray, short_exit: Any, label: str) -> list[Any]:
    events: list[tuple[int, str, int, Any]] = []
    events.extend((int(i), "long", int(long_signal[i]), long_exit) for i in np.flatnonzero(long_signal))
    events.extend((int(i), "short", int(short_signal[i]), short_exit) for i in np.flatnonzero(short_signal))
    events.sort(key=lambda item: (item[0], 0 if item[1] == "long" else 1))
    blocked_until = -1
    trades: list[Any] = []
    for sig_i, source, side, exit_spec in events:
        entry_i = sig_i + 1
        if entry_i <= blocked_until:
            continue
        trade, exit_i = simulate_one(frame, sig_i, side, exit_spec, f"{label}_{source}")
        if trade is None:
            continue
        trades.append(trade)
        blocked_until = exit_i
    return trades


def combo_rows(frame: pd.DataFrame, short_summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    long_sig_spec, long_exit, long_signal = build_long_v61_signal(frame)
    long_trades = v6.simulate_live_orders(frame, long_signal, long_sig_spec, long_exit, label="V6.1_long")
    base_returns = np.array([trade.net_ret_1x * LEVERAGE for trade in long_trades], dtype="float64")
    rows = [{"label": "V6.1_long_only", "short_rank": -1, **equity_metrics(base_returns), "short_label": ""}]
    trade_rows: list[dict[str, Any]] = []
    for i, trade in enumerate(long_trades, start=1):
        trade_rows.append({"combo_label": "V6.1_long_only", "trade_no": i, **trade.__dict__} if hasattr(trade, "__dict__") else {
            "combo_label": "V6.1_long_only",
            "trade_no": i,
            "signal_ts": trade.signal_ts,
            "entry_ts": trade.entry_ts,
            "exit_ts": trade.exit_ts,
            "side": trade.side,
            "reason": trade.reason,
            "bars_held": trade.bars_held,
            "net_ret_1x": trade.net_ret_1x,
            "net_ret_3x": trade.net_ret_1x * LEVERAGE,
            "config": trade.config,
        })

    candidates = short_summary.loc[short_summary["trades"].ge(30)].head(12).copy()
    for rank, row in enumerate(candidates.to_dict(orient="records"), start=1):
        row_series = pd.Series(row)
        _short_sig_spec, short_exit, short_signal = signal_from_candidate(frame, row_series)
        combo_label = f"combo_short_rank{rank}"
        trades = simulate_combo(frame, long_signal, long_exit, short_signal, short_exit, combo_label)
        returns = np.array([trade.net_ret_1x * LEVERAGE for trade in trades], dtype="float64")
        rows.append(
            {
                "label": combo_label,
                "short_rank": rank,
                "short_label": f"{row['signal_label']}__{row['exit_label']}__{row['rule_label']}",
                "short_pf": row["profit_factor"],
                "short_trades": row["trades"],
                **equity_metrics(returns),
            }
        )
        for i, trade in enumerate(trades, start=1):
            trade_rows.append(
                {
                    "combo_label": combo_label,
                    "trade_no": i,
                    "signal_ts": trade.signal_ts,
                    "entry_ts": trade.entry_ts,
                    "exit_ts": trade.exit_ts,
                    "side": trade.side,
                    "reason": trade.reason,
                    "bars_held": trade.bars_held,
                    "net_ret_1x": trade.net_ret_1x,
                    "net_ret_3x": trade.net_ret_1x * LEVERAGE,
                    "config": trade.config,
                }
            )
    return pd.DataFrame(rows).sort_values(["total_return", "max_dd"], ascending=[False, False]), pd.DataFrame(trade_rows)


def render_markdown(short_summary: pd.DataFrame, combo_summary: pd.DataFrame) -> str:
    short_top = short_summary.head(15)
    combo_top = combo_summary.head(15)
    base = combo_summary.loc[combo_summary["label"].eq("V6.1_long_only")].iloc[0]
    best_combo = combo_top.iloc[0]
    lines = [
        "# HYPE-5M-PBTR-V6.1 short combo search 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告尝试搜索一个 short-only executable bracket 策略，并与 `HYPE-5M-PBTR-V6.1` long-only 策略组合。组合回放严格单仓：任意时刻只允许一笔持仓，持仓期间另一边信号跳过。",
        "",
        "## Short-Only Top",
        "",
        "| rank | signal | exit | rule | trades | total | PF | avg | win | DD | IS PF | VAL PF | OOS trades | OOS PF | pass |",
        "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for idx, row in enumerate(short_top.to_dict(orient="records"), start=1):
        lines.append(
            f"| `{idx}` | `{row['signal_label']}` | `{row['exit_label']}` | `{row['rule_label']}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['avg_trade']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_pct(float(row['max_dd']))}` | `{fmt_num(float(row['is_profit_factor']))}` | "
            f"`{fmt_num(float(row['val_profit_factor']))}` | `{int(row['oos_trades'])}` | `{fmt_num(float(row['oos_profit_factor']))}` | `{bool(row['robust_pass'])}` |"
        )
    lines.extend(["", "## Single-Position Combo Top", ""])
    lines.append("| combo | short rank | trades | total | max DD | avg | win | PF | worst | best | short label |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |")
    for row in combo_top.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['short_rank'])}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_pct(float(row['worst_trade']))}` | `{fmt_pct(float(row['best_trade']))}` | `{row.get('short_label', '')}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"V6.1 long-only 基线为总收益 `{fmt_pct(float(base['total_return']))}`、最大回撤 `{fmt_pct(float(base['max_dd']))}`。本轮组合最强为 `{best_combo['label']}`，总收益 `{fmt_pct(float(best_combo['total_return']))}`、最大回撤 `{fmt_pct(float(best_combo['max_dd']))}`。",
            "",
            "如果 short-only 没有通过 robust gate，则组合改善也只能视为探索线索，不能提升为 V6.x。尤其要关注 OOS 笔数和 VAL/OOS PF；做空策略很容易在 HYPE 的少数下跌片段中过拟合。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- short summary CSV：`{SHORT_SUMMARY_PATH}`",
            f"- combo summary CSV：`{COMBO_SUMMARY_PATH}`",
            f"- combo trades CSV：`{COMBO_TRADES_PATH}`",
            f"- JSON：`{REPORT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_search_features(v6.add_features(raw))
    short_summary = search_short(frame)
    combo_summary, combo_trades = combo_rows(frame, short_summary)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    short_summary.to_csv(SHORT_SUMMARY_PATH, index=False)
    combo_summary.to_csv(COMBO_SUMMARY_PATH, index=False)
    combo_trades.to_csv(COMBO_TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(short_summary, combo_summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.1-short-combo-search",
                "short_top": short_summary.head(30).to_dict(orient="records"),
                "combo_top": combo_summary.head(30).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "short_summary": str(SHORT_SUMMARY_PATH),
                    "combo_summary": str(COMBO_SUMMARY_PATH),
                    "combo_trades": str(COMBO_TRADES_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print("short top")
    print(short_summary.head(20).to_string(index=False))
    print("combo top")
    print(combo_summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
