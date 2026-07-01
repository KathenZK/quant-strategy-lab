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


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v621 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v6_2_1_full_ablation.py", "hype_pbtr_v621_dynamic_base")
v62 = v621.v62
v6 = v62.v6

RUN_DATE = "2026-06-30"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_summary_{RUN_DATE}.csv"
SLICE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_slices_{RUN_DATE}.csv"
SIDE_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_sides_{RUN_DATE}.csv"
MONTHLY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_monthly_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_trades_{RUN_DATE}.csv"
JSON_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v6-2-1_dynamic_atr_bracket_{RUN_DATE}.json"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v6-2-1-dynamic-atr-bracket-{RUN_DATE}.md"

DYNAMIC_MODES = (
    "entry_anchor_dynamic_atr",
    "entry_anchor_no_widen_stop",
    "close_reset_dynamic_atr",
    "close_reset_no_widen_stop",
)
TP_SCALES = (0.75, 1.0, 1.25, 1.5)
SL_SCALES = (0.75, 1.0, 1.25)


def fmt_pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def fmt_num(value: float, digits: int = 3) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def reason_counts(trades: list[Any]) -> str:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.reason] = counts.get(trade.reason, 0) + 1
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def update_dynamic_levels(
    *,
    mode: str,
    side: int,
    entry_price: float,
    close_price: float,
    atr_value: float,
    active_stop: float,
    tp_atr: float,
    sl_atr: float,
) -> tuple[float, float, bool]:
    if mode.startswith("entry_anchor"):
        anchor = entry_price
    elif mode.startswith("close_reset"):
        anchor = close_price
    else:
        raise ValueError(mode)

    target = anchor + side * tp_atr * atr_value
    proposed_stop = anchor - side * sl_atr * atr_value
    proposed_widened_stop = bool(proposed_stop < active_stop if side > 0 else proposed_stop > active_stop)
    if mode.endswith("no_widen_stop"):
        stop = max(active_stop, proposed_stop) if side > 0 else min(active_stop, proposed_stop)
        actual_widened_stop = False
    else:
        stop = proposed_stop
        actual_widened_stop = proposed_widened_stop
    return float(target), float(stop), actual_widened_stop


