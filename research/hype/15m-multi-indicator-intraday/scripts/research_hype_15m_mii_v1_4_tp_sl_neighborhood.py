from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_3_signal_drought_diagnostic as drought  # noqa: E402
import research_hype_15m_mii_v1_4_tp_sl_grid as coarse  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.4"
RUN_DATE = "2026-07-09"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_4_tp_sl_neighborhood.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
STANDARD_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_neighborhood_standard_2026-07-09.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_neighborhood_windows_2026-07-09.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_neighborhood_rolling_2026-07-09.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_neighborhood_recent_2026-07-09.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_tp_sl_neighborhood_2026-07-09.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-4-tp-sl-neighborhood-2026-07-09.md"

TP_GRID = tuple(round(float(v), 2) for v in np.arange(0.90, 1.6001, 0.05))
SL_GRID = tuple(round(float(v), 2) for v in np.arange(2.50, 6.0001, 0.25))
BASELINE_LABEL = "tp1p25_sl5"
ENTRY_DELAYS = coarse.ENTRY_DELAYS
STANDARD_WINDOWS = coarse.STANDARD_WINDOWS
RECENT_WINDOWS = coarse.RECENT_WINDOWS


def evaluate_fixed(
    *,
    dataset: str,
    context: coarse.v12.evolution.EvalContext,
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
) -> pd.DataFrame:
    filter_spec = coarse.v14_filter()
    rows: list[dict[str, Any]] = []
    for tp_mult in TP_GRID:
        for sl_mult in SL_GRID:
            candidate = coarse.candidate_for(tp_mult, sl_mult)
            exit_spec = coarse.v12.candidate_exit_spec(candidate)
            for entry_delay_bars, entry_label in ENTRY_DELAYS:
                trades = coarse.v12.simulate_atr_bracket_trades(
                    context,
                    candidate,
                    entry_delay_bars=entry_delay_bars,
                )
                for window, duration in windows:
                    start_ts, end_ts = coarse.window_bounds(context, duration)
                    rows.append(
                        coarse.evaluate_row(
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
        (merged.index != BASELINE_LABEL)
        & (merged["total_return_pct_k1"] > base["total_return_pct_k1"])
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"])
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"])
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"])
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"])
        & (merged["win_rate_pct_k2"] >= base["win_rate_pct_k2"])
    )
    merged["pass_balanced_gate"] = (
        (merged.index != BASELINE_LABEL)
        & (merged["total_return_pct_k1"] >= base["total_return_pct_k1"] * 0.95)
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"] - 1.0)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 1.0)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"])
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] - 1.0)
    )
    merged["pass_defensive_gate"] = (
        (merged.index != BASELINE_LABEL)
        & (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"] + 1.5)
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] + 1.5)
        & (merged["total_return_pct_k1"] >= base["total_return_pct_k1"] * 0.70)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.70)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 2.5)
    )
    merged["score"] = (
        np.log1p(np.maximum(merged["total_return_pct_k1"], -90.0) / 100.0) * 0.30
        + np.log1p(np.maximum(merged["total_return_pct_k2"], -90.0) / 100.0) * 0.25
        + ((merged["max_drawdown_pct_k1"] + 60.0) / 60.0) * 0.16
        + ((merged["max_drawdown_pct_k2"] + 60.0) / 60.0) * 0.14
        + ((merged["win_rate_pct_k1"] - 80.0) / 20.0) * 0.10
        + ((merged["worst_trade_pct_k1"] + 20.0) / 20.0) * 0.05
    )
    return merged.sort_values(
        ["pass_strict_gate", "pass_balanced_gate", "pass_defensive_gate", "score"],
        ascending=False,
    ).reset_index()


