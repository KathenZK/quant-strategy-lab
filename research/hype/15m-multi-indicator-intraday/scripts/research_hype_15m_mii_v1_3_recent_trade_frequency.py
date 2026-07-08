from __future__ import annotations

import json
import sys
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
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_recent_trade_frequency.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "research-notes"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_recent_trade_frequency_weekly_2026-07-08.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_recent_trade_frequency_windows_2026-07-08.csv"
TRADES_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_recent_trade_frequency_trades_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_recent_trade_frequency_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-recent-trade-frequency-2026-07-08.md"

V13_EXPOSURE = 2.5
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
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
) -> pd.DataFrame:
    raw_trades = v12.simulate_atr_bracket_trades(
        context,
        V13_CANDIDATE,
        entry_delay_bars=entry_delay_bars,
    )
    selected = v1.selected_trades_live(raw_trades, v12.BASE_CONFIG.filter)
    rows: list[dict[str, Any]] = []
    for trade in selected:
        entry_ts = pd.Timestamp(trade.entry_ts)
        rows.append(
            {
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
    for entry_label, group in trades.groupby("entry_timing", sort=True):
        group = group.copy()
        group["entry_ts_dt"] = pd.to_datetime(group["entry_ts"], utc=True)
        for window_name, duration in RECENT_WINDOWS:
            start_ts = context_end - duration
            subset = group.loc[(group["entry_ts_dt"] >= start_ts) & (group["entry_ts_dt"] < context_end)]
            returns = subset["net_return_pct"].astype(float).tolist()
            rows.append(
                {
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
    for entry_label, group in trades.groupby("entry_timing", sort=True):
        group = group.copy()
        group["entry_ts_dt"] = pd.to_datetime(group["entry_ts"], utc=True)
        group["week_start_dt"] = pd.to_datetime(group["week_start_utc"], utc=True)
        recent = group.loc[(group["entry_ts_dt"] >= start_ts) & (group["entry_ts_dt"] < context_end)]
        for week_start in week_starts:
            week_end = week_start + pd.Timedelta(days=7)
            subset = recent.loc[(recent["week_start_dt"] == week_start)]
            returns = subset["net_return_pct"].astype(float).tolist()
            rows.append(
                {
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


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def window_table(windows: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = windows.loc[windows["entry_timing"].eq(entry_timing)].copy()
    order = {name: index for index, (name, _duration) in enumerate(RECENT_WINDOWS)}
    subset["order"] = subset["window"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {entry_timing}",
        "",
        "| 窗口 | 交易数 | 平均每周 | 总收益 | 胜率 | 平均单笔 | 最差单笔 | 最后一笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['window']}` | `{int(row['trades'])}` | `{fmt(row['trades_per_week'], 2)}` | "
            f"`{fmt(row['total_return_pct'])}%` | `{fmt(row['win_rate_pct'])}%` | "
            f"`{fmt(row['avg_trade_pct'], 3)}%` | `{fmt(row['worst_trade_pct'], 3)}%` | "
            f"`{row['last_entry_ts'] or '-'}` |"
        )
    return lines


def weekly_table(weekly: pd.DataFrame, entry_timing: str) -> list[str]:
    subset = weekly.loc[weekly["entry_timing"].eq(entry_timing)].copy()
    lines = [
        f"### {entry_timing}",
        "",
        "| 周起点 UTC | 交易数 | 总收益 | 胜率 | 最后一笔 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in subset.to_dict(orient="records"):
        label = row["week_start_utc"][:10]
        if row["is_partial_start"] or row["is_partial_end"]:
            label = f"{label}*"
        lines.append(
            f"| `{label}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['win_rate_pct'])}%` | `{row['last_entry_ts'] or '-'}` |"
        )
    return lines


def render_markdown(
    windows: pd.DataFrame,
    weekly: pd.DataFrame,
    quality: dict[str, Any],
    context_end: pd.Timestamp,
) -> str:
    k1_90 = windows.loc[windows["entry_timing"].eq("K+1") & windows["window"].eq("最近90d")].iloc[0]
    k1_weekly = weekly.loc[weekly["entry_timing"].eq("K+1")]
    nonzero_weeks = int((k1_weekly["trades"] > 0).sum())
    total_weeks = int(len(k1_weekly))
    lines = [
        f"# HYPE-15M-MII V1.3 最近开单频率 {RUN_DATE}",
        "",
        "## 结论",
        "",
        (
            f"按当前 Binance futures public kline 已闭合 `15m` K，`V1.3` K+1 最近 `90d` "
            f"共 `{int(k1_90['trades'])}` 笔，折合 `{fmt(k1_90['trades_per_week'], 2)}` 笔/周。"
        ),
        (
            f"按自然周看，最近 `90d` 覆盖 `{total_weeks}` 个周桶，其中 `{nonzero_weeks}` 个周有交易、"
            f"`{total_weeks - nonzero_weeks}` 个周为 `0` 笔。"
        ),
        "因此这个策略本来就是低频；近期不是“每天都该开”，而是平均每周两三笔，且会出现连续数天到一周无单。",
        "",
        "## 固定窗口",
        "",
        *window_table(windows, "K+1"),
        "",
        *window_table(windows, "K+2"),
        "",
        "## 最近 90d 周度开单",
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
        f"- 周度 CSV：`{WEEKLY_CSV_PATH}`",
        f"- 固定窗口 CSV：`{WINDOW_CSV_PATH}`",
        f"- 逐笔 CSV：`{TRADES_CSV_PATH}`",
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

    frame = drought.fetch_recent_fapi_klines()
    quality = drought.data_quality(frame)
    if not quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(quality, ensure_ascii=False)}")
    context = drought.build_context(frame)
    context_end = pd.Timestamp(context.end_ts)
    trades = pd.concat(
        [
            selected_trade_rows(context, entry_delay_bars, entry_label)
            for entry_delay_bars, entry_label in ENTRY_DELAYS
        ],
        ignore_index=True,
    )
    windows = window_summary(trades, context_end)
    weekly = weekly_summary(trades, context_end)

    trades.to_csv(TRADES_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    weekly.to_csv(WEEKLY_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(render_markdown(windows, weekly, quality, context_end), encoding="utf-8")
    JSON_PATH.write_text(
        json.dumps(
            json_safe(
                {
                    "family": FAMILY,
                    "alias": ALIAS,
                    "version": VERSION,
                    "run_date": RUN_DATE,
                    "status": "recent_trade_frequency_diagnostic_not_promoted",
                    "recent_data_quality": quality,
                    "context_end": context_end,
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
    print("Windows")
    print(windows.to_string(index=False))
    print("Weekly K+1")
    print(weekly.loc[weekly["entry_timing"].eq("K+1")].to_string(index=False))
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
