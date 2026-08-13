from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2f_frontier_tail_states.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2f_tail_states_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_percentile_rank_is_trailing_and_inclusive() -> None:
    module = load_script()
    values = np.arange(1.0, 41.0)
    assert module.percentile_rank(values, 39, 30) == 1.0
    assert module.percentile_rank(values[::-1], 39, 30) == 1.0 / 30.0


def test_source_keeps_exposed_windows_sealed() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source
    assert "PROSPECTIVE" not in source
