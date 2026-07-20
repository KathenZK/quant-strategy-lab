from __future__ import annotations

import gc
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import duckdb
import lightgbm as lgb
import numpy as np
import pandas as pd


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import train_development_walk_forward as development  # noqa: E402


ROOT = development.ROOT
FAMILY_DIR = development.FAMILY_DIR
ARTIFACT_DIR = development.ARTIFACT_DIR
PANEL_ROOT = ARTIFACT_DIR / "multihorizon_factor_dataset/panel"
PANEL_MANIFEST = ARTIFACT_DIR / "multihorizon_factor_dataset/factor_dataset_manifest.json"
MATRIX_MANIFEST = ARTIFACT_DIR / "development_model_matrix_manifest.json"
PREFIT_LOCK = ARTIFACT_DIR / "freeze/bin-1h-mhcsml-v1-prefit-lock.json"
OUTPUT_ROOT = ARTIFACT_DIR / "freeze/final_models"
FINAL_MANIFEST = ARTIFACT_DIR / "freeze/bin-1h-mhcsml-v1-model-freeze.json"
FINAL_SHA = FINAL_MANIFEST.with_suffix(".sha256")
HORIZON = 48
SEEDS = (7, 17, 29, 42)
TRAIN_END = pd.Timestamp("2026-07-01T00:00:00Z")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")
INNER_DAYS = 120
PURGE_HOURS = 48

