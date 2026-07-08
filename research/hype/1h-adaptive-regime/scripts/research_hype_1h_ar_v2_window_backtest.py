from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1_ablation  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402


DATE_TAG = "2026-07-02"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTE_DIR = FAMILY_DIR / "notes"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v2_window_backtest_{DATE_TAG}.json"
RECENT_WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_recent_windows_{DATE_TAG}.csv"
ROLLING_WINDOWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_rolling_windows_{DATE_TAG}.csv"
TRADES_CSV = ARTIFACT_DIR / f"hype_1h_ar_v2_window_backtest_trades_{DATE_TAG}.csv"
REPORT_MD = NOTE_DIR / f"hype-1h-ar-v2-window-backtest-{DATE_TAG}.md"


def selected_trades(
    trades: list[base.Trade], start: pd.Timestamp, end: pd.Timestamp
) -> list[base.Trade]:
    return [trade for trade in trades if start <= trade.entry_ts < end]


def window_row(
    *,
    kind: str,
    window: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    trades: list[base.Trade],
) -> dict[str, Any]:
    values = base.metrics(trades, start, end)
    selected = selected_trades(trades, start, end)
    wins = sum(trade.equity_ret > 0 for trade in selected)
    losses = sum(trade.equity_ret < 0 for trade in selected)
    flats = len(selected) - wins - losses
    return {
        "kind": kind,
        "window": window,
        "start": start,
        "end": end,
        "wins": wins,
        "losses": losses,
        "flat_trades": flats,
        **values,
    }


def recent_window_defs(
    train_start: pd.Timestamp, full_end: pd.Timestamp
) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    requested = [
        ("last_7d", 7),
        ("last_30d", 30),
        ("last_90d", 90),
        ("last_180d", 180),
        ("last_365d", 365),
    ]
    windows = [("current_full", train_start, full_end)]
    windows.extend(
        (label, max(train_start, full_end - pd.Timedelta(days=days)), full_end)
        for label, days in requested
    )
    return windows


def rolling_window_defs(
    train_start: pd.Timestamp, full_end: pd.Timestamp
) -> list[tuple[str, str, pd.Timestamp, pd.Timestamp]]:
    definitions: list[tuple[str, int, int]] = [
        ("rolling_7d_step7d", 7, 7),
        ("rolling_30d_step30d", 30, 30),
        ("rolling_90d_step30d", 90, 30),
        ("rolling_180d_step30d", 180, 30),
    ]
    output: list[tuple[str, str, pd.Timestamp, pd.Timestamp]] = []
    for kind, window_days, step_days in definitions:
        cursor = train_start
        index = 1
        width = pd.Timedelta(days=window_days)
        step = pd.Timedelta(days=step_days)
        while cursor + width <= full_end:
            output.append((kind, f"{kind}_{index:03d}", cursor, cursor + width))
            cursor += step
            index += 1
    return output


def pct(value: float) -> str:
    if not math.isfinite(value):
        return "inf"
    return f"{value * 100:.2f}%"


def mult(value: float) -> str:
    if not math.isfinite(value):
        return "inf"
    return f"{value:.4f}x"


def fmt_ts(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M UTC")


def markdown_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Window | UTC range | Days | Trades | Win rate | Total return | Max DD | Annual multiple |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['window']}`",
                    f"{fmt_ts(row['start'])} -> {fmt_ts(row['end'])}",
                    f"{row['days']:.1f}",
                    str(int(row["trades"])),
                    pct(float(row["win_rate"])),
                    pct(float(row["total_return"])),
                    pct(float(row["max_dd"])),
                    mult(float(row["annual_multiple"])),
                ]
            )
            + " |"
        )
    return lines


def rolling_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frame = pd.DataFrame(rows)
    summaries: list[dict[str, Any]] = []
    for kind, group in frame.groupby("kind", sort=False):
        nonzero = group[group["trades"] > 0]
        summaries.append(
            {
                "kind": kind,
                "windows": int(len(group)),
                "zero_trade_windows": int((group["trades"] == 0).sum()),
                "positive_windows": int((group["total_return"] > 0).sum()),
                "median_trades": float(group["trades"].median()),
                "min_trades": int(group["trades"].min()),
                "max_trades": int(group["trades"].max()),
                "median_win_rate_nonzero": float(nonzero["win_rate"].median())
                if len(nonzero)
                else 0.0,
                "worst_total_return": float(group["total_return"].min()),
                "best_total_return": float(group["total_return"].max()),
            }
        )
    return summaries


def rolling_summary_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Rolling slice | Windows | Zero-trade | Positive | Trades median/min/max | Median win rate | Worst/Best return |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{row['kind']}`",
                    str(row["windows"]),
                    str(row["zero_trade_windows"]),
                    str(row["positive_windows"]),
                    f"{row['median_trades']:.1f}/{row['min_trades']}/{row['max_trades']}",
                    pct(float(row["median_win_rate_nonzero"])),
                    f"{pct(float(row['worst_total_return']))} / {pct(float(row['best_total_return']))}",
                ]
            )
            + " |"
        )
    return lines


