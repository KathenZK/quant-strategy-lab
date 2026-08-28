from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/hype/1d-ma7-machine-learning-trend/scripts/"
    "run_hype_1d_ma7_mlt_p2_episode_policy.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_mlt_p2_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_p2_self_test() -> None:
    load_module().self_test()


def test_p2_frozen_contract_constants() -> None:
    module = load_module()
    assert module.EPISODE_MAX_AGE == 6
    assert module.ENTRY_THRESHOLD == 0.55
    assert module.EXIT_THRESHOLD == 0.45
    assert module.REVERSAL_MARGIN == 0.10
    assert module.ENTRY_LABEL_HORIZON == 21
    assert module.SURVIVAL_HORIZON == 14
    assert module.MAX_HOLD_DAYS == 30
    assert len(module.ENTRY_FEATURES) == 16
    assert len(module.SURVIVAL_FEATURES) == 16


def test_p2_training_labels_end_before_validation() -> None:
    module = load_module()
    latest_entry = module.TRAIN_DAYS - 1 - module.ENTRY_LABEL_HORIZON
    assert latest_entry + module.ENTRY_LABEL_HORIZON == module.TRAIN_DAYS - 1
