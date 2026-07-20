from __future__ import annotations

import importlib.util
import numpy as np
import pandas as pd
from pathlib import Path
import pytest
import sys

from strategy_lab.data.linear_contract_returns import long_net_return, short_net_return


ROOT = Path(__file__).resolve().parents[1]
PANEL_SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1h-cross-sectional-lightgbm-selector/"
    "scripts/build_cross_sectional_factor_panel.py"
)


def load_panel_script():
    spec = importlib.util.spec_from_file_location(
        "build_cross_sectional_factor_panel_for_return_test",
        PANEL_SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_linear_contract_long_and_short_returns_are_not_reciprocals() -> None:
    entry = 100.0
    exit_price = 50.0

    assert long_net_return(
        entry,
        exit_price,
        round_trip_cost=0.0,
        funding_sum=0.0,
    ) == pytest.approx(-0.5)
    assert short_net_return(
        entry,
        exit_price,
        round_trip_cost=0.0,
        funding_sum=0.0,
    ) == pytest.approx(0.5)


def test_linear_contract_cost_and_funding_have_directional_signs() -> None:
    entry = np.array([100.0, 100.0])
    exit_price = np.array([110.0, 90.0])
    funding = np.array([0.001, -0.002])

    long_result = long_net_return(
        entry,
        exit_price,
        round_trip_cost=0.0028,
        funding_sum=funding,
    )
    short_result = short_net_return(
        entry,
        exit_price,
        round_trip_cost=0.0028,
        funding_sum=funding,
    )

    np.testing.assert_allclose(long_result, [0.0962, -0.1008])
    np.testing.assert_allclose(short_result, [-0.1018, 0.0952])


def test_linear_contract_returns_preserve_series_index_and_missing_values() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="1h", tz="UTC")
    entry = pd.Series([100.0, 100.0, np.nan], index=index)
    exit_price = pd.Series([105.0, 95.0, 90.0], index=index)
    funding = pd.Series([0.0, 0.001, 0.0], index=index)

    result = short_net_return(
        entry,
        exit_price,
        round_trip_cost=0.0028,
        funding_sum=funding,
    )

    assert result.index.equals(index)
    assert result.iloc[0] == pytest.approx(-0.0528)
    assert result.iloc[1] == pytest.approx(0.0482)
    assert pd.isna(result.iloc[2])


def test_factor_panel_add_labels_uses_linear_short_pnl() -> None:
    panel = load_panel_script()
    rows = 30
    frame = pd.DataFrame(
        {
            "open": np.linspace(100.0, 71.0, rows),
            "funding_event_rate": np.zeros(rows),
        }
    )

    labelled = panel.add_labels(frame)

    entry = frame.loc[1, "open"]
    exit_price = frame.loc[5, "open"]
    expected = 1.0 - exit_price / entry - panel.ROUND_TRIP_COST
    reciprocal_bug = entry / exit_price - 1.0 - panel.ROUND_TRIP_COST
    assert labelled.loc[0, "label_short_net_4h"] == pytest.approx(expected)
    assert labelled.loc[0, "label_short_net_4h"] != pytest.approx(reciprocal_bug)