def simulate_one(
    frame: pd.DataFrame,
    sig_i: int,
    side: int,
    leg: Any,
    label: str,
    *,
    mode: str,
    tp_scale: float,
    sl_scale: float,
) -> tuple[Any | None, int, dict[str, Any] | None]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    entry_i = sig_i + 1
    n = len(frame)
    if side == 0 or entry_i >= n:
        return None, sig_i, None
    signal_atr = float(atr[sig_i])
    if not np.isfinite(signal_atr) or signal_atr <= 0:
        return None, sig_i, None

    tp_atr = float(leg.tp_atr) * tp_scale
    sl_atr = float(leg.sl_atr) * sl_scale
    entry_price = float(open_[entry_i] * (1.0 + side * v6.ENTRY_SLIPPAGE_RATE))
    active_target = entry_price + side * tp_atr * signal_atr
    active_stop = entry_price - side * sl_atr * signal_atr
    exit_i = min(n - 1, entry_i + leg.time_exit_bars)
    raw_exit_price = float(open_[exit_i])
    reason = "time_open"
    amend_count = 0
    stop_widen_count = 0
    target_widen_count = 0
    both_hit_count = 0

    for bar_i in range(entry_i, min(n, entry_i + leg.time_exit_bars + 1)):
        if v6.crossed_stop(float(open_[bar_i]), active_stop, side):
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "stop_gap_open"
            break
        if v6.crossed_target(float(open_[bar_i]), active_target, side):
            exit_i = bar_i
            raw_exit_price = float(active_target)
            reason = "target_gap_or_open"
            break
        if bar_i == entry_i + leg.time_exit_bars:
            exit_i = bar_i
            raw_exit_price = float(open_[bar_i])
            reason = "time_open"
            break

        stop_hit = v6.touched_stop(float(high[bar_i]), float(low[bar_i]), active_stop, side)
        target_hit = v6.touched_target(float(high[bar_i]), float(low[bar_i]), active_target, side)
        if stop_hit and target_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "both_hit_stop_first"
            both_hit_count += 1
            break
        if stop_hit:
            exit_i = bar_i
            raw_exit_price = float(active_stop)
            reason = "stop_market"
            break
        if target_hit:
            exit_i = bar_i
            raw_exit_price = float(active_target)
            reason = "target"
            break

        # Live timing: after bar_i closes, amend the next bar's orders using only closed-bar ATR.
        if bar_i + 1 < n and np.isfinite(atr[bar_i]) and atr[bar_i] > 0:
            old_target = active_target
            active_target, active_stop, widened = update_dynamic_levels(
                mode=mode,
                side=side,
                entry_price=entry_price,
                close_price=float(close[bar_i]),
                atr_value=float(atr[bar_i]),
                active_stop=active_stop,
                tp_atr=tp_atr,
                sl_atr=sl_atr,
            )
            amend_count += 1
            stop_widen_count += int(widened)
            target_widen_count += int(
                (active_target > old_target) if side > 0 else (active_target < old_target)
            )

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
    trade = v6.Trade(
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
    )
    return trade, exit_i, {
        "mode": mode,
        "label": label,
        "source": "long" if side > 0 else "short",
        "tp_scale": tp_scale,
        "sl_scale": sl_scale,
        "signal_ts": trade.signal_ts,
        "entry_ts": trade.entry_ts,
        "exit_ts": trade.exit_ts,
        "side": side,
        "reason": reason,
        "bars_held": trade.bars_held,
        "net_ret_1x": trade.net_ret_1x,
        "net_ret_3x": trade.net_ret_1x * v621.BASELINE.leverage,
        "mae_1x": trade.mae_1x,
        "mfe_1x": trade.mfe_1x,
        "amend_count": amend_count,
        "stop_widen_count": stop_widen_count,
        "target_widen_count": target_widen_count,
        "both_hit_count": both_hit_count,
    }


def simulate_combo(
    frame: pd.DataFrame,
    long_signal: np.ndarray,
    short_signal: np.ndarray,
    *,
    label: str,
    mode: str,
    tp_scale: float,
    sl_scale: float,
) -> tuple[list[Any], dict[str, int], list[dict[str, Any]]]:
    priority_order = {"long": 0, "short": 1}
    events: list[tuple[int, str, int, Any]] = []
    events.extend((int(i), "long", int(long_signal[i]), v621.BASELINE.long) for i in np.flatnonzero(long_signal))
    events.extend((int(i), "short", int(short_signal[i]), v621.BASELINE.short) for i in np.flatnonzero(short_signal))
    events.sort(key=lambda item: (item[0], priority_order[item[1]]))
    long_idx = set(int(i) for i in np.flatnonzero(long_signal))
    short_idx = set(int(i) for i in np.flatnonzero(short_signal))
    stats = {
        "long_signal_count": len(long_idx),
        "short_signal_count": len(short_idx),
        "same_bar_signal_count": len(long_idx & short_idx),
        "accepted_long": 0,
        "accepted_short": 0,
        "blocked_long": 0,
        "blocked_short": 0,
    }
    blocked_until = -1
    trades: list[Any] = []
    trade_rows: list[dict[str, Any]] = []
    for sig_i, source, side, leg in events:
        entry_i = sig_i + 1
        if entry_i <= blocked_until:
            stats[f"blocked_{source}"] += 1
            continue
        trade, exit_i, trade_row = simulate_one(
            frame,
            sig_i,
            side,
            leg,
            label,
            mode=mode,
            tp_scale=tp_scale,
            sl_scale=sl_scale,
        )
        if trade is None or trade_row is None:
            continue
        trades.append(trade)
        trade_rows.append(trade_row)
        stats[f"accepted_{source}"] += 1
        blocked_until = exit_i
    return trades, stats, trade_rows


