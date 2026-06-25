from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_5m_pbtr_v21a_live_realistic_audit as live_audit
from research_hype_5m_indicator_search import Trade, add_features, build_signal
from research_hype_5m_pbtr_v21_live_cost_variants import variant_specs
from research_hype_5m_pbtr_v2_ablation_slices import FINAL_FILTER_THRESHOLD, LEVERAGE, apply_final_filter, metric_with_sides
from research_hype_5m_pbtr_v2_live_cost_ablation_slices import ENTRY_SLIPPAGE_RATE, EXIT_SLIPPAGE_RATE, FEE_RATE_PER_FILL, simulate_trades_live_cost
from research_hype_5m_positive_payoff_search import load_all_hype_5m


REPORT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_unlock_exit_audit.json")
SUMMARY_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_unlock_exit_audit_summary.csv")
RECENT_PATH = Path("research/hype/families/5m-pullback-trail/artifacts/hype_5m_pbtr_v21a_unlock_exit_audit_recent.csv")
MARKDOWN_PATH = Path(
    "research/hype/families/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v21a-unlock-exit-audit-2026-06-24.md"
)


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def v21a_config() -> Any:
    for spec in variant_specs():
        if spec["version"] == "V2.1A":
            return spec["cfg"]
    raise RuntimeError("V2.1A spec not found")


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
) -> Trade:
    exit_price = float(raw_exit_price * (1.0 - direction * EXIT_SLIPPAGE_RATE))
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
    return Trade(
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


def active_stop(
    *,
    direction: int,
    entry_price: float,
    initial_stop: float,
    trail_atr: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous_stop: float | None = None,
) -> float:
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history))) if len(high_history) else entry_price
        candidate = max(initial_stop, peak - trail_atr * atr_value)
        return float(max(previous_stop, candidate) if previous_stop is not None else candidate)
    trough = min(entry_price, float(np.nanmin(low_history))) if len(low_history) else entry_price
    candidate = min(initial_stop, trough + trail_atr * atr_value)
    return float(min(previous_stop, candidate) if previous_stop is not None else candidate)


def crossed(price: float, stop_price: float, direction: int) -> bool:
    return bool(price <= stop_price if direction > 0 else price >= stop_price)


