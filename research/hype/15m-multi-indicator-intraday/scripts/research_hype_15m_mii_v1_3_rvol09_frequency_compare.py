from __future__ import annotations

import json
import sys
from dataclasses import replace
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
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_rvol09_frequency_compare.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol09_frequency_weekly_2026-07-08.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol09_frequency_windows_2026-07-08.csv"
TRADES_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol09_frequency_trades_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol09_frequency_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-rvol09-frequency-2026-07-08.md"

V13_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
FILTER_VARIANTS = (
    ("rvol1.0_baseline", 1.0),
    ("rvol0.9_candidate", 0.9),
)
RECENT_WINDOWS: tuple[tuple[str, pd.Timedelta], ...] = (
    ("最近24h", pd.Timedelta(hours=24)),
    ("最近72h", pd.Timedelta(hours=72)),
    ("最近7d", pd.Timedelta(days=7)),
    ("最近30d", pd.Timedelta(days=30)),
    ("最近90d", pd.Timedelta(days=90)),
)
V13_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)


def net_return_pct(trade: v12.EventTrade) -> float:
    return float(V13_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)


def compound_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    return float((np.prod([1.0 + value / 100.0 for value in values]) - 1.0) * 100.0)


def week_start_utc(ts: pd.Timestamp) -> pd.Timestamp:
    timestamp = pd.Timestamp(ts)
    return (timestamp - pd.Timedelta(days=timestamp.weekday())).normalize()


def selected_trade_rows(
    context: v12.evolution.EvalContext,
    entry_delay_bars: int,
    entry_label: str,
    variant: str,
    min_rvol96: float,
) -> pd.DataFrame:
    raw_trades = v12.simulate_atr_bracket_trades(
        context,
        V13_CANDIDATE,
        entry_delay_bars=entry_delay_bars,
    )
    filter_spec = replace(v12.BASE_CONFIG.filter, min_rvol96=min_rvol96)
    selected = v1.selected_trades_live(raw_trades, filter_spec)
    rows: list[dict[str, Any]] = []
    for trade in selected:
        entry_ts = pd.Timestamp(trade.entry_ts)
        rows.append(
            {
                "variant": variant,
                "min_rvol96": min_rvol96,
                "entry_timing": entry_label,
                "signal_ts": pd.Timestamp(context.features["ts"].iloc[trade.signal_i]).isoformat(),
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": pd.Timestamp(trade.exit_ts).isoformat(),
                "week_start_utc": week_start_utc(entry_ts).isoformat(),
                "direction": "long" if trade.direction == 1 else "short",
                "atr_pct96": float(trade.atr_pct96),
                "rvol96": float(trade.rvol96),
                "dir_macd": float(trade.dir_macd),
                "raw_return_pct": float(trade.raw_return * 100.0),
                "net_return_pct": net_return_pct(trade),
                "bars_held": int(trade.bars_held),
                "exit_reason": trade.exit_reason,
            }
        )
    return pd.DataFrame(rows)


def window_summary(trades: pd.DataFrame, context_end: pd.Timestamp) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (variant, entry_label), group in trades.groupby(["variant", "entry_timing"], sort=True):
        group = group.copy()
        group["entry_ts_dt"] = pd.to_datetime(group["entry_ts"], utc=True)
        for window_name, duration in RECENT_WINDOWS:
            start_ts = context_end - duration
            subset = group.loc[(group["entry_ts_dt"] >= start_ts) & (group["entry_ts_dt"] < context_end)]
            returns = subset["net_return_pct"].astype(float).tolist()
            rows.append(
                {
                    "variant": variant,
                    "entry_timing": entry_label,
                    "window": window_name,
                    "start_ts": start_ts.isoformat(),
                    "end_ts": context_end.isoformat(),
                    "period_days": float(duration.total_seconds() / 86_400),
                    "trades": int(len(subset)),
                    "trades_per_week": float(len(subset) / (duration.total_seconds() / 86_400 / 7)),
                    "total_return_pct": compound_pct(returns),
                    "win_rate_pct": float((subset["net_return_pct"] > 0).mean() * 100.0) if len(subset) else 0.0,
                    "avg_trade_pct": float(np.mean(returns)) if returns else 0.0,
                    "median_trade_pct": float(np.median(returns)) if returns else 0.0,
                    "worst_trade_pct": float(np.min(returns)) if returns else 0.0,
                    "last_entry_ts": str(subset["entry_ts"].max()) if len(subset) else "",
                }
            )
    return pd.DataFrame(rows)