def metrics_for_trades(
    trades: list[Any],
    leverage: float,
    *,
    start: pd.Timestamp | None = None,
    end: pd.Timestamp | None = None,
) -> dict[str, float]:
    selected = trades
    if start is not None:
        selected = [trade for trade in selected if trade.entry_ts >= start]
    if end is not None:
        selected = [trade for trade in selected if trade.entry_ts < end]
    returns = np.array([trade.net_ret_1x * leverage for trade in selected], dtype="float64")
    return v62.equity_metrics(returns)


def side_metrics(trades: list[Any], side: int) -> dict[str, float]:
    return metrics_for_trades([trade for trade in trades if trade.side == side], v621.BASELINE.leverage)


def validation_slices(frame: pd.DataFrame) -> list[dict[str, Any]]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return [
        {"name": "is", "start": start, "end": v6.IS_END},
        {"name": "val", "start": v6.IS_END, "end": v6.VAL_END},
        {"name": "oos", "start": v6.VAL_END, "end": end},
    ]


def robust_pass(row: dict[str, Any]) -> bool:
    return bool(
        row["trades"] >= 150
        and row["profit_factor"] >= 1.3
        and row["avg_trade"] > 0.0
        and row["max_dd"] > -0.35
        and row["is_profit_factor"] >= 1.1
        and row["val_profit_factor"] >= 1.0
        and row["oos_trades"] >= 10
        and row["oos_profit_factor"] >= 1.0
        and row["short_trades"] >= 30
        and row["short_profit_factor"] >= 1.1
        and row["short_oos_trades"] >= 5
        and row["worst_trade"] > -0.25
    )


