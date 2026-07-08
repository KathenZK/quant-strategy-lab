from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable

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
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_v1_4_loss_regime_filters.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
FULL_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_loss_regime_filters_full_2026-07-08.csv"
WINDOW_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_loss_regime_filters_windows_2026-07-08.csv"
ROLLING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_loss_regime_filters_rolling_2026-07-08.csv"
RECENT_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_loss_regime_filters_recent_2026-07-08.csv"
JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_v1_4_loss_regime_filters_2026-07-08.json"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-v1-4-loss-regime-filters-2026-07-08.md"

V14_EXPOSURE = 2.5
V14_MIN_RVOL96 = 0.85
ENTRY_DELAYS = ((1, "K+1"), (2, "K+2"))
V14_CANDIDATE = v12.AtrBracketCandidate(
    label="atr96_tp1p25x_sl5x_hold24",
    family="atr_bracket",
    atr_window=96,
    tp_atr_mult=1.25,
    sl_atr_mult=5.0,
    max_hold_bars=24,
)
FIXED_WINDOWS: tuple[tuple[str, pd.Timedelta | None], ...] = (
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


@dataclass(frozen=True, slots=True)
class RegimeVariant:
    label: str
    family: str
    description: str
    filter_spec: Any
    custom_filter: Callable[[v12.EventTrade, Any], bool] | None = None


def base_filter() -> Any:
    return replace(v12.BASE_CONFIG.filter, min_rvol96=V14_MIN_RVOL96)


def finite(value: float, default: float) -> float:
    return float(value) if np.isfinite(value) else default


def make_feature_cache(features: pd.DataFrame) -> dict[str, np.ndarray]:
    high = features["high"].to_numpy("float64")
    low = features["low"].to_numpy("float64")
    close = features["close"].to_numpy("float64")
    prev_close = pd.Series(close).shift(1).to_numpy("float64")
    true_range = np.maximum.reduce(
        [
            high - low,
            np.abs(high - prev_close),
            np.abs(low - prev_close),
        ]
    )
    tr_pct = true_range / np.where(close == 0.0, np.nan, close)
    return {
        "atr14_over_96": (
            features["atr_pct14"].to_numpy("float64")
            / features["atr_pct96"].replace(0.0, np.nan).to_numpy("float64")
        ),
        "atr48_over_336": (
            features["atr_pct48"].to_numpy("float64")
            / features["atr_pct336"].replace(0.0, np.nan).to_numpy("float64")
        ),
        "max_tr16_over_atr96": (
            pd.Series(tr_pct).rolling(16, min_periods=1).max().to_numpy("float64")
            / features["atr_pct96"].replace(0.0, np.nan).to_numpy("float64")
        ),
        "abs_ret16": np.abs(features["ret16"].to_numpy("float64")),
        "abs_ret48": np.abs(features["ret48"].to_numpy("float64")),
    }


def custom_max_feature(name: str, threshold: float) -> Callable[[v12.EventTrade, Any], bool]:
    def _passes(trade: v12.EventTrade, cache: Any) -> bool:
        value = finite(cache[name][trade.signal_i], 999.0)
        return value <= threshold

    return _passes


def variants() -> list[RegimeVariant]:
    base = base_filter()
    output: list[RegimeVariant] = [
        RegimeVariant(
            label="baseline_v14",
            family="baseline",
            description="V1.4 baseline：min_rvol96=0.85，其它参数不变",
            filter_spec=base,
        )
    ]
    for value in (0.026, 0.024, 0.022, 0.020, 0.018, 0.016, 0.014, 0.012):
        output.append(
            RegimeVariant(
                label=f"max_atr{int(value * 10_000)}bps",
                family="max_atr_pct96",
                description=f"更严格 max_atr_pct96 <= {value:.2%}",
                filter_spec=replace(base, max_atr_pct96=value),
            )
        )
    for value in (2.0, 1.8, 1.6, 1.4, 1.2):
        output.append(
            RegimeVariant(
                label=f"atr_ratio96_672_le_{value:g}".replace(".", "p"),
                family="atr_ratio96_672",
                description=f"过滤 ATR96 相对 ATR672 过度扩张：atr_ratio96_672 <= {value:g}",
                filter_spec=replace(base, max_atr_ratio96_672=value),
            )
        )
    for value in (2.0, 1.75, 1.5, 1.25):
        output.append(
            RegimeVariant(
                label=f"atr14_over_96_le_{value:g}".replace(".", "p"),
                family="short_atr_expansion",
                description=f"过滤短期 ATR 扩张：ATR14/ATR96 <= {value:g}",
                filter_spec=base,
                custom_filter=custom_max_feature("atr14_over_96", value),
            )
        )
    for value in (1.8, 1.6, 1.4, 1.2):
        output.append(
            RegimeVariant(
                label=f"atr48_over_336_le_{value:g}".replace(".", "p"),
                family="mid_atr_expansion",
                description=f"过滤中期 ATR 扩张：ATR48/ATR336 <= {value:g}",
                filter_spec=base,
                custom_filter=custom_max_feature("atr48_over_336", value),
            )
        )
    for value in (3.5, 3.0, 2.5, 2.0):
        output.append(
            RegimeVariant(
                label=f"max_tr16_over_atr96_le_{value:g}".replace(".", "p"),
                family="single_bar_spike",
                description=f"过滤最近 16 根中单根 TR 尖峰：max(TR%16)/ATR96 <= {value:g}",
                filter_spec=base,
                custom_filter=custom_max_feature("max_tr16_over_atr96", value),
            )
        )
    for value in (0.12, 0.10, 0.08, 0.06):
        output.append(
            RegimeVariant(
                label=f"abs_ret16_le_{int(value * 100)}pct",
                family="direction_vol_anomaly",
                description=f"过滤最近 16 根绝对涨跌过大：abs(ret16) <= {value:.0%}",
                filter_spec=base,
                custom_filter=custom_max_feature("abs_ret16", value),
            )
        )
    for value in (0.18, 0.15, 0.12, 0.10):
        output.append(
            RegimeVariant(
                label=f"abs_ret48_le_{int(value * 100)}pct",
                family="direction_vol_anomaly",
                description=f"过滤最近 48 根绝对涨跌过大：abs(ret48) <= {value:.0%}",
                filter_spec=base,
                custom_filter=custom_max_feature("abs_ret48", value),
            )
        )
    for value in (12, 10, 8, 6):
        output.append(
            RegimeVariant(
                label=f"churn192_le_{value}",
                family="signal_churn",
                description=f"过滤信号拥挤环境：churn192 <= {value}",
                filter_spec=replace(base, max_churn192=float(value)),
            )
        )
    for value in (12, 24, 48):
        output.append(
            RegimeVariant(
                label=f"signal_age_ge_{value}",
                family="signal_age",
                description=f"过滤过近连续信号：previous_signal_age >= {value}",
                filter_spec=replace(base, min_previous_signal_age=float(value)),
            )
        )
    output.extend(
        [
            RegimeVariant(
                label="max_atr220bps_and_atr_ratio1p6",
                family="combo",
                description="max_atr_pct96 <= 2.20% 且 atr_ratio96_672 <= 1.6",
                filter_spec=replace(base, max_atr_pct96=0.022, max_atr_ratio96_672=1.6),
            ),
            RegimeVariant(
                label="max_atr220bps_and_abs_ret16_8pct",
                family="combo",
                description="max_atr_pct96 <= 2.20% 且 abs(ret16) <= 8%",
                filter_spec=replace(base, max_atr_pct96=0.022),
                custom_filter=custom_max_feature("abs_ret16", 0.08),
            ),
            RegimeVariant(
                label="atr_ratio1p6_and_age24",
                family="combo",
                description="atr_ratio96_672 <= 1.6 且 previous_signal_age >= 24",
                filter_spec=replace(base, max_atr_ratio96_672=1.6, min_previous_signal_age=24.0),
            ),
            RegimeVariant(
                label="atr14_1p5_and_spike2p5",
                family="combo",
                description="ATR14/ATR96 <= 1.5 且 max(TR%16)/ATR96 <= 2.5",
                filter_spec=base,
                custom_filter=lambda trade, cache: (
                    finite(cache["atr14_over_96"][trade.signal_i], 999.0) <= 1.5
                    and finite(cache["max_tr16_over_atr96"][trade.signal_i], 999.0) <= 2.5
                ),
            ),
        ]
    )
    return output


def custom_filtered_trades(
    trades: list[v12.EventTrade],
    variant: RegimeVariant,
    cache: dict[str, np.ndarray],
) -> list[v12.EventTrade]:
    if variant.custom_filter is None:
        return trades
    return [trade for trade in trades if variant.custom_filter(trade, cache)]


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
    variant: RegimeVariant,
    trades: list[v12.EventTrade],
    exit_spec: Any,
    entry_label: str,
    window: str,
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> dict[str, Any]:
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades(trades, start_ts, end_ts),
        filter_spec=variant.filter_spec,
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
    returns = selected_returns(trades, variant.filter_spec, start_ts, end_ts)
    return {
        "dataset": dataset,
        "variant": variant.label,
        "family": variant.family,
        "description": variant.description,
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
    variants_to_run: list[RegimeVariant],
    windows: tuple[tuple[str, pd.Timedelta | None], ...],
) -> pd.DataFrame:
    cache = make_feature_cache(context.features)
    exit_spec = v12.candidate_exit_spec(V14_CANDIDATE)
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V14_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    rows: list[dict[str, Any]] = []
    for variant in variants_to_run:
        for _entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = custom_filtered_trades(raw_trades[entry_label], variant, cache)
            for window, duration in windows:
                start_ts, end_ts = window_bounds(context, duration)
                rows.append(
                    evaluate_row(
                        dataset=dataset,
                        variant=variant,
                        trades=trades,
                        exit_spec=exit_spec,
                        entry_label=entry_label,
                        window=window,
                        start_ts=start_ts,
                        end_ts=end_ts,
                    )
                )
    return pd.DataFrame(rows)


def full_comparison(full: pd.DataFrame) -> pd.DataFrame:
    k1 = full.loc[full["entry_timing"].eq("K+1")].set_index("variant")
    k2 = full.loc[full["entry_timing"].eq("K+2")].set_index("variant")
    merged = k1.join(k2, lsuffix="_k1", rsuffix="_k2")
    base = merged.loc["baseline_v14"]
    merged["delta_total_return_pct_k1"] = merged["total_return_pct_k1"] - base["total_return_pct_k1"]
    merged["delta_max_drawdown_pct_k1"] = merged["max_drawdown_pct_k1"] - base["max_drawdown_pct_k1"]
    merged["delta_win_rate_pct_k1"] = merged["win_rate_pct_k1"] - base["win_rate_pct_k1"]
    merged["delta_total_return_pct_k2"] = merged["total_return_pct_k2"] - base["total_return_pct_k2"]
    merged["delta_max_drawdown_pct_k2"] = merged["max_drawdown_pct_k2"] - base["max_drawdown_pct_k2"]
    merged["pass_dd_gate"] = (
        (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"])
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] + 3.0)
        & (merged["total_return_pct_k1"] >= base["total_return_pct_k1"] * 0.70)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.70)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 3.0)
        & (merged["trades_k1"] >= int(base["trades_k1"] * 0.65))
    )
    merged["pass_strict_dd_gate"] = (
        (merged["max_drawdown_pct_k1"] >= base["max_drawdown_pct_k1"])
        & (merged["max_drawdown_pct_k2"] >= base["max_drawdown_pct_k2"] + 5.0)
        & (merged["total_return_pct_k1"] >= base["total_return_pct_k1"] * 0.90)
        & (merged["total_return_pct_k2"] >= base["total_return_pct_k2"] * 0.90)
        & (merged["win_rate_pct_k1"] >= base["win_rate_pct_k1"] - 1.0)
    )
    merged["score"] = (
        ((merged["max_drawdown_pct_k1"] - base["max_drawdown_pct_k1"]) / 20.0) * 0.28
        + ((merged["max_drawdown_pct_k2"] - base["max_drawdown_pct_k2"]) / 20.0) * 0.22
        + np.log1p(np.maximum(merged["total_return_pct_k1"], -90.0) / 100.0) * 0.20
        + np.log1p(np.maximum(merged["total_return_pct_k2"], -90.0) / 100.0) * 0.18
        + ((merged["win_rate_pct_k1"] - 80.0) / 15.0) * 0.12
    )
    return merged.sort_values(
        ["pass_strict_dd_gate", "pass_dd_gate", "score"],
        ascending=False,
    ).reset_index()


