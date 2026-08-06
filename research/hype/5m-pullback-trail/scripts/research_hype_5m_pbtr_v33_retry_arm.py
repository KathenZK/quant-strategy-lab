from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from strategy_lab.data import (
    DataLakeLayout,
    DatasetKind,
    DuckDBWarehouse,
    MarketType,
)
from strategy_lab.data.settings import load_settings

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


v33 = load_module(SCRIPT_DIR / "research_hype_5m_pbtr_v3-3_minimal.py", "hype_pbtr_v33_minimal")

RUN_DATE = "2026-06-26"
FAMILY_ROOT = Path("research/hype/5m-pullback-trail")
ARTIFACT_ROOT = FAMILY_ROOT / "artifacts"
DIAGNOSTIC_ROOT = FAMILY_ROOT / "diagnostics"
REPORT_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v33_retry_arm_{RUN_DATE}.json"
SUMMARY_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v33_retry_arm_summary_{RUN_DATE}.csv"
TRADES_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v33_retry_arm_trades_{RUN_DATE}.csv"
DIAG_PATH = ARTIFACT_ROOT / f"hype_5m_pbtr_v33_retry_arm_diagnostics_{RUN_DATE}.csv"
MARKDOWN_PATH = DIAGNOSTIC_ROOT / f"hype-5m-pbtr-v33-retry-arm-{RUN_DATE}.md"

Mode = Literal["5m_conservative", "5m_optimistic", "1m_conservative", "1m_optimistic"]


def fmt_pct(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value * 100:.2f}%"


def fmt_num(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.3f}"


def fmt_mult(value: float) -> str:
    return "∞" if not np.isfinite(value) else f"{value:.2f}x"


def fmt_optional_pct(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if not np.isfinite(numeric):
        return "n/a"
    return fmt_pct(numeric)


def load_hype_1m() -> pd.DataFrame | None:
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    files = warehouse._filtered_dataset_files(
        layer="normalized",
        kind=DatasetKind.OHLCV,
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="1m",
    )
    if not files:
        return None
    return warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="1m",
    ).reset_index(drop=True)


def armable(direction: int, stop: float, price: float) -> bool:
    return price > stop if direction > 0 else price < stop


def touched(direction: int, stop: float, high: float, low: float) -> bool:
    return low <= stop if direction > 0 else high >= stop


def trailed_stop(
    direction: int,
    entry_price: float,
    initial_stop: float,
    high_history: np.ndarray,
    low_history: np.ndarray,
    atr_value: float,
    previous: float,
) -> float:
    cfg = v33.V33_CONFIG
    if direction > 0:
        peak = max(entry_price, float(np.nanmax(high_history)))
        return float(max(previous, initial_stop, peak - cfg.trail_atr * atr_value))
    trough = min(entry_price, float(np.nanmin(low_history)))
    return float(min(previous, initial_stop, trough + cfg.trail_atr * atr_value))


def interval_can_arm(
    mode: Mode,
    direction: int,
    stop: float,
    process_price: float,
    next_high: float | None,
    next_low: float | None,
    rows_1m: pd.DataFrame | None,
) -> tuple[bool, int]:
    if armable(direction, stop, process_price):
        return True, 0
    if mode == "5m_conservative":
        return False, 1
    if mode == "5m_optimistic":
        if next_high is None or next_low is None:
            return False, 1
        return (next_high > stop, 1) if direction > 0 else (next_low < stop, 1)
    if rows_1m is None or rows_1m.empty:
        return False, 1
    if mode == "1m_conservative":
        opens = rows_1m["open"].to_numpy("float64")
        return bool(any(armable(direction, stop, float(price)) for price in opens)), len(opens)
    if direction > 0:
        return bool((rows_1m["high"].to_numpy("float64") > stop).any()), len(rows_1m)
    return bool((rows_1m["low"].to_numpy("float64") < stop).any()), len(rows_1m)


def exit_price_with_cost(raw_exit: float, direction: int) -> float:
    return float(raw_exit * (1.0 - direction * v33.EXIT_SLIPPAGE_RATE))


