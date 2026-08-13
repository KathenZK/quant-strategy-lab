from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_btc_1d_ma7_rsi6_lgbm_p1 as p1
import research_btc_1d_ma7_rsi6_lgbm_p2_expected_return as p2


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-ma7-rsi6-lightgbm-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p3_logistic_ev_robustness_2026-08-10"
P2_PREDICTIONS_PATH = (
    FAMILY_DIR / "artifacts/p2_expected_return_2026-08-10/p2_outer_predictions.parquet"
)

MAIN_EDGE = 0.0100
STRESS_EDGES = (0.0050, 0.0150)
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 20260810


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen P3 Logistic-EV robustness study on development "
            "data while keeping the final validation year sealed."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def logistic_variant() -> p2.ExpectedReturnVariant:
    return next(
        variant for variant in p2.VARIANTS if variant.variant_id == "logistic_ev_core"
    )


def prediction_identity_sha256(frame: pd.DataFrame) -> str:
    ordered = frame.sort_values(["fold", "event_id"]).reset_index(drop=True)
    digest = hashlib.sha256()
    for column in ("fold", "event_id"):
        values = ordered[column].to_numpy(dtype="int64")
        digest.update(np.ascontiguousarray(values, dtype="int64").tobytes())
    values = ordered["predicted_edge"].to_numpy(dtype="float64")
    digest.update(np.ascontiguousarray(values, dtype="float64").tobytes())
    return digest.hexdigest()


def logistic_parameters(
    model: Any,
    train: pd.DataFrame,
    *,
    fold: int | str,
) -> dict[str, Any]:
    scaler = model.named_steps["scale"]
    classifier = model.named_steps["model"]
    standardized_coef = classifier.coef_[0].astype("float64")
    scale = scaler.scale_.astype("float64")
    mean = scaler.mean_.astype("float64")
    raw_coef = standardized_coef / scale
    standardized_intercept = float(classifier.intercept_[0])
    raw_intercept = standardized_intercept - float(np.sum(raw_coef * mean))
    positive = train.loc[train["label"].eq(1), "net_return"]
    nonpositive = train.loc[train["label"].eq(0), "net_return"]
    return {
        "fold": fold,
        "train_rows": int(len(train)),
        "train_start": pd.Timestamp(train["signal_ts"].min()),
        "train_end": pd.Timestamp(train["signal_ts"].max()),
        "mean_positive_return": float(positive.mean()),
        "mean_nonpositive_return": float(nonpositive.mean()),
        "scaler_mean": {
            feature: float(value)
            for feature, value in zip(p1.CORE_FEATURES, mean, strict=True)
        },
        "scaler_scale": {
            feature: float(value)
            for feature, value in zip(p1.CORE_FEATURES, scale, strict=True)
        },
        "standardized_coefficients": {
            feature: float(value)
            for feature, value in zip(
                p1.CORE_FEATURES,
                standardized_coef,
                strict=True,
            )
        },
        "raw_coefficients": {
            feature: float(value)
            for feature, value in zip(p1.CORE_FEATURES, raw_coef, strict=True)
        },
        "standardized_intercept": standardized_intercept,
        "raw_intercept": raw_intercept,
    }


