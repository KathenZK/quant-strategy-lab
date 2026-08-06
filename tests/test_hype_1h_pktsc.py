from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1h-price-kinematic-trend-survival-control/scripts/research_hype_1h_pktsc.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_1h_pktsc_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def source_frame(hours: int, slope: float = 0.001) -> pd.DataFrame:
    count = hours * 4
    index = pd.date_range("2025-01-01", periods=count, freq="15min", tz="UTC")
    values = np.exp(np.arange(count) * slope / 4.0) * 100.0
    return pd.DataFrame(
        {
            "open": values,
            "high": values * 1.0002,
            "low": values * 0.9998,
            "close": values,
        },
        index=index,
    )


def test_complete_hourly_visibility_and_quality() -> None:
    module = load_module()
    execution, visible, quality = module.build_complete_hourly(source_frame(10))
    assert quality["accepted"] is True
    assert len(execution) == 10
    assert visible.index[0] == execution.index[0] + pd.Timedelta(hours=1)


def test_linear_price_state_is_causal_and_coherent() -> None:
    module = load_module()
    _, visible, _ = module.build_complete_hourly(source_frame(500))
    state = module.build_price_state(visible)
    last = state.iloc[-1]
    assert last["direction"] == 1
    assert last["coherence_336"] == pytest.approx(1.0)
    assert last["roughness_336"] == pytest.approx(0.0, abs=1e-12)
    assert last["slow_alignment"] == 3


def test_dynamic_layers_require_profit_and_stronger_probability() -> None:
    module = load_module()
    assert module.desired_dynamic_fraction(0.54, 3.0, 1.0, True) == 0.35
    assert module.desired_dynamic_fraction(0.58, 0.0, 1.0, True) == 0.70
    assert module.desired_dynamic_fraction(0.61, 1.0, 1.0, True) == 0.85
    assert module.desired_dynamic_fraction(0.63, 2.0, 1.0, True) == 1.00
    assert module.desired_dynamic_fraction(0.63, 3.0, 1.0, False) == 0.35


def test_opposite_prequential_direction_exits_existing_campaign() -> None:
    module = load_module()
    hourly, _, _ = module.build_complete_hourly(source_frame(30, slope=0.0))
    start = pd.Timestamp("2025-09-01 00:00:00+00:00")
    hourly.index = pd.date_range(start, periods=len(hourly), freq="1h", tz="UTC")
    predictions = pd.DataFrame(
        [
            {
                "ts": start,
                "horizon_hours": 24,
                "side": 1,
                "slow_alignment": 3,
                "full_prob": 0.60,
                "full_z_pred": 0.20,
                "stop_distance_log": 0.05,
            },
            {
                "ts": start + pd.Timedelta(hours=4),
                "horizon_hours": 24,
                "side": -1,
                "slow_alignment": 3,
                "full_prob": 0.60,
                "full_z_pred": 0.20,
                "stop_distance_log": 0.05,
            },
        ]
    )
    old_start = module.WF_START
    old_end = module.PROSPECTIVE_START
    module.WF_START = start
    module.PROSPECTIVE_START = start + pd.Timedelta(hours=30)
    try:
        actions, campaigns = module.build_campaign_schedule(
            hourly, predictions, side=1
        )
    finally:
        module.WF_START = old_start
        module.PROSPECTIVE_START = old_end
    assert actions.iloc[0]["action"] == "entry"
    assert campaigns.iloc[0]["exit_reason"] == "probability_or_direction_exit"
    assert campaigns.iloc[0]["hold_hours"] == 4.0