def report_markdown(
    *,
    quality: dict[str, Any],
    train_start: pd.Timestamp,
    full_end: pd.Timestamp,
    recent_rows: list[dict[str, Any]],
    rolling_rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> str:
    current = next(row for row in recent_rows if row["window"] == "current_full")
    last_year = next(row for row in recent_rows if row["window"] == "last_365d")
    lines = [
        "# HYPE-1H-Adaptive-Regime-V2 窗口/滚动切片复核 - 2026-07-02",
        "",
        "## 结论",
        "",
        (
            f"- 本次复核不改变 `HYPE-1H-Adaptive-Regime-V2` 状态："
            f"`NO-GO / not live-ready / not promoted`。"
        ),
        (
            f"- `current_full` 为 `{mult(float(current['annual_multiple']))}` 年化权益倍率、"
            f"`{pct(float(current['win_rate']))}` 胜率、"
            f"`{pct(float(current['max_dd']))}` 最大回撤、`{int(current['trades'])}` 笔。"
        ),
        (
            f"- 最近一年窗口按 V2 canonical 可交易起点 `{fmt_ts(train_start)}` 截断，"
            f"实际覆盖 `{last_year['days']:.1f}` 天；该窗口 `"
            f"{int(last_year['trades'])}` 笔、胜率 `{pct(float(last_year['win_rate']))}`。"
        ),
        "",
        "## 口径",
        "",
        "- 市场：Binance USD-M Futures `HYPEUSDT` perpetual。",
        "- 周期：`1h` closed-only K 线。",
        (
            f"- 数据范围：`{quality['first_ts']}` 到 `{quality['last_ts']}`，"
            f"normalized rows `{quality['rows']}`，missing `{quality['missing_bars']}`，"
            f"duplicate `{quality['duplicate_bars']}`。"
        ),
        "- 执行：闭合 K 信号，下一根 `1h` open 入场；DI fixed bracket，Stoch trailing；同刻冲突 DI 优先。",
        "- 成本：`0.001` fee/fill、`4 bps` slippage/fill，并计入 funding。",
        "- 窗口统计按 `entry_ts` 归属；年化倍数在短窗口里只作形状诊断，不作 promotion 依据。",
        "",
        "## 最近窗口",
        "",
        *markdown_table(recent_rows),
        "",
        "## 滚动窗口摘要",
        "",
        *rolling_summary_table(summaries),
        "",
        "## 机器证据",
        "",
        f"- JSON：`{SUMMARY_JSON.relative_to(FAMILY_DIR)}`",
        f"- 最近窗口 CSV：`{RECENT_WINDOWS_CSV.relative_to(FAMILY_DIR)}`",
        f"- 滚动窗口 CSV：`{ROLLING_WINDOWS_CSV.relative_to(FAMILY_DIR)}`",
        f"- 逐笔交易 CSV：`{TRADES_CSV.relative_to(FAMILY_DIR)}`",
        "",
        "复现：",
        "",
        "```bash",
        "uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v2_window_backtest.py",
        "```",
        "",
        f"滚动明细共 `{len(rolling_rows)}` 行，CSV 中保留每个切片的交易数、胜率、收益、回撤和多空笔数。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTE_DIR.mkdir(parents=True, exist_ok=True)

    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    train_start = v1_ablation.TRAIN_START

    di_cfg = v2.di_to_base(v2.DICleanConfig())
    stoch_cfg = v2.stoch_to_base(v2.StochCleanConfig())
    di_trades = base.simulate_trades(
        frame,
        base.build_signal(frame, di_cfg),
        di_cfg,
        funding_times,
        funding_cumulative,
    )
    stoch_trades = base.simulate_trades(
        frame,
        base.build_signal(frame, stoch_cfg),
        stoch_cfg,
        funding_times,
        funding_cumulative,
    )
    merged_trades = base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)

    recent_rows = [
        window_row(kind="recent", window=name, start=start, end=end, trades=merged_trades)
        for name, start, end in recent_window_defs(train_start, full_end)
    ]
    rolling_rows = [
        window_row(kind=kind, window=name, start=start, end=end, trades=merged_trades)
        for kind, name, start, end in rolling_window_defs(train_start, full_end)
    ]
    summaries = rolling_summary(rolling_rows)

    pd.DataFrame(base.json_safe(recent_rows)).to_csv(RECENT_WINDOWS_CSV, index=False)
    pd.DataFrame(base.json_safe(rolling_rows)).to_csv(ROLLING_WINDOWS_CSV, index=False)
    pd.DataFrame(base.json_safe([asdict(trade) for trade in merged_trades])).to_csv(
        TRADES_CSV, index=False
    )

    payload = {
        "version": "HYPE-1H-Adaptive-Regime-V2",
        "status": "clean equivalent diagnostic baseline / NO-GO / not live-ready / not promoted",
        "quality": quality,
        "train_start": train_start,
        "full_end": full_end,
        "costs": {
            "fee_per_fill": base.FEE_PER_FILL,
            "slippage_per_fill": base.SLIPPAGE_PER_FILL,
        },
        "trade_counts": {
            "di_component": len(di_trades),
            "stoch_component": len(stoch_trades),
            "merged": len(merged_trades),
        },
        "recent_windows": recent_rows,
        "rolling_summary": summaries,
        "rolling_windows": rolling_rows,
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        report_markdown(
            quality=quality,
            train_start=train_start,
            full_end=full_end,
            recent_rows=recent_rows,
            rolling_rows=rolling_rows,
            summaries=summaries,
        ),
        encoding="utf-8",
    )

    print(f"wrote {SUMMARY_JSON.relative_to(ROOT)}")
    print(f"wrote {RECENT_WINDOWS_CSV.relative_to(ROOT)}")
    print(f"wrote {ROLLING_WINDOWS_CSV.relative_to(ROOT)}")
    print(f"wrote {REPORT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
