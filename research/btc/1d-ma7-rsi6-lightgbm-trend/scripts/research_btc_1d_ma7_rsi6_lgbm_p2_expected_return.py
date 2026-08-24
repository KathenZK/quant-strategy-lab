from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

import research_btc_1d_ma7_rsi6_lgbm_p1 as p1


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1d-ma7-rsi6-lightgbm-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts/p2_expected_return_2026-08-10"
EXPECTED_EVENT_ROWS = 449
EXPECTED_EVENT_SHA256 = (
    "941246a90a2fe403b6de152e1527bb4ed1890ee84fdb32095b3a2eb87a3fd529"
)
EDGE_THRESHOLDS = (0.0, 0.0025, 0.0050, 0.0100)
INNER_MIN_TRADES_PER_FOLD = 5
INNER_MIN_TRADES_TOTAL = 15


@dataclass(frozen=True, slots=True)
class ExpectedReturnVariant:
    variant_id: str
    model_type: str
    target_type: str
    features: tuple[str, ...]
    validation_candidate: bool = False


VARIANTS = (
    ExpectedReturnVariant("ridge_core", "ridge", "raw", p1.CORE_FEATURES),
    ExpectedReturnVariant(
        "logistic_ev_core",
        "logistic_ev",
        "binary_ev",
        p1.CORE_FEATURES,
    ),
    ExpectedReturnVariant("lgbm_l2_ma", "lgbm_l2", "raw", p1.MA_FEATURES),
    ExpectedReturnVariant(
        "lgbm_l2_ma_k",
        "lgbm_l2",
        "raw",
        (*p1.MA_FEATURES, *p1.K_FEATURES),
    ),
    ExpectedReturnVariant(
        "lgbm_l2_core",
        "lgbm_l2",
        "raw",
        p1.CORE_FEATURES,
        validation_candidate=True,
    ),
    ExpectedReturnVariant(
        "lgbm_l2_core_vol",
        "lgbm_l2",
        "raw",
        (*p1.CORE_FEATURES, *p1.VOL_FEATURES),
    ),
    ExpectedReturnVariant(
        "lgbm_huber_core",
        "lgbm_huber",
        "raw",
        p1.CORE_FEATURES,
    ),
    ExpectedReturnVariant(
        "lgbm_l2_atr_diag",
        "lgbm_l2",
        "atr",
        p1.CORE_FEATURES,
    ),
)

BASE_REGRESSOR_PARAMS: dict[str, Any] = {
    "n_estimators": 120,
    "learning_rate": 0.03,
    "num_leaves": 7,
    "max_depth": 3,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.5,
    "reg_lambda": 2.0,
    "random_state": p1.SEED,
    "n_jobs": 1,
    "deterministic": True,
    "force_col_wise": True,
    "verbosity": -1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen P2 BTC daily MA7/RSI6 expected-net-return study "
            "without reading sealed validation data."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def event_identity_sha256(events: pd.DataFrame) -> str:
    frame = events.sort_values("event_id").reset_index(drop=True)
    digest = hashlib.sha256()
    for column in ("signal_ts", "entry_ts", "exit_ts"):
        values = (
            pd.to_datetime(frame[column], utc=True)
            .to_numpy(dtype="datetime64[ns]")
            .astype("int64")
        )
        digest.update(np.ascontiguousarray(values, dtype="int64").tobytes())
    for column in ("event_id", "side", "label"):
        values = frame[column].to_numpy(dtype="int64")
        digest.update(np.ascontiguousarray(values, dtype="int64").tobytes())
    float_columns = (
        "net_return",
        "net_return_atr",
        *p1.CORE_FEATURES,
        *p1.VOL_FEATURES,
    )
    for column in float_columns:
        values = frame[column].to_numpy(dtype="float64")
        digest.update(np.ascontiguousarray(values, dtype="float64").tobytes())
    digest.update("\0".join(frame["exit_reason"].astype(str)).encode("utf-8"))
    return digest.hexdigest()


def target_values(
    events: pd.DataFrame,
    variant: ExpectedReturnVariant,
) -> np.ndarray:
    if variant.target_type == "atr":
        return events["net_return_atr"].to_numpy(dtype="float64")
    return events["net_return"].to_numpy(dtype="float64")


def fit_model(
    train: pd.DataFrame,
    variant: ExpectedReturnVariant,
) -> Any:
    features = train[list(variant.features)]
    if variant.model_type == "ridge":
        model: Any = Pipeline(
            [
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=1.0)),
            ]
        )
        model.fit(features, target_values(train, variant))
        return model
    if variant.model_type == "logistic_ev":
        model = Pipeline(
            [
                ("scale", StandardScaler()),
                (
                    "model",
                    LogisticRegression(
                        C=1.0,
                        solver="lbfgs",
                        max_iter=2000,
                        class_weight=None,
                        random_state=p1.SEED,
                    ),
                ),
            ]
        )
        model.fit(features, train["label"].astype(int))
        return model
    objective = "huber" if variant.model_type == "lgbm_huber" else "regression"
    params = {**BASE_REGRESSOR_PARAMS, "objective": objective}
    if objective == "huber":
        params["alpha"] = 0.9
    model = lgb.LGBMRegressor(**params)
    model.fit(features, target_values(train, variant))
    return model


