from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REINIT_PATH = Path(__file__).with_name("research_hype_5m_pbtr_v33_reinit_trailing.py")

REPORT_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_crossing_exit_search.json")
SUMMARY_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_crossing_exit_search_summary.csv")
ROLLING_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_crossing_exit_search_rolling.csv")
TRADE_DIAG_PATH = Path("research/hype/5m-pullback-trail/artifacts/hype_5m_pbtr_v33_no_crossing_exit_search_trade_diagnostics.csv")
MARKDOWN_PATH = Path(
    "research/hype/5m-pullback-trail/diagnostics/"
    "hype-5m-pbtr-v33-no-crossing-exit-search-2026-06-25.md"
)

ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]
TRAIL_ATRS = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0]


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


def pct(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.{digits}f}%"


def num(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}"


def mult(value: float, digits: int = 2) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.{digits}f}x"


def alpha_label(alpha: float) -> str:
    if alpha == 0.0:
        return "open"
    if alpha == 1.0:
        return "peak"
    return f"blend_{alpha:g}"


def simulate_alpha_trailing(
    frame: pd.DataFrame,
    signal: np.ndarray,
    cfg: Any,
    *,
    alpha: float,
    trail_atr: float,
) -> tuple[list[Any], pd.DataFrame]:
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    label = f"alpha_{alpha:g}_trail_{trail_atr:g}"
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
        unlock_open = float(open_[unlock_i])
        atr_value = float(atr[unlock_i - 1])
        if not np.isfinite(atr_value) or atr_value <= 0:
            continue

        lockout_high = high[entry_i:unlock_i]
        lockout_low = low[entry_i:unlock_i]
        if direction > 0:
            lockout_extreme = max(entry_price, float(np.nanmax(lockout_high))) if len(lockout_high) else entry_price
            reference_price = unlock_open + alpha * (lockout_extreme - unlock_open)
            active_stop = reference_price - trail_atr * atr_value
            required_trail_atr = max(0.0, (reference_price - unlock_open) / atr_value)
            lockout_mae = float(np.nanmin(lockout_low / entry_price - 1.0)) if len(lockout_low) else 0.0
            lockout_mfe = float(np.nanmax(lockout_high / entry_price - 1.0)) if len(lockout_high) else 0.0
        else:
            lockout_extreme = min(entry_price, float(np.nanmin(lockout_low))) if len(lockout_low) else entry_price
            reference_price = unlock_open + alpha * (lockout_extreme - unlock_open)
            active_stop = reference_price + trail_atr * atr_value
            required_trail_atr = max(0.0, (unlock_open - reference_price) / atr_value)
            lockout_mae = float(np.nanmin(direction * (lockout_high / entry_price - 1.0))) if len(lockout_high) else 0.0
            lockout_mfe = float(np.nanmax(direction * (lockout_low / entry_price - 1.0))) if len(lockout_low) else 0.0

        unlock_active_stop = float(active_stop)
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
                        trail_atr=trail_atr,
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
                "alpha": alpha,
                "trail_atr": trail_atr,
                "reference": alpha_label(alpha),
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "unlock_ts": pd.Timestamp(ts_ns[unlock_i], unit="ns", tz="UTC"),
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "net_ret_1x": trade.net_ret_1x,
                "entry_price": entry_price,
                "unlock_open": unlock_open,
                "lockout_extreme": lockout_extreme,
                "reference_price": reference_price,
                "unlock_active_stop": unlock_active_stop,
                "final_active_stop": float(active_stop),
                "required_trail_atr_for_unlock_valid": required_trail_atr,
                "unlock_stop_valid": unlock_stop_valid,
                "lockout_mae_bps": lockout_mae * 10000.0,
                "lockout_mfe_bps": lockout_mfe * 10000.0,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag_rows)


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, diag: pd.DataFrame, alpha: float, trail_atr: float) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}
    row.update(
        {
            "alpha": alpha,
            "trail_atr": trail_atr,
            "reference": alpha_label(alpha),
            "unlock_market_rate": float(diag["reason"].eq("unlock_market_exit").mean()) if len(diag) else np.nan,
            "gap_market_rate": float(diag["reason"].eq("gap_market_exit").mean()) if len(diag) else np.nan,
            "stop_market_rate": float(diag["reason"].eq("stop_market").mean()) if len(diag) else np.nan,
            "time_rate": float(diag["reason"].eq("time").mean()) if len(diag) else np.nan,
            "avg_bars_held": float(diag["bars_held"].mean()) if len(diag) else np.nan,
            "p95_required_trail_atr": float(diag["required_trail_atr_for_unlock_valid"].quantile(0.95)) if len(diag) else np.nan,
            "max_required_trail_atr": float(diag["required_trail_atr_for_unlock_valid"].max()) if len(diag) else np.nan,
        }
    )
    rolling, _, _ = v33.baseline_time_slices(frame, trades)
    recent_1m = rolling.loc[rolling["window"].eq("recent_1m")].iloc[0].to_dict()
    recent_3m = rolling.loc[rolling["window"].eq("recent_3m")].iloc[0].to_dict()
    row.update(
        {
            "recent_1m_pf": float(recent_1m["profit_factor"]),
            "recent_1m_return": float(recent_1m["total_return"]),
            "recent_3m_pf": float(recent_3m["profit_factor"]),
            "recent_3m_return": float(recent_3m["total_return"]),
        }
    )
    return row


