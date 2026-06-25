from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SOURCE_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v3-3_full_ablation.py")

REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop_summary.csv")
TRADES_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop_trades.csv")
ROLLING_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop_rolling.csv")
WEEKLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop_weekly.csv")
MONTHLY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_staged_tp_stop_monthly.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-staged-tp-stop-2026-06-25.md"
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


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def first_event_offset(mask: np.ndarray) -> int | None:
    indices = np.flatnonzero(mask)
    if len(indices) == 0:
        return None
    return int(indices[0])


def simulate_staged_tp_stop(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    label: str,
    tp_atr: float,
    tp_disabled_bars: int,
    stop_disabled_bars: int,
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
        atr_signal = float(atr[sig_i])
        if not np.isfinite(atr_signal) or atr_signal <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * atr_signal
        target = entry_price + direction * tp_atr * atr_signal
        end_i = n - 1
        sl = slice(entry_i, end_i + 1)
        high_seg = high[sl]
        low_seg = low[sl]
        close_seg = close[sl]
        atr_seg = atr[sl]

        if direction > 0:
            previous_peak = np.r_[entry_price, np.maximum.accumulate(high_seg)[:-1]]
            stop_levels = np.maximum(np.full(len(high_seg), initial_stop), previous_peak - cfg.trail_atr * atr_seg)
            stop_hit = low_seg <= stop_levels
            target_hit = high_seg >= target
        else:
            previous_trough = np.r_[entry_price, np.minimum.accumulate(low_seg)[:-1]]
            stop_levels = np.minimum(np.full(len(low_seg), initial_stop), previous_trough + cfg.trail_atr * atr_seg)
            stop_hit = high_seg >= stop_levels
            target_hit = low_seg <= target

        if stop_disabled_bars > 0:
            stop_hit[:stop_disabled_bars] = False
        if tp_disabled_bars > 0:
            target_hit[:tp_disabled_bars] = False

        offset = first_event_offset(stop_hit | target_hit)
        reason = "time"
        if offset is None:
            offset = len(close_seg) - 1
            raw_exit_price = float(close_seg[offset])
        elif stop_hit[offset]:
            reason = "stop"
            raw_exit_price = float(stop_levels[offset])
        else:
            reason = "target"
            raw_exit_price = float(target)

        path_high = high_seg[: offset + 1]
        path_low = low_seg[: offset + 1]
        if direction > 0:
            mae = float(np.nanmin(path_low / entry_price - 1.0))
            mfe = float(np.nanmax(path_high / entry_price - 1.0))
        else:
            mae = float(np.nanmin(direction * (path_high / entry_price - 1.0)))
            mfe = float(np.nanmax(direction * (path_low / entry_price - 1.0)))

        exit_i = entry_i + offset
        exit_price = float(raw_exit_price * (1.0 - direction * v33.EXIT_SLIPPAGE_RATE))
        gross = direction * (exit_price / entry_price - 1.0)
        fee_cost = v33.FEE_RATE_PER_FILL * (1.0 + exit_price / entry_price)
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
            mae_1x=float(mae - v33.FEE_RATE_PER_FILL),
            mfe_1x=float(mfe),
        )
        trades.append(trade)
        diag_rows.append(
            {
                "label": label,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "target": target,
                "stop_at_exit": float(stop_levels[offset]) if reason == "stop" else np.nan,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "tp_atr": tp_atr,
                "tp_disabled_bars": tp_disabled_bars,
                "stop_disabled_bars": stop_disabled_bars,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag_rows)


def summarize(label: str, signal_count: int, trades: list[Any], frame: pd.DataFrame, extra: dict[str, Any]) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {
        "label": label,
        "signal_count": signal_count,
        **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end),
        **extra,
    }


