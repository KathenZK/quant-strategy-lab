from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-crisis-override-shadow-trend/scripts/research_binance_1d_be_cost_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_cost_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_has_12_unique_configs() -> None:
    module = load_module()
    assert len(module.configs()) == 12
    assert len(set(module.configs())) == 12


def test_binary_state_confirms_crisis_and_neutral() -> None:
    module = load_module()
    raw = np.array([1, 1, 0, 1, 0, 0], dtype=np.int8)
    assert module.confirmed_binary(raw, 2).tolist() == [0, 1, 1, 1, 1, 0]
