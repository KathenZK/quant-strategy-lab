from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1h-btceth-cross-impulse-lead-lag/scripts/search_binance_1h_be_cill_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1h_be_cill_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_has_2160_unique_configs() -> None:
    module = load_module()
    grid = module.configs()
    assert len(grid) == 2160
    assert len(set(grid)) == 2160


def test_signal_trades_other_asset_in_leader_direction() -> None:
    module = load_module()
    ts = pd.date_range("2025-01-01", periods=30, freq="1h", tz="UTC")
    btc_returns = np.resize(np.array([0.001, -0.0015, 0.0007]), 30)
    eth_returns = np.resize(np.array([0.0008, -0.0006, 0.0003]), 30)
    btc = 100.0 * np.exp(np.cumsum(btc_returns))
    eth = 50.0 * np.exp(np.cumsum(eth_returns))
    btc[-1] = btc[-2] * 1.10
    eth[-1] = eth[-2]
    full = pd.DataFrame({"ts": ts, "BTCUSDT": btc, "ETHUSDT": eth})
    market = module.Market(ts, {"BTCUSDT": btc, "ETHUSDT": eth}, {}, {}, {}, {})
    config = module.Config(24, 2.0, 0.5, 1.0, 0.0, 3, 0.0, 0)
    signals = module.build_signal_book(full, market, config)
    assert signals.leader[-1] == 1
    assert signals.follower[-1] == 2
    assert signals.side[-1] == 1


def test_round_trip_flat_price_loses_two_fees() -> None:
    module = load_module()
    cash, quantity, entry = module.open_position(1.0, 1, 100.0, 0.0)
    closed, _ = module.close_position(cash, quantity, 1, entry, 100.0, 0.0)
    assert np.isclose(closed, (1.0 - module.FEE) / (1.0 + module.FEE))


def test_event_engine_uses_next_open_and_ignores_signals_while_held() -> None:
    module = load_module()
    ts = pd.date_range("2025-01-01", periods=12, freq="1h", tz="UTC")
    ones = np.full(12, 100.0)
    zeros = np.zeros(12)
    market = module.Market(ts, {s: ones.copy() for s in module.SYMBOLS}, {s: ones.copy() for s in module.SYMBOLS}, {s: ones.copy() for s in module.SYMBOLS}, {s: ones.copy() for s in module.SYMBOLS}, {s: zeros.copy() for s in module.SYMBOLS})
    follower = np.zeros(12, dtype=np.int8)
    follower[[0, 2, 4]] = 2
    side = np.zeros(12, dtype=np.int8)
    side[[0, 2, 4]] = 1
    leader = np.zeros(12, dtype=np.int8)
    leader[[0, 2, 4]] = 1
    values = np.full(12, np.nan)
    values[[0, 2, 4]] = 0.01
    signals = module.SignalBook(follower, side, leader, values, values)
    config = module.Config(24, 2.0, 0.5, 1.0, 0.0, 3, 0.0, 0)
    result = module.simulate(market, signals, config, slippage=0.0, retain=True)
    assert result.trades[0]["entry_ts"] == ts[1]
    assert result.trades[0]["exit_ts"] == ts[4]
    assert result.trades[1]["entry_ts"] == ts[5]
