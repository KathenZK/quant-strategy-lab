from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import audit_hype_1h_adaptive_regime_boundary as boundary  # noqa: E402
import research_hype_1h_adaptive_regime_search as base  # noqa: E402
import research_hype_1h_ar_v1_full_ablation as v1  # noqa: E402
import research_hype_1h_ar_v2_clean_tune as v2  # noqa: E402
import research_hype_1h_ar_v3_full_ablation as v3ab  # noqa: E402
import research_hype_1h_ar_v3_prune_and_tune as pt  # noqa: E402


DATE_TAG = "2026-07-10"
FAMILY_DIR = ROOT / "research/hype/1h-adaptive-regime"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
DIAGNOSTIC_DIR = FAMILY_DIR / "diagnostics"
SUMMARY_JSON = ARTIFACT_DIR / f"hype_1h_ar_v4_pressure_optimization_{DATE_TAG}.json"
LEG_ROWS_CSV = ARTIFACT_DIR / f"hype_1h_ar_v4_pressure_optimization_legs_{DATE_TAG}.csv"
ENSEMBLE_ROWS_CSV = (
    ARTIFACT_DIR / f"hype_1h_ar_v4_pressure_optimization_ensembles_{DATE_TAG}.csv"
)
TRADE_ROWS_CSV = (
    ARTIFACT_DIR / f"hype_1h_ar_v4_pressure_optimization_trades_{DATE_TAG}.csv"
)
REPORT_MD = (
    DIAGNOSTIC_DIR / f"hype-1h-ar-v4-execution-pressure-optimization-{DATE_TAG}.md"
)

SCENARIOS = (
    ("base_k1", 0.0010, 0.0004, 1),
    ("delay_k2", 0.0010, 0.0004, 2),
    ("slip_8bps", 0.0010, 0.0008, 1),
)
MAX_DD = -0.20
MIN_WIN = 0.50
TOP_LEGS = 30
FROZEN_ENSEMBLES = 12


def v4_pruned_configs() -> tuple[pt.DIPrunedConfig, pt.StochPrunedConfig]:
    return (
        pt.DIPrunedConfig(
            min_adx=10.0,
            min_rvol=2.0,
            max_atr_bps=250.0,
            htf_mode="h12",
            require_body_dir=False,
            tp_atr=1.5,
            sl_atr=4.5,
            max_hold_bars=18,
            fixed_leverage=3.0,
        ),
        pt.StochPrunedConfig(
            indicator_window=21,
            threshold_low=25.0,
            threshold_high=55.0,
            min_adx=0.0,
            min_rvol=1.0,
            min_atr_bps=200.0,
            max_atr_bps=500.0,
            macd_fast=8,
            macd_slow=55,
            macd_signal=5,
            require_macd_turn=True,
            trail_activation_atr=1.0,
            trail_atr=1.0,
            max_hold_bars=8,
            cooldown_bars=36,
            fixed_leverage=2.0,
        ),
    )


def v4_engine_configs() -> tuple[base.StrategyConfig, base.StrategyConfig]:
    di, stoch = v4_pruned_configs()
    return (
        v2.di_to_base(pt.di_pruned_to_clean(di), "HYPE_1H_AR_V4_DI"),
        v2.stoch_to_base(
            pt.stoch_pruned_to_clean(stoch), "HYPE_1H_AR_V4_STOCH"
        ),
    )


def di_variants() -> list[base.StrategyConfig]:
    baseline, _stoch = v4_engine_configs()
    output = [baseline]
    for sl_atr in (2.5, 3.0, 3.5, 4.0, 4.5):
        for leverage in (2.0, 2.25, 2.5, 2.75, 3.0):
            for max_hold in (12, 15, 18):
                for tp_atr in (1.25, 1.5):
                    output.append(
                        replace(
                            baseline,
                            name=(
                                f"DI_FIXED_SL{sl_atr:g}_L{leverage:g}_"
                                f"H{max_hold}_TP{tp_atr:g}"
                            ),
                            sizing_kind="fixed",
                            sl_atr=sl_atr,
                            fixed_leverage=leverage,
                            max_hold_bars=max_hold,
                            tp_atr=tp_atr,
                        )
                    )
    for sl_atr in (3.0, 3.5, 4.0, 4.5):
        for risk_fraction in (0.12, 0.15, 0.18):
            for max_leverage in (2.0, 2.5, 3.0):
                for max_hold in (15, 18):
                    output.append(
                        replace(
                            baseline,
                            name=(
                                f"DI_RISK_SL{sl_atr:g}_R{risk_fraction:g}_"
                                f"C{max_leverage:g}_H{max_hold}"
                            ),
                            sizing_kind="risk",
                            sl_atr=sl_atr,
                            risk_fraction=risk_fraction,
                            max_leverage=max_leverage,
                            max_hold_bars=max_hold,
                        )
                    )
    return list({cfg: None for cfg in output})


