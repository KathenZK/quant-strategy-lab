from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "research_hype_1d_ma7_ctls_r2_continuous_strength.py"
)


def load_research():
    spec = importlib.util.spec_from_file_location("ctls_r2_research_tested", RESEARCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_direction_metrics_use_three_classes_and_exclude_boundaries() -> None:
    research = load_research()
    index = pd.date_range("2026-01-01", periods=15, tz="UTC", freq="D")
    truth_labels = ["down_slow"] * 5 + ["neutral"] * 5 + ["up_slow"] * 5
    truth = pd.Series(truth_labels, index=index)
    rows = [
        {
            "ts": ts.isoformat(),
            "direction": research._direction(label),
        }
        for ts, label in zip(index, truth_labels, strict=True)
    ]
    result = research._direction_metrics(
        rows,
        truth,
        index[0],
        index[-1] + pd.Timedelta(days=1),
    )
    assert result["samples"] == 9
    assert result["balanced_accuracy"] == 1.0
    assert result["recalls"] == {"down": 1.0, "flat": 1.0, "up": 1.0}


def test_direction_gate_requires_flat_recall_and_four_blocks() -> None:
    research = load_research()
    aggregate = {
        "balanced_accuracy": 0.60,
        "recalls": {"down": 0.60, "flat": 0.39, "up": 0.60},
        "flip_rate": 0.10,
    }
    blocks = [{"balanced_accuracy": 0.51}] * 6
    assert research._direction_gate(aggregate, blocks)["status"] == "FAIL"
    aggregate["recalls"]["flat"] = 0.50
    assert research._direction_gate(aggregate, blocks)["status"] == "PASS"


def candidate(arm_id: str, path: str, complexity: int, score: float):
    return {
        "arm_id": arm_id,
        "status": "OK",
        "direction_path_sha256": path,
        "complexity": complexity,
        "config_sha256": arm_id.lower().ljust(64, "0"),
        "aggregate": {
            "balanced_accuracy": score,
            "recalls": {"down": score, "flat": score, "up": score},
            "flip_rate": 0.10,
        },
        "blocks": [{"balanced_accuracy": score}] * 6,
        "gate": {"status": "PASS"},
    }


def test_a1_dedup_keeps_simpler_equal_direction_path() -> None:
    research = load_research()
    selected = research.select_a1(
        [
            candidate("R2D0001", "same", 5, 0.70),
            candidate("R2D0002", "same", 1, 0.60),
            candidate("R2D0003", "other", 2, 0.65),
        ]
    )
    assert {row["arm_id"] for row in selected} == {"R2D0002", "R2D0003"}


def test_direction_hash_ignores_phase_but_full_hash_does_not() -> None:
    research = load_research()
    first = [{"ts": "2026-01-01", "direction": 1, "phase": "slow"}]
    second = [{"ts": "2026-01-01", "direction": 1, "phase": "accelerating"}]
    assert research._hash_rows(first, direction_only=True) == research._hash_rows(
        second, direction_only=True
    )
    assert research._hash_rows(first, direction_only=False) != research._hash_rows(
        second, direction_only=False
    )

