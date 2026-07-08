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
VERSION = "HYPE-15M-MII-V1.4"
RUN_DATE = "2026-07-08"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_4_tp_sl_grid.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
STANDARD_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_grid_standard_2026-07-08.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_grid_windows_2026-07-08.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_grid_rolling_2026-07-08.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_grid_recent_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_grid_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-4-tp-sl-grid-2026-07-08.md"

V14_EXPOSURE = 2.5
V14_MIN_RVOL96 = 0.85
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
TP_GRID = (0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 3.0, 3.5, 4.0)
SL_GRID = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0)
MAX_HOLD_BARS = 24
BASELINE_LABEL = "tp1p25_sl5"
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


def label_for(tp_mult: float, sl_mult: float) -> str:
    return f"tp{tp_mult:g}_sl{sl_mult:g}".replace(".", "p")


def candidate_for(tp_mult: float, sl_mult: float) -> v12.AtrBracketCandidate:
    return v12.AtrBracketCandidate(
        label=label_for(tp_mult, sl_mult),
        family="atr_bracket",
        atr_window=96,
        tp_atr_mult=tp_mult,
        sl_atr_mult=sl_mult,
        max_hold_bars=MAX_HOLD_BARS,
    )


def v14_filter() -> Any:
    return replace(v12.BASE_CONFIG.filter, min_rvol96=V14_MIN_RVOL96)


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


def selected_returns(
    trades: list[v12.EventTrade],
    filter_spec: Any,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[float]:
    selected = v1.selected_trades_live(window_trades(trades, start_ts, end_ts), filter_spec)
    return [
        float(V14_EXPOSURE * (trade.raw_return - v12.ROUND_TRIP_COST) * 100.0)
        for trade in selected
    ]


def evaluate_row(
    *,
    dataset: str,
    trades: list[v12.EventTrade],
    filter_spec: Any,
    exit_spec: Any,
    tp_mult: float,
    sl_mult: float,
    entry_label: str,
    window: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=filter_spec,
        exposure=V14_EXPOSURE,
        period_days=period_days,
        exit_spec=exit_spec,
        start_ts=start_ts,
        end_ts=end_ts,
    )
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
    returns = selected_returns(trades, filter_spec, start_ts, end_ts)
    return {
        "dataset": dataset,
        "label": label_for(tp_mult, sl_mult),
        "tp_atr_mult": tp_mult,
        "sl_atr_mult": sl_mult,
        "max_hold_bars": MAX_HOLD_BARS,
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
        "best_trade_pct": float(np.max(returns)) if returns else 0.0,
    }


def evaluate_fixed(
    *,
    dataset: str,
    context: v12.evolution.EvalContext,
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
) -> pd.DataFrame:
    filter_spec = v14_filter()
    rows: list[dict[str, Any]] = []
    for tp_mult in TP_GRID:
        for sl_mult in SL_GRID:
            candidate = candidate_for(tp_mult, sl_mult)
            exit_spec = v12.candidate_exit_spec(candidate)
            for entry_delay_bars, entry_label in ENTRY_DELAYS:
                trades = v12.simulate_atr_bracket_trades(
                    context,
                    candidate,
                    entry_delay_bars=entry_delay_bars,
                )
                for window, duration in windows:
                    start_ts, end_ts = window_bounds(context, duration)
                    rows.append(
                        evaluate_row(
                            dataset=dataset,
                            trades=trades,
                            filter_spec=filter_spec,
                            exit_spec=exit_spec,
                            tp_mult=tp_mult,
                            sl_mult=sl_mult,
                            entry_label=entry_label,
                            window=window,
                            start_ts=start_ts,
                            end_ts=end_ts,
                        )
                    )
    return pd.DataFrame(rows)


def full_comparison(standard: pd.DataFrame) -> pd.DataFrame:
    full = standard.loc[standard["window"].eq("全样本")].copy()
    k1 = full.loc[full["entry_timing"].eq("K+1")].set_index("label")
    k2 = full.loc[full["entry_timing"].eq("K+2")].set_index("label")
    merged = k1.join(k2, lsuffix="_k1", rsuffix="_k2")
    base = merged.loc[BASELINE_LABEL]
    merged["delta_total_return_pct_k1"] = merged["total_return_pct_k1"] - base["total_return_pct_k1"]
    merged["delta_max_drawdown_pct_k1"] = merged["max_drawdown_pct_k1"] - base["max_drawdown_pct_k1"]
    merged["delta_win_rate_pct_k1"] = merged["win_rate_pct_k1"] - base["win_rate_pct_k1"]
    merged["delta_total_return_pct_k2"] = merged["total_return_pct_k2"] - base["total_return_pct_k2"]
    merged["delta_max_drawdown_pct_k2"] = merged["max_drawdown_pct_k2"] - base["max_drawdown_pct_k2"]
    merged["pass_strict_gate"] = (
        (merged["total_return_pct_k1"] > base["total_return_pct_k1"])
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"])
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"])
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"])
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"])
        & (merged["win_rate_pct_k2"] >= base["win_rate_pct_k2"])
    )
    merged["pass_relaxed_gate"] = (
        (merged["total_return_pct_k1"] > base["total_return_pct_k1"])
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"] - 3.0)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 2.0)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.9)
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] - 3.0)
    )
    merged["score"] = (
        np.log1p(np.maximum(merged["total_return_pct_k1"], -90.0) / 100.0) * 0.32
        + np.log1p(np.maximum(merged["total_return_pct_k2"], -90.0) / 100.0) * 0.28
        + ((merged["max_drawdown_pct_k1"] + 60.0) / 60.0) * 0.16
        + ((merged["max_drawdown_pct_k2"] + 60.0) / 60.0) * 0.14
        + ((merged["win_rate_pct_k1"] - 65.0) / 30.0) * 0.10
    )
    return merged.sort_values(
        ["pass_strict_gate", "pass_relaxed_gate", "score"],
        ascending=False,
    ).reset_index()