def predict_raw_edge(
    model: Any,
    train: pd.DataFrame,
    test: pd.DataFrame,
    variant: ExpectedReturnVariant,
) -> np.ndarray:
    features = test[list(variant.features)]
    if variant.model_type == "logistic_ev":
        probability = np.asarray(model.predict_proba(features)[:, 1], dtype="float64")
        positive_mean = float(train.loc[train["label"].eq(1), "net_return"].mean())
        nonpositive_mean = float(train.loc[train["label"].eq(0), "net_return"].mean())
        return probability * positive_mean + (1.0 - probability) * nonpositive_mean
    prediction = np.asarray(model.predict(features), dtype="float64")
    if variant.target_type == "atr":
        atr_scale = test["signal_atr7"].to_numpy(dtype="float64") / test[
            "entry_fill"
        ].to_numpy(dtype="float64")
        prediction = prediction * atr_scale
    return prediction


def predict_raw_contributions(
    model: Any,
    test: pd.DataFrame,
    variant: ExpectedReturnVariant,
) -> np.ndarray:
    if not isinstance(model, lgb.LGBMRegressor):
        return np.zeros((len(test), len(variant.features) + 1), dtype="float64")
    contributions = np.asarray(
        model.booster_.predict(
            test[list(variant.features)],
            pred_contrib=True,
        ),
        dtype="float64",
    )
    if variant.target_type == "atr":
        atr_scale = test["signal_atr7"].to_numpy(dtype="float64") / test[
            "entry_fill"
        ].to_numpy(dtype="float64")
        contributions = contributions * atr_scale[:, None]
    return contributions


def regression_metrics(
    realized: pd.Series,
    predicted: np.ndarray,
) -> dict[str, Any]:
    actual = realized.to_numpy(dtype="float64")
    residual = predicted - actual
    prediction_series = pd.Series(predicted, index=realized.index)
    return {
        "rows": int(len(actual)),
        "rmse": float(np.sqrt(np.mean(np.square(residual)))),
        "mae": float(np.mean(np.abs(residual))),
        "mean_error": float(np.mean(residual)),
        "spearman": float(prediction_series.corr(realized, method="spearman")),
        "pearson": float(prediction_series.corr(realized, method="pearson")),
        "predicted_mean": float(np.mean(predicted)),
        "predicted_min": float(np.min(predicted)),
        "predicted_max": float(np.max(predicted)),
        "predicted_positive_rate": float(np.mean(predicted > 0.0)),
        "realized_mean": float(np.mean(actual)),
    }


