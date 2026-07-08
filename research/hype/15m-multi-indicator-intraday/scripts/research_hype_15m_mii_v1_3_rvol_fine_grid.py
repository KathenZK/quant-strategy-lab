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
import research_hype_15m_mii_v1_3_rvol_grid_compare as coarse  # noqa: E402
import research_hype_15m_mii_v1_3_signal_drought_diagnostic as drought  # noqa: E402


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
ALIAS = "HYPE-15M-MII"
VERSION = "HYPE-15M-MII-V1.3"
RUN_DATE = "2026-07-08"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_3_rvol_fine_grid.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
STANDARD_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_fine_grid_standard_2026-07-08.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_fine_grid_rolling_2026-07-08.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_fine_grid_recent_2026-07-08.csv"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_fine_grid_weekly_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_3_rvol_fine_grid_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-3-rvol-fine-grid-2026-07-08.md"

RVOL_FINE_GRID = (1.0, 0.9, 0.89, 0.88, 0.87, 0.86, 0.85, 0.8)


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
    columns = ["rvol1", "rvol0.9", "rvol0.89", "rvol0.88", "rvol0.87", "rvol0.86", "rvol0.85", "rvol0.8"]
    lines = [
        f"### {entry}",
        "",
        "| 周起点 UTC | rvol1 | rvol0.9 | rvol0.89 | rvol0.88 | rvol0.87 | rvol0.86 | rvol0.85 | rvol0.8 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for week_start, row in piv.iterrows():
        values = " | ".join(f"`{int(row.get(column, 0))}`" for column in columns)
        lines.append(f"| `{str(week_start)[:10]}` | {values} |")
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
    recent_90 = recent.loc[
        recent["dataset"].eq("recent_binance_api")
        & recent["entry_timing"].eq("K+1")
        & recent["window"].eq("最近90d")
    ].set_index("variant")
    recent_30 = recent.loc[
        recent["dataset"].eq("recent_binance_api")
        & recent["entry_timing"].eq("K+1")
        & recent["window"].eq("最近30d")
    ].set_index("variant")
    best_k1 = k1_all.loc[[f"rvol{value:g}" for value in RVOL_FINE_GRID if value < 1.0]].sort_values(
        ["total_return_pct", "max_drawdown_pct"], ascending=[False, False]
    ).iloc[0]
    best_recent = recent_90.loc[[f"rvol{value:g}" for value in RVOL_FINE_GRID if value < 1.0]].sort_values(
        ["total_return_pct", "max_drawdown_pct"], ascending=[False, False]
    ).iloc[0]
    lines = [
        f"# HYPE-15M-MII V1.3 RVOL 细网格 {RUN_DATE}",
        "",
        "## 结论",
        "",
        (
            f"`0.85-0.90` 之间按 `0.01` 细分后，K+1 全样本最高收益是 "
            f"`{best_k1.name}`：`{int(best_k1['trades'])}` 笔、总收益 "
            f"`{fmt(best_k1['total_return_pct'])}%`、回撤 `{fmt(best_k1['max_drawdown_pct'])}%`、"
            f"胜率 `{fmt(best_k1['win_rate_pct'])}%`。"
        ),
        (
            f"recent API K+1 最近 `90d` 最高收益是 `{best_recent.name}`："
            f"`{int(best_recent['trades'])}` 笔、总收益 `{fmt(best_recent['total_return_pct'])}%`、"
            f"回撤 `{fmt(best_recent['max_drawdown_pct'])}%`。"
        ),
        (
            f"K+2 全样本 `rvol0.85` 为 `{fmt(k2_all.loc['rvol0.85', 'total_return_pct'])}%`，"
            f"`rvol0.86` 为 `{fmt(k2_all.loc['rvol0.86', 'total_return_pct'])}%`，"
            f"`rvol0.87` 为 `{fmt(k2_all.loc['rvol0.87', 'total_return_pct'])}%`。"
        ),
        (
            f"recent K+1 最近 `30d`：`rvol0.9` `{int(recent_30.loc['rvol0.9', 'trades'])}` 笔，"
            f"`rvol0.88` `{int(recent_30.loc['rvol0.88', 'trades'])}` 笔，"
            f"`rvol0.87` `{int(recent_30.loc['rvol0.87', 'trades'])}` 笔，"
            f"`rvol0.85` `{int(recent_30.loc['rvol0.85', 'trades'])}` 笔。"
        ),
        "最近 `7d/72h/24h` 所有 RVOL 阈值仍然都是 `0` 笔；细调 RVOL 不能解决当前几天不开单。",
        "",
        "结论：`0.85` 仍是这组细网格里最强的进取观察点；`0.86` 非常接近，回撤略浅一点但收益也低一点；`0.87/0.88/0.89` 属于从 `0.9` 到 `0.85` 的平滑过渡，没有超过 `0.85`。如果要实盘模拟优先级，建议：保守观察 `0.90`，进取观察 `0.85/0.86`，暂不选 `0.80`。",
        "",
        "## 标准数据湖",
        "",
        *table_fixed(standard, dataset="standard_data_lake", entry="K+1", window="全样本"),
        "",
        *table_fixed(standard, dataset="standard_data_lake", entry="K+2", window="全样本"),
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

    coarse.RVOL_GRID = RVOL_FINE_GRID
    lake_context, lake_metadata, lake_quality = v12.build_context()
    standard = coarse.evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        windows=coarse.STANDARD_WINDOWS,
    )
    rolling = coarse.rolling_summary(lake_context)

    recent_frame = drought.fetch_recent_fapi_klines()
    recent_quality = drought.data_quality(recent_frame)
    if not recent_quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(recent_quality, ensure_ascii=False)}")
    recent_context = drought.build_context(recent_frame)
    recent = coarse.evaluate_fixed(
        dataset="recent_binance_api",
        context=recent_context,
        windows=tuple((name, duration) for name, duration in coarse.RECENT_WINDOWS),
    )
    weekly = coarse.recent_weekly(recent_context)

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
                    "status": "rvol_fine_grid_diagnostic_not_promoted",
                    "rvol_grid": RVOL_FINE_GRID,
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
        "profit_factor",
    ]
    print("Standard all sample")
    print(
        standard.loc[standard["window"].eq("全样本")]
        .sort_values(["entry_timing", "min_rvol96"], ascending=[True, False])
        [key_cols]
        .to_string(index=False)
    )
    print("Recent K+1 90d")
    print(
        recent.loc[recent["entry_timing"].eq("K+1") & recent["window"].eq("最近90d")]
        .sort_values("min_rvol96", ascending=False)
        [key_cols]
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
