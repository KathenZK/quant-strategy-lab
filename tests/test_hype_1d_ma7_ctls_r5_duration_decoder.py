from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "research_hype_1d_ma7_ctls_r5_duration_decoder.py"
)


def load_research():
    spec = importlib.util.spec_from_file_location("ctls_r5_research_tested", RESEARCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_duration_and_base_post_grid_counts() -> None:
    research = load_research()
    r3 = research._load(research.R3_PATH, "ctls_r5_grid_r3")
    assert len(research.duration_configs()) == 6
    assert len(research.base_post_configs(r3)) == 8


def test_minimum_dwell_prevents_rapid_state_flip() -> None:
    research = load_research()
    base = np.array([1, 1, -1, -1, 1, 1, 1, -1, -1, -1])
    result = research.duration_decode(base, research.DurationConfig(3, 1))
    assert result[:3].tolist() == [0, 0, -1]
    assert result[2:5].tolist() == [-1, -1, -1]
    assert result[5:8].tolist() == [1, 1, 1]
    assert result[-1] == -1


def test_switch_confirmation_resets_when_target_changes() -> None:
    research = load_research()
    base = np.array([1, -1, 1, 1, 0, 0])
    result = research.duration_decode(base, research.DurationConfig(3, 2))
    assert result.tolist() == [0, 0, 0, 1, 1, 1]


def test_decoder_rejects_invalid_states() -> None:
    research = load_research()
    try:
        research.duration_decode(np.array([0, 2]), research.DurationConfig(3, 1))
    except ValueError as exc:
        assert "DOWN/FLAT/UP" in str(exc)
    else:
        raise AssertionError("invalid state must fail closed")


def test_config_and_path_hashes_are_deterministic() -> None:
    research = load_research()
    r3 = research._load(research.R3_PATH, "ctls_r5_hash_r3")
    model = r3.model_configs()[0]
    post = research.base_post_configs(r3)[0]
    duration = research.duration_configs()[0]
    assert research._hash_config(model, 0.4, post, duration) == research._hash_config(
        dict(model), 0.4, post, duration
    )
    rows = [{"fold": 1, "ts": "2026-01-01", "direction": 1}]
    assert research._path_hash(rows) == research._path_hash(list(rows))