def render_markdown(summary: pd.DataFrame) -> str:
    no_unlock_cross = summary.loc[summary["unlock_market_rate"].eq(0.0)].copy()
    positive = no_unlock_cross.loc[
        (no_unlock_cross["profit_factor"] > 1.0)
        & (no_unlock_cross["recent_1m_pf"] > 1.0)
        & (no_unlock_cross["recent_3m_pf"] > 1.0)
    ].copy()
    top_no_cross = no_unlock_cross.sort_values(["profit_factor", "recent_3m_pf"], ascending=False).head(12)
    top_all = summary.sort_values(["profit_factor", "recent_3m_pf"], ascending=False).head(12)

    def table(rows: pd.DataFrame) -> list[str]:
        output = [
            "| reference | alpha | trail_atr | trades | PF | 近1m PF | 近3m PF | 最大回撤 | 解锁穿越 | gap 市价 | 平均持仓K |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for item in rows.to_dict(orient="records"):
            output.append(
                f"| `{item['reference']}` | `{item['alpha']:.2f}` | `{item['trail_atr']:.2f}` | "
                f"`{int(item['trades'])}` | `{num(float(item['profit_factor']))}` | "
                f"`{num(float(item['recent_1m_pf']))}` | `{num(float(item['recent_3m_pf']))}` | "
                f"`{pct(float(item['max_dd']))}` | `{pct(float(item['unlock_market_rate']))}` | "
                f"`{pct(float(item['gap_market_rate']))}` | `{num(float(item['avg_bars_held']))}` |"
            )
        return output

    peak_rows = summary.loc[summary["alpha"].eq(1.0)].sort_values("trail_atr")
    peak_no_cross = peak_rows.loc[peak_rows["unlock_market_rate"].eq(0.0)]
    min_peak_no_cross = None if peak_no_cross.empty else peak_no_cross.iloc[0]
    open_rows = summary.loc[summary["alpha"].eq(0.0)].sort_values("profit_factor", ascending=False).head(5)

    lines = [
        "# HYPE-5M-PBTR-V3.3 no-crossing exit search 2026-06-25",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "目标：寻找解锁时不发生 stop 穿越、可真实挂 stop-market/stop-limit 类保护单，且历史上仍为正期望的 V3.3 退出参数。",
        "",
        "搜索口径：",
        "",
        "- `alpha=0`：完全用第 10 根 K 的 open 作为 trailing 锚点。",
        "- `alpha=0.5`：使用 lockout peak/trough 与 open 的均价。",
        "- `alpha=1`：使用原 V3.3 的 lockout peak/trough 锚点。",
        "- `trail_atr`：从 `0.25` 到 `12.0`。",
        "- 不再使用 `stop_atr` 初始止损锚点；否则单靠调大 `trail_atr` 无法修复 initial stop 已被穿越的问题。",
        "",
        "## 硬筛结论",
        "",
    ]
    if positive.empty:
        lines.append("没有找到同时满足 `解锁穿越率=0`、全样本 PF > 1、近 1m PF > 1、近 3m PF > 1 的候选。")
    else:
        lines.append("找到以下机械候选，但仍需继续做月度稳定性与 paper audit：")
        lines.extend(table(positive.sort_values("profit_factor", ascending=False)))
    lines.extend(
        [
            "",
            "## 解锁 0 穿越候选中表现最好",
            "",
            *table(top_no_cross),
            "",
            "## 全部搜索中表现最好",
            "",
            *table(top_all),
            "",
            "## peak/trough 原锚点需要多宽",
            "",
        ]
    )
    if min_peak_no_cross is None:
        lines.append("在本次 `trail_atr <= 12` 网格内，原 peak/trough 锚点没有做到 0 解锁穿越。")
    else:
        lines.append(
            f"原 peak/trough 锚点至少需要 `trail_atr={float(min_peak_no_cross['trail_atr']):.2f}` "
            f"才做到本次回放中的 0 解锁穿越；对应 PF `{num(float(min_peak_no_cross['profit_factor']))}`，"
            f"近 3m PF `{num(float(min_peak_no_cross['recent_3m_pf']))}`。"
        )
    lines.extend(
        [
            "",
            "纯 open 锚点天然 0 解锁穿越，但最佳几组仍未恢复正期望：",
            "",
            *table(open_rows),
            "",
            "## 结论",
            "",
            "穿越不是一个能靠单个 `trail_atr` 值修好的小瑕疵。要么锚点足够贴近当前 open，能挂单但失去旧 V3.3 的收益结构；要么保留 peak/trough 锚点，必须把 stop 放得很宽，收益结构同样塌掉。",
            "",
            "因此，目前没有从 V3.3 trailing 参数中找到“解锁不穿越 + 可实盘 + 长期正期望”的值。下一步应该转向可执行优先的入场/保护结构，而不是继续修补旧 V3.3 的延迟 trailing。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/research_hype_5m_pbtr_v33_no_crossing_exit_search.py`",
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

    summary_rows: list[dict[str, Any]] = []
    diag_parts: list[pd.DataFrame] = []
    rolling_parts: list[pd.DataFrame] = []
    for alpha in ALPHAS:
        for trail_atr in TRAIL_ATRS:
            cfg = replace(v33.V33_CONFIG, trail_atr=trail_atr, stop_atr=1e9)
            label = f"alpha_{alpha:g}_trail_{trail_atr:g}"
            trades, diag = simulate_alpha_trailing(frame, signal, cfg, alpha=alpha, trail_atr=trail_atr)
            summary_rows.append(summarize(label, trades, frame, diag, alpha, trail_atr))
            diag_parts.append(diag)
            rolling, _, _ = v33.baseline_time_slices(frame, trades)
            rolling.insert(0, "label", label)
            rolling.insert(1, "alpha", alpha)
            rolling.insert(2, "trail_atr", trail_atr)
            rolling_parts.append(rolling)

    summary = pd.DataFrame(summary_rows)
    diag = pd.concat(diag_parts, ignore_index=True, sort=False)
    rolling = pd.concat(rolling_parts, ignore_index=True, sort=False)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKDOWN_PATH.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    diag.to_csv(TRADE_DIAG_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "strategy": "HYPE-5M-PBTR-V3.3 no-crossing executable exit search",
                "base_config": asdict(v33.V33_CONFIG),
                "alphas": ALPHAS,
                "trail_atrs": TRAIL_ATRS,
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "rolling": str(ROLLING_PATH),
                    "diagnostics": str(TRADE_DIAG_PATH),
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
    print(
        summary.sort_values(["unlock_market_rate", "profit_factor"], ascending=[True, False])
        .head(20)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
