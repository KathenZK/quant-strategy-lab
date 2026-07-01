from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_2_atr_bracket_exit as v12  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.2"
RUN_DATE = "2026-06-30"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_2_atr_rvol_filter_ablation.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_rvol_filter_ablation_2026-06-30.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_rvol_filter_ablation_windows_2026-06-30.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_2_atr_rvol_filter_ablation_2026-06-30.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-2-atr-rvol-filter-ablation-2026-06-30.md"

V12_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1周", pd.Timedelta(days=7)),
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)


def filter_variants() -> list[dict[str, Any]]:
    baseline = v12.BASE_CONFIG.filter
    return [
        {
            "variant": "baseline",
            "description": "保留 ATR96 >= 0.75% 与 RVOL96 >= 1.0",
            "filter_spec": baseline,
        },
        {
            "variant": "remove_atr_min",
            "description": "去掉 ATR96 下限，只保留 ATR96 <= 2.80% 与 RVOL96 >= 1.0",
            "filter_spec": replace(baseline, min_atr_pct96=0.0),
        },
        {
            "variant": "remove_rvol",
            "description": "保留 ATR96 0.75%-2.80%，去掉 RVOL96 >= 1.0",
            "filter_spec": replace(baseline, min_rvol96=0.0),
        },
        {
            "variant": "remove_atr_min_and_rvol",
            "description": "去掉 ATR96 下限与 RVOL96 下限，只保留 ATR96 <= 2.80%",
            "filter_spec": replace(baseline, min_atr_pct96=0.0, min_rvol96=0.0),
        },
    ]


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = context.end_ts
    start_ts = context.start_ts if duration is None else max(context.start_ts, end_ts - duration)
    return start_ts, end_ts


def window_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return [trade for trade in trades if start_ts <= trade.entry_ts < end_ts]


