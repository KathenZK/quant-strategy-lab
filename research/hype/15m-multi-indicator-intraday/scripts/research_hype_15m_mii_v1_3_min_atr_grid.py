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
import research_hype_15m_mii_v1_3_signal_drought_diagnostic as drought  # noqa: E402
import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.3"
RUN_DATE = "2026-07-06"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_min_atr_grid.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
FIXED_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_min_atr_grid_fixed_2026-07-06.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_min_atr_grid_rolling_2026-07-06.csv"
ROLLING_SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_min_atr_grid_rolling_summary_2026-07-06.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_min_atr_grid_recent_api_2026-07-06.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_min_atr_grid_2026-07-06.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-min-atr-grid-2026-07-06.md"

MIN_ATR_GRID = (0.0050, 0.0055, 0.0060, 0.0065, 0.0070, 0.0075)
V13_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
FIXED_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近1周", pd.Timedelta(days=7)),
    ("最近1月", pd.Timedelta(days=30)),
    ("最近3月", pd.Timedelta(days=90)),
    ("最近6月", pd.Timedelta(days=182)),
    ("最近1年", pd.Timedelta(days=365)),
    ("全样本", None),
)
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("最近24h", pd.Timedelta(hours=24)),
    ("最近72h", pd.Timedelta(hours=72)),
    ("最近7d", pd.Timedelta(days=7)),
    ("最近15d", pd.Timedelta(days=15)),
    ("最近30d", pd.Timedelta(days=30)),
    ("最近90d", pd.Timedelta(days=90)),
)
ROLLING_DAYS = (30, 90, 180)
ROLLING_STEP_DAYS = 7
V13_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


def filter_for_min_atr(value: float) -> Any:
    return replace(v12.BASE_CONFIG.filter, min_atr_pct96=value)


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


