"""Causal minimum-duration decoder search for CTLS-R5."""

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
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-ctls-r5-duration-decoder-preregistration-2026-08-10.md"
R4_DIAGNOSTIC_PATH = FAMILY_DIR / "diagnostics/hype-1d-ma7-ctls-r4-stable-segment-failure-2026-08-10.md"
R4_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r4_stable_segment.py"
R3_PATH = SCRIPT_DIR / "research_hype_1d_ma7_ctls_r3_walk_forward_identifiability.py"
LABEL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
ORCHESTRATOR_PATH = Path(__file__)
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_ctls_r5_duration_decoder.py"
IMPLEMENTATION_PATHS = (
    CONTRACT_PATH,
    R4_DIAGNOSTIC_PATH,
    R4_PATH,
    R3_PATH,
    LABEL_ENGINE_PATH,
    ADAPTER_PATH,
    ORCHESTRATOR_PATH,
    TEST_PATH,
)
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r5_2026-08-10_manifest.json"
DIRECTION_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r5_2026-08-10_direction.json"
R4_DIRECTION_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r4_2026-08-10_direction.json"
FOLDS = tuple((start, start + 54) for start in range(54, 324, 54))
EMA_ALPHAS = (0.40, 0.60, 0.80)
EXPECTED_TESTS = 5


@dataclass(frozen=True, slots=True)
class DurationConfig:
    minimum_dwell_days: int
    switch_confirm_days: int

    def __post_init__(self) -> None:
        if self.minimum_dwell_days not in (3, 5, 7):
            raise ValueError("minimum dwell outside R5 grid")
        if self.switch_confirm_days not in (1, 2):
            raise ValueError("switch confirmation outside R5 grid")


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
        raise RuntimeError("CTLS-R5 implementation pin drift")


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
        raise RuntimeError(f"R5 preflight failed: {result}")
    return result


def duration_configs() -> tuple[DurationConfig, ...]:
    return tuple(
        DurationConfig(dwell, confirm)
        for dwell in (3, 5, 7)
        for confirm in (1, 2)
    )


def base_post_configs(r3: Any) -> tuple[Any, ...]:
    return tuple(
        r3.PostConfig(enter, confirm, exit_confirm)
        for enter in (0.40, 0.50)
        for confirm in (1, 2)
        for exit_confirm in (1, 2)
    )


def duration_decode(base: np.ndarray, config: DurationConfig) -> np.ndarray:
    if base.ndim != 1 or not np.isin(base, (-1, 0, 1)).all():
        raise ValueError("base states must be one-dimensional DOWN/FLAT/UP")
    state = 0
    dwell = 0
    candidate = 0
    candidate_run = 0
    output = np.zeros(len(base), dtype=int)
    for index, target in enumerate(base):
        dwell += 1
        if target == state:
            candidate = state
            candidate_run = 0
        else:
            if target == candidate:
                candidate_run += 1
            else:
                candidate = int(target)
                candidate_run = 1
            if (
                dwell >= config.minimum_dwell_days
                and candidate_run >= config.switch_confirm_days
            ):
                state = candidate
                dwell = 0
                candidate_run = 0
        output[index] = state
    return output


