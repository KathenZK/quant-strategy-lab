from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/audit_binance_1d_be_rcr_p6_funding_crowding.py"


def test_funding_contract_has_six_features_and_valid_auc() -> None:
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p6", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert len(module.FEATURES) == 6
    assert module.auc(pd.Series([0, 0, 1, 1]), pd.Series([0, 1, 2, 3])) == 1.0
