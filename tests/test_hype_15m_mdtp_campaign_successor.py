from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/15m-multidimensional-trend-pyramiding/scripts"
    / "research_hype_15m_mdtp_campaign_successor.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_mdtp_campaign", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_search_space_is_complete_and_unique() -> None:
    module = load_module()
    candidates = module.configs()
    assert len(candidates) == 54
    assert len({candidate.label for candidate in candidates}) == 54


@pytest.mark.parametrize(
    ("delta", "expected"),
    ((1.0, 100.04), (-1.0, 99.96)),
)
def test_adverse_fill_moves_against_the_order(delta: float, expected: float) -> None:
    module = load_module()
    assert module.adverse_fill(100.0, delta, 0.0004) == pytest.approx(expected)


def test_flat_price_campaign_keeps_fixed_quantity_between_entry_and_exit() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=8, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1.0,
        },
        index=index,
    )
    events = pd.DataFrame(
        {
            "entry_signal": [True],
            "atr24": [1.0],
            "initial_structure": [90.0],
            "entry_boundary": [99.0],
            "regime_same": [True],
            "regime_opposite": [False],
            "structural_stop": [float("nan")],
            "close_1h": [100.0],
            "add_1_signal": [False],
            "add_2_signal": [False],
        },
        index=pd.DatetimeIndex([index[0]]),
    )
    funding = pd.Series(0.0, index=index)
    config = module.CandidateConfig(30, 48, 2.5, 18)
    result = module.backtest(
        frame,
        funding,
        events,
        side=1,
        config=config,
        start=index[0],
        end=index[-1] + pd.Timedelta(minutes=15),
        retain=True,
    )

    assert result.metrics["risk_breaches"] == 0
    assert result.metrics["max_fill_leverage"] <= 3.0
    assert result.metrics["action_counts"] == {
        "entry_seed": 1,
        "exit_terminal_flatten": 1,
    }
    assert len(result.actions) == 2
    assert result.actions.iloc[0]["quantity_after"] == pytest.approx(
        result.actions.iloc[1]["quantity_before"]
    )
    assert result.metrics["total_return_pct"] < 0.0