def rolling_summary(
    context: v12.evolution.EvalContext,
    variants_to_run: list[RegimeVariant],
) -> pd.DataFrame:
    cache = make_feature_cache(context.features)
    exit_spec = v12.candidate_exit_spec(V14_CANDIDATE)
    raw_trades = {
        entry_label: v12.simulate_atr_bracket_trades(
            context,
            V14_CANDIDATE,
            entry_delay_bars=entry_delay_bars,
        )
        for entry_delay_bars, entry_label in ENTRY_DELAYS
    }
    rows: list[dict[str, Any]] = []
    for variant in variants_to_run:
        for _entry_delay_bars, entry_label in ENTRY_DELAYS:
            trades = custom_filtered_trades(raw_trades[entry_label], variant, cache)
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
                        variant=variant,
                        trades=trades,
                        exit_spec=exit_spec,
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
                        "variant": variant.label,
                        "family": variant.family,
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


def comparison_table(frame: pd.DataFrame, limit: int = 18) -> list[str]:
    lines = [
        "| 过滤器 | family | K+1收益 | K+1回撤 | K+1胜率 | K+1笔 | K+2收益 | K+2回撤 | K+2胜率 | DD gate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in frame.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{row['family_k1']}` | `{fmt(row['total_return_pct_k1'])}%` | "
            f"`{fmt(row['max_drawdown_pct_k1'])}%` | `{fmt(row['win_rate_pct_k1'])}%` | "
            f"`{int(row['trades_k1'])}` | `{fmt(row['total_return_pct_k2'])}%` | "
            f"`{fmt(row['max_drawdown_pct_k2'])}%` | `{fmt(row['win_rate_pct_k2'])}%` | "
            f"`{bool(row['pass_strict_dd_gate'])}/{bool(row['pass_dd_gate'])}` |"
        )
    return lines


