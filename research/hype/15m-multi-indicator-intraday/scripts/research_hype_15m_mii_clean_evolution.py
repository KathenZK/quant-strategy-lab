from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import OrderedDict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import research_hype_15m_mii_v1_full_ablation as v1  # noqa: E402
from research_hype_15m_mii_search import (  # noqa: E402
    COMMISSION_PER_SIDE,
    ExitSpec,
    FilterSpec,
    SignalSpec,
    ROUND_TRIP_COST,
    SLIPPAGE_PER_SIDE,
    add_features,
    build_market_arrays,
    rsi,
    signal_state,
)


FAMILY = "HYPE-15M-Multi-Indicator-Intraday"
RUN_DATE = "2026-06-29"
FAMILY_DIR = Path("research/hype/15m-multi-indicator-intraday")
SCRIPT_PATH = FAMILY_DIR / "scripts" / "research_hype_15m_mii_clean_evolution.py"
ARTIFACTS_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
SUMMARY_JSON_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_2026-06-29.json"
RANKING_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_ranking_2026-06-29.csv"
PARETO_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_pareto_2026-06-29.csv"
SLICES_CSV_PATH = ARTIFACTS_DIR / "hype_15m_mii_clean_evolution_slices_2026-06-29.csv"
MARKDOWN_PATH = NOTES_DIR / "hype-15m-mii-clean-parameter-evolution-2026-06-29.md"

FIXED_MACD_PERIODS = (12, 26, 9)
FIXED_ATR_WINDOW = 96
MAX_ATR_PCT_GUARDRAIL = 0.028
TIMEFRAME_MINUTES = 15

GENE_OPTIONS: dict[str, tuple[Any, ...]] = {
    "rsi_window": (5, 7, 9, 11, 14),
    "rsi_low": (20.0, 25.0, 30.0, 35.0, 40.0),
    "rsi_high": (55.0, 60.0, 65.0, 70.0, 75.0, 80.0),
    "min_atr_pct96": (0.0045, 0.006, 0.0075, 0.009, 0.0105),
    "min_rvol96": (0.0, 0.5, 0.75, 1.0),
    "h1_confirm": (False, True),
    "rsi14_band": (False, True),
    "take_profit_pct": (0.006, 0.0075, 0.009, 0.0105, 0.012, 0.015),
    "stop_pct": (0.018, 0.024, 0.028, 0.032, 0.036, 0.045),
    "max_hold_bars": (8, 12, 16, 24, 32, 48),
    "exposure": (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0),
}
GENE_NAMES = tuple(GENE_OPTIONS)


@dataclass(frozen=True, slots=True)
class CleanConfig:
    rsi_window: int = 7
    rsi_low: float = 30.0
    rsi_high: float = 60.0
    min_atr_pct96: float = 0.006
    min_rvol96: float = 0.0
    h1_confirm: bool = False
    rsi14_band: bool = False
    take_profit_pct: float = 0.009
    stop_pct: float = 0.028
    max_hold_bars: int = 16
    exposure: float = 1.5

    @property
    def signal(self) -> SignalSpec:
        return SignalSpec(
            name=(
                f"rsi_reversal_w{self.rsi_window}"
                f"_lo{value_slug(self.rsi_low)}_hi{value_slug(self.rsi_high)}"
            ),
            kind="rsi_reversal",
            window=self.rsi_window,
            low=self.rsi_low,
            high=self.rsi_high,
        )

    @property
    def exit(self) -> ExitSpec:
        return ExitSpec(
            kind="fixed",
            take_profit_pct=self.take_profit_pct,
            stop_pct=self.stop_pct,
            max_hold_bars=self.max_hold_bars,
        )

    @property
    def filter(self) -> FilterSpec:
        return FilterSpec(
            min_rvol96=self.min_rvol96,
            min_h1_dir_spread=0.0 if self.h1_confirm else -99.0,
            min_dir_macd=0.0,
            min_dir_rsi14=48.0 if self.rsi14_band else 0.0,
            max_dir_rsi14=78.0 if self.rsi14_band else 100.0,
            min_atr_pct96=self.min_atr_pct96,
            max_atr_pct96=MAX_ATR_PCT_GUARDRAIL,
        )

    @property
    def name(self) -> str:
        return (
            f"clean_rsi{self.rsi_window}_{value_slug(self.rsi_low)}_"
            f"{value_slug(self.rsi_high)}_atrmin{pct_slug(self.min_atr_pct96)}_"
            f"rvol{value_slug(self.min_rvol96)}_h1{int(self.h1_confirm)}_"
            f"rsi14b{int(self.rsi14_band)}_tp{pct_slug(self.take_profit_pct)}_"
            f"sl{pct_slug(self.stop_pct)}_hold{self.max_hold_bars}_"
            f"x{value_slug(self.exposure)}"
        )