def add_prefixed_slices(strategy: str, frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rolling, weekly, monthly = v33.baseline_time_slices(frame, trades)
    rolling.insert(0, "strategy", strategy)
    weekly.insert(0, "strategy", strategy)
    monthly.insert(0, "strategy", strategy)
    return rolling, weekly, monthly


def render_markdown(summary: pd.DataFrame, trades: pd.DataFrame, rolling: pd.DataFrame) -> str:
    rows = {row["label"]: row for row in summary.to_dict(orient="records")}
    reason_counts = trades.groupby(["label", "reason"]).size().reset_index(name="count")

    def summary_line(label: str, display: str) -> str:
        row = rows[label]
        counts = reason_counts.loc[reason_counts["label"].eq(label)].set_index("reason")["count"].to_dict()
        target_count = int(counts.get("target", 0))
        stop_count = int(counts.get("stop", 0))
        time_count = int(counts.get("time", 0))
        return (
            f"| `{display}` | `{int(row['signal_count'])}` | `{int(row['trades'])}` | "
            f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['total_return']))}` | "
            f"`{pct(float(row['win_rate']))}` | `{num(float(row['payoff_ratio']))}` | "
            f"`{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` | "
            f"`{target_count}` | `{stop_count}` | `{time_count}` |"
        )

    best = summary.sort_values(["profit_factor", "total_return"], ascending=False).iloc[0]
    best_label = str(best["label"])
    best_rolling = rolling.loc[rolling["strategy"].eq(best_label)].copy()
    lines = [
        "# HYPE-5M-PBTR-V3.3 分阶段止盈止损回测 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告按 V3.3 旧回测口径测试一个分阶段退出：固定 `1ATR` 止盈先启用，原 V3.3 trailing stop 后启用。入场、EMA、pullback、`stop_atr=0.5`、`trail_atr=0.75` 均保持 V3.3 不变。",
        "",
        "为避免“第六根开始”歧义，测试两个相邻口径：",
        "",
        "- `tp_bar6_stop_bar10`：第 6 根持仓 K 本身可触发 `1ATR` 止盈；stop 仍按 V3.3 旧口径第 10 根起触发。",
        "- `tp_bar7_stop_bar10`：持满 6 根后，第 7 根起可触发 `1ATR` 止盈；stop 仍按 V3.3 旧口径第 10 根起触发。",
        "",
        "## 结果对比",
        "",
        "| 口径 | 信号数 | 交易数 | 年化 | 累计收益 | 胜率 | payoff | PF | 最大回撤 | target | stop | time |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        summary_line("v33_baseline", "V3.3 baseline"),
        summary_line("tp_bar6_stop_bar10", "TP 第6根 / Stop 第10根"),
        summary_line("tp_bar7_stop_bar10", "TP 第7根 / Stop 第10根"),
        "",
        "## 最佳口径时间切片",
        "",
        f"最佳 PF：`{best_label}`，PF `{num(float(best['profit_factor']))}`，交易 `{int(best['trades'])}` 笔。",
        "",
        "| 切片 | 交易数 | 累计收益 | 年化 | 胜率 | payoff | PF | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in best_rolling.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{pct(float(row['total_return']))}` | "
            f"`{mult(float(row['annualized_multiple']))}` | `{pct(float(row['win_rate']))}` | "
            f"`{num(float(row['payoff_ratio']))}` | `{num(float(row['profit_factor']))}` | `{pct(float(row['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "加入 `1ATR` 早期止盈会显著改变 V3.3 的收益结构：它大幅提高胜率，但截断了原策略赖以盈利的大盈亏比尾部。若 PF/payoff 明显低于 baseline，则不应作为收益增强方向。",
            "",
            "本报告仍是旧 OHLCV 回测口径，不解决 V3.3 的 live-realistic stop 穿越问题。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_staged_tp_stop.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易明细 CSV：`{TRADES_PATH}`",
            f"- rolling CSV：`{ROLLING_PATH}`",
            f"- weekly CSV：`{WEEKLY_PATH}`",
            f"- monthly CSV：`{MONTHLY_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw = v33.load_all_hype_5m()
    raw = raw.loc[raw["ts"] <= v33.END_TS].reset_index(drop=True)
    frame = v33.add_minimal_features(raw, v33.V33_CONFIG)
    signal = v33.build_signal(frame, v33.V33_CONFIG)
    signal_count = int(np.count_nonzero(signal))

    baseline_trades = v33.simulate_trades(frame, signal, v33.V33_CONFIG)
    variants = [
        {
            "label": "v33_baseline",
            "trades": baseline_trades,
            "diag": pd.DataFrame(
                {
                    "label": ["v33_baseline"] * len(baseline_trades),
                    "reason": [trade.reason for trade in baseline_trades],
                    "bars_held": [trade.bars_held for trade in baseline_trades],
                    "net_ret_1x": [trade.net_ret_1x for trade in baseline_trades],
                }
            ),
            "extra": {"tp_atr": np.nan, "tp_disabled_bars": np.nan, "stop_disabled_bars": v33.V33_CONFIG.min_hold_bars},
        }
    ]

    staged_specs = [
        ("tp_bar6_stop_bar10", 5, 9),
        ("tp_bar7_stop_bar10", 6, 9),
    ]
    for label, tp_disabled_bars, stop_disabled_bars in staged_specs:
        trades, diag = simulate_staged_tp_stop(
            frame,
            signal,
            v33.V33_CONFIG,
            label=label,
            tp_atr=1.0,
            tp_disabled_bars=tp_disabled_bars,
            stop_disabled_bars=stop_disabled_bars,
        )
        variants.append(
            {
                "label": label,
                "trades": trades,
                "diag": diag,
                "extra": {"tp_atr": 1.0, "tp_disabled_bars": tp_disabled_bars, "stop_disabled_bars": stop_disabled_bars},
            }
        )

    summary_rows: list[dict[str, Any]] = []
    diag_parts: list[pd.DataFrame] = []
    rolling_parts: list[pd.DataFrame] = []
    weekly_parts: list[pd.DataFrame] = []
    monthly_parts: list[pd.DataFrame] = []
    for item in variants:
        label = str(item["label"])
        trades = item["trades"]
        summary_rows.append(summarize(label, signal_count, trades, frame, item["extra"]))
        diag_parts.append(item["diag"])
        rolling, weekly, monthly = add_prefixed_slices(label, frame, trades)
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
    diag.to_csv(TRADES_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    weekly.to_csv(WEEKLY_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, diag, rolling), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3 staged TP/stop",
                "base_definition": asdict(v33.V33_CONFIG),
                "variants": summary.to_dict(orient="records"),
                "reason_counts": diag.groupby(["label", "reason"]).size().reset_index(name="count").to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trades": str(TRADES_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                    "monthly": str(MONTHLY_PATH),
                },
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