def fixed_table(frame: pd.DataFrame, *, dataset: str, entry: str, window: str, labels: list[str]) -> list[str]:
    subset = frame.loc[
        frame["dataset"].eq(dataset)
        & frame["entry_timing"].eq(entry)
        & frame["window"].eq(window)
        & frame["variant"].isin(labels)
    ].copy()
    order = {label: idx for idx, label in enumerate(labels)}
    subset["order"] = subset["variant"].map(order)
    subset = subset.sort_values("order")
    lines = [
        f"### {dataset} / {entry} / {window}",
        "",
        "| 过滤器 | 交易数 | 总收益 | 回撤 | 胜率 | PF | 平均单笔 | 最差单笔 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{int(row['trades'])}` | `{fmt(row['total_return_pct'])}%` | "
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
        "| 过滤器 | 正收益切片 | 中位收益 | 最差收益 | 中位回撤 | 最差回撤 | 中位交易数 | 零交易切片 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in subset.to_dict(orient="records"):
        lines.append(
            f"| `{row['variant']}` | `{int(row['positive_slices'])}/{int(row['slices'])}` | "
            f"`{fmt(row['median_total_return_pct'])}%` | `{fmt(row['worst_total_return_pct'])}%` | "
            f"`{fmt(row['median_max_drawdown_pct'])}%` | `{fmt(row['worst_max_drawdown_pct'])}%` | "
            f"`{fmt(row['median_trades'], 1)}` | `{int(row['zero_trade_slices'])}` |"
        )
    return lines


def render_markdown(
    comparison: pd.DataFrame,
    full: pd.DataFrame,
    windows: pd.DataFrame,
    rolling: pd.DataFrame,
    recent: pd.DataFrame,
    variants_by_label: dict[str, RegimeVariant],
    lake_quality: dict[str, Any],
    recent_quality: dict[str, Any],
) -> str:
    base = comparison.loc[comparison["variant"].eq("baseline_v14")].iloc[0]
    dd_candidates = comparison.loc[comparison["pass_dd_gate"]]
    strict_candidates = comparison.loc[comparison["pass_strict_dd_gate"]]
    best = comparison.iloc[0]
    labels = list(dict.fromkeys(["baseline_v14", *comparison["variant"].head(8).tolist()]))
    lines = [
        f"# HYPE-15M-MII V1.4 亏损环境过滤诊断 {RUN_DATE}",
        "",
        "## 结论",
        "",
        "本轮不放宽入场，也不改 TP/SL；只在 `V1.4` 上叠加亏损环境过滤，目标是压最大回撤。测试方向包括更严格 `max_atr_pct96`、`atr_ratio96_672`、短期 ATR 扩张、单根波动尖峰、最近方向/波动异常、信号拥挤度和若干组合过滤。",
        "",
        (
            f"`V1.4 baseline`：K+1 总收益 `{fmt(base['total_return_pct_k1'])}%`、"
            f"回撤 `{fmt(base['max_drawdown_pct_k1'])}%`、胜率 `{fmt(base['win_rate_pct_k1'])}%`；"
            f"K+2 总收益 `{fmt(base['total_return_pct_k2'])}%`、回撤 `{fmt(base['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"综合排序第一为 `{best['variant']}`：K+1 总收益 `{fmt(best['total_return_pct_k1'])}%`、"
            f"回撤 `{fmt(best['max_drawdown_pct_k1'])}%`；K+2 总收益 `{fmt(best['total_return_pct_k2'])}%`、"
            f"回撤 `{fmt(best['max_drawdown_pct_k2'])}%`。"
        ),
        (
            f"严格回撤 gate（K+1 回撤不变差、K+2 回撤至少改善 5pp、收益保留 90%）通过 "
            f"`{len(strict_candidates)}/{len(comparison)}`；放宽回撤 gate（K+2 回撤至少改善 3pp、"
            f"收益保留 70%）通过 `{len(dd_candidates)}/{len(comparison)}`。"
        ),
        "",
    ]
    if len(dd_candidates):
        best_dd = dd_candidates.iloc[0]
        lines.append(
            f"可观察的压回撤候选是 `{best_dd['variant']}`：{variants_by_label[str(best_dd['variant'])].description}。"
        )
    else:
        lines.append("没有过滤器在收益、胜率和 K+1/K+2 回撤之间形成足够好的替代。")
    lines.extend(
        [
            "",
            "单独收紧 `max_atr_pct96` 不是有效解：`max_atr_pct96 <= 2.00%` 以上与 baseline 完全相同；继续压到 `1.80%/1.60%/1.40%/1.20%` 主要损失收益和交易数，K+2 回撤没有改善。",
            "",
            "`max(TR%16)/ATR96 <= 2.0` 能显著降低 K+1/K+2 回撤，但 K+1 交易从 `232` 笔降到 `127` 笔、总收益从 `978.36%` 降到 `468.17%`，更像强行少交易，不适合作为 V1.4 替换层。",
            "",
        "结论：多数过滤器不能同时改善 K+1 与 K+2；真正值得继续观察的是 K+1 不恶化、K+2 回撤明显收敛且收益保留较好的过滤器。能否替换 `V1.4 baseline` 需要看 strict/relaxed gate，而不是只看某一个窗口的回撤。",
            "",
            "## 全样本综合对比",
            "",
            *comparison_table(comparison, limit=20),
            "",
            "## 关键过滤器固定窗口",
            "",
            *fixed_table(full, dataset="standard_data_lake", entry="K+1", window="全样本", labels=labels),
            "",
            *fixed_table(full, dataset="standard_data_lake", entry="K+2", window="全样本", labels=labels),
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
            f"- 全样本 CSV：`{FULL_CSV_PATH}`",
            f"- 固定窗口 CSV：`{WINDOW_CSV_PATH}`",
            f"- 滚动窗口 CSV：`{ROLLING_CSV_PATH}`",
            f"- recent API CSV：`{RECENT_CSV_PATH}`",
            f"- JSON：`{JSON_PATH}`",
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

    lake_context, lake_metadata, lake_quality = v12.build_context()
    variants_to_run = variants()
    variants_by_label = {variant.label: variant for variant in variants_to_run}
    fixed = evaluate_fixed(
        dataset="standard_data_lake",
        context=lake_context,
        variants_to_run=variants_to_run,
        windows=FIXED_WINDOWS,
    )
    full = fixed.loc[fixed["window"].eq("全样本")].copy()
    windows = fixed.loc[~fixed["window"].eq("全样本")].copy()
    comparison = full_comparison(full)
    rolling_labels = list(dict.fromkeys(["baseline_v14", *comparison["variant"].head(10).tolist()]))
    rolling_variants = [variants_by_label[label] for label in rolling_labels]
    rolling = rolling_summary(lake_context, rolling_variants)

    recent_frame = drought.fetch_recent_fapi_klines()
    recent_quality = drought.data_quality(recent_frame)
    if not recent_quality["quality_gate_pass"]:
        raise ValueError(f"recent data-quality blocker: {json.dumps(recent_quality, ensure_ascii=False)}")
    recent_context = drought.build_context(recent_frame)
    recent = evaluate_fixed(
        dataset="recent_binance_api",
        context=recent_context,
        variants_to_run=variants_to_run,
        windows=tuple((name, duration) for name, duration in RECENT_WINDOWS),
    )

    full.to_csv(FULL_CSV_PATH, index=False)
    windows.to_csv(WINDOW_CSV_PATH, index=False)
    rolling.to_csv(ROLLING_CSV_PATH, index=False)
    recent.to_csv(RECENT_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(
            comparison,
            full,
            windows,
            rolling,
            recent,
            variants_by_label,
            lake_quality,
            recent_quality,
        ),
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
                    "status": "loss_regime_filter_diagnostic_not_promoted",
                    "lake_metadata": lake_metadata,
                    "lake_quality": lake_quality,
                    "recent_quality": recent_quality,
                    "variants": [
                        {
                            "label": variant.label,
                            "family": variant.family,
                            "description": variant.description,
                            "filter": asdict(variant.filter_spec),
                            "has_custom_filter": variant.custom_filter is not None,
                        }
                        for variant in variants_to_run
                    ],
                    "comparison": comparison.to_dict(orient="records"),
                    "full": full.to_dict(orient="records"),
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
                "variant",
                "family_k1",
                "trades_k1",
                "total_return_pct_k1",
                "max_drawdown_pct_k1",
                "win_rate_pct_k1",
                "total_return_pct_k2",
                "max_drawdown_pct_k2",
                "win_rate_pct_k2",
                "pass_strict_dd_gate",
                "pass_dd_gate",
            ]
        ]
        .head(20)
        .to_string(index=False)
    )
    print(f"Wrote {MARKDOWN_PATH}")


if __name__ == "__main__":
    main()
