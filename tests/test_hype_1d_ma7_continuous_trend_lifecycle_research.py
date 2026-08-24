from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "research_hype_1d_ma7_continuous_trend_lifecycle.py"
)
ENGINE_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def row(arm_id: str, path: str, *, complexity: int, score: float, passed: bool = True):
    return {
        "arm_id": arm_id,
        "status": "OK",
        "state_path_sha256": path,
        "complexity": complexity,
        "config_sha256": arm_id.lower().ljust(64, "0"),
        "aggregate": {
            "direction_balanced_accuracy": score,
            "macro_f1_10": score,
            "slow_up_recall": score,
            "slow_down_recall": score,
            "accel_decel_macro_f1": score,
            "direction_flip_rate": 0.1,
        },
        "blocks": [{"direction_balanced_accuracy": score}] * 6,
        "gate": {"status": "PASS" if passed else "FAIL"},
    }


def test_independent_selection_keeps_lower_complexity_for_equal_path() -> None:
    research = load(RESEARCH_PATH, "ctls_research_selection")
    selected = research.select_independent(
        [
            row("A001", "same", complexity=4, score=0.70),
            row("A002", "same", complexity=1, score=0.60),
            row("A003", "other", complexity=2, score=0.65),
            row("A004", "failed", complexity=0, score=0.90, passed=False),
        ]
    )
    assert {value["arm_id"] for value in selected} == {"A002", "A003"}
    assert all(value["gate"]["status"] == "PASS" for value in selected)


def test_rank_prefers_worst_block_then_aggregate_before_complexity() -> None:
    research = load(RESEARCH_PATH, "ctls_research_rank")
    first = row("A001", "one", complexity=9, score=0.61)
    second = row("A002", "two", complexity=0, score=0.60)
    assert research.stage_a_rank_key(first) < research.stage_a_rank_key(second)


def test_cold_flat_replay_does_not_inherit_pre_window_direction() -> None:
    research = load(RESEARCH_PATH, "ctls_research_cold")
    engine = load(ENGINE_PATH, "ctls_engine_cold")
    index = pd.date_range("2026-01-01", periods=20, tz="UTC", freq="D")
    close = np.r_[100 + np.arange(10) * 0.2, 102 - np.arange(10) * 0.2]
    ma7 = np.r_[close[:10] - 0.1, close[10:] + 0.1]
    daily = pd.DataFrame({"close": close, "ma7": ma7, "atr7": 1.0}, index=index)
    config = engine.DetectionConfig(0.0, 0.0, 0.0, 0.1, 2, 2)
    rows = research._state_rows(engine, daily, config, 10, 20)
    assert rows[0]["direction"] == 0
    assert any(value["direction"] == -1 for value in rows[1:])


def test_locked_json_is_exclusive_and_never_overwrites(tmp_path: Path) -> None:
    research = load(RESEARCH_PATH, "ctls_research_lock")
    target = tmp_path / "locked.json"
    research._write_new_json(target, {"status": "FIRST"})
    with pytest.raises(RuntimeError, match="already exists"):
        research._write_new_json(target, {"status": "SECOND"})
    assert json.loads(target.read_text()) == {"status": "FIRST"}


def test_strict_json_maps_only_nonfinite_evidence_to_null(tmp_path: Path) -> None:
    research = load(RESEARCH_PATH, "ctls_research_json_safe")
    target = tmp_path / "strict.json"
    research._write_new_json(
        target,
        {"finite": 1.5, "missing": float("nan"), "nested": [float("inf"), -2.0]},
    )
    assert json.loads(target.read_text()) == {
        "finite": 1.5,
        "missing": None,
        "nested": [None, -2.0],
    }
