from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts/hype_1d_ma7_opportunity_aware_profit_protection_engine.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("test_hype_oapp_engine", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_counts_and_boundaries() -> None:
    engine = load_engine()
    assert len(engine.trail_specs()) == 912
    assert len(engine.rsi_specs()) == 45
    assert len(engine.stage_a_configs()) == 957
    assert engine.TrailExit("atr", 0.75, 0.15, 4).enabled
    assert engine.TrailExit("fraction", 6.0, 0.10, 3).enabled
    assert engine.ShortRSIExit(50.0, 5).enabled
    with pytest.raises(ValueError):
        engine.TrailExit("atr", 0.6, 0.15, 1)
    with pytest.raises(ValueError):
        engine.ShortRSIExit(55.0, 1)


def test_stage_a_contains_only_permitted_single_modules() -> None:
    engine = load_engine()
    families = []
    for row in engine.stage_a_configs():
        assert not row.entry.enabled
        assert not row.short_exit.enabled
        assert len(row.enabled_modules()) == 1
        families.append(row.enabled_modules()[0])
    assert families.count("long_exit") == 912
    assert families.count("short_rsi") == 45


def test_stage_c_is_exact_two_module_product() -> None:
    engine = load_engine()
    combos = engine.build_combo_configs(engine.trail_specs()[:8], engine.rsi_specs()[:8])
    assert len(combos) == 64
    assert len({engine.config_sha256(row) for row in combos}) == 64
    assert all(row.enabled_modules() == ["long_exit", "short_rsi"] for row in combos)


def test_expanded_adjacent_neighbors_stay_inside_frozen_grid() -> None:
    engine = load_engine()
    config = engine.WTLConfig(
        "C",
        long_exit=engine.TrailExit("atr", 2.5, 0.35, 3),
        short_rsi=engine.ShortRSIExit(25.0, 3),
    )
    neighbors = engine.adjacent_neighbors(config)
    assert neighbors
    assert any(row.long_exit.activation_atr == 2.0 for row in neighbors)
    assert any(row.long_exit.activation_atr == 3.0 for row in neighbors)
    assert any(row.short_rsi.threshold == 20.0 for row in neighbors)
    assert any(row.short_rsi.days == 4 for row in neighbors)