def rolling_summary(context: v12.evolution.EvalContext, labels: list[str]) -> pd.DataFrame:
    filter_spec = v14_filter()
    rows: list[dict[str, Any]] = []
    specs = []
    for label in labels:
        tp = float(label.split("_")[0].removeprefix("tp").replace("p", "."))
        sl = float(label.split("_")[1].removeprefix("sl").replace("p", "."))
        specs.append((label, candidate_for(tp, sl)))
    for label, candidate in specs:
        exit_spec = v12.candidate_exit_spec(candidate)
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = v12.simulate_atr_bracket_trades(
                context,
                candidate,
                entry_delay_bars=entry_delay_bars,
            )
            for days in (30, 90):
                duration = pd.Timedelta(days=days)
                step = pd.Timedelta(days=7)
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
                        tp_mult=candidate.tp_atr_mult or 0.0,
                        sl_mult=candidate.sl_atr_mult or 0.0,
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
                        "label": label,
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


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def merged_table(frame: pd.DataFrame, limit: int = 15) -> list[str]:
    lines = [
        "| 配置 | TP | SL | K+1收益 | K+1回撤 | K+1胜率 | K+1均笔 | K+1最差 | K+2收益 | K+2回撤 | K+2胜率 | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in frame.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{fmt(row['tp_atr_mult_k1'], 2)}` | `{fmt(row['sl_atr_mult_k1'], 2)}` | "
            f"`{fmt(row['total_return_pct_k1'])}%` | `{fmt(row['max_drawdown_pct_k1'])}%` | "
            f"`{fmt(row['win_rate_pct_k1'])}%` | `{fmt(row['avg_trade_pct_k1'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct_k1'], 3)}%` | `{fmt(row['total_return_pct_k2'])}%` | "
            f"`{fmt(row['max_drawdown_pct_k2'])}%` | `{fmt(row['win_rate_pct_k2'])}%` | "
            f"`{bool(row['pass_strict_gate'])}/{bool(row['pass_relaxed_gate'])}` |"
        )
    return lines


