from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research/asset-portfolios/1d-btceth-cross-breadth-channel-trend/scripts/search_binance_1d_be_cbct_p0.py"


def load_module():
    spec = importlib.util.spec_from_file_location("binance_1d_be_cbct_p0", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_grid_has_2808_unique_configs() -> None:
    module = load_module()
    grid = module.configs()
    assert len(grid) == 2808
    assert len(set(grid)) == 2808
    assert all(config.exit_n < config.entry_n for config in grid)


def test_confirmation_requires_same_nonzero_code() -> None:
    module = load_module()
    raw = np.array([1, 1, 0, -2, -2, -2], dtype=np.int8)
    assert module.confirm_codes(raw, 2).tolist() == [0, 1, 0, 0, -2, -2]


def test_handoff_requires_consecutive_close_beyond_frozen_extreme() -> None:
    module = load_module()
    close = np.array([100.0, 111.0, 109.0, 112.0, 113.0, 114.0])
    assert module.find_handoff_signal(close, 1, 110.0, 1, 6, 5, 2) == 4
    assert module.find_handoff_signal(close, -1, 90.0, 1, 6, 5, 1) is None


def test_round_trip_flat_price_loses_two_fees() -> None:
    module = load_module()
    cash, quantity, entry = module.open_position(1.0, 1, 100.0, 0.0)
    closed, _ = module.close_position(cash, quantity, 1, entry, 100.0, 0.0)
    assert np.isclose(closed, (1.0 - module.FEE) / (1.0 + module.FEE))


def test_breakout_requires_peer_breadth_confirmation() -> None:
    module = load_module()
    ts = pd.date_range("2020-01-01", periods=21, freq="1D", tz="UTC")
    btc_close = np.r_[np.full(20, 100.0), 110.0]
    eth_close = np.r_[np.full(20, 100.0), 80.0]

    def make_frame(peer_last: float) -> pd.DataFrame:
        peer_close = eth_close.copy()
        peer_close[-1] = peer_last
        return pd.DataFrame(
            {
                "ts": ts,
                "BTCUSDT_open": btc_close,
                "BTCUSDT_high": np.r_[np.full(20, 100.0), 110.0],
                "BTCUSDT_low": np.r_[np.full(20, 99.0), 109.0],
                "BTCUSDT_close": btc_close,
                "ETHUSDT_open": peer_close,
                "ETHUSDT_high": np.r_[np.full(20, 120.0), 120.0],
                "ETHUSDT_low": np.r_[np.full(20, 90.0), 90.0],
                "ETHUSDT_close": peer_close,
            }
        )

    def make_daily(frame: pd.DataFrame):
        return module.DailyMarket(
            ts=ts,
            open={symbol: frame[f"{symbol}_open"].to_numpy(float) for symbol in module.SYMBOLS},
            high={symbol: frame[f"{symbol}_high"].to_numpy(float) for symbol in module.SYMBOLS},
            low={symbol: frame[f"{symbol}_low"].to_numpy(float) for symbol in module.SYMBOLS},
            close={symbol: frame[f"{symbol}_close"].to_numpy(float) for symbol in module.SYMBOLS},
            atr14={symbol: np.ones(len(ts)) for symbol in module.SYMBOLS},
        )

    blocked_frame = make_frame(80.0)
    blocked = module.build_entry_book(blocked_frame, make_daily(blocked_frame), 20, 20, 1)
    assert blocked.code[-1] == 0

    confirmed_frame = make_frame(110.0)
    confirmed = module.build_entry_book(confirmed_frame, make_daily(confirmed_frame), 20, 20, 1)
    assert confirmed.code[-1] == 1


def test_entry_day_has_no_active_stop_and_first_stop_acts_next_day() -> None:
    module = load_module()
    daily_ts = pd.date_range("2020-01-01", periods=4, freq="1D", tz="UTC")
    hourly_ts = pd.date_range("2020-01-01", periods=73, freq="1h", tz="UTC")
    daily_open = np.array([100.0, 105.0, 105.0, 100.0])
    daily_high = np.array([101.0, 110.0, 106.0, 101.0])
    daily_low = np.array([99.0, 50.0, 99.0, 99.0])
    daily_close = np.array([100.0, 105.0, 100.0, 100.0])
    daily = module.DailyMarket(
        ts=daily_ts,
        open={symbol: daily_open.copy() for symbol in module.SYMBOLS},
        high={symbol: daily_high.copy() for symbol in module.SYMBOLS},
        low={symbol: daily_low.copy() for symbol in module.SYMBOLS},
        close={symbol: daily_close.copy() for symbol in module.SYMBOLS},
        atr14={symbol: np.full(4, 5.0) for symbol in module.SYMBOLS},
    )
    hourly_open = np.full(73, 105.0)
    hourly_high = np.full(73, 106.0)
    hourly_low = np.full(73, 104.0)
    hourly_close = np.full(73, 105.0)
    hourly_low[24] = 50.0
    hourly_low[48] = 99.0
    hourly = module.HourlyMarket(
        ts=hourly_ts,
        open={symbol: hourly_open.copy() for symbol in module.SYMBOLS},
        high={symbol: hourly_high.copy() for symbol in module.SYMBOLS},
        low={symbol: hourly_low.copy() for symbol in module.SYMBOLS},
        close={symbol: hourly_close.copy() for symbol in module.SYMBOLS},
        unit_funding={symbol: np.zeros(73) for symbol in module.SYMBOLS},
    )
    book = module.EntryBook(code=np.array([1, 0, 0, 0], dtype=np.int8), score=np.ones(4))
    channels = (
        {symbol: np.zeros(4) for symbol in module.SYMBOLS},
        {symbol: np.full(4, np.inf) for symbol in module.SYMBOLS},
    )
    data = type(
        "FrozenWindow",
        (),
        {"COMMON_START": daily_ts[0], "DEVELOPMENT_END": daily_ts[-1]},
    )
    config = module.Config(20, 5, 20, 2.0, 1, 0, 0)

    result = module.simulate(data, daily, hourly, book, channels, config, slippage=0.0, retain=True)

    assert result.counts["stop_exit"] == 1
    assert result.trades[0]["exit_ts"] == daily_ts[2]
    assert result.trades[0]["exit_mark"] == 100.0


def test_profit_protection_uses_closed_day_and_exits_next_open() -> None:
    module = load_module()
    daily_ts = pd.date_range("2020-01-01", periods=4, freq="1D", tz="UTC")
    hourly_ts = pd.date_range("2020-01-01", periods=73, freq="1h", tz="UTC")
    daily = module.DailyMarket(
        ts=daily_ts,
        open={symbol: np.array([100.0, 100.0, 104.0, 104.0]) for symbol in module.SYMBOLS},
        high={symbol: np.array([101.0, 110.0, 105.0, 105.0]) for symbol in module.SYMBOLS},
        low={symbol: np.array([99.0, 99.0, 103.0, 103.0]) for symbol in module.SYMBOLS},
        close={symbol: np.array([100.0, 104.0, 104.0, 104.0]) for symbol in module.SYMBOLS},
        atr14={symbol: np.full(4, 5.0) for symbol in module.SYMBOLS},
    )
    hourly = module.HourlyMarket(
        ts=hourly_ts,
        open={symbol: np.full(73, 104.0) for symbol in module.SYMBOLS},
        high={symbol: np.full(73, 105.0) for symbol in module.SYMBOLS},
        low={symbol: np.full(73, 103.0) for symbol in module.SYMBOLS},
        close={symbol: np.full(73, 104.0) for symbol in module.SYMBOLS},
        unit_funding={symbol: np.zeros(73) for symbol in module.SYMBOLS},
    )
    book = module.EntryBook(code=np.array([1, 0, 0, 0], dtype=np.int8), score=np.ones(4))
    channels = (
        {symbol: np.zeros(4) for symbol in module.SYMBOLS},
        {symbol: np.full(4, np.inf) for symbol in module.SYMBOLS},
    )
    data = type("FrozenWindow", (), {"COMMON_START": daily_ts[0], "DEVELOPMENT_END": daily_ts[-1]})
    config = module.Config(20, 5, 20, 20.0, 1, 0, 0)
    protection = module.ProfitProtection(1.0, 0.50, 1)

    result = module.simulate(
        data,
        daily,
        hourly,
        book,
        channels,
        config,
        slippage=0.0,
        retain=True,
        profit_protection=protection,
    )

    assert result.counts["profit_protection_exit"] == 1
    assert result.trades[0]["exit_reason"] == "profit_protection"
    assert result.trades[0]["exit_ts"] == daily_ts[2]


def test_campaign_invalidation_exits_at_next_open() -> None:
    module = load_module()
    daily_ts = pd.date_range("2020-01-01", periods=5, freq="1D", tz="UTC")
    hourly_ts = pd.date_range("2020-01-01", periods=97, freq="1h", tz="UTC")
    daily = module.DailyMarket(
        ts=daily_ts,
        open={symbol: np.full(5, 100.0) for symbol in module.SYMBOLS},
        high={symbol: np.full(5, 101.0) for symbol in module.SYMBOLS},
        low={symbol: np.full(5, 99.0) for symbol in module.SYMBOLS},
        close={symbol: np.full(5, 100.0) for symbol in module.SYMBOLS},
        atr14={symbol: np.full(5, 5.0) for symbol in module.SYMBOLS},
    )
    hourly = module.HourlyMarket(
        ts=hourly_ts,
        open={symbol: np.full(97, 100.0) for symbol in module.SYMBOLS},
        high={symbol: np.full(97, 101.0) for symbol in module.SYMBOLS},
        low={symbol: np.full(97, 99.0) for symbol in module.SYMBOLS},
        close={symbol: np.full(97, 100.0) for symbol in module.SYMBOLS},
        unit_funding={symbol: np.zeros(97) for symbol in module.SYMBOLS},
    )
    book = module.EntryBook(code=np.array([1, 0, 0, 0, 0], dtype=np.int8), score=np.ones(5))
    channels = (
        {symbol: np.full(5, -np.inf) for symbol in module.SYMBOLS},
        {symbol: np.full(5, np.inf) for symbol in module.SYMBOLS},
    )
    data = type("FrozenWindow", (), {"COMMON_START": daily_ts[0], "DEVELOPMENT_END": daily_ts[-1]})
    config = module.Config(20, 5, 20, 20.0, 1, 0, 0)
    campaign_state = np.array([1, 0, 0, 0, 0], dtype=np.int8)

    result = module.simulate(
        data,
        daily,
        hourly,
        book,
        channels,
        config,
        slippage=0.0,
        retain=True,
        campaign_state=campaign_state,
    )

    assert result.counts["regime_exit"] == 1
    assert result.trades[0]["exit_reason"] == "regime"
    assert result.trades[0]["exit_ts"] == daily_ts[2]


def test_partial_profit_reduces_quantity_once_at_next_open() -> None:
    module = load_module()
    daily_ts = pd.date_range("2020-01-01", periods=4, freq="1D", tz="UTC")
    hourly_ts = pd.date_range("2020-01-01", periods=73, freq="1h", tz="UTC")
    daily = module.DailyMarket(
        ts=daily_ts,
        open={symbol: np.array([100.0, 100.0, 104.0, 104.0]) for symbol in module.SYMBOLS},
        high={symbol: np.array([101.0, 110.0, 105.0, 105.0]) for symbol in module.SYMBOLS},
        low={symbol: np.array([99.0, 99.0, 103.0, 103.0]) for symbol in module.SYMBOLS},
        close={symbol: np.array([100.0, 104.0, 104.0, 104.0]) for symbol in module.SYMBOLS},
        atr14={symbol: np.full(4, 5.0) for symbol in module.SYMBOLS},
    )
    hourly = module.HourlyMarket(
        ts=hourly_ts,
        open={symbol: np.full(73, 104.0) for symbol in module.SYMBOLS},
        high={symbol: np.full(73, 105.0) for symbol in module.SYMBOLS},
        low={symbol: np.full(73, 103.0) for symbol in module.SYMBOLS},
        close={symbol: np.full(73, 104.0) for symbol in module.SYMBOLS},
        unit_funding={symbol: np.zeros(73) for symbol in module.SYMBOLS},
    )
    book = module.EntryBook(code=np.array([1, 0, 0, 0], dtype=np.int8), score=np.ones(4))
    channels = (
        {symbol: np.zeros(4) for symbol in module.SYMBOLS},
        {symbol: np.full(4, np.inf) for symbol in module.SYMBOLS},
    )
    data = type("FrozenWindow", (), {"COMMON_START": daily_ts[0], "DEVELOPMENT_END": daily_ts[-1]})
    config = module.Config(20, 5, 20, 20.0, 1, 0, 0)

    result = module.simulate(
        data,
        daily,
        hourly,
        book,
        channels,
        config,
        slippage=0.0,
        retain=True,
        partial_protection=module.PartialProtection(1.0, 0.50, 1, 0.50),
    )

    event = result.trades[0]["partial_events"][0]
    assert result.counts["partial_profit_events"] == 1
    assert event["ts"] == daily_ts[2]
    assert np.isclose(event["quantity_remaining"], event["quantity_before"] * 0.5)
