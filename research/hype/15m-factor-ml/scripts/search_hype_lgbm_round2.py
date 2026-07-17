from __future__ import annotations

import argparse
from dataclasses import asdict
from pathlib import Path
import json
import math
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, log_loss, mean_absolute_error

from audit_hype_15m_factors import (
    TRAIN_END_EXCLUSIVE,
    VALIDATION_END_EXCLUSIVE,
)
from backtest_hype_lgbm import BacktestConfig, run_prediction_backtest
from hype_ml_common import ARTIFACTS_DIR, TripleBarrierConfig, add_triple_barrier_labels, write_json


HARD_GATE = {
    "win_rate_min": 0.55,
    "max_drawdown_max": 0.20,
    "profit_factor_min": 1.30,
    "trade_count_min": 30,
    "total_return_min": 0.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Broad train/validation-only HYPE LightGBM Round 2 search."
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
        default=ARTIFACTS_DIR / "model_round2_search",
    )
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def label_configs() -> list[TripleBarrierConfig]:
    shapes = [
        (8, 0.60, 1.20),
        (8, 0.80, 1.20),
        (8, 1.00, 1.00),
        (8, 1.25, 1.00),
        (12, 0.60, 1.20),
        (12, 0.80, 1.20),
        (12, 1.00, 1.00),
        (12, 1.25, 1.00),
        (12, 1.50, 1.00),
        (24, 0.80, 1.50),
        (24, 1.00, 1.50),
        (24, 1.25, 1.25),
        (24, 1.50, 1.00),
        (24, 2.00, 1.25),
        (48, 1.00, 2.00),
        (48, 1.50, 1.50),
        (48, 2.00, 1.25),
        (48, 2.50, 1.50),
    ]
    return [
        TripleBarrierConfig(
            horizon_bars=horizon,
            take_profit_atr=take,
            stop_loss_atr=stop,
        )
        for horizon, take, stop in shapes
    ]


def label_id(config: TripleBarrierConfig) -> str:
    return (
        f"h{config.horizon_bars}_tp{config.take_profit_atr:.2f}"
        f"_sl{config.stop_loss_atr:.2f}"
    )


def model_specs(stage: int) -> list[dict[str, Any]]:
    if stage == 1:
        shapes = [
            ("shallow", 7, 3, 150, 0.04, 0.75, 2.0, 8.0),
            ("medium", 15, 5, 100, 0.03, 0.85, 1.0, 5.0),
        ]
    else:
        shapes = [
            ("compact", 7, 3, 100, 0.03, 0.70, 2.0, 10.0),
            ("shallow", 15, 4, 150, 0.04, 0.80, 1.0, 6.0),
            ("medium", 31, 6, 75, 0.025, 0.85, 0.5, 4.0),
            ("regularized", 15, 5, 250, 0.05, 0.65, 3.0, 12.0),
        ]
    result: list[dict[str, Any]] = []
    for model_type in (
        "multiclass",
        "dual_binary",
        "dual_binary_weighted",
        "dual_regression",
        "dual_regression_l2",
    ):
        for name, leaves, depth, child, rate, colsample, alpha, lambda_ in shapes:
            result.append(
                {
                    "id": f"{model_type}_{name}",
                    "model_type": model_type,
                    "num_leaves": leaves,
                    "max_depth": depth,
                    "min_child_samples": child,
                    "learning_rate": rate,
                    "colsample_bytree": colsample,
                    "reg_alpha": alpha,
                    "reg_lambda": lambda_,
                }
            )
    return result


def common_model_params(spec: dict[str, Any], seed: int) -> dict[str, Any]:
    return {
        "num_leaves": spec["num_leaves"],
        "max_depth": spec["max_depth"],
        "min_child_samples": spec["min_child_samples"],
        "learning_rate": spec["learning_rate"],
        "n_estimators": int(spec.get("n_estimators", 1500)),
        "subsample": 0.8,
        "subsample_freq": 1,
        "colsample_bytree": spec["colsample_bytree"],
        "reg_alpha": spec["reg_alpha"],
        "reg_lambda": spec["reg_lambda"],
        "random_state": seed,
        "n_jobs": -1,
        "verbosity": -1,
    }


def feature_sets(
    audit: dict[str, Any],
    stats: pd.DataFrame,
) -> dict[str, list[str]]:
    eligible = list(audit["eligible_features"])
    pruned = list(audit["correlation_pruned_features"])
    ranked = stats.loc[stats["factor"].isin(eligible), "factor"].tolist()
    return {
        "top30_ic": ranked[:30],
        "top60_ic": ranked[:60],
        "corr_pruned": pruned,
        "all_eligible": eligible,
    }


