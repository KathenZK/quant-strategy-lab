from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    ROOT
    / "research/hype/1d-multi-horizon-ema-forecast/scripts"
    / "research_hype_1d_multi_horizon_ema_forecast.py"
)
SPEC = importlib.util.spec_from_file_location(
    "research_hype_1d_multi_horizon_ema_forecast",
    SCRIPT_PATH,
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
ENGINE = MODULE.load_engine()


def test_daily_aggregation_keeps_only_complete_utc_days() -> None:
    ts = pd.date_range("2025-01-01 03:00:00", periods=70, freq="1h", tz="UTC")
    close = pd.Series(np.linspace(100.0, 110.0, len(ts)))
    hourly = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
            "quote_volume": close,
            "trade_count": 1,
            "is_closed": True,
        }
    )
    daily, quality = MODULE.aggregate_complete_daily(hourly)
    assert daily["ts"].tolist() == [
        pd.Timestamp("2025-01-02", tz="UTC"),
        pd.Timestamp("2025-01-03", tz="UTC"),
    ]
    assert quality["rows"] == 2
    assert quality["dropped_incomplete_daily_bins"] == 2
    assert quality["blocker_count"] == 0


def test_daily_aggregation_does_not_need_a_future_bar() -> None:
    ts = pd.date_range("2025-01-01", periods=24, freq="1h", tz="UTC")
    close = pd.Series(np.linspace(100.0, 101.0, len(ts)))
    hourly = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1.0,
            "quote_volume": close,
            "trade_count": 1,
            "is_closed": True,
        }
    )

    daily, quality = MODULE.aggregate_complete_daily(hourly)

    assert daily["ts"].tolist() == [pd.Timestamp("2025-01-01", tz="UTC")]
    assert daily["is_closed"].tolist() == [True]
    assert quality["dropped_incomplete_daily_bins"] == 0


def test_classic_ewmac_forecast_is_bounded_and_causal() -> None:
    rows = 400
    ts = pd.date_range("2025-01-01", periods=rows, freq="1D", tz="UTC")
    close = pd.Series(
        100.0
        * np.exp(
            np.linspace(0.0, 0.8, rows)
            + 0.03 * np.sin(np.arange(rows) / 11.0)
        )
    )
    daily = pd.DataFrame(
        {
            "ts": ts,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "quote_volume": close,
            "trade_count": 1,
        }
    )
    base = MODULE.build_classic_ewmac_forecasts(daily, ENGINE)
    changed = daily.copy()
    changed.loc[rows - 1, "close"] *= 1.5
    perturbed = MODULE.build_classic_ewmac_forecasts(changed, ENGINE)
    columns = [
        "forecast_8_32",
        "forecast_16_64",
        "forecast_32_128",
        "forecast_64_256",
        "forecast",
    ]
    assert base[columns].abs().max().max() <= 1.0
    first_valid = int(np.flatnonzero(base["forecast"].notna().to_numpy())[0])
    assert first_valid == 255
    pd.testing.assert_series_equal(
        base.loc[: rows - 2, "forecast"],
        perturbed.loc[: rows - 2, "forecast"],
    )


def test_daily_forecast_uses_frozen_weights() -> None:
    rows = 400
    close = pd.Series(np.exp(np.linspace(4.0, 5.0, rows)))
    daily = pd.DataFrame(
        {
            "ts": pd.date_range("2025-01-01", periods=rows, freq="1D", tz="UTC"),
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "quote_volume": close,
            "trade_count": 1,
        }
    )
    frame = MODULE.build_classic_ewmac_forecasts(daily, ENGINE)
    components = frame[
        [
            "forecast_8_32",
            "forecast_16_64",
            "forecast_32_128",
            "forecast_64_256",
        ]
    ]
    expected = components.mul([0.2, 0.3, 0.3, 0.2], axis=1).sum(
        axis=1,
        min_count=4,
    )
    pd.testing.assert_series_equal(frame["forecast"], expected, check_names=False)