def _hash_config(model: dict[str, Any], alpha: float, post: Any, duration: DurationConfig) -> str:
    payload = {
        "model": model,
        "alpha": alpha,
        "post": asdict(post),
        "duration": asdict(duration),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _path_hash(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def stage_manifest() -> dict[str, Any]:
    tests = preflight()
    pins = _pins()
    r4 = _read(R4_DIRECTION_PATH)
    if r4.get("status") != "FAIL" or r4.get("passing_gate") != 0:
        raise RuntimeError("R5 requires frozen R4 failure")
    adapter = _load(ADAPTER_PATH, "ctls_r5_manifest_adapter")
    context = adapter.load_context()
    payload = {
        "schema_version": "ctls-r5-manifest-v1",
        "status": "LOCKED",
        "preflight": tests,
        "pins": pins,
        "r4_failure": {"path": str(R4_DIRECTION_PATH.relative_to(ROOT)), "sha256": sha256(R4_DIRECTION_PATH)},
        "trials": 31 * 3 * 8 * 6,
        "ema_alphas": EMA_ALPHAS,
        "base_post_count": 8,
        "duration_configs": [asdict(row) for row in duration_configs()],
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
    r3 = _load(R3_PATH, "ctls_r5_r3")
    r4 = _load(R4_PATH, "ctls_r5_r4")
    labels = _load(LABEL_ENGINE_PATH, "ctls_r5_labels")
    adapter = _load(ADAPTER_PATH, "ctls_r5_adapter")
    context = adapter.load_context()
    daily = context.market.daily
    features = r3.build_features(daily)
    raw = labels.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    target = r4.stable_direction_target(r3.direction_target(raw))
    rows = []
    for model_index, model_config in enumerate(r3.model_configs(), 1):
        fold_probabilities = []
        metadata = []
        for fold_index, (eval_start, eval_end) in enumerate(FOLDS, 1):
            train_positions = list(r4.mature_training_positions(eval_start))
            mask = features.iloc[train_positions].notna().all(axis=1) & target.iloc[train_positions].notna()
            train_x = features.iloc[train_positions].loc[mask]
            train_y = target.iloc[train_positions].loc[mask].astype(int).to_numpy()
            eval_x = features.iloc[eval_start:eval_end]
            fold_probabilities.append(r3._fit_predict(model_config, train_x, train_y, eval_x))
            metadata.append(
                {
                    "fold": fold_index,
                    "train_samples": len(train_x),
                    "train_last_label_ts": train_x.index[-1].isoformat(),
                    "eval_start_ts": eval_x.index[0].isoformat(),
                    "eval_end_ts": eval_x.index[-1].isoformat(),
                    "train_class_counts": dict(sorted(Counter(map(int, train_y)).items())),
                }
            )
        for alpha_index, alpha in enumerate(EMA_ALPHAS, 1):
            smoothed_folds = [r4.ema_probabilities(values, alpha) for values in fold_probabilities]
            for post_index, post in enumerate(base_post_configs(r3), 1):
                base_folds = [r3.apply_hysteresis(values, post) for values in smoothed_folds]
                for duration_index, duration in enumerate(duration_configs(), 1):
                    all_actual = []
                    all_predicted = []
                    fold_metrics = []
                    path_rows = []
                    for fold_index, ((eval_start, eval_end), base) in enumerate(
                        zip(FOLDS, base_folds, strict=True), 1
                    ):
                        predicted = duration_decode(base, duration)
                        eval_target = target.iloc[eval_start:eval_end].to_numpy()
                        eligible = np.arange(len(predicted)) < len(predicted) - 4
                        eligible &= np.isfinite(eval_target)
                        actual_values = eval_target[eligible].astype(int)
                        predicted_values = predicted[eligible]
                        metric = r3.direction_metrics(actual_values, predicted_values)
                        fold_metrics.append({**metadata[fold_index - 1], **metric})
                        all_actual.extend(actual_values.tolist())
                        all_predicted.extend(predicted_values.tolist())
                        path_rows.extend(
                            {
                                "fold": fold_index,
                                "ts": daily.index[eval_start + offset].isoformat(),
                                "direction": int(value),
                            }
                            for offset, value in enumerate(predicted)
                        )
                    aggregate = r3.direction_metrics(
                        np.asarray(all_actual), np.asarray(all_predicted)
                    )
                    gate = r3._gate(aggregate, fold_metrics)
                    rows.append(
                        {
                            "arm_id": f"R5D{model_index:02d}_{alpha_index}_{post_index}_{duration_index}",
                            "status": "OK",
                            "model": model_config,
                            "ema_alpha": alpha,
                            "post": asdict(post),
                            "duration": asdict(duration),
                            "config_sha256": _hash_config(
                                model_config, alpha, post, duration
                            ),
                            "complexity": model_index * 1000
                            + alpha_index * 100
                            + post_index * 10
                            + duration_index,
                            "direction_path_sha256": _path_hash(path_rows),
                            "aggregate": aggregate,
                            "folds": fold_metrics,
                            "gate": gate,
                        }
                    )
    passing = [row for row in rows if row["gate"]["status"] == "PASS"]
    best: dict[str, dict[str, Any]] = {}
    for row in passing:
        current = best.get(row["direction_path_sha256"])
        if current is None or rank_key(row) < rank_key(current):
            best[row["direction_path_sha256"]] = row
    selected = sorted(best.values(), key=rank_key)[:16]
    payload = {
        "schema_version": "ctls-r5-direction-v1",
        "status": "PASS" if selected else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "trials": len(rows),
        "passing_gate": len(passing),
        "unique_paths": len({row["direction_path_sha256"] for row in rows}),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"])
    _write_new(DIRECTION_PATH, payload)
    return {
        "status": payload["status"],
        "passing_gate": len(passing),
        "selected": payload["selected_arm_ids"],
        "path": str(DIRECTION_PATH),
        "sha256": sha256(DIRECTION_PATH),
    }


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

