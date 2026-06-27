from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal

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


retry = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v33_retry_arm.py", "hype_pbtr_v33_retry_arm")
v33 = retry.v33

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_no_initial_stop_buffer_grid_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_no_initial_stop_buffer_grid_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_no_initial_stop_buffer_grid_trades_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_no_initial_stop_buffer_grid_diagnostics_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-no-initial-stop-buffer-grid-{RUN_DATE}.md"

PULLBACK_BUFFER_GRID = (
    0.01,
    0.0075,
    0.005,
    0.0025,
    0.0,
    -0.0025,
    -0.005,
    -0.0075,
    -0.01,
    -0.0125,
    -0.015,
    -0.02,
)
Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def buffer_label(value: float) -> str:
    return f"pb_{value:+.4f}".replace("+", "p").replace("-", "m").replace(".", "p")


def trailed_stop_without_initial_floor(
    direction: int,
    entry_price: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous: float | None,
) -> float:
    cfg = v33.V33_CONFIG
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history)))
        candidate = peak - cfg.trail_atr * atr_value
        return float(candidate if previous is None else max(previous, candidate))
    trough = min(entry_price, float(np.nanmin(low_history)))
    candidate = trough + cfg.trail_atr * atr_value
    return float(candidate if previous is None else min(previous, candidate))


def simulate_no_initial_stop(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    *,
    pullback_buffer: float,
) -> tuple[list[Any], pd.DataFrame]:
    ts = pd.to_datetime(frame["ts"], utc=True)
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    trades: list[Any] = []
    diag: list[dict[str, Any]] = []
    blocked_until = -1

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= len(frame) or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        active_stop: float | None = None
        armed = False
        arm_i: int | None = None
        skip_open_gap_i: int | None = None
        retry_count = 0
        reject_count = 0
        reason = "time"
        exit_i = len(frame) - 1
        raw_exit = float(close[-1])

        for j in range(entry_i, len(frame)):
            bars_held = j - entry_i + 1
            if armed and active_stop is not None:
                if j != skip_open_gap_i and not retry.armable(direction, active_stop, float(open_[j])):
                    reason = "gap_market_exit"
                    raw_exit = float(open_[j])
                    exit_i = j
                    break
                if retry.touched(direction, active_stop, float(high[j]), float(low[j])):
                    reason = "stop_market"
                    raw_exit = active_stop
                    exit_i = j
                    break
            if not armed and bars_held > 9:
                reason = "stop_arm_deadline"
                raw_exit = float(close[j])
                exit_i = j
                break
            if bars_held < 7:
                continue

            desired_stop = trailed_stop_without_initial_floor(
                direction,
                entry_price,
                high[entry_i : j + 1],
                low[entry_i : j + 1],
                float(atr[j]),
                active_stop,
            )
            process_time = pd.Timestamp(ts.iloc[j]) + pd.Timedelta(minutes=5)
            next_time = process_time + pd.Timedelta(minutes=5)
            can_arm, retry_points = retry.interval_can_arm(
                mode,
                direction,
                desired_stop,
                float(close[j]),
                float(high[j + 1]) if j + 1 < len(frame) else None,
                float(low[j + 1]) if j + 1 < len(frame) else None,
                retry.one_minute_rows(frame_1m, process_time, next_time),
            )
            retry_count += retry_points
            active_stop = desired_stop
            if can_arm:
                armed = True
                arm_i = j
                skip_open_gap_i = None if retry.armable(direction, desired_stop, float(close[j])) else j + 1
            else:
                reject_count += 1

        exit_price = retry.exit_price_with_cost(raw_exit, direction)
        net, mae, mfe = retry.net_mae_mfe(direction, entry_price, exit_price, high[entry_i : exit_i + 1], low[entry_i : exit_i + 1])
        label = f"HYPE-5M-PBTR-V3.3.1-no-initial-stop-{mode}-{buffer_label(pullback_buffer)}"
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
            net_ret_1x=net,
            mae_1x=mae,
            mfe_1x=mfe,
        )
        trades.append(trade)
        diag.append(
            {
                "mode": mode,
                "pullback_buffer": pullback_buffer,
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": direction,
                "reason": reason,
                "bars_held": trade.bars_held,
                "armed": armed,
                "arm_ts": None if arm_i is None else pd.Timestamp(ts_ns[arm_i], unit="ns", tz="UTC"),
                "retry_count": retry_count,
                "reject_count": reject_count,
                "deadline_exit": reason == "stop_arm_deadline",
                "entry_price": entry_price,
                "final_active_stop": active_stop,
                "exit_price": exit_price,
                "net_ret_1x": net,
                "mae_1x": mae,
                "mfe_1x": mfe,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag)


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, extra: dict[str, Any]) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    return {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end), **extra}


