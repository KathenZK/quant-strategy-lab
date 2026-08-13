from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-crisis-partial-profit-runner/scripts/research_binance_1d_be_cppr_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_cppr_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_control_and_three_partial_fractions_are_frozen() -> None:
    module = load_module()
    assert module.FRACTIONS == (0.0, 0.25, 0.50, 0.75)
