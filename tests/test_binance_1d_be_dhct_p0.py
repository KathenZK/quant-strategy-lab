from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-dual-horizon-campaign-trend/scripts/search_binance_1d_be_dhct_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_dhct_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_has_108_unique_configs() -> None:
    module = load_module()
    grid = module.configs()
    assert len(grid) == 108
    assert len(set(grid)) == 108


def test_campaign_confirms_long_neutral_and_short_transitions() -> None:
    module = load_module()
    raw = np.array([1, 1, 0, 1, 0, 0, -1, -1], dtype=np.int8)
    assert module.confirm_campaign(raw, 2).tolist() == [0, 1, 1, 1, 1, 0, 0, -1]
