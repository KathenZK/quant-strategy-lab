from __future__ import annotations

import argparse
from pathlib import Path
import json

import lightgbm as lgb
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, log_loss

from backtest_hype_lgbm import BacktestConfig, run_prediction_backtest
from hype_ml_common import ARTIFACTS_DIR, write_json
from train_hype_lgbm import _select_feature_columns


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit fixed HYPE LightGBM configuration across random seeds.")
    parser.add_argument("--input", type=Path, default=ARTIFACTS_DIR / "hype_15m_labeled_dataset.parquet")
    parser.add_argument("--dataset-manifest", type=Path, default=ARTIFACTS_DIR / "hype_15m_factor_dataset_manifest.json")
    parser.add_argument("--model-report", type=Path, default=ARTIFACTS_DIR / "model/model_report.json")
    parser.add_argument("--output", type=Path, default=ARTIFACTS_DIR / "model/robustness.json")
    args = parser.parse_args()

    frame = pd.read_parquet(args.input).sort_values("ts").reset_index(drop=True)
    manifest = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    feature_columns = _select_feature_columns(frame, manifest)
    usable = frame.dropna(subset=[*feature_columns, "direction_label", "atr_pct_14", "long_outcome_bps", "short_outcome_bps"]).reset_index(drop=True)
    train_end = int(len(usable) * 0.60)
    validation_end = int(len(usable) * 0.80)
    train = usable.iloc[:train_end]
    validation = usable.iloc[train_end:validation_end]
    oos = usable.iloc[validation_end:]
    report = json.loads(args.model_report.read_text(encoding="utf-8"))
    selected = report["selected_validation_threshold"]
    config = BacktestConfig(
        long_threshold=float(selected["long_threshold"]),
        short_threshold=float(selected["short_threshold"]),
        probability_margin=float(selected["probability_margin"]),
    )

    results: list[dict[str, object]] = []
    for seed in (7, 17, 29, 42):
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
            random_state=seed,
            n_jobs=-1,
            verbosity=-1,
        )
        model.fit(
            train[feature_columns],
            train["direction_label"].astype(int) + 1,
            eval_set=[(validation[feature_columns], validation["direction_label"].astype(int) + 1)],
            eval_metric="multi_logloss",
            callbacks=[lgb.early_stopping(100, verbose=False)],
        )
        probabilities = model.predict_proba(oos[feature_columns], num_iteration=model.best_iteration_)
        predicted = oos[["ts", "open", "high", "low", "close", "atr_pct_14", "funding_ts", "funding_rate", "direction_label"]].copy()
        predicted["p_short"] = probabilities[:, 0]
        predicted["p_flat"] = probabilities[:, 1]
        predicted["p_long"] = probabilities[:, 2]
        _, metrics = run_prediction_backtest(predicted, config)
        metrics.update(
            {
                "seed": seed,
                "best_iteration": int(model.best_iteration_),
                "balanced_accuracy": balanced_accuracy_score(oos["direction_label"].astype(int) + 1, probabilities.argmax(axis=1)),
                "logloss": log_loss(oos["direction_label"].astype(int) + 1, probabilities),
            }
        )
        results.append(metrics)

    payload = {
        "family": "HYPE-15M-Factor-ML",
        "fixed_threshold_source": str(args.model_report),
        "feature_count": len(feature_columns),
        "oos_rows": len(oos),
        "seeds": results,
        "hard_gate": report["hard_gate"],
        "all_seeds_meet_hard_gate": all(
            row["annualized_multiple"] >= report["hard_gate"]["annualized_multiple_min"]
            and row["win_rate"] >= report["hard_gate"]["win_rate_min"]
            and row["max_drawdown"] <= report["hard_gate"]["max_drawdown_max"]
            and row["trade_count"] >= report["hard_gate"]["trade_count_min"]
            for row in results
        ),
    }
    write_json(args.output, payload)
    print(json.dumps(payload, indent=2, default=str))


if __name__ == "__main__":
    main()
