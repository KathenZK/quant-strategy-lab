from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / (
    "research/hype/1d-ma7-asymmetric-body-trend/scripts/"
    "hype_1d_ma7_continuous_trend_lifecycle_harness.py"
)


def load_harness():
    name = "ctls_harness_tested"
    spec = importlib.util.spec_from_file_location(name, HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def detection(harness, **updates):
    values = {
        "distance_min": 0.0,
        "slow_slope_min": 0.0,
        "drift_min": 0.0,
        "er_min": 0.1,
        "direction_score_min": 2,
        "enter_confirm_days": 1,
        "exit_confirm_days": 2,
        "reverse_confirm_days": 1,
    }
    values.update(updates)
    return harness.DetectionConfig(**values)


def config(harness, **updates):
    values = {
        "detection": detection(harness),
        "chase_cap_atr": float("inf"),
        "same_side_reentry": harness.ReentryMode.OFF,
        "decel_exit_days": 0,
        "hard_stop_atr": 2.5,
        "trail_atr": 4.0,
        "long_oapp": harness.LongOAPPMode.OFF,
        "short_rsi": harness.ShortRSIMode.OFF,
    }
    values.update(updates)
    return harness.LifecycleConfig(**values)


def market(
    close: np.ndarray,
    ma7: np.ndarray,
    *,
    atr: float | np.ndarray = 1.0,
    rsi: float | np.ndarray = 50.0,
    opens: np.ndarray | None = None,
    hourly_open: np.ndarray | None = None,
    hourly_high: np.ndarray | None = None,
    hourly_low: np.ndarray | None = None,
    funding: dict[tuple[int, int], float] | None = None,
):
    count = len(close)
    index = pd.date_range("2026-01-01", periods=count, tz="UTC", freq="D")
    atr_values = np.full(count, atr, dtype=float) if np.isscalar(atr) else np.asarray(atr, dtype=float)
    rsi_values = np.full(count, rsi, dtype=float) if np.isscalar(rsi) else np.asarray(rsi, dtype=float)
    open_values = np.asarray(close if opens is None else opens, dtype=float)
    if hourly_open is None:
        hourly_open = np.repeat(open_values[:, None], 24, axis=1)
    if hourly_high is None:
        hourly_high = np.asarray(hourly_open, dtype=float) + 0.05
    if hourly_low is None:
        hourly_low = np.asarray(hourly_open, dtype=float) - 0.05
    events: list[list[SimpleNamespace]] = [[] for _ in range(count)]
    for (day, hour), rate in (funding or {}).items():
        events[day].append(
            SimpleNamespace(
                ts=index[day] + pd.Timedelta(hours=hour),
                rate=rate,
                price=float(hourly_open[day, hour]),
            )
        )
    high = np.maximum.reduce(
        [open_values, np.asarray(close, dtype=float), np.asarray(hourly_high).max(axis=1)]
    )
    low = np.minimum.reduce(
        [open_values, np.asarray(close, dtype=float), np.asarray(hourly_low).min(axis=1)]
    )
    daily = pd.DataFrame(
        {
            "open": open_values,
            "high": high,
            "low": low,
            "close": close,
            "ma7": ma7,
            "atr7": atr_values,
            "rsi6": rsi_values,
        },
        index=index,
    )
    book = SimpleNamespace(
        count=count,
        ts=index,
        terminal_ts=index[-1] + pd.Timedelta(days=1),
        open=open_values,
        high=high,
        low=low,
        close=np.asarray(close, dtype=float),
        quality={"terminal_open": float(open_values[-1])},
    )
    features = SimpleNamespace(
        hourly_open=np.asarray(hourly_open, dtype=float),
        hourly_high=np.asarray(hourly_high, dtype=float),
        hourly_low=np.asarray(hourly_low, dtype=float),
        funding_events=events,
    )
    return SimpleNamespace(book=book, daily=daily, features=features)


def up_market(days: int = 14):
    close = 100.0 + np.arange(days) * 0.20
    return market(close, close - 0.10)


def down_market(days: int = 14, *, rsi: float | np.ndarray = 50.0):
    close = 110.0 - np.arange(days) * 0.20
    return market(close, close + 0.10, rsi=rsi)


def test_daily_signal_executes_at_next_open_and_terminal_suppresses_new_entry() -> None:
    harness = load_harness()
    data = up_market(12)
    result = harness.backtest(
        data,
        config(harness, hard_stop_atr=0.0),
        label="NEXT",
        start_index=7,
        terminal_index=11,
        retain=True,
    )
    entry = next(action for action in result.actions if action["target_side"] == 1)
    assert entry["signal_ts"] == data.daily.index[7].isoformat()
    assert entry["ts"] == data.daily.index[8].isoformat()
    assert result.trades[0]["entry_phase"] == "established"
    assert result.metrics["pending_terminal_suppression_count"] == 0
    assert result.actions[-1]["reason"] == "terminal_flatten"


def test_confirmed_reversal_is_atomic_and_charges_two_fills() -> None:
    harness = load_harness()
    close = np.array([100, 100.2, 100.4, 100.6, 100.8, 101, 101.2, 101.4, 101.6, 99, 97, 95, 93], dtype=float)
    ma7 = np.array([value - 0.1 if i < 9 else value + 0.1 for i, value in enumerate(close)])
    data = market(close, ma7)
    result = harness.backtest(
        data,
        config(harness, hard_stop_atr=0.0),
        label="REV",
        start_index=7,
        terminal_index=12,
        retain=True,
    )
    reversals = [action for action in result.actions if action["reason"] == "confirmed_trend_reversal"]
    assert len(reversals) == 1
    assert reversals[0]["from_side"] == 1
    assert reversals[0]["target_side"] == -1
    assert reversals[0]["fills"] == 2
    assert [trade["side"] for trade in result.trades][:2] == ["long", "short"]
    assert result.metrics["fill_count"] == sum(action["fills"] for action in result.actions)


def test_entry_open_funding_is_charged_but_pre_entry_funding_is_not() -> None:
    harness = load_harness()
    base = up_market(12)
    data = market(
        base.book.close,
        base.daily["ma7"].to_numpy(),
        funding={(7, 0): 0.01, (8, 0): 0.01},
    )
    result = harness.backtest(
        data,
        config(harness),
        label="FUND",
        start_index=7,
        terminal_index=10,
        retain=True,
    )
    entry_qty = float(result.trades[0]["entry_quantity"])
    expected = entry_qty * float(data.book.open[8]) * 0.01
    assert result.metrics["funding_payment"] == pytest.approx(expected)
    assert result.trades[0]["funding_payment"] == pytest.approx(expected)


def test_gap_stop_precedes_same_hour_funding_and_can_reenter_after_full_day() -> None:
    harness = load_harness()
    base = up_market(14)
    opens = base.book.close.copy()
    opens[9] = opens[8] - 3.0
    hourly_open = np.repeat(opens[:, None], 24, axis=1)
    data = market(
        base.book.close,
        base.daily["ma7"].to_numpy(),
        opens=opens,
        hourly_open=hourly_open,
        funding={(9, 0): 0.05},
    )
    result = harness.backtest(
        data,
        config(
            harness,
            same_side_reentry=harness.ReentryMode.CONTINUATION,
            hard_stop_atr=2.5,
        ),
        label="GAP",
        start_index=7,
        terminal_index=13,
        retain=True,
    )
    stop = next(action for action in result.actions if action["reason"] == "protective_stop")
    entries = [action for action in result.actions if action["target_side"] == 1]
    assert stop["gap"] is True and stop["hour"] == 0
    assert result.metrics["funding_payment"] == 0.0
    assert len(entries) >= 2
    assert entries[1]["ts"] == data.daily.index[10].isoformat()


def test_intraday_stop_requires_next_complete_day_before_reentry() -> None:
    harness = load_harness()
    base = up_market(15)
    hourly_open = np.repeat(base.book.open[:, None], 24, axis=1)
    hourly_high = hourly_open + 0.05
    hourly_low = hourly_open - 0.05
    hourly_low[9, 5] = base.book.open[8] - 3.0
    data = market(
        base.book.close,
        base.daily["ma7"].to_numpy(),
        hourly_open=hourly_open,
        hourly_high=hourly_high,
        hourly_low=hourly_low,
    )
    result = harness.backtest(
        data,
        config(
            harness,
            same_side_reentry=harness.ReentryMode.CONTINUATION,
            hard_stop_atr=2.5,
        ),
        label="MIDSTOP",
        start_index=7,
        terminal_index=14,
        retain=True,
    )
    entries = [action for action in result.actions if action["target_side"] == 1]
    stop = next(action for action in result.actions if action["reason"] == "protective_stop")
    assert stop["hour"] == 5 and stop["gap"] is False
    assert entries[1]["ts"] == data.daily.index[11].isoformat()


def test_v5_oapp_and_short_rsi_are_post_entry_profit_exits() -> None:
    harness = load_harness()
    up_close = np.array([98.6, 98.8, 99.0, 99.2, 99.4, 99.6, 99.8, 100.0, 101.0, 102.0, 101.8, 101.7, 101.9, 102.0])
    up_ma = np.linspace(98.5, 101.5, len(up_close))
    up_ma[:8] = up_close[:8] - 0.1
    up_data = market(up_close, up_ma, opens=np.array([*up_close[:8], 100.0, *up_close[9:]]))
    up_result = harness.backtest(
        up_data,
        config(harness, hard_stop_atr=0.0, long_oapp=harness.LongOAPPMode.V5_FIXED),
        label="OAPP",
        start_index=7,
        terminal_index=13,
        retain=True,
    )
    assert any(trade["exit_reason"] == "long_oapp_v5_fixed_exit" for trade in up_result.trades)

    rsi = np.full(14, 50.0)
    rsi[8:10] = 19.0
    down_close = 110.0 - np.arange(14) * 0.50
    down_data = market(down_close, down_close + 0.10, rsi=rsi)
    down_result = harness.backtest(
        down_data,
        config(harness, hard_stop_atr=0.0, short_rsi=harness.ShortRSIMode.RSI20X2),
        label="RSI",
        start_index=7,
        terminal_index=12,
        retain=True,
    )
    rsi_trade = next(trade for trade in down_result.trades if trade["exit_reason"] == "short_rsi_take_profit")
    assert rsi_trade["exit_ts"] == down_data.daily.index[10].isoformat()
    assert rsi_trade["gross_return"] > 0.0028


def test_extra_delay_executes_at_12utc_without_using_close_data() -> None:
    harness = load_harness()
    data = up_market(12)
    result = harness.backtest(
        data,
        config(harness),
        label="D12",
        start_index=7,
        terminal_index=11,
        extra_delay_hours=12,
        retain=True,
    )
    entry = next(action for action in result.actions if action["target_side"] == 1)
    assert entry["ts"] == (data.daily.index[8] + pd.Timedelta(hours=12)).isoformat()
    assert entry["signal_ts"] == data.daily.index[7].isoformat()
    assert entry["delay_hours"] == 12


def test_bankruptcy_is_frozen_at_zero_and_cannot_recover() -> None:
    harness = load_harness()
    base = down_market(13)
    opens = base.book.close.copy()
    opens[9] = 250.0
    hourly_open = np.repeat(opens[:, None], 24, axis=1)
    data = market(
        base.book.close,
        base.daily["ma7"].to_numpy(),
        opens=opens,
        hourly_open=hourly_open,
    )
    result = harness.backtest(
        data,
        config(harness, hard_stop_atr=0.0),
        label="BK",
        start_index=7,
        terminal_index=12,
        retain=True,
    )
    assert result.metrics["bankrupt"] is True
    assert result.metrics["equity_multiple"] == 0.0
    assert result.metrics["max_drawdown_pct"] == -100.0
    assert result.trades[-1]["exit_reason"] in {
        "session_open_bankruptcy",
        "hour_open_bankruptcy",
    }
    assert result.path[-1]["ts"] < data.daily.index[10].isoformat()
