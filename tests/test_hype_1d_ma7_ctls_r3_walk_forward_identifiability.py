from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "research_hype_1d_ma7_ctls_r3_walk_forward_identifiability.py"
)


def load_research():
    spec = importlib.util.spec_from_file_location("ctls_r3_research_tested", RESEARCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def daily_frame(days: int = 30) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=days, tz="UTC", freq="D")
    close = 100.0 + np.arange(days) * 0.2
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "ma7": close - 0.1,
            "atr7": 1.0,
            "rsi6": 55.0,
        },
        index=index,
    )


def test_feature_builder_is_strictly_backward_looking() -> None:
    research = load_research()
    frame = daily_frame()
    changed = frame.copy()
    changed.loc[changed.index[25] :, "close"] *= 2.0
    pd.testing.assert_frame_equal(
        research.build_features(frame).loc[: frame.index[24]],
        research.build_features(changed).loc[: frame.index[24]],
    )


def test_frozen_model_and_postprocess_grid_counts() -> None:
    research = load_research()
    assert len(research.model_configs()) == 31
    assert len(research.post_configs()) == 12
    assert len({json_key(row) for row in research.model_configs()}) == 31


def json_key(value) -> str:
    import json

    return json.dumps(value, sort_keys=True)


def test_label_maturity_excludes_unavailable_last_three_training_days() -> None:
    research = load_research()
    positions = list(research.mature_training_positions(54))
    assert positions[0] == 0
    assert positions[-1] == 51
    assert 52 not in positions and 53 not in positions


def test_probability_hysteresis_can_enter_exit_and_reverse() -> None:
    research = load_research()
    probabilities = np.array(
        [
            [0.1, 0.1, 0.8],
            [0.1, 0.1, 0.8],
            [0.1, 0.8, 0.1],
            [0.1, 0.8, 0.1],
            [0.8, 0.1, 0.1],
            [0.8, 0.1, 0.1],
        ]
    )
    output = research.apply_hysteresis(
        probabilities,
        research.PostConfig(0.5, confirm_days=2, exit_confirm_days=2),
    )
    assert output.tolist() == [0, 1, 1, 0, 0, -1]


def test_direction_metrics_and_gate_are_three_class_balanced() -> None:
    research = load_research()
    actual = np.array([-1] * 10 + [0] * 10 + [1] * 10)
    predicted = actual.copy()
    metrics = research.direction_metrics(actual, predicted)
    folds = [{"balanced_accuracy": 1.0}] * 5
    assert metrics["balanced_accuracy"] == 1.0
    assert research._gate(metrics, folds)["status"] == "PASS"


def test_config_and_path_hashes_are_deterministic() -> None:
    research = load_research()
    model = research.model_configs()[0]
    post = research.post_configs()[0]
    assert research._hash_config(model, post) == research._hash_config(dict(model), post)
    rows = [{"fold": 1, "ts": "2026-01-01", "direction": 1}]
    assert research._path_hash(rows) == research._path_hash(list(rows))
