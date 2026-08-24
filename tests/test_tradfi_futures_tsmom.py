from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = (
    ROOT / "research/asset-portfolios/1d-tradfi-futures-tsmom/scripts"
)


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_universe_has_four_classes_and_24_markets():
    fetch = load("tf_fetch_test", "fetch_tradfi_futures_yahoo.py")
    assert len(fetch.UNIVERSE) == 24
    counts = pd.Series([item["class"] for item in fetch.UNIVERSE.values()]).value_counts()
    assert set(counts.index) == {"equity_index", "bond", "fx", "commodity"}
    assert counts.min() >= 5
    assert "CL=F" not in fetch.UNIVERSE


def test_market_signal_and_volatility_are_lagged():
    model = load("tf_model_signal_test", "run_tradfi_futures_tsmom.py")
    dates = pd.bdate_range("2018-01-02", "2023-01-31", tz="UTC")
    x = np.arange(len(dates), dtype=float)
    close = 100 * np.exp(0.0002 * x + 0.03 * np.sin(x / 25))
    raw = pd.DataFrame({"ts": dates, "close": close})
    daily, monthly = model.market_features(raw, dates[-2])
    expected_sigma = (
        daily["return"]
        .shift(1)
        .pow(2)
        .ewm(com=60, adjust=False, min_periods=60)
        .mean()
        .mul(252)
        .pow(0.5)
    )
    pd.testing.assert_series_equal(daily["sigma_ann"], expected_sigma, check_names=False)
    for horizon in (1, 3, 12):
        expected = np.sign(monthly["close"].pct_change(horizon, fill_method=None))
        np.testing.assert_allclose(
            monthly[f"forecast_{horizon}m"], expected, equal_nan=True
        )


def test_portfolio_cost_identity_and_gross_cap():
    model = load("tf_model_portfolio_test", "run_tradfi_futures_tsmom.py")
    dates = pd.bdate_range("2019-01-02", "2023-06-30", tz="UTC")
    returns = pd.DataFrame(index=dates)
    monthly = {}
    for index, symbol in enumerate(model.UNIVERSE):
        x = np.arange(len(dates), dtype=float)
        close = 100 * np.exp(
            (0.00005 + index * 0.000002) * x
            + 0.025 * np.sin(x / (20 + index % 7) + index)
        )
        daily, events = model.market_features(
            pd.DataFrame({"ts": dates, "close": close}), dates[-2]
        )
        returns[symbol] = daily.set_index("ts")["return"].reindex(dates)
        monthly[symbol] = events
    path, _ = model.build_strategy_path(
        dates, returns, monthly, "composite"
    )
    assert not path.empty
    np.testing.assert_allclose(
        path["net_return_2bps"],
        path["gross_return"] - path["turnover"] * 0.0002,
    )
    assert path["gross_leverage"].max() <= model.GROSS_CAP + 1e-12
    assert pd.Timestamp(path["ts"].iloc[0]) >= model.EVALUATION_START


def test_month_end_announcement_is_not_held_same_day():
    model = load("tf_model_alignment_test", "run_tradfi_futures_tsmom.py")
    dates = pd.bdate_range("2020-01-02", "2023-03-31", tz="UTC")
    monthly = {}
    for symbol in model.UNIVERSE:
        x = np.arange(len(dates), dtype=float)
        close = 100 * np.exp(0.0003 * x + 0.02 * np.sin(x / 19))
        _, events = model.market_features(
            pd.DataFrame({"ts": dates, "close": close}), dates[-2]
        )
        monthly[symbol] = events
    positions = model.expand_unscaled_positions(dates, monthly, "tsmom_12m")
    symbol = next(iter(model.UNIVERSE))
    events = monthly[symbol].dropna(subset=["forecast_12m", "sigma_ann"])
    current = events.iloc[2]
    previous = events.loc[events["ts"].lt(current["ts"])].iloc[-1]
    class_count = sum(
        item["class"] == model.UNIVERSE[symbol]["class"]
        for item in model.UNIVERSE.values()
    )
    expected_previous = (
        previous["forecast_12m"]
        * model.TARGET_VOL
        / previous["sigma_ann"]
        * model.CLASS_WEIGHT
        / class_count
    )
    assert positions.loc[current["ts"], symbol] == expected_previous
    next_day = dates[dates.get_loc(current["ts"]) + 1]
    expected_current = (
        current["forecast_12m"]
        * model.TARGET_VOL
        / current["sigma_ann"]
        * model.CLASS_WEIGHT
        / class_count
    )
    assert positions.loc[next_day, symbol] == expected_current
