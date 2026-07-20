from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = (
    ROOT
    / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
)
SPEC = importlib.util.spec_from_file_location("multi_horizon_ema_forecast_v1", ENGINE_PATH)
assert SPEC is not None and SPEC.loader is not None
ENGINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENGINE
SPEC.loader.exec_module(ENGINE)

DAILY_SCRIPT_PATH = (
    ROOT
    / "research/hype/1d-multi-horizon-ema-forecast/scripts"
    / "research_hype_1d_multi_horizon_ema_forecast.py"
)
DAILY_SPEC = importlib.util.spec_from_file_location(
    "hype_1d_multi_horizon_ema_forecast",
    DAILY_SCRIPT_PATH,
)
assert DAILY_SPEC is not None and DAILY_SPEC.loader is not None
DAILY = importlib.util.module_from_spec(DAILY_SPEC)
sys.modules[DAILY_SPEC.name] = DAILY
DAILY_SPEC.loader.exec_module(DAILY)


def test_ema_matches_explicit_pandas_contract() -> None:
    values = pd.Series(np.linspace(10.0, 20.0, 30))
    expected = values.ewm(span=8, adjust=False, min_periods=8).mean()
    pd.testing.assert_series_equal(ENGINE.ema(values, 8), expected)


def test_forecast_is_bounded_weighted_and_causal() -> None:
    rows = 1800
    ts = pd.date_range("2025-01-01", periods=rows, freq="15min", tz="UTC")
    close = pd.Series(100.0 * np.exp(np.linspace(0.0, 0.8, rows) + 0.01 * np.sin(np.arange(rows) / 9.0)))
    market = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
        }
    )
    base = ENGINE.build_forecasts(market, ENGINE.ForecastConfig())
    changed = market.copy()
    changed.loc[rows - 1, "close"] *= 1.5
    perturbed = ENGINE.build_forecasts(changed, ENGINE.ForecastConfig())

    component_columns = [
        "forecast_8_32",
        "forecast_16_64",
        "forecast_32_128",
        "forecast_64_256",
    ]
    valid = base[component_columns].notna().all(axis=1)
    expected = base.loc[valid, component_columns].mul([0.2, 0.3, 0.3, 0.2], axis=1).sum(axis=1)
    pd.testing.assert_series_equal(base.loc[valid, "forecast"], expected, check_names=False)
    assert float(base.loc[valid, component_columns + ["forecast"]].abs().max().max()) <= 1.0
    pd.testing.assert_series_equal(
        base.loc[: rows - 2, "forecast"],
        perturbed.loc[: rows - 2, "forecast"],
    )


def test_position_buffer_requires_minimum_change() -> None:
    desired = pd.Series([0.0, 0.05, 0.11, 0.15, -0.02, -0.20])
    actual = ENGINE.apply_position_buffer(desired, buffer=0.1, max_abs_position=1.0)
    assert actual.tolist() == pytest.approx([0.0, 0.0, 0.11, 0.11, -0.02, -0.20])


def test_backtest_uses_prior_close_target_and_turnover_cost() -> None:
    market = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=4, freq="1h", tz="UTC"),
            "open": [100.0, 100.0, 110.0, 110.0],
        }
    )
    desired_close = pd.Series([1.0, 1.0, 0.0, 0.0])
    funding = pd.DataFrame(
        {
            "ts": pd.Series([], dtype="datetime64[ns, UTC]"),
            "funding_rate": pd.Series([], dtype="float64"),
        }
    )
    config = ENGINE.ForecastConfig()
    result = ENGINE.backtest_target(
        market,
        funding,
        desired_close,
        name="fixture",
        timeframe="1h",
        buffer=0.0,
        config=config,
        start_index=1,
    )

    assert result.path["position"].tolist() == pytest.approx([1.0, 1.0, 0.0])
    assert result.path["turnover"].tolist() == pytest.approx([1.0, 0.0, 1.0])
    expected = (1.0 - 0.0014) * 1.1
    expected *= 1.0 - 0.0014
    assert float(result.path["equity_net"].iloc[-1]) == pytest.approx(expected)


def test_positive_funding_is_paid_by_long_position() -> None:
    market = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=3, freq="1h", tz="UTC"),
            "open": [100.0, 100.0, 100.0],
        }
    )
    desired_close = pd.Series([1.0, 1.0, 1.0])
    funding = pd.DataFrame(
        {
            "ts": [pd.Timestamp("2025-01-01 02:00:00", tz="UTC")],
            "funding_rate": [0.001],
        }
    )
    result = ENGINE.backtest_target(
        market,
        funding,
        desired_close,
        name="funding_fixture",
        timeframe="1h",
        buffer=0.0,
        config=ENGINE.ForecastConfig(fee_per_turnover=0.0, slippage_per_turnover=0.0),
        start_index=1,
    )
    assert float(result.path["equity_net"].iloc[-1]) == pytest.approx(0.999)
    assert float(result.path["funding_amount"].sum()) == pytest.approx(0.001)


def test_daily_aggregation_keeps_only_complete_utc_days() -> None:
    complete_ts = pd.date_range("2025-01-01", periods=72, freq="1h", tz="UTC")
    partial_ts = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-12-31 23:00:00", tz="UTC"),
            pd.Timestamp("2025-01-04 00:00:00", tz="UTC"),
        ]
    )
    ts = partial_ts[:1].append(complete_ts).append(partial_ts[1:])
    price = pd.Series(np.linspace(100.0, 110.0, len(ts)))
    hourly = pd.DataFrame(
        {
            "ts": ts,
            "open": price,
            "high": price + 1.0,
            "low": price - 1.0,
            "close": price + 0.2,
            "volume": 1.0,
            "quote_volume": 100.0,
            "trade_count": 10,
            "is_closed": True,
        }
    )
    daily, quality = DAILY.aggregate_complete_daily(hourly)
    assert daily["ts"].tolist() == [
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2025-01-02", tz="UTC"),
        pd.Timestamp("2025-01-03", tz="UTC"),
    ]
    assert quality["dropped_incomplete_daily_bins"] == 2
    assert quality["blocker_count"] == 0


def test_classic_daily_ewmac_is_bounded_and_causal() -> None:
    rows = 400
    ts = pd.date_range("2025-01-01", periods=rows, freq="1D", tz="UTC")
    close = pd.Series(
        100.0
        * np.exp(
            np.linspace(0.0, 1.0, rows)
            + 0.025 * np.sin(np.arange(rows) / 7.0)
        )
    )
    daily = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
        }
    )
    base = DAILY.build_classic_ewmac_forecasts(daily, ENGINE)
    changed = daily.copy()
    changed.loc[rows - 1, "close"] *= 1.5
    perturbed = DAILY.build_classic_ewmac_forecasts(changed, ENGINE)
    component_columns = [
        "forecast_8_32",
        "forecast_16_64",
        "forecast_32_128",
        "forecast_64_256",
    ]
    valid = base[component_columns].notna().all(axis=1)
    assert int(np.flatnonzero(valid.to_numpy())[0]) == 255
    assert float(base.loc[valid, component_columns + ["forecast"]].abs().max().max()) <= 1.0
    pd.testing.assert_series_equal(
        base.loc[: rows - 2, "forecast"],
        perturbed.loc[: rows - 2, "forecast"],
    )
