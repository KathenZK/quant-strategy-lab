from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import (
    DataLakeLayout,
    DatasetKind,
    DuckDBWarehouse,
    MarketType,
)
from strategy_lab.data.settings import load_settings

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_full_ablation as engine  # noqa: E402
import research_hype_15m_mii_search as search_engine  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    EventTrade,
    ExitSpec,
    FilterSpec,
    MarketArrays,
    SignalState,
    add_features,
    build_market_arrays,
    ema_pairs,
    passes_filter,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
VERSION = "HYPE-15M-Multi-Indicator-Intraday-V1"
RUN_DATE = "2026-06-29"

FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_full_ablation.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
ABLATIONS_DIR = FAMILY_DIR / "ablations"
NORMALIZED_ROOT = Path(
    "data/normalized/ohlcv/exchange=binance/market_type=perp/timeframe=15m"
)
RAW_ROOT = Path("data/raw/ohlcv/exchange=binance/market_type=perp/timeframe=15m")
SYMBOL_FILE = "symbol=hype_usdt_usdt.parquet"

SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_2026-06-29.json"
SUMMARY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_summary_2026-06-29.csv"
SLICES_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_slices_2026-06-29.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_rolling_2026-06-29.csv"
WEEKLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_weekly_2026-06-29.csv"
MONTHLY_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_full_ablation_monthly_2026-06-29.csv"
MARKDOWN_PATH = ABLATIONS_DIR / "hype-15m-mii-v1-full-parameter-ablation-2026-06-29.md"

REQUIRED_COLUMNS = {
    "ts",
    "exchange",
    "symbol",
    "market_type",
    "timeframe",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "vwap",
    "is_closed",
    "source",
}
NUMERIC_ALIGNMENT_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_volume",
    "trade_count",
    "vwap",
]


def load_partitioned(root: Path) -> tuple[pd.DataFrame, list[Path]]:
    files = sorted(root.glob(f"date=*/{SYMBOL_FILE}"))
    if not files:
        raise FileNotFoundError(f"no HYPE 15m partitions found under {root}")
    frame = pd.concat((pd.read_parquet(path) for path in files), ignore_index=True)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"missing required columns under {root}: {missing}")
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.sort_values("ts").reset_index(drop=True), files


def data_quality_report(
    normalized: pd.DataFrame,
    raw: pd.DataFrame,
    normalized_files: list[Path],
    raw_files: list[Path],
) -> dict[str, Any]:
    expected = pd.Timedelta(minutes=15)
    gaps = normalized["ts"].diff().dropna()
    invalid_ohlc = (
        (normalized["high"] < normalized[["open", "close", "low"]].max(axis=1))
        | (normalized["low"] > normalized[["open", "close", "high"]].min(axis=1))
        | (normalized[["open", "high", "low", "close"]] <= 0).any(axis=1)
        | (normalized["volume"] < 0)
        | (normalized["quote_volume"] < 0)
        | (normalized["trade_count"] < 0)
        | (
            normalized["volume"].gt(0)
            & (
                normalized["vwap"].lt(normalized["low"])
                | normalized["vwap"].gt(normalized["high"])
            )
        )
    )

    raw_dupes = int(raw["ts"].duplicated().sum())
    normalized_dupes = int(normalized["ts"].duplicated().sum())
    merged = normalized[["ts", *NUMERIC_ALIGNMENT_COLUMNS]].merge(
        raw[["ts", *NUMERIC_ALIGNMENT_COLUMNS]],
        on="ts",
        how="outer",
        suffixes=("_normalized", "_raw"),
        indicator=True,
    )
    missing_alignment_rows = int(merged["_merge"].ne("both").sum())
    value_mismatches: dict[str, int] = {}
    both = merged["_merge"].eq("both")
    for column in NUMERIC_ALIGNMENT_COLUMNS:
        left = merged.loc[both, f"{column}_normalized"].astype(float)
        right = merged.loc[both, f"{column}_raw"].astype(float)
        value_mismatches[column] = int(
            (~np.isclose(left, right, rtol=1e-12, atol=1e-12, equal_nan=True)).sum()
        )

    critical_columns = [
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quote_volume",
        "trade_count",
        "vwap",
        "source",
        "is_closed",
    ]
    report = {
        "normalized_root": str(NORMALIZED_ROOT),
        "raw_root": str(RAW_ROOT),
        "normalized_files": len(normalized_files),
        "raw_files": len(raw_files),
        "rows": int(len(normalized)),
        "first_ts": normalized["ts"].min().isoformat(),
        "last_ts": normalized["ts"].max().isoformat(),
        "gap_count": int(gaps.ne(expected).sum()),
        "normalized_duplicates": normalized_dupes,
        "raw_duplicates": raw_dupes,
        "critical_nulls": int(normalized[critical_columns].isna().sum().sum()),
        "invalid_ohlc_rows": int(invalid_ohlc.sum()),
        "open_bar_rows": int((~normalized["is_closed"].astype(bool)).sum()),
        "non_utc_rows": int(normalized["ts"].map(lambda value: value.utcoffset() is None).sum()),
        "unknown_source_rows": int(normalized["source"].astype(str).str.strip().eq("").sum()),
        "sources": {
            str(key): int(value)
            for key, value in normalized["source"].value_counts(dropna=False).items()
        },
        "raw_normalized_missing_rows": missing_alignment_rows,
        "raw_normalized_value_mismatches": value_mismatches,
    }
    blockers = [
        report["gap_count"],
        report["normalized_duplicates"],
        report["raw_duplicates"],
        report["critical_nulls"],
        report["invalid_ohlc_rows"],
        report["open_bar_rows"],
        report["non_utc_rows"],
        report["unknown_source_rows"],
        report["raw_normalized_missing_rows"],
        sum(value_mismatches.values()),
    ]
    report["quality_gate_pass"] = not any(blockers)
    return report


