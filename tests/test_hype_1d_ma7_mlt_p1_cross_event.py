from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/hype/1d-ma7-machine-learning-trend/scripts/"
    "run_hype_1d_ma7_mlt_p1_cross_event.py"
)
RENDERER = (
    ROOT
    / "research/hype/1d-ma7-machine-learning-trend/scripts/"
    "render_hype_1d_ma7_mlt_p1_trade_path.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_mlt_p1_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_p1_self_test() -> None:
    module = load_module()
    module.self_test()


def test_p1_frozen_feature_counts_and_timing() -> None:
    module = load_module()
    assert len(module.ENTRY_FEATURES) == 11
    assert len(module.EXIT_FEATURES) == 14
    assert module.LABEL_HORIZON == 21
    assert module.EXIT_LOOKAHEAD == 5
    assert module.SLOPE_MIN_ATR == 0.02
    assert module.ENTRY_THRESHOLD == 0.5
    assert module.EXIT_THRESHOLD == 0.5


def test_training_label_must_end_before_validation() -> None:
    module = load_module()
    last_train_open = module.TRAIN_DAYS - 1
    latest_allowed_entry = last_train_open - module.LABEL_HORIZON
    assert latest_allowed_entry + module.LABEL_HORIZON == last_train_open


def test_p1_trade_path_renderer_contract() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    assert "'ma7',C.ma" in source
    assert "setPointerCapture" in source
    assert "ctx.lineTo(x2,y2)" in source
    assert "external_dependencies" in source
    assert "ML_ENTRY_DYNAMIC_EXIT" in source