def selected_trades(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return v1.selected_trades_live(window_trades(trades, start_ts, end_ts), filter_spec)


def net_returns_pct(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    picked = selected_trades(trades, filter_spec, start_ts, end_ts)
    return [
        float(v12.BASE_CONFIG.exposure * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in picked
    ]


def evaluate_metrics(
    *,
    trades: list[v12.EventTrade],
    filter_spec: Any,
    exit_spec: v12.ExitSpec,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=filter_spec,
        exposure=v12.BASE_CONFIG.exposure,
        period_days=period_days,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if result is None:
        return {
            "annual_return_pct": 0.0,
            "annual_equity_multiple": 1.0,
            "total_return_pct": 0.0,
            "max_drawdown_pct": 0.0,
            "win_rate_pct": 0.0,
            "trades": 0,
            "trades_per_day": 0.0,
            "profit_factor": 0.0,
        }
    metrics = asdict(result)
    if int(metrics["trades"]) == 0:
        metrics.update(
            {
                "annual_return_pct": 0.0,
                "annual_equity_multiple": 1.0,
                "total_return_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "win_rate_pct": 0.0,
                "trades": 0,
                "trades_per_day": 0.0,
                "profit_factor": 0.0,
            }
        )
    return metrics


def trade_risk_stats(net_returns: list[float], period_days: float, annual_return_pct: float, max_drawdown_pct: float) -> dict[str, float]:
    returns = np.array([value / 100.0 for value in net_returns], dtype="float64")
    trades_per_year = len(returns) / max(period_days, 1.0) * 365.25
    if len(returns) >= 2 and np.std(returns, ddof=1) > 0:
        sharpe = float(np.mean(returns) / np.std(returns, ddof=1) * np.sqrt(trades_per_year))
    else:
        sharpe = 0.0
    downside = returns[returns < 0]
    if len(downside) >= 2 and np.std(downside, ddof=1) > 0:
        sortino = float(np.mean(returns) / np.std(downside, ddof=1) * np.sqrt(trades_per_year))
    else:
        sortino = 0.0
    calmar = float(annual_return_pct / abs(max_drawdown_pct)) if max_drawdown_pct < 0 else 0.0
    return {
        "trade_sharpe": sharpe,
        "trade_sortino": sortino,
        "calmar": calmar,
        "avg_trade_pct": float(np.mean(net_returns)) if net_returns else 0.0,
        "median_trade_pct": float(np.median(net_returns)) if net_returns else 0.0,
        "best_trade_pct": float(np.max(net_returns)) if net_returns else 0.0,
        "worst_trade_pct": float(np.min(net_returns)) if net_returns else 0.0,
    }


def evaluate_row(
    *,
    variant: str,
    description: str,
    filter_spec: Any,
    trades: list[v12.EventTrade],
    exit_spec: v12.ExitSpec,
    entry_label: str,
    entry_delay_bars: int,
    window_name: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    metrics = evaluate_metrics(
        trades=trades,
        filter_spec=filter_spec,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    period_days = max((end_ts - start_ts).total_seconds() / 86_400.0, 0.0)
    returns = net_returns_pct(trades, filter_spec, start_ts, end_ts)
    stats = trade_risk_stats(
        returns,
        period_days,
        float(metrics["annual_return_pct"]),
        float(metrics["max_drawdown_pct"]),
    )
    return {
        "version": VERSION,
        "exit_label": V12_CANDIDATE.label,
        "variant": variant,
        "description": description,
        "entry_timing": entry_label,
        "entry_delay_bars": entry_delay_bars,
        "window": window_name,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "min_atr_pct96": float(filter_spec.min_atr_pct96),
        "max_atr_pct96": float(filter_spec.max_atr_pct96),
        "min_rvol96": float(filter_spec.min_rvol96),
        "annual_return_pct": float(metrics["annual_return_pct"]),
        "total_return_pct": float(metrics["total_return_pct"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
        "win_rate_pct": float(metrics["win_rate_pct"]),
        "trades": int(metrics["trades"]),
        "trades_per_day": float(metrics["trades_per_day"]),
        "profit_factor": float(metrics["profit_factor"]),
        **stats,
    }


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def comparison_table(rows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = rows.loc[rows["entry_timing"].eq(entry_timing)].copy()
    order = {
        "baseline": 0,
        "remove_atr_min": 1,
        "remove_rvol": 2,
        "remove_atr_min_and_rvol": 3,
    }
    subset["order"] = subset["variant"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {entry_timing} 全样本",
        "",
        "| 变体 | 交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['annual_return_pct'])}%` | `{fmt(row['max_drawdown_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['profit_factor'], 3)}` | "
            f"`{fmt(row['trade_sharpe'])}` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def windows_table(rows: pd.DataFrame, variant: str, entry_timing: str) -> list[str]:
    subset = rows.loc[
        rows["variant"].eq(variant) & rows["entry_timing"].eq(entry_timing)
    ].copy()
    order = {name: index for index, (name, _duration) in enumerate(WINDOWS)}
    subset["order"] = subset["window"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {variant} / {entry_timing}",
        "",
        "| 窗口 | 交易数 | 总收益 | 年化 | 最大回撤 | 胜率 | PF | Sharpe |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['annual_return_pct'])}%` | `{fmt(row['max_drawdown_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['profit_factor'], 3)}` | "
            f"`{fmt(row['trade_sharpe'])}` |"
        )
    return lines


def render_markdown(summary: pd.DataFrame, windows: pd.DataFrame, quality: dict[str, Any]) -> str:
    baseline = summary.loc[
        summary["variant"].eq("baseline") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    no_atr = summary.loc[
        summary["variant"].eq("remove_atr_min") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    no_rvol = summary.loc[
        summary["variant"].eq("remove_rvol") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    no_both = summary.loc[
        summary["variant"].eq("remove_atr_min_and_rvol") & summary["entry_timing"].eq("K+1")
    ].iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.2 ATR/RVOL 过滤消融 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`{ALIAS}`）",
        "",
        "## 结论",
        "",
        "`V1.2` 开单少，主要来自 `MACD + ATR 下限 + RVOL` 的共同收缩。本报告只消融 `ATR96 >= 0.75%` 和 `RVOL96 >= 1.0`，保持 RSI 信号、MACD 方向过滤、ATR bracket 出场、`2x` 暴露、成本和单仓状态机不变。",
        "",
        (
            f"- baseline K+1：`{int(baseline['trades'])}` 笔，总收益 `{fmt(baseline['total_return_pct'])}%`，"
            f"回撤 `{fmt(baseline['max_drawdown_pct'])}%`，胜率 `{fmt(baseline['win_rate_pct'])}%`。"
        ),
        (
            f"- 去 ATR 下限 K+1：`{int(no_atr['trades'])}` 笔，总收益 `{fmt(no_atr['total_return_pct'])}%`，"
            f"回撤 `{fmt(no_atr['max_drawdown_pct'])}%`，胜率 `{fmt(no_atr['win_rate_pct'])}%`。"
        ),
        (
            f"- 去 RVOL K+1：`{int(no_rvol['trades'])}` 笔，总收益 `{fmt(no_rvol['total_return_pct'])}%`，"
            f"回撤 `{fmt(no_rvol['max_drawdown_pct'])}%`，胜率 `{fmt(no_rvol['win_rate_pct'])}%`。"
        ),
        (
            f"- 两个都去掉 K+1：`{int(no_both['trades'])}` 笔，总收益 `{fmt(no_both['total_return_pct'])}%`，"
            f"回撤 `{fmt(no_both['max_drawdown_pct'])}%`，胜率 `{fmt(no_both['win_rate_pct'])}%`。"
        ),
        "",
        "状态：本消融只用于理解过滤器贡献，不改变 `NO-GO`。",
        "",
        "## 数据质量",
        "",
        f"- 覆盖：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`，quality gate `{quality['quality_gate_pass']}`。",
        "",
        "## 全样本对比",
        "",
    ]
    lines.extend(comparison_table(summary, "K+1"))
    lines.append("")
    lines.extend(comparison_table(summary, "K+2"))
    lines.extend(["", "## 固定窗口明细", ""])
    for variant in ("baseline", "remove_atr_min", "remove_rvol", "remove_atr_min_and_rvol"):
        lines.extend(windows_table(windows, variant, "K+1"))
        lines.append("")
        lines.extend(windows_table(windows, variant, "K+2"))
        lines.append("")
    lines.extend(
        [
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 窗口 CSV：`{WINDOW_CSV_PATH}`",
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
    summary_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for entry_delay_bars, entry_label in ENTRY_DELAYS:
        trades = v12.simulate_atr_bracket_trades(context, V12_CANDIDATE, entry_delay_bars)
        for item in filter_variants():
            variant = str(item["variant"])
            description = str(item["description"])
            filter_spec = item["filter_spec"]
            summary_rows.append(
                evaluate_row(
                    variant=variant,
                    description=description,
                    filter_spec=filter_spec,
                    trades=trades,
                    exit_spec=exit_spec,
                    entry_label=entry_label,
                    entry_delay_bars=entry_delay_bars,
                    window_name="全样本",
                    start_ts=context.start_ts,
                    end_ts=context.end_ts,
                )
            )
            for window_name, duration in WINDOWS:
                start_ts, end_ts = (
                    (context.start_ts, context.end_ts)
                    if duration is None
                    else (max(context.start_ts, context.end_ts - duration), context.end_ts)
                )
                window_rows.append(
                    evaluate_row(
                        variant=variant,
                        description=description,
                        filter_spec=filter_spec,
                        trades=trades,
                        exit_spec=exit_spec,
                        entry_label=entry_label,
                        entry_delay_bars=entry_delay_bars,
                        window_name=window_name,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )

    summary = pd.DataFrame(summary_rows)
    windows = pd.DataFrame(window_rows)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    payload = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "run_date": RUN_DATE,
        "status": "atr_rvol_filter_ablation_diagnostic_not_promoted",
        "metadata": metadata,
        "data_quality": quality,
        "base_config": asdict(v12.BASE_CONFIG),
        "v12_exit": asdict(V12_CANDIDATE),
        "filter_variants": [
            {
                "variant": item["variant"],
                "description": item["description"],
                "filter_spec": asdict(item["filter_spec"]),
            }
            for item in filter_variants()
        ],
        "summary": summary.to_dict(orient="records"),
        "outputs": {
            "script": str(SCRIPT_PATH),
            "summary_csv": str(SUMMARY_CSV_PATH),
            "window_csv": str(WINDOW_CSV_PATH),
            "markdown": str(MARKDOWN_PATH),
        },
    }
    JSON_PATH.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    MARKDOWN_PATH.write_text(render_markdown(summary, windows, quality), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"Wrote {SUMMARY_CSV_PATH}")
    print(f"Wrote {WINDOW_CSV_PATH}")
    print(f"Wrote {JSON_PATH}")
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