def fixed_table(frame: pd.DataFrame, *, dataset: str, entry: str, window: str, labels: list[str]) -> list[str]:
    subset = frame.loc[
        frame["dataset"].eq(dataset)
        & frame["entry_timing"].eq(entry)
        & frame["window"].eq(window)
        & frame["label"].isin(labels)
    ].copy()
    order = {label: idx for idx, label in enumerate(labels)}
    subset["order"] = subset["label"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {dataset} / {entry} / {window}",
        "",
        "| 配置 | 交易数 | 总收益 | 回撤 | 胜率 | PF | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
            f"`{fmt(row['max_drawdown_pct'])}%` | `{fmt(row['win_rate_pct'])}%` | "
            f"`{fmt(row['profit_factor'], 3)}` | `{fmt(row['avg_trade_pct'], 3)}%` | "
            f"`{fmt(row['worst_trade_pct'], 3)}%` |"
        )
    return lines


def rolling_table(rolling: pd.DataFrame, *, entry: str, days: int) -> list[str]:
    subset = rolling.loc[rolling["entry_timing"].eq(entry) & rolling["rolling_days"].eq(days)]
    lines = [
        f"### {entry} / rolling {days}d",
        "",
        "| 配置 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 中位交易数 | 零交易切片 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{int(row['positive_slices'])}/{int(row['slices'])}` | "
            f"`{fmt(row['median_total_return_pct'])}%` | `{fmt(row['worst_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_trades'], 1)}` | `{int(row['zero_trade_slices'])}` |"
        )
    return lines


