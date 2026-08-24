from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / (
    "research/asset-portfolios/1h-volatility-impulse-pullback-reclaim/"
    "scripts/research_binance_1h_vipr_p1.py"
)


def load_script() -> Any:
    name = "test_binance_1h_vipr_p1_script"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_cache(rows: int = 250) -> dict[str, np.ndarray]:
    timestamps = pd.date_range("2024-01-01", periods=rows, freq="1h", tz="UTC")
    close = np.full(rows, 100.0)
    return {
        "ts_ns": timestamps.view("int64"),
        "open": close.copy(),
        "high": close + 0.2,
        "low": close - 0.2,
        "close": close.copy(),
        "true_range": np.full(rows, 0.4),
        "atr_prior": np.ones(rows),
        "funding_ts_ns": np.array([], dtype="int64"),
        "funding_mark_rate_prefix": np.array([0.0]),
    }


def test_root_signal_boundaries_are_symmetric() -> None:
    script = load_script()
    cache = synthetic_cache(100)
    cache["close"][30] = 101.2
    cache["high"][30] = 101.3
    cache["low"][30] = 100.0
    cache["true_range"][30] = 1.3
    cache["close"][60] = 98.8
    cache["high"][60] = 100.0
    cache["low"][60] = 98.7
    cache["true_range"][60] = 1.3
    config = script.Config(24, 1.0, 0.5)
    sides, levels = script.root_signals(cache, config)
    assert sides[30] == 1
    assert levels[30] == 100.2
    assert sides[60] == -1
    assert levels[60] == 99.8


def test_bracket_uses_stop_first_when_both_touch() -> None:
    script = load_script()
    cache = synthetic_cache(200)
    cache["open"][10] = 100.0
    cache["high"][10] = 103.0
    cache["low"][10] = 98.0
    outcome = script.bracket_exit(
        cache,
        entry_index=10,
        side=1,
        root_atr=1.0,
        data_end_exclusive=pd.Timestamp("2024-01-08T00:00:00Z"),
    )
    assert outcome is not None
    assert outcome["exit_index"] == 10
    assert outcome["exit_reference"] == 99.0
    assert outcome["exit_reason"] == "STOP_BOTH"


def test_pullback_requires_prior_extreme_and_later_reclaim() -> None:
    script = load_script()
    cache = synthetic_cache(250)
    sides = np.zeros(250, dtype="int8")
    levels = np.full(250, np.nan)
    root = 30
    sides[root] = 1
    levels[root] = 100.0
    cache["high"][root] = 102.0
    cache["low"][root] = 100.5
    cache["close"][root] = 101.0
    cache["high"][root + 1] = 103.0
    cache["low"][root + 1] = 102.0
    cache["close"][root + 1] = 102.5
    cache["high"][root + 2] = 102.8
    cache["low"][root + 2] = 102.4
    cache["close"][root + 2] = 102.6
    cache["open"][root + 4 :] = 102.7
    cache["high"][root + 3 :] = 103.0
    cache["low"][root + 3 :] = 102.5
    cache["close"][root + 3 :] = 102.7
    config = script.Config(24, 1.0, 0.5)
    with patch.object(script, "root_signals", return_value=(sides, levels)):
        _, trades = script.simulate_config_asset(
            asset="BTC",
            cache=cache,
            config=config,
            root_start=None,
            root_end_exclusive=pd.Timestamp("2024-01-03T00:00:00Z"),
            data_end_exclusive=pd.Timestamp("2024-01-10T00:00:00Z"),
        )
    assert len(trades) == 1
    trade = trades.iloc[0]
    timestamps = cache["ts_ns"]
    assert trade["armed_bar_ts"] == pd.Timestamp(
        int(timestamps[root + 2]), tz="UTC"
    )
    assert trade["reclaim_bar_ts"] == pd.Timestamp(
        int(timestamps[root + 3]), tz="UTC"
    )
    assert trade["entry_ts"] == pd.Timestamp(
        int(timestamps[root + 4]), tz="UTC"
    )


def test_development_failure_selects_nothing_and_hype_is_locked() -> None:
    script = load_script()
    candidate = {
        "config": {
            "breakout_lookback": 24,
            "impulse_atr": 1.0,
            "pullback_atr": 0.5,
        },
        "gate_checks": {
            "trade_capacity": True,
            "main_economics": False,
            "positive_assets": False,
            "positive_blocks": False,
            "cluster_bootstrap": False,
        },
    }
    assert script.select_development([candidate]) is None
    assert "HYPE" not in script.ASSETS
    assert all("hype" not in slug.lower() for slug in script.ASSET_SLUGS.values())
