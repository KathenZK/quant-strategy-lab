from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-dual-alpha-sleeve-ensemble/scripts/research_binance_1d_be_dase_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_dase_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2020-01-01", periods=len(values), freq="1h", tz="UTC"),
            "equity": values,
            "favorable_equity": np.asarray(values) * 1.01,
            "adverse_equity": np.asarray(values) * 0.99,
        }
    )


def test_controls_and_three_ensemble_weights_are_frozen() -> None:
    module = load_module()
    assert module.WEIGHTS == (0.0, 0.25, 0.50, 0.75, 1.0)


def test_identical_sleeves_remain_identical_after_combination() -> None:
    module = load_module()
    path = sample([1.0, 1.5, 2.0])
    combined = module.combine_paths(path, path, 0.25)
    assert np.allclose(combined["equity"], path["equity"])
    assert np.allclose(combined["favorable_equity"], path["favorable_equity"])
    assert np.allclose(combined["adverse_equity"], path["adverse_equity"])


def test_fixed_capital_terminal_is_exact_weighted_sum() -> None:
    module = load_module()
    left = sample([1.0, 3.0])
    right = sample([1.0, 1.0])
    combined = module.combine_paths(left, right, 0.25)
    assert combined["equity"].iloc[-1] == 1.5
