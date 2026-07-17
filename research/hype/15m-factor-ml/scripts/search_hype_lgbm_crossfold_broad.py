from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from audit_hype_15m_factors import VALIDATION_END_EXCLUSIVE
from audit_hype_lgbm_round2_prefit import (
    WALK_FORWARD_FOLDS,
    fold_predictions,
    relaxed_fold_pass,
)
from backtest_hype_lgbm import run_prediction_backtest, summarize_trades
from hype_ml_common import ARTIFACTS_DIR, TripleBarrierConfig, add_triple_barrier_labels, write_json
from refine_hype_lgbm_round2 import apply_regime, regime_thresholds
from search_hype_lgbm_crossfold import joint_score
from search_hype_lgbm_round2 import (
    base_backtest_config,
    feature_sets,
    gate_pass,
    model_specs,
)


REGIMES = ("none", "low_vol", "trend_follow", "low_vol_trend_follow")
LABELS = (
    TripleBarrierConfig(horizon_bars=12, take_profit_atr=1.0, stop_loss_atr=1.0),
    TripleBarrierConfig(horizon_bars=24, take_profit_atr=1.0, stop_loss_atr=1.5),
    TripleBarrierConfig(horizon_bars=48, take_profit_atr=1.0, stop_loss_atr=2.0),
)
MODEL_IDS = {
    "dual_binary_compact",
    "dual_binary_shallow",
    "dual_binary_regularized",
    "dual_binary_weighted_compact",
    "dual_binary_weighted_shallow",
    "dual_binary_weighted_regularized",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad regularized LightGBM search on five pre-OOS folds."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--factor-audit",
        type=Path,
        default=ARTIFACTS_DIR / "factor_audit_round2/factor_audit_summary.json",
    )
    parser.add_argument(
        "--single-factor-audit",
        type=Path,
        default=ARTIFACTS_DIR / "factor_audit_round2/single_factor_train_audit.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_crossfold_broad",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def label_id(label: TripleBarrierConfig) -> str:
    return (
        f"h{label.horizon_bars}_tp{label.take_profit_atr:.2f}"
        f"_sl{label.stop_loss_atr:.2f}"
    )


def thresholds() -> list[dict[str, Any]]:
    levels = np.arange(0.45, 0.851, 0.05).round(3).tolist()
    long_only = [
        {
            "direction_policy": "long_only",
            "long_threshold": level,
            "short_threshold": 1.0,
            "probability_margin": margin,
        }
        for level in levels
        for margin in (0.0, 0.08)
    ]
    short_only = [
        {
            "direction_policy": "short_only",
            "long_threshold": 1.0,
            "short_threshold": level,
            "probability_margin": margin,
        }
        for level in (0.60, 0.70, 0.80)
        for margin in (0.0, 0.08)
    ]
    both = [
        {
            "direction_policy": "both",
            "long_threshold": long_level,
            "short_threshold": short_level,
            "probability_margin": margin,
        }
        for long_level in (0.55, 0.65, 0.75, 0.85)
        for short_level in (0.55, 0.65, 0.75, 0.85)
        for margin in (0.0, 0.08)
    ]
    return long_only + short_only + both


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos_rows = int((frame["ts"] >= VALIDATION_END_EXCLUSIVE).sum())
    if oos_rows <= 0:
        raise RuntimeError("sealed OOS is absent")
    del frame

    audit = json.loads(args.factor_audit.read_text(encoding="utf-8"))
    stats = pd.read_csv(args.single_factor_audit)
    available_sets = feature_sets(audit, stats)
    selected_sets = {
        name: available_sets[name] for name in ("top30_ic", "top60_ic")
    }
    specs = [spec for spec in model_specs(2) if spec["id"] in MODEL_IDS]
    for spec in specs:
        spec["n_estimators"] = 700

    all_rows: list[dict[str, Any]] = []
    identity_summaries: list[dict[str, Any]] = []
    identity_count = len(LABELS) * len(selected_sets) * len(specs)
    identity_number = 0
    for label in LABELS:
        labeled = add_triple_barrier_labels(pre_oos, label)
        for feature_set_id, features in selected_sets.items():
            for spec in specs:
                identity_number += 1
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
                        seed=args.seed,
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

                identity_best: dict[str, Any] | None = None
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
                        config = base_backtest_config(
                            label,
                            str(spec["model_type"]),
                            threshold,
                            {"risk_per_trade": None, "max_leverage": 1.0},
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
                            bool(item["relaxed_fold_pass"])
                            for item in fold_metrics
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
                        row = {
                            "label_id": label_id(label),
                            "label_config": asdict(label),
                            "feature_set_id": feature_set_id,
                            "features": features,
                            "model_spec": spec,
                            "regime": regime,
                            "direction_policy": direction_policy,
                            "threshold": threshold,
                            "risk": {"risk_per_trade": None, "max_leverage": 1.0},
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
                        all_rows.append(row)
                        if identity_best is None or (
                            bool(row["crossfold_pass"]), row["joint_score"]
                        ) > (
                            bool(identity_best["crossfold_pass"]),
                            identity_best["joint_score"],
                        ):
                            identity_best = row
                if identity_best is None:
                    raise RuntimeError("identity search generated no trials")
                identity_summaries.append(identity_best)
                print(
                    f"broad crossfold {identity_number}/{identity_count} "
                    f"{label_id(label)} {feature_set_id} {spec['id']}",
                    flush=True,
                )

    best = max(
        all_rows,
        key=lambda item: (bool(item["crossfold_pass"]), float(item["joint_score"])),
    )
    frozen_candidate = {
        **best,
        "gate_pass": bool(best["crossfold_pass"]),
        "selection_score": best["joint_score"],
        "selection_scope": "broad five-fold pre-OOS joint search",
    }
    frozen_candidate.pop("crossfold_pass")
    summary_rows = [
        {key: value for key, value in row.items() if key != "fold_metrics"}
        for row in all_rows
    ]
    pd.json_normalize(summary_rows).to_parquet(
        args.output_dir / "crossfold_trials.parquet", index=False
    )
    write_json(args.output_dir / "identity_frontier.json", identity_summaries)
    write_json(
        args.output_dir / "crossfold_summary.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "identity_count": identity_count,
            "trial_count": len(all_rows),
            "crossfold_pass_count": sum(
                bool(row["crossfold_pass"]) for row in all_rows
            ),
            "best": best,
            "oos_rows_present_but_not_loaded": oos_rows,
            "oos_revealed": False,
            "status": (
                "broad crossfold candidate found"
                if best["crossfold_pass"]
                else "HARD-GATE-FAILED in broad crossfold search"
            ),
        },
    )
    write_json(
        args.output_dir / "prefit_candidate_crossfold_broad.json",
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
                "identity_count": identity_count,
                "trial_count": len(all_rows),
                "crossfold_pass_count": sum(
                    bool(row["crossfold_pass"]) for row in all_rows
                ),
                "best": {
                    "label_id": best["label_id"],
                    "feature_set_id": best["feature_set_id"],
                    "model": best["model_spec"]["id"],
                    "regime": best["regime"],
                    "direction_policy": best["direction_policy"],
                    "threshold": best["threshold"],
                    "metrics": best["metrics"],
                    "positive_fold_count": best["positive_fold_count"],
                    "relaxed_fold_pass_count": best[
                        "relaxed_fold_pass_count"
                    ],
                    "worst_fold_return": best["worst_fold_return"],
                    "joint_score": best["joint_score"],
                },
                "oos_revealed": False,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
