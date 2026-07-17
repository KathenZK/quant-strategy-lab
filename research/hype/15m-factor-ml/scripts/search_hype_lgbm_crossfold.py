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
    label_from_candidate,
    relaxed_fold_pass,
)
from backtest_hype_lgbm import run_prediction_backtest, summarize_trades
from hype_ml_common import ARTIFACTS_DIR, add_triple_barrier_labels, write_json
from refine_hype_lgbm_round2 import apply_regime, regime_thresholds
from search_hype_lgbm_round2 import base_backtest_config, gate_pass, score_metrics


DEFAULT_CANDIDATES = (
    ARTIFACTS_DIR
    / "model_round2_expanded_refinement/prefit_candidate_refined.json",
    ARTIFACTS_DIR
    / "model_round2_prefit_candidates/dual_binary_weighted_medium.json",
    ARTIFACTS_DIR
    / "model_round2_prefit_candidates/dual_binary_shallow.json",
    ARTIFACTS_DIR
    / "model_round2_prefit_candidates/dual_regression_shallow.json",
)
REGIMES = ("none", "low_vol", "trend_follow", "low_vol_trend_follow")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Jointly search frozen HYPE model families across five pre-OOS folds."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument("--candidate", action="append", type=Path, default=[])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_crossfold_search",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def load_candidate(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("oos_revealed") is not False:
        raise RuntimeError(f"candidate does not prove sealed OOS: {path}")
    result = payload["candidate"]
    result["candidate_source"] = str(path)
    return result


def probability_thresholds() -> list[dict[str, Any]]:
    directional = np.arange(0.40, 0.851, 0.05).round(3).tolist()
    long_only = [
        {
            "direction_policy": "long_only",
            "long_threshold": threshold,
            "short_threshold": 1.0,
            "probability_margin": margin,
        }
        for threshold in directional
        for margin in (0.0, 0.05, 0.10)
    ]
    short_only = [
        {
            "direction_policy": "short_only",
            "long_threshold": 1.0,
            "short_threshold": threshold,
            "probability_margin": margin,
        }
        for threshold in directional
        for margin in (0.0, 0.05, 0.10)
    ]
    both = [
        {
            "direction_policy": "both",
            "long_threshold": long_threshold,
            "short_threshold": short_threshold,
            "probability_margin": margin,
        }
        for long_threshold in (0.50, 0.60, 0.70, 0.80)
        for short_threshold in (0.50, 0.60, 0.70, 0.80)
        for margin in (0.0, 0.08)
    ]
    return long_only + short_only + both


def regression_thresholds() -> list[dict[str, Any]]:
    edges = (-20.0, 0.0, 20.0, 40.0, 80.0, 120.0)
    long_only = [
        {
            "direction_policy": "long_only",
            "long_edge_threshold_bps": edge,
            "short_edge_threshold_bps": 1e12,
            "edge_margin_bps": margin,
        }
        for edge in edges
        for margin in (0.0, 20.0, 40.0)
    ]
    short_only = [
        {
            "direction_policy": "short_only",
            "long_edge_threshold_bps": 1e12,
            "short_edge_threshold_bps": edge,
            "edge_margin_bps": margin,
        }
        for edge in edges
        for margin in (0.0, 20.0, 40.0)
    ]
    both = [
        {
            "direction_policy": "both",
            "long_edge_threshold_bps": long_edge,
            "short_edge_threshold_bps": short_edge,
            "edge_margin_bps": margin,
        }
        for long_edge in (0.0, 40.0, 80.0)
        for short_edge in (0.0, 40.0, 80.0)
        for margin in (0.0, 20.0, 40.0)
    ]
    return long_only + short_only + both


def clean_threshold(values: dict[str, Any]) -> tuple[str, dict[str, float]]:
    policy = str(values["direction_policy"])
    return policy, {
        key: float(value)
        for key, value in values.items()
        if key != "direction_policy"
    }


def joint_score(
    metrics: dict[str, Any],
    *,
    positive_fold_count: int,
    relaxed_fold_pass_count: int,
    worst_fold_return: float,
) -> float:
    base = score_metrics(metrics)
    stability = (
        0.30 * positive_fold_count
        + 0.50 * relaxed_fold_pass_count
        + 2.0 * min(worst_fold_return, 0.0)
    )
    return float(base + stability)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_paths = tuple(args.candidate) or DEFAULT_CANDIDATES
    candidates = [load_candidate(path) for path in candidate_paths]
    identities: set[tuple[str, str, str]] = set()
    unique_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        identity = (
            str(candidate["label_id"]),
            str(candidate["feature_set_id"]),
            str(candidate["model_spec"]["id"]),
        )
        if identity not in identities:
            identities.add(identity)
            unique_candidates.append(candidate)

    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos_rows = int((frame["ts"] >= VALIDATION_END_EXCLUSIVE).sum())
    if oos_rows <= 0:
        raise RuntimeError("sealed OOS is absent from the source dataset")
    del frame

    rows: list[dict[str, Any]] = []
    model_diagnostics: list[dict[str, Any]] = []
    for candidate_number, candidate in enumerate(unique_candidates, start=1):
        label = label_from_candidate(candidate)
        labeled = add_triple_barrier_labels(pre_oos, label)
        features = list(candidate["features"])
        spec = dict(candidate["model_spec"])
        model_type = str(spec["model_type"])
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
                    "train_end": train_end,
                    "test_end": test_end,
                    "predictions": predictions,
                    "regime_thresholds": regime_thresholds(train),
                    "predictive_metrics": predictive_metrics,
                }
            )
        thresholds = (
            regression_thresholds()
            if model_type.startswith("dual_regression")
            else probability_thresholds()
        )
        for regime in REGIMES:
            regime_folds = [
                {
                    **fold,
                    "predictions": apply_regime(
                        fold["predictions"],
                        model_type=model_type,
                        regime=regime,
                        thresholds=fold["regime_thresholds"],
                        horizon_bars=label.horizon_bars,
                    ),
                }
                for fold in folds
            ]
            for raw_threshold in thresholds:
                direction_policy, threshold = clean_threshold(raw_threshold)
                config = base_backtest_config(
                    label,
                    model_type,
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
                        "candidate_number": candidate_number,
                        "label_id": candidate["label_id"],
                        "feature_set_id": candidate["feature_set_id"],
                        "model_spec": spec,
                        "features": features,
                        "regime": regime,
                        "direction_policy": direction_policy,
                        "threshold": threshold,
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
        model_diagnostics.append(
            {
                "candidate_number": candidate_number,
                "identity": list(next(identity for identity in identities if identity[0] == candidate["label_id"] and identity[1] == candidate["feature_set_id"] and identity[2] == candidate["model_spec"]["id"])),
                "fold_predictive_metrics": [
                    {
                        "fold_id": fold["fold_id"],
                        "metrics": fold["predictive_metrics"],
                    }
                    for fold in folds
                ],
            }
        )
        print(
            f"crossfold search complete {candidate_number}/{len(unique_candidates)} "
            f"{spec['id']}",
            flush=True,
        )

    if not rows:
        raise RuntimeError("crossfold search generated no rows")
    best = max(
        rows,
        key=lambda item: (bool(item["crossfold_pass"]), float(item["joint_score"])),
    )
    source_candidate = unique_candidates[int(best["candidate_number"]) - 1]
    frozen_candidate = {
        "label_id": best["label_id"],
        "label_config": asdict(label_from_candidate(source_candidate)),
        "feature_set_id": best["feature_set_id"],
        "features": best["features"],
        "model_spec": best["model_spec"],
        "predictive_metrics": {},
        "regime": best["regime"],
        "regime_thresholds": {},
        "direction_policy": best["direction_policy"],
        "threshold": best["threshold"],
        "risk": {"risk_per_trade": None, "max_leverage": 1.0},
        "metrics": best["metrics"],
        "fold_metrics": best["fold_metrics"],
        "positive_fold_count": best["positive_fold_count"],
        "relaxed_fold_pass_count": best["relaxed_fold_pass_count"],
        "worst_fold_return": best["worst_fold_return"],
        "selection_score": best["joint_score"],
        "gate_pass": best["crossfold_pass"],
        "selection_scope": "five pre-OOS walk-forward folds",
    }
    normalized = pd.json_normalize(
        [{key: value for key, value in row.items() if key != "fold_metrics"} for row in rows]
    )
    normalized.to_csv(args.output_dir / "crossfold_trials.csv", index=False)
    write_json(args.output_dir / "model_diagnostics.json", model_diagnostics)
    summary = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "candidate_count": len(unique_candidates),
        "trial_count": len(rows),
        "crossfold_pass_count": sum(bool(row["crossfold_pass"]) for row in rows),
        "best": best,
        "oos_rows_present_but_not_loaded": oos_rows,
        "oos_revealed": False,
        "status": (
            "crossfold candidate found"
            if best["crossfold_pass"]
            else "HARD-GATE-FAILED in crossfold search"
        ),
    }
    write_json(args.output_dir / "crossfold_summary.json", summary)
    write_json(
        args.output_dir / "prefit_candidate_crossfold.json",
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
                "trial_count": len(rows),
                "crossfold_pass_count": summary["crossfold_pass_count"],
                "best": {
                    "model": best["model_spec"]["id"],
                    "label": best["label_id"],
                    "regime": best["regime"],
                    "direction_policy": best["direction_policy"],
                    "threshold": best["threshold"],
                    "positive_fold_count": best["positive_fold_count"],
                    "relaxed_fold_pass_count": best["relaxed_fold_pass_count"],
                    "worst_fold_return": best["worst_fold_return"],
                    "metrics": best["metrics"],
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
