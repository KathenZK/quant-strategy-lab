from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd


ENGINE_SCRIPT = Path("research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/research_campaign_engine_v0.py")
LIMIT_SCRIPT = Path("research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/search_limit_retest_v2.py")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_failed_probe_plan_stays_pending_until_resolution() -> None:
    engine = load(ENGINE_SCRIPT, "test_bin_mtf_ptc_campaign_pending")
    start = pd.Timestamp("2026-01-01", tz="UTC")
    end = start + pd.Timedelta(hours=30)
    bar_index = pd.date_range(start, end, freq="15min")
    bars = pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=bar_index)
    funding = pd.Series(0.0, index=bar_index)
    candidate_index = pd.DatetimeIndex([start, start + pd.Timedelta(hours=4)])
    scores = pd.DataFrame({"probability": [0.8, 0.8], "direction": [1, 1], "strong": [True, True]}, index=candidate_index)
    attempts = pd.DataFrame(
        {
            "candidate_ts": candidate_index,
            "side": [1, 1],
            "probability": [0.8, 0.8],
            "entry_ts": [pd.NaT, pd.NaT],
            "resolved_ts": [start + pd.Timedelta(hours=24), start + pd.Timedelta(hours=28)],
            "raw_entry": [float("nan"), float("nan")],
            "stop": [90.0, 90.0],
            "status": ["no_restart", "no_restart"],
        }
    )
    result = engine.run_engine("BTC", bars, funding, scores, attempts, 0.5, start, end, engine.Config("pending_test", allow_adds=False, max_layers=0))
    assert int(result.actions["action"].eq("probe_plan").sum()) == 1
    assert int(result.actions["action"].eq("probe_plan_expired").sum()) == 1
    assert result.metrics["campaigns"] == 0


def test_limit_retest_uses_limit_and_marks_intrabar_fill() -> None:
    limit = load(LIMIT_SCRIPT, "test_bin_mtf_ptc_limit_transform")
    restart_ts = pd.Timestamp("2026-01-01", tz="UTC")
    entry_ts = restart_ts + pd.Timedelta(minutes=15)
    bars = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 101.0, 101.0, 101.0, 101.0],
            "low": [99.0, 97.0, 99.0, 99.0, 99.0],
            "close": [100.0, 98.0, 100.0, 100.0, 100.0],
        },
        index=pd.date_range(restart_ts, periods=5, freq="15min"),
    )
    attempts = pd.DataFrame(
        [{"candidate_ts": restart_ts - pd.Timedelta(hours=2), "side": 1, "probability": 0.8, "entry_ts": entry_ts, "resolved_ts": entry_ts, "raw_entry": 100.0, "stop": 90.0, "status": "entered"}]
    )
    transformed = limit.transform_attempts(attempts, bars, "limit25_1h")
    assert transformed.iloc[0]["entry_ts"] == entry_ts
    assert transformed.iloc[0]["raw_entry"] == 97.5
    assert bool(transformed.iloc[0]["fill_intrabar"])
    assert transformed.iloc[0]["entry_style"] == "limit"


def test_requested_risk_scales_but_keeps_same_stop_contract() -> None:
    engine = load(ENGINE_SCRIPT, "test_bin_mtf_ptc_campaign_scaling")
    one = engine.requested_quantity(1.0, 100.0, 95.0, 1, engine.Config("one", layer_risk=0.0025))
    two = engine.requested_quantity(1.0, 100.0, 95.0, 1, engine.Config("two", layer_risk=0.0050))
    assert abs(two / one - 2.0) < 1e-12
