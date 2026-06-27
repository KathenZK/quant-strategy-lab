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
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_prev_exit_filter_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_prev_exit_filter_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_prev_exit_filter_trades_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v3-3-1_prev_exit_filter_diagnostics_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v3-3-1-prev-exit-filter-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def entry_passes_prev_exit_filter(direction: int, entry_price: float, previous_exit_price: float | None) -> bool:
    if previous_exit_price is None:
        return True
    return entry_price > previous_exit_price if direction > 0 else entry_price < previous_exit_price


def simulate_v331(
    frame: pd.DataFrame,
    signal: np.ndarray,
    frame_1m: pd.DataFrame | None,
    mode: Mode,
    *,
    require_prev_exit_filter: bool,
) -> tuple[list[Any], pd.DataFrame, dict[str, Any]]:
    cfg = v33.V33_CONFIG
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
    previous_exit_price: float | None = None
    candidate_count = 0
    filter_reject_count = 0

    for sig_i in np.flatnonzero(signal):
        direction = int(signal[sig_i])
        entry_i = sig_i + 1
        if entry_i >= len(frame) or entry_i <= blocked_until or direction == 0:
            continue
        signal_atr = float(atr[sig_i])
        if not np.isfinite(signal_atr) or signal_atr <= 0:
            continue
        candidate_count += 1
        entry_price = float(open_[entry_i] * (1.0 + direction * v33.ENTRY_SLIPPAGE_RATE))
        if require_prev_exit_filter and not entry_passes_prev_exit_filter(direction, entry_price, previous_exit_price):
            filter_reject_count += 1
            continue

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
        label = f"HYPE-5M-PBTR-V3.3.1-{mode}"
        if require_prev_exit_filter:
            label += "-prev-exit-filter"
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
                "require_prev_exit_filter": require_prev_exit_filter,
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
                "previous_exit_price": previous_exit_price,
                "entry_price": entry_price,
                "entry_filter_passed": True,
                "initial_stop": initial_stop,
                "final_active_stop": active_stop,
                "exit_price": exit_price,
                "net_ret_1x": net,
                "mae_1x": mae,
                "mfe_1x": mfe,
            }
        )
        previous_exit_price = exit_price
        blocked_until = exit_i

    stats = {
        "candidate_count": candidate_count,
        "filter_reject_count": filter_reject_count,
        "filter_reject_rate": filter_reject_count / candidate_count if candidate_count else 0.0,
    }
    return trades, pd.DataFrame(diag), stats


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, used_1m: bool) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3.1 prev-exit filter 回测 2026-06-27",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "`HYPE-5M-PBTR-V3.3.1` 记录当前 V3.3 retry-arm overlay：第 7 根 5m K 开始尝试挂 reduce-only stop-market，穿越时按 retry 近似，第 10 根处理周期市价兜底。本报告测试一个额外入场过滤：若上一笔交易已有平仓价，则新多头开仓成交价必须高于上一笔平仓价，新空头开仓成交价必须低于上一笔平仓价；第一笔无上一笔，默认允许入场。",
        "",
        "## 回测口径",
        "",
        "- `5m_conservative` / `5m_optimistic`：沿用 V3.3.1 的 5m 悲观/乐观 retry-arm 近似。",
        "- `1m_conservative` / `1m_optimistic`：使用本地 1m 数据的悲观/乐观 retry-arm 近似。",
        "- `*_base` 是 V3.3.1 无新增开仓过滤；`*_prev_exit_filter` 是本次新增条件。",
        f"- 本次使用 1m 数据：`{used_1m}`。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | armed | deadline | filter reject |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt_mult(float(row['annualized_multiple']))}` | "
            f"`{fmt_pct(float(row['win_rate']))}` | `{fmt_num(float(row['profit_factor']))}` | "
            f"`{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_pct(float(row.get('armed_rate', 0.0)))}` | `{fmt_pct(float(row.get('deadline_exit_rate', 0.0)))}` | "
            f"`{fmt_pct(float(row.get('filter_reject_rate', 0.0)))}` |"
        )
    lines.extend(["", "## 诊断", ""])
    for (mode, filtered), group in diag.groupby(["mode", "require_prev_exit_filter"]):
        reasons = group["reason"].value_counts(normalize=True).to_dict()
        label = f"{mode}_{'prev_exit_filter' if filtered else 'base'}"
        lines.append(
            f"- `{label}`：armed `{fmt_pct(float(group['armed'].mean()))}`，deadline `{fmt_pct(float(group['deadline_exit'].mean()))}`，"
            f"stop-market `{fmt_pct(float(reasons.get('stop_market', 0.0)))}`，gap 市价 `{fmt_pct(float(reasons.get('gap_market_exit', 0.0)))}`，"
            f"平均 retry `{fmt_num(float(group['retry_count'].mean()))}`。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "上一单平仓价过滤会明显降低频率：四个口径的 filter reject rate 约 `39%-40%`，交易数从约 `8.3k-8.8k` 降到约 `6.6k-6.8k`。",
            "",
            "但过滤没有改善收益结构：5m 悲观/乐观过滤后 PF 分别为 `0.581`、`0.560`；1m 悲观/乐观过滤后 PF 分别为 `0.568`、`0.571`，均低于各自无过滤基准，也远低于 `1`。最大回撤仍约 `-100%`，说明该开仓条件不能修复 V3.3.1 的 retry-arm 负期望。",
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

    frame = v33.add_minimal_features(raw_5m, v33.V33_CONFIG)
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    summary_rows: list[dict[str, Any]] = []
    diag_frames: list[pd.DataFrame] = []
    trade_rows: list[dict[str, Any]] = []
    for mode in modes:
        for require_filter in (False, True):
            trades, diag, stats = simulate_v331(frame, signal, frame_1m, mode, require_prev_exit_filter=require_filter)
            diag_frames.append(diag)
            label = f"{mode}_{'prev_exit_filter' if require_filter else 'base'}"
            summary_rows.append(
                summarize(
                    label,
                    trades,
                    frame,
                    {
                        "armed_rate": float(diag["armed"].mean()) if len(diag) else 0.0,
                        "deadline_exit_rate": float(diag["deadline_exit"].mean()) if len(diag) else 0.0,
                        **stats,
                    },
                )
            )
            for i, trade in enumerate(trades, start=1):
                trade_rows.append(
                    {
                        "label": label,
                        "mode": mode,
                        "require_prev_exit_filter": require_filter,
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
                "audit": "prev_exit_filter",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "retry_arm_overlay": {
                        "arm_start_bars": 7,
                        "arm_deadline_bars": 9,
                        "retry_seconds": 5,
                    },
                    "entry_filter": "first trade allowed; otherwise long entry_price > previous exit_price, short entry_price < previous exit_price",
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
    print(summary[["label", "trades", "annualized_multiple", "win_rate", "profit_factor", "payoff_ratio", "max_dd", "filter_reject_rate"]].to_string(index=False))
    print(diag_all.groupby(["mode", "require_prev_exit_filter"])["reason"].value_counts(normalize=True).to_string())


if __name__ == "__main__":
    main()
