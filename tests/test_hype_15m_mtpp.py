from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(
    "research/hype/15m-multi-timeframe-probe-pyramiding/scripts/"
    "research_hype_15m_mtpp.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_hype_15m_mtpp_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_risk_budget_does_not_change_stop_location() -> None:
    module = load_module()
    signal = pd.Series({"swing_low_6_4h": 95.0, "swing_high_6_4h": 105.0})
    stop = module.initial_stop(signal, 100.0, 1)
    assert stop == 95.0 * (1.0 - module.STOP_BUFFER)
    quantities = [risk / (100.0 - stop) for risk in module.RISK_BUDGETS]
    assert stop < 100.0
    assert quantities[0] < quantities[1] < quantities[2]


def test_higher_timeframe_features_are_visible_only_after_close() -> None:
    module = load_module()
    index = pd.date_range("2026-01-01", periods=16, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.arange(16, dtype=float) + 100.0,
            "high": np.arange(16, dtype=float) + 101.0,
            "low": np.arange(16, dtype=float) + 99.0,
            "close": np.arange(16, dtype=float) + 100.5,
            "volume": 1.0,
        },
        index=index,
    )
    bars, quality = module.resample_complete(
        frame, "4h", 16, pd.Timedelta(hours=4)
    )
    assert quality["accepted"]
    assert list(bars.index) == [pd.Timestamp("2026-01-01 04:00:00+00:00")]
    assert bars.iloc[0]["close"] == frame.iloc[-1]["close"]


def test_trader_policy_never_adds_before_profit_threshold() -> None:
    module = load_module()
    campaign = module.Campaign(
        side=1,
        entry_ts=pd.Timestamp("2026-01-01", tz="UTC"),
        entry_equity=1.0,
        entry_price=100.0,
        initial_stop=95.0,
        stop=95.0,
        r_price=5.0,
        planned_full_qty=0.2,
        quantity=0.05,
        layer=0,
    )
    signal = pd.Series({"long_trigger": True, "short_trigger": False})
    campaign.max_mfe_r = 0.49
    assert module._target_fraction("trader_full", campaign, signal, 20) == 0.25
    campaign.max_mfe_r = 0.50
    campaign.last_add_bar = 0
    assert module._target_fraction("trader_full", campaign, signal, 20) == 0.50


def test_stop_never_loosens_after_one_r() -> None:
    module = load_module()
    campaign = module.Campaign(
        side=1,
        entry_ts=pd.Timestamp("2026-01-01", tz="UTC"),
        entry_equity=1.0,
        entry_price=100.0,
        initial_stop=90.0,
        stop=92.0,
        r_price=10.0,
        planned_full_qty=0.1,
        quantity=0.025,
        layer=0,
        max_mfe_price=10.0,
        max_mfe_r=1.0,
    )
    signal = pd.Series({"swing_low_6_4h": 91.0, "swing_high_6_4h": 109.0})
    updated = module._updated_stop("trader_full", campaign, signal, 105.0)
    assert updated >= campaign.stop
    assert updated < 105.0
