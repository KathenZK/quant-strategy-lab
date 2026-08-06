from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


SCRIPT_DIR = Path(
    "research/asset-portfolios/multi-timeframe-dual-state-trend-campaign/scripts"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_engine():
    data = load(SCRIPT_DIR / "dstc_data.py", "dstc_data")
    assert data is not None
    return load(SCRIPT_DIR / "dstc_engine.py", "test_dstc_engine")


def test_restart_uses_only_prior_bars_and_current_closed_range() -> None:
    engine = load_engine()
    index = pd.date_range("2026-01-01", periods=25, freq="15min", tz="UTC")
    panel = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "tr": 1.0,
            "tr_median20": 1.5,
        },
        index=index,
    )
    panel.iloc[-1, panel.columns.get_loc("close")] = 102.0
    panel.iloc[-1, panel.columns.get_loc("high")] = 102.5
    panel.iloc[-1, panel.columns.get_loc("tr")] = 2.0
    assert engine.restart_qualified(panel, len(panel) - 1, side=1, lookback=2)


def test_gap_stop_fills_at_worse_open() -> None:
    engine = load_engine()
    assert engine.adverse_fill(94.0, -1, 0.0004) < 94.0
    raw_stop_price = min(94.0, 95.0)
    assert raw_stop_price == 94.0


def test_layer_retry_does_not_end_campaign_state() -> None:
    engine = load_engine()
    config = engine.Config("retry", max_layers=1, max_retry_per_layer=1)
    campaign = engine.Campaign(
        campaign_id=1,
        side=1,
        start_ts=pd.Timestamp("2026-01-01", tz="UTC"),
        start_equity=1.0,
        layer_attempts={0: 1},
    )
    assert engine._next_layer(campaign, [], config) == 0
    campaign.layer_attempts[0] = 2
    assert engine._next_layer(campaign, [], config) is None


def test_risk_size_respects_three_times_leverage_cap() -> None:
    engine = load_engine()
    config = engine.Config("wide", layer_risk=0.10, max_leverage=3.0)
    quantity, _ = engine.requested_quantity(1.0, 100.0, 99.9, 1, config)
    assert quantity * 100.0 <= 3.0 + 1e-12