def select_edge_inner(
    events: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    variant: ExpectedReturnVariant,
) -> tuple[float | None, list[dict[str, Any]]]:
    folds = p1.make_folds(events, initial_fraction=0.50, blocks=3)
    predictions: list[dict[str, Any]] = []
    for fold_number, train, test in folds:
        model = fit_model(train, variant)
        predicted_edge = predict_raw_edge(model, train, test, variant)
        prediction = test.copy()
        prediction["predicted_edge"] = predicted_edge
        predictions.append({"fold": fold_number, "prediction": prediction})
    scores: list[dict[str, Any]] = []
    for edge in EDGE_THRESHOLDS:
        fold_metrics: list[dict[str, Any]] = []
        trade_counts: list[int] = []
        for item in predictions:
            prediction = item["prediction"]
            selected = prediction.loc[prediction["predicted_edge"].gt(edge)].copy()
            metrics = p1.strategy_metrics(selected, paths)
            trade_counts.append(int(metrics["closed_trades"]))
            fold_metrics.append(
                {
                    "fold": int(item["fold"]),
                    "metrics": metrics,
                }
            )
        eligible = bool(
            all(count >= INNER_MIN_TRADES_PER_FOLD for count in trade_counts)
            and sum(trade_counts) >= INNER_MIN_TRADES_TOTAL
        )
        scores.append(
            {
                "edge": float(edge),
                "eligible": eligible,
                "trade_counts": trade_counts,
                "total_trades": int(sum(trade_counts)),
                "worst_fold_return": (
                    min(float(item["metrics"]["total_return"]) for item in fold_metrics)
                    if eligible
                    else None
                ),
                "fold_metrics": fold_metrics,
            }
        )
    eligible_scores = [item for item in scores if item["eligible"]]
    if not eligible_scores:
        return None, scores
    ranked = sorted(
        eligible_scores,
        key=lambda item: (
            -float(item["worst_fold_return"]),
            float(item["edge"]),
            -int(item["total_trades"]),
        ),
    )
    return float(ranked[0]["edge"]), scores


def route_ranking(
    predictions: pd.DataFrame,
    route: str,
) -> dict[str, Any]:
    frame = p1.route_events(predictions, route)
    spearman = float(
        frame["predicted_edge"].corr(frame["net_return"], method="spearman")
    )
    folds: list[dict[str, Any]] = []
    stable_count = 0
    for fold_number in range(1, 5):
        fold = frame.loc[frame["fold"].eq(fold_number)].copy()
        top_count = max(1, int(math.ceil(len(fold) * 0.20)))
        top = fold.nlargest(top_count, "predicted_edge")
        all_mean = float(fold["net_return"].mean())
        top_mean = float(top["net_return"].mean())
        stable = bool(top_mean > all_mean)
        stable_count += int(stable)
        folds.append(
            {
                "fold": fold_number,
                "rows": int(len(fold)),
                "top_rows": int(len(top)),
                "all_realized_mean": all_mean,
                "top_quintile_realized_mean": top_mean,
                "top_quintile_beats_all": stable,
            }
        )
    gate = bool(math.isfinite(spearman) and spearman > 0.10 and stable_count >= 3)
    return {
        "spearman_predicted_vs_realized": spearman,
        "top_quintile_stable_fold_count": stable_count,
        "folds": folds,
        "ranking_gate_pass": gate,
    }