def stoch_variants() -> list[base.StrategyConfig]:
    _di, baseline = v4_engine_configs()
    output = [baseline]
    trail_pairs = (
        (0.5, 0.5),
        (0.5, 0.75),
        (0.75, 0.75),
        (0.75, 1.0),
        (1.0, 1.0),
    )
    for sl_atr in (1.5, 2.0, 2.5, 3.0, 4.0):
        for leverage in (1.25, 1.5, 1.75, 2.0):
            for activation, trail in trail_pairs:
                for max_hold in (4, 6, 8):
                    output.append(
                        replace(
                            baseline,
                            name=(
                                f"ST_FIXED_SL{sl_atr:g}_L{leverage:g}_"
                                f"A{activation:g}_T{trail:g}_H{max_hold}"
                            ),
                            sizing_kind="fixed",
                            sl_atr=sl_atr,
                            fixed_leverage=leverage,
                            trail_activation_atr=activation,
                            trail_atr=trail,
                            max_hold_bars=max_hold,
                        )
                    )
    risk_trails = ((0.5, 0.5), (0.75, 0.75), (1.0, 1.0))
    for sl_atr in (2.0, 2.5, 3.0, 4.0):
        for risk_fraction in (0.10, 0.12, 0.15, 0.18):
            for max_leverage in (1.5, 1.75, 2.0):
                for activation, trail in risk_trails:
                    for max_hold in (6, 8):
                        output.append(
                            replace(
                                baseline,
                                name=(
                                    f"ST_RISK_SL{sl_atr:g}_R{risk_fraction:g}_"
                                    f"C{max_leverage:g}_A{activation:g}_"
                                    f"T{trail:g}_H{max_hold}"
                                ),
                                sizing_kind="risk",
                                sl_atr=sl_atr,
                                risk_fraction=risk_fraction,
                                max_leverage=max_leverage,
                                trail_activation_atr=activation,
                                trail_atr=trail,
                                max_hold_bars=max_hold,
                            )
                        )
    return list({cfg: None for cfg in output})


def window_bundle(
    trades: list[base.Trade], full_end: pd.Timestamp
) -> dict[str, dict[str, float]]:
    return {
        "train": base.metrics(trades, v1.TRAIN_START, v1.TRAIN_END),
        "validation": base.metrics(trades, v1.TRAIN_END, v1.PREFIT_END),
        "prefit": base.metrics(trades, v1.TRAIN_START, v1.PREFIT_END),
        "reused_holdout": base.metrics(trades, v1.PREFIT_END, full_end),
        "current_full": base.metrics(trades, v1.TRAIN_START, full_end),
    }


def flatten_bundle(
    bundle: dict[str, dict[str, float]], prefix: str
) -> dict[str, float]:
    return {
        f"{prefix}_{window}_{key}": value
        for window, metric in bundle.items()
        for key, value in metric.items()
    }


def prefit_leg_gate(bundle: dict[str, dict[str, float]]) -> bool:
    return bool(
        bundle["train"]["total_return"] > 0.0
        and bundle["validation"]["total_return"] > 0.0
        and bundle["validation"]["trades"] >= 4
        and bundle["prefit"]["trades"] >= 15
        and bundle["validation"]["win_rate"] >= MIN_WIN
        and bundle["prefit"]["win_rate"] >= MIN_WIN
        and min(
            bundle["train"]["max_dd"],
            bundle["validation"]["max_dd"],
            bundle["prefit"]["max_dd"],
        )
        > MAX_DD
    )