def rolling_summary(context: coarse.v12.evolution.EvalContext, labels: list[str]) -> pd.DataFrame:
    filter_spec = coarse.v14_filter()
    rows: list[dict[str, Any]] = []
    for label in labels:
        tp = float(label.split("_")[0].removeprefix("tp").replace("p", "."))
        sl = float(label.split("_")[1].removeprefix("sl").replace("p", "."))
        candidate = coarse.candidate_for(tp, sl)
        exit_spec = coarse.v12.candidate_exit_spec(candidate)
        for entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = coarse.v12.simulate_atr_bracket_trades(
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
                    row = coarse.evaluate_row(
                        dataset="standard_data_lake",
                        trades=trades,
                        filter_spec=filter_spec,
                        exit_spec=exit_spec,
                        tp_mult=tp,
                        sl_mult=sl,
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


def link(path: Path) -> str:
    if path.parent.name == "scripts":
        target = f"../scripts/{path.name}"
    elif path.parent.name == "artifacts":
        target = f"../artifacts/{path.name}"
    else:
        target = str(path)
    return f"[`{path}`]({target})"


def comparison_table(frame: pd.DataFrame, limit: int = 20) -> list[str]:
    lines = [
        "| 配置 | TP | SL | K+1收益 | K+1回撤 | K+1胜率 | K+1最差 | K+2收益 | K+2回撤 | K+2胜率 | Gate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in frame.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{fmt(row['tp_atr_mult_k1'], 2)}` | `{fmt(row['sl_atr_mult_k1'], 2)}` | "
            f"`{fmt(row['total_return_pct_k1'])}%` | `{fmt(row['max_drawdown_pct_k1'])}%` | "
            f"`{fmt(row['win_rate_pct_k1'])}%` | `{fmt(row['worst_trade_pct_k1'], 3)}%` | "
            f"`{fmt(row['total_return_pct_k2'])}%` | `{fmt(row['max_drawdown_pct_k2'])}%` | "
            f"`{fmt(row['win_rate_pct_k2'])}%` | "
            f"`{bool(row['pass_strict_gate'])}/{bool(row['pass_balanced_gate'])}/{bool(row['pass_defensive_gate'])}` |"
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


def rolling_table(rolling: pd.DataFrame, *, entry: str, days: int, labels: list[str]) -> list[str]:
    subset = rolling.loc[
        rolling["entry_timing"].eq(entry)
        & rolling["rolling_days"].eq(days)
        & rolling["label"].isin(labels)
    ].copy()
    order = {label: idx for idx, label in enumerate(labels)}
    subset["order"] = subset["label"].map(order)
    subset = subset.sort_values("order")
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
    strict_count = int(comparison["pass_strict_gate"].sum())
    balanced_count = int(comparison["pass_balanced_gate"].sum())
    defensive_count = int(comparison["pass_defensive_gate"].sum())
    best = comparison.iloc[0]
    close_label = "tp1p25_sl4p75"
    recent_label = "tp1p4_sl3"
    close = comparison.loc[comparison["label"].eq(close_label)].iloc[0]
    recent_candidate = comparison.loc[comparison["label"].eq(recent_label)].iloc[0]
    labels = list(
        dict.fromkeys(
            [
                BASELINE_LABEL,
                close_label,
                recent_label,
                str(best["label"]),
                *comparison["label"].head(8).tolist(),
            ]
        )
    )
    lines = [
        f"# HYPE-15M-MII V1.4 TP/SL 邻域搜索 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "本轮保持 `V1.4` 入场、`min_atr_pct96=75 bps`、`min_rvol96=0.85`、`hold=24`、Binance 成本和 `2.5x` 不变，只在 `TP=0.90-1.60`、`SL=2.50-6.00` 做 `0.05/0.25` 细邻域搜索。该范围覆盖 `1.25/5.0` 附近、`SL3` 防守区，以及粗网格未覆盖的 `SL>5.0`。",
        "",
        (
            f"`V1.4 baseline`：K+1 总收益 `{fmt(base['total_return_pct_k1'])}%`、回撤 "
            f"`{fmt(base['max_drawdown_pct_k1'])}%`、胜率 `{fmt(base['win_rate_pct_k1'])}%`；"
            f"K+2 总收益 `{fmt(base['total_return_pct_k2'])}%`、回撤 `{fmt(base['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"综合排序第一为 `{best['label']}`：K+1 `{fmt(best['total_return_pct_k1'])}%` / "
            f"`{fmt(best['max_drawdown_pct_k1'])}%`，K+2 `{fmt(best['total_return_pct_k2'])}%` / "
            f"`{fmt(best['max_drawdown_pct_k2'])}%`。"
        ),
        f"严格 gate `{strict_count}/{len(comparison)}`，balanced gate `{balanced_count}/{len(comparison)}`，defensive gate `{defensive_count}/{len(comparison)}`。",
        "",
    ]
    if strict_count:
        label = str(comparison.loc[comparison["pass_strict_gate"]].iloc[0]["label"])
        lines.append(f"存在严格候选 `{label}`，需要再做 OOS 和 runner 对拍。")
    elif balanced_count:
        label = str(comparison.loc[comparison["pass_balanced_gate"]].iloc[0]["label"])
        lines.append(f"没有严格候选；最接近替换的是 balanced 候选 `{label}`。")
    elif defensive_count:
        label = str(comparison.loc[comparison["pass_defensive_gate"]].iloc[0]["label"])
        lines.append(f"没有收益型替换候选；只有防守型候选 `{label}`，不能替换 baseline。")
    else:
        lines.append("没有任何 TP/SL 组合同时满足全样本收益保留、K+1/K+2 回撤和胜率要求。")
    lines.extend(
        [
            "",
            (
                f"最接近全样本替换的是 `{close_label}`：K+1 从 `{fmt(base['total_return_pct_k1'])}%` "
                f"升到 `{fmt(close['total_return_pct_k1'])}%`，回撤从 `{fmt(base['max_drawdown_pct_k1'])}%` "
                f"浅到 `{fmt(close['max_drawdown_pct_k1'])}%`，胜率持平；但 K+2 回撤从 "
                f"`{fmt(base['max_drawdown_pct_k2'])}%` 变深到 `{fmt(close['max_drawdown_pct_k2'])}%`，"
                "因此不能替换 baseline。"
            ),
            (
                f"最近窗口最强的方向是 `{recent_label}` 一类较高 TP + 窄 SL：recent 90d/30d 会明显变好，"
                f"但全样本 K+1 只有 `{fmt(recent_candidate['total_return_pct_k1'])}%`，回撤 "
                f"`{fmt(recent_candidate['max_drawdown_pct_k1'])}%`，胜率 `{fmt(recent_candidate['win_rate_pct_k1'])}%`，"
                "属于近期防守/进攻混合观察，不是长期替换。"
            ),
        ]
    )
    lines.extend(
        [
            "",
            "## 全样本综合对比",
            "",
            *comparison_table(comparison),
            "",
            "## 固定窗口",
            "",
            *fixed_table(standard, dataset="standard_data_lake", entry="K+1", window="全样本", labels=labels),
            "",
            *fixed_table(standard, dataset="standard_data_lake", entry="K+2", window="全样本", labels=labels),
            "",
            *fixed_table(windows, dataset="standard_data_lake", entry="K+1", window="最近90d", labels=labels),
            "",
            "## Recent API",
            "",
            *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近90d", labels=labels),
            "",
            *fixed_table(recent, dataset="recent_binance_api", entry="K+1", window="最近30d", labels=labels),
            "",
            "## 滚动窗口",
            "",
            *rolling_table(rolling, entry="K+1", days=30, labels=labels),
            "",
            *rolling_table(rolling, entry="K+2", days=90, labels=labels),
            "",
            "## 数据质量",
            "",
            f"- Standard data lake：`{lake_quality['first_ts']}` 到 `{lake_quality['last_ts']}`，rows `{lake_quality['rows']}`，quality gate `{lake_quality['quality_gate_pass']}`。",
            f"- Recent Binance API：`{recent_quality['first_ts']}` 到 `{recent_quality['last_ts']}`，rows `{recent_quality['rows']}`，quality gate `{recent_quality['quality_gate_pass']}`。",
            "",
            "## 产物",
            "",
            f"- 脚本：{link(SCRIPT_PATH)}",
            f"- 标准数据湖全样本 CSV：{link(STANDARD_CSV_PATH)}",
            f"- 标准数据湖分窗口 CSV：{link(WINDOW_CSV_PATH)}",
            f"- 滚动窗口 CSV：{link(ROLLING_CSV_PATH)}",
            f"- recent API CSV：{link(RECENT_CSV_PATH)}",
            f"- JSON：{link(JSON_PATH)}",
        ]
    )
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

    lake_context, lake_metadata, lake_quality = coarse.v12.build_context()
    fixed = evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        windows=STANDARD_WINDOWS,
    )
    standard = fixed.loc[fixed["window"].eq("全样本")].copy()
    windows = fixed.loc[~fixed["window"].eq("全样本")].copy()
    comparison = full_comparison(standard)
    rolling_labels = list(dict.fromkeys([BASELINE_LABEL, *comparison["label"].head(10).tolist()]))
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
                    "status": "tp_sl_neighborhood_diagnostic_not_promoted",
                    "grid": {
                        "tp_atr_mult": TP_GRID,
                        "sl_atr_mult": SL_GRID,
                        "max_hold_bars": coarse.MAX_HOLD_BARS,
                        "min_rvol96": coarse.V14_MIN_RVOL96,
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
                "worst_trade_pct_k1",
                "total_return_pct_k2",
                "max_drawdown_pct_k2",
                "win_rate_pct_k2",
                "pass_strict_gate",
                "pass_balanced_gate",
                "pass_defensive_gate",
            ]
        ]
        .head(24)
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