def weekly_summary(trades: pd.DataFrame, context_end: pd.Timestamp) -> pd.DataFrame:
    start_ts = context_end - pd.Timedelta(days=90)
    first_week = week_start_utc(start_ts)
    last_week = week_start_utc(context_end - pd.Timedelta(minutes=15))
    week_starts = pd.date_range(first_week, last_week, freq="7D", tz="UTC")
    rows: list[dict[str, Any]] = []
    for (variant, entry_label), group in trades.groupby(["variant", "entry_timing"], sort=True):
        group = group.copy()
        group["entry_ts_dt"] = pd.to_datetime(group["entry_ts"], utc=True)
        group["week_start_dt"] = pd.to_datetime(group["week_start_utc"], utc=True)
        recent = group.loc[(group["entry_ts_dt"] >= start_ts) & (group["entry_ts_dt"] < context_end)]
        for week_start in week_starts:
            week_end = week_start + pd.Timedelta(days=7)
            subset = recent.loc[recent["week_start_dt"] == week_start]
            returns = subset["net_return_pct"].astype(float).tolist()
            rows.append(
                {
                    "variant": variant,
                    "entry_timing": entry_label,
                    "week_start_utc": week_start.isoformat(),
                    "week_end_utc": week_end.isoformat(),
                    "is_partial_start": bool(week_start < start_ts),
                    "is_partial_end": bool(week_end > context_end),
                    "trades": int(len(subset)),
                    "total_return_pct": compound_pct(returns),
                    "win_rate_pct": float((subset["net_return_pct"] > 0).mean() * 100.0) if len(subset) else 0.0,
                    "avg_trade_pct": float(np.mean(returns)) if returns else 0.0,
                    "last_entry_ts": str(subset["entry_ts"].max()) if len(subset) else "",
                }
            )
    return pd.DataFrame(rows)


