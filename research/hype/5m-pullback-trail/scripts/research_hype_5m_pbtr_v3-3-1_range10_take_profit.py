from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
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

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_range10_take_profit_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_range10_take_profit_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_range10_take_profit_trades_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_range10_take_profit_diagnostics_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-range10-take-profit-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def add_range10(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["range10"] = (result["high"] - result["low"]).rolling(10, min_periods=10).mean()
    return result


def target_touched(direction: int, target_price: float, high_price: float, low_price: float) -> bool:
    return high_price >= target_price if direction > 0 else low_price <= target_price


def one_minute_target_touched(
    frame_1m: pd.DataFrame | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    direction: int,
    target_price: float,
) -> bool:
    if frame_1m is None:
        return False
    rows = frame_1m.loc[(frame_1m["ts"] >= start) & (frame_1m["ts"] < end)]
    if rows.empty:
        return False
    if direction > 0:
        return bool((rows["high"].to_numpy("float64") >= target_price).any())
    return bool((rows["low"].to_numpy("float64") <= target_price).any())


def should_take_profit(
    mode: Mode,
    frame_1m: pd.DataFrame | None,
    bar_start: pd.Timestamp,
    direction: int,
    target_price: float,
    high_price: float,
    low_price: float,
) -> bool:
    if mode.startswith("1m_"):
        return one_minute_target_touched(
            frame_1m,
            bar_start,
            bar_start + pd.Timedelta(minutes=5),
            direction,
            target_price,
        )
    return target_touched(direction, target_price, high_price, low_price)


def simulate_range10_take_profit(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
) -> tuple[list[Any], pd.DataFrame]:
    cfg = v33.V33_CONFIG
    ts = pd.to_datetime(frame["ts"], utc=True)
    ts_ns = frame["_ts_ns"].to_numpy("int64")
    open_ = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    atr = frame["atr14"].to_numpy("float64")
    range10 = frame["range10"].to_numpy("float64")
    trades: list[Any] = []
    diag_rows: list[dict[str, Any]] = []
    blocked_until = -1

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= len(frame) or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        target_distance = float(range10[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0 or not np.isfinite(target_distance) or target_distance <= 0:
            continue

        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        target_price = entry_price + direction * target_distance
        initial_stop = entry_price - direction * cfg.stop_atr * signal_atr
        active_stop = initial_stop
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
            if should_take_profit(
                mode,
                frame_1m,
                pd.Timestamp(ts.iloc[j]),
                direction,
                target_price,
                float(high[j]),
                float(low[j]),
            ):
                reason = "range10_take_profit"
                raw_exit = float(target_price)
                exit_i = j
                break

            if armed:
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

            desired_stop = retry.trailed_stop(
                direction,
                entry_price,
                initial_stop,
                high[entry_i : j + 1],
                low[entry_i : j + 1],
                float(atr[j]),
                active_stop,
            )
            process_time = pd.Timestamp(ts.iloc[j]) + pd.Timedelta(minutes=5)
            can_arm, retry_points = retry.interval_can_arm(
                mode,
                direction,
                desired_stop,
                float(close[j]),
                float(high[j + 1]) if j + 1 < len(frame) else None,
                float(low[j + 1]) if j + 1 < len(frame) else None,
                retry.one_minute_rows(frame_1m, process_time, process_time + pd.Timedelta(minutes=5)),
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
        trade = v33.Trade(
            config=f"HYPE-5M-PBTR-V3.3.1-range10-take-profit-{mode}",
            signal_ts=pd.Timestamp(ts_ns[sig_i], unit="ns", tz="UTC"),
            entry_ts=pd.Timestamp(ts_ns[entry_i], unit="ns", tz="UTC"),
            exit_ts=pd.Timestamp(ts_ns[exit_i], unit="ns", tz="UTC"),
            side=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            reason=reason,
            bars_held=int(exit_i - entry_i + 1),
            net_ret_1x=float(net),
            mae_1x=float(mae),
            mfe_1x=float(mfe),
        )
        trades.append(trade)
        diag_rows.append(
            {
                "mode": mode,
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
                "target_distance": target_distance,
                "target_distance_bps": target_distance / entry_price * 10000.0,
                "entry_price": entry_price,
                "target_price": target_price,
                "initial_stop": initial_stop,
                "final_active_stop": active_stop,
                "exit_price": exit_price,
                "net_ret_1x": net,
                "mae_1x": mae,
                "mfe_1x": mfe,
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


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, used_1m: bool) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 range10 take-profit overlay 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试一个线上可执行的早停止盈 overlay：开仓后持续轮询，若浮盈已经达到信号 K 最近 10 根 5m K 的平均振幅，则立刻 reduce-only 市价平仓，不再进入后续 stop-arm / trailing 流程。",
        "",
        "回测近似：5m 口径用 5m OHLC 判断是否触达目标；1m 口径用本地 1m OHLC 判断是否触达目标。触达后按目标价再扣平仓滑点和手续费。",
        "",
        "注意：由于本地 1m 数据从 `2026-03-25` 才开始，本报告统一裁剪到 5m/1m 重叠区间，避免无 1m 覆盖的早期样本低估轮询触发率。",
        "",
        f"本次使用 1m 数据：`{used_1m}`。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 累计收益 | 年化 | 胜率 | PF | payoff | 最大回撤 | TP exit | deadline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt_pct(float(row['total_return']))}` | "
            f"`{fmt_mult(float(row['annualized_multiple']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_num(float(row['payoff_ratio']))}` | "
            f"`{fmt_pct(float(row['max_dd']))}` | `{fmt_pct(float(row.get('tp_exit_rate', 0.0)))}` | "
            f"`{fmt_pct(float(row.get('deadline_exit_rate', 0.0)))}` |"
        )
    lines.extend(["", "## 诊断", ""])
    for mode, group in diag.groupby("mode"):
        reasons = group["reason"].value_counts(normalize=True).to_dict()
        target_bps = group["target_distance_bps"].quantile([0.1, 0.5, 0.9]).to_dict()
        lines.append(
            f"- `{mode}`：TP exit `{fmt_pct(float(reasons.get('range10_take_profit', 0.0)))}`；deadline `{fmt_pct(float(reasons.get('stop_arm_deadline', 0.0)))}`；"
            f"stop-market `{fmt_pct(float(reasons.get('stop_market', 0.0)))}`；gap 市价 `{fmt_pct(float(reasons.get('gap_market_exit', 0.0)))}`；"
            f"target bps P10/P50/P90 `{fmt_num(float(target_bps[0.1]))}/{fmt_num(float(target_bps[0.5]))}/{fmt_num(float(target_bps[0.9]))}`。"
        )
    best = summary.sort_values(["profit_factor", "total_return"], ascending=False).iloc[0]
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"最佳口径为 `{best['label']}`：交易 `{int(best['trades'])}` 笔，累计收益 `{fmt_pct(float(best['total_return']))}`，PF `{fmt_num(float(best['profit_factor']))}`，最大回撤 `{fmt_pct(float(best['max_dd']))}`。",
            "",
            "range10 早停止盈把约一半交易提前平仓，胜率提升到约 `51%-53%`，但单笔平均赢利被压得过小，payoff 只有约 `0.50-0.54`。四个口径 PF 都只有约 `0.55-0.56`，总收益和最大回撤仍接近归零。",
            "",
            "结论：这个 5 秒轮询早停止盈 overlay 不能救回原始 V3.3.1。它更像是把尾部亏损换成大量过早止盈，改善胜率观感但破坏盈亏比。",
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
        min_ts = max(pd.Timestamp(raw_5m["ts"].iloc[0]), pd.Timestamp(frame_1m["ts"].iloc[0]).ceil("5min"))
        max_ts = min(pd.Timestamp(raw_5m["ts"].iloc[-1]), pd.Timestamp(frame_1m["ts"].iloc[-1]).floor("5min"))
        raw_5m = raw_5m.loc[(raw_5m["ts"] >= min_ts) & (raw_5m["ts"] <= max_ts)].reset_index(drop=True)
        frame_1m = frame_1m.loc[
            (frame_1m["ts"] >= raw_5m["ts"].iloc[0]) & (frame_1m["ts"] <= max_ts + pd.Timedelta(minutes=5))
        ].reset_index(drop=True)

    frame = add_range10(v33.add_minimal_features(raw_5m, v33.V33_CONFIG))
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    summary_rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    trade_rows: list[dict[str, Any]] = []
    for mode in modes:
        trades, diag = simulate_range10_take_profit(frame, signal, frame_1m, mode)
        diag_frames.append(diag)
        label = f"{mode}_range10_take_profit"
        summary_rows.append(
            summarize(
                label,
                trades,
                frame,
                {
                    "tp_exit_rate": float((diag["reason"] == "range10_take_profit").mean()) if len(diag) else 0.0,
                    "deadline_exit_rate": float((diag["reason"] == "stop_arm_deadline").mean()) if len(diag) else 0.0,
                },
            )
        )
        for i, trade in enumerate(trades, start=1):
            trade_rows.append(
                {
                    "mode": mode,
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
    MARKDOWN_PATH.write_text(render_markdown(summary, diag_all, frame_1m is not None), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "range10_take_profit_overlay",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "take_profit": "entry +/- rolling mean high-low over previous 10 closed 5m bars at signal bar",
                    "used_1m": frame_1m is not None,
                    "data_start": str(frame["ts"].iloc[0]),
                    "data_end": str(frame["ts"].iloc[-1]),
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
    print(summary[["label", "trades", "total_return", "win_rate", "profit_factor", "payoff_ratio", "max_dd", "tp_exit_rate"]].to_string(index=False))
    print(diag_all.groupby("mode")["reason"].value_counts(normalize=True).to_string())


if __name__ == "__main__":
    main()
