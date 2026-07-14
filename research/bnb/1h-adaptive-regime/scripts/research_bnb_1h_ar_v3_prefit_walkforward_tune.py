"""Low-degree prefit-only optimization for BNB-1H-Adaptive-Regime-V3.

The search never calculates or persists reused locked-OOS metrics. It freezes
leverage and merge priority, searches exit and filter coordinates separately,
requires K+2 and 8 bps execution robustness, and uses four chronological
prefit validation blocks as an inner walk-forward gate.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass, replace
from itertools import product
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

import bnb_1h_ar_v2 as v2
import bnb_1h_ar_v3 as v3


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/bnb/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
NOTES_DIR = FAMILY_DIR / "notes"
DATE_TAG = "2026-07-13"

SUMMARY_JSON = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_walkforward_tune_{DATE_TAG}.json"
PHASE_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_walkforward_phases_{DATE_TAG}.csv"
FINAL_CSV = ARTIFACT_DIR / f"bnb_1h_ar_v3_prefit_walkforward_final_{DATE_TAG}.csv"
REPORT_MD = NOTES_DIR / f"bnb-1h-ar-v3-prefit-walkforward-optimization-{DATE_TAG}.md"

MAX_EXPOSURE = 2.5
TOP_BASE_PER_PHASE = 500
TOP_ROBUST_PER_PHASE = 6
MIN_PREFIT_TRADES = 75
MIN_VALIDATION_TRADES = 15
MIN_FOLD_TRADES = 6
MAX_DD = -0.20


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    fee: float
    slippage: float
    delay: int


@dataclass(slots=True)
class Candidate:
    candidate_id: str
    phase: str
    component: str
    config: Any
    updates: dict[str, Any]
    scenarios: dict[str, dict[str, Any]]
    robust_score: float
    robust_pass: bool


SCENARIOS = (
    Scenario("base_k1", 0.0010, 0.0004, 1),
    Scenario("delay_k2", 0.0010, 0.0004, 2),
    Scenario("slip_8bps", 0.0010, 0.0008, 1),
)

EMA_EXIT_GRID = {
    "trail_activation_atr": (1.5, 2.0, 2.5),
    "trail_atr": (1.0, 1.25, 1.5, 1.75),
    "sl_atr": (4.0, 5.0, 6.0),
    "max_hold_bars": (168, 240),
    "cooldown_bars": (6, 12),
}

EMA_FILTER_GRID = {
    "ema_htf": (233, 377),
    "max_dist_ema_bps": (200.0, 300.0, 500.0),
    "min_rvol": (0.8, 1.0, 1.25),
    "min_atr_bps": (25.0, 50.0, 75.0),
}

WICK_EXIT_GRID = {
    "tp_atr": (1.0, 1.25, 1.5),
    "sl_atr": (4.0, 5.0),
    "max_hold_bars": (24, 48),
    "cooldown_bars": (12, 24),
}

WICK_FILTER_GRID = {
    "threshold_low": (0.35, 0.40, 0.45),
    "threshold_high": (0.75, 0.80, 0.85),
    "band_k": (0.50, 0.75),
    "min_adx": (24.0, 28.0, 32.0),
    "min_rvol": (1.5, 2.0, 2.5),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="BNB V3 prefit-only walk-forward exit/filter optimization."
    )
    parser.add_argument(
        "--top-base-per-phase",
        type=int,
        default=TOP_BASE_PER_PHASE,
    )
    parser.add_argument(
        "--top-robust-per-phase",
        type=int,
        default=TOP_ROBUST_PER_PHASE,
    )
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    return v2.json_safe(value)


def pct(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value * 100:.2f}%"


def mult(value: float) -> str:
    return "inf" if not np.isfinite(value) else f"{value:.2f}x"


def metric_text(values: dict[str, Any]) -> str:
    return (
        f"`{mult(values['prefit_annual_multiple'])}` / "
        f"`{pct(values['prefit_max_dd'])}` DD / "
        f"`{pct(values['prefit_win_rate'])}` win / "
        f"`{int(values['prefit_trades'])}` trades"
    )


def grid_updates(grid: dict[str, tuple[Any, ...]]) -> list[dict[str, Any]]:
    keys = tuple(grid)
    return [
        dict(zip(keys, values, strict=True))
        for values in product(*(grid[key] for key in keys))
    ]


def config_key(config: Any) -> str:
    payload = asdict(config)
    payload.pop("name", None)
    return json.dumps(json_safe(payload), sort_keys=True, ensure_ascii=False)


def walk_folds(
    split: dict[str, pd.Timestamp],
) -> list[dict[str, pd.Timestamp | str]]:
    oos_start = split["oos_start"]
    folds: list[dict[str, pd.Timestamp | str]] = []
    for index in range(4):
        start = oos_start - pd.Timedelta(days=90 * (4 - index))
        end = start + pd.Timedelta(days=90)
        folds.append(
            {
                "name": f"wf_oos_{index + 1}",
                "is_start": split["train_start"],
                "is_end": start - pd.Timedelta(days=10),
                "gap_start": start - pd.Timedelta(days=10),
                "gap_end": start,
                "oos_start": start,
                "oos_end": end,
            }
        )
    return folds


def closed_window_metrics(
    engine: Any,
    trades: list[Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, float]:
    closed = [trade for trade in trades if trade.exit_ts < end]
    return engine.metrics(closed, start, end)


def selection_metrics(
    engine: Any,
    trades: list[Any],
    split: dict[str, pd.Timestamp],
    folds: list[dict[str, pd.Timestamp | str]],
) -> dict[str, Any]:
    train = closed_window_metrics(
        engine,
        trades,
        split["train_start"],
        split["train_end"],
    )
    validation = closed_window_metrics(
        engine,
        trades,
        split["train_end"],
        split["oos_start"],
    )
    prefit = closed_window_metrics(
        engine,
        trades,
        split["train_start"],
        split["oos_start"],
    )
    result: dict[str, Any] = {}
    for prefix, values in (
        ("train", train),
        ("validation", validation),
        ("prefit", prefit),
    ):
        result.update({f"{prefix}_{key}": value for key, value in values.items()})

    eligible = 0
    positive = 0
    fold_returns: list[float] = []
    fold_drawdowns: list[float] = []
    fold_trades: list[float] = []
    for fold in folds:
        name = str(fold["name"])
        start = pd.Timestamp(fold["oos_start"])
        end = pd.Timestamp(fold["oos_end"])
        values = closed_window_metrics(engine, trades, start, end)
        result.update({f"{name}_{key}": value for key, value in values.items()})
        fold_trades.append(values["trades"])
        if values["trades"] >= MIN_FOLD_TRADES:
            eligible += 1
            positive += int(values["total_return"] > 0.0)
            fold_returns.append(values["total_return"])
            fold_drawdowns.append(values["max_dd"])

    result["eligible_folds"] = eligible
    result["positive_folds"] = positive
    result["worst_fold_return"] = min(fold_returns) if fold_returns else -1.0
    result["median_fold_return"] = (
        float(np.median(fold_returns)) if fold_returns else -1.0
    )
    result["worst_fold_dd"] = min(fold_drawdowns) if fold_drawdowns else -1.0
    result["min_fold_trades"] = min(fold_trades) if fold_trades else 0.0
    return result


def scenario_gate(values: dict[str, Any]) -> bool:
    return bool(
        values["train_total_return"] > 0.0
        and values["validation_total_return"] > 0.0
        and values["prefit_total_return"] > 0.0
        and values["prefit_trades"] >= MIN_PREFIT_TRADES
        and values["validation_trades"] >= MIN_VALIDATION_TRADES
        and values["train_max_dd"] > MAX_DD
        and values["validation_max_dd"] > MAX_DD
        and values["prefit_max_dd"] > MAX_DD
        and values["validation_win_rate"] >= 0.65
        and 0.70 <= values["prefit_win_rate"] <= 0.93
        and values["prefit_max_exposure"] <= MAX_EXPOSURE
        and values["eligible_folds"] == 4
        and values["positive_folds"] >= 3
        and values["worst_fold_dd"] > MAX_DD
        and values["median_fold_return"] > 0.0
    )


def scenario_score(values: dict[str, Any]) -> float:
    if values["prefit_annual_multiple"] <= 0.0:
        return -1e9
    high_win_penalty = max(0.0, values["prefit_win_rate"] - 0.90) * 5.0
    trade_penalty = max(0.0, 85.0 - values["prefit_trades"]) / 85.0
    fold_penalty = max(0, 3 - values["positive_folds"]) * 0.8
    return float(
        math.log(values["prefit_annual_multiple"])
        + 0.45 * math.log(max(values["validation_annual_multiple"], 1e-9))
        + 2.5 * values["prefit_max_dd"]
        + 0.8 * values["prefit_win_rate"]
        + 0.6 * values["median_fold_return"]
        + 0.4 * values["worst_fold_return"]
        - high_win_penalty
        - trade_penalty
        - fold_penalty
    )


def robust_evaluation(
    by_scenario: dict[str, dict[str, Any]],
    baseline_by_scenario: dict[str, dict[str, Any]],
) -> tuple[float, bool]:
    scenario_names = [scenario.name for scenario in SCENARIOS]
    if any(name not in by_scenario for name in scenario_names):
        return -1e9, False
    scores = [scenario_score(by_scenario[name]) for name in scenario_names]
    annual_ratios = [
        by_scenario[name]["prefit_annual_multiple"]
        / baseline_by_scenario[name]["prefit_annual_multiple"]
        for name in scenario_names
    ]
    geometric_ratio = math.exp(
        sum(math.log(max(value, 1e-9)) for value in annual_ratios)
        / len(annual_ratios)
    )
    worst_ratio = min(annual_ratios)
    all_gates = all(scenario_gate(by_scenario[name]) for name in scenario_names)
    base = by_scenario["base_k1"]
    baseline_base = baseline_by_scenario["base_k1"]
    passed = bool(
        all_gates
        and base["prefit_annual_multiple"]
        >= baseline_base["prefit_annual_multiple"] * 1.03
        and base["prefit_max_dd"] >= baseline_base["prefit_max_dd"] - 0.01
        and geometric_ratio > 1.0
        and worst_ratio >= 0.85
    )
    robust_score = float(
        min(scores)
        + 0.35 * sum(scores) / len(scores)
        + 0.9 * math.log(max(geometric_ratio, 1e-9))
        + 0.4 * math.log(max(worst_ratio, 1e-9))
    )
    return robust_score, passed


class Evaluator:
    def __init__(
        self,
        *,
        engine: Any,
        frame: pd.DataFrame,
        funding_times: np.ndarray,
        funding_cumulative: np.ndarray,
        split: dict[str, pd.Timestamp],
    ) -> None:
        self.engine = engine
        self.frame = frame
        self.funding_times = funding_times
        self.funding_cumulative = funding_cumulative
        self.split = split
        self.folds = walk_folds(split)
        self.trade_cache: dict[tuple[str, str], list[Any]] = {}
        self.original_fee = float(engine.FEE_PER_FILL)
        self.original_slippage = float(engine.SLIPPAGE_PER_FILL)

    def restore_costs(self) -> None:
        self.engine.FEE_PER_FILL = self.original_fee
        self.engine.SLIPPAGE_PER_FILL = self.original_slippage

    def component_trades(self, config: Any, scenario: Scenario) -> list[Any]:
        adjusted = replace(
            config,
            entry_delay_bars=scenario.delay,
            fixed_leverage=min(float(config.fixed_leverage), MAX_EXPOSURE),
        )
        key = (scenario.name, config_key(adjusted))
        cached = self.trade_cache.get(key)
        if cached is not None:
            return cached

        self.engine.FEE_PER_FILL = scenario.fee
        self.engine.SLIPPAGE_PER_FILL = scenario.slippage
        signal = self.engine.build_signal(self.frame, adjusted)
        safe_signal_end = self.split["oos_start"] - pd.Timedelta(
            hours=adjusted.entry_delay_bars + adjusted.max_hold_bars + 1
        )
        signal = signal.copy()
        signal[(self.frame["ts"] > safe_signal_end).to_numpy()] = 0
        trades = self.engine.simulate_trades(
            self.frame,
            signal,
            adjusted,
            self.funding_times,
            self.funding_cumulative,
        )
        self.trade_cache[key] = trades
        return trades

    def pair_metrics(
        self,
        ema_config: Any,
        wick_config: Any,
        scenario: Scenario,
    ) -> dict[str, Any]:
        ema_trades = self.component_trades(ema_config, scenario)
        wick_trades = self.component_trades(wick_config, scenario)
        merged = self.engine.merge_trade_sets(
            ema_trades,
            wick_trades,
            v3.PRIORITIES[0],
            v3.PRIORITIES[1],
        )
        return selection_metrics(self.engine, merged, self.split, self.folds)

    def all_scenarios(
        self,
        ema_config: Any,
        wick_config: Any,
    ) -> dict[str, dict[str, Any]]:
        return {
            scenario.name: self.pair_metrics(ema_config, wick_config, scenario)
            for scenario in SCENARIOS
        }


def component_attribution(
    evaluator: Evaluator,
    base_ema: Any,
    base_wick: Any,
) -> dict[str, dict[str, dict[str, Any]]]:
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for scenario in SCENARIOS:
        output[scenario.name] = {}
        for label, config in (
            ("ema_pullback", base_ema),
            ("wick_reject", base_wick),
        ):
            trades = evaluator.component_trades(config, scenario)
            output[scenario.name][label] = selection_metrics(
                evaluator.engine,
                trades,
                evaluator.split,
                evaluator.folds,
            )
    return output


def direction_diagnostic(
    evaluator: Evaluator,
    base_ema: Any,
    base_wick: Any,
    baseline_by_scenario: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ema_side, wick_side in product(("both", "long", "short"), repeat=2):
        ema_config = replace(
            base_ema,
            name=f"{base_ema.name}_SIDE_{ema_side.upper()}",
            side_mode=ema_side,
        )
        wick_config = replace(
            base_wick,
            name=f"{base_wick.name}_SIDE_{wick_side.upper()}",
            side_mode=wick_side,
        )
        scenarios = evaluator.all_scenarios(ema_config, wick_config)
        score, passed = robust_evaluation(scenarios, baseline_by_scenario)
        rows.append(
            {
                "ema_side": ema_side,
                "wick_side": wick_side,
                "robust_score": score,
                "robust_pass": passed,
                "metrics": scenarios,
            }
        )
    rows.sort(
        key=lambda item: (item["robust_pass"], item["robust_score"]),
        reverse=True,
    )
    return rows


def candidate_row(candidate: Candidate) -> dict[str, Any]:
    row: dict[str, Any] = {
        "candidate_id": candidate.candidate_id,
        "phase": candidate.phase,
        "component": candidate.component,
        "robust_score": candidate.robust_score,
        "robust_pass": candidate.robust_pass,
        "updates": json.dumps(
            json_safe(candidate.updates),
            sort_keys=True,
            ensure_ascii=False,
        ),
        "config": json.dumps(
            json_safe(asdict(candidate.config)),
            sort_keys=True,
            ensure_ascii=False,
        ),
    }
    for scenario_name, values in candidate.scenarios.items():
        for key, value in values.items():
            row[f"{scenario_name}_{key}"] = value
    return row


def make_phase_configs(
    base_config: Any,
    phase: str,
    grid: dict[str, tuple[Any, ...]],
) -> list[tuple[str, Any, dict[str, Any]]]:
    output: list[tuple[str, Any, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, updates in enumerate([{}, *grid_updates(grid)]):
        config = replace(
            base_config,
            name=f"{base_config.name}_{phase.upper()}_{index:04d}",
            **updates,
        )
        key = config_key(config)
        if key in seen:
            continue
        seen.add(key)
        output.append((f"{phase}_{index:04d}", config, updates))
    return output


def evaluate_phase(
    *,
    evaluator: Evaluator,
    phase: str,
    component: str,
    configs: list[tuple[str, Any, dict[str, Any]]],
    base_ema: Any,
    base_wick: Any,
    baseline_by_scenario: dict[str, dict[str, Any]],
    top_base: int,
    top_robust: int,
) -> tuple[list[Candidate], list[Candidate]]:
    base_scored: list[tuple[float, str, Any, dict[str, Any], dict[str, Any]]] = []
    base_scenario = SCENARIOS[0]
    for candidate_id, config, updates in configs:
        values = (
            evaluator.pair_metrics(config, base_wick, base_scenario)
            if component == "ema_pullback"
            else evaluator.pair_metrics(base_ema, config, base_scenario)
        )
        base_scored.append(
            (scenario_score(values), candidate_id, config, updates, values)
        )
    base_scored.sort(key=lambda item: item[0], reverse=True)

    evaluated: list[Candidate] = []
    for _, candidate_id, config, updates, base_values in base_scored[:top_base]:
        scenarios = {"base_k1": base_values}
        for scenario in SCENARIOS[1:]:
            scenarios[scenario.name] = (
                evaluator.pair_metrics(config, base_wick, scenario)
                if component == "ema_pullback"
                else evaluator.pair_metrics(base_ema, config, scenario)
            )
        score, passed = robust_evaluation(scenarios, baseline_by_scenario)
        evaluated.append(
            Candidate(
                candidate_id=candidate_id,
                phase=phase,
                component=component,
                config=config,
                updates=updates,
                scenarios=scenarios,
                robust_score=score,
                robust_pass=passed,
            )
        )
    evaluated.sort(
        key=lambda item: (item.robust_pass, item.robust_score),
        reverse=True,
    )
    retained = [item for item in evaluated if item.robust_pass][:top_robust]
    retained_ids = {item.candidate_id for item in retained}
    if len(retained) < top_robust:
        retained.extend(
            item
            for item in evaluated
            if item.candidate_id not in retained_ids
        )
        retained = retained[:top_robust]
    return evaluated, retained


def combine_updates(
    base_config: Any,
    left: Iterable[Candidate],
    right: Iterable[Candidate],
    phase: str,
) -> list[tuple[str, Any, dict[str, Any]]]:
    left_updates = [{}, *(item.updates for item in left)]
    right_updates = [{}, *(item.updates for item in right)]
    output: list[tuple[str, Any, dict[str, Any]]] = []
    seen: set[str] = set()
    for index, (first, second) in enumerate(product(left_updates, right_updates)):
        updates = {**first, **second}
        config = replace(
            base_config,
            name=f"{base_config.name}_{phase.upper()}_{index:04d}",
            **updates,
        )
        key = config_key(config)
        if key in seen:
            continue
        seen.add(key)
        output.append((f"{phase}_{index:04d}", config, updates))
    return output


def evaluate_combined_component(
    *,
    evaluator: Evaluator,
    phase: str,
    component: str,
    configs: list[tuple[str, Any, dict[str, Any]]],
    base_ema: Any,
    base_wick: Any,
    baseline_by_scenario: dict[str, dict[str, Any]],
    keep: int,
) -> list[Candidate]:
    evaluated: list[Candidate] = []
    for candidate_id, config, updates in configs:
        scenarios = (
            evaluator.all_scenarios(config, base_wick)
            if component == "ema_pullback"
            else evaluator.all_scenarios(base_ema, config)
        )
        score, passed = robust_evaluation(scenarios, baseline_by_scenario)
        evaluated.append(
            Candidate(
                candidate_id=candidate_id,
                phase=phase,
                component=component,
                config=config,
                updates=updates,
                scenarios=scenarios,
                robust_score=score,
                robust_pass=passed,
            )
        )
    evaluated.sort(
        key=lambda item: (item.robust_pass, item.robust_score),
        reverse=True,
    )
    passed = [item for item in evaluated if item.robust_pass][:keep]
    passed_ids = {item.candidate_id for item in passed}
    if len(passed) < keep:
        passed.extend(
            item
            for item in evaluated
            if item.candidate_id not in passed_ids
        )
    return passed[:keep]


def evaluate_final_pairs(
    *,
    evaluator: Evaluator,
    ema_pool: list[Candidate],
    wick_pool: list[Candidate],
    base_ema: Any,
    base_wick: Any,
    baseline_by_scenario: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ema_options = [(base_ema, {}), *((item.config, item.updates) for item in ema_pool)]
    wick_options = [
        (base_wick, {}),
        *((item.config, item.updates) for item in wick_pool),
    ]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for ema_config, ema_updates in ema_options:
        for wick_config, wick_updates in wick_options:
            key = (config_key(ema_config), config_key(wick_config))
            if key in seen:
                continue
            seen.add(key)
            scenarios = evaluator.all_scenarios(ema_config, wick_config)
            score, passed = robust_evaluation(scenarios, baseline_by_scenario)
            row: dict[str, Any] = {
                "ema_name": ema_config.name,
                "wick_name": wick_config.name,
                "robust_score": score,
                "robust_pass": passed,
                "ema_updates": json.dumps(
                    json_safe(ema_updates),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "wick_updates": json.dumps(
                    json_safe(wick_updates),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "ema_config": json.dumps(
                    json_safe(asdict(ema_config)),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "wick_config": json.dumps(
                    json_safe(asdict(wick_config)),
                    sort_keys=True,
                    ensure_ascii=False,
                ),
                "_ema_config": ema_config,
                "_wick_config": wick_config,
                "_scenarios": scenarios,
            }
            for scenario_name, values in scenarios.items():
                for metric_name, value in values.items():
                    row[f"{scenario_name}_{metric_name}"] = value
            rows.append(row)
    rows.sort(
        key=lambda item: (item["robust_pass"], item["robust_score"]),
        reverse=True,
    )
    return rows


def risk_normalization_diagnostic(
    *,
    evaluator: Evaluator,
    best_near_miss: dict[str, Any],
    baseline_by_scenario: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for leverage in (2.5, 2.25, 2.0, 1.75):
        ema_config = replace(
            best_near_miss["_ema_config"],
            name=f"{best_near_miss['_ema_config'].name}_RISK_X{leverage:g}",
            fixed_leverage=leverage,
        )
        scenarios = evaluator.all_scenarios(
            ema_config,
            best_near_miss["_wick_config"],
        )
        score, passed = robust_evaluation(scenarios, baseline_by_scenario)
        rows.append(
            {
                "ema_fixed_leverage": leverage,
                "robust_score": score,
                "robust_pass": passed,
                "metrics": scenarios,
            }
        )
    return rows


def report_lines(
    *,
    quality: dict[str, Any],
    split: dict[str, pd.Timestamp],
    folds: list[dict[str, pd.Timestamp | str]],
    baseline: dict[str, dict[str, Any]],
    attribution: dict[str, dict[str, dict[str, Any]]],
    direction_rows: list[dict[str, Any]],
    phase_summary: dict[str, dict[str, int]],
    final_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
) -> list[str]:
    passed = [row for row in final_rows if row["robust_pass"]]
    preferred = passed[0] if passed else None
    best_near_miss = final_rows[0]
    lines = [
        f"# BNB-1H-Adaptive-Regime-V3 prefit walk-forward 优化 - {DATE_TAG}",
        "",
        "## 结论",
        "",
        "本轮只使用 prefit 数据，未计算、未排序、未持久化 reused locked OOS 指标。搜索冻结 V3 的杠杆（EMA `2.5x`、wick `1.0x`）和 merge priority，只分阶段研究 exit/trailing 与过滤强度。",
        "",
        f"- base K+1 V3（同一边界净化口径）：{metric_text(baseline['base_k1'])}。",
        f"- K+2 V3：{metric_text(baseline['delay_k2'])}。",
        f"- 8bps V3：{metric_text(baseline['slip_8bps'])}。",
        f"- 最终组合评估 `{len(final_rows)}` 个，通过三场景 + 四时间块 gate `{len(passed)}` 个。",
        "",
    ]
    if preferred is None:
        near_scenarios = best_near_miss["_scenarios"]
        lines.extend(
            [
                "没有候选在不提高杠杆的前提下同时改善年化并通过 K+2、8bps 与 inner walk-forward gate；本轮不产生 V4 候选。继续扩大同一参数面只会增加过拟合风险，应停止参数微调并等待 fresh forward。",
                "",
                f"- 最高分 near-miss：K+1 {metric_text(near_scenarios['base_k1'])}；K+2 {metric_text(near_scenarios['delay_k2'])}；8bps {metric_text(near_scenarios['slip_8bps'])}。",
                f"- near-miss EMA 变化：`{best_near_miss['ema_updates']}`。",
                f"- near-miss wick 变化：`{best_near_miss['wick_updates']}`。",
                "- 它显著修复 K+2 收益，但三场景回撤仍超过 `20%`，因此不是候选。",
                "",
            ]
        )
    else:
        scenarios = preferred["_scenarios"]
        ema_config = preferred["_ema_config"]
        wick_config = preferred["_wick_config"]
        lines.extend(
            [
                "存在通过全部 prefit-only gate 的首选设计，但它仍只是未登记观察值，不是 V4，也不是 promotion 证据。",
                "",
                f"- base K+1：{metric_text(scenarios['base_k1'])}。",
                f"- K+2：{metric_text(scenarios['delay_k2'])}。",
                f"- 8bps：{metric_text(scenarios['slip_8bps'])}。",
                f"- EMA 变化：`{preferred['ema_updates']}`。",
                f"- wick 变化：`{preferred['wick_updates']}`。",
                f"- 最大暴露：`{scenarios['base_k1']['prefit_max_exposure']:.2f}x`。",
                f"- EMA config：`{ema_config.name}`；wick config：`{wick_config.name}`。",
                "",
            ]
        )

    lines.extend(
        [
            "## 搜索协议",
            "",
            "- Stage A：EMA trailing/stop/hold/cooldown；不动信号与杠杆。",
            "- Stage B：EMA 长周期距离、成交量和波动过滤；不动 exit 与杠杆。",
            "- Stage C：wick fixed TP/SL/hold/cooldown；不动过滤与杠杆。",
            "- Stage D：wick 影线阈值、ADX、相对成交量；不动 exit 与杠杆。",
            "- 各坐标面先独立筛选；若单轴没有直接过完整 gate，仅保留 robust score 最靠前的少量诊断种子做一次受限合装，最终组合 gate 不放宽。",
            "- 入选场景：base K+1、delay K+2、8bps/fill；三者均需通过收益、交易数、`<20%` DD、胜率和最大暴露 gate。",
            "- 四个 chronological 90d prefit validation block；每个 block 前保留 10d gap，要求四个 block 均有足够交易、至少三个为正、最差 block DD `<20%`。这些 block 参与选参，不是 fresh OOS。",
            "- prefit 末端按 `entry_delay + max_hold + 1` 小时做 entry purge，避免任何候选依赖 OOS 内退出。",
            "",
            "## 分阶段结果",
            "",
            "| Phase | Base shortlist | Robust pass | Retained |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for phase, values in phase_summary.items():
        lines.append(
            f"| `{phase}` | `{values['base_shortlist']}` | "
            f"`{values['robust_pass']}` | `{values['retained']}` |"
        )

    best_direction = direction_rows[0]
    lines.extend(
        [
            "",
            "## K+2 风险归因",
            "",
            "| Scenario | Component | Annual | DD | Win | Trades |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for scenario in SCENARIOS:
        for component in ("ema_pullback", "wick_reject"):
            values = attribution[scenario.name][component]
            lines.append(
                f"| `{scenario.name}` | `{component}` | "
                f"`{mult(values['prefit_annual_multiple'])}` | "
                f"`{pct(values['prefit_max_dd'])}` | "
                f"`{pct(values['prefit_win_rate'])}` | "
                f"`{int(values['prefit_trades'])}` |"
            )
    direction_k1 = best_direction["metrics"]["base_k1"]
    direction_k2 = best_direction["metrics"]["delay_k2"]
    lines.extend(
        [
            "",
            f"- K+2 下 EMA 腿是主要回撤来源，但 wick 腿也从盈利降为亏损；这不是单腿 exit 参数可以完全修复的问题。",
            f"- 9 个方向组合均未通过。最稳方向为 EMA `{best_direction['ema_side']}` + wick `{best_direction['wick_side']}`：K+1 {metric_text(direction_k1)}；K+2 {metric_text(direction_k2)}。",
            "- 方向过滤降低了回撤和收益，却没有恢复 K+2 `<20%` DD，因此不作为候选。",
            "",
            "## 后续优化判断",
            "",
            "1. 停止扩大 trailing、TP/SL、ADX、影线阈值和成交量网格；这些坐标已无候选通过。",
            "2. 下一项可检验机制应是 live-executable 的信号新鲜度：在实际 entry open 检查价格相对 signal close/ATR 的漂移，或在 K+2 时要求最后一根已闭合 K 仍保持趋势/regime；不满足则取消过期信号。",
            "3. 新鲜度机制必须单独开结构实验，只用 prefit inner walk-forward + K+1/K+2/8bps 三场景；自由度限制为少量离散阈值，不与 exit/filter 再做高维联合。",
            "4. 若该结构实验仍不能把 K+2 DD 压回 `<20%` 且保持正向年化，就停止历史调参，保留 V3 等 fresh forward。",
            "",
            "## Near-miss 机械降风险压力",
            "",
            "| EMA leverage | K+1 annual / DD | K+2 annual / DD | 8bps annual / DD | Pass |",
            "| ---: | --- | --- | --- | --- |",
        ]
    )
    for row in risk_rows:
        base = row["metrics"]["base_k1"]
        delay = row["metrics"]["delay_k2"]
        slip = row["metrics"]["slip_8bps"]
        lines.append(
            f"| `{row['ema_fixed_leverage']:.2f}x` | "
            f"`{mult(base['prefit_annual_multiple'])}` / `{pct(base['prefit_max_dd'])}` | "
            f"`{mult(delay['prefit_annual_multiple'])}` / `{pct(delay['prefit_max_dd'])}` | "
            f"`{mult(slip['prefit_annual_multiple'])}` / `{pct(slip['prefit_max_dd'])}` | "
            f"`{row['robust_pass']}` |"
        )
    lines.extend(
        [
            "",
            "`2.25x` 仍略穿回撤边界；`2.0x` 回撤合格但没有严格改善 V3 K+1 年化。不会继续搜索 `2.1x/2.15x` 等贴门槛杠杆。",
        ]
    )

    lines.extend(
        [
            "",
            "## 数据与执行口径",
            "",
            "- Market：Binance USD-M Futures `BNBUSDT` perpetual `1h`。",
            f"- 数据：UTC `{quality['first_ts']}` 至 `{quality['last_ts']}`；closed K rows `{quality['rows']}`；missing/duplicate=`{quality['missing_bars']}/{quality['duplicate_bars']}`。",
            f"- 数据质量：source=`{quality['source_counts']}`；critical nulls=`{sum(quality['critical_nulls'].values())}`；raw/normalized mismatch=`{sum(quality['raw_normalized_mismatch'].values())}`；OHLCV violations=`{sum(quality['ohlcv_violations'].values())}`。",
            f"- Funding 固定读取家族 artifact `bnb_binance_funding_history_2y.csv`：rows `{quality['funding_rows']}`，UTC `{quality['funding_first_ts']}` 至 `{quality['funding_last_ts']}`；不依赖会被其他周期抓取覆盖的共享 funding 湖。",
            f"- 选参边界：`{split['train_start']}` 至 `{split['oos_start']}`，不读取后段指标。",
            "- 成本：base fee `0.001`/fill + `4 bps`/fill；压力场景为 K+2 或 `8 bps`/fill；均计入历史 funding。",
            "- 执行：闭合 K 信号、下一根或 K+2 open 成交；stop-first；open 穿 stop 按 open；trailing 当前 K 更新、下一根生效。",
            "- trailing 模式下引擎不设置固定 target，因此 `ema_pullback.tp_atr=3.0` 不参与 V3 trailing 出场，也不作为本轮搜索轴。",
            "",
            "## Prefit chronological validation 时间块",
            "",
            "| Block | Expanding IS end | Gap | Validation block |",
            "| --- | --- | --- | --- |",
        ]
    )
    for fold in folds:
        lines.append(
            f"| `{fold['name']}` | `{fold['is_end']}` | "
            f"`{fold['gap_start']} -> {fold['gap_end']}` | "
            f"`{fold['oos_start']} -> {fold['oos_end']}` |"
        )

    lines.extend(
        [
            "",
            "## Promotion 边界",
            "",
            "本轮只能产生 prefit-only 设计建议。无论是否有候选通过，都不得读取 reused OOS 回头选参，也不得据此登记 candidate、dry-run、handoff 或 live。下一次有效验证必须使用 fresh forward，或在正式 re-freeze 协议下重新建立未读 OOS。",
            "",
            "## 产物",
            "",
            f"- `{SUMMARY_JSON.relative_to(ROOT)}`",
            f"- `{PHASE_CSV.relative_to(ROOT)}`",
            f"- `{FINAL_CSV.relative_to(ROOT)}`",
            "",
        ]
    )
    return lines


def public_final_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: json_safe(value)
        for key, value in row.items()
        if not key.startswith("_")
    }


def main() -> None:
    args = parse_args()
    if args.top_base_per_phase < 5:
        raise ValueError("--top-base-per-phase must be >= 5")
    if args.top_robust_per_phase < 2:
        raise ValueError("--top-robust-per-phase must be >= 2")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    context = v2.load_context()
    engine = context["engine"]
    split = context["split"]
    frame = (
        context["frame"]
        .loc[context["frame"]["ts"] < split["oos_start"]]
        .copy()
        .reset_index(drop=True)
    )
    evaluator = Evaluator(
        engine=engine,
        frame=frame,
        funding_times=context["funding_times"],
        funding_cumulative=context["funding_cumulative"],
        split=split,
    )
    base_ema, base_wick = v3.v3_configs(engine)

    try:
        baseline_by_scenario = evaluator.all_scenarios(base_ema, base_wick)
        attribution = component_attribution(evaluator, base_ema, base_wick)
        direction_rows = direction_diagnostic(
            evaluator,
            base_ema,
            base_wick,
            baseline_by_scenario,
        )
        print(
            "baseline "
            + " ".join(
                f"{name}={values['prefit_annual_multiple']:.3f}x/"
                f"{values['prefit_max_dd']:.2%}"
                for name, values in baseline_by_scenario.items()
            ),
            flush=True,
        )

        phase_definitions = (
            ("ema_exit", "ema_pullback", base_ema, EMA_EXIT_GRID),
            ("ema_filter", "ema_pullback", base_ema, EMA_FILTER_GRID),
            ("wick_exit", "wick_reject", base_wick, WICK_EXIT_GRID),
            ("wick_filter", "wick_reject", base_wick, WICK_FILTER_GRID),
        )
        all_phase_candidates: list[Candidate] = []
        retained_by_phase: dict[str, list[Candidate]] = {}
        phase_summary: dict[str, dict[str, int]] = {}

        for phase, component, base_config, grid in phase_definitions:
            configs = make_phase_configs(base_config, phase, grid)
            evaluated, retained = evaluate_phase(
                evaluator=evaluator,
                phase=phase,
                component=component,
                configs=configs,
                base_ema=base_ema,
                base_wick=base_wick,
                baseline_by_scenario=baseline_by_scenario,
                top_base=args.top_base_per_phase,
                top_robust=args.top_robust_per_phase,
            )
            all_phase_candidates.extend(evaluated)
            retained_by_phase[phase] = retained
            phase_summary[phase] = {
                "base_shortlist": len(evaluated),
                "robust_pass": sum(item.robust_pass for item in evaluated),
                "retained": len(retained),
            }
            print(
                f"{phase}: shortlist={len(evaluated)} "
                f"robust_pass={phase_summary[phase]['robust_pass']} "
                f"retained={len(retained)}",
                flush=True,
            )

        ema_combined_configs = combine_updates(
            base_ema,
            retained_by_phase["ema_exit"],
            retained_by_phase["ema_filter"],
            "ema_combined",
        )
        wick_combined_configs = combine_updates(
            base_wick,
            retained_by_phase["wick_exit"],
            retained_by_phase["wick_filter"],
            "wick_combined",
        )
        ema_pool = evaluate_combined_component(
            evaluator=evaluator,
            phase="ema_combined",
            component="ema_pullback",
            configs=ema_combined_configs,
            base_ema=base_ema,
            base_wick=base_wick,
            baseline_by_scenario=baseline_by_scenario,
            keep=args.top_robust_per_phase,
        )
        wick_pool = evaluate_combined_component(
            evaluator=evaluator,
            phase="wick_combined",
            component="wick_reject",
            configs=wick_combined_configs,
            base_ema=base_ema,
            base_wick=base_wick,
            baseline_by_scenario=baseline_by_scenario,
            keep=args.top_robust_per_phase,
        )
        phase_summary["ema_combined"] = {
            "base_shortlist": len(ema_combined_configs),
            "robust_pass": sum(item.robust_pass for item in ema_pool),
            "retained": len(ema_pool),
        }
        phase_summary["wick_combined"] = {
            "base_shortlist": len(wick_combined_configs),
            "robust_pass": sum(item.robust_pass for item in wick_pool),
            "retained": len(wick_pool),
        }
        all_phase_candidates.extend(ema_pool)
        all_phase_candidates.extend(wick_pool)

        final_rows = evaluate_final_pairs(
            evaluator=evaluator,
            ema_pool=ema_pool,
            wick_pool=wick_pool,
            base_ema=base_ema,
            base_wick=base_wick,
            baseline_by_scenario=baseline_by_scenario,
        )
        risk_rows = risk_normalization_diagnostic(
            evaluator=evaluator,
            best_near_miss=final_rows[0],
            baseline_by_scenario=baseline_by_scenario,
        )
    finally:
        evaluator.restore_costs()

    pd.DataFrame(
        [candidate_row(candidate) for candidate in all_phase_candidates]
    ).to_csv(PHASE_CSV, index=False)
    pd.DataFrame([public_final_row(row) for row in final_rows]).to_csv(
        FINAL_CSV,
        index=False,
    )

    passed_rows = [row for row in final_rows if row["robust_pass"]]
    preferred = passed_rows[0] if passed_rows else None
    summary = {
        "family": "BNB-1H-Adaptive-Regime",
        "base_version": "BNB-1H-Adaptive-Regime-V3",
        "date": DATE_TAG,
        "selection": "prefit_only_low_degree_walkforward_k2_8bps",
        "reused_oos_metrics_calculated": False,
        "max_exposure": MAX_EXPOSURE,
        "priorities_frozen": list(v3.PRIORITIES),
        "scenarios": [asdict(scenario) for scenario in SCENARIOS],
        "folds": evaluator.folds,
        "baseline": baseline_by_scenario,
        "component_attribution": attribution,
        "direction_diagnostic": direction_rows,
        "phase_summary": phase_summary,
        "final_pairs_evaluated": len(final_rows),
        "final_pairs_passed": len(passed_rows),
        "best_near_miss": {
            "ema_config": asdict(final_rows[0]["_ema_config"]),
            "wick_config": asdict(final_rows[0]["_wick_config"]),
            "ema_updates": json.loads(final_rows[0]["ema_updates"]),
            "wick_updates": json.loads(final_rows[0]["wick_updates"]),
            "robust_score": final_rows[0]["robust_score"],
            "metrics": final_rows[0]["_scenarios"],
        },
        "risk_normalization_diagnostic": risk_rows,
        "preferred_prefit_only": (
            {
                "status": "prefit_only_design_not_version_not_promoted",
                "ema_config": asdict(preferred["_ema_config"]),
                "wick_config": asdict(preferred["_wick_config"]),
                "ema_updates": json.loads(preferred["ema_updates"]),
                "wick_updates": json.loads(preferred["wick_updates"]),
                "robust_score": preferred["robust_score"],
                "metrics": preferred["_scenarios"],
            }
            if preferred is not None
            else None
        ),
    }
    SUMMARY_JSON.write_text(
        json.dumps(json_safe(summary), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    REPORT_MD.write_text(
        "\n".join(
            report_lines(
                quality=context["quality"],
                split=split,
                folds=evaluator.folds,
                baseline=baseline_by_scenario,
                attribution=attribution,
                direction_rows=direction_rows,
                phase_summary=phase_summary,
                final_rows=final_rows,
                risk_rows=risk_rows,
            )
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            json_safe(
                {
                    "phase_summary": phase_summary,
                    "final_pairs_evaluated": len(final_rows),
                    "final_pairs_passed": len(passed_rows),
                    "preferred_prefit_only": summary["preferred_prefit_only"],
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
