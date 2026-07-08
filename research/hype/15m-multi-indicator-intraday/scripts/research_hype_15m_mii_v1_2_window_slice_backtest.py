from __future__ import annotations

import json
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.2"
RUN_DATE = "2026-06-30"
RANDOM_SEED = 20260630
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_2_window_slice_backtest.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_window_slice_backtest_2026-06-30.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_window_slice_rolling_2026-06-30.csv"
RANDOM_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_window_slice_random_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_window_slice_backtest_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-2-window-slice-backtest-2026-06-30.md"

V12_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)

FIXED_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1周", pd.Timedelta(days=7)),
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)
ROLLING_DAYS = (30, 90, 180)
ROLLING_STEP_DAYS = 7
RANDOM_DAYS = (30, 90, 180)
RANDOM_SAMPLES_PER_DAYS = 80
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = context.end_ts
    start_ts = context.start_ts if duration is None else max(context.start_ts, end_ts - duration)
    return start_ts, end_ts


def selected_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return v12.selected_trades(trades, start_ts, end_ts)


def net_return_decimal(trade: v12.EventTrade) -> float:
    return float(v12.BASE_CONFIG.exposure * (trade.raw_return - v12.ROUND_TRIP_COST))


def risk_stats(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    max_drawdown_pct: float,
) -> dict[str, float]:
    picked = selected_trades(trades, start_ts, end_ts)
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 1.0)
    returns = np.array([net_return_decimal(trade) for trade in picked], dtype="float64")
    trades_per_year = len(returns) / period_days * 365.25
    if len(returns) >= 2 and float(np.std(returns, ddof=1)) > 0:
        sharpe = float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(trades_per_year))
    else:
        sharpe = 0.0
    downside = returns[returns < 0]
    if len(downside) >= 2 and float(np.std(downside, ddof=1)) > 0:
        sortino = float(np.mean(returns) / np.std(downside, ddof=1) * np.sqrt(trades_per_year))
    else:
        sortino = 0.0
    calmar = 0.0
    if max_drawdown_pct < 0:
        # annual_return_pct is added by the caller; this placeholder is replaced there.
        calmar = np.nan
    return {
        "trade_sharpe": sharpe,
        "trade_sortino": sortino,
        "trade_count_for_risk": int(len(returns)),
        "trades_per_year": float(trades_per_year),
        "avg_trade_pct": float(np.mean(returns) * 100.0) if len(returns) else 0.0,
        "median_trade_pct": float(np.median(returns) * 100.0) if len(returns) else 0.0,
        "best_trade_pct": float(np.max(returns) * 100.0) if len(returns) else 0.0,
        "worst_trade_pct": float(np.min(returns) * 100.0) if len(returns) else 0.0,
        "calmar": float(calmar),
    }


