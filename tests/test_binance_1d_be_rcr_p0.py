from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/"
    "search_binance_1d_be_rcr_p0.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_grid_is_exactly_frozen_7560_configs() -> None:
    module = load_module()
    grid = module.configs()
    assert len(grid) == 7560
    assert len(set(grid)) == len(grid)


def test_raw_state_maps_bull_to_stronger_and_bear_to_weaker() -> None:
    module = load_module()
    market = np.array([1.0, 1.0, -1.0, -1.0, 0.0])
    relative = np.array([1.0, -1.0, 1.0, -1.0, 2.0])
    actual = module.raw_states(market, relative, deadzone=0.25, margin=0.25)
    assert actual.tolist() == [1, 2, -2, -1, 0]


def test_confirmation_retains_old_state_until_new_candidate_is_confirmed() -> None:
    module = load_module()
    raw = np.array([1, 1, 2, 2, 0, 0], dtype=np.int8)
    actual = module.confirmed_states(raw, confirm_days=2)
    assert actual.tolist() == [0, 1, 1, 2, 2, 0]


def test_execution_is_next_open_and_extra_delay_adds_one_day() -> None:
    module = load_module()
    decisions = np.array([0, 1, 1, -2], dtype=np.int8)
    assert module.execution_states(decisions).tolist() == [0, 0, 1, 1]
    assert module.execution_states(decisions, 1).tolist() == [0, 0, 0, 1]


def test_entry_sizing_keeps_notional_equal_to_post_fee_equity() -> None:
    module = load_module()
    cash, quantity, fill = module._open_position(1.0, 1, 100.0, 0.0)
    assert np.isclose(cash, quantity * fill)
    assert cash < 1.0


def test_fill_slippage_is_adverse_for_all_four_actions() -> None:
    module = load_module()
    assert module._fill_price(100.0, 1, 0.001, entry=True) == 100.1
    assert module._fill_price(100.0, 1, 0.001, entry=False) == 99.9
    assert module._fill_price(100.0, -1, 0.001, entry=True) == 99.9
    assert module._fill_price(100.0, -1, 0.001, entry=False) == 100.1
