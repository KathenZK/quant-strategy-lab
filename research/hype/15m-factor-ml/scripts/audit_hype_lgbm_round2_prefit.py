from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from audit_hype_15m_factors import TRAIN_END_EXCLUSIVE, VALIDATION_END_EXCLUSIVE
from backtest_hype_lgbm import run_prediction_backtest, summarize_trades
from hype_ml_common import (
    ARTIFACTS_DIR,
    TripleBarrierConfig,
    add_triple_barrier_labels,
    write_json,
)
from refine_hype_lgbm_round2 import apply_regime, regime_thresholds
from search_hype_lgbm_round2 import (
    base_backtest_config,
    gate_pass,
    prepare_label_frame,
    train_and_predict,
)


SEEDS = (7, 17, 29, 42)
WALK_FORWARD_FOLDS = (
    ("wf1", "2025-09-01T00:00:00Z", "2025-10-15T00:00:00Z"),
    ("wf2", "2025-10-15T00:00:00Z", "2025-12-01T00:00:00Z"),
    ("wf3", "2025-12-01T00:00:00Z", "2026-01-15T00:00:00Z"),
    ("wf4", "2026-01-15T00:00:00Z", "2026-03-01T00:00:00Z"),
    ("wf5", "2026-03-01T00:00:00Z", "2026-04-17T00:00:00Z"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a frozen HYPE Round 2 candidate before revealing OOS."
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
            / "model_round2_expanded_refinement/prefit_candidate_refined.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_prefit_robustness",
    )
    parser.add_argument(
        "--disable-short",
        action="store_true",
        help="Audit an explicit long-only variant without changing model training.",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("oos_revealed") is not False:
        raise RuntimeError("candidate does not prove that OOS is still sealed")
    candidate = payload["candidate"]
    if not bool(candidate.get("gate_pass")):
        raise RuntimeError("candidate did not pass the validation gate")
    return candidate


def label_from_candidate(candidate: dict[str, Any]) -> TripleBarrierConfig:
    return TripleBarrierConfig(**candidate["label_config"])


def threshold_from_candidate(candidate: dict[str, Any]) -> dict[str, float]:
    return {
        key: float(value)
        for key, value in candidate["threshold"].items()
        if value is not None
    }


def risk_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in candidate["risk"].items()
        if value is not None
    }


def prediction_columns(model_type: str) -> list[str]:
    if model_type.startswith("dual_regression"):
        return ["pred_long_bps", "pred_short_bps"]
    return ["p_long", "p_short"]


def purge_tail(
    predictions: pd.DataFrame, *, model_type: str, horizon_bars: int
) -> pd.DataFrame:
    result = predictions.copy()
    result.loc[
        result.index[-horizon_bars:], prediction_columns(model_type)
    ] = np.nan
    return result


def validation_predictions(
    pre_oos: pd.DataFrame,
    *,
    label: TripleBarrierConfig,
    features: list[str],
    spec: dict[str, Any],
    seed: int,
    regime: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    train, validation_labeled, _ = prepare_label_frame(pre_oos, label)
    validation_full = pre_oos.loc[
        (pre_oos["ts"] >= TRAIN_END_EXCLUSIVE)
        & (pre_oos["ts"] < VALIDATION_END_EXCLUSIVE)
    ].copy()
    validation_model = validation_full.merge(
        validation_labeled[
            ["ts", "direction_label", "long_outcome_bps", "short_outcome_bps"]
        ],
        on="ts",
        how="inner",
        validate="one_to_one",
    )
    predictions, predictive_metrics = train_predict_maybe_ensemble(
        train,
        validation_model,
        features=features,
        spec=spec,
        horizon_bars=label.horizon_bars,
        fallback_seed=seed,
    )
    regime_columns = [
        "atr_percentile_672",
        "efficiency_ratio_48",
        "trend_strength_21_55",
    ]
    predictions = predictions.merge(
        validation_full[["ts", *regime_columns]],
        on="ts",
        how="left",
        validate="one_to_one",
    )
    predictions = apply_regime(
        predictions,
        model_type=str(spec["model_type"]),
        regime=regime,
        thresholds=regime_thresholds(train),
        horizon_bars=label.horizon_bars,
    )
    return predictions, predictive_metrics


def fold_predictions(
    pre_oos: pd.DataFrame,
    labeled: pd.DataFrame,
    *,
    train_end: pd.Timestamp,
    test_end: pd.Timestamp,
    label: TripleBarrierConfig,
    features: list[str],
    spec: dict[str, Any],
    regime: str,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    train = labeled.loc[
        (labeled["ts"] < train_end)
        & labeled["long_exit_ts"].lt(train_end)
        & labeled["short_exit_ts"].lt(train_end)
        & labeled["long_outcome_bps"].notna()
        & labeled["short_outcome_bps"].notna()
    ].copy()
    test_labeled = labeled.loc[
        (labeled["ts"] >= train_end)
        & (labeled["ts"] < test_end)
        & labeled["long_exit_ts"].lt(test_end)
        & labeled["short_exit_ts"].lt(test_end)
        & labeled["long_outcome_bps"].notna()
        & labeled["short_outcome_bps"].notna()
    ].copy()
    test_full = pre_oos.loc[
        (pre_oos["ts"] >= train_end) & (pre_oos["ts"] < test_end)
    ].copy()
    test_model = test_full.merge(
        test_labeled[
            ["ts", "direction_label", "long_outcome_bps", "short_outcome_bps"]
        ],
        on="ts",
        how="inner",
        validate="one_to_one",
    )
    predictions, predictive_metrics = train_predict_maybe_ensemble(
        train.reset_index(drop=True),
        test_model.reset_index(drop=True),
        features=features,
        spec=spec,
        horizon_bars=label.horizon_bars,
        fallback_seed=seed,
    )
    regime_columns = [
        "atr_percentile_672",
        "efficiency_ratio_48",
        "trend_strength_21_55",
    ]
    predictions = predictions.merge(
        test_full[["ts", *regime_columns]],
        on="ts",
        how="left",
        validate="one_to_one",
    )
    predictions = apply_regime(
        predictions,
        model_type=str(spec["model_type"]),
        regime=regime,
        thresholds=regime_thresholds(train),
        horizon_bars=label.horizon_bars,
    )
    return predictions, predictive_metrics


def train_predict_maybe_ensemble(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: list[str],
    spec: dict[str, Any],
    horizon_bars: int,
    fallback_seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    ensemble_seeds = [int(value) for value in spec.get("ensemble_seeds", [])]
    seeds = ensemble_seeds or [fallback_seed]
    prediction_frames: list[pd.DataFrame] = []
    member_metrics: list[dict[str, Any]] = []
    for member_seed in seeds:
        predictions, metrics = train_and_predict(
            train,
            validation,
            features=features,
            spec=spec,
            horizon_bars=horizon_bars,
            seed=member_seed,
        )
        prediction_frames.append(predictions)
        member_metrics.append({"seed": member_seed, "metrics": metrics})
    result = prediction_frames[0].copy()
    model_type = str(spec["model_type"])
    values = (
        ["pred_long_bps", "pred_short_bps"]
        if model_type.startswith("dual_regression")
        else ["p_long", "p_short", "p_flat"]
    )
    for column in values:
        result[column] = np.mean(
            [frame[column].to_numpy(dtype="float64") for frame in prediction_frames],
            axis=0,
        )
    return result, {
        "ensemble": bool(ensemble_seeds),
        "ensemble_seeds": seeds,
        "member_metrics": member_metrics,
    }


def neighborhood(candidate: dict[str, Any]) -> list[dict[str, float]]:
    model_type = str(candidate["model_spec"]["model_type"])
    base = threshold_from_candidate(candidate)
    if model_type.startswith("dual_regression"):
        long_base = float(base.get("long_edge_threshold_bps", 0.0))
        short_base = float(base.get("short_edge_threshold_bps", 0.0))
        margin_base = float(base.get("edge_margin_bps", 0.0))
        return [
            {
                "long_edge_threshold_bps": long_base + long_delta,
                "short_edge_threshold_bps": short_base + short_delta,
                "edge_margin_bps": max(0.0, margin_base + margin_delta),
            }
            for long_delta in (-10.0, 0.0, 10.0)
            for short_delta in (-10.0, 0.0, 10.0)
            for margin_delta in (0.0, 10.0)
        ]
    long_base = float(base["long_threshold"])
    short_base = float(base["short_threshold"])
    margin_base = float(base["probability_margin"])
    return [
        {
            "long_threshold": float(np.clip(long_base + long_delta, 0.01, 0.99)),
            "short_threshold": float(
                np.clip(short_base + short_delta, 0.01, 0.99)
            ),
            "probability_margin": float(
                np.clip(margin_base + margin_delta, 0.0, 0.50)
            ),
        }
        for long_delta in (-0.05, -0.025, 0.0, 0.025, 0.05)
        for short_delta in (-0.05, 0.0, 0.05)
        for margin_delta in (0.0, 0.03)
    ]


def relaxed_fold_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        int(metrics["trade_count"]) >= 8
        and float(metrics["total_return"]) > 0.0
        and float(metrics["win_rate"]) >= 0.55
        and float(metrics["max_drawdown"]) <= 0.20
        and float(metrics["profit_factor"]) >= 1.0
    )


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate = candidate_payload(args.candidate)
    candidate = json.loads(json.dumps(candidate))
    if args.disable_short:
        model_type = str(candidate["model_spec"]["model_type"])
        if model_type.startswith("dual_regression"):
            candidate["threshold"]["short_edge_threshold_bps"] = 1e12
        else:
            candidate["threshold"]["short_threshold"] = 1.0
        candidate["direction_policy"] = "long_only"
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos_rows = int((frame["ts"] >= VALIDATION_END_EXCLUSIVE).sum())
    if oos_rows <= 0:
        raise RuntimeError("source dataset does not contain the sealed OOS")
    del frame

    label = label_from_candidate(candidate)
    features = list(candidate["features"])
    spec = dict(candidate["model_spec"])
    regime = str(candidate["regime"])
    threshold = threshold_from_candidate(candidate)
    risk = risk_from_candidate(candidate)
    baseline_config = base_backtest_config(
        label, str(spec["model_type"]), threshold, risk
    )

    seed_rows: list[dict[str, Any]] = []
    ensemble_seeds = [int(value) for value in spec.get("ensemble_seeds", [])]
    audit_variants: list[tuple[str, int, dict[str, Any]]] = []
    if ensemble_seeds:
        for held_out_seed in ensemble_seeds:
            variant_spec = {
                **spec,
                "ensemble_seeds": [
                    seed for seed in ensemble_seeds if seed != held_out_seed
                ],
            }
            audit_variants.append(
                (f"leave_out_{held_out_seed}", held_out_seed, variant_spec)
            )
    else:
        audit_variants = [(f"seed_{seed}", seed, spec) for seed in SEEDS]
    for variant_id, seed, variant_spec in audit_variants:
        predictions, predictive_metrics = validation_predictions(
            pre_oos,
            label=label,
            features=features,
            spec=variant_spec,
            seed=seed,
            regime=regime,
        )
        trades, metrics = run_prediction_backtest(predictions, baseline_config)
        seed_rows.append(
            {
                "variant_id": variant_id,
                "seed": seed,
                "ensemble_seeds": variant_spec.get("ensemble_seeds", []),
                "predictive_metrics": predictive_metrics,
                "metrics": metrics,
                "hard_gate_pass": gate_pass(metrics),
            }
        )
        print(f"seed audit complete {seed}", flush=True)

    baseline_predictions, _ = validation_predictions(
        pre_oos,
        label=label,
        features=features,
        spec=spec,
        seed=42,
        regime=regime,
    )
    baseline_trades, _ = run_prediction_backtest(
        baseline_predictions, baseline_config
    )
    baseline_trades.to_parquet(args.output_dir / "validation_trades_baseline.parquet")

    cost_rows: list[dict[str, Any]] = []
    for slippage_bps in (4.0, 8.0, 12.0):
        stressed_label = TripleBarrierConfig(
            **{
                **asdict(label),
                "slippage_bps_per_fill": slippage_bps,
            }
        )
        config = base_backtest_config(
            stressed_label, str(spec["model_type"]), threshold, risk
        )
        _, metrics = run_prediction_backtest(baseline_predictions, config)
        cost_rows.append(
            {
                "fee_rate_per_fill": stressed_label.fee_rate_per_fill,
                "slippage_bps_per_fill": slippage_bps,
                "metrics": metrics,
                "hard_gate_pass": gate_pass(metrics),
            }
        )

    neighborhood_rows: list[dict[str, Any]] = []
    for nearby_threshold in neighborhood(candidate):
        config = base_backtest_config(
            label, str(spec["model_type"]), nearby_threshold, risk
        )
        _, metrics = run_prediction_backtest(baseline_predictions, config)
        neighborhood_rows.append(
            {
                "threshold": nearby_threshold,
                "metrics": metrics,
                "hard_gate_pass": gate_pass(metrics),
            }
        )

    labeled = add_triple_barrier_labels(pre_oos, label)
    fold_rows: list[dict[str, Any]] = []
    all_fold_trades: list[dict[str, Any]] = []
    fold_frames: list[pd.DataFrame] = []
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
            regime=regime,
            seed=42,
        )
        trades, metrics = run_prediction_backtest(predictions, baseline_config)
        fold_frames.append(predictions)
        all_fold_trades.extend(trades.to_dict("records"))
        fold_rows.append(
            {
                "fold_id": fold_id,
                "train_end_exclusive": train_end,
                "test_end_exclusive": test_end,
                "predictive_metrics": predictive_metrics,
                "metrics": metrics,
                "relaxed_fold_pass": relaxed_fold_pass(metrics),
            }
        )
        print(f"walk-forward complete {fold_id}", flush=True)

    combined_frame = pd.concat(fold_frames, ignore_index=True)
    combined_metrics = summarize_trades(
        all_fold_trades, combined_frame, baseline_config
    )
    combined_gate_pass = gate_pass(combined_metrics)

    seed_pass_count = sum(bool(row["hard_gate_pass"]) for row in seed_rows)
    neighbor_pass_count = sum(
        bool(row["hard_gate_pass"]) for row in neighborhood_rows
    )
    fold_pass_count = sum(bool(row["relaxed_fold_pass"]) for row in fold_rows)
    active_fold_count = sum(
        int(row["metrics"]["trade_count"]) > 0 for row in fold_rows
    )
    nonnegative_fold_count = sum(
        float(row["metrics"]["total_return"]) >= 0.0 for row in fold_rows
    )
    strict_fold_gate = fold_pass_count >= 3
    sparse_coverage_gate = bool(
        fold_pass_count >= 2
        and active_fold_count >= 3
        and nonnegative_fold_count == len(fold_rows)
    )
    cost_8 = next(
        row for row in cost_rows if row["slippage_bps_per_fill"] == 8.0
    )["metrics"]
    cost_12 = next(
        row for row in cost_rows if row["slippage_bps_per_fill"] == 12.0
    )["metrics"]
    prefit_checks = {
        "seed_gate": seed_pass_count >= 3,
        "threshold_neighborhood_gate": (
            neighbor_pass_count / max(len(neighborhood_rows), 1) >= 0.50
        ),
        "walk_forward_aggregate_gate": combined_gate_pass,
        "walk_forward_fold_or_sparse_coverage_gate": (
            strict_fold_gate or sparse_coverage_gate
        ),
        "cost_8bps_gate": bool(
            cost_8["total_return"] > 0.0
            and cost_8["win_rate"] >= 0.55
            and cost_8["max_drawdown"] <= 0.20
            and cost_8["profit_factor"] >= 1.15
        ),
        "cost_12bps_survival_gate": bool(
            cost_12["total_return"] > 0.0
            and cost_12["max_drawdown"] <= 0.20
            and cost_12["profit_factor"] >= 1.0
        ),
    }
    prefit_pass = all(prefit_checks.values())
    payload = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "selection_scope": "pre-OOS only",
        "candidate_source": str(args.candidate),
        "candidate_sha256": file_sha256(args.candidate),
        "candidate_variant": "long_only" if args.disable_short else "as_selected",
        "dataset_source": str(args.input),
        "dataset_sha256": file_sha256(args.input),
        "factor_count": len(features),
        "candidate": candidate,
        "oos_rows_present_but_not_loaded_into_any_selection_or_audit_frame": oos_rows,
        "oos_revealed": False,
        "seed_audit": seed_rows,
        "seed_gate_pass_count": seed_pass_count,
        "cost_stress": cost_rows,
        "threshold_neighborhood": neighborhood_rows,
        "threshold_neighborhood_pass_count": neighbor_pass_count,
        "walk_forward": fold_rows,
        "walk_forward_relaxed_pass_count": fold_pass_count,
        "walk_forward_active_fold_count": active_fold_count,
        "walk_forward_nonnegative_fold_count": nonnegative_fold_count,
        "walk_forward_strict_fold_gate": strict_fold_gate,
        "walk_forward_sparse_coverage_gate": sparse_coverage_gate,
        "walk_forward_combined_metrics": combined_metrics,
        "walk_forward_combined_hard_gate_pass": combined_gate_pass,
        "prefit_checks": prefit_checks,
        "prefit_pass": prefit_pass,
        "status": (
            "frozen prefit candidate; eligible for one-time OOS reveal"
            if prefit_pass
            else "prefit robustness failed; OOS remains sealed"
        ),
        "notes": [
            "Walk-forward folds are post-selection diagnostics, not a substitute for the locked OOS.",
            "No OOS target, prediction, trade, or performance metric was read by this script.",
        ],
    }
    write_json(args.output_dir / "prefit_robustness.json", payload)
    write_json(
        args.output_dir / "frozen_candidate.json",
        {
            "family": "HYPE-15M-Factor-ML",
            "round": 2,
            "candidate": candidate,
            "candidate_source_sha256": file_sha256(args.candidate),
            "candidate_variant": "long_only" if args.disable_short else "as_selected",
            "prefit_robustness_sha256": file_sha256(
                args.output_dir / "prefit_robustness.json"
            ),
            "prefit_pass": prefit_pass,
            "oos_revealed": False,
        },
    )
    pd.json_normalize(seed_rows).to_csv(args.output_dir / "seed_audit.csv", index=False)
    pd.json_normalize(cost_rows).to_csv(args.output_dir / "cost_stress.csv", index=False)
    pd.json_normalize(neighborhood_rows).to_csv(
        args.output_dir / "threshold_neighborhood.csv", index=False
    )
    pd.json_normalize(fold_rows).to_csv(
        args.output_dir / "walk_forward.csv", index=False
    )
    print(
        json.dumps(
            {
                "prefit_pass": prefit_pass,
                "prefit_checks": prefit_checks,
                "seed_gate_pass_count": seed_pass_count,
                "threshold_neighborhood_pass_count": neighbor_pass_count,
                "threshold_neighborhood_trials": len(neighborhood_rows),
                "walk_forward_relaxed_pass_count": fold_pass_count,
                "walk_forward_combined_metrics": combined_metrics,
                "cost_stress": cost_rows,
                "oos_revealed": False,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
