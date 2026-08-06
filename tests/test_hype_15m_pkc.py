from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/15m-price-kinematics-continuation/scripts/research_hype_15m_pkc.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_15m_pkc_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def visible_prices(values: np.ndarray) -> pd.DataFrame:
    index = pd.date_range(
        "2025-01-01 00:00", periods=len(values), freq="15min", tz="UTC"
    )
    return pd.DataFrame(
        {"open": values, "high": values, "low": values, "close": values}, index=index
    )


def test_frozen_short_horizon_contract() -> None:
    module = load_module()
    engine = module.load_engine()
    assert engine.PAST_WINDOWS == (4, 12, 24)
    assert engine.FUTURE_HORIZONS == (4, 12, 24, 48)
    assert engine.DIRECTION_WINDOW == 12
    assert engine.SENSITIVITY_HORIZON == 24
    assert engine.BAR_MINUTES == 15


def test_visibility_moves_open_timestamp_to_bar_close() -> None:
    module = load_module()
    frame = visible_prices(np.array([100.0, 101.0, 102.0, 103.0]))
    visible, quality = module.prepare_visible_15m(frame)
    assert quality["accepted"] is True
    assert visible.index[0] == frame.index[0] + pd.Timedelta(minutes=15)


def test_linear_15m_path_has_expected_geometry() -> None:
    module = load_module()
    engine = module.load_engine()
    prices = np.exp(np.linspace(0.0, 1.0, 500))
    state = engine.build_kinematic_state(visible_prices(prices))
    last = state.iloc[-1]
    assert last["direction"] == 1
    assert last["coherence_24"] == pytest.approx(1.0)
    assert last["roughness_24"] == pytest.approx(0.0, abs=1e-12)
    assert last["scale_alignment"] == 3


def test_primary_phase_is_hourly_close_grid() -> None:
    module = load_module()
    engine = module.load_engine()
    prices = np.exp(np.linspace(0.0, 1.0, 500))
    state = engine.build_kinematic_state(visible_prices(prices))
    primary = state.loc[state["anchor_phase"].eq(0)]
    assert set(primary.index.minute) == {0}


def test_future_12h_label_uses_48_bars() -> None:
    module = load_module()
    engine = module.load_engine()
    prices = np.exp(np.linspace(0.0, 1.0, 500))
    state = engine.build_kinematic_state(visible_prices(prices))
    labelled = engine.add_future_labels(state)
    row = labelled.iloc[100]
    expected = np.log(prices[148]) - np.log(prices[100])
    assert row["future_return_48"] == pytest.approx(expected)
    assert row["continuation_48"] == 1