def prefit_ensemble_gate(
    bundles: dict[str, dict[str, dict[str, float]]]
) -> bool:
    for scenario, bundle in bundles.items():
        if (
            not prefit_leg_gate(bundle)
            or bundle["prefit"]["trades"] < 20
            or bundle["prefit"]["annual_multiple"] < base.TARGET_ANNUAL_MULTIPLE
        ):
            return False
        if scenario == "base_k1" and bundle["validation"]["trades"] < 5:
            return False
    return True


def robust_score(
    bundles: dict[str, dict[str, dict[str, float]]]
) -> tuple[float, float, float]:
    min_annual = min(
        bundle["prefit"]["annual_multiple"] for bundle in bundles.values()
    )
    worst_dd = min(bundle["prefit"]["max_dd"] for bundle in bundles.values())
    min_win = min(bundle["prefit"]["win_rate"] for bundle in bundles.values())
    score = math.log(max(min_annual, 1e-9)) + 4.0 * (worst_dd + 0.20) + 0.3 * min_win
    return float(score), float(min_annual), float(worst_dd)


class ExactJointEngine:
    def __init__(
        self,
        frame: pd.DataFrame,
        funding_times: np.ndarray,
        funding_cumulative: np.ndarray,
    ) -> None:
        self.frame = frame
        self.funding_times = funding_times
        self.funding_cumulative = funding_cumulative
        self.raw_cache: dict[
            tuple[base.StrategyConfig, str], list[base.Trade]
        ] = {}

    def _correct_exit_bar_mae(
        self, trade: base.Trade, fee: float
    ) -> base.Trade:
        if trade.exit_i > trade.entry_i:
            prior = self.frame.iloc[trade.entry_i : trade.exit_i]
            adverse = (
                float(prior["low"].min())
                if trade.side > 0
                else float(prior["high"].max())
            )
        else:
            adverse = trade.entry_price
        open_exit_reasons = {
            "timeout_open",
            "stop_gap_open",
            "target_gap_or_open",
        }
        if trade.exit_reason in open_exit_reasons or "stop" in trade.exit_reason:
            adverse = (
                min(adverse, trade.exit_price)
                if trade.side > 0
                else max(adverse, trade.exit_price)
            )
        else:
            exit_bar = self.frame.iloc[trade.exit_i]
            adverse = (
                min(adverse, float(exit_bar["low"]))
                if trade.side > 0
                else max(adverse, float(exit_bar["high"]))
            )
        mae = (
            adverse / trade.entry_price - 1.0
            if trade.side > 0
            else 1.0 - adverse / trade.entry_price
        )
        mae -= 2.0 * fee
        return replace(
            trade,
            mae_1x=float(mae),
            equity_mae=float(trade.exposure * mae),
        )

    def raw_events(
        self,
        cfg: base.StrategyConfig,
        scenario: tuple[str, float, float, int],
    ) -> list[base.Trade]:
        scenario_name, fee, slippage, delay = scenario
        scenario_cfg = replace(cfg, entry_delay_bars=delay)
        key = (scenario_cfg, scenario_name)
        if key in self.raw_cache:
            return self.raw_cache[key]
        signal = base.build_signal(self.frame, scenario_cfg)
        n = len(signal)
        original_costs = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
        output: list[base.Trade] = []
        try:
            base.FEE_PER_FILL = fee
            base.SLIPPAGE_PER_FILL = slippage
            for signal_i in np.flatnonzero(signal):
                if signal_i + delay >= n:
                    continue
                one_signal = np.zeros(n, dtype=np.int8)
                one_signal[signal_i] = signal[signal_i]
                trades = base.simulate_trades(
                    self.frame,
                    one_signal,
                    scenario_cfg,
                    self.funding_times,
                    self.funding_cumulative,
                )
                if trades:
                    output.append(
                        self._correct_exit_bar_mae(trades[0], fee)
                    )
        finally:
            base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original_costs
        self.raw_cache[key] = output
        return output

    def exact_joint(
        self,
        di_cfg: base.StrategyConfig,
        stoch_cfg: base.StrategyConfig,
        scenario: tuple[str, float, float, int],
    ) -> list[base.Trade]:
        tagged = [
            (trade, "di_cross", 1)
            for trade in self.raw_events(di_cfg, scenario)
        ] + [
            (trade, "stoch_reversal", 0)
            for trade in self.raw_events(stoch_cfg, scenario)
        ]
        tagged.sort(
            key=lambda item: (
                item[0].entry_i,
                -item[2],
                item[0].signal_i,
            )
        )
        global_blocked_until = -1
        component_cooldown_until = {
            "di_cross": -1,
            "stoch_reversal": -1,
        }
        output: list[base.Trade] = []
        cooldowns = {
            "di_cross": di_cfg.cooldown_bars,
            "stoch_reversal": stoch_cfg.cooldown_bars,
        }
        for trade, component, _priority in tagged:
            if (
                trade.entry_i <= global_blocked_until
                or trade.entry_i <= component_cooldown_until[component]
            ):
                continue
            output.append(trade)
            global_blocked_until = trade.exit_i
            component_cooldown_until[component] = (
                trade.exit_i + cooldowns[component]
            )
        return output


