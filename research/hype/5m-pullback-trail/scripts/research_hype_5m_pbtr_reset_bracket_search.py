from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


V4_AUDIT_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v4_live_viability_audit.py")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search_summary.csv")
SIGNALS_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search_signals.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search_rolling.csv")
WEEKLY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search_weekly.csv")
TRADE_DIAG_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_reset_bracket_search_trade_diagnostics.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-reset-bracket-search-2026-06-24.md"
)

TP_ATR_GRID = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)
SL_ATR_GRID = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0)


def load_v4_audit_module() -> Any:
    spec = importlib.util.spec_from_file_location("v4_live_viability_audit", V4_AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module from {V4_AUDIT_PATH}")
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


def signal_stats(label: str, signal: np.ndarray, normal_trades: list[Any]) -> dict[str, Any]:
    return {
        "strategy": label,
        "raw_signal_count": int(np.count_nonzero(signal)),
        "raw_long_signals": int((signal > 0).sum()),
        "raw_short_signals": int((signal < 0).sum()),
        "normal_trade_count": int(len(normal_trades)),
        "normal_long_trades": int(sum(1 for trade in normal_trades if trade.side > 0)),
        "normal_short_trades": int(sum(1 for trade in normal_trades if trade.side < 0)),
    }


def bracket_prices(reference_price: float, atr_value: float, direction: int, tp_atr: float, sl_atr: float) -> tuple[float, float]:
    target_price = reference_price + direction * tp_atr * atr_value
    stop_price = reference_price - direction * sl_atr * atr_value
    return float(target_price), float(stop_price)


def simulate_reset_bracket(
    frame: pd.DataFrame,
    signal: np.ndarray,
    *,
    label: str,
    tp_atr: float,
    sl_atr: float,
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

        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        reference_price = entry_price
        reference_atr = signal_atr
        target_price, stop_price = bracket_prices(reference_price, reference_atr, direction, tp_atr, sl_atr)

        exit_i = n - 1
        reason = "time"
        raw_exit_price = float(close[-1])
        both_hit = False
        reset_count = 0

        for j in range(entry_i, n):
            if direction > 0:
                stop_hit = low[j] <= stop_price
                target_hit = high[j] >= target_price
            else:
                stop_hit = high[j] >= stop_price
                target_hit = low[j] <= target_price
            both_hit = bool(stop_hit and target_hit)
            if stop_hit:
                exit_i = j
                reason = "both_hit_stop_first" if both_hit else "stop"
                raw_exit_price = float(stop_price)
                break
            if target_hit:
                exit_i = j
                reason = "target"
                raw_exit_price = float(target_price)
                break

            # Live timing: after bar j closes, amend orders around close[j] for bar j+1.
            if j + 1 < n and np.isfinite(atr[j]) and atr[j] > 0:
                reference_price = float(close[j])
                reference_atr = float(atr[j])
                target_price, stop_price = bracket_prices(reference_price, reference_atr, direction, tp_atr, sl_atr)
                reset_count += 1

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
                "tp_atr": tp_atr,
                "sl_atr": sl_atr,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "both_hit_stop_first": both_hit,
                "reset_count": reset_count,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "mae_1x": trade.mae_1x,
                "mfe_1x": trade.mfe_1x,
                "entry_price": entry_price,
                "exit_price": exit_price,
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


def run_grid(strategy: str, frame: pd.DataFrame, signal: np.ndarray) -> tuple[pd.DataFrame, dict[str, list[Any]], dict[str, pd.DataFrame]]:
    rows: list[dict[str, Any]] = []
    trades_by_label: dict[str, list[Any]] = {}
    diag_by_label: dict[str, pd.DataFrame] = {}
    for tp_atr in TP_ATR_GRID:
        for sl_atr in SL_ATR_GRID:
            label = f"{strategy}-reset-bracket-tp{tp_atr:g}-sl{sl_atr:g}"
            trades, diag = simulate_reset_bracket(frame, signal, label=label, tp_atr=tp_atr, sl_atr=sl_atr)
            rows.append(
                summarize(
                    label,
                    trades,
                    frame,
                    {
                        "strategy": strategy,
                        "tp_atr": tp_atr,
                        "sl_atr": sl_atr,
                        "both_hit_rate": float(diag["both_hit_stop_first"].mean()) if len(diag) else 0.0,
                        "target_exit_rate": float((diag["reason"] == "target").mean()) if len(diag) else 0.0,
                        "stop_exit_rate": float(diag["reason"].isin(["stop", "both_hit_stop_first"]).mean()) if len(diag) else 0.0,
                        "median_bars_held": float(diag["bars_held"].median()) if len(diag) else 0.0,
                        "median_reset_count": float(diag["reset_count"].median()) if len(diag) else 0.0,
                    },
                )
            )
            trades_by_label[label] = trades
            diag_by_label[label] = diag
    summary = pd.DataFrame(rows).sort_values(["profit_factor", "total_return"], ascending=False).reset_index(drop=True)
    return summary, trades_by_label, diag_by_label


def add_slices(strategy: str, label: str, frame: pd.DataFrame, trades: list[Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rolling, weekly, _monthly = v33.baseline_time_slices(frame, trades)
    rolling.insert(0, "strategy", strategy)
    rolling.insert(1, "label", label)
    weekly.insert(0, "strategy", strategy)
    weekly.insert(1, "label", label)
    return rolling, weekly


def render_markdown(signal_summary: pd.DataFrame, grid_summary: pd.DataFrame, rolling: pd.DataFrame, weekly: pd.DataFrame) -> str:
    def row(item: dict[str, Any]) -> str:
        return (
            f"| `{item['strategy']}` | `{item['tp_atr']}` | `{item['sl_atr']}` | `{int(item['trades'])}` | "
            f"`{mult(float(item['annualized_multiple']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['profit_factor']))}` | `{num(float(item['payoff_ratio']))}` | "
            f"`{pct(float(item['max_dd']))}` | `{pct(float(item['both_hit_rate']))}` | `{num(float(item['median_reset_count']))}` |"
        )

    lines = [
        "# HYPE-5M-PBTR 每 5m 重设 ATR bracket 搜索 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试 `HYPE-5M-PBTR-V3.3` 和 `HYPE-5M-PBTR-V4` 信号的动态 bracket 退出：入场后立即挂 TP/SL；之后每根 5m K 收盘后，围绕刚收盘的 close 和 ATR14 取消/重挂下一根 K 的 TP/SL。",
        "",
        "这是一个可实盘执行口径：每次重设只使用已经收盘的 K 线。同一根 5m K 同时触及 TP 和 SL 时，按保守口径记为先触发止损。",
        "",
        "## 信号数",
        "",
        "| 策略 | 原始信号数 | 多头信号 | 空头信号 | 原始回测实际交易 | 原始多/空交易 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in signal_summary.to_dict(orient="records"):
        lines.append(
            f"| `{item['strategy']}` | `{int(item['raw_signal_count'])}` | `{int(item['raw_long_signals'])}` | `{int(item['raw_short_signals'])}` | `{int(item['normal_trade_count'])}` | `{int(item['normal_long_trades'])}/{int(item['normal_short_trades'])}` |"
        )

    top_rows = grid_summary.sort_values(["profit_factor", "total_return"], ascending=False).groupby("strategy").head(5)
    lines.extend(
        [
            "",
            "## 动态 bracket 最佳结果",
            "",
            "| 策略 | TP ATR | SL ATR | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | 同 K 双触发率 | 中位重设次数 |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in top_rows.to_dict(orient="records"):
        lines.append(row(item))

    for strategy in ("HYPE-5M-PBTR-V3.3", "HYPE-5M-PBTR-V4"):
        best = top_rows[top_rows["strategy"] == strategy].iloc[0]
        best_weekly = weekly[weekly["label"] == best["label"]]
        best_rolling = rolling[rolling["label"] == best["label"]]
        lines.extend(
            [
                "",
                f"## `{strategy}` 最佳组合切片",
                "",
                f"- 最佳组合：`TP={best['tp_atr']} ATR / SL={best['sl_atr']} ATR`，PF `{num(float(best['profit_factor']))}`，最大回撤 `{pct(float(best['max_dd']))}`。",
                f"- 周切片：盈利周 `{int((best_weekly['total_return'] > 0).sum())}/{len(best_weekly)}`，中位周收益 `{pct(float(best_weekly['total_return'].median()))}`。",
            ]
        )
        for row_item in best_rolling.to_dict(orient="records"):
            lines.append(
                f"- `{row_item['window']}`：交易 `{int(row_item['trades'])}`，收益 `{pct(float(row_item['total_return']))}`，胜率 `{pct(float(row_item['win_rate']))}`，PF `{num(float(row_item['profit_factor']))}`，最大回撤 `{pct(float(row_item['max_dd']))}`。"
            )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "每 5m 重设 bracket 是实盘可执行的退出机制，但它不能救活 V3.3/V4。动态重设会让 TP/SL 跟随价格移动，某些宽参数组合会出现表面 PF 改善，但代价是单笔持仓极长、交易数极少、深回撤和大量信号被占仓屏蔽。",
            "",
            "V3.3 的最佳组合 `TP=6 ATR / SL=10 ATR` 虽然 PF `2.22`，但全样本只有 `24` 笔交易，中位持仓约 `2984` 根 5m K，最大回撤 `-69.21%`，最近 1 个月没有任何交易。这更像长期占仓的偶然样本，而不是可交接的高频 pullback 策略。",
            "",
            "V4 的最佳组合全样本收益仍为负，且同样依赖极少数超长持仓。`TP=5 ATR / SL=3 ATR` 这类直觉参数在 V3.3/V4 上也分别只有 PF `0.95`/`0.93`，回撤超过 `-80%`。",
            "",
            "因此，动态 bracket 可以作为未来 live-ready 状态机组件，但不能直接作为 V3.3/V4 修复方案。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_reset_bracket_search.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 信号 CSV：`{SIGNALS_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易诊断 CSV：`{TRADE_DIAG_PATH}`",
            f"- rolling CSV：`{ROLLING_PATH}`",
            f"- weekly CSV：`{WEEKLY_PATH}`",
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

    signal_rows: list[dict[str, Any]] = []
    grid_frames: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    weekly_frames: list[pd.DataFrame] = []
    diag_frames: list[pd.DataFrame] = []
    strategy_defs: dict[str, Any] = {}

    for strategy, cfg in configs:
        frame = v33.add_minimal_features(raw, cfg)
        signal = v33.build_signal(frame, cfg)
        normal_trades = v33.simulate_trades(frame, signal, cfg)
        signal_rows.append(signal_stats(strategy, signal, normal_trades))
        grid, trades_by_label, diag_by_label = run_grid(strategy, frame, signal)
        grid_frames.append(grid)
        top_labels = set(grid.head(5)["label"])
        top_labels.add(str(grid.iloc[0]["label"]))
        for label in top_labels:
            rolling, weekly = add_slices(strategy, label, frame, trades_by_label[label])
            rolling_frames.append(rolling)
            weekly_frames.append(weekly)
            diag_frames.append(diag_by_label[label])
        strategy_defs[strategy] = asdict(cfg)

    signal_summary = pd.DataFrame(signal_rows)
    grid_summary = pd.concat(grid_frames, ignore_index=True).sort_values(["strategy", "profit_factor", "total_return"], ascending=[True, False, False])
    rolling_all = pd.concat(rolling_frames, ignore_index=True)
    weekly_all = pd.concat(weekly_frames, ignore_index=True)
    diag_all = pd.concat(diag_frames, ignore_index=True)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    signal_summary.to_csv(SIGNALS_PATH, index=False)
    grid_summary.to_csv(SUMMARY_PATH, index=False)
    rolling_all.to_csv(ROLLING_PATH, index=False)
    weekly_all.to_csv(WEEKLY_PATH, index=False)
    diag_all.to_csv(TRADE_DIAG_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(signal_summary, grid_summary, rolling_all, weekly_all), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "audit": "reset_atr_bracket_search",
                "tp_atr_grid": TP_ATR_GRID,
                "sl_atr_grid": SL_ATR_GRID,
                "both_hit_policy": "stop_first",
                "reset_timing": "after each closed 5m bar, active next bar",
                "strategies": strategy_defs,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "signals": str(SIGNALS_PATH),
                    "summary": str(SUMMARY_PATH),
                    "trade_diagnostics": str(TRADE_DIAG_PATH),
                    "rolling": str(ROLLING_PATH),
                    "weekly": str(WEEKLY_PATH),
                },
                "signal_summary": signal_summary.to_dict(orient="records"),
                "top_summary": grid_summary.groupby("strategy").head(10).to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(signal_summary.to_string(index=False))
    print(
        grid_summary.groupby("strategy")
        .head(10)[["strategy", "tp_atr", "sl_atr", "trades", "annualized_multiple", "win_rate", "profit_factor", "payoff_ratio", "max_dd", "both_hit_rate", "median_reset_count"]]
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