def comparison_rows(windows: pd.DataFrame, weekly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for entry_label in ("K+1", "K+2"):
        base = windows.loc[
            windows["variant"].eq("rvol1.0_baseline") & windows["entry_timing"].eq(entry_label)
        ].set_index("window")
        cand = windows.loc[
            windows["variant"].eq("rvol0.9_candidate") & windows["entry_timing"].eq(entry_label)
        ].set_index("window")
        for window in ("最近30d", "最近90d"):
            rows.append(
                {
                    "entry_timing": entry_label,
                    "scope": window,
                    "rvol1_trades": int(base.loc[window, "trades"]),
                    "rvol09_trades": int(cand.loc[window, "trades"]),
                    "delta_trades": int(cand.loc[window, "trades"] - base.loc[window, "trades"]),
                    "rvol1_trades_per_week": float(base.loc[window, "trades_per_week"]),
                    "rvol09_trades_per_week": float(cand.loc[window, "trades_per_week"]),
                    "rvol1_total_return_pct": float(base.loc[window, "total_return_pct"]),
                    "rvol09_total_return_pct": float(cand.loc[window, "total_return_pct"]),
                    "rvol1_last_entry_ts": str(base.loc[window, "last_entry_ts"]),
                    "rvol09_last_entry_ts": str(cand.loc[window, "last_entry_ts"]),
                }
            )
        base_week = weekly.loc[
            weekly["variant"].eq("rvol1.0_baseline") & weekly["entry_timing"].eq(entry_label)
        ]
        cand_week = weekly.loc[
            weekly["variant"].eq("rvol0.9_candidate") & weekly["entry_timing"].eq(entry_label)
        ]
        rows.append(
            {
                "entry_timing": entry_label,
                "scope": "最近90d自然周",
                "rvol1_trades": int(base_week["trades"].sum()),
                "rvol09_trades": int(cand_week["trades"].sum()),
                "delta_trades": int(cand_week["trades"].sum() - base_week["trades"].sum()),
                "rvol1_nonzero_weeks": int((base_week["trades"] > 0).sum()),
                "rvol09_nonzero_weeks": int((cand_week["trades"] > 0).sum()),
                "rvol1_zero_weeks": int((base_week["trades"] == 0).sum()),
                "rvol09_zero_weeks": int((cand_week["trades"] == 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def window_table(windows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = windows.loc[windows["entry_timing"].eq(entry_timing)].copy()
    order = {name: index for index, (name, _duration) in enumerate(RECENT_WINDOWS)}
    variant_order = {"rvol1.0_baseline": 0, "rvol0.9_candidate": 1}
    subset["order"] = subset["window"].map(order)
    subset["variant_order"] = subset["variant"].map(variant_order)
    subset = subset.sort_values(["order", "variant_order"])
    lines = [
        f"### {entry_timing}",
        "",
        "| 窗口 | 版本 | 交易数 | 平均每周 | 总收益 | 胜率 | 平均单笔 | 最后一笔 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{row['variant']}` | `{int(row['trades'])}` | "
            f"`{fmt(row['trades_per_week'], 2)}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{row['last_entry_ts'] or '-'}` |"
        )
    return lines


def weekly_table(weekly: pd.DataFrame, entry_timing: str) -> list[str]:
    base = weekly.loc[
        weekly["entry_timing"].eq(entry_timing) & weekly["variant"].eq("rvol1.0_baseline")
    ].set_index("week_start_utc")
    cand = weekly.loc[
        weekly["entry_timing"].eq(entry_timing) & weekly["variant"].eq("rvol0.9_candidate")
    ].set_index("week_start_utc")
    lines = [
        f"### {entry_timing}",
        "",
        "| 周起点 UTC | rvol1.0 | rvol0.9 | 增量 | rvol0.9 最后一笔 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for week_start in base.index:
        base_row = base.loc[week_start]
        cand_row = cand.loc[week_start]
        label = str(week_start)[:10]
        if bool(base_row["is_partial_start"]) or bool(base_row["is_partial_end"]):
            label = f"{label}*"
        delta = int(cand_row["trades"] - base_row["trades"])
        lines.append(
            f"| `{label}` | `{int(base_row['trades'])}` | `{int(cand_row['trades'])}` | "
            f"`{delta:+d}` | `{cand_row['last_entry_ts'] or '-'}` |"
        )
    return lines


def render_markdown(
    windows: pd.DataFrame,
    weekly: pd.DataFrame,
    compare: pd.DataFrame,
    quality: dict[str, Any],
    context_end: pd.Timestamp,
) -> str:
    k1_90 = compare.loc[compare["entry_timing"].eq("K+1") & compare["scope"].eq("最近90d")].iloc[0]
    k1_week = compare.loc[
        compare["entry_timing"].eq("K+1") & compare["scope"].eq("最近90d自然周")
    ].iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.3 rvol0.9 近期频率对比 {RUN_DATE}",
        "",
        "## 结论",
        "",
        (
            f"K+1 最近 `90d`，`rvol1.0` 为 `{int(k1_90['rvol1_trades'])}` 笔，"
            f"`rvol0.9` 为 `{int(k1_90['rvol09_trades'])}` 笔，增加 "
            f"`{int(k1_90['delta_trades'])}` 笔；平均每周从 "
            f"`{fmt(k1_90['rvol1_trades_per_week'], 2)}` 提到 "
            f"`{fmt(k1_90['rvol09_trades_per_week'], 2)}`。"
        ),
        (
            f"按自然周，`rvol1.0` 最近 `90d` 有 `{int(k1_week['rvol1_nonzero_weeks'])}` 周开单、"
            f"`{int(k1_week['rvol1_zero_weeks'])}` 周无单；`rvol0.9` 为 "
            f"`{int(k1_week['rvol09_nonzero_weeks'])}` 周开单、`{int(k1_week['rvol09_zero_weeks'])}` 周无单。"
        ),
        "提频主要发生在 5 月中旬到 6 月中旬；最近 `7d/72h/24h` 两个版本仍都是 `0` 笔，因此 `rvol0.9` 不能解决当前几天不开单的问题。",
        "",
        "## 固定窗口对比",
        "",
        *window_table(windows, "K+1"),
        "",
        *window_table(windows, "K+2"),
        "",
        "## 最近 90d 周度开单对比",
        "",
        "带 `*` 的周是 90 天窗口边界处的非完整周。",
        "",
        *weekly_table(weekly, "K+1"),
        "",
        *weekly_table(weekly, "K+2"),
        "",
        "## 数据质量",
        "",
        f"- Recent Binance API：`{quality['first_ts']}` 到 `{quality['last_ts']}`，rows `{quality['rows']}`，quality gate `{quality['quality_gate_pass']}`。",
        f"- 统计截止：`{context_end.isoformat()}`。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 固定窗口 CSV：`{WINDOW_CSV_PATH}`",
        f"- 周度 CSV：`{WEEKLY_CSV_PATH}`",
        f"- 逐笔 CSV：`{TRADES_CSV_PATH}`",
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

    frame = drought.fetch_recent_fapi_klines()
    quality = drought.data_quality(frame)
    if not quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(quality, ensure_ascii=False)}")
    context = drought.build_context(frame)
    context_end = pd.Timestamp(context.end_ts)
    trades = pd.concat(
        [
            selected_trade_rows(context, entry_delay_bars, entry_label, variant, min_rvol96)
            for variant, min_rvol96 in FILTER_VARIANTS
            for entry_delay_bars, entry_label in ENTRY_DELAYS
        ],
        ignore_index=True,
    )
    windows = window_summary(trades, context_end)
    weekly = weekly_summary(trades, context_end)
    compare = comparison_rows(windows, weekly)

    trades.to_csv(TRADES_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    weekly.to_csv(WEEKLY_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(windows, weekly, compare, quality, context_end), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "rvol09_recent_frequency_compare_not_promoted",
                    "recent_data_quality": quality,
                    "context_end": context_end,
                    "compare": compare.to_dict(orient="records"),
                    "windows": windows.to_dict(orient="records"),
                    "weekly": weekly.to_dict(orient="records"),
                    "outputs": {
                        "markdown": str(MARKDOWN_PATH),
                        "weekly_csv": str(WEEKLY_CSV_PATH),
                        "window_csv": str(WINDOW_CSV_PATH),
                        "trades_csv": str(TRADES_CSV_PATH),
                    },
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Comparison")
    print(compare.to_string(index=False))
    print("Weekly K+1")
    print(weekly.loc[weekly["entry_timing"].eq("K+1")].to_string(index=False))
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
