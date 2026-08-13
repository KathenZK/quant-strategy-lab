from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/search_binance_1d_be_rcr_p3_relative_extreme_gate.py"


def test_gate_only_blocks_state_changes_and_rechecks_daily() -> None:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p3", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    base = np.array([0, 1, 1, 2, 2], dtype=np.int8)
    risk = np.array([0.0, 0.0, 2.0, 0.5, 0.0])
    assert module.gated_states(base, risk, 1.0).tolist() == [0, 1, 1, 0, 2]