def run_outer_predictions(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    variant = logistic_variant()
    prediction_frames: list[pd.DataFrame] = []
    fold_models: list[dict[str, Any]] = []
    for fold_number, train, test in p1.make_folds(
        events,
        initial_fraction=0.40,
        blocks=4,
    ):
        model = p2.fit_model(train, variant)
        probability = np.asarray(
            model.predict_proba(test[list(variant.features)])[:, 1],
            dtype="float64",
        )
        predicted_edge = p2.predict_raw_edge(
            model,
            train,
            test,
            variant,
        )
        prediction = test.copy()
        prediction["variant_id"] = "logistic_ev_p3"
        prediction["fold"] = fold_number
        prediction["probability"] = probability
        prediction["predicted_edge"] = predicted_edge
        prediction["edge_threshold"] = MAIN_EDGE
        prediction["selected"] = prediction["predicted_edge"].gt(MAIN_EDGE)
        prediction_frames.append(prediction)
        parameters = logistic_parameters(model, train, fold=fold_number)
        parameters["predictive_ev"] = p2.regression_metrics(
            test["net_return"],
            predicted_edge,
        )
        parameters["predictive_label"] = p1.predictive_metrics(
            test["label"],
            probability,
        )
        fold_models.append(parameters)
    return pd.concat(prediction_frames, ignore_index=True), fold_models


def stratified_trade_bootstrap(
    selected: pd.DataFrame,
    *,
    route_seed_offset: int,
) -> tuple[dict[str, Any], np.ndarray]:
    rng = np.random.default_rng(BOOTSTRAP_SEED + route_seed_offset)
    fold_returns = {
        int(fold): group["net_return"].to_numpy(dtype="float64")
        for fold, group in selected.groupby("fold", sort=True)
    }
    samples = np.empty(BOOTSTRAP_ITERATIONS, dtype="float64")
    for iteration in range(BOOTSTRAP_ITERATIONS):
        drawn: list[np.ndarray] = []
        for fold_number in range(1, 5):
            values = fold_returns.get(fold_number, np.array([], dtype="float64"))
            if len(values):
                drawn.append(rng.choice(values, size=len(values), replace=True))
        if not drawn:
            samples[iteration] = 0.0
            continue
        returns = np.concatenate(drawn)
        samples[iteration] = float(np.prod(1.0 + returns) - 1.0)
    positive_probability = float(np.mean(samples > 0.0))
    summary = {
        "iterations": BOOTSTRAP_ITERATIONS,
        "seed": BOOTSTRAP_SEED + route_seed_offset,
        "method": "within-outer-fold stratified trade resampling",
        "selected_trades": int(len(selected)),
        "positive_return_probability": positive_probability,
        "return_quantiles": {
            "p025": float(np.quantile(samples, 0.025)),
            "p50": float(np.quantile(samples, 0.50)),
            "p975": float(np.quantile(samples, 0.975)),
        },
        "bootstrap_gate_pass": positive_probability >= 0.95,
    }
    return summary, samples


def evaluate_route(
    predictions: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    route: str,
    *,
    route_seed_offset: int,
) -> tuple[dict[str, Any], np.ndarray]:
    frame = p1.route_events(predictions, route)
    selected = frame.loc[frame["predicted_edge"].gt(MAIN_EDGE)].copy()
    model_metrics = p1.strategy_metrics(selected, paths)
    baseline_metrics = p1.strategy_metrics(frame, paths)
    fold_reports: list[dict[str, Any]] = []
    for fold_number in range(1, 5):
        fold = frame.loc[frame["fold"].eq(fold_number)].copy()
        fold_selected = fold.loc[fold["predicted_edge"].gt(MAIN_EDGE)].copy()
        metrics = p1.strategy_metrics(fold_selected, paths)
        baseline = p1.strategy_metrics(fold, paths)
        fold_reports.append(
            {
                "fold": fold_number,
                "model": metrics,
                "all_cross_baseline": baseline,
                "absolute_return_positive": float(metrics["total_return"]) > 0.0,
                "return_beats_baseline": (
                    float(metrics["total_return"]) > float(baseline["total_return"])
                ),
            }
        )
    positive_fold_count = sum(
        bool(item["absolute_return_positive"]) for item in fold_reports
    )
    better_fold_count = sum(
        bool(item["return_beats_baseline"]) for item in fold_reports
    )
    ranking = p2.route_ranking(predictions, route)
    economic_gate = bool(
        int(model_metrics["closed_trades"]) >= 30
        and float(model_metrics["total_return"]) > 0.0
        and float(model_metrics["profit_factor"]) >= 1.20
        and float(model_metrics["max_drawdown"])
        >= float(baseline_metrics["max_drawdown"])
        and better_fold_count >= 3
    )
    absolute_fold_gate = positive_fold_count >= 3
    stress: dict[str, Any] = {}
    stress_gate = True
    for edge in STRESS_EDGES:
        stress_selected = frame.loc[frame["predicted_edge"].gt(edge)].copy()
        metrics = p1.strategy_metrics(stress_selected, paths)
        passed = bool(
            float(metrics["total_return"]) > 0.0
            and float(metrics["profit_factor"]) >= 1.10
        )
        stress[f"{edge:.4f}"] = {
            "edge": edge,
            "metrics": metrics,
            "stress_gate_pass": passed,
        }
        stress_gate = stress_gate and passed
    bootstrap, samples = stratified_trade_bootstrap(
        selected,
        route_seed_offset=route_seed_offset,
    )
    full_gate = bool(
        economic_gate
        and ranking["ranking_gate_pass"]
        and absolute_fold_gate
        and stress_gate
        and bootstrap["bootstrap_gate_pass"]
    )
    return (
        {
            "main_edge": MAIN_EDGE,
            "model": model_metrics,
            "all_cross_baseline": baseline_metrics,
            "folds": fold_reports,
            "positive_absolute_fold_count": positive_fold_count,
            "better_baseline_fold_count": better_fold_count,
            "economic_gate_pass": economic_gate,
            "ranking": ranking,
            "absolute_fold_gate_pass": absolute_fold_gate,
            "stress": stress,
            "stress_gate_pass": stress_gate,
            "bootstrap": bootstrap,
            "development_gate_pass": full_gate,
        },
        samples,
    )


def choose_route(routes: dict[str, Any]) -> str | None:
    if routes["combined"]["development_gate_pass"]:
        return "combined"
    passing = [
        route
        for route in ("long_only", "short_only")
        if routes[route]["development_gate_pass"]
    ]
    if not passing:
        return None
    if len(passing) == 1:
        return passing[0]
    return sorted(
        passing,
        key=lambda route: (
            float(routes[route]["bootstrap"]["positive_return_probability"]),
            min(
                float(fold["model"]["total_return"]) for fold in routes[route]["folds"]
            ),
        ),
        reverse=True,
    )[0]


def coefficient_stability(
    fold_models: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature in p1.CORE_FEATURES:
        values = np.asarray(
            [fold["raw_coefficients"][feature] for fold in fold_models],
            dtype="float64",
        )
        nonzero = values[values != 0.0]
        sign_consistency = (
            max(int(np.sum(nonzero > 0.0)), int(np.sum(nonzero < 0.0))) / len(nonzero)
            if len(nonzero)
            else 0.0
        )
        rows.append(
            {
                "feature": feature,
                "raw_coefficient_mean": float(values.mean()),
                "raw_coefficient_std": float(values.std(ddof=0)),
                "mean_abs_raw_coefficient": float(np.abs(values).mean()),
                "fold_sign_consistency": float(sign_consistency),
                "fold_values": values.tolist(),
            }
        )
    return sorted(
        rows,
        key=lambda row: row["mean_abs_raw_coefficient"],
        reverse=True,
    )


def run_self_tests() -> None:
    returns = pd.DataFrame(
        {
            "fold": [1, 1, 2, 2, 3, 3, 4, 4],
            "net_return": [0.01, -0.005] * 4,
        }
    )
    summary, samples = stratified_trade_bootstrap(
        returns,
        route_seed_offset=0,
    )
    assert len(samples) == BOOTSTRAP_ITERATIONS
    assert summary["selected_trades"] == 8
    prediction = pd.Series([0.0100, 0.0101])
    assert int(prediction.gt(MAIN_EDGE).sum()) == 1


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_tests()
        print(json.dumps({"self_test": "PASS"}, indent=2))
        return
    args.output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(UTC)
    daily = p1.add_indicators(p1.load_development_daily())
    hourly = p1.load_development_hourly()
    funding = p1.load_development_funding()
    events, paths = p1.build_events(daily, hourly, funding)
    event_hash = p2.event_identity_sha256(events)
    if len(events) != p2.EXPECTED_EVENT_ROWS or event_hash != p2.EXPECTED_EVENT_SHA256:
        raise RuntimeError(
            f"P3 event mismatch: rows={len(events)}, sha256={event_hash}"
        )

    predictions, fold_models = run_outer_predictions(events)
    p2_predictions = pd.read_parquet(
        P2_PREDICTIONS_PATH,
        filters=[("variant_id", "==", "logistic_ev_core")],
    ).sort_values(["fold", "event_id"])
    current = predictions.sort_values(["fold", "event_id"])
    merged = current[["fold", "event_id", "predicted_edge"]].merge(
        p2_predictions[["fold", "event_id", "predicted_edge"]],
        on=["fold", "event_id"],
        how="outer",
        suffixes=("_p3", "_p2"),
        validate="one_to_one",
        indicator=True,
    )
    max_prediction_diff = float(
        (merged["predicted_edge_p3"] - merged["predicted_edge_p2"]).abs().max()
    )
    if (
        len(merged) != 270
        or merged["_merge"].ne("both").any()
        or max_prediction_diff != 0.0
    ):
        raise RuntimeError(
            "P3 Logistic-EV predictions differ from the frozen P2 diagnostic"
        )
    prediction_hash = prediction_identity_sha256(predictions)

    event_path = args.output_dir / "p3_events.parquet"
    prediction_path = args.output_dir / "p3_outer_predictions.parquet"
    p1.atomic_write_path(
        event_path,
        lambda temp_path: events.to_parquet(temp_path, index=False),
    )
    p1.atomic_write_path(
        prediction_path,
        lambda temp_path: predictions.to_parquet(temp_path, index=False),
    )

    routes: dict[str, Any] = {}
    bootstrap_frames: list[pd.DataFrame] = []
    for offset, route in enumerate(
        ("combined", "long_only", "short_only"),
    ):
        report, samples = evaluate_route(
            predictions,
            paths,
            route,
            route_seed_offset=offset,
        )
        routes[route] = report
        bootstrap_frames.append(
            pd.DataFrame(
                {
                    "route": route,
                    "iteration": np.arange(BOOTSTRAP_ITERATIONS, dtype="int64"),
                    "compounded_return": samples,
                }
            )
        )
    bootstrap_frame = pd.concat(bootstrap_frames, ignore_index=True)
    bootstrap_path = args.output_dir / "p3_bootstrap_returns.parquet"
    p1.atomic_write_path(
        bootstrap_path,
        lambda temp_path: bootstrap_frame.to_parquet(temp_path, index=False),
    )
    selected_route = choose_route(routes)

    variant = logistic_variant()
    final_model = p2.fit_model(events, variant)
    final_parameters = logistic_parameters(
        final_model,
        events,
        fold="full_development",
    )
    final_parameters.update(
        {
            "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
            "stage": "P3 Logistic-EV development-only",
            "features": list(p1.CORE_FEATURES),
            "main_edge": MAIN_EDGE,
            "event_identity_sha256": event_hash,
        }
    )
    model_path = args.output_dir / "p3_final_logistic_ev_model.json"
    p1.write_json(model_path, final_parameters)
    coefficient_rows = coefficient_stability(fold_models)
    coefficient_path = args.output_dir / "p3_coefficient_stability.json"
    p1.write_json(coefficient_path, coefficient_rows)

    candidate_trades = (
        p1.route_events(predictions, selected_route)
        if selected_route is not None
        else predictions.iloc[0:0].copy()
    )
    candidate_trades = candidate_trades.loc[
        candidate_trades["predicted_edge"].gt(MAIN_EDGE)
    ].copy()
    candidate_path = args.output_dir / "p3_candidate_oos_trades.parquet"
    p1.atomic_write_path(
        candidate_path,
        lambda temp_path: candidate_trades.to_parquet(temp_path, index=False),
    )
    main_combined = predictions.loc[predictions["predicted_edge"].gt(MAIN_EDGE)].copy()
    main_combined_path = args.output_dir / "p3_main_edge_combined_trades.parquet"
    p1.atomic_write_path(
        main_combined_path,
        lambda temp_path: main_combined.to_parquet(temp_path, index=False),
    )

    validation_eligible = selected_route is not None
    manifest = {
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P3 Logistic-EV development-only",
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": p1.file_sha256(model_path),
        "main_edge": MAIN_EDGE,
        "selected_route": selected_route,
        "development_gate_pass": validation_eligible,
        "validation_eligible": validation_eligible,
        "manual_validation_approval_required": True,
        "validation_authorized": False,
        "validation_revealed": False,
        "development_end_exclusive": p1.DEVELOPMENT_END_EXCLUSIVE,
        "validation_end_inclusive_sealed": p1.VALIDATION_END_INCLUSIVE,
    }
    p1.write_json(args.output_dir / "p3_model_manifest.json", manifest)

    summary = {
        "generated_at_utc": generated_at,
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P3 Logistic-EV development-only robustness",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "validation_revealed": False,
        "manual_validation_approval_required": True,
        "event_consistency": {
            "rows": int(len(events)),
            "event_identity_sha256": event_hash,
            "matches_p1_p2": True,
        },
        "prediction_consistency": {
            "rows": int(len(predictions)),
            "prediction_identity_sha256": prediction_hash,
            "matches_p2_logistic_ev": True,
            "max_abs_predicted_edge_diff": max_prediction_diff,
        },
        "contract": {
            "main_edge": MAIN_EDGE,
            "stress_edges": list(STRESS_EDGES),
            "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "fold_models": fold_models,
        "coefficient_stability": coefficient_rows,
        "prediction_quintiles": p2.probability_quintiles(predictions),
        "routes": routes,
        "decision": {
            "selected_route": selected_route,
            "development_gate_pass": validation_eligible,
            "validation_eligible": validation_eligible,
            "validation_authorized": False,
            "validation_revealed": False,
        },
        "typical_events": p2.typical_events(
            predictions,
            selected_route,
        ),
        "recent_slices_anchored_to_development_end_audit_only": (
            p1.recent_slice_metrics(
                predictions,
                paths,
                selected_route,
            )
            if validation_eligible
            else {}
        ),
        "artifacts": {
            "events": str(event_path.relative_to(ROOT)),
            "predictions": str(prediction_path.relative_to(ROOT)),
            "bootstrap_returns": str(bootstrap_path.relative_to(ROOT)),
            "final_model": str(model_path.relative_to(ROOT)),
            "coefficient_stability": str(coefficient_path.relative_to(ROOT)),
            "candidate_trades": str(candidate_path.relative_to(ROOT)),
            "main_edge_combined_trades": str(main_combined_path.relative_to(ROOT)),
        },
    }
    summary_path = args.output_dir / "p3_development_summary.json"
    p1.write_json(summary_path, summary)
    print(
        json.dumps(
            p1.json_ready(
                {
                    "decision": summary["decision"],
                    "routes": routes,
                    "summary": str(summary_path),
                }
            ),
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
