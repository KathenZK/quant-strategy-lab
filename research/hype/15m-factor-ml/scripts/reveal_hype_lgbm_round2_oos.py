from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from audit_hype_15m_factors import VALIDATION_END_EXCLUSIVE
from audit_hype_lgbm_round2_prefit import (
    label_from_candidate,
    risk_from_candidate,
    threshold_from_candidate,
)
from backtest_hype_lgbm import run_prediction_backtest
from hype_ml_common import ARTIFACTS_DIR, add_triple_barrier_labels, write_json
from search_hype_lgbm_round2 import (
    HARD_GATE,
    base_backtest_config,
    clean_features,
    common_model_params,
    gate_pass,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-time locked OOS reveal for the frozen HYPE Round 2 ensemble."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ARTIFACTS_DIR / "hype_15m_factor_dataset.parquet",
    )
    parser.add_argument(
        "--frozen-candidate",
        type=Path,
        default=(
            ARTIFACTS_DIR
            / "model_round2_stable_ensemble_prefit_robustness/frozen_candidate.json"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR / "model_round2_final_oos",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frozen_candidate(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("prefit_pass") is not True:
        raise RuntimeError("prefit robustness did not pass; OOS reveal is forbidden")
    if payload.get("oos_revealed") is not False:
        raise RuntimeError("frozen candidate does not prove an unrevealed OOS")
    candidate = payload["candidate"]
    if not bool(candidate.get("gate_pass")):
        raise RuntimeError("frozen candidate did not pass its selection gate")
    return candidate


def fit_final_ensemble(
    train: pd.DataFrame,
    oos: pd.DataFrame,
    *,
    features: list[str],
    spec: dict[str, Any],
    horizon_bars: int,
    model_dir: Path,
) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame]:
    if spec["model_type"] != "dual_binary_weighted":
        raise RuntimeError("final trainer currently requires dual_binary_weighted")
    ensemble_seeds = [int(value) for value in spec.get("ensemble_seeds", [])]
    if not ensemble_seeds:
        raise RuntimeError("frozen candidate has no ensemble seeds")
    split = int(len(train) * 0.80)
    fit = train.iloc[: max(split - horizon_bars, 1)].copy()
    early = train.iloc[split:].copy()
    if len(fit) < 1000 or len(early) < 500:
        raise RuntimeError("insufficient pre-OOS rows for purged early stopping")
    X_fit = clean_features(fit, features)
    X_early = clean_features(early, features)
    X_train = clean_features(train, features)
    X_oos = clean_features(oos, features)
    prediction_members: dict[str, list[np.ndarray]] = {"long": [], "short": []}
    model_rows: list[dict[str, Any]] = []
    importance_rows: list[dict[str, Any]] = []
    model_dir.mkdir(parents=True, exist_ok=True)

    for seed in ensemble_seeds:
        for direction in ("long", "short"):
            target_column = f"{direction}_outcome_bps"
            params = common_model_params(spec, seed)
            preliminary = lgb.LGBMClassifier(
                objective="binary",
                class_weight="balanced",
                **params,
            )
            magnitude = fit[target_column].abs()
            scale = max(float(magnitude.median()), 1.0)
            sample_weight = (0.25 + magnitude / scale).clip(0.25, 5.0)
            preliminary.fit(
                X_fit,
                fit[target_column].gt(0).astype(int),
                sample_weight=sample_weight,
                eval_set=[(X_early, early[target_column].gt(0).astype(int))],
                eval_metric="binary_logloss",
                callbacks=[lgb.early_stopping(100, verbose=False)],
            )
            best_iteration = max(int(preliminary.best_iteration_), 1)
            final_params = {
                **common_model_params(spec, seed),
                "n_estimators": best_iteration,
            }
            final_model = lgb.LGBMClassifier(
                objective="binary",
                class_weight="balanced",
                **final_params,
            )
            full_magnitude = train[target_column].abs()
            full_scale = max(float(full_magnitude.median()), 1.0)
            full_weight = (0.25 + full_magnitude / full_scale).clip(0.25, 5.0)
            final_model.fit(
                X_train,
                train[target_column].gt(0).astype(int),
                sample_weight=full_weight,
            )
            probability = final_model.predict_proba(X_oos)[:, 1]
            prediction_members[direction].append(probability)
            model_path = model_dir / f"{direction}_seed_{seed}.txt"
            final_model.booster_.save_model(str(model_path))
            model_rows.append(
                {
                    "direction": direction,
                    "seed": seed,
                    "best_iteration_from_purged_early_stop": best_iteration,
                    "fit_rows": len(fit),
                    "early_stop_rows": len(early),
                    "final_train_rows": len(train),
                    "model_path": str(model_path),
                    "model_sha256": file_sha256(model_path),
                }
            )
            gain = final_model.booster_.feature_importance(importance_type="gain")
            split_importance = final_model.booster_.feature_importance(
                importance_type="split"
            )
            for feature, gain_value, split_value in zip(
                features, gain, split_importance, strict=True
            ):
                importance_rows.append(
                    {
                        "direction": direction,
                        "seed": seed,
                        "feature": feature,
                        "gain": float(gain_value),
                        "split": int(split_value),
                    }
                )

    predictions = oos[
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
    predictions["p_long"] = np.mean(prediction_members["long"], axis=0)
    predictions["p_short"] = np.mean(prediction_members["short"], axis=0)
    predictions["p_flat"] = 1.0 - np.maximum(
        predictions["p_long"], predictions["p_short"]
    )
    predictions.loc[
        predictions.index[-horizon_bars:], ["p_long", "p_short", "p_flat"]
    ] = np.nan
    importance = pd.DataFrame(importance_rows)
    aggregated = (
        importance.groupby(["direction", "feature"], as_index=False)
        .agg(gain_mean=("gain", "mean"), gain_std=("gain", "std"), split_mean=("split", "mean"))
        .sort_values(["direction", "gain_mean"], ascending=[True, False])
    )
    return predictions, model_rows, aggregated


def slice_metrics(
    predictions: pd.DataFrame,
    *,
    config: Any,
) -> dict[str, Any]:
    end = pd.Timestamp(predictions["ts"].max())
    result: dict[str, Any] = {}
    windows = {
        "1d": pd.Timedelta(days=1),
        "7d": pd.Timedelta(days=7),
        "1m": pd.Timedelta(days=30),
        "3m": pd.Timedelta(days=90),
        "6m": pd.Timedelta(days=180),
        "1y": pd.Timedelta(days=365),
    }
    oos_start = pd.Timestamp(predictions["ts"].min())
    for name, delta in windows.items():
        requested_start = end - delta
        if requested_start < oos_start:
            result[name] = {
                "available": False,
                "reason": "locked OOS is shorter than requested window",
                "oos_start": oos_start,
                "requested_start": requested_start,
            }
            continue
        current = predictions.loc[predictions["ts"] >= requested_start].copy()
        trades, metrics = run_prediction_backtest(current, config)
        result[name] = {
            "available": True,
            "start": current["ts"].min(),
            "end": current["ts"].max(),
            "rows": len(current),
            "metrics": metrics,
            "trade_count": len(trades),
        }
    return result


def buy_and_hold_metrics(oos: pd.DataFrame, config: Any) -> dict[str, float]:
    slip = float(config.slippage_bps_per_fill) / 10_000.0
    entry = float(oos.iloc[0]["open"]) * (1.0 + slip)
    exit_price = float(oos.iloc[-1]["close"]) * (1.0 - slip)
    gross = exit_price / entry - 1.0
    funding = oos[["funding_ts", "funding_rate"]].dropna().drop_duplicates(
        "funding_ts"
    )
    funding_return = -float(funding["funding_rate"].sum())
    net = gross - 2.0 * float(config.fee_rate_per_fill) + funding_return
    return {
        "entry_price_after_slippage": entry,
        "exit_price_after_slippage": exit_price,
        "gross_return": gross,
        "fee_return": 2.0 * float(config.fee_rate_per_fill),
        "funding_return": funding_return,
        "net_return": net,
    }


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate = load_frozen_candidate(args.frozen_candidate)
    label = label_from_candidate(candidate)
    features = list(candidate["features"])
    spec = dict(candidate["model_spec"])
    threshold = threshold_from_candidate(candidate)
    risk = risk_from_candidate(candidate)
    config = base_backtest_config(
        label, str(spec["model_type"]), threshold, risk
    )

    # The full dataset is loaded only after the immutable prefit gate above passes.
    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    pre_oos = frame.loc[frame["ts"] < VALIDATION_END_EXCLUSIVE].copy()
    oos = frame.loc[frame["ts"] >= VALIDATION_END_EXCLUSIVE].copy()
    if pre_oos.empty or oos.empty:
        raise RuntimeError("train or locked OOS partition is empty")
    labeled_train = add_triple_barrier_labels(pre_oos, label)
    labeled_train = labeled_train.iloc[: -label.horizon_bars].copy()
    labeled_train = labeled_train.loc[
        labeled_train["long_outcome_bps"].notna()
        & labeled_train["short_outcome_bps"].notna()
    ].reset_index(drop=True)

    predictions, model_rows, importance = fit_final_ensemble(
        labeled_train,
        oos.reset_index(drop=True),
        features=features,
        spec=spec,
        horizon_bars=label.horizon_bars,
        model_dir=args.output_dir / "models",
    )
    trades, metrics = run_prediction_backtest(predictions, config)
    oos_gate_pass = gate_pass(metrics)
    predictions.to_parquet(args.output_dir / "oos_predictions.parquet", index=False)
    trades.to_parquet(args.output_dir / "oos_trades.parquet", index=False)
    importance.to_csv(args.output_dir / "feature_importance.csv", index=False)
    model_manifest = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "frozen_candidate_source": str(args.frozen_candidate),
        "frozen_candidate_sha256": file_sha256(args.frozen_candidate),
        "dataset_source": str(args.input),
        "dataset_sha256": file_sha256(args.input),
        "features": features,
        "feature_count": len(features),
        "model_spec": spec,
        "label_config": asdict(label),
        "threshold": threshold,
        "risk": risk,
        "models": model_rows,
    }
    write_json(args.output_dir / "model_manifest.json", model_manifest)
    report = {
        "family": "HYPE-15M-Factor-ML",
        "round": 2,
        "reveal_type": "one-time locked OOS",
        "oos_revealed": True,
        "oos_start": oos["ts"].min(),
        "oos_end": oos["ts"].max(),
        "oos_rows": len(oos),
        "purged_oos_tail_bars": label.horizon_bars,
        "pre_oos_train_rows": len(labeled_train),
        "hard_gate": HARD_GATE,
        "oos_metrics": metrics,
        "oos_hard_gate_pass": oos_gate_pass,
        "buy_and_hold": buy_and_hold_metrics(oos, config),
        "recent_oos_slices": slice_metrics(predictions, config=config),
        "status": (
            "OOS hard gate passed; research candidate only, not promoted"
            if oos_gate_pass
            else "HARD-GATE-FAILED / not promoted / not live-ready"
        ),
        "no_oos_retuning_allowed": True,
        "artifacts": {
            "predictions": str(args.output_dir / "oos_predictions.parquet"),
            "trades": str(args.output_dir / "oos_trades.parquet"),
            "feature_importance": str(args.output_dir / "feature_importance.csv"),
            "model_manifest": str(args.output_dir / "model_manifest.json"),
        },
    }
    write_json(args.output_dir / "oos_report.json", report)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