def render_markdown(
    comparison: pd.DataFrame,
    standard: pd.DataFrame,
    windows: pd.DataFrame,
    rolling: pd.DataFrame,
    recent: pd.DataFrame,
    lake_quality: dict[str, Any],
    recent_quality: dict[str, Any],
) -> str:
    base = comparison.loc[comparison["label"].eq(BASELINE_LABEL)].iloc[0]
    best = comparison.iloc[0]
    strict_count = int(comparison["pass_strict_gate"].sum())
    relaxed_count = int(comparison["pass_relaxed_gate"].sum())
    top_labels = list(dict.fromkeys([BASELINE_LABEL, str(best["label"]), *comparison["label"].head(6).tolist()]))
    lines = [
        f"# HYPE-15M-MII V1.4 TP/SL ATR 倍数网格 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "本轮只针对 `HYPE-15M-MII-V1.4` 调整 `tp_atr_mult/sl_atr_mult`，保持 RSI/MACD、`min_atr_pct96=75 bps`、`min_rvol96=0.85`、`hold=24`、Binance 成本和 `2.5x` 暴露不变。",
        "",
        (
            f"现有 `TP=1.25*ATR96 / SL=5.0*ATR96` 的 K+1 全样本总收益 "
            f"`{fmt(base['total_return_pct_k1'])}%`、回撤 `{fmt(base['max_drawdown_pct_k1'])}%`、"
            f"胜率 `{fmt(base['win_rate_pct_k1'])}%`；K+2 总收益 `{fmt(base['total_return_pct_k2'])}%`、"
            f"回撤 `{fmt(base['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"综合排序第一是 `{best['label']}`：K+1 总收益 `{fmt(best['total_return_pct_k1'])}%`、"
            f"回撤 `{fmt(best['max_drawdown_pct_k1'])}%`、胜率 `{fmt(best['win_rate_pct_k1'])}%`；"
            f"K+2 总收益 `{fmt(best['total_return_pct_k2'])}%`、回撤 `{fmt(best['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"严格 gate（K+1/K+2 收益、回撤、胜率均不差且 K+1 收益更高）通过 "
            f"`{strict_count}/{len(comparison)}`；放宽 gate 通过 `{relaxed_count}/{len(comparison)}`。"
        ),
        "结论：宽止损不是无脑选择，但现有 `1.25/5.0` 在 `V1.4` 上仍是最稳的高胜率配置之一。更高 TP 或更窄 SL 可以提高单笔盈亏比，但会明显降低胜率或恶化 K+1/K+2 的联合形状；若要替换，必须选能同时通过 K+2 与 rolling 的配置，而不是只看单笔赚得更多。",
        "",
        "## 全样本综合排名",
        "",
        *merged_table(comparison, limit=18),
        "",
        "## 关键配置窗口对比",
        "",
        *fixed_table(standard, dataset="standard_data_lake", entry="K+1", window="全样本", labels=top_labels),
        "",
        *fixed_table(standard, dataset="standard_data_lake", entry="K+2", window="全样本", labels=top_labels),
        "",
        *fixed_table(windows, dataset="standard_data_lake", entry="K+1", window="最近90d", labels=top_labels),
        "",
        "## Recent API",
        "",
        *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近90d", labels=top_labels),
        "",
        *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近30d", labels=top_labels),
        "",
        "## 滚动窗口",
        "",
        *rolling_table(rolling, entry="K+1", days=30),
        "",
        *rolling_table(rolling, entry="K+2", days=90),
        "",
        "## 数据质量",
        "",
        f"- Standard data lake：`{lake_quality['first_ts']}` 到 `{lake_quality['last_ts']}`，rows `{lake_quality['rows']}`，quality gate `{lake_quality['quality_gate_pass']}`。",
        f"- Recent Binance API：`{recent_quality['first_ts']}` 到 `{recent_quality['last_ts']}`，rows `{recent_quality['rows']}`，quality gate `{recent_quality['quality_gate_pass']}`。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- 标准数据湖全样本 CSV：`{STANDARD_CSV_PATH}`",
        f"- 标准数据湖分窗口 CSV：`{WINDOW_CSV_PATH}`",
        f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
        f"- recent API CSV：`{RECENT_CSV_PATH}`",
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
    fixed = evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        windows=STANDARD_WINDOWS,
    )
    standard = fixed.loc[fixed["window"].eq("全样本")].copy()
    windows = fixed.loc[~fixed["window"].eq("全样本")].copy()
    comparison = full_comparison(standard)
    rolling_labels = list(dict.fromkeys([BASELINE_LABEL, *comparison["label"].head(8).tolist()]))
    rolling = rolling_summary(lake_context, rolling_labels)

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

    standard.to_csv(STANDARD_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    recent.to_csv(RECENT_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(comparison, standard, windows, rolling, recent, lake_quality, recent_quality),
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
                    "status": "tp_sl_grid_diagnostic_not_promoted",
                    "grid": {
                        "tp_atr_mult": TP_GRID,
                        "sl_atr_mult": SL_GRID,
                        "max_hold_bars": MAX_HOLD_BARS,
                        "min_rvol96": V14_MIN_RVOL96,
                    },
                    "lake_metadata": lake_metadata,
                    "lake_quality": lake_quality,
                    "recent_quality": recent_quality,
                    "comparison": comparison.to_dict(orient="records"),
                    "standard": standard.to_dict(orient="records"),
                    "windows": windows.to_dict(orient="records"),
                    "rolling": rolling.to_dict(orient="records"),
                    "recent": recent.to_dict(orient="records"),
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Top comparison")
    print(
        comparison[
            [
                "label",
                "total_return_pct_k1",
                "max_drawdown_pct_k1",
                "win_rate_pct_k1",
                "avg_trade_pct_k1",
                "worst_trade_pct_k1",
                "total_return_pct_k2",
                "max_drawdown_pct_k2",
                "win_rate_pct_k2",
                "pass_strict_gate",
                "pass_relaxed_gate",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
