from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import search_development_allocator as allocator  # noqa: E402


ROOT = allocator.ROOT
OUTPUT_ROOT = allocator.OUTPUT_ROOT
HORIZON = 48
SEEDS = (7, 17, 29, 42)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search a cross-sectionally calibrated 48h utility allocator."
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seeds = list(dict.fromkeys(args.seeds))
    if len(seeds) < 2:
        raise ValueError("calibrated utility search requires a seed ensemble")
    allocator.validate_boundary()
    base_args = argparse.Namespace(
        feature_set="stable_full",
        return_model_type="regression",
        mae_model_type="quantile",
        event_model_type="classification",
        seed=seeds[0],
    )
    bundle = allocator.load_prediction_bundle(
        base_args, HORIZON, ensemble_seeds=seeds
    )
    candidates = allocator.candidate_sides(
        bundle, score_source="lgbm", horizon=HORIZON
    )
    candidates = candidates.loc[candidates["side"] == "short"].copy()
    confirmation = allocator.load_task_score_ensemble(
        task="short_return",
        model_type="classification",
        feature_set="compact",
        horizon=HORIZON,
        seeds=seeds,
        include_outcomes=False,
    )[["ts", "symbol", "score"]]
    confirmation["confirmation_z"] = allocator.within_time_zscore(
        confirmation, "score"
    )
    candidates = candidates.merge(
        confirmation[["ts", "symbol", "confirmation_z"]],
        on=["ts", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    for decision_frequency in (4, 8):
        scheduled_base = candidates.loc[
            candidates["ts"].dt.hour % decision_frequency == 0
        ].copy()
        print(f"calibrated frequency={decision_frequency} rows={len(scheduled_base)}", flush=True)
        for confirmation_weight in (0.25, 0.50):
            weighted = scheduled_base.copy()
            weighted["return_z"] = (
                weighted["return_z"]
                + confirmation_weight * weighted["confirmation_z"]
            )
            for confirmation_z_min in (None, 0.0, 0.5):
                confirmed = weighted
                if confirmation_z_min is not None:
                    confirmed = weighted.loc[
                        weighted["confirmation_z"] >= confirmation_z_min
                    ].copy()
                for mae_penalty, event_penalty in ((0.75, 0.25), (1.0, 0.5)):
                    scored = confirmed.copy()
                    scored["raw_utility"] = (
                        scored["return_z"]
                        - mae_penalty * scored["mae_z"]
                        - event_penalty * scored["event_z"]
                    )
                    scored["utility"] = allocator.within_time_zscore(
                        scored, "raw_utility"
                    )
                    for utility_z_threshold in (1.0, 1.25, 1.5, 1.75, 2.0):
                        eligible = scored.loc[
                            scored["utility"] >= utility_z_threshold
                        ]
                        for max_positions in (3, 5):
                            selected = (
                                eligible.sort_values(
                                    ["ts", "utility", "symbol"],
                                    ascending=[True, False, True],
                                )
                                .groupby("ts", sort=False, group_keys=False)
                                .head(max_positions)
                                .copy()
                            )
                            decisions, legs = allocator.scheduled_policy(
                                scheduled_base,
                                selected,
                                decision_frequency=decision_frequency,
                            )
                            for gross_exposure in (0.20, 0.25, 0.30, 0.375):
                                metrics = allocator.evaluate_policy(
                                    decisions,
                                    legs,
                                    horizon=HORIZON,
                                    decision_frequency=decision_frequency,
                                    gross_exposure=gross_exposure,
                                )
                                rows.append(
                                    {
                                        "score_source": "lgbm_calibrated_utility",
                                        "feature_set": "stable_full",
                                        "return_model_type": "regression",
                                        "confirmation_feature_set": "compact",
                                        "confirmation_model_type": "classification",
                                        "ensemble_seeds": ",".join(map(str, seeds)),
                                        "horizon_hours": HORIZON,
                                        "decision_frequency_hours": decision_frequency,
                                        "side_mode": "short_only",
                                        "confirmation_weight": confirmation_weight,
                                        "confirmation_z_min": confirmation_z_min,
                                        "mae_penalty": mae_penalty,
                                        "event_penalty": event_penalty,
                                        "utility_calibration": "within_time_robust_zscore",
                                        "utility_z_threshold": utility_z_threshold,
                                        "max_positions": max_positions,
                                        "gross_exposure": gross_exposure,
                                        **metrics,
                                    }
                                )
    results = pd.DataFrame(rows)
    results["projected_three_month_decisions"] = results["decision_count"] / 13.0
    results["projected_three_month_legs"] = results["trade_count"] / 13.0
    results["contract_feasible_development"] = (
        (results["max_drawdown"] >= -0.20)
        & (results["sharpe"] >= 1.50)
        & (results["profit_factor"] >= 1.30)
        & (results["positive_fold_count"] >= 4)
        & (results["stress_total_return"] > 0.0)
        & (results["stress_max_drawdown"] >= -0.25)
        & (results["projected_three_month_decisions"] >= 45)
        & (results["projected_three_month_legs"] >= 300)
        & (results["symbol_positive_profit_concentration"] <= 0.25)
        & (results["month_positive_profit_concentration"] <= 0.35)
    )
    results["selection_score_r3"] = (
        results["annualized_return"]
        + 0.25 * results["sharpe"]
        + 0.75 * results["win_rate"]
        + 0.05 * results["positive_fold_count"]
        - 3.0 * (-results["max_drawdown"] - 0.20).clip(lower=0.0)
        - 2.0 * (0.55 - results["win_rate"]).clip(lower=0.0)
    )
    results = results.sort_values(
        ["contract_feasible_development", "selection_score_r3"],
        ascending=[False, False],
    )
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = "ensemble_s" + "-".join(map(str, seeds))
    results_path = OUTPUT_ROOT / f"h48_calibrated_utility_search_{suffix}.csv"
    frontier_path = OUTPUT_ROOT / f"h48_calibrated_utility_frontier_{suffix}.csv"
    summary_path = OUTPUT_ROOT / f"h48_calibrated_utility_summary_{suffix}.json"
    results.to_csv(results_path, index=False)
    results.head(300).to_csv(frontier_path, index=False)
    feasible = results.loc[results["contract_feasible_development"]]
    summary = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "configuration_count": len(results),
        "contract_feasible_count": len(feasible),
        "best": results.iloc[0].to_dict(),
        "results_csv": str(results_path.relative_to(ROOT)),
        "frontier_csv": str(frontier_path.relative_to(ROOT)),
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "configuration_count": len(results),
                "contract_feasible_count": len(feasible),
                "best": summary["best"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
