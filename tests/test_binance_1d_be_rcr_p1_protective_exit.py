from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-btceth-relative-cycle-rotation/scripts/"
    "search_binance_1d_be_rcr_p1_protective_exit.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_rcr_p1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_overlay_grid_has_184_unique_configs() -> None:
    module = load_module()
    grid = module.overlay_configs()
    assert len(grid) == 184
    assert len(set(grid)) == 184
    assert all(config.stop_atr > 0 or config.fast_ema > 0 for config in grid)


def test_state_change_rearm_blocks_same_state_and_clears_on_change() -> None:
    module = load_module()
    day = pd.Timestamp("2025-01-10", tz="UTC")
    allowed, banned, _ = module.rearm_allows(1, 1, day, day, "state_change")
    assert not allowed and banned == 1
    allowed, banned, ban_day = module.rearm_allows(2, 1, day, day, "state_change")
    assert allowed and banned == 0 and ban_day is None


def test_cooldown_rearm_uses_full_utc_open_count() -> None:
    module = load_module()
    ban_day = pd.Timestamp("2025-01-10", tz="UTC")
    before = pd.Timestamp("2025-01-12", tz="UTC")
    ready = pd.Timestamp("2025-01-13", tz="UTC")
    assert not module.rearm_allows(1, 1, ban_day, before, "cooldown_3")[0]
    assert module.rearm_allows(1, 1, ban_day, ready, "cooldown_3")[0]
