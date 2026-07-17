from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from audit_hype_15m_factors import VALIDATION_END_EXCLUSIVE
from audit_hype_lgbm_round2_prefit import (
    WALK_FORWARD_FOLDS,
    fold_predictions,
    label_from_candidate,
    relaxed_fold_pass,
    validation_predictions,
)
from backtest_hype_lgbm import run_prediction_backtest, summarize_trades
from hype_ml_common import ARTIFACTS_DIR, add_triple_barrier_labels, write_json
from search_hype_lgbm_crossfold import joint_score
from search_hype_lgbm_round2 import base_backtest_config, gate_pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jointly refine ensemble thresholds across folds and leave-one-out ensembles."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--candidate",
        type=Path,
        default=(
            ARTIFACTS_DIR
            / "model_round2_crossfold_ensemble/prefit_candidate_ensemble.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_ensemble_stability_refinement",
    )
    return parser.parse_args()


def threshold_grid() -> list[dict[str, float]]:
    long_levels = np.arange(0.45, 0.751, 0.025).round(3).tolist()
    short_levels = np.arange(0.65, 0.901, 0.025).round(3).tolist()
    both = [
        {
            "long_threshold": long_threshold,
            "short_threshold": short_threshold,
            "probability_margin": margin,
        }
        for long_threshold in long_levels
        for short_threshold in short_levels
        for margin in (0.0, 0.03, 0.08)
    ]
    long_only = [
        {
            "long_threshold": threshold,
            "short_threshold": 1.0,
            "probability_margin": margin,
        }
        for threshold in long_levels
        for margin in (0.0, 0.05)
    ]
    short_only = [
        {
            "long_threshold": 1.0,
            "short_threshold": threshold,
            "probability_margin": margin,
        }
        for threshold in short_levels
        for margin in (0.0, 0.05)
    ]
    return both + long_only + short_only


