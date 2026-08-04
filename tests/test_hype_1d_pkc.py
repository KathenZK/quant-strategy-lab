from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-price-kinematics-continuation/scripts/research_hype_1d_pkc.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_1d_pkc_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_prices(days: int) -> pd.DataFrame:
    periods = days * 96
    index = pd.date_range("2025-01-01", periods=periods, freq="15min", tz="UTC")
    values = np.exp(np.linspace(0.0, 1.0, periods))
    return pd.DataFrame(
        {"open": values, "high": values, "low": values, "close": values},
        index=index,
    )


def test_frozen_daily_contract() -> None:
    module = load_module()
    engine = module.load_engine()
    assert engine.PAST_WINDOWS == (3, 7, 14)
    assert engine.FUTURE_HORIZONS == (3, 7, 14)
    assert engine.DIRECTION_WINDOW == 7
    assert engine.BAR_MINUTES == 1_440
    assert engine.PRIMARY_PHASE is None


def test_daily_aggregation_requires_96_bars_and_moves_to_availability() -> None:
    module = load_module()
    frame = source_prices(3)
    daily, quality = module.build_complete_daily(frame)
    assert quality["accepted"] is True
    assert len(daily) == 3
    assert daily.index[0] == pd.Timestamp("2025-01-02 00:00:00+00:00")
    assert daily["source_bars"].eq(96).all()


def test_linear_daily_path_has_expected_geometry_and_labels() -> None:
    module = load_module()
    engine = module.load_engine()
    daily, _ = module.build_complete_daily(source_prices(100))
    state = engine.build_kinematic_state(daily)
    labelled = engine.add_future_labels(state)
    row = labelled.iloc[30]
    assert row["direction"] == 1
    assert row["coherence_14"] == pytest.approx(1.0)
    assert row["roughness_14"] == pytest.approx(0.0, abs=1e-12)
    assert row["future_return_14"] > 0
    assert row["continuation_14"] == 1


def test_daily_stride_phases_cover_all_days() -> None:
    module = load_module()
    engine = module.load_engine()
    daily, _ = module.build_complete_daily(source_prices(30))
    state = engine.build_kinematic_state(daily)
    assert set(state["anchor_phase"].unique()) == set(range(7))
