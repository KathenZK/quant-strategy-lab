from __future__ import annotations

import argparse
from pathlib import Path
import json

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, log_loss

from backtest_hype_lgbm import BacktestConfig, run_prediction_backtest, threshold_candidates
from hype_ml_common import ARTIFACTS_DIR, write_json


HARD_GATE = {
    "annualized_multiple_min": 10.0,
    "win_rate_min": 0.70,
    "max_drawdown_max": 0.20,
    "trade_count_min": 30,
}


def _select_feature_columns(frame: pd.DataFrame, manifest: dict) -> list[str]:
    coverage = manifest.get("factor_coverage", {})
    names = [name for name in manifest["factor_names"] if name in frame.columns and float(coverage.get(name, 0.0)) >= 0.95]
    if "atr_pct_14" not in names:
        raise RuntimeError("atr_pct_14 is required for executable labels and bracket simulation")
    return names


def _metric_score(metrics: dict[str, object]) -> tuple[int, int, float, float, float]:
    gate = (
        float(metrics.get("annualized_multiple", 0.0)) >= HARD_GATE["annualized_multiple_min"]
        and float(metrics.get("win_rate", 0.0)) >= HARD_GATE["win_rate_min"]
        and float(metrics.get("max_drawdown", 1.0)) <= HARD_GATE["max_drawdown_max"]
        and int(metrics.get("trade_count", 0)) >= HARD_GATE["trade_count_min"]
    )
    return (
        int(gate),
        int(metrics.get("trade_count", 0)) >= HARD_GATE["trade_count_min"],
        float(metrics.get("total_return", 0.0)),
        float(metrics.get("win_rate", 0.0)),
        -float(metrics.get("max_drawdown", 1.0)),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and audit HYPE 15m LightGBM classifier.")
    parser.add_argument("--input", type=Path, default=ARTIFACTS_DIR / "hype_15m_labeled_dataset.parquet")
    parser.add_argument("--dataset-manifest", type=Path, default=ARTIFACTS_DIR / "hype_15m_factor_dataset_manifest.json")
    parser.add_argument("--output-dir", type=Path, default=ARTIFACTS_DIR / "model")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    feature_columns = _select_feature_columns(frame, manifest)
    usable = frame.dropna(subset=[*feature_columns, "direction_label", "atr_pct_14"]).copy().reset_index(drop=True)
    usable = usable[usable["long_outcome_bps"].notna() & usable["short_outcome_bps"].notna()].reset_index(drop=True)
    if len(usable) < 1000:
        raise RuntimeError(f"too few usable labeled rows: {len(usable)}")

    train_end = int(len(usable) * 0.60)
    validation_end = int(len(usable) * 0.80)
    train = usable.iloc[:train_end]
    validation = usable.iloc[train_end:validation_end]
    oos = usable.iloc[validation_end:]
    X_train = train[feature_columns]
    y_train = train["direction_label"].astype(int) + 1
    X_validation = validation[feature_columns]
    y_validation = validation["direction_label"].astype(int) + 1

    model = lgb.LGBMClassifier(
        objective="multiclass",
        num_class=3,
        num_leaves=15,
        max_depth=5,
        learning_rate=0.03,
        n_estimators=2000,
        min_child_samples=100,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=42,
        n_jobs=-1,
        verbosity=-1,
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_validation, y_validation)],
        eval_metric="multi_logloss",
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )

    probabilities = model.predict_proba(usable[feature_columns], num_iteration=model.best_iteration_)
    prediction_frame = usable[["ts", "open", "high", "low", "close", "atr_pct_14", "funding_ts", "funding_rate", "direction_label"]].copy()
    prediction_frame["p_short"] = probabilities[:, 0]
    prediction_frame["p_flat"] = probabilities[:, 1]
    prediction_frame["p_long"] = probabilities[:, 2]
    prediction_frame.to_parquet(args.output_dir / "predictions.parquet", index=False)

    val_predictions = prediction_frame.iloc[train_end:validation_end].copy()
    val_backtest_frame = validation.merge(val_predictions[["ts", "p_short", "p_flat", "p_long"]], on="ts", how="left", validate="one_to_one")
    threshold_results: list[dict[str, object]] = []
    for long_threshold, short_threshold, margin in threshold_candidates():
        config = BacktestConfig(long_threshold=long_threshold, short_threshold=short_threshold, probability_margin=margin)
        trades, metrics = run_prediction_backtest(val_backtest_frame, config)
        threshold_results.append({**metrics, "long_threshold": long_threshold, "short_threshold": short_threshold, "probability_margin": margin, "trades_path": str(args.output_dir / f"validation_trades_{long_threshold:.2f}_{margin:.2f}.parquet")})
        trades.to_parquet(args.output_dir / f"validation_trades_{long_threshold:.2f}_{margin:.2f}.parquet", index=False)
    selected = sorted(threshold_results, key=_metric_score, reverse=True)[0]
    selected_config = BacktestConfig(
        long_threshold=float(selected["long_threshold"]),
        short_threshold=float(selected["short_threshold"]),
        probability_margin=float(selected["probability_margin"]),
    )

    split_frames = {"train": train, "validation": validation, "oos": oos}
    split_metrics: dict[str, object] = {}
    for split_name, split in split_frames.items():
        predicted = prediction_frame[prediction_frame["ts"].isin(split["ts"])]
        backtest_frame = split.merge(predicted[["ts", "p_short", "p_flat", "p_long"]], on="ts", how="left", validate="one_to_one")
        trades, metrics = run_prediction_backtest(backtest_frame, selected_config)
        trades.to_parquet(args.output_dir / f"{split_name}_trades.parquet", index=False)
        metrics["balanced_accuracy"] = balanced_accuracy_score(split["direction_label"].astype(int) + 1, predicted[["p_short", "p_flat", "p_long"]].to_numpy().argmax(axis=1))
        metrics["logloss"] = log_loss(split["direction_label"].astype(int) + 1, predicted[["p_short", "p_flat", "p_long"]])
        split_metrics[split_name] = metrics

    recent_slices: dict[str, object] = {}
    dataset_end = pd.Timestamp(prediction_frame["ts"].max())
    for label, days in (("1d", 1), ("7d", 7), ("1m", 30), ("3m", 90), ("6m", 180), ("1y", 365)):
        cutoff = dataset_end - pd.Timedelta(days=days)
        slice_frame = prediction_frame[prediction_frame["ts"] >= cutoff].copy()
        slice_frame = slice_frame.merge(usable[["ts", "open", "high", "low", "close", "atr_pct_14", "funding_ts", "funding_rate"]], on="ts", how="left", suffixes=("", "_label"))
        slice_frame = slice_frame.loc[:, ~slice_frame.columns.duplicated()]
        _, metrics = run_prediction_backtest(slice_frame, selected_config)
        metrics["start"] = slice_frame["ts"].min().isoformat() if not slice_frame.empty else None
        metrics["end"] = slice_frame["ts"].max().isoformat() if not slice_frame.empty else None
        recent_slices[label] = metrics

    model.booster_.save_model(str(args.output_dir / "model.txt"))
    feature_importance = pd.DataFrame(
        {
            "feature": model.booster_.feature_name(),
            "gain": model.booster_.feature_importance(importance_type="gain"),
            "split": model.booster_.feature_importance(importance_type="split"),
        }
    ).sort_values(["gain", "split"], ascending=False)
    feature_importance.to_csv(args.output_dir / "feature_importance.csv", index=False)
    report = {
        "family": "HYPE-15M-Factor-ML",
        "model": "LightGBM multiclass classifier",
        "feature_columns": feature_columns,
        "feature_count": len(feature_columns),
        "usable_rows": len(usable),
        "splits": {name: {"rows": len(split), "start": split["ts"].min().isoformat(), "end": split["ts"].max().isoformat()} for name, split in split_frames.items()},
        "best_iteration": int(model.best_iteration_),
        "feature_importance_path": str(args.output_dir / "feature_importance.csv"),
        "selected_validation_threshold": selected,
        "hard_gate": HARD_GATE,
        "split_metrics": split_metrics,
        "recent_slices_audit_only": recent_slices,
        "conclusion": "PASS-CANDIDATE" if all(_metric_score(split_metrics["oos"])[0:1]) else "HARD-GATE-FAILED",
        "promotion_status": "not promoted / not live-ready",
    }
    write_json(args.output_dir / "model_report.json", report)
    print(json.dumps({"features": len(feature_columns), "best_iteration": model.best_iteration_, "selected": selected, "oos": split_metrics["oos"], "conclusion": report["conclusion"]}, indent=2, default=str))


if __name__ == "__main__":
    main()