def survival_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        int(metrics["trade_count"]) >= 20
        and float(metrics["total_return"]) > 0.0
        and float(metrics["win_rate"]) >= 0.55
        and float(metrics["max_drawdown"]) <= 0.20
        and float(metrics["profit_factor"]) >= 1.0
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.loads(args.candidate.read_text(encoding="utf-8"))
    if payload.get("oos_revealed") is not False:
        raise RuntimeError("candidate does not prove sealed OOS")
    candidate = payload["candidate"]
    spec = dict(candidate["model_spec"])
    ensemble_seeds = [int(value) for value in spec.get("ensemble_seeds", [])]
    if len(ensemble_seeds) < 4:
        raise RuntimeError("stability refinement requires at least four ensemble seeds")
    label = label_from_candidate(candidate)
    features = list(candidate["features"])
    risk = {"risk_per_trade": None, "max_leverage": 1.0}

    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos_rows = int((frame["ts"] >= VALIDATION_END_EXCLUSIVE).sum())
    if oos_rows <= 0:
        raise RuntimeError("sealed OOS is absent")
    del frame
    labeled = add_triple_barrier_labels(pre_oos, label)

    fold_predictions_list: list[dict[str, Any]] = []
    for fold_id, train_end_text, test_end_text in WALK_FORWARD_FOLDS:
        predictions, predictive_metrics = fold_predictions(
            pre_oos,
            labeled,
            train_end=pd.Timestamp(train_end_text),
            test_end=pd.Timestamp(test_end_text),
            label=label,
            features=features,
            spec=spec,
            regime="none",
            seed=42,
        )
        fold_predictions_list.append(
            {
                "fold_id": fold_id,
                "predictions": predictions,
                "predictive_metrics": predictive_metrics,
            }
        )

    leave_one_out_predictions: list[dict[str, Any]] = []
    for held_out_seed in ensemble_seeds:
        variant_spec = {
            **spec,
            "ensemble_seeds": [
                seed for seed in ensemble_seeds if seed != held_out_seed
            ],
        }
        predictions, predictive_metrics = validation_predictions(
            pre_oos,
            label=label,
            features=features,
            spec=variant_spec,
            seed=held_out_seed,
            regime="none",
        )
        leave_one_out_predictions.append(
            {
                "held_out_seed": held_out_seed,
                "ensemble_seeds": variant_spec["ensemble_seeds"],
                "predictions": predictions,
                "predictive_metrics": predictive_metrics,
            }
        )

    rows: list[dict[str, Any]] = []
    for threshold in threshold_grid():
        config = base_backtest_config(
            label, str(spec["model_type"]), threshold, risk
        )
        fold_metrics: list[dict[str, Any]] = []
        all_trades: list[dict[str, Any]] = []
        fold_frames: list[pd.DataFrame] = []
        for fold in fold_predictions_list:
            trades, metrics = run_prediction_backtest(
                fold["predictions"], config
            )
            all_trades.extend(trades.to_dict("records"))
            fold_frames.append(fold["predictions"])
            fold_metrics.append(
                {
                    "fold_id": fold["fold_id"],
                    "metrics": metrics,
                    "relaxed_fold_pass": relaxed_fold_pass(metrics),
                }
            )
        combined = summarize_trades(all_trades, pd.concat(fold_frames), config)
        positive_fold_count = sum(
            float(item["metrics"]["total_return"]) > 0.0
            for item in fold_metrics
        )
        relaxed_fold_count = sum(
            bool(item["relaxed_fold_pass"]) for item in fold_metrics
        )
        worst_fold_return = min(
            float(item["metrics"]["total_return"]) for item in fold_metrics
        )
        crossfold_pass = bool(
            gate_pass(combined)
            and positive_fold_count >= 3
            and relaxed_fold_count >= 2
            and worst_fold_return > -0.15
        )

        leave_one_out_metrics: list[dict[str, Any]] = []
        for variant in leave_one_out_predictions:
            _, metrics = run_prediction_backtest(
                variant["predictions"], config
            )
            leave_one_out_metrics.append(
                {
                    "held_out_seed": variant["held_out_seed"],
                    "ensemble_seeds": variant["ensemble_seeds"],
                    "metrics": metrics,
                    "hard_gate_pass": gate_pass(metrics),
                    "survival_pass": survival_pass(metrics),
                }
            )
        loo_hard_count = sum(
            bool(item["hard_gate_pass"]) for item in leave_one_out_metrics
        )
        loo_survival_count = sum(
            bool(item["survival_pass"]) for item in leave_one_out_metrics
        )
        min_loo_profit_factor = min(
            float(item["metrics"]["profit_factor"])
            for item in leave_one_out_metrics
        )
        stability_pass = bool(
            crossfold_pass
            and loo_hard_count >= 3
            and loo_survival_count == len(leave_one_out_metrics)
            and min_loo_profit_factor >= 1.0
        )
        score = (
            joint_score(
                combined,
                positive_fold_count=positive_fold_count,
                relaxed_fold_pass_count=relaxed_fold_count,
                worst_fold_return=worst_fold_return,
            )
            + 1.5 * loo_hard_count
            + 0.25 * loo_survival_count
            + 0.20 * min(min_loo_profit_factor, 3.0)
        )
        rows.append(
            {
                "threshold": threshold,
                "crossfold_metrics": combined,
                "fold_metrics": fold_metrics,
                "positive_fold_count": positive_fold_count,
                "relaxed_fold_pass_count": relaxed_fold_count,
                "worst_fold_return": worst_fold_return,
                "crossfold_pass": crossfold_pass,
                "leave_one_out_metrics": leave_one_out_metrics,
                "loo_hard_gate_pass_count": loo_hard_count,
                "loo_survival_pass_count": loo_survival_count,
                "min_loo_profit_factor": min_loo_profit_factor,
                "stability_pass": stability_pass,
                "stability_score": score,
            }
        )

    best = max(
        rows,
        key=lambda row: (bool(row["stability_pass"]), float(row["stability_score"])),
    )
    frozen_candidate = {
        **candidate,
        "threshold": best["threshold"],
        "metrics": best["crossfold_metrics"],
        "fold_metrics": best["fold_metrics"],
        "leave_one_out_metrics": best["leave_one_out_metrics"],
        "positive_fold_count": best["positive_fold_count"],
        "relaxed_fold_pass_count": best["relaxed_fold_pass_count"],
        "worst_fold_return": best["worst_fold_return"],
        "gate_pass": bool(best["stability_pass"]),
        "selection_score": best["stability_score"],
        "selection_scope": "five pre-OOS folds plus four leave-one-out ensembles",
    }
    pd.json_normalize(
        [
            {
                key: value
                for key, value in row.items()
                if key not in {"fold_metrics", "leave_one_out_metrics"}
            }
            for row in rows
        ]
    ).to_parquet(args.output_dir / "stability_threshold_trials.parquet", index=False)
    write_json(
        args.output_dir / "stability_summary.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "threshold_trial_count": len(rows),
            "stability_pass_count": sum(bool(row["stability_pass"]) for row in rows),
            "best": best,
            "oos_rows_present_but_not_loaded": oos_rows,
            "oos_revealed": False,
        },
    )
    write_json(
        args.output_dir / "prefit_candidate_stable_ensemble.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "candidate": frozen_candidate,
            "validation_gate_pass": bool(best["stability_pass"]),
            "oos_revealed": False,
        },
    )
    print(
        json.dumps(
            {
                "threshold_trial_count": len(rows),
                "stability_pass_count": sum(
                    bool(row["stability_pass"]) for row in rows
                ),
                "best": {
                    "threshold": best["threshold"],
                    "crossfold_metrics": best["crossfold_metrics"],
                    "positive_fold_count": best["positive_fold_count"],
                    "relaxed_fold_pass_count": best[
                        "relaxed_fold_pass_count"
                    ],
                    "worst_fold_return": best["worst_fold_return"],
                    "loo_hard_gate_pass_count": best[
                        "loo_hard_gate_pass_count"
                    ],
                    "loo_survival_pass_count": best[
                        "loo_survival_pass_count"
                    ],
                    "min_loo_profit_factor": best["min_loo_profit_factor"],
                    "stability_pass": best["stability_pass"],
                },
                "oos_revealed": False,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
