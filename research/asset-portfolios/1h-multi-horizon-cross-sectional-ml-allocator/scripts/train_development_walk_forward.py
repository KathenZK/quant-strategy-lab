from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MATRIX_ROOT = ARTIFACT_DIR / "development_model_matrix_4h"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "development_model_matrix_manifest.json"
OUTPUT_ROOT = ARTIFACT_DIR / "development_walk_forward"
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
PURGE_HOURS = 48
INNER_VALIDATION_DAYS = 120
HORIZONS = (4, 8, 12, 24, 48)
TASKS = (
    "long_return",
    "short_return",
    "long_mae",
    "short_mae",
    "long_event",
    "short_event",
)
MODEL_TYPES = (
    "regression",
    "regression_l2",
    "huber",
    "quantile",
    "classification",
    "ranker",
    "ridge",
)
FOLDS: tuple[tuple[str, str, str], ...] = (
    ("wf_2023_h1", "2023-01-01T00:00:00Z", "2023-07-01T00:00:00Z"),
    ("wf_2023_h2", "2023-07-01T00:00:00Z", "2024-01-01T00:00:00Z"),
    ("wf_2024_h1", "2024-01-01T00:00:00Z", "2024-07-01T00:00:00Z"),
    ("wf_2024_h2", "2024-07-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("wf_2025_h1", "2025-01-01T00:00:00Z", "2025-07-01T00:00:00Z"),
    ("wf_2025_h2", "2025-07-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("wf_2026_q1", "2026-01-01T00:00:00Z", "2026-04-01T00:00:00Z"),
)
SPARSE_PREFIX = "donchian_breakout_strength_"
RULE_FEATURES = (
    "cs_rank_ret_24",
    "cs_rank_ret_168",
    "cs_rank_ema_spread_24_96",
    "cs_rank_funding_rate",
    "cs_rank_realized_vol_24",
    "cs_rank_mark_premium",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train leakage-safe nested rolling development OOF models."
    )
    parser.add_argument("--tasks", nargs="+", choices=TASKS, required=True)
    parser.add_argument(
        "--model-types", nargs="+", choices=MODEL_TYPES, required=True
    )
    parser.add_argument(
        "--horizons", nargs="+", type=int, choices=HORIZONS, required=True
    )
    parser.add_argument("--feature-set", default="compact")
    parser.add_argument("--folds", nargs="+", default=[fold[0] for fold in FOLDS])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-window-days", type=int)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(feature_set: str) -> tuple[dict[str, Any], list[str]]:
    manifest = json.loads(MATRIX_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise RuntimeError("development matrix manifest is not PASS")
    if not manifest.get("physical_outcome_isolation"):
        raise RuntimeError("development matrix lacks physical outcome isolation")
    if manifest.get("development_end_exclusive") != DEVELOPMENT_END.isoformat():
        raise RuntimeError("unexpected development boundary")
    if manifest.get("reused_holdout_outcomes_read"):
        raise RuntimeError("development matrix accessed reused-holdout outcomes")
    if manifest.get("prospective_oos_outcomes_read"):
        raise RuntimeError("development matrix accessed prospective OOS outcomes")
    sets = manifest.get("feature_sets", {})
    if feature_set not in sets or feature_set == "sparse_event_features":
        raise RuntimeError(f"unknown model feature set: {feature_set}")
    return manifest, list(sets[feature_set])


def matrix_glob() -> Path:
    path = MATRIX_ROOT / "**/*.parquet"
    if not list(MATRIX_ROOT.glob("**/*.parquet")):
        raise RuntimeError(f"development matrix missing: {path}")
    return path


def horizon_columns(horizon: int) -> list[str]:
    return [
        f"label_path_valid_{horizon}h",
        f"label_funding_sum_{horizon}h",
        f"label_gross_return_{horizon}h",
        f"label_long_net_{horizon}h",
        f"label_short_net_{horizon}h",
        f"label_long_relative_{horizon}h",
        f"label_short_relative_{horizon}h",
        f"label_long_mae_{horizon}h",
        f"label_long_mfe_{horizon}h",
        f"label_short_mae_{horizon}h",
        f"label_short_mfe_{horizon}h",
        f"label_short_squeeze_10pct_{horizon}h",
        f"label_short_squeeze_20pct_{horizon}h",
        f"label_long_crash_10pct_{horizon}h",
        f"label_long_crash_20pct_{horizon}h",
    ]


def task_target(task: str, horizon: int) -> str:
    targets = {
        "long_return": f"label_long_net_{horizon}h",
        "short_return": f"label_short_net_{horizon}h",
        "long_mae": f"label_long_mae_{horizon}h",
        "short_mae": f"label_short_mae_{horizon}h",
        "long_event": f"label_long_crash_10pct_{horizon}h",
        "short_event": f"label_short_squeeze_10pct_{horizon}h",
    }
    return targets[task]


def validate_task_model(task: str, model_type: str) -> None:
    allowed = {
        "long_return": set(MODEL_TYPES),
        "short_return": set(MODEL_TYPES),
        "long_mae": {"regression", "quantile", "ridge"},
        "short_mae": {"regression", "quantile", "ridge"},
        "long_event": {"classification"},
        "short_event": {"classification"},
    }
    if model_type not in allowed[task]:
        raise ValueError(f"model {model_type} is not supported for task {task}")


def load_slice(
    connection: duckdb.DuckDBPyConnection,
    *,
    features: list[str],
    horizon: int,
    start: pd.Timestamp | None,
    end: pd.Timestamp,
) -> pd.DataFrame:
    selected = list(dict.fromkeys(features + list(RULE_FEATURES)))
    feature_sql = ", ".join(f'"{name}"' for name in selected)
    labels_sql = ", ".join(horizon_columns(horizon))
    predicates = [f"ts < TIMESTAMPTZ '{end.isoformat()}'"]
    if start is not None:
        predicates.append(f"ts >= TIMESTAMPTZ '{start.isoformat()}'")
    frame = connection.execute(
        f"""
        SELECT
            epoch_ms(ts)::BIGINT AS ts_ms,
            symbol,
            {feature_sql},
            {labels_sql}
        FROM read_parquet(
            '{sql_path(matrix_glob())}',
            hive_partitioning=false,
            union_by_name=true
        )
        WHERE {' AND '.join(predicates)}
        ORDER BY ts, symbol
        """
    ).fetch_df()
    frame["ts"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    return frame


def clean_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    result = frame[features].astype("float32").copy()
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    sparse = [name for name in features if name.startswith(SPARSE_PREFIX)]
    if sparse:
        result[sparse] = result[sparse].fillna(0.0)
    return result


def group_sizes(frame: pd.DataFrame) -> np.ndarray:
    return frame.groupby("ts", sort=False).size().to_numpy(dtype="int32")


def cross_sectional_percentile(frame: pd.DataFrame, target: str) -> pd.Series:
    return frame.groupby("ts", sort=False)[target].rank(
        method="average", pct=True, na_option="keep"
    )


def transformed_target(
    frame: pd.DataFrame, *, task: str, model_type: str, horizon: int
) -> np.ndarray:
    target = task_target(task, horizon)
    raw = frame[target]
    if task in {"long_mae", "short_mae"}:
        raw = -raw
    if task in {"long_event", "short_event"}:
        return raw.to_numpy(dtype="int8")
    if model_type == "classification":
        return raw.gt(0.0).to_numpy(dtype="int8")
    if model_type == "ranker":
        percentile = cross_sectional_percentile(
            frame.assign(_rank_target=raw), "_rank_target"
        )
        return np.minimum(
            np.floor(percentile.to_numpy(dtype="float64") * 5.0), 4.0
        ).astype("int8")
    return raw.to_numpy(dtype="float32")


def lightgbm_parameters(
    *, task: str, model_type: str, seed: int
) -> dict[str, Any]:
    common: dict[str, Any] = {
        "n_estimators": 500,
        "learning_rate": 0.04,
        "num_leaves": 31,
        "max_depth": -1,
        "min_child_samples": 300,
        "subsample": 0.80,
        "subsample_freq": 1,
        "colsample_bytree": 0.75,
        "reg_alpha": 0.10,
        "reg_lambda": 1.00,
        "random_state": seed,
        "n_jobs": 8,
        "deterministic": True,
        "force_col_wise": True,
        "verbosity": -1,
    }
    if model_type == "regression":
        return {**common, "objective": "regression_l1", "metric": "l1"}
    if model_type == "regression_l2":
        return {**common, "objective": "regression", "metric": "l2"}
    if model_type == "huber":
        return {**common, "objective": "huber", "metric": "l1", "alpha": 0.90}
    if model_type == "quantile":
        alpha = 0.80 if task in {"long_mae", "short_mae"} else 0.30
        return {
            **common,
            "objective": "quantile",
            "metric": "quantile",
            "alpha": alpha,
        }
    if model_type == "classification":
        return {**common, "objective": "binary", "metric": "binary_logloss"}
    if model_type == "ranker":
        return {**common, "objective": "lambdarank", "metric": "ndcg"}
    raise ValueError(f"not a LightGBM model: {model_type}")


def predictive_diagnostics(
    frame: pd.DataFrame,
    *,
    score: np.ndarray,
    task: str,
    horizon: int,
) -> dict[str, Any]:
    target = task_target(task, horizon)
    observed = -frame[target] if task in {"long_mae", "short_mae"} else frame[target]
    valid = observed.notna() & np.isfinite(score)
    if int(valid.sum()) < 2:
        return {"rows": int(valid.sum()), "spearman": None}
    correlation = spearmanr(
        score[valid.to_numpy()],
        observed.loc[valid].to_numpy(dtype="float64"),
        nan_policy="omit",
    ).statistic
    by_time = pd.DataFrame(
        {
            "ts": frame.loc[valid, "ts"].to_numpy(),
            "score": score[valid.to_numpy()],
            "target": observed.loc[valid].to_numpy(dtype="float64"),
        }
    )
    hourly_ic = by_time.groupby("ts", sort=False).apply(
        lambda group: group["score"].corr(group["target"], method="spearman"),
        include_groups=False,
    )
    return {
        "rows": int(valid.sum()),
        "spearman": None if not np.isfinite(correlation) else float(correlation),
        "mean_cross_sectional_rank_ic": float(hourly_ic.mean()),
        "positive_cross_sectional_rank_ic_share": float(hourly_ic.gt(0.0).mean()),
    }


def fit_predict(
    *,
    task: str,
    model_type: str,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: list[str],
    horizon: int,
    seed: int,
    model_path: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    validate_task_model(task, model_type)
    target = task_target(task, horizon)
    train = train.loc[train[target].notna()].copy()
    inner_start = train["ts"].max() - pd.Timedelta(days=INNER_VALIDATION_DAYS)
    fit_end = inner_start - pd.Timedelta(hours=PURGE_HOURS)
    fit = train.loc[train["ts"] < fit_end].copy()
    inner = train.loc[train["ts"] >= inner_start].copy()
    if len(fit) < 100_000 or len(inner) < 10_000:
        raise RuntimeError(
            f"insufficient nested time split: fit={len(fit)} inner={len(inner)}"
        )
    x_fit = clean_features(fit, features)
    x_inner = clean_features(inner, features)
    x_validation = clean_features(validation, features)
    y_fit = transformed_target(
        fit, task=task, model_type=model_type, horizon=horizon
    )
    y_inner = transformed_target(
        inner, task=task, model_type=model_type, horizon=horizon
    )
    best_iteration: int | None = None
    if model_type == "ridge":
        model: Any = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
                ("model", Ridge(alpha=10.0, solver="lsqr")),
            ]
        )
        model.fit(x_fit, y_fit)
        score = model.predict(x_validation).astype("float64")
        joblib.dump(model, model_path)
    elif model_type in {"regression", "regression_l2", "huber", "quantile"}:
        model = lgb.LGBMRegressor(
            **lightgbm_parameters(task=task, model_type=model_type, seed=seed)
        )
        model.fit(
            x_fit,
            y_fit,
            eval_set=[(x_inner, y_inner)],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        score = model.predict(x_validation, num_iteration=model.best_iteration_)
        best_iteration = int(model.best_iteration_)
        model.booster_.save_model(str(model_path))
    elif model_type == "classification":
        model = lgb.LGBMClassifier(
            **lightgbm_parameters(task=task, model_type=model_type, seed=seed)
        )
        model.fit(
            x_fit,
            y_fit,
            eval_set=[(x_inner, y_inner)],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        score = model.predict_proba(
            x_validation, num_iteration=model.best_iteration_
        )[:, 1]
        best_iteration = int(model.best_iteration_)
        model.booster_.save_model(str(model_path))
    else:
        model = lgb.LGBMRanker(
            **lightgbm_parameters(task=task, model_type=model_type, seed=seed)
        )
        model.fit(
            x_fit,
            y_fit,
            group=group_sizes(fit),
            eval_set=[(x_inner, y_inner)],
            eval_group=[group_sizes(inner)],
            eval_at=[1, 3, 5],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        score = model.predict(x_validation, num_iteration=model.best_iteration_)
        best_iteration = int(model.best_iteration_)
        model.booster_.save_model(str(model_path))
    diagnostics = {
        "train_rows_before_inner_split": len(train),
        "fit_rows": len(fit),
        "inner_validation_rows": len(inner),
        "validation_rows": len(validation),
        "inner_start": inner_start.isoformat(),
        "fit_end_exclusive": fit_end.isoformat(),
        "best_iteration": best_iteration,
        "predictive": predictive_diagnostics(
            validation,
            score=np.asarray(score),
            task=task,
            horizon=horizon,
        ),
    }
    return np.asarray(score, dtype="float64"), diagnostics


def prediction_frame(
    validation: pd.DataFrame,
    *,
    score: np.ndarray,
    task: str,
    model_type: str,
    horizon: int,
    fold_id: str,
    feature_set: str,
    seed: int,
) -> pd.DataFrame:
    columns = ["ts", "symbol"]
    if task in {"long_return", "short_return"}:
        columns.extend(RULE_FEATURES)
        columns.extend(horizon_columns(horizon))
    result = validation[list(dict.fromkeys(columns))].copy()
    result["score"] = score.astype("float32")
    result["task"] = task
    result["model_type"] = model_type
    result["horizon"] = horizon
    result["fold_id"] = fold_id
    result["feature_set"] = feature_set
    result["seed"] = seed
    return result


def main() -> None:
    args = parse_args()
    manifest, features = validate_manifest(args.feature_set)
    selected_folds = [fold for fold in FOLDS if fold[0] in set(args.folds)]
    if len(selected_folds) != len(set(args.folds)):
        raise RuntimeError(f"unknown fold ids: {args.folds}")
    for task in args.tasks:
        for model_type in args.model_types:
            validate_task_model(task, model_type)
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    completed: list[str] = []
    for horizon in args.horizons:
        for fold_id, validation_start_text, validation_end_text in selected_folds:
            validation_start = pd.Timestamp(validation_start_text)
            validation_end = pd.Timestamp(validation_end_text)
            if validation_end > DEVELOPMENT_END:
                raise RuntimeError(f"fold crosses development boundary: {fold_id}")
            train_end = validation_start - pd.Timedelta(hours=PURGE_HOURS)
            train_start = (
                train_end - pd.Timedelta(days=args.train_window_days)
                if args.train_window_days is not None
                else None
            )
            train = load_slice(
                connection,
                features=features,
                horizon=horizon,
                start=train_start,
                end=train_end,
            )
            validation = load_slice(
                connection,
                features=features,
                horizon=horizon,
                start=validation_start,
                end=validation_end,
            )
            for task in args.tasks:
                for model_type in args.model_types:
                    window_suffix = (
                        f"_tw{args.train_window_days}d"
                        if args.train_window_days is not None
                        else ""
                    )
                    identity = (
                        f"{task}_{model_type}_{args.feature_set}_{horizon}h_"
                        f"{fold_id}{window_suffix}_s{args.seed}"
                    )
                    output_directory = OUTPUT_ROOT / identity
                    prediction_path = output_directory / "predictions.parquet"
                    diagnostic_path = output_directory / "diagnostics.json"
                    suffix = ".joblib" if model_type == "ridge" else ".txt"
                    model_path = output_directory / f"model{suffix}"
                    if (
                        prediction_path.exists()
                        and diagnostic_path.exists()
                        and not args.overwrite
                    ):
                        print(f"skip {identity}", flush=True)
                        continue
                    output_directory.mkdir(parents=True, exist_ok=True)
                    print(
                        f"fit {identity} train={len(train)} validation={len(validation)}",
                        flush=True,
                    )
                    score, diagnostics = fit_predict(
                        task=task,
                        model_type=model_type,
                        train=train,
                        validation=validation,
                        features=features,
                        horizon=horizon,
                        seed=args.seed,
                        model_path=model_path,
                    )
                    predictions = prediction_frame(
                        validation,
                        score=score,
                        task=task,
                        model_type=model_type,
                        horizon=horizon,
                        fold_id=fold_id,
                        feature_set=args.feature_set,
                        seed=args.seed,
                    )
                    predictions.to_parquet(
                        prediction_path, index=False, compression="zstd"
                    )
                    payload = {
                        "family": (
                            "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator"
                        ),
                        "identity": identity,
                        "generated_at": pd.Timestamp.now("UTC").isoformat(),
                        "development_only": True,
                        "reused_holdout_outcomes_read": False,
                        "prospective_oos_outcomes_read": False,
                        "matrix_manifest": str(MATRIX_MANIFEST_PATH.relative_to(ROOT)),
                        "matrix_manifest_sha256": sha256(MATRIX_MANIFEST_PATH),
                        "matrix_rows": manifest["rows"],
                        "task": task,
                        "target": task_target(task, horizon),
                        "model_type": model_type,
                        "feature_set": args.feature_set,
                        "feature_count": len(features),
                        "features": features,
                        "horizon_hours": horizon,
                        "fold_id": fold_id,
                        "validation_start": validation_start.isoformat(),
                        "validation_end_exclusive": validation_end.isoformat(),
                        "train_start_inclusive": (
                            train_start.isoformat() if train_start is not None else None
                        ),
                        "train_end_exclusive": train_end.isoformat(),
                        "train_window_days": args.train_window_days,
                        "purge_hours": PURGE_HOURS,
                        "inner_validation_days": INNER_VALIDATION_DAYS,
                        "seed": args.seed,
                        "model_parameters": (
                            {"ridge_alpha": 10.0, "solver": "lsqr"}
                            if model_type == "ridge"
                            else lightgbm_parameters(
                                task=task, model_type=model_type, seed=args.seed
                            )
                        ),
                        **diagnostics,
                        "model_path": str(model_path.relative_to(ROOT)),
                        "model_sha256": sha256(model_path),
                        "predictions_path": str(prediction_path.relative_to(ROOT)),
                    }
                    diagnostic_path.write_text(
                        json.dumps(
                            payload, indent=2, ensure_ascii=False, default=str
                        ),
                        encoding="utf-8",
                    )
                    completed.append(identity)
                    ic = diagnostics["predictive"].get(
                        "mean_cross_sectional_rank_ic"
                    )
                    print(f"done {identity} mean_rank_ic={ic}", flush=True)
                    del score, predictions
                    gc.collect()
            del train, validation
            gc.collect()
    connection.close()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    run_manifest = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "tasks": args.tasks,
        "model_types": args.model_types,
        "horizons": args.horizons,
        "feature_set": args.feature_set,
        "folds": [fold[0] for fold in selected_folds],
        "seed": args.seed,
        "train_window_days": args.train_window_days,
        "completed_models": completed,
    }
    run_path = OUTPUT_ROOT / (
        f"run_manifest_{args.feature_set}_s{args.seed}_"
        f"{pd.Timestamp.now('UTC').strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    run_path.write_text(
        json.dumps(run_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"run_manifest -> {run_path}")


if __name__ == "__main__":
    main()
