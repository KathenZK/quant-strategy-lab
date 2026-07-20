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
DECISION_FREQUENCIES = (8, 12, 24)
PENALTIES = ((0.25, 0.10), (0.50, 0.25), (0.75, 0.25), (1.00, 0.50))
RISK_CAPS = (
    (None, None),
    (0.5, 1.0),
    (0.0, 1.0),
    (0.0, 0.5),
    (-0.5, 0.5),
)
UTILITY_THRESHOLDS = (1.50, 1.75, 2.00, 2.25, 2.50)
MAX_POSITIONS = (1, 2, 3, 5)
GROSS_EXPOSURES = (0.25, 0.375, 0.50, 0.625)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Focused 48h short allocator search with explicit risk caps."
    )
    parser.add_argument("--feature-set", default="compact")
    parser.add_argument("--return-model-type", default="regression")
    parser.add_argument("--mae-model-type", default="quantile")
    parser.add_argument("--event-model-type", default="classification")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--ensemble-seeds", nargs="+", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    allocator.validate_boundary()
    bundle = allocator.load_prediction_bundle(
        args, HORIZON, ensemble_seeds=args.ensemble_seeds
    )
    candidates = allocator.candidate_sides(
        bundle, score_source="lgbm", horizon=HORIZON
    )
    candidates = candidates.loc[candidates["side"] == "short"].copy()
    rows = []
    for decision_frequency in DECISION_FREQUENCIES:
        scheduled = candidates.loc[
            candidates["ts"].dt.hour % decision_frequency == 0
        ].copy()
        print(
            f"local_h48 frequency={decision_frequency}h rows={len(scheduled)}",
            flush=True,
        )
        for mae_penalty, event_penalty in PENALTIES:
            for mae_z_max, event_z_max in RISK_CAPS:
                for utility_threshold in UTILITY_THRESHOLDS:
                    for max_positions in MAX_POSITIONS:
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
                            scheduled,
                            selected,
                            decision_frequency=decision_frequency,
                        )
                        for gross_exposure in GROSS_EXPOSURES:
                            metrics = allocator.evaluate_policy(
                                decisions,
                                legs,
                                horizon=HORIZON,
                                decision_frequency=decision_frequency,
                                gross_exposure=gross_exposure,
                            )
                            rows.append(
                                {
                                    "score_source": "lgbm",
                                    "return_model_type": args.return_model_type,
                                    "mae_model_type": "quantile",
                                    "event_model_type": "classification",
                                    "feature_set": args.feature_set,
                                    "seed": args.seed,
                                    "ensemble_seeds": (
                                        ",".join(
                                            str(seed) for seed in args.ensemble_seeds
                                        )
                                        if args.ensemble_seeds
                                        else None
                                    ),
                                    "horizon_hours": HORIZON,
                                    "decision_frequency_hours": decision_frequency,
                                    "side_mode": "short_only",
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
    seed_text = (
        "ensemble_s" + "-".join(str(seed) for seed in args.ensemble_seeds)
        if args.ensemble_seeds
        else f"s{args.seed}"
    )
    suffix = f"{args.feature_set}_{args.return_model_type}_{seed_text}"
    results_path = OUTPUT_ROOT / f"h48_local_risk_search_{suffix}.csv"
    frontier_path = OUTPUT_ROOT / f"h48_local_risk_frontier_{suffix}.csv"
    summary_path = OUTPUT_ROOT / f"h48_local_risk_summary_{suffix}.json"
    results.to_csv(results_path, index=False)
    results.head(300).to_csv(frontier_path, index=False)
    summary = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "configuration_count": len(results),
        "historical_gate_pass_count": int(results["historical_gate_pass"].sum()),
        "feature_set": args.feature_set,
        "return_model_type": args.return_model_type,
        "seed": args.seed,
        "ensemble_seeds": args.ensemble_seeds,
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
