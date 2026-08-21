from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-tradfi-futures-tsmom/scripts"
    / "run_mop2012_exact_replication.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("mop2012_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOP = load_module()


def test_paper_sigma_matches_frozen_ewma_variance() -> None:
    returns = pd.Series(np.sin(np.arange(400) / 17) / 100)
    actual = MOP.paper_sigma(returns)
    mean = returns.ewm(com=60, adjust=False, min_periods=60).mean()
    second = returns.pow(2).ewm(com=60, adjust=False, min_periods=60).mean()
    expected = ((second - mean.pow(2)).clip(lower=0) * 261).pow(0.5)
    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_paper_sigma_has_no_future_leakage() -> None:
    base = pd.Series(np.linspace(-0.01, 0.01, 300))
    shocked = base.copy()
    shocked.iloc[-1] = 1.0
    left = MOP.paper_sigma(base)
    right = MOP.paper_sigma(shocked)
    np.testing.assert_allclose(left.iloc[:-1], right.iloc[:-1], equal_nan=True)
    assert left.iloc[-1] != right.iloc[-1]


def test_market_features_uses_month_end_twelve_month_sign() -> None:
    dates = pd.bdate_range("2018-01-01", periods=1000, tz="UTC")
    close = pd.Series(100 * np.exp(np.arange(len(dates)) * 0.0003))
    _, monthly = MOP.market_features(
        pd.DataFrame({"ts": dates, "close": close}), dates[-1]
    )
    expected = np.sign(monthly["close"].pct_change(12, fill_method=None))
    np.testing.assert_allclose(monthly["forecast_12m"], expected, equal_nan=True)


def test_positions_are_equal_weighted_and_start_next_session() -> None:
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2024-01-31", "2024-02-01", "2024-02-02"], utc=True)
    )
    monthly = {
        "A": pd.DataFrame(
            {
                "ts": [dates[0]],
                "forecast_12m": [1.0],
                "forecast_always_long": [1.0],
                "sigma_ann": [0.20],
            }
        ),
        "B": pd.DataFrame(
            {
                "ts": [dates[0]],
                "forecast_12m": [-1.0],
                "forecast_always_long": [1.0],
                "sigma_ann": [0.20],
            }
        ),
    }
    returns = pd.DataFrame({"A": [0.0, 0.01, 0.0], "B": [0.0, -0.01, 0.0]}, index=dates)
    universe = {
        "A": {"class": "x", "exchange": "test", "name": "A"},
        "B": {"class": "y", "exchange": "test", "name": "B"},
    }
    path, detail = MOP.build_local_path(
        dates,
        returns,
        monthly,
        universe,
        "mop_tsmom",
        dates[0],
        (0.0,),
    )
    assert path.loc[0, "gross_leverage"] == 0.0
    assert path.loc[1, "gross_leverage"] == 2.0
    assert path.loc[1, "gross_return"] == 0.02
    positions = detail.loc[detail["ts"].eq(dates[1])].set_index("symbol")["position"]
    assert positions["A"] == 1.0
    assert positions["B"] == -1.0


def test_paper_construction_has_no_gross_cap() -> None:
    dates = pd.DatetimeIndex(
        pd.to_datetime(["2024-01-31", "2024-02-01"], utc=True)
    )
    events = pd.DataFrame(
        {
            "ts": [dates[0]],
            "forecast_12m": [1.0],
            "forecast_always_long": [1.0],
            "sigma_ann": [0.01],
        }
    )
    monthly = {"A": events.copy(), "B": events.copy()}
    returns = pd.DataFrame({"A": [0.0, 0.0], "B": [0.0, 0.0]}, index=dates)
    universe = {
        "A": {"class": "x", "exchange": "test", "name": "A"},
        "B": {"class": "y", "exchange": "test", "name": "B"},
    }
    path, _ = MOP.build_local_path(
        dates,
        returns,
        monthly,
        universe,
        "mop_tsmom",
        dates[0],
        (0.0,),
    )
    assert path.loc[1, "gross_leverage"] == 40.0

