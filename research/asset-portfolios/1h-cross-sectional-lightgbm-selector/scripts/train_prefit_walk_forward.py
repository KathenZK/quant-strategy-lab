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
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MATRIX_ROOT = ARTIFACT_DIR / "prefit_model_matrix"
MATRIX_MANIFEST_PATH = ARTIFACT_DIR / "prefit_model_matrix_manifest.json"
OUTPUT_ROOT = ARTIFACT_DIR / "prefit_walk_forward"
PREFIT_END = pd.Timestamp("2026-03-31T00:00:00Z")
PURGE_HOURS = 24
TRAIN_SAMPLE_HOURS = 4
INNER_VALIDATION_DAYS = 120
SPARSE_PREFIX = "donchian_breakout_strength_"

FOLDS: tuple[tuple[str, str, str], ...] = (
    ("wf_2024_h1", "2024-01-01T00:00:00Z", "2024-07-01T00:00:00Z"),
    ("wf_2024_h2", "2024-07-01T00:00:00Z", "2025-01-01T00:00:00Z"),
    ("wf_2025_h1", "2025-01-01T00:00:00Z", "2025-07-01T00:00:00Z"),
    ("wf_2025_h2", "2025-07-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    ("wf_2026_q1", "2026-01-01T00:00:00Z", "2026-03-31T00:00:00Z"),
)
MODEL_TYPES = ("regression", "classification", "ranker", "ridge")
HORIZONS = (4, 12, 24)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train leakage-safe pre-OOS cross-sectional walk-forward models."
    )
    parser.add_argument(
        "--model-types",
        nargs="+",
        choices=MODEL_TYPES,
        default=list(MODEL_TYPES),
    )
    parser.add_argument(
        "--horizons", nargs="+", type=int, choices=HORIZONS, default=list(HORIZONS)
    )
    parser.add_argument("--feature-set", default="compact")
    parser.add_argument("--folds", nargs="+", default=[fold[0] for fold in FOLDS])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def sql_path(path: Path) -> str:
    return str(path).replace("'", "''")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(feature_set: str) -> tuple[dict[str, Any], list[str]]:
    if not MATRIX_MANIFEST_PATH.exists():
        raise RuntimeError(f"prefit matrix manifest is missing: {MATRIX_MANIFEST_PATH}")
    manifest = json.loads(MATRIX_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not manifest.get("physical_oos_isolation"):
        raise RuntimeError("model matrix does not prove physical OOS isolation")
    if manifest.get("prefit_end_exclusive") != PREFIT_END.isoformat():
        raise RuntimeError("unexpected prefit boundary")
    if int(manifest.get("forbidden_rows", -1)) != 0:
        raise RuntimeError("prefit matrix contains forbidden rows")
    sets = manifest.get("feature_sets", {})
    if feature_set not in sets or feature_set == "sparse_event_features":
        raise RuntimeError(f"unknown model feature set: {feature_set}")
    return manifest, list(sets[feature_set])


def matrix_glob() -> Path:
    result = MATRIX_ROOT / "**/*.parquet"
    if not list(MATRIX_ROOT.glob("**/*.parquet")):
        raise RuntimeError(f"prefit model matrix is missing: {result}")
    return result


def label_columns(horizon: int) -> list[str]:
    return [
        f"label_funding_sum_{horizon}h",
        f"label_long_net_{horizon}h",
        f"label_short_net_{horizon}h",
        f"label_gross_return_{horizon}h",
        f"label_long_relative_{horizon}h",
        f"label_short_relative_{horizon}h",
    ]


def load_slice(
    connection: duckdb.DuckDBPyConnection,
    *,
    features: list[str],
    horizon: int,
    start: pd.Timestamp | None,
    end: pd.Timestamp,
    sampled: bool,
) -> pd.DataFrame:
    feature_sql = ", ".join(f'"{name}"' for name in features)
    labels_sql = ", ".join(label_columns(horizon))
    predicates = [f"ts < TIMESTAMPTZ '{end.isoformat()}'"]
    if start is not None:
        predicates.append(f"ts >= TIMESTAMPTZ '{start.isoformat()}'")
    if sampled:
        predicates.append(
            f"(floor(epoch(ts) / 3600)::BIGINT % {TRAIN_SAMPLE_HOURS}) = 0"
        )
    query = f"""
        SELECT
            epoch_ms(ts)::BIGINT AS ts_ms,
            symbol,
            liquidity_rank,
            avg_daily_quote_volume_7d,
            {feature_sql},
            {labels_sql}
        FROM read_parquet(
            '{sql_path(matrix_glob())}',
            hive_partitioning = false,
            union_by_name = true
        )
        WHERE {' AND '.join(predicates)}
        ORDER BY ts, symbol
    """
    frame = connection.execute(query).fetch_df()
    frame["ts"] = pd.to_datetime(frame.pop("ts_ms"), unit="ms", utc=True)
    return frame


def clean_features(frame: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    result = frame[features].astype("float32", copy=True)
    result.replace([np.inf, -np.inf], np.nan, inplace=True)
    sparse = [name for name in features if name.startswith(SPARSE_PREFIX)]
    if sparse:
        result[sparse] = result[sparse].fillna(0.0)
    return result


def target_percentile(frame: pd.DataFrame, label: str) -> pd.Series:
    return frame.groupby("ts", sort=False)[label].rank(
        method="average", pct=True, na_option="keep"
    )


def group_sizes(frame: pd.DataFrame) -> np.ndarray:
    return frame.groupby("ts", sort=False).size().to_numpy(dtype="int32")


def lightgbm_parameters(model_type: str, seed: int) -> dict[str, Any]:
    common: dict[str, Any] = {
        "n_estimators": 600,
        "learning_rate": 0.03,
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
    if model_type == "classification":
        return {**common, "objective": "binary", "metric": "binary_logloss"}
    if model_type == "ranker":
        return {**common, "objective": "lambdarank", "metric": "ndcg"}
    raise ValueError(f"not a LightGBM model: {model_type}")


def predictive_diagnostics(
    frame: pd.DataFrame,
    *,
    score: np.ndarray,
    horizon: int,
) -> dict[str, Any]:
    label = f"label_long_relative_{horizon}h"
    valid = frame[label].notna() & np.isfinite(score)
    if int(valid.sum()) < 2:
        return {"rows": int(valid.sum()), "spearman_ic": None}
    correlation = spearmanr(
        score[valid.to_numpy()],
        frame.loc[valid, label].to_numpy(dtype="float64"),
        nan_policy="omit",
    ).statistic
    by_time = pd.DataFrame(
        {
            "ts": frame.loc[valid, "ts"].to_numpy(),
            "score": score[valid.to_numpy()],
            "label": frame.loc[valid, label].to_numpy(dtype="float64"),
        }
    )
    hourly_ic = by_time.groupby("ts", sort=False).apply(
        lambda group: group["score"].corr(group["label"], method="spearman"),
        include_groups=False,
    )
    return {
        "rows": int(valid.sum()),
        "spearman_ic": None if not np.isfinite(correlation) else float(correlation),
        "mean_hourly_rank_ic": float(hourly_ic.mean()),
        "positive_hourly_rank_ic_share": float(hourly_ic.gt(0.0).mean()),
    }


def fit_predict(
    *,
    model_type: str,
    train: pd.DataFrame,
    validation: pd.DataFrame,
    features: list[str],
    horizon: int,
    seed: int,
    model_path: Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    label = f"label_long_relative_{horizon}h"
    train = train.loc[train[label].notna()].copy()
    inner_start = train["ts"].max() - pd.Timedelta(days=INNER_VALIDATION_DAYS)
    fit_end = inner_start - pd.Timedelta(hours=PURGE_HOURS)
    fit = train.loc[train["ts"] < fit_end].copy()
    inner = train.loc[train["ts"] >= inner_start].copy()
    if len(fit) < 100_000 or len(inner) < 10_000:
        raise RuntimeError(
            f"insufficient temporal train split: fit={len(fit)} inner={len(inner)}"
        )
    x_fit = clean_features(fit, features)
    x_inner = clean_features(inner, features)
    x_validation = clean_features(validation, features)
    best_iteration: int | None = None
    if model_type in {"regression", "ridge"}:
        y_fit = fit[label].to_numpy(dtype="float32")
        y_inner = inner[label].to_numpy(dtype="float32")
    else:
        fit_percentile = target_percentile(fit, label)
        inner_percentile = target_percentile(inner, label)
        if model_type == "classification":
            y_fit = fit_percentile.ge(0.80).to_numpy(dtype="int8")
            y_inner = inner_percentile.ge(0.80).to_numpy(dtype="int8")
        else:
            y_fit = np.minimum(
                np.floor(fit_percentile.to_numpy(dtype="float64") * 5.0), 4.0
            ).astype("int8")
            y_inner = np.minimum(
                np.floor(inner_percentile.to_numpy(dtype="float64") * 5.0), 4.0
            ).astype("int8")
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
    elif model_type == "regression":
        model = lgb.LGBMRegressor(**lightgbm_parameters(model_type, seed))
        model.fit(
            x_fit,
            y_fit,
            eval_set=[(x_inner, y_inner)],
            callbacks=[lgb.early_stopping(60, verbose=False)],
        )
        score = model.predict(x_validation, num_iteration=model.best_iteration_)
        best_iteration = int(model.best_iteration_)
        model.booster_.save_model(str(model_path))
    elif model_type == "classification":
        model = lgb.LGBMClassifier(**lightgbm_parameters(model_type, seed))
        model.fit(
            x_fit,
            y_fit,
            eval_set=[(x_inner, y_inner)],
            callbacks=[lgb.early_stopping(60, verbose=False)],
        )
        score = model.predict_proba(
            x_validation, num_iteration=model.best_iteration_
        )[:, 1]
        best_iteration = int(model.best_iteration_)
        model.booster_.save_model(str(model_path))
    else:
        model = lgb.LGBMRanker(**lightgbm_parameters(model_type, seed))
        model.fit(
            x_fit,
            y_fit,
            group=group_sizes(fit),
            eval_set=[(x_inner, y_inner)],
            eval_group=[group_sizes(inner)],
            eval_at=[1, 3, 5],
            callbacks=[lgb.early_stopping(60, verbose=False)],
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
            validation, score=np.asarray(score), horizon=horizon
        ),
    }
    return np.asarray(score, dtype="float64"), diagnostics


def prediction_frame(
    validation: pd.DataFrame,
    *,
    score: np.ndarray,
    horizon: int,
    fold_id: str,
    model_type: str,
    feature_set: str,
    seed: int,
) -> pd.DataFrame:
    columns = [
        "ts",
        "symbol",
        "liquidity_rank",
        "avg_daily_quote_volume_7d",
        "cs_rank_ret_24",
        "cs_rank_ret_168",
        "cs_rank_ema_spread_24_96",
        "cs_rank_funding_rate",
        *label_columns(horizon),
    ]
    result = validation[columns].copy()
    result["score"] = score.astype("float32")
    result["fold_id"] = fold_id
    result["model_type"] = model_type
    result["feature_set"] = feature_set
    result["horizon"] = horizon
    result["seed"] = seed
    return result


def main() -> None:
    args = parse_args()
    manifest, features = validate_manifest(args.feature_set)
    selected_folds = [fold for fold in FOLDS if fold[0] in set(args.folds)]
    if len(selected_folds) != len(set(args.folds)):
        raise RuntimeError(f"unknown fold ids: {args.folds}")
    connection = duckdb.connect()
    connection.execute("SET threads = 8")
    connection.execute("SET memory_limit = '8GB'")
    run_rows: list[dict[str, Any]] = []
    for horizon in args.horizons:
        for fold_id, validation_start_text, validation_end_text in selected_folds:
            validation_start = pd.Timestamp(validation_start_text)
            validation_end = pd.Timestamp(validation_end_text)
            if validation_end > PREFIT_END:
                raise RuntimeError(f"fold crosses sealed boundary: {fold_id}")
            train_end = validation_start - pd.Timedelta(hours=PURGE_HOURS)
            train = load_slice(
                connection,
                features=features,
                horizon=horizon,
                start=None,
                end=train_end,
                sampled=True,
            )
            validation = load_slice(
                connection,
                features=features,
                horizon=horizon,
                start=validation_start,
                end=validation_end,
                sampled=False,
            )
            for model_type in args.model_types:
                identity = f"{model_type}_{args.feature_set}_{horizon}h_{fold_id}_s{args.seed}"
                output_directory = OUTPUT_ROOT / identity
                prediction_path = output_directory / "predictions.parquet"
                diagnostic_path = output_directory / "diagnostics.json"
                model_suffix = ".joblib" if model_type == "ridge" else ".txt"
                model_path = output_directory / f"model{model_suffix}"
                if prediction_path.exists() and diagnostic_path.exists() and not args.overwrite:
                    print(f"skip {identity}", flush=True)
                    continue
                output_directory.mkdir(parents=True, exist_ok=True)
                print(
                    f"fit {identity} train={len(train)} validation={len(validation)}",
                    flush=True,
                )
                score, diagnostics = fit_predict(
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
                    horizon=horizon,
                    fold_id=fold_id,
                    model_type=model_type,
                    feature_set=args.feature_set,
                    seed=args.seed,
                )
                predictions.to_parquet(prediction_path, index=False, compression="zstd")
                payload = {
                    "family": "Binance-1H-Cross-Sectional-LightGBM-Selector",
                    "identity": identity,
                    "generated_at": pd.Timestamp.now("UTC").isoformat(),
                    "oos_revealed": False,
                    "physical_oos_isolation": True,
                    "matrix_manifest": str(MATRIX_MANIFEST_PATH),
                    "matrix_manifest_sha256": file_sha256(MATRIX_MANIFEST_PATH),
                    "matrix_rows": manifest["rows"],
                    "model_type": model_type,
                    "feature_set": args.feature_set,
                    "feature_count": len(features),
                    "features": features,
                    "horizon_hours": horizon,
                    "fold_id": fold_id,
                    "validation_start": validation_start.isoformat(),
                    "validation_end_exclusive": validation_end.isoformat(),
                    "train_end_exclusive": train_end.isoformat(),
                    "purge_hours": PURGE_HOURS,
                    "train_sample_hours": TRAIN_SAMPLE_HOURS,
                    "seed": args.seed,
                    "model_parameters": (
                        {"ridge_alpha": 10.0, "solver": "lsqr"}
                        if model_type == "ridge"
                        else lightgbm_parameters(model_type, args.seed)
                    ),
                    **diagnostics,
                    "model_path": str(model_path),
                    "predictions_path": str(prediction_path),
                }
                diagnostic_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                    encoding="utf-8",
                )
                run_rows.append(payload)
                print(
                    f"done {identity} rank_ic="
                    f"{diagnostics['predictive']['mean_hourly_rank_ic']:.6f}",
                    flush=True,
                )
                del score, predictions
                gc.collect()
            del train, validation
            gc.collect()
    run_manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "oos_revealed": False,
        "model_types": args.model_types,
        "horizons": args.horizons,
        "feature_set": args.feature_set,
        "folds": [fold[0] for fold in selected_folds],
        "seed": args.seed,
        "completed_models": [row["identity"] for row in run_rows],
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
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
