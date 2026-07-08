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
RUN_DATE = "2026-07-08"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_rvol_grid_compare.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
STANDARD_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_grid_standard_2026-07-08.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_grid_rolling_2026-07-08.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_grid_recent_2026-07-08.csv"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_grid_weekly_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_grid_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-rvol-grid-2026-07-08.md"

V13_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
RVOL_GRID = (1.0, 0.9, 0.85, 0.8)
STANDARD_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
    ("全样本", None),
    ("最近90d", pd.Timedelta(days=90)),
    ("最近30d", pd.Timedelta(days=30)),
)
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta], ...] = (
    ("最近24h", pd.Timedelta(hours=24)),
    ("最近72h", pd.Timedelta(hours=72)),
    ("最近7d", pd.Timedelta(days=7)),
    ("最近30d", pd.Timedelta(days=30)),
    ("最近90d", pd.Timedelta(days=90)),
)
ROLLING_DAYS = (30, 90)
ROLLING_STEP_DAYS = 7
V13_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


def variant_label(min_rvol96: float) -> str:
    return f"rvol{min_rvol96:g}"


def filter_for_rvol(min_rvol96: float) -> Any:
    return replace(v12.BASE_CONFIG.filter, min_rvol96=min_rvol96)


def window_bounds(
    context: v12.evolution.EvalContext,
    duration: pd.Timedelta | None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    end_ts = pd.Timestamp(context.end_ts)
    if duration is None:
        return pd.Timestamp(context.start_ts), end_ts
    return max(pd.Timestamp(context.start_ts), end_ts - duration), end_ts


def window_trades(
    trades: list[v12.EventTrade],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[v12.EventTrade]:
    return [trade for trade in trades if start_ts <= pd.Timestamp(trade.entry_ts) < end_ts]


def net_returns_pct(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    picked = v1.selected_trades_live(window_trades(trades, start_ts, end_ts), filter_spec)
    return [
        float(V13_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in picked
    ]


def evaluate_row(
    *,
    dataset: str,
    trades: list[v12.EventTrade],
    filter_spec: Any,
    exit_spec: Any,
    min_rvol96: float,
    entry_label: str,
    window: str,
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
    returns = net_returns_pct(trades, filter_spec, start_ts, end_ts)
    metrics = {
        "annual_return_pct": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "win_rate_pct": 0.0,
        "trades": 0,
        "trades_per_day": 0.0,
        "profit_factor": 0.0,
    }
    if result is not None:
        metrics.update(asdict(result))
    return {
        "dataset": dataset,
        "variant": variant_label(min_rvol96),
        "min_rvol96": min_rvol96,
        "entry_timing": entry_label,
        "window": window,
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "period_days": period_days,
        "trades": int(metrics["trades"]),
        "trades_per_week": float(metrics["trades"]) / period_days * 7.0,
        "total_return_pct": float(metrics["total_return_pct"]),
        "annual_return_pct": float(metrics["annual_return_pct"]),
        "max_drawdown_pct": float(metrics["max_drawdown_pct"]),
        "win_rate_pct": float(metrics["win_rate_pct"]),
        "profit_factor": float(metrics["profit_factor"]),
        "avg_trade_pct": float(np.mean(returns)) if returns else 0.0,
        "median_trade_pct": float(np.median(returns)) if returns else 0.0,
        "worst_trade_pct": float(np.min(returns)) if returns else 0.0,
    }


def evaluate_fixed(
    *,
    dataset: str,
    context: v12.evolution.EvalContext,
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
) -> pd.DataFrame:
    exit_spec = v12.candidate_exit_spec(V13_CANDIDATE)
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V13_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    rows: list[dict[str, Any]] = []
    for min_rvol96 in RVOL_GRID:
        filter_spec = filter_for_rvol(min_rvol96)
        for _entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = raw_trades[entry_label]
            for window, duration in windows:
                start_ts, end_ts = window_bounds(context, duration)
                rows.append(
                    evaluate_row(
                        dataset=dataset,
                        trades=trades,
                        filter_spec=filter_spec,
                        exit_spec=exit_spec,
                        min_rvol96=min_rvol96,
                        entry_label=entry_label,
                        window=window,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )
    return pd.DataFrame(rows)


def rolling_summary(context: v12.evolution.EvalContext) -> pd.DataFrame:
    exit_spec = v12.candidate_exit_spec(V13_CANDIDATE)
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V13_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    rows: list[dict[str, Any]] = []
    for min_rvol96 in RVOL_GRID:
        filter_spec = filter_for_rvol(min_rvol96)
        for _entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = raw_trades[entry_label]
            for days in ROLLING_DAYS:
                duration = pd.Timedelta(days=days)
                step = pd.Timedelta(days=ROLLING_STEP_DAYS)
                left = pd.Timestamp(context.start_ts)
                returns: list[float] = []
                drawdowns: list[float] = []
                trade_counts: list[int] = []
                while left + duration <= pd.Timestamp(context.end_ts):
                    row = evaluate_row(
                        dataset="standard_data_lake",
                        trades=trades,
                        filter_spec=filter_spec,
                        exit_spec=exit_spec,
                        min_rvol96=min_rvol96,
                        entry_label=entry_label,
                        window=f"rolling_{days}d",
                        start_ts=left,
                        end_ts=left + duration,
                    )
                    returns.append(float(row["total_return_pct"]))
                    drawdowns.append(float(row["max_drawdown_pct"]))
                    trade_counts.append(int(row["trades"]))
                    left += step
                arr = np.array(returns)
                dd = np.array(drawdowns)
                counts = np.array(trade_counts)
                rows.append(
                    {
                        "variant": variant_label(min_rvol96),
                        "min_rvol96": min_rvol96,
                        "entry_timing": entry_label,
                        "rolling_days": days,
                        "slices": int(len(arr)),
                        "positive_slices": int((arr > 0).sum()) if len(arr) else 0,
                        "median_total_return_pct": float(np.median(arr)) if len(arr) else 0.0,
                        "worst_total_return_pct": float(arr.min()) if len(arr) else 0.0,
                        "median_max_drawdown_pct": float(np.median(dd)) if len(dd) else 0.0,
                        "worst_max_drawdown_pct": float(dd.min()) if len(dd) else 0.0,
                        "median_trades": float(np.median(counts)) if len(counts) else 0.0,
                        "zero_trade_slices": int((counts == 0).sum()) if len(counts) else 0,
                    }
                )
    return pd.DataFrame(rows)


def week_start_utc(ts: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(ts)
    return (timestamp - pd.Timedelta(days=timestamp.weekday())).normalize()


def recent_weekly(context: v12.evolution.EvalContext) -> pd.DataFrame:
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V13_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    context_end = pd.Timestamp(context.end_ts)
    start_ts = context_end - pd.Timedelta(days=90)
    first_week = week_start_utc(start_ts)
    last_week = week_start_utc(context_end - pd.Timedelta(minutes=15))
    week_starts = pd.date_range(first_week, last_week, freq="7D", tz="UTC")
    rows: list[dict[str, Any]] = []
    for min_rvol96 in RVOL_GRID:
        filter_spec = filter_for_rvol(min_rvol96)
        for _entry_delay_bars, entry_label in ENTRY_DELAYS:
            selected = v1.selected_trades_live(raw_trades[entry_label], filter_spec)
            for week_start in week_starts:
                week_end = week_start + pd.Timedelta(days=7)
                subset = [
                    trade
                    for trade in selected
                    if start_ts <= pd.Timestamp(trade.entry_ts) < context_end
                    and week_start <= week_start_utc(pd.Timestamp(trade.entry_ts)) < week_end
                ]
                returns = [
                    float(V13_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
                    for trade in subset
                ]
                rows.append(
                    {
                        "variant": variant_label(min_rvol96),
                        "min_rvol96": min_rvol96,
                        "entry_timing": entry_label,
                        "week_start_utc": week_start.isoformat(),
                        "week_end_utc": week_end.isoformat(),
                        "is_partial_start": bool(week_start < start_ts),
                        "is_partial_end": bool(week_end > context_end),
                        "trades": int(len(subset)),
                        "total_return_pct": compound_pct(returns),
                        "last_entry_ts": str(max((pd.Timestamp(t.entry_ts).isoformat() for t in subset), default="")),
                    }
                )
    return pd.DataFrame(rows)


def compound_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return float((np.prod([1.0 + value / 100.0 for value in values]) - 1.0) * 100.0)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def table_fixed(frame: pd.DataFrame, *, dataset: str, entry: str, window: str) -> list[str]:
    subset = frame.loc[
        frame["dataset"].eq(dataset) & frame["entry_timing"].eq(entry) & frame["window"].eq(window)
    ].sort_values("min_rvol96", ascending=False)
    lines = [
        f"### {dataset} / {entry} / {window}",
        "",
        "| RVOL下限 | 交易数 | 笔/周 | 总收益 | 回撤 | 胜率 | PF | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['min_rvol96']:.2f}` | `{int(row['trades'])}` | `{fmt(row['trades_per_week'], 2)}` | "
            f"`{fmt(row['total_return_pct'])}%` | `{fmt(row['max_drawdown_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['profit_factor'], 3)}` | "
            f"`{fmt(row['avg_trade_pct'], 3)}%` | `{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def table_rolling(rolling: pd.DataFrame, *, entry: str, days: int) -> list[str]:
    subset = rolling.loc[rolling["entry_timing"].eq(entry) & rolling["rolling_days"].eq(days)].sort_values(
        "min_rvol96", ascending=False
    )
    lines = [
        f"### {entry} / rolling {days}d",
        "",
        "| RVOL下限 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 中位交易数 | 零交易切片 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['min_rvol96']:.2f}` | `{int(row['positive_slices'])}/{int(row['slices'])}` | "
            f"`{fmt(row['median_total_return_pct'])}%` | `{fmt(row['worst_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_trades'], 1)}` | `{int(row['zero_trade_slices'])}` |"
        )
    return lines


def table_weekly(weekly: pd.DataFrame, *, entry: str) -> list[str]:
    subset = weekly.loc[weekly["entry_timing"].eq(entry)].copy()
    piv = subset.pivot(index="week_start_utc", columns="variant", values="trades").fillna(0).astype(int)
    lines = [
        f"### {entry}",
        "",
        "| 周起点 UTC | rvol1 | rvol0.9 | rvol0.85 | rvol0.8 |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for week_start, row in piv.iterrows():
        label = str(week_start)[:10]
        lines.append(
            f"| `{label}` | `{int(row.get('rvol1', 0))}` | `{int(row.get('rvol0.9', 0))}` | "
            f"`{int(row.get('rvol0.85', 0))}` | `{int(row.get('rvol0.8', 0))}` |"
        )
    return lines


def render_markdown(
    standard: pd.DataFrame,
    rolling: pd.DataFrame,
    recent: pd.DataFrame,
    weekly: pd.DataFrame,
    lake_quality: dict[str, Any],
    recent_quality: dict[str, Any],
) -> str:
    k1_all = standard.loc[
        standard["dataset"].eq("standard_data_lake")
        & standard["entry_timing"].eq("K+1")
        & standard["window"].eq("全样本")
    ].set_index("variant")
    k2_all = standard.loc[
        standard["dataset"].eq("standard_data_lake")
        & standard["entry_timing"].eq("K+2")
        & standard["window"].eq("全样本")
    ].set_index("variant")
    rvol08 = k1_all.loc["rvol0.8"]
    rvol085 = k1_all.loc["rvol0.85"]
    base = k1_all.loc["rvol1"]
    recent_90 = recent.loc[
        recent["dataset"].eq("recent_binance_api")
        & recent["entry_timing"].eq("K+1")
        & recent["window"].eq("最近90d")
    ].set_index("variant")
    lines = [
        f"# HYPE-15M-MII V1.3 RVOL 阈值定向对比 {RUN_DATE}",
        "",
        "## 结论",
        "",
        (
            f"`rvol0.85` K+1 全样本 `{int(rvol085['trades'])}` 笔，较 baseline `{int(base['trades'])}` 笔增加 "
            f"`{int(rvol085['trades'] - base['trades'])}` 笔；总收益 `{fmt(rvol085['total_return_pct'])}%`，"
            f"回撤 `{fmt(rvol085['max_drawdown_pct'])}%`。"
        ),
        (
            f"`rvol0.8` K+1 全样本 `{int(rvol08['trades'])}` 笔，增加 "
            f"`{int(rvol08['trades'] - base['trades'])}` 笔；总收益 `{fmt(rvol08['total_return_pct'])}%`，"
            f"回撤 `{fmt(rvol08['max_drawdown_pct'])}%`。"
        ),
        (
            f"但 K+2 全样本上，`rvol0.85` 总收益 `{fmt(k2_all.loc['rvol0.85', 'total_return_pct'])}%`、"
            f"回撤 `{fmt(k2_all.loc['rvol0.85', 'max_drawdown_pct'])}%`；`rvol0.8` 总收益 "
            f"`{fmt(k2_all.loc['rvol0.8', 'total_return_pct'])}%`、回撤 "
            f"`{fmt(k2_all.loc['rvol0.8', 'max_drawdown_pct'])}%`。`rvol0.85` 的 K+2 形状强于 `rvol0.9`，"
            "但 K+1 全样本回撤更深；`rvol0.8` 的额外交易没有带来足够增益。"
        ),
        (
            f"recent API K+1 最近 `90d`：`rvol1.0` `{int(recent_90.loc['rvol1', 'trades'])}` 笔，"
            f"`rvol0.9` `{int(recent_90.loc['rvol0.9', 'trades'])}` 笔，"
            f"`rvol0.85` `{int(recent_90.loc['rvol0.85', 'trades'])}` 笔，"
            f"`rvol0.8` `{int(recent_90.loc['rvol0.8', 'trades'])}` 笔。最近 `7d/72h/24h` 四个阈值仍均为 `0` 笔。"
        ),
        "",
        "结论：`0.85` 可列为进取观察候选，收益、K+2 和 recent 90d 都强，但代价是 K+1 全样本最大回撤从 baseline 的 `-22.01%` 扩到约 `-24.70%`；`0.9` 仍是更保守的观察候选。`0.8` 已经明显偏激进，新增交易不多、K+1 回撤和胜率退化，不建议替换 baseline。",
        "",
        "## 标准数据湖",
        "",
        *table_fixed(standard, dataset="standard_data_lake", entry="K+1", window="全样本"),
        "",
        *table_fixed(standard, dataset="standard_data_lake", entry="K+2", window="全样本"),
        "",
        *table_fixed(standard, dataset="standard_data_lake", entry="K+1", window="最近90d"),
        "",
        "## Recent API",
        "",
        *table_fixed(recent, dataset="recent_binance_api", entry="K+1", window="最近90d"),
        "",
        *table_fixed(recent, dataset="recent_binance_api", entry="K+1", window="最近30d"),
        "",
        "## 最近 90d 周度开单",
        "",
        *table_weekly(weekly, entry="K+1"),
        "",
        "## 滚动窗口",
        "",
        *table_rolling(rolling, entry="K+1", days=30),
        "",
        *table_rolling(rolling, entry="K+2", days=90),
        "",
        "## 数据质量",
        "",
        f"- Standard data lake：`{lake_quality['first_ts']}` 到 `{lake_quality['last_ts']}`，rows `{lake_quality['rows']}`，quality gate `{lake_quality['quality_gate_pass']}`。",
        f"- Recent Binance API：`{recent_quality['first_ts']}` 到 `{recent_quality['last_ts']}`，rows `{recent_quality['rows']}`，quality gate `{recent_quality['quality_gate_pass']}`。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 标准数据湖 CSV：`{STANDARD_CSV_PATH}`",
        f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
        f"- recent API CSV：`{RECENT_CSV_PATH}`",
        f"- 周度 CSV：`{WEEKLY_CSV_PATH}`",
        f"- JSON：`{JSON_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
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

    lake_context, lake_metadata, lake_quality = v12.build_context()
    standard = evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        windows=STANDARD_WINDOWS,
    )
    rolling = rolling_summary(lake_context)

    recent_frame = drought.fetch_recent_fapi_klines()
    recent_quality = drought.data_quality(recent_frame)
    if not recent_quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(recent_quality, ensure_ascii=False)}")
    recent_context = drought.build_context(recent_frame)
    recent = evaluate_fixed(
        dataset="recent_binance_api",
        context=recent_context,
        windows=tuple((name, duration) for name, duration in RECENT_WINDOWS),
    )
    weekly = recent_weekly(recent_context)

    standard.to_csv(STANDARD_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    recent.to_csv(RECENT_CSV_PATH, index=False)
    weekly.to_csv(WEEKLY_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(standard, rolling, recent, weekly, lake_quality, recent_quality),
        encoding="utf-8",
    )
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "rvol_grid_diagnostic_not_promoted",
                    "rvol_grid": RVOL_GRID,
                    "lake_metadata": lake_metadata,
                    "lake_quality": lake_quality,
                    "recent_quality": recent_quality,
                    "standard": standard.to_dict(orient="records"),
                    "rolling": rolling.to_dict(orient="records"),
                    "recent": recent.to_dict(orient="records"),
                    "weekly": weekly.to_dict(orient="records"),
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    key_cols = [
        "dataset",
        "variant",
        "entry_timing",
        "window",
        "trades",
        "trades_per_week",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate_pct",
    ]
    print("Standard all sample")
    print(
        standard.loc[standard["window"].eq("全样本")]
        .sort_values(["entry_timing", "min_rvol96"], ascending=[True, False])
        [key_cols]
        .to_string(index=False)
    )
    print("Recent K+1")
    print(
        recent.loc[recent["entry_timing"].eq("K+1")]
        .sort_values(["window", "min_rvol96"], ascending=[True, False])
        [key_cols]
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
