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
ARTIFACT_DIR = allocator.ARTIFACT_DIR
HORIZON = 48
DECISION_FREQUENCY = 4
CONFIRMATION_WEIGHT = 0.25
CONFIRMATION_Z_MIN = None
MAE_PENALTY = 1.00
EVENT_PENALTY = 0.50
UTILITY_THRESHOLD = 1.75
MAX_POSITIONS = 5
GROSS_EXPOSURE = 0.375
DEFAULT_SEEDS = (7, 17, 29, 42)
OUTPUT_PATH = ARTIFACT_DIR / "h48_candidate_seed_stability_r4_2026-07-18.json"
CSV_PATH = ARTIFACT_DIR / "h48_candidate_seed_stability_r4_2026-07-18.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate one frozen historical candidate across seeds and ensemble."
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=list(DEFAULT_SEEDS))
    return parser.parse_args()


def evaluate(seeds: list[int]) -> dict[str, object]:
    is_ensemble = len(seeds) > 1
    base_args = argparse.Namespace(
        feature_set="stable_full",
        return_model_type="regression",
        mae_model_type="quantile",
        event_model_type="classification",
        seed=seeds[0],
    )
    bundle = allocator.load_prediction_bundle(
        base_args,
        HORIZON,
        ensemble_seeds=seeds if is_ensemble else None,
    )
    candidates = allocator.candidate_sides(
        bundle, score_source="lgbm", horizon=HORIZON
    )
    candidates = candidates.loc[candidates["side"] == "short"].copy()
    if is_ensemble:
        confirmation = allocator.load_task_score_ensemble(
            task="short_return",
            model_type="classification",
            feature_set="compact",
            horizon=HORIZON,
            seeds=seeds,
            include_outcomes=False,
        )
    else:
        confirmation = allocator.load_task_scores(
            task="short_return",
            model_type="classification",
            feature_set="compact",
            horizon=HORIZON,
            seed=seeds[0],
            include_outcomes=False,
        )
    confirmation = confirmation[["ts", "symbol", "score"]].copy()
    confirmation["confirmation_z"] = allocator.within_time_zscore(
        confirmation, "score"
    )
    candidates = candidates.merge(
        confirmation[["ts", "symbol", "confirmation_z"]],
        on=["ts", "symbol"],
        how="inner",
        validate="one_to_one",
    )
    if CONFIRMATION_Z_MIN is not None:
        candidates = candidates.loc[
            candidates["confirmation_z"] >= CONFIRMATION_Z_MIN
        ].copy()
    candidates["return_z"] = (
        candidates["return_z"]
        + CONFIRMATION_WEIGHT * candidates["confirmation_z"]
    )
    candidates = candidates.loc[
        candidates["ts"].dt.hour % DECISION_FREQUENCY == 0
    ].copy()
    candidates["raw_utility"] = (
        candidates["return_z"]
        - MAE_PENALTY * candidates["mae_z"]
        - EVENT_PENALTY * candidates["event_z"]
    )
    candidates["utility"] = allocator.within_time_zscore(
        candidates, "raw_utility"
    )
    selected = (
        candidates.loc[candidates["utility"] >= UTILITY_THRESHOLD]
        .sort_values(["ts", "utility", "symbol"], ascending=[True, False, True])
        .groupby("ts", sort=False, group_keys=False)
        .head(MAX_POSITIONS)
        .copy()
    )
    decisions, legs = allocator.scheduled_policy(
        candidates,
        selected,
        decision_frequency=DECISION_FREQUENCY,
    )
    metrics = allocator.evaluate_policy(
        decisions,
        legs,
        horizon=HORIZON,
        decision_frequency=DECISION_FREQUENCY,
        gross_exposure=GROSS_EXPOSURE,
    )
    return {
        "identity": (
            "ensemble_s" + "-".join(str(seed) for seed in seeds)
            if is_ensemble
            else f"seed_{seeds[0]}"
        ),
        "seeds": ",".join(str(seed) for seed in seeds),
        **metrics,
    }


def main() -> None:
    args = parse_args()
    seeds = list(dict.fromkeys(args.seeds))
    if len(seeds) < 2:
        raise ValueError("seed stability audit requires at least two seeds")
    rows = [evaluate([seed]) for seed in seeds]
    rows.append(evaluate(seeds))
    frame = pd.DataFrame(rows)
    frame.to_csv(CSV_PATH, index=False)
    seed_rows = frame.loc[frame["identity"].str.startswith("seed_")]
    ensemble_row = frame.loc[frame["identity"].str.startswith("ensemble_")].iloc[0]
    gates = {
        "all_seeds_positive": bool(seed_rows["total_return"].gt(0.0).all()),
        "all_seeds_stress_positive": bool(
            seed_rows["stress_total_return"].gt(0.0).all()
        ),
        "all_seeds_max_drawdown_lte_25pct": bool(
            seed_rows["max_drawdown"].ge(-0.25).all()
        ),
        "ensemble_historical_win_rate_gte_53pct": bool(
            ensemble_row["win_rate"] >= 0.53
        ),
        "ensemble_max_drawdown_lte_20pct": bool(
            ensemble_row["max_drawdown"] >= -0.20
        ),
        "ensemble_stress_drawdown_lte_25pct": bool(
            ensemble_row["stress_max_drawdown"] >= -0.25
        ),
        "ensemble_positive_fold_count_gte_4": bool(
            ensemble_row["positive_fold_count"] >= 4
        ),
        "ensemble_sharpe_gte_1_5": bool(ensemble_row["sharpe"] >= 1.50),
        "ensemble_profit_factor_gte_1_30": bool(
            ensemble_row["profit_factor"] >= 1.30
        ),
        "projected_three_month_legs_gte_300": bool(
            ensemble_row["trade_count"] / 13.0 >= 300
        ),
    }
    blockers = [name for name, passed in gates.items() if not passed]
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "candidate_config": {
            "horizon_hours": HORIZON,
            "decision_frequency_hours": DECISION_FREQUENCY,
            "side_mode": "short_only",
            "return_feature_set": "stable_full",
            "return_model": "LightGBM regression_l1",
            "confirmation_feature_set": "compact",
            "confirmation_model": "LightGBM classification",
            "confirmation_weight": CONFIRMATION_WEIGHT,
            "confirmation_z_min": CONFIRMATION_Z_MIN,
            "mae_penalty": MAE_PENALTY,
            "event_penalty": EVENT_PENALTY,
            "utility_calibration": "within_time_robust_zscore",
            "utility_z_threshold": UTILITY_THRESHOLD,
            "max_positions": MAX_POSITIONS,
            "gross_exposure": GROSS_EXPOSURE,
        },
        "seeds": seeds,
        "gates": gates,
        "blockers": blockers,
        "ensemble": ensemble_row.to_dict(),
        "prospective_target_observations": {
            "development_win_rate_gte_final_55pct_target": bool(
                ensemble_row["win_rate"] >= 0.55
            ),
            "projected_three_month_decisions": float(
                ensemble_row["decision_count"] / 13.0
            ),
            "projected_three_month_legs": float(
                ensemble_row["trade_count"] / 13.0
            ),
            "note": (
                "The 55% win-rate threshold remains a prospective OOS hard gate; "
                "development shortfall is disclosed and is not promoted as a pass."
            ),
        },
        "seed_metrics_csv": str(CSV_PATH.relative_to(ROOT)),
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"candidate seed stability failed: {blockers}")


if __name__ == "__main__":
    main()