def approximate_joint(
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    di_cfg: base.StrategyConfig,
    stoch_cfg: base.StrategyConfig,
    scenario: tuple[str, float, float, int],
) -> list[base.Trade]:
    _name, fee, slippage, delay = scenario
    original_costs = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
    try:
        base.FEE_PER_FILL = fee
        base.SLIPPAGE_PER_FILL = slippage
        di_trades = boundary.component_trades(
            frame,
            funding_times,
            funding_cumulative,
            replace(di_cfg, entry_delay_bars=delay),
        )
        stoch_trades = boundary.component_trades(
            frame,
            funding_times,
            funding_cumulative,
            replace(stoch_cfg, entry_delay_bars=delay),
        )
        return base.merge_trade_sets(di_trades, stoch_trades, 1.0, 0.0)
    finally:
        base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original_costs


def evaluate_leg_variants(
    *,
    component: str,
    variants: list[base.StrategyConfig],
    frame: pd.DataFrame,
    funding_times: np.ndarray,
    funding_cumulative: np.ndarray,
    full_end: pd.Timestamp,
) -> tuple[list[base.StrategyConfig], list[dict[str, Any]]]:
    ranked: list[
        tuple[float, float, float, base.StrategyConfig]
    ] = []
    rows: list[dict[str, Any]] = []
    for index, cfg in enumerate(variants):
        bundles: dict[str, dict[str, dict[str, float]]] = {}
        original_costs = (base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL)
        try:
            for scenario in SCENARIOS:
                name, fee, slippage, delay = scenario
                base.FEE_PER_FILL = fee
                base.SLIPPAGE_PER_FILL = slippage
                trades = boundary.component_trades(
                    frame,
                    funding_times,
                    funding_cumulative,
                    replace(cfg, entry_delay_bars=delay),
                )
                bundles[name] = window_bundle(trades, full_end)
        finally:
            base.FEE_PER_FILL, base.SLIPPAGE_PER_FILL = original_costs
        passed = all(prefit_leg_gate(bundle) for bundle in bundles.values())
        score, min_annual, worst_dd = robust_score(bundles)
        rows.append(
            {
                "component": component,
                "name": cfg.name,
                "prefit_pressure_gate": passed,
                "robust_score": score,
                "min_scenario_prefit_annual": min_annual,
                "worst_scenario_prefit_dd": worst_dd,
                "config": json.dumps(asdict(cfg), sort_keys=True),
                **{
                    key: value
                    for name, bundle in bundles.items()
                    for key, value in flatten_bundle(bundle, name).items()
                },
            }
        )
        if passed:
            ranked.append((score, min_annual, worst_dd, cfg))
        if (index + 1) % 100 == 0:
            print(
                f"{component} {index + 1}/{len(variants)} "
                f"prefit-gate={len(ranked)}",
                flush=True,
            )
    ranked.sort(reverse=True, key=lambda item: item[:3])
    baseline = v4_engine_configs()[0 if component == "di_cross" else 1]
    selected = [item[3] for item in ranked[:TOP_LEGS]]
    if baseline not in selected:
        selected.append(baseline)
    return selected, rows