def raw_pass_count(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> int:
    return sum(
        1
        for trade in window_trades(trades, start_ts, end_ts)
        if v1.passes_filter(trade, filter_spec)
    )


def net_returns_pct(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    return [
        float(V13_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in selected_trades(trades, filter_spec, start_ts, end_ts)
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
        exposure=V13_EXPOSURE,
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


def trade_stats(
    net_returns: list[float],
    period_days: float,
    annual_return_pct: float,
    max_drawdown_pct: float,
) -> dict[str, float]:
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
    dataset: str,
    trades: list[v12.EventTrade],
    filter_spec: Any,
    exit_spec: v12.ExitSpec,
    entry_label: str,
    entry_delay_bars: int,
    window_type: str,
    window_name: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    extra: dict[str, Any] | None = None,
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
    stats = trade_stats(
        returns,
        period_days,
        float(metrics["annual_return_pct"]),
        float(metrics["max_drawdown_pct"]),
    )
    row = {
        "dataset": dataset,
        "version": VERSION,
        "entry_timing": entry_label,
        "entry_delay_bars": entry_delay_bars,
        "window_type": window_type,
        "window": window_name,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "min_atr_pct96": float(filter_spec.min_atr_pct96),
        "min_atr_bps": int(round(float(filter_spec.min_atr_pct96) * 10_000)),
        "min_rvol96": float(filter_spec.min_rvol96),
        "max_atr_pct96": float(filter_spec.max_atr_pct96),
        "exposure": V13_EXPOSURE,
        "raw_pass_before_single_position": raw_pass_count(trades, filter_spec, start_ts, end_ts),
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


def rolling_specs(
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


def evaluate_context(
    *,
    dataset: str,
    context: v12.evolution.EvalContext,
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
    include_rolling: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    exit_spec = v12.candidate_exit_spec(V13_CANDIDATE)
    fixed_rows: list[dict[str, Any]] = []
    rolling_rows: list[dict[str, Any]] = []
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V13_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    for min_atr in MIN_ATR_GRID:
        filter_spec = filter_for_min_atr(min_atr)
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = raw_trades[entry_label]
            for window_name, duration in windows:
                start_ts, end_ts = window_bounds(context, duration)
                fixed_rows.append(
                    evaluate_row(
                        dataset=dataset,
                        trades=trades,
                        filter_spec=filter_spec,
                        exit_spec=exit_spec,
                        entry_label=entry_label,
                        entry_delay_bars=entry_delay_bars,
                        window_type="fixed",
                        window_name=window_name,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )
            if include_rolling:
                for window_name, start_ts, end_ts, extra in rolling_specs(context.start_ts, context.end_ts):
                    rolling_rows.append(
                        evaluate_row(
                            dataset=dataset,
                            trades=trades,
                            filter_spec=filter_spec,
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
    return pd.DataFrame(fixed_rows), pd.DataFrame(rolling_rows)


def rolling_summary(rolling: pd.DataFrame) -> pd.DataFrame:
    return (
        rolling.groupby(["dataset", "entry_timing", "min_atr_bps", "rolling_days"], dropna=False)
        .agg(
            slices=("window", "count"),
            positive_slices=("total_return_pct", lambda values: int((values > 0).sum())),
            median_total_return_pct=("total_return_pct", "median"),
            worst_total_return_pct=("total_return_pct", "min"),
            best_total_return_pct=("total_return_pct", "max"),
            median_max_drawdown_pct=("max_drawdown_pct", "median"),
            worst_max_drawdown_pct=("max_drawdown_pct", "min"),
            median_trades=("trades", "median"),
            zero_trade_slices=("trades", lambda values: int((values == 0).sum())),
            median_sharpe=("trade_sharpe", "median"),
            worst_sharpe=("trade_sharpe", "min"),
        )
        .reset_index()
    )


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def fixed_table(rows: pd.DataFrame, *, dataset: str, entry_timing: str, window: str) -> list[str]:
    subset = rows.loc[
        rows["dataset"].eq(dataset)
        & rows["entry_timing"].eq(entry_timing)
        & rows["window"].eq(window)
    ].sort_values("min_atr_bps")
    lines = [
        f"### {dataset} / {entry_timing} / {window}",
        "",
        "| ATR下限 | raw pass | 交易数 | 总收益 | 年化 | 回撤 | 胜率 | PF | Sharpe | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{int(row['min_atr_bps'])} bps` | `{int(row['raw_pass_before_single_position'])}` | "
            f"`{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['annual_return_pct'])}%` | `{fmt(row['max_drawdown_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['profit_factor'], 3)}` | "
            f"`{fmt(row['trade_sharpe'])}` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def rolling_table(summary: pd.DataFrame, *, entry_timing: str, rolling_days: int) -> list[str]:
    subset = summary.loc[
        summary["entry_timing"].eq(entry_timing) & summary["rolling_days"].eq(rolling_days)
    ].sort_values("min_atr_bps")
    lines = [
        f"### rolling {rolling_days}d / {entry_timing}",
        "",
        "| ATR下限 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 中位交易数 | 零交易切片 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{int(row['min_atr_bps'])} bps` | `{int(row['positive_slices'])}/{int(row['slices'])}` | "
            f"`{fmt(row['median_total_return_pct'])}%` | `{fmt(row['worst_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_trades'], 1)}` | `{int(row['zero_trade_slices'])}` |"
        )
    return lines


def render_markdown(
    fixed: pd.DataFrame,
    rolling_summary_frame: pd.DataFrame,
    recent: pd.DataFrame,
    lake_quality: dict[str, Any],
    recent_quality: dict[str, Any],
) -> str:
    k1_all = fixed.loc[
        fixed["dataset"].eq("standard_data_lake")
        & fixed["entry_timing"].eq("K+1")
        & fixed["window"].eq("全样本")
    ].sort_values("min_atr_bps")
    k2_all = fixed.loc[
        fixed["dataset"].eq("standard_data_lake")
        & fixed["entry_timing"].eq("K+2")
        & fixed["window"].eq("全样本")
    ].sort_values("min_atr_bps")
    baseline = k1_all.loc[k1_all["min_atr_bps"].eq(75)].iloc[0]
    best_k1 = k1_all.sort_values(["total_return_pct", "max_drawdown_pct"], ascending=[False, False]).iloc[0]
    best_k2 = k2_all.sort_values(["total_return_pct", "max_drawdown_pct"], ascending=[False, False]).iloc[0]
    recent_72 = recent.loc[
        recent["dataset"].eq("recent_binance_api")
        & recent["entry_timing"].eq("K+1")
        & recent["window"].eq("最近72h")
    ].sort_values("min_atr_bps")
    opening = recent_72.loc[recent_72["trades"].gt(0)]
    recent_note = (
        "最近 72h 所有网格仍没有最终交易。"
        if opening.empty
        else f"最近 72h 降到 `{int(opening.iloc[0]['min_atr_bps'])} bps` 后恢复交易，但窗口收益为 `{fmt(opening.iloc[0]['total_return_pct'])}%`。"
    )
    lines = [
        f"# HYPE-15M-MII V1.3 min_atr_pct96 网格诊断 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "本轮只调整 `min_atr_pct96`，其它 `V1.3` 条件保持不变：RSI/MACD/RVOL、`ATR96 TP=1.25x / SL=5x / hold=24`、Binance 成本和 `2.5x` 权益暴露。",
        "",
        (
            f"- 原 `75 bps` K+1 全样本 `{int(baseline['trades'])}` 笔、总收益 "
            f"`{fmt(baseline['total_return_pct'])}%`、回撤 `{fmt(baseline['max_drawdown_pct'])}%`。"
        ),
        (
            f"- K+1 全样本收益最高仍是 `{int(best_k1['min_atr_bps'])} bps`："
            f"总收益 `{fmt(best_k1['total_return_pct'])}%`、回撤 `{fmt(best_k1['max_drawdown_pct'])}%`。"
        ),
        (
            f"- K+2 全样本收益最高仍是 `{int(best_k2['min_atr_bps'])} bps`："
            f"总收益 `{fmt(best_k2['total_return_pct'])}%`、回撤 `{fmt(best_k2['max_drawdown_pct'])}%`。"
        ),
        f"- {recent_note}",
        "",
        "结论：降低到 `50-70 bps` 可以显著增加交易数，但全样本收益、K+2 稳健性和 recent API 最近窗口都明显差于 `75 bps`。当前不建议把 `75 bps` 直接下调；如果要继续研究，应把低 ATR regime 作为新版本重新搜索，而不是只改一个门槛。",
        "",
        "## 标准数据湖全样本",
        "",
        *fixed_table(fixed, dataset="standard_data_lake", entry_timing="K+1", window="全样本"),
        "",
        *fixed_table(fixed, dataset="standard_data_lake", entry_timing="K+2", window="全样本"),
        "",
        "## Recent API",
        "",
        *fixed_table(recent, dataset="recent_binance_api", entry_timing="K+1", window="最近72h"),
        "",
        *fixed_table(recent, dataset="recent_binance_api", entry_timing="K+1", window="最近7d"),
        "",
        *fixed_table(recent, dataset="recent_binance_api", entry_timing="K+1", window="最近30d"),
        "",
        "## 滚动窗口摘要",
        "",
        *rolling_table(rolling_summary_frame, entry_timing="K+1", rolling_days=30),
        "",
        *rolling_table(rolling_summary_frame, entry_timing="K+2", rolling_days=30),
        "",
        *rolling_table(rolling_summary_frame, entry_timing="K+1", rolling_days=90),
        "",
        *rolling_table(rolling_summary_frame, entry_timing="K+2", rolling_days=90),
        "",
        "## 数据质量",
        "",
        f"- Standard data lake：`{lake_quality['first_ts']}` 到 `{lake_quality['last_ts']}`，rows `{lake_quality['rows']}`，quality gate `{lake_quality['quality_gate_pass']}`。",
        f"- Recent Binance API：`{recent_quality['first_ts']}` 到 `{recent_quality['last_ts']}`，rows `{recent_quality['rows']}`，quality gate `{recent_quality['quality_gate_pass']}`。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 固定窗口 CSV：`{FIXED_CSV_PATH}`",
        f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
        f"- 滚动摘要 CSV：`{ROLLING_SUMMARY_CSV_PATH}`",
        f"- Recent API CSV：`{RECENT_CSV_PATH}`",
        f"- JSON：`{JSON_PATH}`",
    ]
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
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    lake_context, metadata, lake_quality = v12.build_context()
    fixed, rolling = evaluate_context(
        dataset="standard_data_lake",
        context=lake_context,
        windows=FIXED_WINDOWS,
        include_rolling=True,
    )
    rolling_summary_frame = rolling_summary(rolling)

    recent_frame = drought.fetch_recent_fapi_klines()
    recent_quality = drought.data_quality(recent_frame)
    if not recent_quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(recent_quality, ensure_ascii=False)}")
    recent_context = drought.build_context(recent_frame)
    recent, _recent_rolling = evaluate_context(
        dataset="recent_binance_api",
        context=recent_context,
        windows=RECENT_WINDOWS,
        include_rolling=False,
    )

    fixed.to_csv(FIXED_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    rolling_summary_frame.to_csv(ROLLING_SUMMARY_CSV_PATH, index=False)
    recent.to_csv(RECENT_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(fixed, rolling_summary_frame, recent, lake_quality, recent_quality),
        encoding="utf-8",
    )
    payload = {
        "family": FAMILY,
        "alias": ALIAS,
        "version": VERSION,
        "run_date": RUN_DATE,
        "status": "min_atr_grid_diagnostic_not_promoted",
        "metadata": metadata,
        "lake_data_quality": lake_quality,
        "recent_data_quality": recent_quality,
        "base_config": asdict(v12.BASE_CONFIG),
        "v13_exposure": V13_EXPOSURE,
        "min_atr_grid": list(MIN_ATR_GRID),
        "fixed": fixed.to_dict(orient="records"),
        "rolling_summary": rolling_summary_frame.to_dict(orient="records"),
        "recent_api": recent.to_dict(orient="records"),
        "outputs": {
            "markdown": str(MARKDOWN_PATH),
            "fixed_csv": str(FIXED_CSV_PATH),
            "rolling_csv": str(ROLLING_CSV_PATH),
            "rolling_summary_csv": str(ROLLING_SUMMARY_CSV_PATH),
            "recent_csv": str(RECENT_CSV_PATH),
        },
    }
    JSON_PATH.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print("Standard data lake / all sample")
    print(
        fixed.loc[fixed["window"].eq("全样本")]
        .sort_values(["entry_timing", "min_atr_bps"])
        .to_string(index=False)
    )
    print("Recent API K+1 72h")
    print(
        recent.loc[recent["entry_timing"].eq("K+1") & recent["window"].eq("最近72h")]
        .sort_values("min_atr_bps")
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
