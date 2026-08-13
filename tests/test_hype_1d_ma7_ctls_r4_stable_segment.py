from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "research_hype_1d_ma7_ctls_r4_stable_segment.py"
)


def load_research():
    spec = importlib.util.spec_from_file_location("ctls_r4_research_tested", RESEARCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_viterbi_transition_cost_suppresses_isolated_flip() -> None:
    research = load_research()
    raw = np.array([1, 1, 1, -1, 1, 1, 1])
    assert research._viterbi(raw).tolist() == [1] * 7


def test_short_trend_run_merges_equal_neighbors_or_becomes_flat() -> None:
    research = load_research()
    merged = research._short_run_cleanup(np.array([1, 1, 1, -1, -1, 1, 1, 1]))
    boundary = research._short_run_cleanup(np.array([-1, -1, 1, 1, 1]))
    assert merged.tolist() == [1] * 8
    assert boundary.tolist() == [0, 0, 1, 1, 1]


def test_stable_target_preserves_missing_boundaries() -> None:
    research = load_research()
    index = pd.date_range("2026-01-01", periods=10, tz="UTC", freq="D")
    raw = pd.Series([np.nan, 1, 1, 1, -1, 1, 1, 1, 1, np.nan], index=index)
    stable = research.stable_direction_target(raw)
    assert pd.isna(stable.iloc[0]) and pd.isna(stable.iloc[-1])
    assert stable.iloc[1:9].tolist() == [1.0] * 8


def test_probability_ema_is_causal_and_rows_sum_to_one() -> None:
    research = load_research()
    probabilities = np.array([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
    smoothed = research.ema_probabilities(probabilities, 0.20)
    assert smoothed[0].tolist() == probabilities[0].tolist()
    assert np.allclose(smoothed.sum(axis=1), 1.0)
    changed_future = probabilities.copy()
    changed_future[2] = [0.0, 1.0, 0.0]
    assert np.allclose(
        research.ema_probabilities(changed_future, 0.20)[:2],
        smoothed[:2],
    )


def test_stable_label_maturity_delays_one_more_day_than_r3() -> None:
    research = load_research()
    positions = list(research.mature_training_positions(54))
    assert positions[-1] == 50
    assert 51 not in positions


def test_config_and_path_hashes_are_deterministic() -> None:
    research = load_research()
    r3 = research._load(research.R3_PATH, "ctls_r4_hash_r3")
    model = r3.model_configs()[0]
    post = r3.post_configs()[0]
    assert research._hash_config(model, 0.2, post) == research._hash_config(
        dict(model), 0.2, post
    )
    rows = [{"fold": 1, "ts": "2026-01-01", "direction": 1}]
    assert research._path_hash(rows) == research._path_hash(list(rows))

