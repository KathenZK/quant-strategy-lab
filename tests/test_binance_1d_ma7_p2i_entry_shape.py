from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2i_entry_shape.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2i_entry_shape_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def daily_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=10, tz="UTC"),
            "open": np.arange(10.0, 20.0),
            "high": np.arange(12.0, 22.0),
            "low": np.arange(9.0, 19.0),
            "close": np.arange(11.0, 21.0),
        }
    )


def test_shape_features_are_directional() -> None:
    module = load_script()
    context = module.daily_context(daily_fixture())
    entry_ts = pd.Timestamp("2026-01-11T00:00:00Z")
    long = module.shape_features(entry_ts, side=1, context=context)
    short = module.shape_features(entry_ts, side=-1, context=context)
    for feature in ("BODY_ATR", "BODY_SHARE", "CLV", "ER7"):
        assert long[feature] == -short[feature]
    assert long["RANGE_ATR"] == short["RANGE_ATR"]


def test_source_keeps_exposed_windows_sealed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source
    assert "PROSPECTIVE" not in source