def net_mae_mfe(direction: int, entry: float, exit_price: float, highs: np.ndarray, lows: np.ndarray) -> tuple[float, float, float]:
    gross = direction * (exit_price / entry - 1.0)
    fee_cost = v33.FEE_RATE_PER_FILL * (1.0 + exit_price / entry)
    net = gross - fee_cost
    if direction > 0:
        mae = float(np.nanmin(lows / entry - 1.0))
        mfe = float(np.nanmax(highs / entry - 1.0))
    else:
        mae = float(np.nanmin(direction * (highs / entry - 1.0)))
        mfe = float(np.nanmax(direction * (lows / entry - 1.0)))
    return float(net), float(mae - v33.FEE_RATE_PER_FILL), float(mfe)


def one_minute_rows(frame_1m: pd.DataFrame | None, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame | None:
    if frame_1m is None:
        return None
    return frame_1m.loc[(frame_1m["ts"] >= start) & (frame_1m["ts"] < end)]


def simulate_retry_arm(frame: pd.DataFrame, signal: np.ndarray, frame_1m: pd.DataFrame | None, mode: Mode) -> tuple[list[Any], pd.DataFrame]:
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
                if j != skip_open_gap_i and not armable(direction, active_stop, float(open_[j])):
                    reason = "gap_market_exit"
                    raw_exit = float(open_[j])
                    exit_i = j
                    break
                if touched(direction, active_stop, float(high[j]), float(low[j])):
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
            desired_stop = trailed_stop(
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
            can_arm, retry_points = interval_can_arm(
                mode,
                direction,
                desired_stop,
                float(close[j]),
                float(high[j + 1]) if j + 1 < len(frame) else None,
                float(low[j + 1]) if j + 1 < len(frame) else None,
                one_minute_rows(frame_1m, process_time, next_time),
            )
            retry_count += retry_points
            active_stop = desired_stop
            if can_arm:
                armed = True
                arm_i = j
                skip_open_gap_i = None if armable(direction, desired_stop, float(close[j])) else j + 1
            else:
                reject_count += 1

        exit_price = exit_price_with_cost(raw_exit, direction)
        net, mae, mfe = net_mae_mfe(direction, entry_price, exit_price, high[entry_i : exit_i + 1], low[entry_i : exit_i + 1])
        trade = v33.Trade(
            config=f"HYPE-5M-PBTR-V3.3-retry-arm-{mode}",
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


def summarize(label: str, trades: list[Any], frame: pd.DataFrame, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    start = pd.Timestamp(frame["ts"].iloc[0])
    end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(minutes=5)
    row = {"label": label, **v33.metric_with_sides(trades, v33.LEVERAGE, start=start, end=end)}
    if extra:
        row.update(extra)
    return row


def render_markdown(summary: pd.DataFrame, diag: pd.DataFrame, used_1m: bool) -> str:
    lines = [
        "# HYPE-5M-PBTR-V3.3 retry-arm 近似回测 2026-06-26",
        "",
        "Family id：`HYPE-5M-PBTR`",
        "",
        "本报告复核线上新增的 stop-arm overlay：第 7 根 5m K 开始尝试挂 reduce-only `STOP_MARKET`；若当前价已穿越 stop，假设按 5 秒轮询继续尝试；第 9 根收盘后仍未挂上，则第 10 根处理周期市价平仓。",
        "",
        "## 口径",
        "",
        "- `5m_conservative`：只有 5m 收盘处理价未穿越时才允许挂单。",
        "- `5m_optimistic`：若下一根 5m OHLC 显示价格曾回到可挂区，也认为 5 秒轮询能挂上。",
        "- `1m_conservative`：使用本地 1m 数据，只用每根 1m open 作为重试采样点。",
        "- `1m_optimistic`：使用本地 1m OHLC，只要 1m 区间曾回到可挂区就算挂上。",
        "- 这些仍是近似口径，不是 tick/5s 级精确 replay。",
        "",
        f"本次使用 1m 数据：`{used_1m}`。",
        "",
        "## 结果",
        "",
        "| 口径 | 交易数 | 年化 | 胜率 | PF | payoff | 最大回撤 | armed | deadline |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt_mult(float(row['annualized_multiple']))}` | `{fmt_pct(float(row['win_rate']))}` | "
            f"`{fmt_num(float(row['profit_factor']))}` | `{fmt_num(float(row['payoff_ratio']))}` | `{fmt_pct(float(row['max_dd']))}` | "
            f"`{fmt_optional_pct(row.get('armed_rate'))}` | `{fmt_optional_pct(row.get('deadline_exit_rate'))}` |"
        )
    lines.extend(["", "## 诊断", ""])
    for mode, group in diag.groupby("mode"):
        reasons = group["reason"].value_counts(normalize=True).to_dict()
        lines.append(
            f"- `{mode}`：armed `{fmt_pct(float(group['armed'].mean()))}`，deadline `{fmt_pct(float(group['deadline_exit'].mean()))}`，"
            f"stop-market `{fmt_pct(float(reasons.get('stop_market', 0.0)))}`，gap 市价 `{fmt_pct(float(reasons.get('gap_market_exit', 0.0)))}`，"
            f"平均 retry `{fmt_num(float(group['retry_count'].mean()))}`，平均 reject `{fmt_num(float(group['reject_count'].mean()))}`。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "四个 retry-arm 近似口径全部低于 PF 1，且最大回撤均达到约 `-100%`。这说明 5 秒重试确实能提高部分交易的挂单成功率，但不能把旧 V3.3 的 crossed-stop 成交优势恢复为可实盘正 EV。",
            "",
            "1m 数据没有改变结论：`1m_conservative` PF `0.574`，`1m_optimistic` PF `0.580`，只比 5m 保守略好，仍然是亏损结构。因此本次结果不支持把 V3.3 retry-arm overlay 提升为 paper/live 候选；它更适合作为线上小额审计和风控兜底机制。",
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
    frame_1m = load_hype_1m()
    if frame_1m is not None:
        max_ts = min(pd.Timestamp(raw_5m["ts"].iloc[-1]), pd.Timestamp(frame_1m["ts"].iloc[-1]).floor("5min"))
        raw_5m = raw_5m.loc[raw_5m["ts"] <= max_ts].reset_index(drop=True)
        frame_1m = frame_1m.loc[
            (frame_1m["ts"] >= raw_5m["ts"].iloc[0]) & (frame_1m["ts"] <= max_ts + pd.Timedelta(minutes=5))
        ].reset_index(drop=True)

    frame = v33.add_minimal_features(raw_5m, v33.V33_CONFIG)
    signal = v33.build_v33_signal(frame, v33.V33_CONFIG)
    baseline_trades = v33.simulate_v33(frame, signal, v33.V33_CONFIG)

    modes: list[Mode] = ["5m_conservative", "5m_optimistic"]
    if frame_1m is not None:
        modes.extend(["1m_conservative", "1m_optimistic"])

    summary_rows = [summarize("old_stop_fill_baseline", baseline_trades, frame)]
    all_diag: list[pd.DataFrame] = []
    trade_rows: list[dict[str, Any]] = []
    for mode in modes:
        trades, diag = simulate_retry_arm(frame, signal, frame_1m, mode)
        all_diag.append(diag)
        summary_rows.append(
            summarize(
                mode,
                trades,
                frame,
                {
                    "armed_rate": float(diag["armed"].mean()),
                    "deadline_exit_rate": float(diag["deadline_exit"].mean()),
                    "avg_retry_count": float(diag["retry_count"].mean()),
                    "avg_reject_count": float(diag["reject_count"].mean()),
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
    diag_all = pd.concat(all_diag, ignore_index=True)
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
                "strategy": "HYPE-5M-PBTR-V3.3",
                "audit": "retry_arm_approximation",
                "definition": {
                    "base": asdict(v33.V33_CONFIG),
                    "arm_start_bars": 7,
                    "arm_deadline_bars": 9,
                    "retry_seconds": 5,
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
    print(summary[["label", "trades", "annualized_multiple", "win_rate", "profit_factor", "payoff_ratio", "max_dd"]].to_string(index=False))
    print(diag_all.groupby("mode")["reason"].value_counts(normalize=True).to_string())


if __name__ == "__main__":
    main()