@dataclass(slots=True)
class EvalContext:
    features: pd.DataFrame
    market: Any
    start_ts: pd.Timestamp
    end_ts: pd.Timestamp
    signal_cache: dict[str, Any]
    trade_cache: OrderedDict[tuple[str, str], list[Any]]
    trade_cache_limit: int = 256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Time-slice-constrained evolution for the clean HYPE 15m MII baseline."
    )
    parser.add_argument("--population", type=int, default=420)
    parser.add_argument("--generations", type=int, default=12)
    parser.add_argument("--elite", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260629)
    return parser.parse_args()


def value_slug(value: float) -> str:
    return f"{value:g}".replace("-", "m").replace(".", "p")


def pct_slug(value: float) -> str:
    return value_slug(value * 10_000)


def valid_config(config: CleanConfig) -> bool:
    return config.rsi_high - config.rsi_low >= 15.0


def random_config(rng: random.Random) -> CleanConfig:
    while True:
        config = CleanConfig(
            **{name: rng.choice(options) for name, options in GENE_OPTIONS.items()}
        )
        if valid_config(config):
            return config


def mutate(config: CleanConfig, rng: random.Random) -> CleanConfig:
    values = asdict(config)
    mutation_count = 1 if rng.random() < 0.65 else rng.choice((2, 3))
    for name in rng.sample(GENE_NAMES, mutation_count):
        options = GENE_OPTIONS[name]
        current_i = options.index(values[name])
        if rng.random() < 0.75:
            candidates = [index for index in (current_i - 1, current_i + 1) if 0 <= index < len(options)]
            values[name] = options[rng.choice(candidates)] if candidates else rng.choice(options)
        else:
            values[name] = rng.choice(options)
    candidate = CleanConfig(**values)
    return candidate if valid_config(candidate) else mutate(config, rng)


def crossover(left: CleanConfig, right: CleanConfig, rng: random.Random) -> CleanConfig:
    left_values = asdict(left)
    right_values = asdict(right)
    values = {
        name: left_values[name] if rng.random() < 0.5 else right_values[name]
        for name in GENE_NAMES
    }
    candidate = CleanConfig(**values)
    return candidate if valid_config(candidate) else mutate(left, rng)


def add_rsi_features(features: pd.DataFrame) -> pd.DataFrame:
    enriched = features.copy()
    close = enriched["close"].astype("float64")
    for window in GENE_OPTIONS["rsi_window"]:
        column = f"rsi{window}"
        if column not in enriched:
            enriched[column] = rsi(close, int(window))
    return enriched


def raw_trades(context: EvalContext, config: CleanConfig) -> list[Any]:
    key = (config.signal.name, config.exit.name)
    if key in context.trade_cache:
        context.trade_cache.move_to_end(key)
        return context.trade_cache[key]
    if config.signal.name not in context.signal_cache:
        context.signal_cache[config.signal.name] = signal_state(context.features, config.signal)
    trades = v1.simulate_trades_live(
        context.market,
        context.signal_cache[config.signal.name],
        config.exit,
    )
    context.trade_cache[key] = trades
    context.trade_cache.move_to_end(key)
    while len(context.trade_cache) > context.trade_cache_limit:
        context.trade_cache.popitem(last=False)
    return trades