def evaluate_variant(
    frame: pd.DataFrame,
    long_signal: np.ndarray,
    short_signal: np.ndarray,
    *,
    label: str,
    mode: str,
    tp_scale: float,
    sl_scale: float,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    trades, exec_stats, trade_rows = simulate_combo(
        frame,
        long_signal,
        short_signal,
        label=label,
        mode=mode,
        tp_scale=tp_scale,
        sl_scale=sl_scale,
    )
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    trade_frame = pd.DataFrame(trade_rows)
    row: dict[str, Any] = {
        "label": label,
        "mode": mode,
        "tp_scale": tp_scale,
        "sl_scale": sl_scale,
        "reason_counts": reason_counts(trades),
        "median_bars_held": float(trade_frame["bars_held"].median()) if len(trade_frame) else 0.0,
        "median_amend_count": float(trade_frame["amend_count"].median()) if len(trade_frame) else 0.0,
        "avg_amend_count": float(trade_frame["amend_count"].mean()) if len(trade_frame) else 0.0,
        "stop_widen_trades": int((trade_frame["stop_widen_count"] > 0).sum()) if len(trade_frame) else 0,
        "target_widen_trades": int((trade_frame["target_widen_count"] > 0).sum()) if len(trade_frame) else 0,
        "both_hit_count": int((trade_frame["both_hit_count"] > 0).sum()) if len(trade_frame) else 0,
        **exec_stats,
        **metrics_for_trades(trades, v621.BASELINE.leverage, start=start, end=end),
    }
    for item in validation_slices(frame):
        metrics = metrics_for_trades(trades, v621.BASELINE.leverage, start=item["start"], end=item["end"])
        for key, value in metrics.items():
            row[f"{item['name']}_{key}"] = value
    long_metrics = side_metrics(trades, 1)
    short_metrics = side_metrics(trades, -1)
    for key, value in long_metrics.items():
        row[f"long_{key}"] = value
    for key, value in short_metrics.items():
        row[f"short_{key}"] = value
    short_oos = metrics_for_trades(
        [trade for trade in trades if trade.side < 0],
        v621.BASELINE.leverage,
        start=v6.VAL_END,
        end=end,
    )
    row["short_oos_trades"] = short_oos["trades"]
    row["short_oos_profit_factor"] = short_oos["profit_factor"]
    row["robust_pass"] = robust_pass(row)

    slice_rows = []
    for item in validation_slices(frame):
        slice_rows.append(
            {
                "label": label,
                "mode": mode,
                "slice": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics_for_trades(trades, v621.BASELINE.leverage, start=item["start"], end=item["end"]),
            }
        )
    side_rows = []
    for side, side_label in ((1, "long"), (-1, "short")):
        side_trades = [trade for trade in trades if trade.side == side]
        side_rows.append({"label": label, "mode": mode, "side": side_label, **metrics_for_trades(side_trades, v621.BASELINE.leverage)})
    monthly_rows = []
    for item in v6.month_slices(frame):
        monthly_rows.append(
            {
                "label": label,
                "mode": mode,
                "month": item["name"],
                "slice_start": item["start"],
                "slice_end": item["end"],
                **metrics_for_trades(trades, v621.BASELINE.leverage, start=item["start"], end=item["end"]),
            }
        )
    return row, slice_rows, side_rows, monthly_rows, trade_rows


def build_variants() -> list[dict[str, Any]]:
    variants = [
        {
            "label": "baseline_fixed_entry_atr",
            "mode": "entry_anchor_dynamic_atr",
            "tp_scale": 1.0,
            "sl_scale": 1.0,
            "baseline": True,
        }
    ]
    for mode in DYNAMIC_MODES:
        for tp_scale in TP_SCALES:
            for sl_scale in SL_SCALES:
                label = f"{mode}__tp{str(tp_scale).replace('.', 'p')}__sl{str(sl_scale).replace('.', 'p')}"
                variants.append({"label": label, "mode": mode, "tp_scale": tp_scale, "sl_scale": sl_scale, "baseline": False})
    return variants


def table(rows: pd.DataFrame, limit: int = 15) -> list[str]:
    lines = [
        "| 变体 | mode | TP scale | SL scale | trades | total | PF | avg | win | DD | OOS PF | short PF | amend | stop widen | pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['mode']}` | `{float(row['tp_scale']):.2f}` | `{float(row['sl_scale']):.2f}` | "
            f"`{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_pct(float(row['avg_trade']))}` | `{fmt_pct(float(row['win_rate']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_num(float(row['oos_profit_factor']))}` | `{fmt_num(float(row['short_profit_factor']))}` | "
            f"`{fmt_num(float(row['median_amend_count']), 1)}` | `{int(row['stop_widen_trades'])}` | `{bool(row['robust_pass'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, slices: pd.DataFrame, sides: pd.DataFrame, monthly: pd.DataFrame) -> str:
    baseline = summary.loc[summary["label"].eq("baseline_fixed_entry_atr")].iloc[0]
    dynamic = summary.loc[~summary["label"].eq("baseline_fixed_entry_atr")].copy()
    dynamic["delta_total_return"] = dynamic["total_return"] - float(baseline["total_return"])
    dynamic["delta_pf"] = dynamic["profit_factor"] - float(baseline["profit_factor"])
    dynamic["delta_dd"] = dynamic["max_dd"] - float(baseline["max_dd"])
    top_return = dynamic.sort_values(["total_return", "profit_factor"], ascending=False)
    top_pf = dynamic.sort_values(["profit_factor", "total_return"], ascending=False)
    robust = dynamic.loc[dynamic["robust_pass"]].sort_values(["total_return", "profit_factor"], ascending=False)
    same_scale = dynamic.loc[dynamic["tp_scale"].eq(1.0) & dynamic["sl_scale"].eq(1.0)].sort_values("mode")
    best = top_return.iloc[0]
    best_monthly = monthly.loc[monthly["label"].eq(best["label"])]
    worst_month = best_monthly.sort_values("total_return").iloc[0]
    best_month = best_monthly.sort_values("total_return", ascending=False).iloc[0]
    better_than_baseline = dynamic.loc[
        (dynamic["total_return"] > float(baseline["total_return"]))
        & (dynamic["profit_factor"] >= float(baseline["profit_factor"]))
        & (dynamic["max_dd"] >= float(baseline["max_dd"]) - 0.02)
    ]
    conclusion = (
        "本轮未找到收益、PF 和回撤同时稳健优于固定 bracket baseline 的动态 ATR 版本。"
        if better_than_baseline.empty
        else f"本轮存在 `{len(better_than_baseline)}` 个动态 ATR 版本在收益/PF/回撤近似约束下优于 baseline，但仍需单独 live-order 审计。"
    )
    lines = [
        "# HYPE-5M-PBTR-V6.2.1 动态 ATR TP/SL 回测 2026-06-30",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "用户问题：V6.2.1 是否是固定止盈止损；如果改成根据 ATR 波动率动态调整 TP/SL 会怎样。",
        "",
        "回答：V6.2.1 当前是入场即固定 bracket。TP/SL 距离用信号 K 的 ATR14 算出后，在持仓期间不再随 ATR 改变。本报告测试四种 live-executable 动态 ATR bracket：每根 K 先用当时已挂的 bracket 判断是否成交，若没有成交，才在该 K 收盘后用已收盘 ATR 更新下一根 K 可用的 TP/SL。",
        "",
        "## 动态定义",
        "",
        "- `entry_anchor_dynamic_atr`：TP/SL 始终锚定入场价，但距离使用最新已收盘 ATR，可放宽止损。",
        "- `entry_anchor_no_widen_stop`：TP 锚定入场价并随 ATR 变；SL 锚定入场价但只能变紧，不能放宽。",
        "- `close_reset_dynamic_atr`：每根收盘后围绕该根 close 用最新 ATR 重设下一根的 TP/SL，可放宽止损。",
        "- `close_reset_no_widen_stop`：TP 围绕 close 重设，SL 只允许向有利方向移动。",
        "",
        "表格中的 `stop widen` 表示实际发生过止损放宽的交易数；`no_widen_stop` 模式应为 `0`。",
        "",
        "每种模式扫描 `TP scale = 0.75/1.0/1.25/1.5`、`SL scale = 0.75/1.0/1.25`。scale 作用于 V6.2.1 原始参数：long `TP2.5/SL7`，short `TP1.5/SL2`。",
        "",
        "## Baseline",
        "",
        "| label | trades | total | PF | avg | win | DD | reasons |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        (
            f"| `{baseline['label']}` | `{int(baseline['trades'])}` | `{fmt_pct(float(baseline['total_return']))}` | "
            f"`{fmt_num(float(baseline['profit_factor']))}` | `{fmt_pct(float(baseline['avg_trade']))}` | "
            f"`{fmt_pct(float(baseline['win_rate']))}` | `{fmt_pct(float(baseline['max_dd']))}` | `{baseline['reason_counts']}` |"
        ),
        "",
        "## 同参数动态对照",
        "",
        *table(same_scale, limit=10),
        "",
        "## Top By Total Return",
        "",
        *table(top_return, limit=15),
        "",
        "## Top By PF",
        "",
        *table(top_pf, limit=15),
        "",
        "## Robust Pass 动态版本",
        "",
    ]
    if robust.empty:
        lines.append("无。")
    else:
        lines.extend(table(robust, limit=20))
    lines.extend(
        [
            "",
            "## 最佳收益版本月份",
            "",
            f"最佳收益版本：`{best['label']}`。最差月份 `{worst_month['month']}`：`{fmt_pct(float(worst_month['total_return']))}` / PF `{fmt_num(float(worst_month['profit_factor']))}`；最好月份 `{best_month['month']}`：`{fmt_pct(float(best_month['total_return']))}` / PF `{fmt_num(float(best_month['profit_factor']))}`。",
            "",
            "## 结论",
            "",
            conclusion,
            "",
            "动态 ATR bracket 没有发现未来函数：订单更新只发生在上一根 K 收盘之后，下一根 K 才使用新 TP/SL。但动态重挂会显著增加真实订单维护复杂度，尤其是允许 stop widening 的模式会把风险边界往外放，实盘上比固定 bracket 更难审计。除非后续有明确优于 baseline 的稳健结果，否则 `HYPE-5M-PBTR-V6.2.1` 默认仍应保留固定入场 ATR bracket。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- summary：`{SUMMARY_PATH}`",
            f"- slices：`{SLICE_PATH}`",
            f"- sides：`{SIDE_PATH}`",
            f"- monthly：`{MONTHLY_PATH}`",
            f"- trades：`{TRADES_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v6.load_closed_frame()
    frame = v6.add_search_features(v6.add_features(raw))
    long_signal, _long_raw, _long_filtered = v62.build_leg_signal(frame, v621.BASELINE.long)
    short_signal, _short_raw, _short_filtered = v62.build_leg_signal(frame, v621.BASELINE.short)

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    side_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    trade_rows: list[dict[str, Any]] = []

    # Baseline uses the original fixed bracket simulator for exact current-data comparison.
    baseline_spec = {
        "label": "baseline_fixed_entry_atr",
        "family": "baseline",
        "parameter": "baseline",
        "value": "fixed_entry_atr",
        "cfg": v621.BASELINE,
    }
    base_row, base_slices, base_sides, base_monthly, base_trades = v62.evaluate_variant(frame, baseline_spec)
    base_row = {
        **base_row,
        "mode": "fixed_entry_atr",
        "tp_scale": 1.0,
        "sl_scale": 1.0,
        "median_bars_held": float(np.median([trade.bars_held for trade in base_trades])) if base_trades else 0.0,
        "median_amend_count": 0.0,
        "avg_amend_count": 0.0,
        "stop_widen_trades": 0,
        "target_widen_trades": 0,
        "both_hit_count": int(sum(1 for trade in base_trades if trade.reason == "both_hit_stop_first")),
    }
    summary_rows.append(base_row)
    for item in base_slices:
        slice_rows.append({**item, "mode": "fixed_entry_atr"})
    for item in base_sides:
        side_rows.append({**item, "mode": "fixed_entry_atr"})
    for item in base_monthly:
        monthly_rows.append({**item, "mode": "fixed_entry_atr"})
    for trade in base_trades:
        trade_rows.append(
            {
                "label": "baseline_fixed_entry_atr",
                "mode": "fixed_entry_atr",
                "source": "long" if trade.side > 0 else "short",
                "tp_scale": 1.0,
                "sl_scale": 1.0,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "reason": trade.reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "net_ret_3x": trade.net_ret_1x * v621.BASELINE.leverage,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "amend_count": 0,
                "stop_widen_count": 0,
                "target_widen_count": 0,
                "both_hit_count": 0,
            }
        )

    for spec in build_variants()[1:]:
        row, slices, sides, monthly, trades = evaluate_variant(
            frame,
            long_signal,
            short_signal,
            label=str(spec["label"]),
            mode=str(spec["mode"]),
            tp_scale=float(spec["tp_scale"]),
            sl_scale=float(spec["sl_scale"]),
        )
        summary_rows.append(row)
        slice_rows.extend(slices)
        side_rows.extend(sides)
        monthly_rows.extend(monthly)
        trade_rows.extend(trades)

    summary = pd.DataFrame(summary_rows)
    baseline_return = float(summary.loc[summary["label"].eq("baseline_fixed_entry_atr"), "total_return"].iloc[0])
    summary["delta_total_return"] = summary["total_return"] - baseline_return
    summary = summary.sort_values(["total_return", "profit_factor", "max_dd"], ascending=[False, False, False]).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    sides = pd.DataFrame(side_rows)
    monthly = pd.DataFrame(monthly_rows)
    trades = pd.DataFrame(trade_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    slices.to_csv(SLICE_PATH, index=False)
    sides.to_csv(SIDE_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, slices, sides, monthly), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V6.2.1",
                "run_date": RUN_DATE,
                "baseline": asdict(v621.BASELINE),
                "dynamic_modes": list(DYNAMIC_MODES),
                "tp_scales": list(TP_SCALES),
                "sl_scales": list(SL_SCALES),
                "summary_top": summary.head(30).to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "slices": str(SLICE_PATH),
                    "sides": str(SIDE_PATH),
                    "monthly": str(MONTHLY_PATH),
                    "trades": str(TRADES_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