def load_data_lake() -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    normalized = warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="15m",
    ).reset_index(drop=True)
    normalized_files = [
        Path(path)
        for path in warehouse._filtered_dataset_files(
            layer="normalized",
            kind=DatasetKind.OHLCV,
            exchange="binance",
            market_type=MarketType.PERP,
            symbol="HYPE/USDT:USDT",
            timeframe="15m",
        )
    ]
    raw, raw_files = load_partitioned(RAW_ROOT)
    quality = data_quality_report(normalized, raw, normalized_files, raw_files)
    if not quality["quality_gate_pass"]:
        raise ValueError(f"data-quality blocker: {json.dumps(quality, ensure_ascii=False)}")
    metadata = {
        "exchange": "binance",
        "market_type": "perp",
        "symbol": "HYPE/USDT:USDT",
        "timeframe": "15m",
        "source": "standard_raw_and_normalized_data_lake",
    }
    return normalized, metadata, quality


def pct(value: float, digits: int = 2) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}%"


def num(value: float, digits: int = 3) -> str:
    if not np.isfinite(value):
        return "inf"
    return f"{value:.{digits}f}"


def metric_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 变体 | 参数 | 值 | 年化 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | Last90 年化 | Delta年化 |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['label']}` | `{row['parameter']}` | `{row['value']}` | "
            f"`{pct(float(row['annual_return_pct']))}` | "
            f"`{pct(float(row['max_drawdown_pct']))}` | "
            f"`{pct(float(row['win_rate_pct']))}` | `{int(row['trades'])}` | "
            f"`{num(float(row['trades_per_day']))}` | "
            f"`{num(float(row['profit_factor']))}` | "
            f"`{pct(float(row.get('last_90d_annual_return_pct', 0.0)))}` | "
            f"`{pct(float(row['delta_annual_return_pct']))}` |"
        )
    return lines


def slice_table(rows: pd.DataFrame) -> list[str]:
    lines = [
        "| 切片 | 年化 | 总收益 | 回撤 | 胜率 | 笔数 | 笔/日 | PF |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.to_dict(orient="records"):
        lines.append(
            f"| `{row['slice']}` | `{pct(float(row['annual_return_pct']))}` | "
            f"`{pct(float(row['total_return_pct']))}` | "
            f"`{pct(float(row['max_drawdown_pct']))}` | "
            f"`{pct(float(row['win_rate_pct']))}` | `{int(row['trades'])}` | "
            f"`{num(float(row['trades_per_day']))}` | "
            f"`{num(float(row['profit_factor']))}` |"
        )
    return lines


def parameter_group_table(summary: pd.DataFrame) -> list[str]:
    variants = summary.loc[summary["label"].ne("baseline")].copy()
    grouped = (
        variants.groupby(["family", "parameter"], sort=False)
        .agg(
            variants=("label", "count"),
            best_annual=("annual_return_pct", "max"),
            worst_annual=("annual_return_pct", "min"),
            best_drawdown=("max_drawdown_pct", "max"),
            stable=("stability_pass", "sum"),
        )
        .reset_index()
    )
    lines = [
        "| 参数组 | 参数 | 变体数 | 最好年化 | 最差年化 | 最低回撤 | 稳定性通过 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in grouped.to_dict(orient="records"):
        lines.append(
            f"| `{row['family']}` | `{row['parameter']}` | `{int(row['variants'])}` | "
            f"`{pct(float(row['best_annual']))}` | `{pct(float(row['worst_annual']))}` | "
            f"`{pct(float(row['best_drawdown']))}` | `{int(row['stable'])}` |"
        )
    return lines


def render_markdown(
    quality: dict[str, Any],
    summary: pd.DataFrame,
    slices: pd.DataFrame,
    rolling: pd.DataFrame,
    monthly: pd.DataFrame,
) -> str:
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    variants = summary.loc[summary["label"].ne("baseline")].copy()
    baseline_slices = slices.loc[slices["label"].eq("baseline")]
    helpful = variants.sort_values(
        ["ablation_gate_pass", "stability_pass", "annual_return_pct", "profit_factor"],
        ascending=False,
    ).head(12)
    harmful = variants.sort_values(["annual_return_pct", "profit_factor"]).head(12)
    best_by_parameter = (
        variants.sort_values(
            ["ablation_gate_pass", "stability_pass", "annual_return_pct", "profit_factor"],
            ascending=False,
        )
        .groupby("parameter", sort=False)
        .head(1)
    )
    rolling90 = rolling.loc[rolling["days"].eq(90)]
    worst_rolling90 = rolling90.sort_values("annual_return_pct").head(1)
    target_count = int(summary["meets_core_target"].sum())
    full_count = int(summary["ablation_gate_pass"].sum())
    stable_count = int(summary["stability_pass"].sum())

    lines = [
        f"# {VERSION} 全参数消融 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        "本报告把 2026-06-25 广泛搜索得到的最佳综合策略正式锁定为 V1 研究基线，并在标准 raw/normalized 数据湖上使用修正后的可执行时序重新执行单参数全消融。V1 是可复现基线，不是 live 或 paper-live promotion。",
        "",
        f"- 共评估 `{len(summary)}` 行：`1` 条 V1 基线 + `{len(variants)}` 条单参数或结构替换变体。",
        f"- 原始 core target 通过：`{target_count}/{len(summary)}`。",
        f"- 最近稳定性通过：`{stable_count}/{len(summary)}`。",
        f"- 完整 gate 通过：`{full_count}/{len(summary)}`。",
        "- V1 全样本仍远低于用户要求的 `>=2000%` 年化；Last90 仅接近盈亏平衡，不构成可接受的正向稳定性证据。",
        "",
        "结论：`diagnostic baseline only / not live-ready`。",
        "",
        "## 数据质量",
        "",
        f"- normalized：`{quality['normalized_root']}`；raw：`{quality['raw_root']}`。",
        f"- 覆盖：`{quality['first_ts']}` 到 `{quality['last_ts']}`，共 `{quality['rows']}` 根闭合 `15m` K，normalized/raw 各 `{quality['normalized_files']}` / `{quality['raw_files']}` 个分区。",
        f"- 缺口 `{quality['gap_count']}`；normalized 重复 `{quality['normalized_duplicates']}`；raw 重复 `{quality['raw_duplicates']}`；关键空值 `{quality['critical_nulls']}`；非法 OHLCV/VWAP `{quality['invalid_ohlc_rows']}`。",
        f"- raw/normalized 缺行 `{quality['raw_normalized_missing_rows']}`；字段值不一致合计 `{sum(quality['raw_normalized_value_mismatches'].values())}`；开放 K `{quality['open_bar_rows']}`。",
        f"- data-quality gate：`{quality['quality_gate_pass']}`；来源分布：`{quality['sources']}`。",
        "",
        "## V1 固定口径",
        "",
        "- 信号：`RSI(7)` 反转，low `30`、high `60`，闭合 K 确认。",
        "- 过滤：方向化 `MACD(12,26,9) histogram >= 0`；`ATR96 / close` 在 `0.60%-2.80%`。",
        "- 入场：下一根 `15m` open；单仓、不重叠、多空双向。",
        "- 出场：`TP=0.90%`、`SL=2.80%`、最长 `16` 根 K；同 K 双触发按 stop-first；timeout 在下一根 open 先执行，不读取该根 high/low。",
        "- open 穿越 stop 时按 open 退出；盘中退出后下一根 K 才能重新入场，只有 open 退出允许同一 open 先平后开。",
        (
            f"- 暴露：`1.5x`；每次成交手续费 `{COMMISSION_PER_SIDE:.4%}`，"
            f"每次成交滑点 `{SLIPPAGE_PER_SIDE:.4%}`，"
            f"round-trip `{ROUND_TRIP_COST:.4%}`。"
        ),
        "",
        "| 年化 | 总收益 | 年化倍数 | 回撤 | 胜率 | 笔数 | 笔/日 | PF | 后半段年化 | Last90 年化 |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| `{pct(float(baseline['annual_return_pct']))}` | `{pct(float(baseline['total_return_pct']))}` | `{num(float(baseline['annual_equity_multiple']))}x` | `{pct(float(baseline['max_drawdown_pct']))}` | `{pct(float(baseline['win_rate_pct']))}` | `{int(baseline['trades'])}` | `{num(float(baseline['trades_per_day']))}` | `{num(float(baseline['profit_factor']))}` | `{pct(float(baseline['second_half_annual_return_pct']))}` | `{pct(float(baseline['last_90d_annual_return_pct']))}` |",
        "",
        "## V1 时间切片",
        "",
        *slice_table(baseline_slices),
        "",
        "## 参数覆盖",
        "",
        "所有 V1 生效参数均至少有一个移除、收紧、放宽或邻域替换；替代信号和替代退出属于结构探针，不改变 V1 定义。",
        "",
        *parameter_group_table(summary),
        "",
        "## 表面最好变体",
        "",
        *metric_table(helpful),
        "",
        "## 伤害最大变体",
        "",
        *metric_table(harmful),
        "",
        "## 每个参数的最佳单因子",
        "",
        *metric_table(best_by_parameter),
        "",
        "## 稳健性与实盘边界",
        "",
        f"- 盈利月份：`{int((monthly['total_return_pct'] > 0).sum())}/{len(monthly)}`；最差月总收益 `{pct(float(monthly['total_return_pct'].min()))}`。",
        "- 更高 TP 或更高 exposure 可以抬高样本内收益，但会同步放大回撤；这不是信号质量改善。",
        "- 移除 MACD 或 ATR 过滤后策略显著恶化，说明收益高度依赖搜索得到的窄过滤组合。",
        "- V1 已处理可见的 `15m open` 跳过 stop，但仍没有 tick/盘口级回放，无法覆盖 stop-market 尾部滑点、订单延迟和下单失败。",
        "- 当前没有可重启恢复、订单对账、missing-bar fail-closed、kill switch 和仓位上限的 live runner。",
        "- 永续资金费未计入。虽然最长持仓约 4 小时，跨 funding 时点仍需在 runner 与回测中统一。",
    ]
    if not worst_rolling90.empty:
        row = worst_rolling90.iloc[0]
        lines.append(
            f"- 最差滚动 90d：`{row['window']}`，年化 `{pct(float(row['annual_return_pct']))}`，回撤 `{pct(float(row['max_drawdown_pct']))}`。"
        )
    lines.extend(
        [
            "",
            "因此，V1 只能作为后续 walk-forward、真实 stop-market 压力测试和 runner 设计的对照基线；现在不能直接实盘。",
            "",
            "## 产物",
            "",
            f"- 脚本：`{SCRIPT_PATH}`",
            f"- JSON：`{SUMMARY_JSON_PATH}`",
            f"- 汇总 CSV：`{SUMMARY_CSV_PATH}`",
            f"- 时间切片 CSV：`{SLICES_CSV_PATH}`",
            f"- 滚动 CSV：`{ROLLING_CSV_PATH}`",
            f"- 周度 CSV：`{WEEKLY_CSV_PATH}`",
            f"- 月度 CSV：`{MONTHLY_CSV_PATH}`",
        ]
    )
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return str(value)


def finite_feature(value: float, default: float) -> float:
    return float(value) if np.isfinite(value) else default


def feature_parameter_variants(
    features: pd.DataFrame,
    baseline_raw_trades: list[Any],
) -> list[tuple[engine.VariantSpec, list[Any]]]:
    variants: list[tuple[engine.VariantSpec, list[Any]]] = []
    for fast, slow, signal in ((8, 21, 5), (21, 55, 9), (34, 89, 13)):
        column = f"macd_{fast}_{slow}_{signal}_hist"
        values = features[column].to_numpy("float64")
        trades = [
            replace(
                trade,
                dir_macd=finite_feature(values[trade.signal_i], 0.0) * trade.direction,
            )
            for trade in baseline_raw_trades
        ]
        value = f"{fast}_{slow}_{signal}"
        variants.append(
            (
                engine.VariantSpec(
                    label=f"macd_periods_{value}",
                    family="indicator_period",
                    parameter="macd_periods",
                    value=value,
                    config=engine.BASELINE,
                ),
                trades,
            )
        )

    for window in (14, 48, 336, 672):
        values = features[f"atr_pct{window}"].to_numpy("float64")
        trades = [
            replace(
                trade,
                atr_pct96=finite_feature(values[trade.signal_i], 99.0),
            )
            for trade in baseline_raw_trades
        ]
        variants.append(
            (
                engine.VariantSpec(
                    label=f"atr_window_{window}",
                    family="indicator_period",
                    parameter="atr_window",
                    value=window,
                    config=engine.BASELINE,
                ),
                trades,
            )
        )
    return variants


def simulate_trades_live(
    market: MarketArrays,
    state: SignalState,
    exit_spec: ExitSpec,
    entry_delay_bars: int = 1,
) -> list[EventTrade]:
    if entry_delay_bars < 1:
        raise ValueError("entry_delay_bars must be >= 1")
    trades: list[EventTrade] = []
    n = len(market.open)
    for signal_idx, direction_value in zip(
        state.signal_i,
        state.directions,
        strict=False,
    ):
        entry_i = int(signal_idx + entry_delay_bars)
        if entry_i >= n - 1:
            continue
        forced_exit_i = min(entry_i + exit_spec.max_hold_bars, n - 1)
        if forced_exit_i <= entry_i:
            continue

        direction = int(direction_value)
        entry_price = float(market.open[entry_i])
        stop_price = entry_price * (1 - direction * exit_spec.stop_pct)
        take_profit_price = (
            entry_price * (1 + direction * float(exit_spec.take_profit_pct))
            if exit_spec.kind == "fixed"
            else None
        )
        trail_stop: float | None = None
        best_price = entry_price
        min_path = 0.0
        max_path = 0.0
        exit_i = forced_exit_i
        exit_price = float(market.open[forced_exit_i])
        exit_reason = "max_hold"

        # The timeout open is an order event. Its intrabar high/low is not available yet.
        for i in range(entry_i, forced_exit_i):
            open_price = float(market.open[i])
            high = float(market.high[i])
            low = float(market.low[i])
            if direction == 1:
                min_path = min(min_path, low / entry_price - 1)
                max_path = max(max_path, high / entry_price - 1)
                if open_price <= stop_price:
                    exit_i, exit_price, exit_reason = i, open_price, "stop_gap"
                    break
                if trail_stop is not None and open_price <= trail_stop:
                    exit_i, exit_price, exit_reason = i, open_price, "trailing_gap"
                    break
                if take_profit_price is not None and open_price >= take_profit_price:
                    exit_i, exit_price, exit_reason = (
                        i,
                        take_profit_price,
                        "take_profit_gap",
                    )
                    break
                if low <= stop_price:
                    exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                    break
                if trail_stop is not None and low <= trail_stop:
                    exit_i, exit_price, exit_reason = i, trail_stop, "trailing_stop"
                    break
                if take_profit_price is not None and high >= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break
                if exit_spec.kind == "trailing":
                    best_price = max(best_price, high)
                    if best_price / entry_price - 1 >= float(exit_spec.activation_pct):
                        candidate = best_price * (1 - float(exit_spec.trail_pct))
                        trail_stop = candidate if trail_stop is None else max(trail_stop, candidate)
            else:
                min_path = min(min_path, entry_price / high - 1)
                max_path = max(max_path, entry_price / low - 1)
                if open_price >= stop_price:
                    exit_i, exit_price, exit_reason = i, open_price, "stop_gap"
                    break
                if trail_stop is not None and open_price >= trail_stop:
                    exit_i, exit_price, exit_reason = i, open_price, "trailing_gap"
                    break
                if take_profit_price is not None and open_price <= take_profit_price:
                    exit_i, exit_price, exit_reason = (
                        i,
                        take_profit_price,
                        "take_profit_gap",
                    )
                    break
                if high >= stop_price:
                    exit_i, exit_price, exit_reason = i, stop_price, "stop_loss"
                    break
                if trail_stop is not None and high >= trail_stop:
                    exit_i, exit_price, exit_reason = i, trail_stop, "trailing_stop"
                    break
                if take_profit_price is not None and low <= take_profit_price:
                    exit_i, exit_price, exit_reason = i, take_profit_price, "take_profit"
                    break
                if exit_spec.kind == "trailing":
                    best_price = min(best_price, low)
                    if entry_price / best_price - 1 >= float(exit_spec.activation_pct):
                        candidate = best_price * (1 + float(exit_spec.trail_pct))
                        trail_stop = candidate if trail_stop is None else min(trail_stop, candidate)

        if exit_reason == "max_hold":
            if direction == 1:
                timeout_return = exit_price / entry_price - 1
            else:
                timeout_return = entry_price / exit_price - 1
            min_path = min(min_path, timeout_return)
            max_path = max(max_path, timeout_return)

        raw_return = direction * (exit_price / entry_price - 1)
        signal_i = int(signal_idx)
        trades.append(
            EventTrade(
                signal_i=signal_i,
                entry_i=entry_i,
                exit_i=int(exit_i),
                direction=direction,
                entry_ts=pd.Timestamp(market.ts[entry_i]),
                exit_ts=pd.Timestamp(market.ts[exit_i]),
                entry_price=entry_price,
                exit_price=float(exit_price),
                raw_return=float(raw_return),
                min_path_return=float(min_path),
                max_path_return=float(max_path),
                bars_held=int(max(exit_i - entry_i, 0)),
                exit_reason=exit_reason,
                signal_name=state.spec.name,
                signal_kind=state.spec.kind,
                adx14=finite_feature(market.adx14[signal_i], 0.0),
                rvol96=finite_feature(market.rvol96[signal_i], 0.0),
                h1_dir_spread=(
                    finite_feature(market.h1_spread[signal_i], 0.0) * direction
                ),
                h4_dir_spread=(
                    finite_feature(market.h4_spread[signal_i], 0.0) * direction
                ),
                dir_ret16=finite_feature(market.ret16[signal_i], 0.0) * direction,
                dir_ret48=finite_feature(market.ret48[signal_i], 0.0) * direction,
                dir_ret96=finite_feature(market.ret96[signal_i], 0.0) * direction,
                dir_macd=finite_feature(market.macd_hist[signal_i], 0.0) * direction,
                dir_rsi14=(
                    finite_feature(market.rsi14[signal_i], 50.0)
                    if direction == 1
                    else 100.0 - finite_feature(market.rsi14[signal_i], 50.0)
                ),
                atr_pct96=finite_feature(market.atr_pct96[signal_i], 0.0),
                atr_ratio96_672=finite_feature(
                    market.atr_ratio96_672[signal_i],
                    99.0,
                ),
                previous_signal_age=finite_feature(
                    state.previous_signal_age[signal_i],
                    0.0,
                ),
                churn192=finite_feature(state.churn192[signal_i], 999.0),
            )
        )
    return trades


def selected_trades_live(
    trades: list[EventTrade],
    filter_spec: FilterSpec,
) -> list[EventTrade]:
    selected: list[EventTrade] = []
    available_i = -1
    open_exit_reasons = {"max_hold", "stop_gap", "trailing_gap", "take_profit_gap"}
    for trade in trades:
        if trade.entry_i < available_i or not passes_filter(trade, filter_spec):
            continue
        selected.append(trade)
        intrabar_delay = 0 if trade.exit_reason in open_exit_reasons else 1
        available_i = trade.exit_i + filter_spec.cooldown_bars + intrabar_delay
    return selected


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ABLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    raw, metadata, quality = load_data_lake()
    engine.simulate_trades = simulate_trades_live
    engine.selected_trades = selected_trades_live
    search_engine.selected_trades = selected_trades_live
    start_ts = pd.Timestamp(raw["ts"].min())
    end_ts = pd.Timestamp(raw["ts"].max()) + pd.Timedelta(minutes=15)
    variants = engine.build_variants()
    signals = {variant.config.signal.name: variant.config.signal for variant in variants}
    spans = sorted(
        {
            value
            for signal in signals.values()
            for value in (signal.fast, signal.slow)
            if value
        }
        | {fast for fast, _slow in ema_pairs()}
        | {slow for _fast, slow in ema_pairs()}
    )
    features = add_features(raw, spans)
    market = build_market_arrays(features)
    states = {signal.name: signal_state(features, signal) for signal in signals.values()}
    raw_trade_cache: dict[tuple[str, str], list[Any]] = {}

    summary_rows: list[dict[str, Any]] = []
    slice_rows: list[dict[str, Any]] = []
    baseline_raw_trades: list[Any] | None = None
    print(f"data {start_ts} -> {end_ts} rows={len(raw)}", flush=True)
    for index, variant in enumerate(variants, start=1):
        raw_trades = engine.calculate_raw_trades(
            states=states,
            market=market,
            config=variant.config,
            raw_trade_cache=raw_trade_cache,
        )
        if variant.label == "baseline":
            baseline_raw_trades = raw_trades
        row, slices = engine.evaluate_variant(
            variant=variant,
            raw_trades=raw_trades,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        summary_rows.append(row)
        slice_rows.extend(slices)
        if index % 10 == 0 or index == len(variants):
            print(f"base variant {index}/{len(variants)}", flush=True)

    if baseline_raw_trades is None:
        raise RuntimeError("baseline raw trades were not captured")

    period_variants = feature_parameter_variants(features, baseline_raw_trades)
    for index, (variant, transformed_trades) in enumerate(period_variants, start=1):
        row, variant_slices = engine.evaluate_variant(
            variant=variant,
            raw_trades=transformed_trades,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        summary_rows.append(row)
        slice_rows.extend(variant_slices)
        print(f"indicator-period variant {index}/{len(period_variants)}", flush=True)

    summary = pd.DataFrame(summary_rows)
    baseline = summary.loc[summary["label"].eq("baseline")].iloc[0]
    for column in (
        "annual_return_pct",
        "total_return_pct",
        "annual_equity_multiple",
        "max_drawdown_pct",
        "win_rate_pct",
        "trades_per_day",
        "profit_factor",
    ):
        summary[f"delta_{column}"] = summary[column] - baseline[column]
    summary = summary.sort_values(
        ["ablation_gate_pass", "stability_pass", "annual_return_pct", "profit_factor"],
        ascending=False,
    ).reset_index(drop=True)
    slices = pd.DataFrame(slice_rows)
    rolling = pd.DataFrame(
        engine.window_rows(
            config=engine.BASELINE,
            raw_trades=baseline_raw_trades,
            windows=engine.rolling_windows(start_ts, end_ts),
        )
    )
    weekly = pd.DataFrame(
        engine.window_rows(
            config=engine.BASELINE,
            raw_trades=baseline_raw_trades,
            windows=engine.weekly_windows(start_ts, end_ts),
        )
    )
    monthly = pd.DataFrame(
        engine.window_rows(
            config=engine.BASELINE,
            raw_trades=baseline_raw_trades,
            windows=engine.calendar_month_windows(start_ts, end_ts),
        )
    )

    summary.to_csv(SUMMARY_CSV_PATH, index=False)
    slices.to_csv(SLICES_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    weekly.to_csv(WEEKLY_CSV_PATH, index=False)
    monthly.to_csv(MONTHLY_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(quality, summary, slices, rolling, monthly),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "version": VERSION,
                "status": "diagnostic_baseline_only_not_live_ready",
                "metadata": metadata,
                "data_quality": quality,
                "baseline": {
                    "signal": asdict(engine.BASELINE.signal),
                    "exit": asdict(engine.BASELINE.exit),
                    "filter": asdict(engine.BASELINE.filter),
                    "exposure": engine.BASELINE.exposure,
                },
                "cost_model": {
                    "commission_per_side": COMMISSION_PER_SIDE,
                    "slippage_per_side": SLIPPAGE_PER_SIDE,
                    "round_trip_cost": ROUND_TRIP_COST,
                    "funding_included": False,
                },
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "summary_csv": str(SUMMARY_CSV_PATH),
                    "slices_csv": str(SLICES_CSV_PATH),
                    "rolling_csv": str(ROLLING_CSV_PATH),
                    "weekly_csv": str(WEEKLY_CSV_PATH),
                    "monthly_csv": str(MONTHLY_CSV_PATH),
                },
                "summary": summary.to_dict(orient="records"),
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        summary.head(12)[
            [
                "label",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades",
                "trades_per_day",
                "profit_factor",
                "last_90d_annual_return_pct",
                "ablation_gate_pass",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
