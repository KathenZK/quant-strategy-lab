"""Fail-closed orchestrator for the CTLS continuous-trend research branch."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PREREG_PATH = FAMILY_DIR / "specs/hype-1d-ma7-continuous-trend-lifecycle-preregistration-2026-08-10.md"
REPAIR_PATH = FAMILY_DIR / "specs/hype-1d-ma7-ctls-preperformance-repair-2026-08-10.md"
ENGINE_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
HARNESS_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_harness.py"
METRICS_PATH = SCRIPT_DIR / "hype_1d_ma7_continuous_trend_lifecycle_metrics.py"
ADAPTER_PATH = SCRIPT_DIR / "hype_1d_ma7_v4_fair_adapter.py"
ORCHESTRATOR_PATH = Path(__file__)
TEST_PATHS = (
    ROOT / "tests/test_hype_1d_ma7_continuous_trend_lifecycle_engine.py",
    ROOT / "tests/test_hype_1d_ma7_continuous_trend_lifecycle_harness.py",
    ROOT / "tests/test_hype_1d_ma7_continuous_trend_lifecycle_metrics.py",
    ROOT / "tests/test_hype_1d_ma7_continuous_trend_lifecycle_research.py",
)
IMPLEMENTATION_PATHS = (
    PREREG_PATH,
    REPAIR_PATH,
    ENGINE_PATH,
    HARNESS_PATH,
    METRICS_PATH,
    ADAPTER_PATH,
    ORCHESTRATOR_PATH,
    *TEST_PATHS,
)
MANIFEST_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_2026-08-10_manifest_v2.json"
STAGE_A_PATH = ARTIFACT_DIR / "hype_1d_ma7_ctls_2026-08-10_stage_a_v2.json"
DEVELOPMENT_START = 0
DEVELOPMENT_END = 324
BLOCK_DAYS = 54
EXPECTED_STAGE_A = 324
EXPECTED_PREFLIGHT_TESTS = 24


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
        drift = {
            key: {"expected": expected.get(key), "actual": actual.get(key)}
            for key in sorted(set(expected) | set(actual))
            if expected.get(key) != actual.get(key)
        }
        raise RuntimeError(f"CTLS implementation pin drift: {drift}")


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode()
    try:
        with path.open("xb") as handle:
            handle.write(encoded)
            handle.write(b"\n")
    except FileExistsError as exc:
        raise RuntimeError(f"locked artifact already exists: {path}") from exc


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"required upstream artifact is absent: {path}")
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f"artifact root must be an object: {path}")
    return value


def run_preflight() -> dict[str, Any]:
    before = _pins()
    command = [str(ROOT / ".venv/bin/pytest"), "-q", *map(str, TEST_PATHS)]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(value for value in (completed.stdout, completed.stderr) if value)
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    after = _pins()
    status = (
        "PASS"
        if completed.returncode == 0
        and passed == EXPECTED_PREFLIGHT_TESTS
        and before == after
        else "FAIL"
    )
    result = {
        "status": status,
        "returncode": completed.returncode,
        "passed": passed,
        "expected_passed": EXPECTED_PREFLIGHT_TESTS,
        "pins_stable": before == after,
        "output": output.strip(),
    }
    if status != "PASS":
        raise RuntimeError(f"CTLS preflight failed: {result}")
    return result


def build_manifest(preflight: dict[str, Any]) -> dict[str, Any]:
    pins = _pins()
    adapter = _load(ADAPTER_PATH, "ctls_manifest_v4_adapter")
    context = adapter.load_context()
    engine = _load(ENGINE_PATH, "ctls_manifest_engine")
    grid = engine.detection_grid()
    if len(grid) != EXPECTED_STAGE_A or len(set(grid)) != EXPECTED_STAGE_A:
        raise RuntimeError("CTLS Stage A grid cardinality drift")
    market = context.market
    return {
        "schema_version": "ctls-manifest-v2",
        "status": "LOCKED",
        "branch": "CTLS",
        "created_at": "2026-08-10",
        "visibility": "all_432_days_researcher_exposed",
        "supersedes_execution_manifest": {
            "path": str((ARTIFACT_DIR / "hype_1d_ma7_ctls_2026-08-10_manifest.json").relative_to(ROOT)),
            "sha256": "ae9e83a958e9b37844cacc31b58dcee8a1b8a9fababbdd97d0c2f326f507c53c",
            "reason": "pre-performance strict-JSON and incomplete-MA label repair",
        },
        "windows": {
            "development": [DEVELOPMENT_START, DEVELOPMENT_END],
            "development_blocks": [
                [start, start + BLOCK_DAYS]
                for start in range(DEVELOPMENT_START, DEVELOPMENT_END, BLOCK_DAYS)
            ],
            "locked_exposed_stress": [324, 432],
            "full_exposed": [0, 432],
            "clean_prospective_not_before": "2026-08-11T00:00:00+00:00",
        },
        "stage_a_grid_count": len(grid),
        "stage_b_max_count": 3888,
        "stage_c_max_count": 864,
        "preflight": preflight,
        "pins": pins,
        "market": {
            "book_count": market.book.count,
            "terminal_ts": pd.Timestamp(market.book.terminal_ts).isoformat(),
            "audit": market.audit,
            "adapter_pins": dict(context.pins),
        },
    }


def stage_manifest() -> dict[str, Any]:
    preflight = run_preflight()
    manifest = build_manifest(preflight)
    _assert_pins(manifest["pins"])
    _write_new_json(MANIFEST_PATH, manifest)
    return {"status": "PASS", "path": str(MANIFEST_PATH), "sha256": sha256(MANIFEST_PATH)}


def _state_rows(engine: Any, daily: pd.DataFrame, config: Any, start: int, end: int) -> list[dict[str, Any]]:
    machine = engine.ContinuousTrendMachine(config)
    start_ts = pd.Timestamp(daily.index[start])
    end_ts = pd.Timestamp(daily.index[end]) if end < len(daily) else pd.Timestamp(daily.index[-1]) + pd.Timedelta(days=1)
    rows: list[dict[str, Any]] = []
    for features in engine.feature_rows(daily.loc[:, ["close", "ma7", "atr7"]]):
        if not start_ts <= features.ts < end_ts:
            continue
        snapshot = machine.observe(features)
        rows.append(
            {
                "ts": snapshot.ts.isoformat(),
                "direction": int(snapshot.direction),
                "phase": snapshot.phase.value,
                "label": snapshot.label.value,
                "transition": snapshot.transition,
                "up_score": snapshot.up_score,
                "down_score": snapshot.down_score,
            }
        )
    return rows


def _complexity(config: Any) -> int:
    ranks = (
        (0.0, 0.10, 0.25).index(config.distance_min),
        (0.0, 0.01, 0.02).index(config.slow_slope_min),
        (0.0, 0.05, 0.10).index(config.drift_min),
        (0.10, 0.20, 0.30).index(config.er_min),
        config.direction_score_min - 2,
        config.enter_confirm_days - 1,
    )
    return int(sum(ranks))


def _finite_rank(value: float, *, worst: float = -math.inf) -> float:
    return float(value) if math.isfinite(float(value)) else worst


def stage_a_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    aggregate = row["aggregate"]
    block_worst = min(block["direction_balanced_accuracy"] for block in row["blocks"])
    return (
        0 if row["gate"]["status"] == "PASS" else 1,
        -_finite_rank(block_worst),
        -_finite_rank(aggregate["direction_balanced_accuracy"]),
        -_finite_rank(aggregate["macro_f1_10"]),
        -_finite_rank(min(aggregate["slow_up_recall"], aggregate["slow_down_recall"])),
        -_finite_rank(aggregate["accel_decel_macro_f1"]),
        _finite_rank(aggregate["direction_flip_rate"], worst=math.inf),
        row["complexity"],
        row["config_sha256"],
    )


def _config_hash(config: Any) -> str:
    payload = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def select_independent(rows: list[dict[str, Any]], limit: int = 24) -> list[dict[str, Any]]:
    passing = [row for row in rows if row.get("status") == "OK" and row["gate"]["status"] == "PASS"]
    best_by_path: dict[str, dict[str, Any]] = {}
    for row in passing:
        current = best_by_path.get(row["state_path_sha256"])
        if current is None or (row["complexity"], stage_a_rank_key(row)) < (
            current["complexity"],
            stage_a_rank_key(current),
        ):
            best_by_path[row["state_path_sha256"]] = row
    return sorted(best_by_path.values(), key=stage_a_rank_key)[:limit]


def stage_a() -> dict[str, Any]:
    manifest = _read_json(MANIFEST_PATH)
    if manifest.get("status") != "LOCKED":
        raise RuntimeError("CTLS manifest is not locked")
    _assert_pins(manifest["pins"])
    engine = _load(ENGINE_PATH, "ctls_stage_a_engine")
    metrics = _load(METRICS_PATH, "ctls_stage_a_metrics")
    adapter = _load(ADAPTER_PATH, "ctls_stage_a_v4_adapter")
    context = adapter.load_context()
    daily = context.market.daily
    truth = engine.hindsight_labels(daily.loc[:, ["close", "ma7", "atr7"]])
    d_start_ts = pd.Timestamp(daily.index[DEVELOPMENT_START])
    d_end_ts = pd.Timestamp(daily.index[DEVELOPMENT_END])
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(engine.detection_grid(), 1):
        identity = f"A{index:03d}"
        try:
            full_rows = _state_rows(engine, daily, config, DEVELOPMENT_START, DEVELOPMENT_END)
            aggregate = metrics.evaluate_state_path(
                full_rows,
                truth,
                start_ts=d_start_ts,
                end_ts=d_end_ts,
            )
            blocks = []
            for start in range(DEVELOPMENT_START, DEVELOPMENT_END, BLOCK_DAYS):
                end = start + BLOCK_DAYS
                block_rows = _state_rows(engine, daily, config, start, end)
                blocks.append(
                    metrics.evaluate_state_path(
                        block_rows,
                        truth,
                        start_ts=pd.Timestamp(daily.index[start]),
                        end_ts=pd.Timestamp(daily.index[end]),
                    )
                )
            gate = metrics.aggregate_gate(aggregate, blocks)
            rows.append(
                {
                    "arm_id": identity,
                    "status": "OK",
                    "config": asdict(config),
                    "config_sha256": _config_hash(config),
                    "complexity": _complexity(config),
                    "state_path_sha256": metrics.state_path_sha256(full_rows),
                    "state_rows": len(full_rows),
                    "aggregate": aggregate,
                    "blocks": blocks,
                    "gate": gate,
                }
            )
        except Exception as exc:  # noqa: BLE001 - every grid failure is retained
            rows.append(
                {
                    "arm_id": identity,
                    "status": "ERROR",
                    "config": asdict(config),
                    "config_sha256": _config_hash(config),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    selected = select_independent(rows)
    errors = [row for row in rows if row["status"] == "ERROR"]
    payload = {
        "schema_version": "ctls-stage-a-v2",
        "status": "BLOCKED" if errors else ("PASS" if selected else "FAIL"),
        "manifest_sha256": sha256(MANIFEST_PATH),
        "pins": manifest["pins"],
        "grid_expected": EXPECTED_STAGE_A,
        "grid_completed": len(rows),
        "errors": len(errors),
        "passing_accuracy_gate": sum(
            row.get("gate", {}).get("status") == "PASS" for row in rows
        ),
        "unique_state_paths": len(
            {row["state_path_sha256"] for row in rows if row["status"] == "OK"}
        ),
        "selected_arm_ids": [row["arm_id"] for row in selected],
        "selected": selected,
        "rows": rows,
    }
    _assert_pins(manifest["pins"])
    _write_new_json(STAGE_A_PATH, payload)
    return {
        "status": payload["status"],
        "path": str(STAGE_A_PATH),
        "sha256": sha256(STAGE_A_PATH),
        "passing_accuracy_gate": payload["passing_accuracy_gate"],
        "selected": payload["selected_arm_ids"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("self-test", "manifest", "stage-a"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "self-test":
        result = run_preflight()
    elif args.stage == "manifest":
        result = stage_manifest()
    else:
        result = stage_a()
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
