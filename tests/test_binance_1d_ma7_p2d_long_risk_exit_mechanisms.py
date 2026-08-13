from __future__ import annotations

from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-asset-specific-search/scripts/"
    "audit_binance_1d_ma7_p2d_long_risk_exit_mechanisms.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "binance_ma7_p2d_mechanisms_tested", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_arms_change_only_preregistered_fields() -> None:
    module = load_script()
    baseline = module.load_module(
        module.BASELINE_PATH, "binance_ma7_p2d_test_baseline"
    )
    transfer = baseline.load_module(
        baseline.TRANSFER_PATH,
        baseline.TRANSFER_SHA256,
        "binance_ma7_p2d_test_transfer",
    )
    engine = transfer.load_engine()
    long_config, _ = baseline.v1_configs(engine)
    arms = module.frozen_arms(long_config)
    expected = {
        "P0_PULLBACK": {"entry_mode"},
        "H2_INITIAL_STOP": {"entry_mode", "hard_stop_atr"},
        "X0_STRUCTURE_EXIT": {
            "entry_mode",
            "exit_confirm_days",
            "exit_buffer_atr",
        },
        "H2_X0_COMBINED": {
            "entry_mode",
            "hard_stop_atr",
            "exit_confirm_days",
            "exit_buffer_atr",
        },
    }
    before = asdict(long_config)
    for arm_id, config in arms.items():
        after = asdict(config)
        changed = {key for key in before if before[key] != after[key]}
        assert changed == expected[arm_id]


def test_source_never_references_exposed_window() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "RESEARCHER_EXPOSED" not in source
    assert "researcher_exposed_audit" not in source

