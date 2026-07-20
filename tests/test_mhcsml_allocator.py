from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/search_development_allocator.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "search_development_allocator_for_test", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_overlapping_sleeves_cap_scheduled_gross_and_compound_on_exit() -> None:
    allocator = load_script()
    decisions = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=3, freq="4h", tz="UTC"),
            "fold_id": ["fold"] * 3,
            "active": [True, True, True],
            "portfolio_return": [0.10, 0.10, 0.10],
        }
    )

    curve, notionals, max_open_gross = allocator.simulate_overlapping_sleeves(
        decisions,
        return_column="portfolio_return",
        horizon=8,
        sleeve_exposure=0.5,
    )

    assert max_open_gross == pytest.approx(1.0)
    np.testing.assert_allclose(notionals, [0.5, 0.5, 0.525])
    assert curve["equity"].iloc[-1] == pytest.approx(1.1525)


def test_inactive_decisions_remain_zero_return_observations() -> None:
    allocator = load_script()
    decisions = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=3, freq="4h", tz="UTC"),
            "fold_id": ["fold"] * 3,
            "active": [False, False, False],
            "portfolio_return": [0.0, 0.0, 0.0],
        }
    )

    curve, notionals, max_open_gross = allocator.simulate_overlapping_sleeves(
        decisions,
        return_column="portfolio_return",
        horizon=8,
        sleeve_exposure=0.5,
    )

    assert len(curve) == 3
    assert curve["period_return"].eq(0.0).all()
    assert curve["equity"].eq(1.0).all()
    assert notionals.sum() == 0.0
    assert max_open_gross == 0.0


def test_bankrupt_account_cannot_be_resurrected_by_later_pending_profit() -> None:
    allocator = load_script()
    decisions = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=2, freq="4h", tz="UTC"),
            "fold_id": ["fold"] * 2,
            "active": [True, True],
            "portfolio_return": [-3.0, 3.0],
        }
    )

    curve, _, _ = allocator.simulate_overlapping_sleeves(
        decisions,
        return_column="portfolio_return",
        horizon=8,
        sleeve_exposure=0.5,
    )

    assert curve["equity"].iloc[-1] == 0.0
    assert curve["drawdown"].min() == -1.0


def test_dynamic_allocator_never_opens_both_sides_of_same_symbol() -> None:
    allocator = load_script()
    ts = pd.Timestamp("2025-01-01T00:00:00Z")
    candidates = pd.DataFrame(
        {
            "ts": [ts, ts, ts, ts],
            "symbol": ["A", "A", "B", "B"],
            "fold_id": ["fold"] * 4,
            "side": ["long", "short", "long", "short"],
            "return_z": [2.0, 1.0, 0.8, 1.5],
            "mae_z": [0.0, 0.0, 0.0, 0.0],
            "event_z": [0.0, 0.0, 0.0, 0.0],
            "trade_return": [0.01, -0.01, 0.02, 0.03],
            "stress_trade_return": [0.0086, -0.0114, 0.0186, 0.0286],
        }
    )

    selected = allocator.select_legs(
        candidates,
        side_mode="long_short_dynamic",
        mae_penalty=0.0,
        event_penalty=0.0,
        utility_threshold=1.0,
        max_positions=3,
        mae_z_max=0.5,
        event_z_max=0.5,
    )

    assert not selected.duplicated(["ts", "symbol"]).any()
    assert dict(zip(selected["symbol"], selected["side"], strict=True)) == {
        "A": "long",
        "B": "short",
    }


def test_decision_frequency_uses_utc_clock_hours_not_timestamp_storage_unit() -> None:
    allocator = load_script()
    timestamps = pd.date_range("2025-01-01", periods=4, freq="4h", tz="UTC")
    candidates = pd.DataFrame(
        {
            "ts": timestamps,
            "symbol": ["A"] * 4,
            "fold_id": ["fold"] * 4,
            "side": ["long"] * 4,
            "utility": [2.0] * 4,
            "trade_return": [0.01] * 4,
            "stress_trade_return": [0.0086] * 4,
        }
    )

    decisions, legs = allocator.scheduled_policy(
        candidates,
        candidates,
        decision_frequency=8,
    )

    assert decisions["ts"].dt.hour.tolist() == [0, 8]
    assert legs["ts"].dt.hour.tolist() == [0, 8]
