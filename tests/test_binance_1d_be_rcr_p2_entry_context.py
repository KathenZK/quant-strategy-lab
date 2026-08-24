from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p2_entry_context.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p2", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_rank_auc_is_one_for_perfect_order_and_half_for_ties() -> None:
    module = load_module()
    labels = pd.Series([0, 0, 1, 1])
    assert module.auc(labels, pd.Series([0.0, 1.0, 2.0, 3.0])) == 1.0
    assert module.auc(labels, pd.Series([1.0, 1.0, 1.0, 1.0])) == 0.5


def test_six_features_are_frozen() -> None:
    module = load_module()
    assert len(module.FEATURES) == 6