def empty_metrics() -> dict[str, float | int]:
    return {
        "annual_return_pct": -100.0,
        "annual_equity_multiple": 0.0,
        "total_return_pct": -100.0,
        "max_drawdown_pct": -100.0,
        "win_rate_pct": 0.0,
        "trades": 0,
        "trades_per_day": 0.0,
        "profit_factor": 0.0,
    }


def evaluate_window(
    context: EvalContext,
    config: CleanConfig,
    trades: list[Any],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    *,
    purge_end: bool,
) -> dict[str, Any]:
    selection_end = end_ts
    if purge_end:
        selection_end -= pd.Timedelta(
            minutes=TIMEFRAME_MINUTES * config.max_hold_bars
        )
    window_trades = [
        trade for trade in trades if start_ts <= trade.entry_ts < selection_end
    ]
    period_days = max((end_ts - start_ts).total_seconds() / 86_400, 1.0)
    result = v1.engine.evaluate_trades(
        trades=window_trades,
        filter_spec=config.filter,
        exposure=config.exposure,
        period_days=period_days,
        exit_spec=config.exit,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    return empty_metrics() if result is None else asdict(result)


def evaluation_windows(
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
) -> list[tuple[str, pd.Timestamp, pd.Timestamp, bool]]:
    duration = end_ts - start_ts
    midpoint = start_ts + duration / 2
    quarter = duration / 4
    windows = [
        ("full", start_ts, end_ts, False),
        ("first_half", start_ts, midpoint, True),
        ("second_half", midpoint, end_ts, False),
        ("last90", max(start_ts, end_ts - pd.Timedelta(days=90)), end_ts, False),
    ]
    windows.extend(
        (
            f"q{index + 1}",
            start_ts + quarter * index,
            start_ts + quarter * (index + 1),
            index < 3,
        )
        for index in range(4)
    )
    return windows


def safe_log_multiple(annual_return_pct: float) -> float:
    return math.log(max(0.01, 1.0 + annual_return_pct / 100.0))


def score_row(row: dict[str, Any]) -> float:
    quarter_logs = [safe_log_multiple(float(row[f"q{index}_annual_return_pct"])) for index in range(1, 5)]
    capped_profit_factor = min(max(float(row["profit_factor"]), 0.05), 5.0)
    score = (
        2.8 * safe_log_multiple(float(row["annual_return_pct"]))
        + 0.8 * safe_log_multiple(float(row["second_half_annual_return_pct"]))
        + 0.9 * safe_log_multiple(float(row["last90_annual_return_pct"]))
        + 0.55 * float(np.median(quarter_logs))
        + 0.35 * min(quarter_logs)
        + 0.035 * (float(row["win_rate_pct"]) - 70.0)
        + 0.8 * math.log(capped_profit_factor)
        + 0.06 * float(row["max_drawdown_pct"])
    )
    drawdown_gap = max(0.0, -20.0 - float(row["max_drawdown_pct"]))
    win_gap = max(0.0, 70.0 - float(row["win_rate_pct"]))
    trades_gap = max(0.0, 150.0 - float(row["trades"]))
    frequency = float(row["trades_per_day"])
    frequency_gap = max(0.0, 0.5 - frequency) + max(0.0, frequency - 2.0) * 0.5
    score -= drawdown_gap * 0.45 + win_gap * 0.18 + trades_gap / 100.0
    score -= frequency_gap * 2.0
    if float(row["second_half_annual_return_pct"]) <= 0:
        score -= 1.0
    if float(row["last90_annual_return_pct"]) <= 0:
        score -= 1.2
    score -= 0.08 * int(bool(row["h1_confirm"]))
    score -= 0.08 * int(bool(row["rsi14_band"]))
    score -= 0.04 * int(float(row["min_rvol96"]) > 0)
    return score


def evaluate_config(context: EvalContext, config: CleanConfig) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    trades = raw_trades(context, config)
    slice_rows: list[dict[str, Any]] = []
    for label, start_ts, end_ts, purge_end in evaluation_windows(
        context.start_ts,
        context.end_ts,
    ):
        metrics = evaluate_window(
            context,
            config,
            trades,
            start_ts,
            end_ts,
            purge_end=purge_end,
        )
        slice_row = {
            "slice": label,
            "slice_start": start_ts.isoformat(),
            "slice_end": end_ts.isoformat(),
            "purge_end": purge_end,
            **metrics,
        }
        slice_row["engine_name"] = str(slice_row.get("name", ""))
        slice_row["name"] = config.name
        slice_rows.append(slice_row)
    slices = {row["slice"]: row for row in slice_rows}
    full = slices["full"]
    row: dict[str, Any] = {**asdict(config), **full}
    row["engine_name"] = str(row.get("name", ""))
    row["name"] = config.name
    for label in ("first_half", "second_half", "last90", "q1", "q2", "q3", "q4"):
        for field in (
            "annual_return_pct",
            "max_drawdown_pct",
            "win_rate_pct",
            "trades",
            "trades_per_day",
            "profit_factor",
        ):
            row[f"{label}_{field}"] = slices[label][field]
    row["positive_quarters"] = sum(
        float(row[f"q{index}_annual_return_pct"]) > 0 for index in range(1, 5)
    )
    row["risk_feasible"] = bool(
        row["max_drawdown_pct"] >= -20.0
        and row["win_rate_pct"] >= 70.0
        and 0.5 <= row["trades_per_day"] <= 2.0
        and row["trades"] >= 150
        and row["second_half_annual_return_pct"] > 0
        and row["last90_annual_return_pct"] > 0
    )
    row["strict_original_target"] = bool(
        row["annual_return_pct"] >= 2000.0
        and row["max_drawdown_pct"] >= -20.0
        and row["win_rate_pct"] >= 70.0
        and 0.75 <= row["trades_per_day"] <= 2.25
        and row["second_half_annual_return_pct"] > 0
        and row["last90_annual_return_pct"] > 0
    )
    row["score"] = score_row(row)
    return row, slice_rows


def evaluate_population(
    context: EvalContext,
    configs: list[CleanConfig],
    evaluation_cache: dict[CleanConfig, dict[str, Any]],
    slice_cache: dict[CleanConfig, list[dict[str, Any]]],
) -> None:
    for config in configs:
        if config in evaluation_cache:
            continue
        row, slices = evaluate_config(context, config)
        evaluation_cache[config] = row
        slice_cache[config] = slices


def unique_configs(configs: list[CleanConfig]) -> list[CleanConfig]:
    return list(dict.fromkeys(configs))


def seed_population(rng: random.Random, population_size: int) -> list[CleanConfig]:
    baseline = CleanConfig()
    seeds = [
        baseline,
        replace(baseline, min_atr_pct96=0.009),
        replace(baseline, min_rvol96=0.75),
        replace(baseline, min_rvol96=1.0),
        replace(baseline, h1_confirm=True),
        replace(baseline, rsi14_band=True),
        replace(baseline, take_profit_pct=0.012),
        replace(baseline, take_profit_pct=0.012, exposure=1.25),
        replace(baseline, min_rvol96=0.75, take_profit_pct=0.012),
        replace(baseline, min_atr_pct96=0.009, take_profit_pct=0.012),
    ]
    while len(seeds) < population_size:
        seeds.append(random_config(rng))
    return unique_configs(seeds)[:population_size]


def next_generation(
    ranked: list[CleanConfig],
    rng: random.Random,
    population_size: int,
    elite_size: int,
) -> list[CleanConfig]:
    elites = ranked[:elite_size]
    parent_pool = ranked[: min(len(ranked), max(elite_size * 2, 50))]
    children = list(elites)
    while len(children) < population_size:
        left = rng.choice(parent_pool)
        right = rng.choice(parent_pool)
        child = crossover(left, right, rng)
        if rng.random() < 0.9:
            child = mutate(child, rng)
        children.append(child)
    while len(unique_configs(children)) < population_size:
        children.append(random_config(rng))
    return unique_configs(children)[:population_size]


def local_refinement(configs: list[CleanConfig]) -> list[CleanConfig]:
    refined: list[CleanConfig] = []
    for config in configs:
        values = asdict(config)
        for name, options in GENE_OPTIONS.items():
            for value in options:
                if value == values[name]:
                    continue
                candidate = replace(config, **{name: value})
                if valid_config(candidate):
                    refined.append(candidate)
    return unique_configs(refined)


def pareto_front(rows: pd.DataFrame) -> pd.DataFrame:
    feasible = rows.loc[rows["risk_feasible"]].copy()
    if feasible.empty:
        feasible = rows.loc[
            rows["max_drawdown_pct"].ge(-25.0)
            & rows["win_rate_pct"].ge(68.0)
            & rows["trades"].ge(100)
        ].copy()
    feasible = feasible.sort_values("annual_return_pct", ascending=False)
    metrics = [
        "annual_return_pct",
        "max_drawdown_pct",
        "win_rate_pct",
        "profit_factor",
        "last90_annual_return_pct",
    ]
    values = feasible[metrics].to_numpy("float64")
    keep = np.ones(len(feasible), dtype=bool)
    for index in range(len(feasible)):
        if not keep[index]:
            continue
        dominates = np.all(values >= values[index], axis=1) & np.any(
            values > values[index], axis=1
        )
        dominates[index] = False
        if dominates.any():
            keep[index] = False
    return feasible.loc[keep].sort_values("score", ascending=False).reset_index(drop=True)


def row_table(rows: pd.DataFrame, limit: int = 12) -> list[str]:
    lines = [
        "| 名称 | 年化 | 回撤 | 胜率 | 笔/日 | PF | 后半段年化 | Last90 年化 | 正收益季度 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows.head(limit).to_dict(orient="records"):
        lines.append(
            f"| `{row['name']}` | `{row['annual_return_pct']:.2f}%` | "
            f"`{row['max_drawdown_pct']:.2f}%` | `{row['win_rate_pct']:.2f}%` | "
            f"`{row['trades_per_day']:.3f}` | `{row['profit_factor']:.3f}` | "
            f"`{row['second_half_annual_return_pct']:.2f}%` | "
            f"`{row['last90_annual_return_pct']:.2f}%` | "
            f"`{int(row['positive_quarters'])}/4` |"
        )
    return lines


def parameter_table(row: pd.Series) -> list[str]:
    labels = {
        "rsi_window": "RSI window",
        "rsi_low": "RSI long cross",
        "rsi_high": "RSI short cross",
        "min_atr_pct96": "ATR96 lower",
        "min_rvol96": "RVOL96 lower",
        "h1_confirm": "1h direction confirm",
        "rsi14_band": "directional RSI14 band",
        "take_profit_pct": "take profit",
        "stop_pct": "stop",
        "max_hold_bars": "max hold bars",
        "exposure": "exposure",
    }
    lines = ["| 参数 | 值 |", "| --- | ---: |"]
    for name in GENE_NAMES:
        lines.append(f"| `{labels[name]}` | `{row[name]}` |")
    lines.extend(
        [
            f"| `MACD periods` | `{FIXED_MACD_PERIODS}` |",
            f"| `ATR window` | `{FIXED_ATR_WINDOW}` |",
            f"| `max ATR guardrail` | `{MAX_ATR_PCT_GUARDRAIL}` |",
        ]
    )
    return lines


def render_markdown(
    quality: dict[str, Any],
    args: argparse.Namespace,
    ranking: pd.DataFrame,
    pareto: pd.DataFrame,
    baseline: pd.Series,
) -> str:
    feasible = ranking.loc[ranking["risk_feasible"]]
    lead = feasible.iloc[0] if not feasible.empty else ranking.iloc[0]
    high_return = (
        feasible.sort_values("annual_return_pct", ascending=False).iloc[0]
        if not feasible.empty
        else ranking.sort_values("annual_return_pct", ascending=False).iloc[0]
    )
    high_win_pool = ranking.loc[
        ranking["annual_return_pct"].ge(50.0)
        & ranking["max_drawdown_pct"].ge(-20.0)
        & ranking["trades_per_day"].ge(0.3)
    ]
    high_win = (
        high_win_pool.sort_values(["win_rate_pct", "annual_return_pct"], ascending=False).iloc[0]
        if not high_win_pool.empty
        else lead
    )
    low_dd_pool = ranking.loc[
        ranking["annual_return_pct"].ge(50.0)
        & ranking["win_rate_pct"].ge(70.0)
        & ranking["trades_per_day"].ge(0.3)
    ]
    low_dd = (
        low_dd_pool.sort_values(["max_drawdown_pct", "annual_return_pct"], ascending=False).iloc[0]
        if not low_dd_pool.empty
        else lead
    )
    balanced_improvements = feasible.loc[
        feasible["annual_return_pct"].gt(float(baseline["annual_return_pct"]))
        & feasible["max_drawdown_pct"].ge(float(baseline["max_drawdown_pct"]))
        & feasible["win_rate_pct"].ge(float(baseline["win_rate_pct"]))
    ]

    lines = [
        f"# HYPE-15M-MII 干净参数演化 {RUN_DATE}",
        "",
        f"Family：`{FAMILY}`（alias：`HYPE-15M-MII`）",
        "",
        "## 结论",
        "",
        "本轮先根据 V1 全参数消融收缩配置，再对仍有信息量的参数做确定性多目标演化。搜索同时惩罚高回撤、低胜率、低交易支持、后半段或 Last90 亏损，并使用 purge 后的季度切片降低边界污染。",
        "",
        f"- 唯一候选数：`{len(ranking)}`；risk-feasible：`{len(feasible)}`；Pareto：`{len(pareto)}`。",
        f"- 原始 `>=2000%` 年化目标通过：`{int(ranking['strict_original_target'].sum())}/{len(ranking)}`。",
        f"- 同时超过 clean baseline 年化、回撤和胜率：`{len(balanced_improvements)}`。",
        "- 所有结果仍是同一历史样本上的二次优化，不是未见过的 forward OOS，因此不得直接 promotion。",
        "",
        "## 参数清理",
        "",
        "### 删除出配置的 dormant 字段",
        "",
        "`min_adx14=0`、`min_h4_dir_spread=-99`、`min_dir_ret16/48/96=-99`、`max_atr_ratio96_672=99`、`min_previous_signal_age=0`、`max_churn192=999`、`cooldown_bars=0` 等字段在 V1 中等价于关闭，干净配置不再序列化它们。",
        "",
        "### 冻结而不继续搜索",
        "",
        "- `MACD(12,26,9)`：替代周期在消融中显著恶化，固定为 V1 周期。",
        "- `ATR96`：替代窗口均未改善收益/回撤/近期稳定性，固定为 `96`。",
        "- `max_atr_pct96=2.8%`：样本内放宽没有改变交易，但它是未来极端波动 guardrail，不因 dormant 就删除。",
        "- `side=both`：作为策略行为固定，不再当作优化旋钮。",
        "- 替代 signal family、trailing exit、ADX/H4/ret48/cooldown 等探针没有形成更好的 V1 邻域，本轮不带入。",
        "",
        "### 继续演化",
        "",
        "RSI 周期与阈值、ATR96 下限、RVOL96、可选 1h 方向确认、可选 directional RSI14 band、TP、SL、最长持仓，以及独立的 exposure 风险层。",
        "",
        "## 数据与搜索",
        "",
        f"- 数据：`{quality['first_ts']}` 到 `{quality['last_ts']}`，`{quality['rows']}` 根闭合 K；data-quality gate `{quality['quality_gate_pass']}`。",
        f"- 种群 `{args.population}`，代数 `{args.generations}`，elite `{args.elite}`，seed `{args.seed}`。",
        (
            f"- 固定成本：每次成交手续费 `{COMMISSION_PER_SIDE:.4%}`，"
            f"每次成交滑点 `{SLIPPAGE_PER_SIDE:.4%}`，"
            f"round-trip `{ROUND_TRIP_COST:.4%}`；资金费未计入。"
        ),
        "- 执行：V1 修正版 next-open、open-gap、timeout-open 和单仓时序。",
        "",
        "## Clean Baseline",
        "",
        *row_table(pd.DataFrame([baseline]), limit=1),
        "",
        "## 演化领先版本",
        "",
        *row_table(pd.DataFrame([lead]), limit=1),
        "",
        *parameter_table(lead),
        "",
        "## 多目标代表",
        "",
        "### Risk-feasible 年化最高",
        "",
        *row_table(pd.DataFrame([high_return]), limit=1),
        "",
        "### 高胜率代表",
        "",
        *row_table(pd.DataFrame([high_win]), limit=1),
        "",
        "### 低回撤代表",
        "",
        *row_table(pd.DataFrame([low_dd]), limit=1),
        "",
        "## Pareto Top",
        "",
        *row_table(pareto, limit=15),
        "",
        "## 状态判断",
        "",
        "- 本轮可以产生更干净、更平衡的诊断版本，但不能据此声称已有可实盘策略。",
        "- 数据截止早于审计日，且所有可用历史都已参与过 V1 搜索；没有真正 untouched forward holdout。",
        "- 没有 tick/盘口级 stop-market、资金费、真实滑点、runner、重启恢复、订单对账和 kill switch。",
        "- 任何领先版本都必须先做局部消融、参数扰动和新增 forward 数据复核，之后才能讨论版本提升。",
        "",
        "## 产物",
        "",
        f"- 脚本：`{SCRIPT_PATH}`",
        f"- JSON：`{SUMMARY_JSON_PATH}`",
        f"- 全排名：`{RANKING_CSV_PATH}`",
        f"- Pareto：`{PARETO_CSV_PATH}`",
        f"- 时间切片：`{SLICES_CSV_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)


def main() -> None:
    args = parse_args()
    if args.population < 50 or args.generations < 1:
        raise ValueError("population must be >= 50 and generations must be >= 1")
    args.elite = min(max(args.elite, 10), args.population // 2)
    rng = random.Random(args.seed)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    frame, metadata, quality = v1.load_data_lake()
    features = add_rsi_features(add_features(frame, []))
    context = EvalContext(
        features=features,
        market=build_market_arrays(features),
        start_ts=pd.Timestamp(features["ts"].min()),
        end_ts=pd.Timestamp(features["ts"].max()) + pd.Timedelta(minutes=15),
        signal_cache={},
        trade_cache=OrderedDict(),
    )
    v1.engine.simulate_trades = v1.simulate_trades_live
    v1.engine.selected_trades = v1.selected_trades_live
    v1.search_engine.selected_trades = v1.selected_trades_live

    evaluation_cache: dict[CleanConfig, dict[str, Any]] = {}
    slice_cache: dict[CleanConfig, list[dict[str, Any]]] = {}
    population = seed_population(rng, args.population)
    for generation in range(1, args.generations + 1):
        evaluate_population(context, population, evaluation_cache, slice_cache)
        ranked = sorted(
            population,
            key=lambda config: float(evaluation_cache[config]["score"]),
            reverse=True,
        )
        best = evaluation_cache[ranked[0]]
        feasible_count = sum(evaluation_cache[config]["risk_feasible"] for config in population)
        print(
            f"generation {generation}/{args.generations} unique={len(evaluation_cache)} "
            f"feasible={feasible_count} score={best['score']:.3f} "
            f"ann={best['annual_return_pct']:.2f}% dd={best['max_drawdown_pct']:.2f}% "
            f"win={best['win_rate_pct']:.2f}% last90={best['last90_annual_return_pct']:.2f}%",
            flush=True,
        )
        population = next_generation(
            ranked,
            rng,
            args.population,
            args.elite,
        )

    evaluate_population(context, population, evaluation_cache, slice_cache)
    preliminary = sorted(
        evaluation_cache,
        key=lambda config: float(evaluation_cache[config]["score"]),
        reverse=True,
    )
    refinement = local_refinement(preliminary[:40])
    evaluate_population(context, refinement, evaluation_cache, slice_cache)
    print(
        f"local refinement candidates={len(refinement)} total_unique={len(evaluation_cache)}",
        flush=True,
    )

    ranking = pd.DataFrame(evaluation_cache.values()).sort_values(
        ["risk_feasible", "score", "annual_return_pct"],
        ascending=False,
    ).reset_index(drop=True)
    baseline = ranking.loc[ranking["name"].eq(CleanConfig().name)].iloc[0]
    ranking["beats_baseline_return"] = ranking["annual_return_pct"].gt(
        baseline["annual_return_pct"]
    )
    ranking["beats_baseline_drawdown"] = ranking["max_drawdown_pct"].ge(
        baseline["max_drawdown_pct"]
    )
    ranking["beats_baseline_win"] = ranking["win_rate_pct"].ge(
        baseline["win_rate_pct"]
    )
    ranking["triple_improvement"] = (
        ranking["beats_baseline_return"]
        & ranking["beats_baseline_drawdown"]
        & ranking["beats_baseline_win"]
    )
    pareto = pareto_front(ranking)

    top_names = set(ranking.head(100)["name"]) | set(pareto["name"])
    selected_slices = [
        row
        for config, rows in slice_cache.items()
        if config.name in top_names
        for row in rows
    ]
    slices = pd.DataFrame(selected_slices)
    ranking.to_csv(RANKING_CSV_PATH, index=False)
    pareto.to_csv(PARETO_CSV_PATH, index=False)
    slices.to_csv(SLICES_CSV_PATH, index=False)
    MARKDOWN_PATH.write_text(
        render_markdown(quality, args, ranking, pareto, baseline),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "family": FAMILY,
                "run_date": RUN_DATE,
                "status": "diagnostic_only_not_promoted",
                "metadata": metadata,
                "data_quality": quality,
                "search": vars(args),
                "fixed_parameters": {
                    "macd_periods": FIXED_MACD_PERIODS,
                    "atr_window": FIXED_ATR_WINDOW,
                    "max_atr_pct_guardrail": MAX_ATR_PCT_GUARDRAIL,
                    "side": "both",
                },
                "gene_options": GENE_OPTIONS,
                "evaluated": len(ranking),
                "risk_feasible": int(ranking["risk_feasible"].sum()),
                "strict_original_target": int(ranking["strict_original_target"].sum()),
                "triple_improvement": int(ranking["triple_improvement"].sum()),
                "baseline": baseline.to_dict(),
                "top_ranking": ranking.head(100).to_dict(orient="records"),
                "pareto": pareto.to_dict(orient="records"),
                "outputs": {
                    "markdown": str(MARKDOWN_PATH),
                    "ranking_csv": str(RANKING_CSV_PATH),
                    "pareto_csv": str(PARETO_CSV_PATH),
                    "slices_csv": str(SLICES_CSV_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )
    print(f"wrote {MARKDOWN_PATH}")
    print(
        ranking.head(15)[
            [
                "name",
                "annual_return_pct",
                "max_drawdown_pct",
                "win_rate_pct",
                "trades_per_day",
                "profit_factor",
                "second_half_annual_return_pct",
                "last90_annual_return_pct",
                "risk_feasible",
                "score",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
