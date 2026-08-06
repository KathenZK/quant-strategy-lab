from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = Path(
    "research/asset-portfolios/1h-price-impulse-campaign/scripts/"
    "research_binance_1h_pic_v0.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_binance_1h_pic_v0_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_hourly() -> pd.DataFrame:
    index = pd.date_range("2025-01-01 01:00", periods=900, freq="1h", tz="UTC")
    returns = np.resize(np.array([0.001, -0.001]), len(index))
    close = 100.0 * np.exp(np.cumsum(returns))
    frame = pd.DataFrame(index=index)
    frame["close"] = close
    frame["open"] = frame["close"].shift(1).fillna(frame["close"])
    frame["high"] = frame[["open", "close"]].max(axis=1) * 1.0001
    frame["low"] = frame[["open", "close"]].min(axis=1) * 0.9999
    frame["funding_rate"] = 0.0
    return frame


def test_past_rms_is_frozen_before_the_four_hour_impulse() -> None:
    module = load_module()
    frame = synthetic_hourly()
    signal_ts = frame.index[frame.index.hour == module.IMPULSE_HOURS][-1]
    location = frame.index.get_loc(signal_ts)
    frame.iloc[location, frame.columns.get_loc("close")] *= 1.05
    featured = module.build_features(frame)
    expected = (
        np.log(frame["close"]).diff().iloc[: location - module.IMPULSE_HOURS + 1].tail(720)
    )
    expected_rms = float(np.sqrt(np.mean(np.square(expected))))
    assert featured.loc[signal_ts, "past_rms"] == pytest.approx(expected_rms)


def test_planned_quantity_includes_stop_fill_and_both_fees() -> None:
    module = load_module()
    equity = 1.0
    entry = 100.0
    stop = 95.0
    quantity, planned_loss = module.planned_quantity(
        equity,
        entry,
        stop,
        1,
        module.FEE_RATE,
        module.BASE_SLIPPAGE,
    )
    assert quantity > 0.0
    assert planned_loss == pytest.approx(module.RISK_BUDGET * equity)
    assert quantity * entry <= module.MAX_LEVERAGE * equity


def test_adverse_fill_moves_against_both_entry_and_exit() -> None:
    module = load_module()
    assert module.adverse_fill(100.0, 1, 0.001) == pytest.approx(100.1)
    assert module.adverse_fill(100.0, -1, 0.001) == pytest.approx(99.9)


def test_signal_requires_fixed_utc_clock_and_threshold() -> None:
    module = load_module()
    frame = synthetic_hourly()
    signal_ts = frame.index[frame.index.hour == module.IMPULSE_HOURS][-1]
    location = frame.index.get_loc(signal_ts)
    frame.iloc[location, frame.columns.get_loc("close")] *= 1.03
    featured = module.build_features(frame)
    assert bool(featured.loc[signal_ts, "signal"])
    assert not featured.loc[~featured.index.hour.isin([module.IMPULSE_HOURS]), "signal"].any()


def test_flat_path_exits_after_24h_validation_window() -> None:
    module = load_module()
    frame = synthetic_hourly()
    signal_ts = frame.index[frame.index.hour == module.IMPULSE_HOURS][-2]
    location = frame.index.get_loc(signal_ts)
    frame.iloc[location, frame.columns.get_loc("close")] *= 1.03
    frame.iloc[location + 1 :, frame.columns.get_loc("open")] = frame.iloc[location]["close"]
    frame.iloc[location + 1 :, frame.columns.get_loc("close")] = frame.iloc[location]["close"]
    frame.iloc[location + 1 :, frame.columns.get_loc("high")] = frame.iloc[location]["close"] * 1.0001
    frame.iloc[location + 1 :, frame.columns.get_loc("low")] = frame.iloc[location]["close"] * 0.9999
    result = module.run_backtest(frame, module.RunConfig())
    closed = result.campaigns.loc[result.campaigns["closed"]]
    assert not closed.empty
    campaign = closed.iloc[-1]
    assert campaign["exit_reason"] == "validation_failed_24h"
    assert campaign["hold_hours"] == module.VALIDATION_HOURS

