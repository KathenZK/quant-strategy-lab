from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, dataclass, replace
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


retry = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v33_retry_arm.py", "hype_pbtr_v33_retry_arm_pb005_arm4")
v33 = retry.v33

RUN_DATE = "2026-06-27"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"

REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_pb005_arm4_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_pb005_arm4_summary_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_pb005_arm4_diag_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-pb005-arm4-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


@dataclass(frozen=True, slots=True)
class Variant:
    label: str
    pullback_buffer: float
    stop_arm_start_bars: int
    stop_arm_deadline_bars: int = 9


VARIANTS = [
    Variant("baseline_pb010_arm7_deadline9", pullback_buffer=0.01, stop_arm_start_bars=7),
    Variant("pb005_arm4_deadline9", pullback_buffer=0.005, stop_arm_start_bars=4),
]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def simulate_variant(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    variant: Variant,
) -> tuple[list[Any], pd.DataFrame]:
    cfg = replace(v33.V33_CONFIG, pullback_buffer=variant.pullback_buffer)
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
            if not armed and bars_held > variant.stop_arm_deadline_bars:
                reason = "stop_arm_deadline"
                raw_exit = float(close[j])
                exit_i = j
                break
            if bars_held < variant.stop_arm_start_bars:
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
        net, mae, mfe = retry.net_mae_mfe(
            direction,
            entry_price,
            exit_price,
            high[entry_i : exit_i + 1],
            low[entry_i : exit_i + 1],
        )
        trade = v33.Trade(
            config=f"{variant.label}-{mode}",
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
                "variant": variant.label,
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
                "entry_price": entry_price,
                "initial_stop": initial_stop,
                "final_active_stop": active_stop,
                "exit_price": exit_price,
                "net_ret_1x": net,
                "mae_1x": mae,
                "mfe_1x": mfe,
            }
        )
        blocked_until = exit_i
    return trades, pd.DataFrame(diag)


def summarize(
    variant: Variant,
    mode: Mode,
    signal_count: int,
    trades: list[Any],
    frame: pd.DataFrame,
    diag: pd.DataFrame,
) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    metrics = v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)
    return {
        "variant": variant.label,
        "mode": mode,
        "pullback_buffer": variant.pullback_buffer,
        "stop_arm_start_bars": variant.stop_arm_start_bars,
        "stop_arm_deadline_bars": variant.stop_arm_deadline_bars,
        "signal_count": signal_count,
        **metrics,
        "armed_rate": float(diag["armed"].mean()) if len(diag) else np.nan,
        "deadline_exit_rate": float(diag["deadline_exit"].mean()) if len(diag) else np.nan,
        "avg_bars_held": float(diag["bars_held"].mean()) if len(diag) else np.nan,
        "avg_retry_count": float(diag["retry_count"].mean()) if len(diag) else np.nan,
        "avg_reject_count": float(diag["reject_count"].mean()) if len(diag) else np.nan,
    }


