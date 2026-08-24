"""Walk-forward identifiability audit for the CTLS-R3 state labels."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-ctls-r3-walk-forward-identifiability-preregistration-2026-08-10.md"
R2_DIAGNOSTIC_PATH = FAMILY_DIR / "diagnostics/hype-1d-ma7-ctls-r2-direction-failure-2026-08-10.md"
LABEL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
ORCHESTRATOR_PATH = Path(__file__)
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_ctls_r3_walk_forward_identifiability.py"
IMPLEMENTATION_PATHS = (
    CONTRACT_PATH,
    R2_DIAGNOSTIC_PATH,
    LABEL_ENGINE_PATH,
    ADAPTER_PATH,
    ORCHESTRATOR_PATH,
    TEST_PATH,
)
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r3_2026-08-10_manifest.json"
DIRECTION_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r3_2026-08-10_direction.json"
R2_A1_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r2_2026-08-10_direction_a1.json"
FOLDS = tuple((start, start + 54) for start in range(54, 324, 54))
RANDOM_SEED = 20260810
EXPECTED_TESTS = 6
FEATURE_COLUMNS = (
    "z",
    "s1",
    "s3",
    "d1",
    "d3",
    "er7",
    "ma_curvature",
    "drift_curvature",
    "ret1_atr",
    "ret2_atr",
    "ret3_atr",
    "ret5_atr",
    "ret7_atr",
    "er3",
    "er5",
    "er10",
    "range_atr",
    "body_atr",
    "atr_change1",
    "atr_change3",
    "rsi6_scaled",
    "ma_side_flips5",
    "positive_return_share5",
)


@dataclass(frozen=True, slots=True)
class PostConfig:
    enter_probability: float
    confirm_days: int
    exit_confirm_days: int
    hold_probability: float = 0.35


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pins() -> dict[str, str]:
    return {str(path.relative_to(ROOT)): sha256(path) for path in IMPLEMENTATION_PATHS}


def _assert_pins(expected: dict[str, str]) -> None:
    if _pins() != expected:
        raise RuntimeError("CTLS-R3 implementation pin drift")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(
        _safe(payload), ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ).encode()
    try:
        with path.open("xb") as handle:
            handle.write(encoded + b"\n")
    except FileExistsError as exc:
        raise RuntimeError(f"locked artifact already exists: {path}") from exc


def _read(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing upstream artifact: {path}")
    return json.loads(path.read_text())


def preflight() -> dict[str, Any]:
    before = _pins()
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/pytest"), "-q", str(TEST_PATH)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    after = _pins()
    status = "PASS" if completed.returncode == 0 and passed == EXPECTED_TESTS and before == after else "FAIL"
    result = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_TESTS,
        "pins_stable": before == after,
        "returncode": completed.returncode,
        "output": output.strip(),
    }
    if status != "PASS":
        raise RuntimeError(f"R3 preflight failed: {result}")
    return result


def build_features(daily: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "ma7", "atr7", "rsi6"}
    if not required.issubset(daily.columns):
        raise ValueError(f"missing daily columns: {sorted(required - set(daily.columns))}")
    frame = daily.loc[:, sorted(required)].astype(float).copy()
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is None:
        raise ValueError("R3 features require timezone-aware daily index")
    close = frame["close"]
    atr = frame["atr7"]
    frame["z"] = (close - frame["ma7"]) / atr
    frame["s1"] = frame["ma7"].diff() / atr
    frame["s3"] = frame["ma7"].diff(3) / (3.0 * atr)
    frame["d1"] = close.diff() / atr
    frame["d3"] = close.diff(3) / (3.0 * atr)
    change = close.diff()
    frame["er7"] = close.diff(7) / change.abs().rolling(7, min_periods=7).sum()
    frame["ma_curvature"] = frame["s1"] - frame["s3"]
    frame["drift_curvature"] = frame["d1"] - frame["d3"]
    for lookback in (1, 2, 3, 5, 7):
        frame[f"ret{lookback}_atr"] = close.diff(lookback) / (lookback * atr)
    for lookback in (3, 5, 10):
        frame[f"er{lookback}"] = close.diff(lookback) / change.abs().rolling(
            lookback, min_periods=lookback
        ).sum()
    frame["range_atr"] = (frame["high"] - frame["low"]) / atr
    frame["body_atr"] = (frame["close"] - frame["open"]) / atr
    frame["atr_change1"] = atr.pct_change(1)
    frame["atr_change3"] = atr.pct_change(3)
    frame["rsi6_scaled"] = (frame["rsi6"] - 50.0) / 50.0
    relation = np.sign(frame["close"] - frame["ma7"])
    relation_change = relation.ne(relation.shift()) & relation.ne(0) & relation.shift().ne(0)
    frame["ma_side_flips5"] = relation_change.astype(float).rolling(5, min_periods=5).sum()
    frame["positive_return_share5"] = change.gt(0.0).astype(float).rolling(5, min_periods=5).mean()
    return frame.loc[:, FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan)


def model_configs() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for c_value in (0.01, 0.1, 1.0, 10.0):
        rows.append({"family": "logistic", "C": c_value})
    for depth in (2, 3, 5):
        for leaf in (5, 10, 20):
            rows.append({"family": "random_forest", "max_depth": depth, "min_samples_leaf": leaf})
    for leaves in (3, 7, 15):
        for child in (10, 20, 40):
            for rate in (0.02, 0.05):
                rows.append(
                    {
                        "family": "lightgbm",
                        "num_leaves": leaves,
                        "min_child_samples": child,
                        "learning_rate": rate,
                    }
                )
    if len(rows) != 31:
        raise AssertionError("R3 direction model grid must contain 31 configs")
    return tuple(rows)


def post_configs() -> tuple[PostConfig, ...]:
    rows = tuple(
        PostConfig(enter, confirm, exit_confirm)
        for enter in (0.40, 0.50, 0.60)
        for confirm in (1, 2)
        for exit_confirm in (1, 2)
    )
    if len(rows) != 12:
        raise AssertionError("R3 postprocess grid must contain 12 configs")
    return rows


def direction_target(labels: pd.Series) -> pd.Series:
    def convert(value: Any) -> float:
        if pd.isna(value):
            return math.nan
        label = str(value)
        return 1.0 if label.startswith("up_") else -1.0 if label.startswith("down_") else 0.0

    return labels.map(convert)


def mature_training_positions(eval_start: int) -> range:
    if eval_start < 4:
        raise ValueError("eval_start must leave label maturity history")
    return range(0, eval_start - 2)


def _fit_predict(
    config: dict[str, Any],
    train_x: pd.DataFrame,
    train_y: np.ndarray,
    eval_x: pd.DataFrame,
) -> np.ndarray:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.utils.class_weight import compute_sample_weight

    family = config["family"]
    if family == "logistic":
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=config["C"],
                class_weight="balanced",
                max_iter=2000,
                random_state=RANDOM_SEED,
            ),
        )
        model.fit(train_x, train_y)
    elif family == "random_forest":
        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=config["max_depth"],
            min_samples_leaf=config["min_samples_leaf"],
            class_weight="balanced",
            random_state=RANDOM_SEED,
            n_jobs=1,
        )
        model.fit(train_x, train_y)
    else:
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(
            objective="multiclass",
            n_estimators=200,
            num_leaves=config["num_leaves"],
            min_child_samples=config["min_child_samples"],
            learning_rate=config["learning_rate"],
            random_state=RANDOM_SEED,
            n_jobs=1,
            verbosity=-1,
            deterministic=True,
        )
        model.fit(train_x, train_y, sample_weight=compute_sample_weight("balanced", train_y))
    classes = np.asarray(model.classes_, dtype=int)
    raw = np.asarray(model.predict_proba(eval_x), dtype=float)
    result = np.zeros((len(eval_x), 3), dtype=float)
    for column, value in enumerate((-1, 0, 1)):
        matches = np.flatnonzero(classes == value)
        if len(matches):
            result[:, column] = raw[:, int(matches[0])]
    return result


def apply_hysteresis(probabilities: np.ndarray, config: PostConfig) -> np.ndarray:
    if probabilities.ndim != 2 or probabilities.shape[1] != 3:
        raise ValueError("probabilities must be N x 3 ordered DOWN/FLAT/UP")
    state = 0
    candidate = 0
    candidate_run = 0
    loss_run = 0
    output = np.zeros(len(probabilities), dtype=int)
    for index, row in enumerate(probabilities):
        best_column = int(np.argmax(row))
        best_side = (-1, 0, 1)[best_column]
        if state == 0:
            raw = best_side if best_side and row[best_column] >= config.enter_probability else 0
            if raw and raw == candidate:
                candidate_run += 1
            elif raw:
                candidate = raw
                candidate_run = 1
            else:
                candidate = 0
                candidate_run = 0
            if candidate_run >= config.confirm_days:
                state = candidate
                candidate = 0
                candidate_run = 0
        else:
            opposite = -state
            opposite_column = 0 if opposite < 0 else 2
            if best_side == opposite and row[opposite_column] >= config.enter_probability:
                if candidate == opposite:
                    candidate_run += 1
                else:
                    candidate = opposite
                    candidate_run = 1
                if candidate_run >= config.confirm_days:
                    state = opposite
                    candidate = 0
                    candidate_run = 0
                    loss_run = 0
            else:
                candidate = 0
                candidate_run = 0
                current_column = 0 if state < 0 else 2
                losing = best_side == 0 or row[current_column] < config.hold_probability
                loss_run = loss_run + 1 if losing else 0
                if loss_run >= config.exit_confirm_days:
                    state = 0
                    loss_run = 0
        output[index] = state
    return output


def direction_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, Any]:
    if len(actual) != len(predicted) or not len(actual):
        raise ValueError("direction metrics require equal nonempty arrays")
    recalls = {}
    for value, name in ((-1, "down"), (0, "flat"), (1, "up")):
        mask = actual == value
        recalls[name] = float(np.mean(predicted[mask] == value)) if mask.any() else math.nan
    flips = int(np.sum(predicted[1:] != predicted[:-1]))
    return {
        "samples": len(actual),
        "balanced_accuracy": float(np.mean([value for value in recalls.values() if math.isfinite(value)])),
        "recalls": recalls,
        "flip_rate": flips / max(1, len(predicted) - 1),
        "true_counts": dict(sorted(Counter(map(int, actual)).items())),
        "predicted_counts": dict(sorted(Counter(map(int, predicted)).items())),
    }


def _gate(aggregate: dict[str, Any], folds: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "balanced_accuracy_ge_055": aggregate["balanced_accuracy"] >= 0.55,
        "flat_recall_ge_040": aggregate["recalls"]["flat"] >= 0.40,
        "up_recall_ge_040": aggregate["recalls"]["up"] >= 0.40,
        "down_recall_ge_040": aggregate["recalls"]["down"] >= 0.40,
        "flip_rate_le_015": aggregate["flip_rate"] <= 0.15,
        "four_of_five_folds_ge_050": sum(row["balanced_accuracy"] >= 0.50 for row in folds) >= 4,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _hash_config(model: dict[str, Any], post: PostConfig) -> str:
    payload = {"model": model, "post": asdict(post)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path_hash(fold_rows: list[dict[str, Any]]) -> str:
    payload = [
        {"fold": row["fold"], "ts": row["ts"], "direction": row["direction"]}
        for row in fold_rows
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def stage_manifest() -> dict[str, Any]:
    tests = preflight()
    pins = _pins()
    adapter = _load(ADAPTER_PATH, "ctls_r3_manifest_adapter")
    context = adapter.load_context()
    r2 = _read(R2_A1_PATH)
    if r2.get("status") != "FAIL" or r2.get("passing_gate") != 0:
        raise RuntimeError("R3 requires frozen R2 direction failure")
    payload = {
        "schema_version": "ctls-r3-manifest-v1",
        "status": "LOCKED",
        "preflight": tests,
        "pins": pins,
        "r2_failure": {"path": str(R2_A1_PATH.relative_to(ROOT)), "sha256": sha256(R2_A1_PATH)},
        "folds": FOLDS,
        "model_configs": len(model_configs()),
        "post_configs": len(post_configs()),
        "direction_trials": len(model_configs()) * len(post_configs()),
        "LES_accessed": False,
        "market": {
            "book_count": context.book.count,
            "terminal_ts": pd.Timestamp(context.book.terminal_ts).isoformat(),
            "audit": context.market.audit,
            "adapter_pins": dict(context.pins),
        },
    }
    _assert_pins(pins)
    _write_new(MANIFEST_PATH, payload)
    return {"status": "PASS", "path": str(MANIFEST_PATH), "sha256": sha256(MANIFEST_PATH)}


def _complexity(model: dict[str, Any], post: PostConfig) -> int:
    family_rank = {"logistic": 0, "random_forest": 1, "lightgbm": 2}[model["family"]]
    return family_rank * 100 + list(model_configs()).index(model) + list(post_configs()).index(post)


def rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row["gate"]["status"] == "PASS" else 1,
        -min(fold["balanced_accuracy"] for fold in row["folds"]),
        -row["aggregate"]["balanced_accuracy"],
        -min(row["aggregate"]["recalls"].values()),
        row["aggregate"]["flip_rate"],
        row["complexity"],
        row["config_sha256"],
    )


def stage_direction() -> dict[str, Any]:
    manifest = _read(MANIFEST_PATH)
    _assert_pins(manifest["pins"])
    label_engine = _load(LABEL_ENGINE_PATH, "ctls_r3_direction_labels")
    adapter = _load(ADAPTER_PATH, "ctls_r3_direction_adapter")
    context = adapter.load_context()
    daily = context.market.daily
    features = build_features(daily)
    labels = label_engine.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    target = direction_target(labels)
    rows = []
    for model_index, model_config in enumerate(model_configs(), 1):
        fold_probabilities = []
        fold_meta = []
        for fold_index, (eval_start, eval_end) in enumerate(FOLDS, 1):
            train_positions = list(mature_training_positions(eval_start))
            train_mask = features.iloc[train_positions].notna().all(axis=1) & target.iloc[train_positions].notna()
            train_x = features.iloc[train_positions].loc[train_mask]
            train_y = target.iloc[train_positions].loc[train_mask].astype(int).to_numpy()
            eval_x = features.iloc[eval_start:eval_end]
            if not eval_x.notna().all(axis=1).all():
                raise RuntimeError("R3 eval features contain non-finite rows")
            probabilities = _fit_predict(model_config, train_x, train_y, eval_x)
            fold_probabilities.append(probabilities)
            fold_meta.append(
                {
                    "fold": fold_index,
                    "train_samples": len(train_x),
                    "train_last_label_ts": train_x.index[-1].isoformat(),
                    "eval_start_ts": eval_x.index[0].isoformat(),
                    "eval_end_ts": eval_x.index[-1].isoformat(),
                    "train_class_counts": dict(sorted(Counter(map(int, train_y)).items())),
                }
            )
        for post_index, post_config in enumerate(post_configs(), 1):
            all_actual = []
            all_predicted = []
            fold_metrics = []
            path_rows = []
            for fold_index, ((eval_start, eval_end), probabilities) in enumerate(
                zip(FOLDS, fold_probabilities, strict=True), 1
            ):
                predicted = apply_hysteresis(probabilities, post_config)
                eval_target = target.iloc[eval_start:eval_end].to_numpy()
                eligible = np.arange(len(predicted)) < len(predicted) - 3
                eligible &= np.isfinite(eval_target)
                actual_values = eval_target[eligible].astype(int)
                predicted_values = predicted[eligible]
                metrics = direction_metrics(actual_values, predicted_values)
                fold_metrics.append({**fold_meta[fold_index - 1], **metrics})
                all_actual.extend(actual_values.tolist())
                all_predicted.extend(predicted_values.tolist())
                for offset, value in enumerate(predicted):
                    path_rows.append(
                        {
                            "fold": fold_index,
                            "ts": daily.index[eval_start + offset].isoformat(),
                            "direction": int(value),
                        }
                    )
            aggregate = direction_metrics(np.asarray(all_actual), np.asarray(all_predicted))
            gate = _gate(aggregate, fold_metrics)
            rows.append(
                {
                    "arm_id": f"R3D{model_index:02d}_{post_index:02d}",
                    "status": "OK",
                    "model": model_config,
                    "post": asdict(post_config),
                    "config_sha256": _hash_config(model_config, post_config),
                    "complexity": _complexity(model_config, post_config),
                    "direction_path_sha256": _path_hash(path_rows),
                    "aggregate": aggregate,
                    "folds": fold_metrics,
                    "gate": gate,
                }
            )
    passing = [row for row in rows if row["gate"]["status"] == "PASS"]
    best_by_path: dict[str, dict[str, Any]] = {}
    for row in passing:
        current = best_by_path.get(row["direction_path_sha256"])
        if current is None or rank_key(row) < rank_key(current):
            best_by_path[row["direction_path_sha256"]] = row
    selected = sorted(best_by_path.values(), key=rank_key)[:16]
    payload = {
        "schema_version": "ctls-r3-direction-v1",
        "status": "PASS" if selected else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "trials": len(rows),
        "passing_gate": len(passing),
        "unique_direction_paths": len({row["direction_path_sha256"] for row in rows}),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"])
    _write_new(DIRECTION_PATH, payload)
    return {"status": payload["status"], "passing_gate": len(passing), "selected": payload["selected_arm_ids"], "path": str(DIRECTION_PATH), "sha256": sha256(DIRECTION_PATH)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("self-test", "manifest", "direction"))
    return parser.parse_args()


def main() -> None:
    stage = parse_args().stage
    if stage == "self-test":
        result = preflight()
    elif stage == "manifest":
        result = stage_manifest()
    else:
        result = stage_direction()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
