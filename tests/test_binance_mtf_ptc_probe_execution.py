from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


SCRIPT = Path("research/asset-portfolios/multi-timeframe-pullback-trend-campaign/scripts/search_probe_entry_v0.py")


def load_module():
    spec = importlib.util.spec_from_file_location("test_bin_mtf_ptc_probe_execution", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fills():
    return SimpleNamespace(adverse_fill=lambda price, side: price * (1.0 + side * 0.0004))


def entry_frame(ts: pd.Timestamp, stop: float) -> pd.DataFrame:
    return pd.DataFrame(
        [{"candidate_ts": ts - pd.Timedelta(hours=1), "entry_ts": ts, "side": 1, "fill": 100.04, "stop": stop, "probability": 0.8, "reason": "entered"}]
    )


def flat_bars(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0}, index=index)


def test_gap_stop_has_priority_over_24h_validation_exit() -> None:
    module = load_module()
    start = pd.Timestamp("2026-01-01", tz="UTC")
    index = pd.date_range(start, start + pd.Timedelta(hours=24), freq="15min")
    bars = flat_bars(index)
    bars.loc[index[-1], ["open", "high", "low", "close"]] = [89.0, 90.0, 88.0, 89.5]
    funding = pd.Series(0.0, index=index)
    _, ledger = module.run_probe(fills(), entry_frame(start, 90.0), bars, funding, start, index[-1] + pd.Timedelta(minutes=15))
    assert ledger.iloc[0]["reason"] == "stop_gap"
    assert ledger.iloc[0]["exit"] < 89.0


def test_probe_reports_mark_to_market_drawdown_and_risk_invariants() -> None:
    module = load_module()
    start = pd.Timestamp("2026-01-01", tz="UTC")
    index = pd.date_range(start, start + pd.Timedelta(hours=24), freq="15min")
    bars = flat_bars(index)
    shock = start + pd.Timedelta(hours=12)
    bars.loc[shock, ["open", "high", "low", "close"]] = [100.0, 100.5, 85.0, 86.0]
    funding = pd.Series(0.0, index=index)
    metrics, ledger = module.run_probe(fills(), entry_frame(start, 80.0), bars, funding, start, index[-1] + pd.Timedelta(minutes=15))
    assert metrics["max_drawdown_pct"] < 0.0
    assert metrics["intrabar_max_drawdown_pct"] <= metrics["max_drawdown_pct"]
    assert metrics["max_effective_leverage"] <= 3.0
    assert metrics["max_stop_risk_pct"] <= 0.25 + 1e-12
    assert ledger.iloc[0]["stop_risk_pct"] <= 0.25 + 1e-12