def run_variant_walk_forward(
    events: pd.DataFrame,
    paths: dict[int, pd.DataFrame],
    variant: ExpectedReturnVariant,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    outer_folds = p1.make_folds(events, initial_fraction=0.40, blocks=4)
    prediction_frames: list[pd.DataFrame] = []
    shap_frames: list[pd.DataFrame] = []
    fold_reports: list[dict[str, Any]] = []
    for fold_number, train, test in outer_folds:
        edge, inner_scores = select_edge_inner(train, paths, variant)
        model = fit_model(train, variant)
        predicted_edge = predict_raw_edge(model, train, test, variant)
        prediction = test.copy()
        prediction["variant_id"] = variant.variant_id
        prediction["fold"] = fold_number
        prediction["predicted_edge"] = predicted_edge
        prediction["edge_threshold"] = np.nan if edge is None else edge
        prediction["edge_eligible"] = edge is not None
        prediction["selected"] = (
            False if edge is None else prediction["predicted_edge"].gt(edge)
        )
        prediction_frames.append(prediction)
        if isinstance(model, lgb.LGBMRegressor):
            contributions = predict_raw_contributions(model, test, variant)
            shap = test[["event_id", "signal_ts", "side", "label", "net_return"]].copy()
            shap["variant_id"] = variant.variant_id
            shap["fold"] = fold_number
            for feature_index, feature in enumerate(variant.features):
                shap[f"shap_{feature}"] = contributions[:, feature_index]
            shap["shap_base"] = contributions[:, -1]
            shap_frames.append(shap)
        fold_reports.append(
            {
                "fold": fold_number,
                "train_rows": int(len(train)),
                "train_start": pd.Timestamp(train["signal_ts"].min()),
                "train_end": pd.Timestamp(train["signal_ts"].max()),
                "test_rows": int(len(test)),
                "test_start": pd.Timestamp(test["signal_ts"].min()),
                "test_end": pd.Timestamp(test["signal_ts"].max()),
                "selected_edge": edge,
                "edge_selection_failed": edge is None,
                "predictive": regression_metrics(
                    test["net_return"],
                    predicted_edge,
                ),
                "inner_edge_scores": inner_scores,
            }
        )
    predictions = pd.concat(prediction_frames, ignore_index=True)
    shap = pd.concat(shap_frames, ignore_index=True) if shap_frames else pd.DataFrame()
    routes: dict[str, Any] = {}
    for route in ("combined", "long_only", "short_only"):
        fold_comparisons: list[dict[str, Any]] = []
        for fold_number in range(1, 5):
            fold = predictions.loc[predictions["fold"].eq(fold_number)].copy()
            fold_route = p1.route_events(fold, route)
            selected = fold_route.loc[fold_route["selected"]].copy()
            model_metrics = p1.strategy_metrics(selected, paths)
            baseline_metrics = p1.strategy_metrics(fold_route, paths)
            fold_comparisons.append(
                {
                    "fold": fold_number,
                    "model": model_metrics,
                    "all_cross_baseline": baseline_metrics,
                    "return_beats_baseline": (
                        float(model_metrics["total_return"])
                        > float(baseline_metrics["total_return"])
                    ),
                }
            )
        route_frame = p1.route_events(predictions, route)
        selected_route = route_frame.loc[route_frame["selected"]].copy()
        model_metrics = p1.strategy_metrics(selected_route, paths)
        baseline_metrics = p1.strategy_metrics(route_frame, paths)
        better_fold_count = sum(
            bool(item["return_beats_baseline"]) for item in fold_comparisons
        )
        economic_gate = bool(
            int(model_metrics["closed_trades"]) >= 30
            and float(model_metrics["total_return"]) > 0.0
            and float(model_metrics["profit_factor"]) >= 1.20
            and float(model_metrics["max_drawdown"])
            >= float(baseline_metrics["max_drawdown"])
            and better_fold_count >= 3
        )
        ranking = route_ranking(predictions, route)
        routes[route] = {
            "model": model_metrics,
            "all_cross_baseline": baseline_metrics,
            "better_fold_count": better_fold_count,
            "folds": fold_comparisons,
            "economic_gate_pass": economic_gate,
            "ranking": ranking,
            "development_gate_pass": bool(
                economic_gate and ranking["ranking_gate_pass"]
            ),
        }
    return (
        predictions,
        shap,
        {
            "variant": asdict(variant),
            "outer_folds": fold_reports,
            "routes": routes,
        },
    )


def choose_primary_route(report: dict[str, Any]) -> str | None:
    routes = report["routes"]
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
            min(
                float(fold["model"]["total_return"]) for fold in routes[route]["folds"]
            ),
            int(routes[route]["model"]["closed_trades"]),
        ),
        reverse=True,
    )[0]


def probability_quintiles(frame: pd.DataFrame) -> list[dict[str, Any]]:
    ranked = frame.copy()
    ranked["predicted_edge_quintile"] = pd.qcut(
        ranked["predicted_edge"],
        q=5,
        labels=False,
        duplicates="drop",
    )
    result = (
        ranked.groupby("predicted_edge_quintile", observed=True)
        .agg(
            rows=("event_id", "size"),
            predicted_edge_mean=("predicted_edge", "mean"),
            realized_return_mean=("net_return", "mean"),
            positive_rate=("label", "mean"),
        )
        .reset_index()
    )
    return result.to_dict("records")


def typical_events(
    predictions: pd.DataFrame,
    route: str | None,
) -> dict[str, Any]:
    frame = (
        p1.route_events(predictions, route) if route is not None else predictions.copy()
    )
    columns = [
        "event_id",
        "signal_ts",
        "side_name",
        "predicted_edge",
        "edge_threshold",
        "selected",
        "net_return",
        "net_return_atr",
        "exit_reason",
        "rsi6",
        "rsi6_max_5",
        "close_ma_gap_atr",
        "ma7_slope_3_atr",
        "body_atr",
        "upper_wick_atr",
        "lower_wick_atr",
    ]
    selected = frame.loc[frame["selected"]].copy()
    return {
        "highest_predicted_winners": frame.loc[frame["label"].eq(1)]
        .nlargest(5, "predicted_edge")[columns]
        .to_dict("records"),
        "highest_predicted_losers": frame.loc[frame["label"].eq(0)]
        .nlargest(5, "predicted_edge")[columns]
        .to_dict("records"),
        "selected_best": selected.nlargest(5, "net_return")[columns].to_dict("records"),
        "selected_worst": selected.nsmallest(5, "net_return")[columns].to_dict(
            "records"
        ),
    }


