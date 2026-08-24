from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.data.models import MarketType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/gold/1d-multi-speed-tsmom/scripts"
    / "research_gold_1d_multi_speed_tsmom.py"
)
RECENT_SCRIPT = SCRIPT.with_name("research_gold_1d_multi_speed_tsmom_recent.py")


def load_module():
    spec = importlib.util.spec_from_file_location("gold_tsmom", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_recent_module():
    spec = importlib.util.spec_from_file_location("gold_tsmom_recent", RECENT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def strategy_module():
    return load_module()


@pytest.fixture(scope="module")
def synthetic_data(strategy_module):
    dates = pd.bdate_range("2018-01-02", "2022-03-31", tz="UTC")
    index = np.arange(len(dates), dtype="float64")
    close = 100.0 * np.exp(0.00015 * index + 0.035 * np.sin(index / 27.0))
    raw = pd.DataFrame(
        {
            "ts": dates,
            "open": close * 0.999,
            "high": close * 1.004,
            "low": close * 0.996,
            "close": close,
        }
    )
    frame, month_end = strategy_module.build_features(raw)
    path, _ = strategy_module.expand_positions(frame, month_end)
    return frame, month_end, path


def test_futures_market_type_is_explicit():
    assert MarketType.FUTURES.value == "futures"


def test_month_end_forecasts_equal_return_sign(strategy_module, synthetic_data):
    _, month_end, _ = synthetic_data
    valid = month_end.loc[month_end["common_valid"]]
    assert not valid.empty
    for horizon in (1, 3, 12):
        expected = np.sign(valid[f"return_{horizon}m"].to_numpy())
        np.testing.assert_array_equal(valid[f"forecast_{horizon}m"], expected)
    expected_composite = valid[
        ["forecast_1m", "forecast_3m", "forecast_12m"]
    ].mean(axis=1)
    np.testing.assert_allclose(valid["forecast_composite"], expected_composite)
    assert set(valid["forecast_composite"].unique()).issubset(
        {-1.0, -1.0 / 3.0, 1.0 / 3.0, 1.0}
    )


def test_volatility_is_lagged_one_session(strategy_module, synthetic_data):
    frame, _, _ = synthetic_data
    expected = (
        frame["daily_return"]
        .shift(1)
        .pow(2)
        .ewm(
            com=strategy_module.VOL_COM,
            adjust=False,
            min_periods=strategy_module.VOL_MIN_PERIODS,
        )
        .mean()
        .mul(strategy_module.ANNUALIZER)
        .pow(0.5)
    )
    pd.testing.assert_series_equal(frame["sigma_ann"], expected, check_names=False)


def test_month_end_target_only_applies_next_session(synthetic_data):
    frame, month_end, path = synthetic_data
    event = month_end.loc[month_end["common_valid"]].iloc[3]
    event_ts = pd.Timestamp(event["ts"])
    next_ts = frame.loc[frame["ts"].gt(event_ts), "ts"].iloc[0]
    strategy = "composite_1_3_12m"
    next_position = path.loc[path["ts"].eq(next_ts), f"position_{strategy}"].iloc[0]
    assert next_position == pytest.approx(event[f"target_{strategy}"])

    prior_event = month_end.loc[
        month_end["common_valid"] & month_end["ts"].lt(event_ts)
    ].iloc[-1]
    same_day_position = path.loc[
        path["ts"].eq(event_ts), f"position_{strategy}"
    ].iloc[0]
    assert same_day_position == pytest.approx(prior_event[f"target_{strategy}"])


def test_cost_identity_and_common_sample(strategy_module, synthetic_data):
    _, _, path = synthetic_data
    starts = []
    for strategy in strategy_module.STRATEGIES:
        gross = path[f"gross_return_{strategy}"]
        turnover = path[f"turnover_{strategy}"]
        net = path[f"net_return_{strategy}_2bps"]
        np.testing.assert_allclose(net, gross - turnover * 0.0002)
        starts.append(path.loc[path[f"position_{strategy}"].notna(), "ts"].iloc[0])
    assert len(set(starts)) == 1


def test_raw_unaccepted_requires_explicit_override(strategy_module, monkeypatch):
    class FakeRoot:
        def glob(self, _pattern):
            return [Path("gc_f.parquet")]

    monkeypatch.setattr(strategy_module, "RAW_ROOT", FakeRoot())
    raw = pd.DataFrame(
        {
            "ts": pd.to_datetime(["2021-11-30"], utc=True),
            "session_date": ["2021-11-30"],
            "open": [1780.0],
            "high": [1790.0],
            "low": [1770.0],
            "close": [1785.0],
            "volume": [1.0],
            "open_interest": [1.0],
            "exchange": ["comex"],
            "symbol": ["GC.F"],
            "market_type": ["futures"],
            "timeframe": ["1d"],
            "source": ["github_stooq_commodities_snapshot"],
            "source_dataset_id": ["pinned-test"],
            "roll_adjustment": ["unknown"],
            "quality_status": ["raw_unaccepted"],
        }
    )
    monkeypatch.setattr(strategy_module.pd, "read_parquet", lambda _path: raw)
    with pytest.raises(RuntimeError, match="raw_unaccepted"):
        strategy_module.load_raw(allow_untrusted=False)


def test_recent_extension_buyhold_uses_raw_close_and_one_entry_cost(
    synthetic_data, monkeypatch
):
    recent = load_recent_module()
    _, _, full_path = synthetic_data
    start = pd.Timestamp(full_path["ts"].iloc[10])
    monkeypatch.setattr(recent, "EVALUATION_START", start)
    path = recent.normalize_extension(full_path)
    expected_gross = path["close"].iloc[-1] / path["close"].iloc[0] - 1.0
    assert path["buyhold_equity_0bps"].iloc[-1] - 1.0 == pytest.approx(
        expected_gross
    )
    assert path["buyhold_net_return_2bps"].iloc[0] == pytest.approx(-0.0002)
    np.testing.assert_allclose(
        path["buyhold_net_return_2bps"].iloc[1:],
        path["buyhold_return"].iloc[1:],
    )


def test_recent_extension_starts_on_requested_session(synthetic_data, monkeypatch):
    recent = load_recent_module()
    _, _, full_path = synthetic_data
    requested = pd.Timestamp(full_path["ts"].iloc[25])
    monkeypatch.setattr(recent, "EVALUATION_START", requested)
    path = recent.normalize_extension(full_path)
    assert pd.Timestamp(path["ts"].iloc[0]) == requested
    assert path["ts"].is_monotonic_increasing
