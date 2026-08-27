from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-regime-continuation/scripts"
    / "run_binance_1d_ma7_regime_p3_confirmatory.py"
)


def load_module():
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("binance_ma7_p3", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_leave_one_out_median_matches_brute_force() -> None:
    module = load_module()
    for size in range(2, 12):
        values = np.random.default_rng(size).normal(size=size)
        expected = np.asarray(
            [np.median(np.delete(values, position)) for position in range(size)]
        )
        actual = module._loo_median(pd.Series(values)).to_numpy()
        np.testing.assert_allclose(actual, expected)


def test_fixed_rule_directional_volatility_contract() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "direction": ["long", "short", "long", "short"],
            "ma_slope_aligned": [True, True, True, False],
            "breakout_range_ratio": [1.3, 1.4, 1.1, 1.5],
            "atr_path_percentile_60": [0.9, 0.1, 0.95, 0.05],
            "aligned_breadth_trend_balance_loo": [0.2, -0.1, 0.3, 0.4],
        }
    )
    masks = module.fixed_masks(frame)
    assert masks["P2_LOCAL_FIXED"].tolist() == [True, True, False, False]
    assert masks["P2_LOCAL_BREADTH_FIXED"].tolist() == [True, False, False, False]


def test_account_stops_at_zero_after_unbounded_short_loss() -> None:
    module = load_module()
    dates = pd.to_datetime(["2026-01-02", "2026-01-03"], utc=True)
    candidates = pd.DataFrame(
        {
            "event_id": ["event"],
            "symbol": ["TEST/USDT:USDT"],
            "direction": ["short"],
            "direction_sign": [-1.0],
            "event_date": [pd.Timestamp("2026-01-01", tz="UTC")],
            "entry_date_1": [dates[0]],
            "entry_open_1": [1.0],
            "exit_date_1": [dates[1]],
            "exit_open_1": [10.0],
            "rank_score": [1.0],
        }
    )
    panel = pd.DataFrame(
        {
            "symbol": ["TEST/USDT:USDT", "TEST/USDT:USDT"],
            "event_date": dates,
            "open": [1.0, 10.0],
            "close": [1.0, 10.0],
        }
    )
    _, _, metrics = module.run_account(
        candidates,
        panel,
        strategy="TEST",
        horizon=1,
        scope="ALL_OOS",
    )
    assert metrics["ruined"] is True
    assert metrics["total_return"] == -1.0
    assert metrics["maximum_drawdown"] == -1.0