def run_self_tests() -> None:
    sample = pd.DataFrame(
        {
            "signal_ts": pd.date_range("2024-01-01", periods=60, freq="D", tz="UTC"),
            "exit_ts": pd.date_range("2024-01-02", periods=60, freq="D", tz="UTC"),
            "label": [0, 1] * 30,
            "net_return": np.linspace(-0.03, 0.03, 60),
        }
    )
    folds = p1.make_folds(sample, initial_fraction=0.50, blocks=3)
    assert len(folds) == 3
    assert all(len(test) == 10 for _, _, test in folds)
    prediction = pd.Series([0.0, 0.0025, 0.0026])
    assert int(prediction.gt(0.0025).sum()) == 1


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_tests()
        print(json.dumps({"self_test": "PASS"}, indent=2))
        return
    generated_at = datetime.now(UTC)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    daily = p1.add_indicators(p1.load_development_daily())
    hourly = p1.load_development_hourly()
    funding = p1.load_development_funding()
    events, paths = p1.build_events(daily, hourly, funding)
    event_hash = event_identity_sha256(events)
    if len(events) != EXPECTED_EVENT_ROWS or event_hash != EXPECTED_EVENT_SHA256:
        raise RuntimeError(
            "P2 event identity differs from frozen P1 evidence: "
            f"rows={len(events)}, sha256={event_hash}"
        )
    event_path = args.output_dir / "p2_events.parquet"
    p1.atomic_write_path(
        event_path,
        lambda temp_path: events.to_parquet(temp_path, index=False),
    )

    all_predictions: list[pd.DataFrame] = []
    all_shap: list[pd.DataFrame] = []
    variant_reports: dict[str, Any] = {}
    for variant in VARIANTS:
        predictions, shap, report = run_variant_walk_forward(
            events,
            paths,
            variant,
        )
        all_predictions.append(predictions)
        if not shap.empty:
            all_shap.append(shap)
        variant_reports[variant.variant_id] = report
    predictions = pd.concat(all_predictions, ignore_index=True)
    prediction_path = args.output_dir / "p2_outer_predictions.parquet"
    p1.atomic_write_path(
        prediction_path,
        lambda temp_path: predictions.to_parquet(temp_path, index=False),
    )
    shap = pd.concat(all_shap, ignore_index=True)
    shap_path = args.output_dir / "p2_outer_shap.parquet"
    p1.atomic_write_path(
        shap_path,
        lambda temp_path: shap.to_parquet(temp_path, index=False),
    )

    primary_variant = next(
        variant for variant in VARIANTS if variant.variant_id == "lgbm_l2_core"
    )
    primary_report = variant_reports[primary_variant.variant_id]
    primary_predictions = predictions.loc[
        predictions["variant_id"].eq(primary_variant.variant_id)
    ].copy()
    primary_shap = shap.loc[shap["variant_id"].eq(primary_variant.variant_id)].copy()
    selected_route = choose_primary_route(primary_report)
    full_development_edges: dict[str, Any] = {}
    for variant in VARIANTS:
        variant_edge, variant_scores = select_edge_inner(
            events,
            paths,
            variant,
        )
        full_development_edges[variant.variant_id] = {
            "selected_edge": variant_edge,
            "scores": variant_scores,
        }
    final_edge = full_development_edges[primary_variant.variant_id]["selected_edge"]
    final_edge_scores = full_development_edges[primary_variant.variant_id]["scores"]
    if final_edge is None:
        selected_route = None
    final_model = fit_model(events, primary_variant)
    if not isinstance(final_model, lgb.LGBMRegressor):
        raise RuntimeError("P2 final primary model is not LightGBM regressor")
    model_path = args.output_dir / "p2_final_lgbm_l2_core_model.txt"
    final_model.booster_.save_model(str(model_path))
    split_thresholds = p1.extract_split_thresholds(final_model)
    p1.write_json(
        args.output_dir / "p2_final_core_split_thresholds.json",
        split_thresholds[:100],
    )
    shap_table, dependence = p1.shap_summary(
        events,
        primary_shap,
        p1.CORE_FEATURES,
    )
    shap_summary_path = args.output_dir / "p2_core_shap_summary.csv"
    p1.atomic_write_path(
        shap_summary_path,
        lambda temp_path: shap_table.to_csv(temp_path, index=False),
    )
    p1.write_json(args.output_dir / "p2_core_feature_dependence.json", dependence)

    manifest = {
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P2 development-only expected net return",
        "features": list(p1.CORE_FEATURES),
        "model_params": {
            **BASE_REGRESSOR_PARAMS,
            "objective": "regression",
        },
        "event_identity_sha256": event_hash,
        "diagnostic_full_development_edge": final_edge,
        "selected_route": selected_route,
        "validation_authorized": bool(
            selected_route is not None and final_edge is not None
        ),
        "development_end_exclusive": p1.DEVELOPMENT_END_EXCLUSIVE,
        "validation_end_inclusive_sealed": p1.VALIDATION_END_INCLUSIVE,
        "validation_revealed": False,
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": p1.file_sha256(model_path),
    }
    p1.write_json(args.output_dir / "p2_final_core_model_manifest.json", manifest)

    selected_oos = (
        p1.route_events(primary_predictions, selected_route)
        if selected_route is not None
        else primary_predictions.iloc[0:0].copy()
    )
    selected_oos = selected_oos.loc[selected_oos["selected"]].copy()
    selected_path = args.output_dir / "p2_selected_oos_trades.parquet"
    p1.atomic_write_path(
        selected_path,
        lambda temp_path: selected_oos.to_parquet(temp_path, index=False),
    )

    model_rankings = {
        variant_id: {
            "spearman_predicted_vs_realized": float(
                frame["predicted_edge"].corr(
                    frame["net_return"],
                    method="spearman",
                )
            ),
            "quintiles": probability_quintiles(frame),
        }
        for variant_id, frame in predictions.groupby("variant_id", sort=True)
    }
    summary = {
        "generated_at_utc": generated_at,
        "family": "BTC-1D-MA7-RSI6-LightGBM-Trend",
        "stage": "P2 development-only expected net return",
        "status": "explore / diagnostic-only / not promoted / not live-ready",
        "validation_revealed": False,
        "event_consistency": {
            "rows": int(len(events)),
            "event_identity_sha256": event_hash,
            "expected_rows": EXPECTED_EVENT_ROWS,
            "expected_sha256": EXPECTED_EVENT_SHA256,
            "matches_p1": True,
        },
        "edge_contract": {
            "thresholds": list(EDGE_THRESHOLDS),
            "strict_comparison": "predicted_edge > edge",
            "inner_min_trades_per_fold": INNER_MIN_TRADES_PER_FOLD,
            "inner_min_trades_total": INNER_MIN_TRADES_TOTAL,
        },
        "variant_reports": variant_reports,
        "oos_rankings": model_rankings,
        "full_development_edges": full_development_edges,
        "primary_decision": {
            "selected_route": selected_route,
            "development_gate_pass": selected_route is not None,
            "diagnostic_full_development_edge": final_edge,
            "edge_for_future_validation": (
                final_edge if selected_route is not None else None
            ),
            "final_edge_scores": final_edge_scores,
            "validation_eligible": selected_route is not None,
        },
        "interpretability": {
            "shap_summary": shap_table.to_dict("records"),
            "top_split_thresholds": split_thresholds[:30],
            "typical_events": typical_events(
                primary_predictions,
                selected_route,
            ),
        },
        "recent_slices_anchored_to_development_end_audit_only": (
            p1.recent_slice_metrics(
                primary_predictions,
                paths,
                selected_route,
            )
            if selected_route is not None
            else {}
        ),
        "artifacts": {
            "events": str(event_path.relative_to(ROOT)),
            "predictions": str(prediction_path.relative_to(ROOT)),
            "outer_shap": str(shap_path.relative_to(ROOT)),
            "shap_summary": str(shap_summary_path.relative_to(ROOT)),
            "selected_oos_trades": str(selected_path.relative_to(ROOT)),
            "model": str(model_path.relative_to(ROOT)),
        },
    }
    summary_path = args.output_dir / "p2_development_summary.json"
    p1.write_json(summary_path, summary)
    print(
        json.dumps(
            p1.json_ready(
                {
                    "event_consistency": summary["event_consistency"],
                    "primary_decision": summary["primary_decision"],
                    "primary_routes": primary_report["routes"],
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
