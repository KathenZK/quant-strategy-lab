from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-log-ratio-mean-reversion/scripts/search_binance_1d_be_lrmr_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_lrmr_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_has_15288_unique_configs() -> None:
    module = load_module()
    grid = module.configs()
    assert len(grid) == 15288
    assert len(set(grid)) == 15288


def test_pair_state_is_next_open_and_waits_full_cooldown() -> None:
    module = load_module()
    config = module.Config(20, 1.0, 0.25, 0.0, 0, 1)
    z = np.array([2.0, 0.0, 2.0, 2.0, 2.0])
    assert module.pair_states(z, config).tolist() == [0, -1, 0, 0, -1]


def test_pair_fills_charge_two_legs_and_are_direction_symmetric() -> None:
    module = load_module()
    cash_long, legs_long = module.open_pair(1.0, 1, 100.0, 50.0, 0.0)
    cash_short, legs_short = module.open_pair(1.0, -1, 100.0, 50.0, 0.0)
    assert np.isclose(cash_long, 1.0 - module.FEE)
    assert np.isclose(cash_short, 1.0 - module.FEE)
    assert legs_long["BTCUSDT"]["side"] == -legs_short["BTCUSDT"]["side"]
    assert legs_long["ETHUSDT"]["side"] == -legs_short["ETHUSDT"]["side"]


def test_equal_positive_funding_is_neutral_for_equal_notional_pair() -> None:
    module = load_module()
    cash, legs = module.open_pair(1.0, 1, 100.0, 50.0, 0.0)
    after = module.apply_funding(cash, legs, {"BTCUSDT": 0.01, "ETHUSDT": 0.005})
    assert np.isclose(after, cash)


def test_round_trip_flat_prices_loses_exact_fees_without_slippage() -> None:
    module = load_module()
    cash, legs = module.open_pair(1.0, 1, 100.0, 50.0, 0.0)
    closed, _ = module.close_pair(cash, legs, {"BTCUSDT": 100.0, "ETHUSDT": 50.0}, 0.0)
    assert np.isclose(closed, 1.0 - 2.0 * module.FEE)