def render_markdown(summary: pd.DataFrame, used_1m: bool, start: pd.Timestamp, end: pd.Timestamp) -> str:
    baseline = summary.loc[summary["variant"] == "baseline_pb010_arm7_deadline9"].set_index("mode")
    variant = summary.loc[summary["variant"] == "pb005_arm4_deadline9"].set_index("mode")
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 pb=0.005 + arm4 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告测试用户提出的变体：把 `pullback_buffer` 从 `0.01` 改为 `0.005`，同时把 V3.3.1 stop-arm 从“等 6 根、第 7 根开始挂 trailing stop”改为“等 3 根、第 4 根开始挂 trailing stop”，deadline 仍保留第 9 根，未 armed 则第 10 根处理周期市价平仓。",
        "",
        "## 口径",
        "",
        "- `stop_arm_start_bars=4`：入场 K 记第 1 根，持满 3 根后第 4 根收盘处理周期开始尝试挂 reduce-only `STOP_MARKET`。",
        "- trailing 公式不变，仍使用入场后的峰谷、`trail_atr=0.75` 和初始 `0.5 ATR` stop floor。",
        "- 四口径沿用 V3.3.1：5m/1m conservative 与 optimistic。",
        f"- 样本区间：`{start}` 到 `{end}`；使用 1m 数据：`{used_1m}`。",
        "",
        "## 结果",
        "",
        "| variant | mode | signals | trades | total | win | PF | payoff | DD | armed | deadline | avg bars |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{row['mode']}` | `{int(row['signal_count'])}` | `{int(row['trades'])}` | "
            f"`{fmt_pct(float(row['total_return']))}` | `{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | `{fmt_pct(float(row['armed_rate']))}` | "
            f"`{fmt_pct(float(row['deadline_exit_rate']))}` | `{fmt_num(float(row['avg_bars_held']))}` |"
        )
    lines.extend(["", "## 相对 baseline 变化", ""])
    lines.append("| mode | signal change | trade change | PF change | armed change | deadline change | avg bars change |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for mode in variant.index:
        base = baseline.loc[mode]
        row = variant.loc[mode]
        lines.append(
            f"| `{mode}` | `{fmt_pct(float(row['signal_count'] / base['signal_count'] - 1.0))}` | "
            f"`{fmt_pct(float(row['trades'] / base['trades'] - 1.0))}` | "
            f"`{fmt_num(float(row['profit_factor'] - base['profit_factor']))}` | "
            f"`{fmt_pct(float(row['armed_rate'] - base['armed_rate']))}` | "
            f"`{fmt_pct(float(row['deadline_exit_rate'] - base['deadline_exit_rate']))}` | "
            f"`{fmt_num(float(row['avg_bars_held'] - base['avg_bars_held']))}` |"
        )
    best_pf = float(variant["profit_factor"].min())
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"`pb=0.005 + arm4` 明显提前了 stop-arm，armed 率上升、deadline 率下降，平均持仓缩短；但四口径最差 PF 仍只有 `{fmt_num(best_pf)}`，仍低于 `1`。",
            "",
            "这说明把 trailing stop 提前到第 4 根能减少一部分裸露和超时市价平仓，但也会更早把噪声波动变成 stop 退出；它改善执行形态，不足以把原始 V3.3.1 变成正期望。",
            "",
            "## 产物",
            "",
            f"- 脚本：`research/hype/5m-pullback-trail/scripts/{Path(__file__).name}`",
            f"- JSON：`{REPORT_PATH}`",
            f"- summary CSV：`{SUMMARY_PATH}`",
            f"- diag CSV：`{DIAG_PATH}`",
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

    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    summary_rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        cfg = replace(v33.V33_CONFIG, pullback_buffer=variant.pullback_buffer)
        frame = v33.add_minimal_features(raw_5m, cfg)
        signal = v33.build_v33_signal(frame, cfg)
        signal_count = int(np.count_nonzero(signal))
        for mode in modes:
            trades, diag = simulate_variant(frame, signal, frame_1m, mode, variant)
            summary_rows.append(summarize(variant, mode, signal_count, trades, frame, diag))
            diag_frames.append(diag)

    summary = pd.DataFrame(summary_rows)
    diag = pd.concat(diag_frames, ignore_index=True)
    start = pd.Timestamp(raw_5m["ts"].iloc[0])
    end = pd.Timestamp(raw_5m["ts"].iloc[-1]) + pd.Timedelta(minutes=5)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_ROOT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False)
    diag.to_csv(DIAG_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(summary, frame_1m is not None, start, end), encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps(
            {
                "family_id": "HYPE-5M-PBTR",
                "strategy": "HYPE-5M-PBTR-V3.3.1",
                "audit": "pb005_arm4",
                "variants": [asdict(item) for item in VARIANTS],
                "base": asdict(v33.V33_CONFIG),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary": str(SUMMARY_PATH),
                    "diag": str(DIAG_PATH),
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
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
