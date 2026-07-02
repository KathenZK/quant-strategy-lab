from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from research_hype_ema_cross_strategy import SLIPPAGE, TRADE_COST
from research_hype_v13_late_reentry import run_late_reentry
from research_hype_v17_hybrid_ablation import (
    HybridCandidate,
    HybridSignalConfig,
    base_late_spec,
    hybrid_signal,
    load_frame,
    run_candidate,
    trade_attribution,
)
from research_hype_v17_trend_state_search import SignalPlan, build_signal


LEDGER_END = pd.Timestamp("2026-06-01 03:00:00+00:00")
REPORT_PATH = Path(
    "research/hype/15m-ema-crossover/diagnostics/"
    "hype-ema-x-v18-retest-and-rolling-windows-2026-07-01.md"
)
SUMMARY_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_x_v18_retest_summary_2026-07-01.csv")
ROLLING_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_x_v18_retest_rolling_windows_2026-07-01.csv")
TRADES_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_x_v18_retest_trades_2026-07-01.csv")
ATTRIBUTION_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_x_v18_retest_trade_attribution_2026-07-01.csv")
JSON_PATH = Path("research/hype/15m-ema-crossover/artifacts/hype_ema_x_v18_retest_2026-07-01.json")

FIXED_WINDOWS: dict[str, pd.Timedelta] = {
    "7D": pd.Timedelta(days=7),
    "30D": pd.Timedelta(days=30),
    "90D": pd.Timedelta(days=90),
    "180D": pd.Timedelta(days=180),
    "365D": pd.Timedelta(days=365),
}
ROLLING_WINDOWS: dict[str, pd.Timedelta] = {
    "30D": pd.Timedelta(days=30),
    "90D": pd.Timedelta(days=90),
    "180D": pd.Timedelta(days=180),
    "365D": pd.Timedelta(days=365),
}
ROLLING_STEP = pd.Timedelta(days=30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retest HYPE-EMA-X-V18 and rolling windows.")
    parser.add_argument(
        "--ledger-end",
        default=str(LEDGER_END),
        help="Inclusive UTC candle end for the ledger slice.",
    )
    parser.add_argument(
        "--rolling-step-days",
        type=int,
        default=30,
        help="Step size for rolling windows.",
    )
    return parser.parse_args()


def v18_candidate() -> HybridCandidate:
    return HybridCandidate(
        parameter="baseline",
        value="HYPE-EMA-X-V18",
        name="HYPE_EMA_X_V18",
        signal=HybridSignalConfig(),
        spec=base_late_spec("HYPE_EMA_X_V18"),
        hq_scale=1.1,
        lq_scale=1.0,
    )


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def row_from_result(
    *,
    label: str,
    result: dict[str, Any],
    counts: dict[str, int],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    window: str,
    kind: str,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "label": label,
        "window": window,
        "start_ts": str(start_ts),
        "end_ts": str(end_ts),
        "return": float(result["return"]),
        "max_dd": float(result["max_dd"]),
        "sharpe": float(result["sharpe"]),
        "trades": int(result["trades"]),
        "late_trades": int(result["late_trades"]),
        "win_rate": float(result["win_rate"]),
        "avg_trade_pct": float(result["avg_trade_pct"]),
        "median_trade_pct": float(result["median_trade_pct"]),
        "best_trade_pct": float(result["best_trade_pct"]),
        "worst_trade_pct": float(result["worst_trade_pct"]),
        "avg_hold_bars": float(result["avg_hold_bars"]),
        "exit_reasons": json.dumps(result["exit_reasons"], ensure_ascii=False, sort_keys=True),
        **counts,
    }


def run_v18_on_frame(
    frame: pd.DataFrame,
    candidate: HybridCandidate,
    base_signal,
    start_ts: pd.Timestamp,
    *,
    collect_trades: bool = False,
) -> tuple[dict[str, Any], dict[str, int]]:
    return run_candidate(frame, candidate, start_ts, base_signal, collect_trades=collect_trades)


def run_recent_windows(
    frame: pd.DataFrame,
    candidate: HybridCandidate,
    base_signal,
    ledger_end: pd.Timestamp,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, delta in FIXED_WINDOWS.items():
        start_ts = ledger_end - delta
        result, counts = run_v18_on_frame(frame, candidate, base_signal, start_ts)
        rows.append(
            row_from_result(
                label=f"recent_{label}",
                result=result,
                counts=counts,
                start_ts=start_ts,
                end_ts=ledger_end,
                window=label,
                kind="recent",
            )
        )
    return pd.DataFrame(rows)


def run_rolling_windows(
    frame: pd.DataFrame,
    candidate: HybridCandidate,
    base_signal,
    ledger_end: pd.Timestamp,
    step: pd.Timedelta,
) -> pd.DataFrame:
    ts = pd.to_datetime(frame.ts, utc=True)
    first_ts = pd.Timestamp(ts.iloc[0])
    rows: list[dict[str, Any]] = []
    for label, delta in ROLLING_WINDOWS.items():
        window_end = first_ts + delta
        while window_end <= ledger_end:
            window_frame = frame.loc[ts <= window_end].reset_index(drop=True)
            window_signal = base_signal[: len(window_frame)]
            start_ts = window_end - delta
            result, counts = run_v18_on_frame(window_frame, candidate, window_signal, start_ts)
            rows.append(
                row_from_result(
                    label=f"rolling_{label}_{window_end:%Y-%m-%d}",
                    result=result,
                    counts=counts,
                    start_ts=start_ts,
                    end_ts=window_end,
                    window=label,
                    kind="rolling",
                )
            )
            window_end += step
        if rows and rows[-1]["window"] == label and pd.Timestamp(rows[-1]["end_ts"]) < ledger_end:
            window_end = ledger_end
            window_frame = frame.loc[ts <= window_end].reset_index(drop=True)
            window_signal = base_signal[: len(window_frame)]
            start_ts = window_end - delta
            result, counts = run_v18_on_frame(window_frame, candidate, window_signal, start_ts)
            rows.append(
                row_from_result(
                    label=f"rolling_{label}_{window_end:%Y-%m-%d}",
                    result=result,
                    counts=counts,
                    start_ts=start_ts,
                    end_ts=window_end,
                    window=label,
                    kind="rolling",
                )
            )
    return pd.DataFrame(rows)


def rolling_summary(rolling: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window, group in rolling.groupby("window", sort=False):
        rows.append(
            {
                "window": window,
                "slices": int(len(group)),
                "positive_return_slices": int((group["return"] > 0).sum()),
                "negative_return_slices": int((group["return"] < 0).sum()),
                "median_return": float(group["return"].median()),
                "min_return": float(group["return"].min()),
                "max_return": float(group["return"].max()),
                "median_max_dd": float(group["max_dd"].median()),
                "worst_max_dd": float(group["max_dd"].min()),
                "median_trades": float(group["trades"].median()),
                "zero_trade_slices": int((group["trades"] == 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return "（无数据）"
    out = frame.loc[:, columns].copy()
    for column in ("return", "max_dd", "win_rate", "avg_trade_pct", "median_return", "min_return", "max_return", "median_max_dd", "worst_max_dd"):
        if column in out.columns:
            out[column] = out[column].map(lambda value: pct(float(value)))
    header = "| " + " | ".join(out.columns) + " |"
    divider = "| " + " | ".join("---" for _ in out.columns) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in out.astype(object).itertuples(index=False, name=None)
    ]
    return "\n".join([header, divider, *rows])


def write_report(
    *,
    ledger_end: pd.Timestamp,
    data_start: pd.Timestamp,
    data_end: pd.Timestamp,
    bars: int,
    baseline_row: dict[str, Any],
    recent: pd.DataFrame,
    rolling: pd.DataFrame,
    rolling_stats: pd.DataFrame,
    signal_counts: dict[str, int],
) -> None:
    report = "\n".join(
        [
            "# HYPE-EMA-X-V18 复测与滚动窗口回测 2026-07-01",
            "",
            "## 结论",
            "",
            f"- 数据切片：Binance HYPEUSDT perpetual `15m`，`{data_start}` 至 `{data_end}`，本次强制截断到 `{ledger_end}`，共 `{bars}` 根 K 线。",
            f"- 成本：`trade_cost={TRADE_COST}`，`slippage={SLIPPAGE}`；信号收盘确认、下一根 open 成交；1h 指标 resample 后 `shift(1)`。",
            f"- V18 基线 365D：收益 `{pct(float(baseline_row['return']))}`，最大回撤 `{pct(float(baseline_row['max_dd']))}`，胜率 `{pct(float(baseline_row['win_rate']))}`，交易 `{baseline_row['trades']}` 笔，late `{baseline_row['late_trades']}` 笔。",
            "- 状态仍为 `research candidate / not live-ready`；本复测不改变 live 审计结论。",
            "",
            "## V18 基线与最近窗口",
            "",
            markdown_table(
                pd.concat([pd.DataFrame([baseline_row]), recent], ignore_index=True),
                ["kind", "window", "return", "max_dd", "sharpe", "trades", "late_trades", "win_rate", "exit_reasons"],
            ),
            "",
            "## 滚动窗口汇总",
            "",
            markdown_table(
                rolling_stats,
                [
                    "window",
                    "slices",
                    "positive_return_slices",
                    "negative_return_slices",
                    "median_return",
                    "min_return",
                    "max_return",
                    "median_max_dd",
                    "worst_max_dd",
                    "median_trades",
                    "zero_trade_slices",
                ],
            ),
            "",
            "## 信号计数",
            "",
            "\n".join(f"- `{key}`: `{value}`" for key, value in signal_counts.items()),
            "",
            "## 保留证据",
            "",
            f"- 汇总 CSV：`../artifacts/{SUMMARY_PATH.name}`",
            f"- 滚动窗口 CSV：`../artifacts/{ROLLING_PATH.name}`",
            f"- 交易明细 CSV：`../artifacts/{TRADES_PATH.name}`",
            f"- 交易归因 CSV：`../artifacts/{ATTRIBUTION_PATH.name}`",
            f"- JSON：`../artifacts/{JSON_PATH.name}`",
            "",
            "## 注意事项",
            "",
            "- 滚动窗口使用固定步长向前推进；每个窗口只截取到该窗口终点之前的数据，避免窗口终点之后 K 线影响结果。",
            "- 低频策略的短窗口交易数很少，`7D/30D` 结果主要用于暴露空窗和路径风险，不应单独视为 promotion 证据。",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    ledger_end = pd.Timestamp(args.ledger_end)
    if ledger_end.tzinfo is None:
        ledger_end = ledger_end.tz_localize("UTC")
    else:
        ledger_end = ledger_end.tz_convert("UTC")
    step = pd.Timedelta(days=args.rolling_step_days)

    frame = load_frame()
    frame["ts"] = pd.to_datetime(frame.ts, utc=True)
    raw_data_start = pd.Timestamp(frame.ts.iloc[0])
    frame = frame.loc[frame.ts <= ledger_end].reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"no bars at or before {ledger_end}")
    data_start = pd.Timestamp(frame.ts.iloc[0])
    data_end = pd.Timestamp(frame.ts.iloc[-1])

    base_signal, _base_kind, signal_counts = build_signal(frame, SignalPlan("atr18_base", "atr18"))
    candidate = v18_candidate()
    baseline_start = ledger_end - pd.Timedelta(days=365)
    baseline_result, baseline_counts = run_v18_on_frame(
        frame,
        candidate,
        base_signal,
        baseline_start,
        collect_trades=True,
    )
    baseline_row = row_from_result(
        label="HYPE-EMA-X-V18",
        result=baseline_result,
        counts=baseline_counts,
        start_ts=baseline_start,
        end_ts=ledger_end,
        window="365D",
        kind="baseline",
    )
    recent = run_recent_windows(frame, candidate, base_signal, ledger_end)
    rolling = run_rolling_windows(frame, candidate, base_signal, ledger_end, step)
    rolling_stats = rolling_summary(rolling)
    trades = pd.DataFrame(baseline_result.get("trades_detail", []))
    attribution = trade_attribution(baseline_result)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([pd.DataFrame([baseline_row]), recent], ignore_index=True).to_csv(SUMMARY_PATH, index=False)
    rolling.to_csv(ROLLING_PATH, index=False)
    trades.to_csv(TRADES_PATH, index=False)
    attribution.to_csv(ATTRIBUTION_PATH, index=False)
    JSON_PATH.write_text(
        json.dumps(
            {
                "data": {
                    "raw_data_start": str(raw_data_start),
                    "data_start": str(data_start),
                    "data_end": str(data_end),
                    "ledger_end": str(ledger_end),
                    "bars": int(len(frame)),
                },
                "candidate": {
                    "name": candidate.name,
                    "signal": asdict(candidate.signal),
                    "late_spec": asdict(candidate.spec),
                    "hq_scale": candidate.hq_scale,
                    "lq_scale": candidate.lq_scale,
                },
                "costs": {"trade_cost": TRADE_COST, "slippage": SLIPPAGE},
                "signal_counts": signal_counts,
                "baseline": baseline_row,
                "recent_windows": recent.to_dict(orient="records"),
                "rolling_summary": rolling_stats.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    write_report(
        ledger_end=ledger_end,
        data_start=data_start,
        data_end=data_end,
        bars=len(frame),
        baseline_row=baseline_row,
        recent=recent,
        rolling=rolling,
        rolling_stats=rolling_stats,
        signal_counts=signal_counts,
    )
    print(f"summary={SUMMARY_PATH}")
    print(f"rolling={ROLLING_PATH}")
    print(f"trades={TRADES_PATH}")
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
