from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from audit_hype_15m_factors import VALIDATION_END_EXCLUSIVE
from audit_hype_lgbm_round2_prefit import (
    SEEDS,
    WALK_FORWARD_FOLDS,
    fold_predictions,
    relaxed_fold_pass,
)
from backtest_hype_lgbm import run_prediction_backtest, summarize_trades
from hype_ml_common import ARTIFACTS_DIR, TripleBarrierConfig, add_triple_barrier_labels, write_json
from refine_hype_lgbm_round2 import apply_regime, regime_thresholds
from search_hype_lgbm_crossfold import joint_score
from search_hype_lgbm_crossfold_broad import REGIMES, thresholds
from search_hype_lgbm_round2 import base_backtest_config, gate_pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search four-seed LightGBM ensembles on the broad crossfold frontier."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--frontier",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_crossfold_broad/identity_frontier.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_crossfold_ensemble",
    )
    parser.add_argument("--top", type=int, default=6)
    return parser.parse_args()


def label_from_row(row: dict[str, Any]) -> TripleBarrierConfig:
    return TripleBarrierConfig(**row["label_config"])


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frontier = json.loads(args.frontier.read_text(encoding="utf-8"))
    frontier.sort(
        key=lambda row: (bool(row["crossfold_pass"]), float(row["joint_score"])),
        reverse=True,
    )
    selected = frontier[: args.top]
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos_rows = int((frame["ts"] >= VALIDATION_END_EXCLUSIVE).sum())
    if oos_rows <= 0:
        raise RuntimeError("sealed OOS is absent")
    del frame

    rows: list[dict[str, Any]] = []
    for identity_number, identity in enumerate(selected, start=1):
        label = label_from_row(identity)
        labeled = add_triple_barrier_labels(pre_oos, label)
        features = list(identity["features"])
        spec = {**identity["model_spec"], "ensemble_seeds": list(SEEDS)}
        folds: list[dict[str, Any]] = []
        for fold_id, train_end_text, test_end_text in WALK_FORWARD_FOLDS:
            train_end = pd.Timestamp(train_end_text)
            test_end = pd.Timestamp(test_end_text)
            predictions, predictive_metrics = fold_predictions(
                pre_oos,
                labeled,
                train_end=train_end,
                test_end=test_end,
                label=label,
                features=features,
                spec=spec,
                regime="none",
                seed=42,
            )
            train = labeled.loc[
                (labeled["ts"] < train_end)
                & labeled["long_exit_ts"].lt(train_end)
                & labeled["short_exit_ts"].lt(train_end)
            ].copy()
            folds.append(
                {
                    "fold_id": fold_id,
                    "predictions": predictions,
                    "regime_thresholds": regime_thresholds(train),
                    "predictive_metrics": predictive_metrics,
                }
            )
        for regime in REGIMES:
            regime_folds = [
                {
                    **fold,
                    "predictions": apply_regime(
                        fold["predictions"],
                        model_type=str(spec["model_type"]),
                        regime=regime,
                        thresholds=fold["regime_thresholds"],
                        horizon_bars=label.horizon_bars,
                    ),
                }
                for fold in folds
            ]
            for raw_threshold in thresholds():
                direction_policy = str(raw_threshold["direction_policy"])
                threshold = {
                    key: float(value)
                    for key, value in raw_threshold.items()
                    if key != "direction_policy"
                }
                risk = {"risk_per_trade": None, "max_leverage": 1.0}
                config = base_backtest_config(
                    label, str(spec["model_type"]), threshold, risk
                )
                fold_metrics: list[dict[str, Any]] = []
                all_trades: list[dict[str, Any]] = []
                prediction_frames: list[pd.DataFrame] = []
                for fold in regime_folds:
                    trades, metrics = run_prediction_backtest(
                        fold["predictions"], config
                    )
                    fold_metrics.append(
                        {
                            "fold_id": fold["fold_id"],
                            "metrics": metrics,
                            "relaxed_fold_pass": relaxed_fold_pass(metrics),
                        }
                    )
                    all_trades.extend(trades.to_dict("records"))
                    prediction_frames.append(fold["predictions"])
                combined = summarize_trades(
                    all_trades, pd.concat(prediction_frames), config
                )
                positive_count = sum(
                    float(item["metrics"]["total_return"]) > 0.0
                    for item in fold_metrics
                )
                relaxed_count = sum(
                    bool(item["relaxed_fold_pass"]) for item in fold_metrics
                )
                worst_return = min(
                    float(item["metrics"]["total_return"])
                    for item in fold_metrics
                )
                crossfold_pass = bool(
                    gate_pass(combined)
                    and positive_count >= 3
                    and relaxed_count >= 2
                    and worst_return > -0.15
                )
                rows.append(
                    {
                        "source_identity_rank": identity_number,
                        "label_id": identity["label_id"],
                        "label_config": identity["label_config"],
                        "feature_set_id": identity["feature_set_id"],
                        "features": features,
                        "model_spec": spec,
                        "regime": regime,
                        "direction_policy": direction_policy,
                        "threshold": threshold,
                        "risk": risk,
                        "metrics": combined,
                        "fold_metrics": fold_metrics,
                        "positive_fold_count": positive_count,
                        "relaxed_fold_pass_count": relaxed_count,
                        "worst_fold_return": worst_return,
                        "crossfold_pass": crossfold_pass,
                        "joint_score": joint_score(
                            combined,
                            positive_fold_count=positive_count,
                            relaxed_fold_pass_count=relaxed_count,
                            worst_fold_return=worst_return,
                        ),
                    }
                )
        print(
            f"ensemble crossfold {identity_number}/{len(selected)} "
            f"{spec['id']}",
            flush=True,
        )

    best = max(
        rows,
        key=lambda row: (bool(row["crossfold_pass"]), float(row["joint_score"])),
    )
    frozen_candidate = {
        **best,
        "gate_pass": bool(best["crossfold_pass"]),
        "selection_score": best["joint_score"],
        "selection_scope": "four-seed ensemble on five pre-OOS folds",
    }
    frozen_candidate.pop("crossfold_pass")
    pd.json_normalize(
        [{key: value for key, value in row.items() if key != "fold_metrics"} for row in rows]
    ).to_parquet(args.output_dir / "ensemble_trials.parquet", index=False)
    write_json(
        args.output_dir / "ensemble_summary.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "source_identity_count": len(selected),
            "trial_count": len(rows),
            "crossfold_pass_count": sum(
                bool(row["crossfold_pass"]) for row in rows
            ),
            "best": best,
            "oos_rows_present_but_not_loaded": oos_rows,
            "oos_revealed": False,
        },
    )
    write_json(
        args.output_dir / "prefit_candidate_ensemble.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "candidate": frozen_candidate,
            "validation_gate_pass": bool(best["crossfold_pass"]),
            "oos_revealed": False,
        },
    )
    print(
        json.dumps(
            {
                "source_identity_count": len(selected),
                "trial_count": len(rows),
                "crossfold_pass_count": sum(
                    bool(row["crossfold_pass"]) for row in rows
                ),
                "best": {
                    "label_id": best["label_id"],
                    "feature_set_id": best["feature_set_id"],
                    "model": best["model_spec"]["id"],
                    "ensemble_seeds": best["model_spec"]["ensemble_seeds"],
                    "regime": best["regime"],
                    "direction_policy": best["direction_policy"],
                    "threshold": best["threshold"],
                    "metrics": best["metrics"],
                    "positive_fold_count": best["positive_fold_count"],
                    "relaxed_fold_pass_count": best[
                        "relaxed_fold_pass_count"
                    ],
                    "worst_fold_return": best["worst_fold_return"],
                },
                "oos_revealed": False,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
