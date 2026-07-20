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
DECISION_FREQUENCIES = (4, 8)
CONFIRMATION_WEIGHTS = (0.25, 0.50)
CONFIRMATION_Z_MINS = (None, 0.0, 0.5)
PENALTIES = ((0.75, 0.25), (1.00, 0.50))
RISK_CAPS = ((None, None), (0.5, 1.0))
UTILITY_THRESHOLDS = (2.25, 2.50)
MAX_POSITIONS = (1, 3, 5)
GROSS_EXPOSURES = (0.50, 0.625, 0.75)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Confirm stable-full 48h return scores with a second OOF model."
    )
    parser.add_argument(
        "--confirmation-model-type",
        choices=("classification", "ranker"),
        required=True,
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ensemble-seeds", nargs="+", type=int)
    parser.add_argument("--fine", action="store_true")
    parser.add_argument("--robust-fine", action="store_true")
    parser.add_argument("--aggressive", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    allocator.validate_boundary()
    search_modes = (args.fine, args.robust_fine, args.aggressive)
    if sum(search_modes) > 1:
        raise ValueError(
            "--fine, --robust-fine and --aggressive are mutually exclusive"
        )
    if args.aggressive:
        confirmation_weights = (0.05, 0.10, 0.15)
        confirmation_z_mins = (0.25, 0.50)
        penalties = ((0.75, 0.25), (1.00, 0.50))
        risk_caps = ((None, None), (0.5, 1.0), (0.0, 1.0), (0.0, 0.5))
        utility_thresholds = (2.50, 2.75)
        max_positions_grid = (1, 3, 5)
        gross_exposures = (0.75, 0.85, 1.00)
    elif args.robust_fine:
        # Narrow refinement around the four-seed ensemble's balanced frontier.
        # This mode intentionally keeps the model family and risk terms frozen.
        confirmation_weights = (0.20, 0.225, 0.25, 0.275, 0.30)
        confirmation_z_mins = (0.40, 0.50, 0.60, 0.70, 0.80)
        penalties = ((1.00, 0.50),)
        risk_caps = ((None, None),)
        utility_thresholds = (2.40, 2.50, 2.60, 2.70, 2.80)
        max_positions_grid = (1, 3, 5)
        gross_exposures = (0.40, 0.45, 0.50, 0.55)
    elif args.fine:
        confirmation_weights = (0.05, 0.10, 0.15, 0.20, 0.25)
        confirmation_z_mins = (0.25, 0.50)
        penalties = ((1.00, 0.50),)
        risk_caps = ((None, None),)
        utility_thresholds = (2.25, 2.50, 2.75)
        max_positions_grid = (1, 3, 5)
        gross_exposures = (0.625, 0.70, 0.75)
    else:
        confirmation_weights = CONFIRMATION_WEIGHTS
        confirmation_z_mins = CONFIRMATION_Z_MINS
        penalties = PENALTIES
        risk_caps = RISK_CAPS
        utility_thresholds = UTILITY_THRESHOLDS
        max_positions_grid = MAX_POSITIONS
        gross_exposures = GROSS_EXPOSURES
    base_args = argparse.Namespace(
        feature_set="stable_full",
        return_model_type="regression",
        mae_model_type="quantile",
        event_model_type="classification",
        seed=args.seed,
    )
    bundle = allocator.load_prediction_bundle(
        base_args, HORIZON, ensemble_seeds=args.ensemble_seeds
    )
    candidates = allocator.candidate_sides(
        bundle, score_source="lgbm", horizon=HORIZON
    )
    candidates = candidates.loc[candidates["side"] == "short"].copy()
    if args.ensemble_seeds:
        confirmation = allocator.load_task_score_ensemble(
            task="short_return",
            model_type=args.confirmation_model_type,
            feature_set="compact",
            horizon=HORIZON,
            seeds=args.ensemble_seeds,
            include_outcomes=False,
        )[["ts", "symbol", "score"]]
    else:
        confirmation = allocator.load_task_scores(
            task="short_return",
            model_type=args.confirmation_model_type,
            feature_set="compact",
            horizon=HORIZON,
            seed=args.seed,
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
    rows = []
    for decision_frequency in DECISION_FREQUENCIES:
        scheduled_base = candidates.loc[
            candidates["ts"].dt.hour % decision_frequency == 0
        ].copy()
        print(
            f"confirmation={args.confirmation_model_type} "
            f"frequency={decision_frequency}h rows={len(scheduled_base)}",
            flush=True,
        )
        for confirmation_weight in confirmation_weights:
            scheduled_weighted = scheduled_base.copy()
            scheduled_weighted["return_z"] = (
                scheduled_weighted["return_z"]
                + confirmation_weight * scheduled_weighted["confirmation_z"]
            )
            for confirmation_z_min in confirmation_z_mins:
                scheduled = scheduled_weighted
                if confirmation_z_min is not None:
                    scheduled = scheduled.loc[
                        scheduled["confirmation_z"] >= confirmation_z_min
                    ]
                for mae_penalty, event_penalty in penalties:
                    for mae_z_max, event_z_max in risk_caps:
                        for utility_threshold in utility_thresholds:
                            for max_positions in max_positions_grid:
                                selected = allocator.select_legs(
                                    scheduled,
                                    side_mode="short_only",
                                    mae_penalty=mae_penalty,
                                    event_penalty=event_penalty,
                                    utility_threshold=utility_threshold,
                                    max_positions=max_positions,
                                    mae_z_max=mae_z_max,
                                    event_z_max=event_z_max,
                                )
                                decisions, legs = allocator.scheduled_policy(
                                    scheduled_base,
                                    selected,
                                    decision_frequency=decision_frequency,
                                )
                                for gross_exposure in gross_exposures:
                                    metrics = allocator.evaluate_policy(
                                        decisions,
                                        legs,
                                        horizon=HORIZON,
                                        decision_frequency=decision_frequency,
                                        gross_exposure=gross_exposure,
                                    )
                                    rows.append(
                                        {
                                            "score_source": "lgbm_confirmation",
                                            "feature_set": "stable_full",
                                            "return_model_type": "regression",
                                            "confirmation_feature_set": "compact",
                                            "confirmation_model_type": (
                                                args.confirmation_model_type
                                            ),
                                            "seed": args.seed,
                                            "ensemble_seeds": (
                                                ",".join(
                                                    str(seed)
                                                    for seed in args.ensemble_seeds
                                                )
                                                if args.ensemble_seeds
                                                else None
                                            ),
                                            "horizon_hours": HORIZON,
                                            "decision_frequency_hours": (
                                                decision_frequency
                                            ),
                                            "side_mode": "short_only",
                                            "confirmation_weight": (
                                                confirmation_weight
                                            ),
                                            "confirmation_z_min": confirmation_z_min,
                                            "mae_penalty": mae_penalty,
                                            "event_penalty": event_penalty,
                                            "mae_z_max": mae_z_max,
                                            "event_z_max": event_z_max,
                                            "utility_threshold": utility_threshold,
                                            "max_positions": max_positions,
                                            "gross_exposure": gross_exposure,
                                            **metrics,
                                        }
                                    )
    results = pd.DataFrame(rows).sort_values(
        ["historical_gate_pass", "selection_score"], ascending=[False, False]
    )
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.aggressive:
        grid_suffix = "_aggressive"
    elif args.robust_fine:
        grid_suffix = "_robust_fine"
    elif args.fine:
        grid_suffix = "_fine"
    else:
        grid_suffix = ""
    seed_text = (
        "ensemble_s" + "-".join(str(seed) for seed in args.ensemble_seeds)
        if args.ensemble_seeds
        else f"s{args.seed}"
    )
    suffix = f"{args.confirmation_model_type}{grid_suffix}_{seed_text}"
    results_path = OUTPUT_ROOT / f"h48_confirmation_search_{suffix}.csv"
    frontier_path = OUTPUT_ROOT / f"h48_confirmation_frontier_{suffix}.csv"
    summary_path = OUTPUT_ROOT / f"h48_confirmation_summary_{suffix}.json"
    results.to_csv(results_path, index=False)
    results.head(250).to_csv(frontier_path, index=False)
    summary = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "configuration_count": len(results),
        "historical_gate_pass_count": int(results["historical_gate_pass"].sum()),
        "confirmation_model_type": args.confirmation_model_type,
        "seed": args.seed,
        "ensemble_seeds": args.ensemble_seeds,
        "fine_grid": args.fine,
        "robust_fine_grid": args.robust_fine,
        "aggressive_grid": args.aggressive,
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
                "historical_gate_pass_count": summary[
                    "historical_gate_pass_count"
                ],
                "best": summary["best"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
