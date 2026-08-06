from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1h-price-kinematics-continuation/scripts/research_hype_1h_pkc.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_1h_pkc_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def hourly_prices(values: np.ndarray) -> pd.DataFrame:
    index = pd.date_range("2025-01-01 01:00", periods=len(values), freq="1h", tz="UTC")
    return pd.DataFrame(
        {"open": values, "high": values, "low": values, "close": values},
        index=index,
    )


def test_linear_path_has_unit_coherence_and_zero_roughness() -> None:
    module = load_module()
    prices = np.exp(np.linspace(0.0, 1.0, 500))
    state = module.build_kinematic_state(hourly_prices(prices))
    last = state.iloc[-1]
    assert last["coherence_72"] == pytest.approx(1.0)
    assert last["roughness_72"] == pytest.approx(0.0, abs=1e-12)
    assert last["scale_alignment"] == 3
    assert last["direction"] == 1


def test_state_features_are_causal_under_future_price_change() -> None:
    module = load_module()
    prices = np.exp(np.linspace(0.0, 0.2, 500))
    original = hourly_prices(prices)
    changed = original.copy()
    changed.iloc[300:, changed.columns.get_loc("close")] *= 3.0
    changed.iloc[300:, changed.columns.get_loc("open")] *= 3.0
    changed.iloc[300:, changed.columns.get_loc("high")] *= 3.0
    changed.iloc[300:, changed.columns.get_loc("low")] *= 3.0
    state_a = module.build_kinematic_state(original)
    state_b = module.build_kinematic_state(changed)
    pd.testing.assert_series_equal(
        state_a.loc[state_a.index[250], list(module.FULL_FEATURES)],
        state_b.loc[state_b.index[250], list(module.FULL_FEATURES)],
    )


def test_future_label_follows_past_direction_and_horizon() -> None:
    module = load_module()
    prices = np.exp(np.linspace(0.0, 1.0, 800))
    state = module.build_kinematic_state(hourly_prices(prices))
    labelled = module.add_future_labels(state)
    row = labelled.iloc[200]
    assert row["direction"] == 1
    assert row["future_return_72"] > 0
    assert row["continuation_72"] == 1
    assert row["mfe_72"] > 0
    assert row["mae_72"] == pytest.approx(0.0)


def test_train_edges_are_reused_without_validation_refit() -> None:
    module = load_module()
    train = pd.Series(np.arange(100, dtype=float))
    validation = pd.Series([-1_000.0, 1_000.0])
    edges = module.frozen_edges(train)
    bins = module.apply_edges(validation, edges)
    assert bins.tolist() == [1.0, 5.0]


def test_primary_anchor_phase_is_utc_four_hour_grid() -> None:
    module = load_module()
    prices = np.exp(np.linspace(0.0, 1.0, 200))
    state = module.build_kinematic_state(hourly_prices(prices))
    primary = state.loc[state["anchor_phase"].eq(module.PRIMARY_PHASE)]
    assert set(primary.index.hour) == {0, 4, 8, 12, 16, 20}