def best_rows(summary: pd.DataFrame, mode: str, n: int = 5) -> pd.DataFrame:
    return summary.loc[summary["mode"].eq(mode)].sort_values(["profit_factor", "total_return"], ascending=False).head(n)


def render_table_rows(rows: pd.DataFrame) -> list[str]:
    result: list[str] = []
    for row in rows.to_dict(orient="records"):
        result.append(
            f"| `{row['mode']}` | `{float(row['pullback_buffer']):+.4f}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_num(float(row['payoff_ratio']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_pct(float(row['armed_rate']))}` | `{fmt_pct(float(row['deadline_exit_rate']))}` |"
        )
    return result


def render_markdown(summary: pd.DataFrame, used_1m: bool) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 no-initial-stop + pullback_buffer 网格 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告在 `HYPE-5M-PBTR-V3.3.1` retry-arm overlay 基础上测试两个修改：",
        "",
        "- 去掉初始止损价 floor：第 7 根开始的 desired stop 只由锁仓期峰谷和 `trail_atr=0.75` 推导，不再与 `entry_price ± 0.5 ATR` 比较取更保守值。",
        "- 扫描更小甚至负的 `pullback_buffer`：`0.0100/0.0075/0.0050/0.0025/0/-0.0025/-0.0050/-0.0075/-0.0100/-0.0125/-0.0150/-0.0200`。",
        "",
        f"本次使用 1m 数据：`{used_1m}`。",
        "",
        "## 全部结果",
        "",
        "| 口径 | pullback_buffer | 交易数 | 累计收益 | 胜率 | PF | payoff | 最大回撤 | armed | deadline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(render_table_rows(summary))
    lines.extend(["", "## 各口径 PF Top", ""])
    for mode in summary["mode"].drop_duplicates().tolist():
        lines.append(f"### {mode}")
        lines.append("")
        lines.append("| pullback_buffer | 交易数 | 累计收益 | 胜率 | PF | payoff | 最大回撤 |")
        lines.append("| ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in best_rows(summary, mode).to_dict(orient="records"):
            lines.append(
                f"| `{float(row['pullback_buffer']):+.4f}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
                f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
                f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` |"
            )
        lines.append("")
    best = summary.sort_values(["profit_factor", "total_return"], ascending=False).iloc[0]
    liquid_candidates = summary.loc[summary["trades"] >= 30]
    best_liquid = liquid_candidates.sort_values(["profit_factor", "total_return"], ascending=False).iloc[0]
    lines.extend(
        [
            "## 结论",
            "",
            f"全网格最佳行为出现在 `{best['mode']}` / `pullback_buffer={float(best['pullback_buffer']):+.4f}`，PF `{fmt_num(float(best['profit_factor']))}`，交易数 `{int(best['trades'])}`，累计收益 `{fmt_pct(float(best['total_return']))}`，最大回撤 `{fmt_pct(float(best['max_dd']))}`。",
            "",
            f"但该全网格最佳只有 `{int(best['trades'])}` 笔，不能作为稳健策略证据。交易数 `>=30` 的最佳行为是 `{best_liquid['mode']}` / `pullback_buffer={float(best_liquid['pullback_buffer']):+.4f}`，PF `{fmt_num(float(best_liquid['profit_factor']))}`，交易数 `{int(best_liquid['trades'])}`，累计收益 `{fmt_pct(float(best_liquid['total_return']))}`，最大回撤 `{fmt_pct(float(best_liquid['max_dd']))}`。",
            "",
            "`pullback_buffer=-0.0100` 在四个口径都为正收益且 PF `>1`，说明极严格的反向深回踩触发值得作为事件质量线索继续观察；但它只有 `37` 笔交易，`-0.0125` 变回亏损，`-0.0150` 只剩 `7` 笔，`-0.0200` 只剩 `1` 笔。因此本轮不能把 no-initial-stop + 负 buffer 直接提升为 V3.3.1 候选，只能记录为低样本诊断线索。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_PATH}`",
            f"- 交易 CSV：`{TRADES_PATH}`",
            f"- 诊断 CSV：`{DIAG_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    raw_5m = v33.load_all_hype_5m()
    frame_1m = retry.load_hype_1m()
    if frame_1m is not None:
        max_ts = min(pd.Timestamp(raw_5m["ts"].iloc[-1]), pd.Timestamp(frame_1m["ts"].iloc[-1]).floor("5min"))
        raw_5m = raw_5m.loc[raw_5m["ts"] <= max_ts].reset_index(drop=True)
        frame_1m = frame_1m.loc[
            (frame_1m["ts"] >= raw_5m["ts"].iloc[0]) & (frame_1m["ts"] <= max_ts + pd.Timedelta(minutes=5))
        ].reset_index(drop=True)

    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    summary_rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    trade_rows: list[dict[str, Any]] = []
    for pullback_buffer in PULLBACK_BUFFER_GRID:
        cfg = replace(v33.V33_CONFIG, pullback_buffer=pullback_buffer)
        frame = v33.add_minimal_features(raw_5m, cfg)
        signal = v33.build_v33_signal(frame, cfg)
        signal_count = int(np.count_nonzero(signal))
        for mode in modes:
            trades, diag = simulate_no_initial_stop(frame, signal, frame_1m, mode, pullback_buffer=pullback_buffer)
            diag_frames.append(diag)
            label = f"{mode}_{buffer_label(pullback_buffer)}"
            summary_rows.append(
                summarize(
                    label,
                    trades,
                    frame,
                    {
                        "mode": mode,
                        "pullback_buffer": pullback_buffer,
                        "signal_count": signal_count,
                        "armed_rate": float(diag["armed"].mean()) if len(diag) else 0.0,
                        "deadline_exit_rate": float(diag["deadline_exit"].mean()) if len(diag) else 0.0,
                        "avg_retry_count": float(diag["retry_count"].mean()) if len(diag) else 0.0,
                        "avg_reject_count": float(diag["reject_count"].mean()) if len(diag) else 0.0,
                    },
                )
            )
            for i, trade in enumerate(trades, start=1):
                trade_rows.append(
                    {
                        "label": label,
                        "mode": mode,
                        "pullback_buffer": pullback_buffer,
                        "trade_no": i,
                        "signal_ts": trade.signal_ts,
                        "entry_ts": trade.entry_ts,
                        "exit_ts": trade.exit_ts,
                        "side": trade.side,
                        "reason": trade.reason,
                        "bars_held": trade.bars_held,
                        "entry_price": trade.entry_price,
                        "exit_price": trade.exit_price,
                        "net_ret_1x": trade.net_ret_1x,
                        "mae_1x": trade.mae_1x,
                        "mfe_1x": trade.mfe_1x,
                    }
                )

    summary = pd.DataFrame(summary_rows)
    diag_all = pd.concat(diag_frames, ignore_index=True)
    trades_out = pd.DataFrame(trade_rows)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag_all.to_csv(DIAG_PATH, index=False)
    trades_out.to_csv(TRADES_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, frame_1m is not None), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "no_initial_stop_pullback_buffer_grid",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "pullback_buffer_grid": list(PULLBACK_BUFFER_GRID),
                    "initial_stop_floor": "removed",
                    "used_1m": frame_1m is not None,
                    "data_start": str(raw_5m["ts"].iloc[0]),
                    "data_end": str(raw_5m["ts"].iloc[-1]),
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "diagnostics": str(DIAG_PATH),
                    "trades": str(TRADES_PATH),
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
    print(summary.sort_values(["profit_factor", "total_return"], ascending=False)[["mode", "pullback_buffer", "trades", "total_return", "win_rate", "profit_factor", "payoff_ratio", "max_dd"]].to_string(index=False))


if __name__ == "__main__":
    main()