def simulate_fixed_unlock_open(frame: pd.DataFrame, signal: np.ndarray, cfg: Any) -> tuple[list[Trade], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    diag: list[dict[str, Any]] = []
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
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        trade = make_trade(
            label="V2.1A_fixed_unlock_open",
            ts_ns=ts_ns,
            sig_i=sig_i,
            entry_i=entry_i,
            exit_i=unlock_i,
            direction=direction,
            entry_price=entry_price,
            raw_exit_price=float(open_[unlock_i]),
            reason="unlock_open",
            high=high,
            low=low,
        )
        trades.append(trade)
        diag.append({"reason": trade.reason, "bars_held": trade.bars_held, "net_ret_1x": trade.net_ret_1x})
        blocked_until = unlock_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def simulate_unlock_close_trail(frame: pd.DataFrame, signal: np.ndarray, cfg: Any) -> tuple[list[Trade], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    trades: list[Trade] = []
    diag: list[dict[str, Any]] = []
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
        entry_price = float(open_[entry_i] * (1.0 + direction * ENTRY_SLIPPAGE_RATE))
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        end_i = min(n - 1, entry_i + cfg.max_hold_bars)
        unlock_i = entry_i + cfg.min_hold_bars
        if unlock_i > end_i:
            break
        stop_price: float | None = None
        exit_i = end_i
        reason = "time"
        raw_exit_price = float(close[end_i])
        for i in range(unlock_i, end_i + 1):
            stop_price = active_stop(
                direction=direction,
                entry_price=entry_price,
                initial_stop=initial_stop,
                trail_atr=cfg.trail_atr,
                high_history=high[entry_i : i + 1],
                low_history=low[entry_i : i + 1],
                atr_value=float(atr[i]),
                previous_stop=stop_price,
            )
            if crossed(float(close[i]), stop_price, direction):
                exit_i = i
                reason = "close_cross_trail"
                raw_exit_price = float(close[i])
                break
        trade = make_trade(
            label="V2.1A_unlock_close_trail",
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
        diag.append({"reason": reason, "bars_held": trade.bars_held, "net_ret_1x": trade.net_ret_1x})
        blocked_until = exit_i + cfg.cooldown_bars
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Trade], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **metric_with_sides(trades, LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def subset_stats(label: str, trades: list[Trade]) -> dict[str, Any]:
    returns = np.array([trade.net_ret_1x for trade in trades], dtype=float)
    wins = returns[returns > 0]
    losses = returns[returns <= 0]
    return {
        "label": label,
        "trades": int(len(trades)),
        "mean_net_ret_1x": float(returns.mean()) if len(returns) else 0.0,
        "win_rate": float((returns > 0).mean()) if len(returns) else 0.0,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) and abs(losses.sum()) > 0 else float("inf") if len(wins) else 0.0,
    }


def recent_rows(frame: pd.DataFrame, series: dict[str, list[Trade]]) -> list[dict[str, Any]]:
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    rows: list[dict[str, Any]] = []
    for label, trades in series.items():
        for days in (1, 2, 3, 7, 30):
            start = end - pd.Timedelta(days=days)
            selected = [trade for trade in trades if trade.entry_ts >= start]
            metrics = metric_with_sides(selected, LEVERAGE, start=start, end=end)
            rows.append({"label": label, "window": f"recent_{days}d", **metrics})
    return rows


def render_markdown(summary: pd.DataFrame, subset: pd.DataFrame, recent: pd.DataFrame) -> str:
    def row(label: str, display: str) -> str:
        item = summary[summary["label"] == label].iloc[0]
        return (
            f"| `{display}` | `{int(item['trades'])}` | `{mult(float(item['annualized_multiple']))}` | "
            f"`{pct(float(item['total_return']))}` | `{pct(float(item['win_rate']))}` | "
            f"`{num(float(item['profit_factor']))}` | `{num(float(item['payoff_ratio']))}` | `{pct(float(item['max_dd']))}` |"
        )

    lines = [
        "# HYPE-5M-PBTR-V2.1A unlock exit 审计 2026-06-24",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告专门复核 V2.1A dry-run 中观察到的现象：多数交易似乎在 `min_hold_bars=6` 结束后，第 7 根 K 计算 trailing 后直接退出，短样本仍然赚钱。",
        "",
        "## 对比口径",
        "",
        "- `原始回测`：V2.1A 既有实盘成本回测。前 6 根 K 不触发退出，第 7 根起如果 stop 被触发，按计算出的 stop 价成交。",
        "- `第7根开盘直接平仓`：信号入场后固定持有 6 根 K，第 7 根 K 开盘按市价平仓。",
        "- `第7根开盘 trailing 判定`：第 7 根开盘前根据前 6 根 K 计算 active stop；若已经穿越，则按第 7 根开盘市价平仓，否则继续挂 stop-market。",
        "- `第7根收盘 trailing 判定`：第 7 根收盘后用已收盘 K 计算 trailing；若 close 已穿越 active stop，则按 close 平仓。",
        "",
        "## 全样本结果",
        "",
        "| 口径 | 交易数 | 年化 | 总收益 | 胜率 | PF | payoff | 最大回撤 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        row("normal_original", "原始回测"),
        row("fixed_unlock_open", "第7根开盘直接平仓"),
        row("unlock_open_trail_market", "第7根开盘 trailing 判定"),
        row("unlock_close_trail_market", "第7根收盘 trailing 判定"),
        "",
        "## 第7根原始 stop 子集",
        "",
        "| 子集 | 交易数 | 平均单笔 1x 收益 | 胜率 | PF |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in subset.to_dict(orient="records"):
        lines.append(
            f"| `{item['label']}` | `{int(item['trades'])}` | `{pct(float(item['mean_net_ret_1x']))}` | `{pct(float(item['win_rate']))}` | `{num(float(item['profit_factor']))}` |"
        )
    lines.extend(
        [
            "",
            "原始回测中，第 7 根 K 触发 stop 的交易有 `2746` 笔，PF 接近 `1.98`。这解释了为什么 dry-run 看到大量第 7 根退出时会感觉像有 edge：研究回测里这个子集确实是赚钱的。",
            "",
            "但关键差异是成交价格。原始回测假设第 7 根 bar 内触发后能按计算出的 stop 价成交；如果实盘是在第 7 根开盘或收盘发现“已经不能继续拿”，然后用当前市价/close 平仓，全样本 PF 只有约 `0.54`。",
            "",
            "## 最近窗口",
            "",
            "| 口径 | 窗口 | 交易数 | 收益 | 胜率 | PF | 最大回撤 |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in recent.to_dict(orient="records"):
        lines.append(
            f"| `{item['label']}` | `{item['window']}` | `{int(item['trades'])}` | `{pct(float(item['total_return']))}` | `{pct(float(item['win_rate']))}` | `{num(float(item['profit_factor']))}` | `{pct(float(item['max_dd']))}` |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "你同事说的现象和原始回测是一致的：V2.1A 绝大多数原始退出确实发生在第 7 根，原因是第 7 根开始 trailing stop 生效并触发。",
            "",
            "但“第 7 根计算完 trailing 后直接触发 stop”是否赚钱，取决于成交价：",
            "",
            "- 如果按原始回测的 stop 价成交，第 7 根 stop 子集是赚钱的。",
            "- 如果实盘只能在发现穿越后按第 7 根开盘、市价或收盘价平仓，历史回测是亏损的。",
            "",
            "因此，14 笔 dry-run 盈利不能直接证明这个状态机已经可实盘。它可能是短样本，也可能是实盘 runner 的成交/判断时序与我们当前可执行回放仍有差异。下一步必须拿真实 14 笔的 entry、exit、signal_ts、bars_held、退出触发价、实际成交价和当时 active_stop 做逐笔对账。",
            "",
            "## 产物",
            "",
            "- 脚本：`research/hype/families/5m-pullback-trail/scripts/research_hype_5m_pbtr_v21a_unlock_exit_audit.py`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 最近窗口 CSV：`{RECENT_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    cfg = v21a_config()
    raw = load_all_hype_5m()
    frame = add_features(raw)
    frame["_ts_ns"] = frame["ts"].map(lambda value: pd.Timestamp(value).value).astype("int64")
    signal = apply_final_filter(frame, cfg, build_signal(frame, cfg), enabled=True, threshold=FINAL_FILTER_THRESHOLD)

    normal = simulate_trades_live_cost(frame, signal, cfg)
    fixed, _fixed_diag = simulate_fixed_unlock_open(frame, signal, cfg)
    live_open, live_open_diag = live_audit.simulate_live_realistic(frame, signal, cfg)
    close_trail, _close_diag = simulate_unlock_close_trail(frame, signal, cfg)

    live_open_by_trade = pd.DataFrame(
        {
            "reason": live_open_diag["reason"],
            "bars_held": live_open_diag["bars_held"],
            "net_ret_1x": [trade.net_ret_1x for trade in live_open],
        }
    )
    original_diag = pd.DataFrame({"reason": [trade.reason for trade in normal], "bars_held": [trade.bars_held for trade in normal], "net_ret_1x": [trade.net_ret_1x for trade in normal]})
    original_bars7_stop = [trade for trade in normal if trade.reason == "stop" and trade.bars_held == 7]

    summary = pd.DataFrame(
        [
            summarize("normal_original", normal, frame),
            summarize("fixed_unlock_open", fixed, frame, {"median_bars_held": 7.0}),
            summarize(
                "unlock_open_trail_market",
                live_open,
                frame,
                {
                    "median_bars_held": float(live_open_diag["bars_held"].median()),
                    "unlock_market_exit_rate": float((live_open_diag["reason"] == "unlock_market_exit").mean()),
                },
            ),
            summarize("unlock_close_trail_market", close_trail, frame, {"median_bars_held": 7.0}),
        ]
    )
    subset = pd.DataFrame(
        [
            subset_stats("original_stop_bars_held_7", original_bars7_stop),
            subset_stats("unlock_open_market_all", live_open),
            subset_stats("unlock_open_market_unlock_exit_only", [trade for trade, reason in zip(live_open, live_open_by_trade["reason"], strict=True) if reason == "unlock_market_exit"]),
        ]
    )
    recent = pd.DataFrame(
        recent_rows(
            frame,
            {
                "normal_original": normal,
                "fixed_unlock_open": fixed,
                "unlock_open_trail_market": live_open,
                "unlock_close_trail_market": close_trail,
            },
        )
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    recent.to_csv(RECENT_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, subset, recent), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V2.1A",
                "definition": asdict(cfg),
                "audit": "unlock_exit_semantics",
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "recent": str(RECENT_PATH),
                },
                "summary": summary.to_dict(orient="records"),
                "subset": subset.to_dict(orient="records"),
                "original_reason_bars_top": original_diag.groupby(["reason", "bars_held"]).size().sort_values(ascending=False).head(20).reset_index(name="count").to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"markdown={MARKDOWN_PATH}")
    print(summary[["label", "trades", "annualized_multiple", "total_return", "win_rate", "profit_factor", "payoff_ratio", "max_dd"]].to_string(index=False))
    print(subset.to_string(index=False))


if __name__ == "__main__":
    main()