def evaluate_window_row(
    *,
    context: v12.evolution.EvalContext,
    trades: list[v12.EventTrade],
    exit_spec: v12.ExitSpec,
    entry_label: str,
    entry_delay_bars: int,
    window_type: str,
    window_name: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = v12.evaluate_metrics(
        context=context,
        trades=trades,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    stats = risk_stats(
        trades,
        start_ts,
        end_ts,
        float(metrics["max_drawdown_pct"]),
    )
    if float(metrics["max_drawdown_pct"]) < 0:
        stats["calmar"] = float(metrics["annual_return_pct"]) / abs(float(metrics["max_drawdown_pct"]))
    else:
        stats["calmar"] = 0.0
    row = {
        "version": VERSION,
        "label": V12_CANDIDATE.label,
        "window_type": window_type,
        "window": window_name,
        "entry_timing": entry_label,
        "entry_delay_bars": entry_delay_bars,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": max((end_ts - start_ts).total_seconds() / 86_400.0, 0.0),
        "atr_window": V12_CANDIDATE.atr_window,
        "tp_atr_mult": V12_CANDIDATE.tp_atr_mult,
        "sl_atr_mult": V12_CANDIDATE.sl_atr_mult,
        "max_hold_bars": V12_CANDIDATE.max_hold_bars,
        "exposure": v12.BASE_CONFIG.exposure,
        "annual_return_pct": float(metrics["annual_return_pct"]),
        "total_return_pct": float(metrics["total_return_pct"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
        "win_rate_pct": float(metrics["win_rate_pct"]),
        "trades": int(metrics["trades"]),
        "trades_per_day": float(metrics["trades_per_day"]),
        "profit_factor": float(metrics["profit_factor"]),
        **stats,
    }
    if extra:
        row.update(extra)
    return row


def rolling_windows(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp, dict[str, Any]]]:
    output: list[tuple[str, pd.Timestamp, pd.Timestamp, dict[str, Any]]] = []
    for days in ROLLING_DAYS:
        duration = pd.Timedelta(days=days)
        step = pd.Timedelta(days=ROLLING_STEP_DAYS)
        left = start_ts
        index = 0
        while left + duration <= end_ts:
            right = left + duration
            output.append(
                (
                    f"rolling_{days}d_{index:03d}_{left.strftime('%Y%m%d')}",
                    left,
                    right,
                    {"rolling_days": days, "slice_index": index},
                )
            )
            left += step
            index += 1
    return output


def random_windows(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp, dict[str, Any]]]:
    rng = random.Random(RANDOM_SEED)
    output: list[tuple[str, pd.Timestamp, pd.Timestamp, dict[str, Any]]] = []
    total_minutes = int((end_ts - start_ts).total_seconds() // 60)
    for days in RANDOM_DAYS:
        duration_minutes = days * 24 * 60
        max_start = max(total_minutes - duration_minutes, 0)
        for index in range(RANDOM_SAMPLES_PER_DAYS):
            offset_minutes = rng.randrange(0, max_start + 1, 15)
            left = start_ts + pd.Timedelta(minutes=offset_minutes)
            right = left + pd.Timedelta(minutes=duration_minutes)
            output.append(
                (
                    f"random_{days}d_{index:03d}_{left.strftime('%Y%m%d')}",
                    left,
                    right,
                    {"random_days": days, "slice_index": index, "random_seed": RANDOM_SEED},
                )
            )
    return output


def summary_by_group(rows: pd.DataFrame, window_type: str) -> pd.DataFrame:
    subset = rows.loc[rows["window_type"].eq(window_type)].copy()
    grouped = (
        subset.groupby(["entry_timing", "rolling_days" if window_type == "rolling" else "random_days"], dropna=False)
        .agg(
            slices=("window", "count"),
            positive_slices=("total_return_pct", lambda values: int((values > 0).sum())),
            median_total_return_pct=("total_return_pct", "median"),
            worst_total_return_pct=("total_return_pct", "min"),
            best_total_return_pct=("total_return_pct", "max"),
            median_max_drawdown_pct=("max_drawdown_pct", "median"),
            worst_max_drawdown_pct=("max_drawdown_pct", "min"),
            median_sharpe=("trade_sharpe", "median"),
            worst_sharpe=("trade_sharpe", "min"),
            median_trades=("trades", "median"),
        )
        .reset_index()
    )
    return grouped


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def fixed_table(rows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = rows.loc[
        rows["window_type"].eq("fixed") & rows["entry_timing"].eq(entry_timing)
    ].copy()
    order = {name: index for index, (name, _duration) in enumerate(FIXED_WINDOWS)}
    subset["order"] = subset["window"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {entry_timing}",
        "",
        "| 窗口 | 交易数 | 总收益 | 年化 | 回撤 | 胜率 | PF | Sharpe | Sortino | Calmar | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['annual_return_pct'])}%` | `{fmt(row['max_drawdown_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['profit_factor'], 3)}` | "
            f"`{fmt(row['trade_sharpe'], 2)}` | `{fmt(row['trade_sortino'], 2)}` | "
            f"`{fmt(row['calmar'], 2)}` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def aggregate_table(summary: pd.DataFrame, kind: str) -> list[str]:
    window_column = "rolling_days" if kind == "rolling" else "random_days"
    lines = [
        f"### {kind}",
        "",
        "| 入场 | 天数 | 切片数 | 正收益片数 | 中位总收益 | 最差总收益 | 最好总收益 | 中位回撤 | 最差回撤 | 中位 Sharpe | 最差 Sharpe | 中位交易数 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.to_dict(orient="records"):
        lines.append(
            f"| `{row['entry_timing']}` | `{int(row[window_column])}` | `{int(row['slices'])}` | "
            f"`{int(row['positive_slices'])}` | `{fmt(row['median_total_return_pct'])}%` | "
            f"`{fmt(row['worst_total_return_pct'])}%` | `{fmt(row['best_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_sharpe'], 2)}` | `{fmt(row['worst_sharpe'], 2)}` | "
            f"`{fmt(row['median_trades'], 1)}` |"
        )
    return lines


def render_markdown(
    fixed: pd.DataFrame,
    rolling_summary: pd.DataFrame,
    random_summary: pd.DataFrame,
    quality: dict[str, Any],
) -> str:
    k1_all = fixed.loc[
        fixed["entry_timing"].eq("K+1") & fixed["window"].eq("全样本")
    ].iloc[0]
    k2_all = fixed.loc[
        fixed["entry_timing"].eq("K+2") & fixed["window"].eq("全样本")
    ].iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.2 分窗口、滚动与随机切片回测 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "`HYPE-15M-MII-V1.2` 使用 `ATR96` 入场固定 bracket：`TP = 1.25 * ATR96%`、`SL = 5.0 * ATR96%`、`hold=24`，沿用 `V1.1` 的 RSI/MACD/ATR/RVOL 入场过滤、`2x` 暴露和 Binance 成本。",
        "",
        (
            f"- K+1 全样本：交易 `{int(k1_all['trades'])}` 笔，总收益 `{fmt(k1_all['total_return_pct'])}%`，"
            f"年化 `{fmt(k1_all['annual_return_pct'])}%`，回撤 `{fmt(k1_all['max_drawdown_pct'])}%`，"
            f"Sharpe `{fmt(k1_all['trade_sharpe'], 2)}`。"
        ),
        (
            f"- K+2 全样本：交易 `{int(k2_all['trades'])}` 笔，总收益 `{fmt(k2_all['total_return_pct'])}%`，"
            f"年化 `{fmt(k2_all['annual_return_pct'])}%`，回撤 `{fmt(k2_all['max_drawdown_pct'])}%`，"
            f"Sharpe `{fmt(k2_all['trade_sharpe'], 2)}`。"
        ),
        "- Sharpe/Sortino 使用交易净收益序列年化，净收益已包含 `2x` 暴露、手续费和滑点；资金费未计入。",
        "- 本报告仍是 diagnostic，不改变 `NO-GO` 状态。",
        "",
        "## 数据质量",
        "",
        f"- 覆盖：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`。",
        f"- gap `{quality['gap_count']}`，duplicate `{quality['normalized_duplicates']}`，critical null `{quality['critical_nulls']}`，invalid OHLC `{quality['invalid_ohlc_rows']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 固定窗口",
        "",
    ]
    lines.extend(fixed_table(fixed, "K+1"))
    lines.append("")
    lines.extend(fixed_table(fixed, "K+2"))
    lines.extend(["", "## 滚动窗口汇总", ""])
    lines.extend(aggregate_table(rolling_summary, "rolling"))
    lines.extend(["", "## 随机切片汇总", ""])
    lines.extend(aggregate_table(random_summary, "random"))
    lines.extend(
        [
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 固定窗口 CSV：`{WINDOW_CSV_PATH}`",
            f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
            f"- 随机切片 CSV：`{RANDOM_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [json_safe(child) for child in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def main() -> None:
    context, metadata, quality = v12.build_context()
    exit_spec = v12.candidate_exit_spec(V12_CANDIDATE)
    fixed_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    random_rows: list[dict[str, Any]] = []

    for entry_delay_bars, entry_label in ENTRY_DELAYS:
        trades = v12.simulate_atr_bracket_trades(context, V12_CANDIDATE, entry_delay_bars)
        for window_name, duration in FIXED_WINDOWS:
            start_ts, end_ts = window_bounds(context, duration)
            fixed_rows.append(
                evaluate_window_row(
                    context=context,
                    trades=trades,
                    exit_spec=exit_spec,
                    entry_label=entry_label,
                    entry_delay_bars=entry_delay_bars,
                    window_type="fixed",
                    window_name=window_name,
                    start_ts=start_ts,
                    end_ts=end_ts,
                )
            )
        for window_name, start_ts, end_ts, extra in rolling_windows(context.start_ts, context.end_ts):
            rolling_rows.append(
                evaluate_window_row(
                    context=context,
                    trades=trades,
                    exit_spec=exit_spec,
                    entry_label=entry_label,
                    entry_delay_bars=entry_delay_bars,
                    window_type="rolling",
                    window_name=window_name,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    extra=extra,
                )
            )
        for window_name, start_ts, end_ts, extra in random_windows(context.start_ts, context.end_ts):
            random_rows.append(
                evaluate_window_row(
                    context=context,
                    trades=trades,
                    exit_spec=exit_spec,
                    entry_label=entry_label,
                    entry_delay_bars=entry_delay_bars,
                    window_type="random",
                    window_name=window_name,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    extra=extra,
                )
            )

    fixed = pd.DataFrame(fixed_rows)
    rolling = pd.DataFrame(rolling_rows)
    random_slices = pd.DataFrame(random_rows)
    rolling_summary = summary_by_group(rolling, "rolling")
    random_summary = summary_by_group(random_slices, "random")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    fixed.to_csv(WINDOW_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    random_slices.to_csv(RANDOM_CSV_PATH, index=False)

    summary = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "run_date": RUN_DATE,
        "status": "window_slice_backtest_diagnostic_not_promoted",
        "metadata": metadata,
        "data_quality": quality,
        "base_config": asdict(v12.BASE_CONFIG),
        "v12_exit": asdict(V12_CANDIDATE),
        "risk_metric_note": "trade_sharpe/sortino are annualized from net per-trade returns including exposure, fees and slippage; funding not included",
        "fixed_windows": fixed.to_dict(orient="records"),
        "rolling_summary": rolling_summary.to_dict(orient="records"),
        "random_summary": random_summary.to_dict(orient="records"),
        "outputs": {
            "script": str(SCRIPT_PATH),
            "fixed_csv": str(WINDOW_CSV_PATH),
            "rolling_csv": str(ROLLING_CSV_PATH),
            "random_csv": str(RANDOM_CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(
        json.dumps(json_safe(summary), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(
        render_markdown(fixed, rolling_summary, random_summary, quality),
        encoding="utf-8",
    )
    print(fixed.to_string(index=False))
    print(f"Wrote {WINDOW_CSV_PATH}")
    print(f"Wrote {ROLLING_CSV_PATH}")
    print(f"Wrote {RANDOM_CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