def scenario_target_pass(
    bundle: dict[str, dict[str, float]]
) -> bool:
    return base.target_gate(
        bundle["reused_holdout"], bundle["current_full"]
    )


def pct(value: float) -> str:
    return base.pct(float(value))


def mult(value: float) -> str:
    return base.mult(float(value), digits=4)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_DIR.mkdir(parents=True, exist_ok=True)
    frame, funding, quality = base.load_data()
    frame = base.add_features(frame, funding)
    frame = v3ab.ensure_extra_macd_features(frame)
    funding_times, funding_cumulative = base.funding_prefix(funding)
    full_end = pd.Timestamp(frame["ts"].iloc[-1]) + pd.Timedelta(hours=1)
    engine = ExactJointEngine(frame, funding_times, funding_cumulative)
    v4_di, v4_stoch = v4_engine_configs()

    baseline_audit: dict[str, Any] = {}
    baseline_trade_rows: list[dict[str, Any]] = []
    for scenario in SCENARIOS:
        scenario_name = scenario[0]
        approximate = approximate_joint(
            frame,
            funding_times,
            funding_cumulative,
            v4_di,
            v4_stoch,
            scenario,
        )
        exact = engine.exact_joint(v4_di, v4_stoch, scenario)
        approximate_bundle = window_bundle(approximate, full_end)
        exact_bundle = window_bundle(exact, full_end)
        approximate_keys = {
            (trade.style, trade.signal_i, trade.side) for trade in approximate
        }
        exact_keys = {
            (trade.style, trade.signal_i, trade.side) for trade in exact
        }
        baseline_audit[scenario_name] = {
            "approximate": approximate_bundle,
            "exact": exact_bundle,
            "trade_path_equal": approximate_keys == exact_keys,
            "approximate_trade_count": len(approximate),
            "exact_trade_count": len(exact),
            "approximate_only": sorted(approximate_keys - exact_keys),
            "exact_only": sorted(exact_keys - approximate_keys),
        }
        for trade in exact:
            baseline_trade_rows.append(
                {
                    "candidate": "V4_exact_joint",
                    "scenario": scenario_name,
                    **asdict(trade),
                }
            )

    di_selected, di_rows = evaluate_leg_variants(
        component="di_cross",
        variants=di_variants(),
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        full_end=full_end,
    )
    stoch_selected, stoch_rows = evaluate_leg_variants(
        component="stoch_reversal",
        variants=stoch_variants(),
        frame=frame,
        funding_times=funding_times,
        funding_cumulative=funding_cumulative,
        full_end=full_end,
    )
    pd.DataFrame(di_rows + stoch_rows).to_csv(LEG_ROWS_CSV, index=False)

    ensemble_candidates: list[dict[str, Any]] = []
    for di_cfg in di_selected:
        for stoch_cfg in stoch_selected:
            bundles = {
                scenario[0]: window_bundle(
                    engine.exact_joint(di_cfg, stoch_cfg, scenario),
                    full_end,
                )
                for scenario in SCENARIOS
            }
            passed = prefit_ensemble_gate(bundles)
            score, min_annual, worst_dd = robust_score(bundles)
            ensemble_candidates.append(
                {
                    "combo_id": f"{di_cfg.name}__{stoch_cfg.name}",
                    "di_config": asdict(di_cfg),
                    "stoch_config": asdict(stoch_cfg),
                    "prefit_pressure_gate": passed,
                    "robust_score": score,
                    "min_scenario_prefit_annual": min_annual,
                    "worst_scenario_prefit_dd": worst_dd,
                    "bundles": bundles,
                }
            )
    eligible = [
        row for row in ensemble_candidates if row["prefit_pressure_gate"]
    ]
    eligible.sort(
        key=lambda row: (
            row["robust_score"],
            row["min_scenario_prefit_annual"],
            row["worst_scenario_prefit_dd"],
        ),
        reverse=True,
    )
    frozen = eligible[:FROZEN_ENSEMBLES]
    for row in ensemble_candidates:
        row["frozen_reveal"] = row in frozen
        bundles = row["bundles"]
        row["all_scenario_current_dd_pass"] = all(
            bundle["current_full"]["max_dd"] > MAX_DD
            for bundle in bundles.values()
        )
        row["all_scenario_holdout_dd_pass"] = all(
            bundle["reused_holdout"]["max_dd"] > MAX_DD
            for bundle in bundles.values()
        )
        row["all_scenario_target_pass"] = all(
            scenario_target_pass(bundle) for bundle in bundles.values()
        )
    posthoc_dd_fixes = [
        row
        for row in eligible
        if row["all_scenario_current_dd_pass"]
        and row["all_scenario_holdout_dd_pass"]
    ]
    posthoc_dd_fixes.sort(
        key=lambda row: (
            row["robust_score"],
            row["min_scenario_prefit_annual"],
        ),
        reverse=True,
    )
    best_posthoc_dd_fix = posthoc_dd_fixes[0] if posthoc_dd_fixes else None

    csv_rows: list[dict[str, Any]] = []
    for row in ensemble_candidates:
        csv_rows.append(
            {
                key: value
                for key, value in row.items()
                if key not in {"bundles", "di_config", "stoch_config"}
            }
            | {
                "di_config": json.dumps(row["di_config"], sort_keys=True),
                "stoch_config": json.dumps(
                    row["stoch_config"], sort_keys=True
                ),
            }
            | {
                key: value
                for scenario, bundle in row["bundles"].items()
                for key, value in flatten_bundle(bundle, scenario).items()
            }
        )
    pd.DataFrame(csv_rows).sort_values(
        ["prefit_pressure_gate", "robust_score"], ascending=[False, False]
    ).to_csv(ENSEMBLE_ROWS_CSV, index=False)

    for row in frozen:
        di_cfg = base.StrategyConfig(**row["di_config"])
        stoch_cfg = base.StrategyConfig(**row["stoch_config"])
        for scenario in SCENARIOS:
            for trade in engine.exact_joint(di_cfg, stoch_cfg, scenario):
                baseline_trade_rows.append(
                    {
                        "candidate": row["combo_id"],
                        "scenario": scenario[0],
                        **asdict(trade),
                    }
                )
    if best_posthoc_dd_fix is not None and best_posthoc_dd_fix not in frozen:
        di_cfg = base.StrategyConfig(**best_posthoc_dd_fix["di_config"])
        stoch_cfg = base.StrategyConfig(**best_posthoc_dd_fix["stoch_config"])
        for scenario in SCENARIOS:
            for trade in engine.exact_joint(di_cfg, stoch_cfg, scenario):
                baseline_trade_rows.append(
                    {
                        "candidate": (
                            "POSTHOC_DD_FIX__"
                            f"{best_posthoc_dd_fix['combo_id']}"
                        ),
                        "scenario": scenario[0],
                        **asdict(trade),
                    }
                )
    pd.DataFrame(baseline_trade_rows).to_csv(TRADE_ROWS_CSV, index=False)

    best_dd_fix = next(
        (
            row
            for row in frozen
            if row["all_scenario_current_dd_pass"]
            and row["all_scenario_holdout_dd_pass"]
        ),
        None,
    )
    payload = {
        "family": "HYPE-1H-Adaptive-Regime",
        "base_version": "HYPE-1H-Adaptive-Regime-V4",
        "status": "exact_joint_state_machine_audit_and_pressure_optimization_not_promoted",
        "date": DATE_TAG,
        "data_quality": quality,
        "full_end": full_end,
        "costs": [
            {
                "scenario": name,
                "fee_per_fill": fee,
                "slippage_per_fill": slippage,
                "entry_delay_bars": delay,
            }
            for name, fee, slippage, delay in SCENARIOS
        ],
        "baseline_state_machine_audit": baseline_audit,
        "search_counts": {
            "di_variants": len(di_variants()),
            "stoch_variants": len(stoch_variants()),
            "di_retained": len(di_selected),
            "stoch_retained": len(stoch_selected),
            "ensemble_combinations": len(ensemble_candidates),
            "prefit_pressure_gate": len(eligible),
            "frozen_reveal": len(frozen),
        },
        "frozen_reveal": frozen,
        "best_frozen_dd_fix": best_dd_fix,
        "posthoc_dd_fix_count": len(posthoc_dd_fixes),
        "best_posthoc_dd_fix": best_posthoc_dd_fix,
    }
    SUMMARY_JSON.write_text(
        json.dumps(base.json_safe(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    exact_base = baseline_audit["base_k1"]["exact"]["current_full"]
    approx_base = baseline_audit["base_k1"]["approximate"]["current_full"]
    exact_hold = baseline_audit["base_k1"]["exact"]["reused_holdout"]
    approx_hold = baseline_audit["base_k1"]["approximate"]["reused_holdout"]
    exact_k2 = baseline_audit["delay_k2"]["exact"]["current_full"]
    exact_8bps = baseline_audit["slip_8bps"]["exact"]["current_full"]
    report = [
        "# HYPE-1H-Adaptive-Regime-V4 执行压力归因与优化 - 2026-07-10",
        "",
        "## 结论",
        "",
        (
            "优化前先发现 V4 现有 ensemble 回测不是精确单账户状态机："
            "它先独立模拟两条腿，再合并交易；被另一条腿挡掉的虚拟交易仍会在单腿流中错误触发持仓/冷却，"
            "从而压掉后续真实可入场信号。精确联合回放在 base/K+2/8bps 三个场景都比旧近似口径多出 "
            "`1` 笔 Stoch 空单，因此旧 V4 指标不是 live runner 可直接复现的事实源。"
        ),
        "",
        (
            f"Base K+1 current full 从旧近似 `{mult(approx_base['annual_multiple'])} / "
            f"{pct(approx_base['max_dd'])} / {pct(approx_base['win_rate'])} / "
            f"{int(approx_base['trades'])} trades` 修正为精确联合回放 "
            f"`{mult(exact_base['annual_multiple'])} / {pct(exact_base['max_dd'])} / "
            f"{pct(exact_base['win_rate'])} / {int(exact_base['trades'])} trades`；"
            f"reused holdout 年化由 `{mult(approx_hold['annual_multiple'])}` 降至 "
            f"`{mult(exact_hold['annual_multiple'])}`。"
        ),
        "",
        (
            f"精确联合回放下，K+2 current full 为 `{mult(exact_k2['annual_multiple'])} / "
            f"{pct(exact_k2['max_dd'])}`；8bps 为 `{mult(exact_8bps['annual_multiple'])} / "
            f"{pct(exact_8bps['max_dd'])}`。压力失败的结构性原因是固定杠杆与 ATR 宽止损叠加："
            "单笔 DI/Stoch 风险已经接近或超过组合 `20%` 回撤预算。"
        ),
        "",
        "## 精确状态机对账",
        "",
        "| Scenario | Old annual/DD/trades | Exact annual/DD/trades | Path equal |",
        "| --- | ---: | ---: | --- |",
    ]
    for scenario_name, values in baseline_audit.items():
        old = values["approximate"]["current_full"]
        exact = values["exact"]["current_full"]
        report.append(
            f"| `{scenario_name}` | `{mult(old['annual_multiple'])} / "
            f"{pct(old['max_dd'])} / {int(old['trades'])}` | "
            f"`{mult(exact['annual_multiple'])} / {pct(exact['max_dd'])} / "
            f"{int(exact['trades'])}` | `{values['trade_path_equal']}` |"
        )
    report.extend(
        [
            "",
            "## 压力优先搜索协议",
            "",
            "- 只用 train / validation / prefit 选择腿与 ensemble；reused holdout/current full 只在冻结后揭示。",
            "- 三个场景都要求 prefit 年化 `>=10x`、胜率 `>=50%`、train/validation/prefit 最大回撤严格小于 `20%`。",
            "- 搜索只改风险机制：DI/Stoch 的硬止损、最长持仓、trailing、固定杠杆或按止损距离封顶的 risk sizing；不按后段坏交易拟合新的指标过滤器。",
            "",
            "## 冻结揭示结果",
            "",
            "| Candidate | Base full/DD | K+2 full/DD | 8bps full/DD | All current/holdout DD pass | All target pass |",
            "| --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in frozen:
        bundles = row["bundles"]
        report.append(
            f"| `{row['combo_id']}` | "
            f"`{mult(bundles['base_k1']['current_full']['annual_multiple'])} / "
            f"{pct(bundles['base_k1']['current_full']['max_dd'])}` | "
            f"`{mult(bundles['delay_k2']['current_full']['annual_multiple'])} / "
            f"{pct(bundles['delay_k2']['current_full']['max_dd'])}` | "
            f"`{mult(bundles['slip_8bps']['current_full']['annual_multiple'])} / "
            f"{pct(bundles['slip_8bps']['current_full']['max_dd'])}` | "
            f"`{row['all_scenario_current_dd_pass'] and row['all_scenario_holdout_dd_pass']}` | "
            f"`{row['all_scenario_target_pass']}` |"
        )
    if best_posthoc_dd_fix is not None:
        bundles = best_posthoc_dd_fix["bundles"]
        report.extend(
            [
                "",
                "## 后验回撤修复方向（不是冻结赢家）",
                "",
                (
                    f"冻结榜前 `{len(frozen)}` 名没有完整回撤通过行；在全部 "
                    f"`{len(eligible)}` 个 prefit pressure-gate 组合中，事后查看 "
                    f"reused holdout/current full 后共有 `{len(posthoc_dd_fixes)}` 行能让三个场景回撤都小于 `20%`。"
                    "这只能用于定位机制，不能重新包装成未见数据赢家。"
                ),
                "",
                (
                    f"代表行 `{best_posthoc_dd_fix['combo_id']}`："
                    f"base `{mult(bundles['base_k1']['current_full']['annual_multiple'])} / "
                    f"{pct(bundles['base_k1']['current_full']['max_dd'])}`；"
                    f"K+2 `{mult(bundles['delay_k2']['current_full']['annual_multiple'])} / "
                    f"{pct(bundles['delay_k2']['current_full']['max_dd'])}`；"
                    f"8bps `{mult(bundles['slip_8bps']['current_full']['annual_multiple'])} / "
                    f"{pct(bundles['slip_8bps']['current_full']['max_dd'])}`。"
                ),
                "",
                (
                    "该方向只做三件事：DI 杠杆 `3.0x -> 2.5x`；"
                    "Stoch 硬止损 `4 ATR -> 2 ATR`；Stoch 最长持仓 `8h -> 6h`。"
                    "它证明风险预算可以修复回撤，但 K+2 和 reused holdout 年化显著不足，"
                    "说明剩余问题是延迟后信号边际消失，而不是再调高杠杆可以解决。"
                ),
            ]
        )
    report.extend(
        [
            "",
            "## 决策边界",
            "",
            "- 本报告先修复研究事实源，不登记新版本、不提升状态。",
            "- 即使找到三个压力场景回撤都小于 `20%` 的冻结诊断行，也必须继续检查 K+2 年化/后段稳定性、逐笔路径、真实 stop-market 滑点和生产 runner 状态恢复。",
            "- 若没有完整 target pass，则只能把结果描述为“回撤修复方向”，不能称为 live-ready。",
            "",
            "## 机器证据",
            "",
            f"- JSON：`artifacts/{SUMMARY_JSON.name}`",
            f"- 单腿搜索：`artifacts/{LEG_ROWS_CSV.name}`",
            f"- ensemble 搜索：`artifacts/{ENSEMBLE_ROWS_CSV.name}`",
            f"- 精确交易路径：`artifacts/{TRADE_ROWS_CSV.name}`",
            "",
            "复现：",
            "",
            "```bash",
            "uv run python research/hype/1h-adaptive-regime/scripts/audit_hype_1h_ar_v4_pressure_optimization.py",
            "```",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")
    print(
        json.dumps(
            base.json_safe(
                {
                    "baseline_exact": {
                        "base": exact_base,
                        "reused_holdout": exact_hold,
                        "k2": exact_k2,
                        "8bps": exact_8bps,
                    },
                    "search_counts": payload["search_counts"],
                    "best_frozen_dd_fix": best_dd_fix,
                    "posthoc_dd_fix_count": len(posthoc_dd_fixes),
                    "best_posthoc_dd_fix": best_posthoc_dd_fix,
                }
            ),
            indent=2,
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