MODEL_SPECS = (
    {
        "identity": "short_return_regression_stable_full",
        "task": "short_return",
        "model_type": "regression",
        "feature_set": "stable_full",
    },
    {
        "identity": "short_mae_quantile_stable_full",
        "task": "short_mae",
        "model_type": "quantile",
        "feature_set": "stable_full",
    },
    {
        "identity": "short_event_classification_stable_full",
        "task": "short_event",
        "model_type": "classification",
        "feature_set": "stable_full",
    },
    {
        "identity": "short_return_classification_compact",
        "task": "short_return",
        "model_type": "classification",
        "feature_set": "compact",
    },
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def panel_files() -> list[Path]:
    files: list[Path] = []
    for directory in sorted(PANEL_ROOT.glob("year_month=*")):
        month = directory.name.removeprefix("year_month=")
        if month >= "2026-07":
            continue
        files.extend(sorted(directory.glob("*.parquet")))
    if not files:
        raise RuntimeError("no pre-July factor-panel files found")
    return files


def validate_lock() -> dict[str, Any]:
    if pd.Timestamp.now("UTC") >= PROSPECTIVE_START:
        raise RuntimeError("final models must be frozen before prospective OOS starts")
    lock = json.loads(PREFIT_LOCK.read_text(encoding="utf-8"))
    if lock.get("status") != "PASS":
        raise RuntimeError("prefit candidate lock is not PASS")
    if lock["prospective_oos"].get("outcomes_read"):
        raise RuntimeError("prefit lock reports prospective OOS outcome access")
    expected = {
        "horizon_hours": 48,
        "decision_frequency_hours": 8,
        "side_mode": "short_only",
        "confirmation_weight": 0.275,
        "confirmation_z_min": 0.4,
        "mae_penalty": 1.0,
        "event_penalty": 0.5,
        "utility_threshold": 2.5,
        "max_positions": 1,
        "gross_exposure": 0.45,
    }
    actual = lock["candidate_config"]
    mismatch = {
        key: (actual.get(key), value)
        for key, value in expected.items()
        if actual.get(key) != value
    }
    if mismatch:
        raise RuntimeError(f"candidate lock mismatch: {mismatch}")
    return lock


def load_training_frame(
    files: list[Path], features: list[str], labels: list[str]
) -> pd.DataFrame:
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '10GB'")
    source = "[" + ",".join(f"'{sql_path(path)}'" for path in files) + "]"
    feature_sql = ", ".join(f'CAST("{name}" AS FLOAT) AS "{name}"' for name in features)
    label_sql = ", ".join(f'CAST("{name}" AS FLOAT) AS "{name}"' for name in labels)
    frame = connection.execute(
        f"""
        SELECT
            epoch_ms(ts)::BIGINT AS ts_ms,
            symbol,
            {feature_sql},
            {label_sql}
        FROM read_parquet(
            {source}, hive_partitioning=false, union_by_name=true
        )
        WHERE universe_main
          AND ts < TIMESTAMPTZ '{TRAIN_END.isoformat()}'
          AND (floor(epoch(ts) / 3600)::BIGINT % 4) = 0
          AND label_path_valid_{HORIZON}h
          AND label_short_net_{HORIZON}h IS NOT NULL
          AND label_short_mae_{HORIZON}h IS NOT NULL
          AND label_short_squeeze_10pct_{HORIZON}h IS NOT NULL
        ORDER BY ts, symbol
        """
    ).fetch_df()
    connection.close()
    frame["ts"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    if frame.empty:
        raise RuntimeError("final training frame is empty")
    if frame["ts"].max() >= TRAIN_END:
        raise RuntimeError("final training frame crossed the locked boundary")
    if frame.duplicated(["ts", "symbol"]).any():
        raise RuntimeError("duplicate final-training keys")
    return frame


def target_values(frame: pd.DataFrame, task: str, model_type: str) -> np.ndarray:
    return development.transformed_target(
        frame, task=task, model_type=model_type, horizon=HORIZON
    )


def fit_one(
    *,
    frame: pd.DataFrame,
    x_all: pd.DataFrame,
    features: list[str],
    task: str,
    model_type: str,
    seed: int,
    model_path: Path,
) -> dict[str, Any]:
    y = target_values(frame, task, model_type)
    inner_start = frame["ts"].max() - pd.Timedelta(days=INNER_DAYS)
    fit_end = inner_start - pd.Timedelta(hours=PURGE_HOURS)
    fit_mask = frame["ts"].lt(fit_end).to_numpy()
    inner_mask = frame["ts"].ge(inner_start).to_numpy()
    if int(fit_mask.sum()) < 100_000 or int(inner_mask.sum()) < 10_000:
        raise RuntimeError("insufficient final nested split")
    parameters = development.lightgbm_parameters(
        task=task, model_type=model_type, seed=seed
    )
    if model_type == "classification":
        tuning_model: Any = lgb.LGBMClassifier(**parameters)
        final_class: Any = lgb.LGBMClassifier
    else:
        tuning_model = lgb.LGBMRegressor(**parameters)
        final_class = lgb.LGBMRegressor
    tuning_model.fit(
        x_all.loc[fit_mask, features],
        y[fit_mask],
        eval_set=[(x_all.loc[inner_mask, features], y[inner_mask])],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    best_iteration = int(tuning_model.best_iteration_)
    final_parameters = {**parameters, "n_estimators": best_iteration}
    final_model = final_class(**final_parameters)
    final_model.fit(x_all[features], y)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    final_model.booster_.save_model(str(model_path))
    inner_metric = float(tuning_model.best_score_["valid_0"][parameters["metric"]])
    result = {
        "task": task,
        "target": development.task_target(task, HORIZON),
        "target_transform": (
            "negative_mae" if task == "short_mae" else (
                "net_return_gt_zero" if model_type == "classification" and task == "short_return" else "identity"
            )
        ),
        "model_type": model_type,
        "seed": seed,
        "feature_count": len(features),
        "rows": len(frame),
        "fit_rows_for_iteration_selection": int(fit_mask.sum()),
        "inner_validation_rows": int(inner_mask.sum()),
        "inner_start": inner_start.isoformat(),
        "fit_end_exclusive": fit_end.isoformat(),
        "best_iteration": best_iteration,
        "inner_metric_name": parameters["metric"],
        "inner_metric_value": inner_metric,
        "final_refit_rows": len(frame),
        "model_parameters": final_parameters,
        "model_path": str(model_path.relative_to(ROOT)),
        "model_sha256": sha256(model_path),
    }
    del tuning_model, final_model, y
    gc.collect()
    return result


def main() -> None:
    lock = validate_lock()
    matrix_manifest = json.loads(MATRIX_MANIFEST.read_text(encoding="utf-8"))
    feature_sets = matrix_manifest["feature_sets"]
    stable_features = list(feature_sets["stable_full"])
    compact_features = list(feature_sets["compact"])
    if not set(compact_features).issubset(stable_features):
        raise RuntimeError("compact feature set is not a stable-full subset")
    files = panel_files()
    labels = [
        f"label_short_net_{HORIZON}h",
        f"label_short_mae_{HORIZON}h",
        f"label_short_squeeze_10pct_{HORIZON}h",
    ]
    frame = load_training_frame(files, stable_features, labels)
    x_all = frame[stable_features].astype("float32").copy()
    x_all.replace([np.inf, -np.inf], np.nan, inplace=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUTPUT_ROOT / "stable_full_features.json").write_text(
        json.dumps(stable_features, indent=2), encoding="utf-8"
    )
    (OUTPUT_ROOT / "compact_features.json").write_text(
        json.dumps(compact_features, indent=2), encoding="utf-8"
    )
    models: list[dict[str, Any]] = []
    for spec in MODEL_SPECS:
        features = list(feature_sets[spec["feature_set"]])
        for seed in SEEDS:
            identity = f"{spec['identity']}_s{seed}"
            print(f"fit final {identity}", flush=True)
            model_path = OUTPUT_ROOT / identity / "model.txt"
            result = fit_one(
                frame=frame,
                x_all=x_all,
                features=features,
                task=spec["task"],
                model_type=spec["model_type"],
                seed=seed,
                model_path=model_path,
            )
            models.append({"identity": identity, "feature_set": spec["feature_set"], **result})
            print(
                f"done {identity} best_iteration={result['best_iteration']}",
                flush=True,
            )
    source_partitions = [
        {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
        for path in files
    ]
    manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS",
        "freeze_stage": "final_model_freeze",
        "candidate_prefit_lock": str(PREFIT_LOCK.relative_to(ROOT)),
        "candidate_prefit_lock_sha256": sha256(PREFIT_LOCK),
        "candidate_config": lock["candidate_config"],
        "horizon_hours": HORIZON,
        "ensemble_seeds": list(SEEDS),
        "training_start": frame["ts"].min().isoformat(),
        "training_last_feature_ts": frame["ts"].max().isoformat(),
        "training_end_exclusive": TRAIN_END.isoformat(),
        "training_rows": len(frame),
        "training_symbols": int(frame["symbol"].nunique()),
        "reused_holdout_outcomes_read": True,
        "reused_holdout_role": (
            "final refit only after parameter lock; not used for candidate selection "
            "and not claimed as independent OOS"
        ),
        "freeze_gap_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "prospective_oos_start": PROSPECTIVE_START.isoformat(),
        "prospective_oos_end_exclusive": "2026-10-19T00:00:00+00:00",
        "panel_manifest": str(PANEL_MANIFEST.relative_to(ROOT)),
        "panel_manifest_sha256": sha256(PANEL_MANIFEST),
        "development_matrix_manifest": str(MATRIX_MANIFEST.relative_to(ROOT)),
        "development_matrix_manifest_sha256": sha256(MATRIX_MANIFEST),
        "feature_lists": {
            "stable_full": {
                "count": len(stable_features),
                "path": str((OUTPUT_ROOT / "stable_full_features.json").relative_to(ROOT)),
                "sha256": sha256(OUTPUT_ROOT / "stable_full_features.json"),
            },
            "compact": {
                "count": len(compact_features),
                "path": str((OUTPUT_ROOT / "compact_features.json").relative_to(ROOT)),
                "sha256": sha256(OUTPUT_ROOT / "compact_features.json"),
            },
        },
        "source_partitions": source_partitions,
        "models": models,
    }
    FINAL_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    digest = sha256(FINAL_MANIFEST)
    FINAL_SHA.write_text(f"{digest}  {FINAL_MANIFEST.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "models": len(models),
                "training_rows": len(frame),
                "manifest": str(FINAL_MANIFEST.relative_to(ROOT)),
                "sha256": digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