def prepare_label_frame(
    pre_oos: pd.DataFrame,
    config: TripleBarrierConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labeled = add_triple_barrier_labels(pre_oos, config)
    train = labeled.loc[labeled["ts"] < TRAIN_END_EXCLUSIVE].copy()
    train = train.loc[
        train["long_exit_ts"].lt(TRAIN_END_EXCLUSIVE)
        & train["short_exit_ts"].lt(TRAIN_END_EXCLUSIVE)
        & train["long_outcome_bps"].notna()
        & train["short_outcome_bps"].notna()
    ].reset_index(drop=True)
    validation_labeled = labeled.loc[
        (labeled["ts"] >= TRAIN_END_EXCLUSIVE)
        & (labeled["ts"] < VALIDATION_END_EXCLUSIVE)
    ].copy()
    validation_labeled = validation_labeled.loc[
        validation_labeled["long_exit_ts"].lt(VALIDATION_END_EXCLUSIVE)
        & validation_labeled["short_exit_ts"].lt(VALIDATION_END_EXCLUSIVE)
        & validation_labeled["long_outcome_bps"].notna()
        & validation_labeled["short_outcome_bps"].notna()
    ].reset_index(drop=True)
    diagnostics = {
        "label_id": label_id(config),
        "config": asdict(config),
        "train_rows": len(train),
        "validation_labeled_rows": len(validation_labeled),
        "train_class_counts": {
            str(key): int(value)
            for key, value in train["direction_label"].value_counts().items()
        },
        "validation_class_counts": {
            str(key): int(value)
            for key, value in validation_labeled["direction_label"].value_counts().items()
        },
        "train_long_positive_rate": float(train["long_outcome_bps"].gt(0).mean()),
        "train_short_positive_rate": float(train["short_outcome_bps"].gt(0).mean()),
        "validation_long_positive_rate": float(
            validation_labeled["long_outcome_bps"].gt(0).mean()
        ),
        "validation_short_positive_rate": float(
            validation_labeled["short_outcome_bps"].gt(0).mean()
        ),
    }
    return train, validation_labeled, diagnostics


def clean_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return frame[features].replace([np.inf, -np.inf], np.nan)


def train_and_predict(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    features: list[str],
    spec: dict[str, Any],
    horizon_bars: int,
    seed: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    split = int(len(train) * 0.80)
    fit = train.iloc[: max(split - horizon_bars, 1)].copy()
    early = train.iloc[split:].copy()
    if len(fit) < 1000 or len(early) < 500:
        raise RuntimeError("insufficient rows for purged early-stopping split")
    X_fit = clean_features(fit, features)
    X_early = clean_features(early, features)
    X_validation = clean_features(validation, features)
    params = common_model_params(spec, seed)
    callbacks = [lgb.early_stopping(100, verbose=False)]
    model_type = spec["model_type"]
    metrics: dict[str, Any] = {
        "fit_rows": len(fit),
        "early_stopping_rows": len(early),
        "feature_count": len(features),
    }
    predicted = validation[
        [
            "ts",
            "open",
            "high",
            "low",
            "close",
            "atr_pct_14",
            "funding_ts",
            "funding_rate",
        ]
    ].copy()

    if model_type == "multiclass":
        model = lgb.LGBMClassifier(
            objective="multiclass",
            num_class=3,
            class_weight="balanced",
            **params,
        )
        y_fit = fit["direction_label"].astype(int) + 1
        y_early = early["direction_label"].astype(int) + 1
        model.fit(
            X_fit,
            y_fit,
            eval_set=[(X_early, y_early)],
            eval_metric="multi_logloss",
            callbacks=callbacks,
        )
        probabilities = model.predict_proba(
            X_validation, num_iteration=model.best_iteration_
        )
        predicted["p_short"] = probabilities[:, 0]
        predicted["p_flat"] = probabilities[:, 1]
        predicted["p_long"] = probabilities[:, 2]
        target = validation["direction_label"].astype(int) + 1
        metrics.update(
            {
                "best_iterations": [int(model.best_iteration_)],
                "validation_balanced_accuracy": balanced_accuracy_score(
                    target, probabilities.argmax(axis=1)
                ),
                "validation_logloss": log_loss(target, probabilities, labels=[0, 1, 2]),
            }
        )
    elif model_type in {"dual_binary", "dual_binary_weighted"}:
        probabilities: dict[str, np.ndarray] = {}
        iterations: list[int] = []
        losses: dict[str, float] = {}
        for direction in ("long", "short"):
            target_column = f"{direction}_outcome_bps"
            model = lgb.LGBMClassifier(
                objective="binary",
                class_weight="balanced",
                **params,
            )
            y_fit = fit[target_column].gt(0).astype(int)
            y_early = early[target_column].gt(0).astype(int)
            fit_kwargs: dict[str, Any] = {}
            if model_type == "dual_binary_weighted":
                magnitude = fit[target_column].abs()
                scale = max(float(magnitude.median()), 1.0)
                fit_kwargs["sample_weight"] = (0.25 + magnitude / scale).clip(0.25, 5.0)
            model.fit(
                X_fit,
                y_fit,
                eval_set=[(X_early, y_early)],
                eval_metric="binary_logloss",
                callbacks=callbacks,
                **fit_kwargs,
            )
            probability = model.predict_proba(
                X_validation, num_iteration=model.best_iteration_
            )[:, 1]
            probabilities[direction] = probability
            iterations.append(int(model.best_iteration_))
            losses[direction] = log_loss(
                validation[target_column].gt(0).astype(int), probability
            )
        predicted["p_long"] = probabilities["long"]
        predicted["p_short"] = probabilities["short"]
        predicted["p_flat"] = 1.0 - np.maximum(
            probabilities["long"], probabilities["short"]
        )
        metrics.update(
            {
                "best_iterations": iterations,
                "validation_long_logloss": losses["long"],
                "validation_short_logloss": losses["short"],
            }
        )
    elif model_type in {"dual_regression", "dual_regression_l2"}:
        predictions: dict[str, np.ndarray] = {}
        iterations = []
        errors: dict[str, float] = {}
        for direction in ("long", "short"):
            target_column = f"{direction}_outcome_bps"
            objective = "regression_l2" if model_type == "dual_regression_l2" else "huber"
            model = lgb.LGBMRegressor(objective=objective, **params)
            y_fit = fit[target_column].clip(-1000.0, 1000.0)
            y_early = early[target_column].clip(-1000.0, 1000.0)
            model.fit(
                X_fit,
                y_fit,
                eval_set=[(X_early, y_early)],
                eval_metric="l1",
                callbacks=callbacks,
            )
            values = model.predict(X_validation, num_iteration=model.best_iteration_)
            predictions[direction] = values
            iterations.append(int(model.best_iteration_))
            errors[direction] = mean_absolute_error(
                validation[target_column].clip(-1000.0, 1000.0), values
            )
        predicted["pred_long_bps"] = predictions["long"]
        predicted["pred_short_bps"] = predictions["short"]
        metrics.update(
            {
                "best_iterations": iterations,
                "validation_long_mae_bps": errors["long"],
                "validation_short_mae_bps": errors["short"],
            }
        )
    else:
        raise ValueError(f"unsupported model type: {model_type}")
    return predicted, metrics


def probability_thresholds(fine: bool) -> list[dict[str, float]]:
    thresholds = (
        np.arange(0.35, 0.751, 0.025).round(3).tolist()
        if fine
        else [0.40, 0.50, 0.60]
    )
    margins = [0.0, 0.02, 0.05, 0.08, 0.12] if fine else [0.03, 0.08]
    return [
        {
            "long_threshold": float(threshold),
            "short_threshold": float(threshold),
            "probability_margin": float(margin),
        }
        for threshold in thresholds
        for margin in margins
    ]


def regression_thresholds(fine: bool) -> list[dict[str, float]]:
    edges = [-10.0, 0.0, 10.0, 20.0, 30.0, 40.0, 60.0, 80.0, 100.0] if fine else [10.0, 30.0, 60.0]
    margins = [0.0, 10.0, 20.0, 40.0] if fine else [10.0, 30.0]
    return [
        {"edge_threshold_bps": edge, "edge_margin_bps": margin}
        for edge in edges
        for margin in margins
    ]


def gate_pass(metrics: dict[str, Any]) -> bool:
    return bool(
        int(metrics["trade_count"]) >= HARD_GATE["trade_count_min"]
        and float(metrics["win_rate"]) >= HARD_GATE["win_rate_min"]
        and float(metrics["max_drawdown"]) <= HARD_GATE["max_drawdown_max"]
        and float(metrics["profit_factor"]) >= HARD_GATE["profit_factor_min"]
        and float(metrics["total_return"]) > HARD_GATE["total_return_min"]
    )


def score_metrics(metrics: dict[str, Any]) -> float:
    trades = int(metrics.get("trade_count", 0))
    if trades < 10:
        return -100.0 + trades
    profit_factor = float(metrics.get("profit_factor", 0.0))
    if not np.isfinite(profit_factor):
        profit_factor = 5.0
    score = (
        5.0 * float(metrics.get("total_return", 0.0))
        + 2.0 * (float(metrics.get("win_rate", 0.0)) - 0.50)
        - 3.0 * float(metrics.get("max_drawdown", 1.0))
        + 0.40 * math.log(max(profit_factor, 0.05))
        + 0.03 * math.log(max(trades, 1))
    )
    if gate_pass(metrics):
        score += 10.0
    elif trades < HARD_GATE["trade_count_min"]:
        score -= 2.0
    return float(score)


def base_backtest_config(
    label: TripleBarrierConfig,
    model_type: str,
    threshold: dict[str, float],
    risk: dict[str, Any] | None = None,
) -> BacktestConfig:
    values: dict[str, Any] = {
        "horizon_bars": label.horizon_bars,
        "take_profit_atr": label.take_profit_atr,
        "stop_loss_atr": label.stop_loss_atr,
        "fee_rate_per_fill": label.fee_rate_per_fill,
        "slippage_bps_per_fill": label.slippage_bps_per_fill,
        "signal_mode": "expected_bps" if model_type.startswith("dual_regression") else "probability",
        **threshold,
    }
    if risk:
        values.update(risk)
    return BacktestConfig(**values)


def evaluate_thresholds(
    predictions: pd.DataFrame,
    *,
    label: TripleBarrierConfig,
    model_type: str,
    fine: bool,
    risk: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    thresholds = (
        regression_thresholds(fine)
        if model_type.startswith("dual_regression")
        else probability_thresholds(fine)
    )
    rows: list[dict[str, Any]] = []
    working = predictions.copy()
    prediction_columns = (
        ["pred_long_bps", "pred_short_bps"]
        if model_type.startswith("dual_regression")
        else ["p_long", "p_short"]
    )
    # Purge validation-end signals whose maximum holding path would enter OOS.
    working.loc[working.index[-label.horizon_bars :], prediction_columns] = np.nan
    for threshold in thresholds:
        config = base_backtest_config(label, model_type, threshold, risk)
        _, metrics = run_prediction_backtest(working, config)
        rows.append(
            {
                **metrics,
                "threshold": threshold,
                "risk": risk or {},
                "gate_pass": gate_pass(metrics),
                "selection_score": score_metrics(metrics),
            }
        )
    return rows


def risk_configs() -> list[dict[str, Any]]:
    configs: list[dict[str, Any]] = [
        {"risk_per_trade": None, "max_leverage": 1.0},
    ]
    for risk in (0.0025, 0.0050, 0.0075, 0.0100):
        for leverage in (1.0, 2.0):
            configs.append({"risk_per_trade": risk, "max_leverage": leverage})
            configs.append(
                {
                    "risk_per_trade": risk,
                    "max_leverage": leverage,
                    "max_consecutive_losses": 3,
                    "loss_cooldown_bars": 16,
                }
            )
    configs.extend(
        [
            {
                "risk_per_trade": 0.005,
                "max_leverage": 2.0,
                "drawdown_pause_threshold": 0.10,
                "drawdown_cooldown_bars": 96,
            },
            {
                "risk_per_trade": 0.0075,
                "max_leverage": 2.0,
                "drawdown_pause_threshold": 0.15,
                "drawdown_cooldown_bars": 96,
            },
        ]
    )
    return configs


def serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(row, default=str, allow_nan=True))


def run_candidate(
    train: pd.DataFrame,
    validation_labeled: pd.DataFrame,
    validation_full: pd.DataFrame,
    *,
    features: list[str],
    feature_set_id: str,
    spec: dict[str, Any],
    label: TripleBarrierConfig,
    seed: int,
    fine: bool,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    validation_for_model = validation_full.merge(
        validation_labeled[
            ["ts", "direction_label", "long_outcome_bps", "short_outcome_bps"]
        ],
        on="ts",
        how="inner",
        validate="one_to_one",
    )
    predictions, predictive_metrics = train_and_predict(
        train,
        validation_for_model,
        features=features,
        spec=spec,
        horizon_bars=label.horizon_bars,
        seed=seed,
    )
    threshold_rows = evaluate_thresholds(
        predictions,
        label=label,
        model_type=spec["model_type"],
        fine=fine,
    )
    best = max(threshold_rows, key=lambda row: row["selection_score"])
    result = {
        "label_id": label_id(label),
        "label_config": asdict(label),
        "feature_set_id": feature_set_id,
        "feature_count": len(features),
        "model_spec": spec,
        "predictive_metrics": predictive_metrics,
        "best_threshold_metrics": best,
        "selection_score": best["selection_score"],
        "gate_pass": best["gate_pass"],
    }
    return result, predictions, threshold_rows


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    # Hard seal: the search process never loads OOS rows into its working frame.
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy().reset_index(drop=True)
    if pre_oos["ts"].max() != VALIDATION_END_EXCLUSIVE - pd.Timedelta(minutes=15):
        raise RuntimeError("pre-OOS search frame does not end at the locked boundary")
    del frame

    audit = json.loads(args.factor_audit.read_text(encoding="utf-8"))
    if audit.get("oos_target_revealed") is not False:
        raise RuntimeError("factor audit does not prove an unrevealed OOS target")
    stats = pd.read_csv(args.single_factor_audit)
    sets = feature_sets(audit, stats)
    validation_full = pre_oos.loc[
        (pre_oos["ts"] >= TRAIN_END_EXCLUSIVE)
        & (pre_oos["ts"] < VALIDATION_END_EXCLUSIVE)
    ].copy()

    labels = label_configs()
    label_cache: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
    label_diagnostics: list[dict[str, Any]] = []
    for label in labels:
        train, validation_labeled, diagnostics = prepare_label_frame(pre_oos, label)
        label_cache[label_id(label)] = (train, validation_labeled)
        label_diagnostics.append(diagnostics)
    write_json(
        args.output_dir / "label_diagnostics.json",
        {"labels": label_diagnostics, "oos_rows_loaded": 0},
    )

    stage1_path = args.output_dir / "stage1_model_frontier.csv"
    expected_stage1_rows = len(labels) * len(model_specs(1))
    if stage1_path.exists():
        stage1_frame = pd.read_csv(stage1_path)
    else:
        stage1_frame = pd.DataFrame()
    if len(stage1_frame) != expected_stage1_rows:
        stage1_rows: list[dict[str, Any]] = []
        stage1_threshold_rows: list[dict[str, Any]] = []
        stage1_features = sets["corr_pruned"]
        for label in labels:
            train, validation_labeled = label_cache[label_id(label)]
            for spec in model_specs(1):
                result, _, thresholds = run_candidate(
                    train,
                    validation_labeled,
                    validation_full,
                    features=stage1_features,
                    feature_set_id="corr_pruned",
                    spec=spec,
                    label=label,
                    seed=args.seed,
                    fine=False,
                )
                stage1_rows.append(serialize_row(result))
                for threshold in thresholds:
                    stage1_threshold_rows.append(
                        serialize_row(
                            {
                                "label_id": label_id(label),
                                "feature_set_id": "corr_pruned",
                                "model_spec_id": spec["id"],
                                **threshold,
                            }
                        )
                    )
            print(f"stage1 complete {label_id(label)}", flush=True)
        stage1_frame = pd.json_normalize(stage1_rows)
        stage1_frame.to_csv(stage1_path, index=False)
        pd.json_normalize(stage1_threshold_rows).to_parquet(
            args.output_dir / "stage1_threshold_trials.parquet", index=False
        )
    else:
        print(f"resume complete stage1 rows={len(stage1_frame)}", flush=True)

    best_by_label = (
        stage1_frame.sort_values("selection_score", ascending=False)
        .drop_duplicates("label_id")
        .head(5)
    )
    top_label_ids = best_by_label["label_id"].tolist()
    label_lookup = {label_id(label): label for label in labels}

    stage2_path = args.output_dir / "stage2_model_frontier.csv"
    expected_stage2_rows = len(top_label_ids) * len(sets) * len(model_specs(2))
    if stage2_path.exists():
        stage2_frame = pd.read_csv(stage2_path)
    else:
        stage2_frame = pd.DataFrame()
    if len(stage2_frame) != expected_stage2_rows:
        stage2_rows: list[dict[str, Any]] = []
        for current_label_id in top_label_ids:
            label = label_lookup[current_label_id]
            train, validation_labeled = label_cache[current_label_id]
            for feature_set_id, features in sets.items():
                for spec in model_specs(2):
                    result, _, _ = run_candidate(
                        train,
                        validation_labeled,
                        validation_full,
                        features=features,
                        feature_set_id=feature_set_id,
                        spec=spec,
                        label=label,
                        seed=args.seed,
                        fine=False,
                    )
                    stage2_rows.append(serialize_row(result))
            print(f"stage2 complete {current_label_id}", flush=True)
        stage2_frame = pd.json_normalize(stage2_rows)
        stage2_frame.to_csv(stage2_path, index=False)
    else:
        print(f"resume complete stage2 rows={len(stage2_frame)}", flush=True)

    detailed_candidates = (
        stage2_frame.sort_values("selection_score", ascending=False)
        .head(15)
        .to_dict("records")
    )
    detailed_rows: list[dict[str, Any]] = []
    for candidate_number, candidate in enumerate(detailed_candidates, start=1):
        current_label_id = str(candidate["label_id"])
        label = label_lookup[current_label_id]
        train, validation_labeled = label_cache[current_label_id]
        feature_set_id = str(candidate["feature_set_id"])
        features = sets[feature_set_id]
        spec_id = str(candidate["model_spec.id"])
        spec = next(item for item in model_specs(2) if item["id"] == spec_id)
        _, predictions, fine_threshold_rows = run_candidate(
            train,
            validation_labeled,
            validation_full,
            features=features,
            feature_set_id=feature_set_id,
            spec=spec,
            label=label,
            seed=args.seed,
            fine=True,
        )
        top_thresholds = sorted(
            fine_threshold_rows,
            key=lambda row: row["selection_score"],
            reverse=True,
        )[:3]
        for threshold_rank, threshold_row in enumerate(top_thresholds, start=1):
            threshold = threshold_row["threshold"]
            for risk in risk_configs():
                config = base_backtest_config(label, spec["model_type"], threshold, risk)
                working = predictions.copy()
                prediction_columns = (
                    ["pred_long_bps", "pred_short_bps"]
                    if str(spec["model_type"]).startswith("dual_regression")
                    else ["p_long", "p_short"]
                )
                working.loc[
                    working.index[-label.horizon_bars :], prediction_columns
                ] = np.nan
                _, metrics = run_prediction_backtest(working, config)
                detailed_rows.append(
                    serialize_row(
                        {
                            "candidate_rank_source": candidate_number,
                            "threshold_rank_source": threshold_rank,
                            "label_id": current_label_id,
                            "label_config": asdict(label),
                            "feature_set_id": feature_set_id,
                            "features": features,
                            "model_spec": spec,
                            "threshold": threshold,
                            "risk": risk,
                            "metrics": metrics,
                            "selection_score": score_metrics(metrics),
                            "gate_pass": gate_pass(metrics),
                        }
                    )
                )
        print(f"detailed tune complete {candidate_number}/15", flush=True)

    detailed_frame = pd.json_normalize(detailed_rows)
    detailed_frame.to_csv(args.output_dir / "detailed_validation_trials.csv", index=False)
    best_row = max(detailed_rows, key=lambda row: row["selection_score"])
    frozen_candidate = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "selection_scope": "train + validation only",
        "oos_rows_loaded_by_search": 0,
        "hard_gate": HARD_GATE,
        "candidate": best_row,
        "validation_gate_pass": bool(best_row["gate_pass"]),
        "status": "prefit candidate; OOS not revealed",
    }
    write_json(args.output_dir / "prefit_candidate.json", frozen_candidate)
    summary = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "candidate_factor_count": int(audit["candidate_factor_count"]),
        "feature_sets": {name: len(values) for name, values in sets.items()},
        "label_config_count": len(labels),
        "stage1_model_count": len(stage1_frame),
        "stage2_model_count": len(stage2_frame),
        "detailed_trial_count": len(detailed_rows),
        "top_label_ids": top_label_ids,
        "hard_gate": HARD_GATE,
        "best_validation": best_row,
        "validation_gate_pass_count": sum(bool(row["gate_pass"]) for row in detailed_rows),
        "oos_rows_loaded": 0,
        "next_gate": "walk-forward, seed, cost, and parameter-neighborhood prefit audit",
    }
    write_json(args.output_dir / "search_summary.json", summary)
    print(
        json.dumps(
            {
                "stage1_models": len(stage1_frame),
                "stage2_models": len(stage2_frame),
                "detailed_trials": len(detailed_rows),
                "validation_gate_pass_count": summary["validation_gate_pass_count"],
                "best_validation_metrics": best_row["metrics"],
                "best_label": best_row["label_id"],
                "best_model": best_row["model_spec"]["id"],
                "best_feature_set": best_row["feature_set_id"],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
