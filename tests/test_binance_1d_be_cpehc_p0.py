from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-crisis-profit-exit-handoff-continuity/scripts/research_binance_1d_be_cpehc_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_cpehc_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_handoff_grid_has_six_unique_configs() -> None:
    module = load_module()
    assert len(module.configs()) == 6
    assert len(set(module.configs())) == 6
