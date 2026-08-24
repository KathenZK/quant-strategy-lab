"""Governed direction/phase search for the CTLS-R2 successor."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = FAMILY_DIR / "specs/hype-1d-ma7-ctls-r2-continuous-strength-preregistration-2026-08-10.md"
R1_DIAGNOSTIC_PATH = FAMILY_DIR / "diagnostics/hype-1d-ma7-ctls-r1-state-accuracy-failure-2026-08-10.md"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_ctls_r2_continuous_strength_engine.py"
LABEL_ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
ORCHESTRATOR_PATH = Path(__file__)
TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_ctls_r2_continuous_strength_engine.py",
    ROOT / "tests/test_hype_1d_ma7_ctls_r2_continuous_strength_research.py",
)
IMPLEMENTATION_PATHS = (
    CONTRACT_PATH,
    R1_DIAGNOSTIC_PATH,
    ENGINE_PATH,
    LABEL_ENGINE_PATH,
    METRICS_PATH,
    ADAPTER_PATH,
    ORCHESTRATOR_PATH,
    *TEST_PATHS,
)
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r2_2026-08-10_manifest.json"
A1_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r2_2026-08-10_direction_a1.json"
A2_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_r2_2026-08-10_phase_a2.json"
R1_STAGE_A_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_2026-08-10_stage_a_v2.json"
DEVELOPMENT_END = 324
BLOCK_DAYS = 54
EXPECTED_A1 = 1944
EXPECTED_PREFLIGHT = 10


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
    actual = _pins()
    if actual != expected:
        raise RuntimeError("CTLS-R2 implementation pin drift")


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
    result = json.loads(path.read_text())
    if not isinstance(result, dict):
        raise RuntimeError("artifact root must be an object")
    return result


def preflight() -> dict[str, Any]:
    before = _pins()
    completed = subprocess.run(
        [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    after = _pins()
    status = "PASS" if completed.returncode == 0 and passed == EXPECTED_PREFLIGHT and before == after else "FAIL"
    result = {
        "status": status,
        "passed": passed,
        "expected": EXPECTED_PREFLIGHT,
        "returncode": completed.returncode,
        "pins_stable": before == after,
        "output": output.strip(),
    }
    if status != "PASS":
        raise RuntimeError(f"CTLS-R2 preflight failed: {result}")
    return result


def stage_manifest() -> dict[str, Any]:
    tests = preflight()
    pins = _pins()
    engine = _load(ENGINE_PATH, "ctls_r2_manifest_engine")
    adapter = _load(ADAPTER_PATH, "ctls_r2_manifest_adapter")
    context = adapter.load_context()
    if len(engine.direction_grid()) != EXPECTED_A1 or len(engine.phase_grid()) != 81:
        raise RuntimeError("CTLS-R2 grid drift")
    r1 = _read(R1_STAGE_A_PATH)
    if r1.get("status") != "FAIL" or r1.get("passing_accuracy_gate") != 0:
        raise RuntimeError("R2 requires the frozen R1 accuracy failure")
    payload = {
        "schema_version": "ctls-r2-manifest-v1",
        "status": "LOCKED",
        "preflight": tests,
        "pins": pins,
        "r1_failure": {"path": str(R1_STAGE_A_PATH.relative_to(ROOT)), "sha256": sha256(R1_STAGE_A_PATH)},
        "windows": {"D": [0, 324], "LES": [324, 432], "LES_accessed": False},
        "grids": {"A1": 1944, "A2_per_parent": 81, "A2_max": 2592},
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


def _direction(label: str) -> int:
    return 1 if label.startswith("up_") else -1 if label.startswith("down_") else 0


def _state_rows(engine: Any, features: Iterable[Any], strength_config: Any, phase_config: Any | None = None) -> list[dict[str, Any]]:
    machine = engine.ContinuousStrengthMachine(strength_config, phase_config)
    rows = []
    for feature in features:
        snapshot = machine.observe(feature)
        rows.append(
            {
                "ts": snapshot.ts.isoformat(),
                "direction": int(snapshot.direction),
                "phase": snapshot.phase.value,
                "label": snapshot.label,
                "transition": snapshot.transition,
                "q": snapshot.q,
                "velocity": snapshot.velocity,
                "acceleration": snapshot.acceleration,
            }
        )
    return rows


def _direction_metrics(
    rows: list[dict[str, Any]],
    truth: pd.Series,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    by_ts = {pd.Timestamp(row["ts"]): int(row["direction"]) for row in rows}
    eligible_start = start + pd.Timedelta(days=3)
    eligible_end = end - pd.Timedelta(days=3)
    actual: list[int] = []
    predicted: list[int] = []
    for ts, label in truth.items():
        timestamp = pd.Timestamp(ts)
        if timestamp < eligible_start or timestamp >= eligible_end or pd.isna(label) or timestamp not in by_ts:
            continue
        actual.append(_direction(str(label)))
        predicted.append(by_ts[timestamp])
    if not actual:
        raise RuntimeError("no eligible R2 direction labels")
    recalls = {}
    for value, name in ((-1, "down"), (0, "flat"), (1, "up")):
        count = sum(row == value for row in actual)
        recalls[name] = sum(left == value and right == value for left, right in zip(actual, predicted, strict=True)) / count if count else math.nan
    flips = sum(left != right for left, right in zip(predicted, predicted[1:], strict=False))
    return {
        "samples": len(actual),
        "balanced_accuracy": float(np.mean([value for value in recalls.values() if math.isfinite(value)])),
        "recalls": recalls,
        "flip_rate": flips / max(1, len(predicted) - 1),
        "true_counts": dict(sorted(Counter(actual).items())),
        "predicted_counts": dict(sorted(Counter(predicted).items())),
    }


def _direction_gate(aggregate: dict[str, Any], blocks: list[dict[str, Any]]) -> dict[str, Any]:
    checks = {
        "balanced_accuracy_ge_055": aggregate["balanced_accuracy"] >= 0.55,
        "flat_recall_ge_040": aggregate["recalls"]["flat"] >= 0.40,
        "up_recall_ge_040": aggregate["recalls"]["up"] >= 0.40,
        "down_recall_ge_040": aggregate["recalls"]["down"] >= 0.40,
        "flip_rate_le_015": aggregate["flip_rate"] <= 0.15,
        "four_of_six_blocks_ge_050": sum(row["balanced_accuracy"] >= 0.50 for row in blocks) >= 4,
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}


def _hash_rows(rows: list[dict[str, Any]], *, direction_only: bool) -> str:
    payload = [
        {"ts": row["ts"], "direction": row["direction"]}
        if direction_only
        else {"ts": row["ts"], "direction": row["direction"], "phase": row["phase"]}
        for row in rows
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _config_hash(*configs: Any) -> str:
    payload = [asdict(config) for config in configs]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _a1_complexity(config: Any) -> int:
    return sum(
        (
            (0.25, 0.50, 1.00).index(config.z_scale),
            (0.03, 0.08, 0.15).index(config.slope_scale),
            (0.05, 0.10, 0.20).index(config.drift_scale),
            tuple(("equal", "persistence", "early", "smooth")).index(config.weight_template),
            (0.20, 0.35, 0.50).index(config.enter_q),
            (-0.05, 0.05, 0.15).index(config.exit_q),
            config.enter_confirm_days - 1,
        )
    )


def a1_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    aggregate = row["aggregate"]
    return (
        0 if row["gate"]["status"] == "PASS" else 1,
        -min(block["balanced_accuracy"] for block in row["blocks"]),
        -aggregate["balanced_accuracy"],
        -min(aggregate["recalls"].values()),
        aggregate["flip_rate"],
        row["complexity"],
        row["config_sha256"],
    )


def select_a1(rows: list[dict[str, Any]], limit: int = 32) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row.get("status") != "OK" or row["gate"]["status"] != "PASS":
            continue
        current = best.get(row["direction_path_sha256"])
        if current is None or (row["complexity"], a1_rank(row)) < (current["complexity"], a1_rank(current)):
            best[row["direction_path_sha256"]] = row
    return sorted(best.values(), key=a1_rank)[:limit]


def _runtime() -> tuple[Any, Any, Any, Any, pd.DataFrame, pd.Series, tuple[Any, ...]]:
    engine = _load(ENGINE_PATH, "ctls_r2_runtime_engine")
    label_engine = _load(LABEL_ENGINE_PATH, "ctls_r2_runtime_label_engine")
    metrics = _load(METRICS_PATH, "ctls_r2_runtime_metrics")
    adapter = _load(ADAPTER_PATH, "ctls_r2_runtime_adapter")
    context = adapter.load_context()
    daily = context.market.daily
    truth = label_engine.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    all_features = engine.feature_rows(daily.loc[:, ["close", "ma7", "atr7"]])
    return engine, label_engine, metrics, context, daily, truth, all_features


def _window_features(features: tuple[Any, ...], start: pd.Timestamp, end: pd.Timestamp) -> tuple[Any, ...]:
    return tuple(row for row in features if start <= row.ts < end)


def stage_a1() -> dict[str, Any]:
    manifest = _read(MANIFEST_PATH)
    _assert_pins(manifest["pins"])
    engine, _, _, _, daily, truth, all_features = _runtime()
    d_start = pd.Timestamp(daily.index[0])
    d_end = pd.Timestamp(daily.index[DEVELOPMENT_END])
    d_features = _window_features(all_features, d_start, d_end)
    block_features = []
    for start_index in range(0, DEVELOPMENT_END, BLOCK_DAYS):
        start = pd.Timestamp(daily.index[start_index])
        end = pd.Timestamp(daily.index[start_index + BLOCK_DAYS])
        block_features.append((start, end, _window_features(all_features, start, end)))
    rows = []
    for index, config in enumerate(engine.direction_grid(), 1):
        try:
            full_rows = _state_rows(engine, d_features, config)
            aggregate = _direction_metrics(full_rows, truth, d_start, d_end)
            blocks = [
                _direction_metrics(_state_rows(engine, values, config), truth, start, end)
                for start, end, values in block_features
            ]
            rows.append(
                {
                    "arm_id": f"R2D{index:04d}",
                    "status": "OK",
                    "config": asdict(config),
                    "config_sha256": _config_hash(config),
                    "complexity": _a1_complexity(config),
                    "direction_path_sha256": _hash_rows(full_rows, direction_only=True),
                    "aggregate": aggregate,
                    "blocks": blocks,
                    "gate": _direction_gate(aggregate, blocks),
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append({"arm_id": f"R2D{index:04d}", "status": "ERROR", "config": asdict(config), "error": f"{type(exc).__name__}: {exc}"})
    selected = select_a1(rows)
    errors = sum(row["status"] == "ERROR" for row in rows)
    payload = {
        "schema_version": "ctls-r2-a1-v1",
        "status": "BLOCKED" if errors else ("PASS" if selected else "FAIL"),
        "manifest_sha256": sha256(MANIFEST_PATH),
        "grid_completed": len(rows),
        "errors": errors,
        "passing_gate": sum(row.get("gate", {}).get("status") == "PASS" for row in rows),
        "unique_direction_paths": len({row["direction_path_sha256"] for row in rows if row["status"] == "OK"}),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"])
    _write_new(A1_PATH, payload)
    return {"status": payload["status"], "passing_gate": payload["passing_gate"], "selected": payload["selected_arm_ids"], "path": str(A1_PATH), "sha256": sha256(A1_PATH)}


def _a2_complexity(phase: Any) -> int:
    return sum(
        (
            ("s3", "d3", "blend").index(phase.velocity_source),
            ("ma_curvature", "drift_curvature", "blend").index(phase.accel_source),
            (0.05, 0.10, 0.20).index(phase.slow_threshold),
            (0.02, 0.05, 0.10).index(phase.accel_threshold),
        )
    )


def a2_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    aggregate = row["aggregate"]
    return (
        0 if row["gate"]["status"] == "PASS" else 1,
        -min(block["direction_balanced_accuracy"] for block in row["blocks"]),
        -aggregate["macro_f1_10"],
        -min(aggregate["slow_up_recall"], aggregate["slow_down_recall"]),
        -aggregate["accel_decel_macro_f1"],
        aggregate["direction_flip_rate"],
        row["complexity"],
        row["config_sha256"],
    )


def stage_a2() -> dict[str, Any]:
    manifest = _read(MANIFEST_PATH)
    a1 = _read(A1_PATH)
    _assert_pins(manifest["pins"])
    if a1.get("status") != "PASS" or not a1.get("selected"):
        raise RuntimeError("R2 A2 requires passing A1 parents")
    engine, _, metrics, _, daily, truth, all_features = _runtime()
    d_start = pd.Timestamp(daily.index[0])
    d_end = pd.Timestamp(daily.index[DEVELOPMENT_END])
    d_features = _window_features(all_features, d_start, d_end)
    block_features = [
        (
            pd.Timestamp(daily.index[start]),
            pd.Timestamp(daily.index[start + BLOCK_DAYS]),
            _window_features(
                all_features,
                pd.Timestamp(daily.index[start]),
                pd.Timestamp(daily.index[start + BLOCK_DAYS]),
            ),
        )
        for start in range(0, DEVELOPMENT_END, BLOCK_DAYS)
    ]
    rows = []
    sequence = 0
    for parent in a1["selected"]:
        strength_config = engine.StrengthConfig(**parent["config"])
        for phase_config in engine.phase_grid():
            sequence += 1
            full_rows = _state_rows(engine, d_features, strength_config, phase_config)
            aggregate = metrics.evaluate_state_path(full_rows, truth, start_ts=d_start, end_ts=d_end)
            blocks = [
                metrics.evaluate_state_path(
                    _state_rows(engine, values, strength_config, phase_config),
                    truth,
                    start_ts=start,
                    end_ts=end,
                )
                for start, end, values in block_features
            ]
            gate = metrics.aggregate_gate(aggregate, blocks)
            rows.append(
                {
                    "arm_id": f"R2P{sequence:04d}",
                    "parent_arm_id": parent["arm_id"],
                    "status": "OK",
                    "strength_config": parent["config"],
                    "phase_config": asdict(phase_config),
                    "config_sha256": _config_hash(strength_config, phase_config),
                    "complexity": parent["complexity"] + _a2_complexity(phase_config),
                    "state_path_sha256": _hash_rows(full_rows, direction_only=False),
                    "aggregate": aggregate,
                    "blocks": blocks,
                    "gate": gate,
                }
            )
    passing = [row for row in rows if row["gate"]["status"] == "PASS"]
    best_by_path: dict[str, dict[str, Any]] = {}
    for row in passing:
        current = best_by_path.get(row["state_path_sha256"])
        if current is None or a2_rank(row) < a2_rank(current):
            best_by_path[row["state_path_sha256"]] = row
    selected = sorted(best_by_path.values(), key=a2_rank)[:24]
    payload = {
        "schema_version": "ctls-r2-a2-v1",
        "status": "PASS" if selected else "FAIL",
        "manifest_sha256": sha256(MANIFEST_PATH),
        "a1_sha256": sha256(A1_PATH),
        "grid_completed": len(rows),
        "passing_gate": len(passing),
        "unique_state_paths": len({row["state_path_sha256"] for row in rows}),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"])
    _write_new(A2_PATH, payload)
    return {"status": payload["status"], "passing_gate": len(passing), "selected": payload["selected_arm_ids"], "path": str(A2_PATH), "sha256": sha256(A2_PATH)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("self-test", "manifest", "a1", "a2"))
    return parser.parse_args()


def main() -> None:
    stage = parse_args().stage
    if stage == "self-test":
        result = preflight()
    elif stage == "manifest":
        result = stage_manifest()
    elif stage == "a1":
        result = stage_a1()
    else:
        result = stage_a2()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

