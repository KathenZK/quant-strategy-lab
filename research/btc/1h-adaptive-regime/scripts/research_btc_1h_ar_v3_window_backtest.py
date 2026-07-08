from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import btc_1h_ar_v1 as v1  # noqa: E402
import btc_1h_ar_v3 as v3  # noqa: E402


FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-06"
SUMMARY_JSON = ARTIFACT_DIR / f"btc_1h_ar_v3_window_backtest_{DATE_TAG}.json"
WINDOWS_CSV = ARTIFACT_DIR / f"btc_1h_ar_v3_window_backtest_windows_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"btc_1h_ar_v3_window_backtest_trades_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"btc-1h-ar-v3-window-backtest-{DATE_TAG}.md"


def metric_row(
    engine: Any,
    trades: list[Any],
    *,
    name: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    group: str,
) -> dict[str, Any]:
    return {
        "group": group,
        "window": name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        **engine.metrics(trades, start, end),
    }


def fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def fmt_mult(value: float) -> str:
    return f"{value:.4f}x"


def table_lines(rows: list[dict[str, Any]], title: str) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Window | Start | End | Annual | Return | DD | Win | Trades | Long/Short |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['window']}` | `{row['start']}` | `{row['end']}` | "
            f"`{fmt_mult(row['annual_multiple'])}` | `{fmt_pct(row['total_return'])}` | "
            f"`{fmt_pct(row['max_dd'])}` | `{fmt_pct(row['win_rate'])}` | "
            f"`{int(row['trades'])}` | `{int(row['long_trades'])}/{int(row['short_trades'])}` |"
        )
    if not rows:
        lines.append("| - | - | - | - | - | - | - | - | - |")
    lines.append("")
    return lines


def monthly_rows(
    engine: Any,
    trades: list[Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = start
    while cursor < end:
        next_cursor = min(cursor + pd.DateOffset(months=1), end)
        rows.append(
            metric_row(
                engine,
                trades,
                name=cursor.strftime("%Y-%m"),
                start=cursor,
                end=next_cursor,
                group="monthly",
            )
        )
        cursor = next_cursor
    return rows


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    trades, _keltner, _cci, priorities = v3.simulate_v3(
        engine, frame, funding_times, funding_cumulative
    )

    canonical_specs = [
        ("train", v1.TRAIN_START, v1.TRAIN_END),
        ("validation", v1.TRAIN_END, v1.PREFIT_END),
        ("prefit", v1.TRAIN_START, v1.PREFIT_END),
        ("reused_holdout", v1.PREFIT_END, v1.FULL_END),
        ("current_full", v1.TRAIN_START, v1.FULL_END),
    ]
    recent_specs = [
        ("last_7d", v1.FULL_END - pd.Timedelta(days=7), v1.FULL_END),
        ("last_30d", v1.FULL_END - pd.Timedelta(days=30), v1.FULL_END),
        ("last_90d", v1.FULL_END - pd.Timedelta(days=90), v1.FULL_END),
        ("last_180d", v1.FULL_END - pd.Timedelta(days=180), v1.FULL_END),
        ("last_365d", v1.FULL_END - pd.Timedelta(days=365), v1.FULL_END),
    ]
    calendar_specs = [
        (
            "2024_partial",
            v1.TRAIN_START,
            pd.Timestamp("2025-01-01T00:00:00Z"),
        ),
        (
            "2025",
            pd.Timestamp("2025-01-01T00:00:00Z"),
            pd.Timestamp("2026-01-01T00:00:00Z"),
        ),
        (
            "2026_ytd",
            pd.Timestamp("2026-01-01T00:00:00Z"),
            v1.FULL_END,
        ),
    ]
    half_year_specs = [
        (
            "2024_H2_partial",
            v1.TRAIN_START,
            pd.Timestamp("2025-01-01T00:00:00Z"),
        ),
        (
            "2025_H1",
            pd.Timestamp("2025-01-01T00:00:00Z"),
            pd.Timestamp("2025-07-01T00:00:00Z"),
        ),
        (
            "2025_H2",
            pd.Timestamp("2025-07-01T00:00:00Z"),
            pd.Timestamp("2026-01-01T00:00:00Z"),
        ),
        (
            "2026_H1_plus",
            pd.Timestamp("2026-01-01T00:00:00Z"),
            v1.FULL_END,
        ),
    ]

    rows: list[dict[str, Any]] = []
    for group, specs in (
        ("canonical", canonical_specs),
        ("recent", recent_specs),
        ("calendar", calendar_specs),
        ("half_year", half_year_specs),
    ):
        for name, start, end in specs:
            rows.append(
                metric_row(engine, trades, name=name, start=start, end=end, group=group)
            )
    rows.extend(monthly_rows(engine, trades, v1.TRAIN_START, v1.FULL_END))
    rows_frame = pd.DataFrame(rows)
    rows_frame.to_csv(WINDOWS_CSV, index=False)
    pd.DataFrame(
        [
            {
                "signal_ts": trade.signal_ts,
                "entry_ts": trade.entry_ts,
                "exit_ts": trade.exit_ts,
                "side": trade.side,
                "entry_price": trade.entry_price,
                "exit_price": trade.exit_price,
                "exit_reason": trade.exit_reason,
                "bars_held": trade.bars_held,
                "exposure": trade.exposure,
                "equity_ret": trade.equity_ret,
                "equity_mae": trade.equity_mae,
            }
            for trade in trades
        ]
    ).to_csv(TRADES_CSV, index=False)

    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V3",
        "status": "window_backtest_diagnostic_not_live_ready",
        "date": DATE_TAG,
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "component_prefit_priority_scores": priorities,
        "windows": rows,
        "data_quality": quality,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    canonical_rows = [row for row in rows if row["group"] == "canonical"]
    recent_rows = [row for row in rows if row["group"] == "recent"]
    calendar_rows = [row for row in rows if row["group"] == "calendar"]
    half_year_rows = [row for row in rows if row["group"] == "half_year"]
    monthly_nonzero = [
        row
        for row in rows
        if row["group"] == "monthly" and int(row["trades"]) > 0
    ]
    worst_months = sorted(monthly_nonzero, key=lambda row: row["total_return"])[:8]
    best_months = sorted(
        monthly_nonzero, key=lambda row: row["total_return"], reverse=True
    )[:8]

    lines = [
        "# BTC-1H-Adaptive-Regime-V3 多窗口回测 - 2026-07-06",
        "",
        "## 结论",
        "",
        (
            "本报告只复用 V3 冻结参数和 2026-07-02 已固定两年闭合 `1h` 数据，"
            "不引入新增 forward 数据。所有窗口均使用 Binance `0.001` fee/fill、"
            "`4 bps` slippage/fill 和历史资金费。"
        ),
        "",
        (
            "年化倍率在短窗口中会被少数交易显著放大或压低，判断时优先同时看 "
            "`total_return`、`trades`、`max_dd` 和 `win_rate`。"
        ),
        "",
        *table_lines(canonical_rows, "Canonical Split"),
        *table_lines(recent_rows, "Recent Windows"),
        *table_lines(calendar_rows, "Calendar Windows"),
        *table_lines(half_year_rows, "Half-Year Windows"),
        "## 月度非零交易 Top/Bottom",
        "",
        "### Best Months",
        "",
        "| Month | Return | Annual | DD | Win | Trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in best_months:
        lines.append(
            f"| `{row['window']}` | `{fmt_pct(row['total_return'])}` | "
            f"`{fmt_mult(row['annual_multiple'])}` | `{fmt_pct(row['max_dd'])}` | "
            f"`{fmt_pct(row['win_rate'])}` | `{int(row['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "### Worst Months",
            "",
            "| Month | Return | Annual | DD | Win | Trades |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in worst_months:
        lines.append(
            f"| `{row['window']}` | `{fmt_pct(row['total_return'])}` | "
            f"`{fmt_mult(row['annual_multiple'])}` | `{fmt_pct(row['max_dd'])}` | "
            f"`{fmt_pct(row['win_rate'])}` | `{int(row['trades'])}` |"
        )
    lines.extend(
        [
            "",
            "## 选择边界",
            "",
            "- 本报告是 V3 的固定参数多窗口诊断，不做参数再选择。",
            "- reused holdout 已解锁；窗口结果只用于风险画像，不是新鲜 OOS。",
            "- V3 仍缺少新增 forward trades、production runner、重启恢复、交易所对账、missing-bar fail-closed、kill switch 和真实 stop-market 滑点证据。",
            "",
            "## 机器证据",
            "",
            f"- `artifacts/{SUMMARY_JSON.name}`",
            f"- `artifacts/{WINDOWS_CSV.name}`",
            f"- `artifacts/{TRADES_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v3_window_backtest.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
