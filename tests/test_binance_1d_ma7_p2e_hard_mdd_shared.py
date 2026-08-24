from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "search_binance_1d_ma7_p2e_hard_mdd_shared.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2e_search_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hard_target_requires_both_assets_and_both_gates() -> None:
    module = load_script()
    passing = {
        "BTCUSDT": {
            "equity_multiple": 20.0,
            "max_drawdown_pct": -20.0,
            "bankrupt_intraday": False,
        },
        "ETHUSDT": {
            "equity_multiple": 25.0,
            "max_drawdown_pct": -19.0,
            "bankrupt_intraday": False,
        },
    }
    assert module.hard_target(passing)
    passing["ETHUSDT"]["equity_multiple"] = 19.99
    assert not module.hard_target(passing)
    passing["ETHUSDT"]["equity_multiple"] = 25.0
    passing["BTCUSDT"]["max_drawdown_pct"] = -20.01
    assert not module.hard_target(passing)


def test_seed_and_search_size_are_frozen() -> None:
    module = load_script()
    assert module.SEED == 20260812
    assert module.DEFAULT_SAMPLES == 20_000
    assert module.DEFAULT_STAGE1_KEEP == 300
    assert module.DEFAULT_STABLE_KEEP == 60


def test_source_never_references_exposed_window() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source

