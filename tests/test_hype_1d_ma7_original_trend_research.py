from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend/scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ENGINE = load_module(
    "hype_ma7_original_engine_harness_test",
    SCRIPT_DIR / "hype_1d_ma7_original_trend_engine.py",
)
RESEARCH = load_module(
    "hype_ma7_original_research_harness_test",
    SCRIPT_DIR / "research_hype_1d_ma7_original_trend.py",
)


def synthetic_market(*, stop_low: float | None = None, days: int = 7):
    index = pd.date_range("2026-01-01", periods=days, freq="1D", tz="UTC")
    opens = np.asarray([99.0 + day for day in range(days)], dtype=float)
    closes = np.asarray([99.0, 101.0, 103.0, 101.0, 102.0, 103.0, 104.0])[:days]
    slopes = np.asarray([-0.1, 0.1, 0.1, -0.1, 0.1, 0.1, 0.1])[:days]
    ma = np.full(days, 100.0)
    atr = np.full(days, 10.0)
    rsi = np.full(days, 50.0)
    highs = np.maximum(opens, closes) + 1.0
    lows = np.minimum(opens, closes) - 1.0
    hourly_open = np.repeat(opens[:, None], 24, axis=1)
    hourly_high = hourly_open + 0.5
    hourly_low = hourly_open - 0.5
    if stop_low is not None:
        hourly_low[2, 0] = stop_low
        lows[2] = min(lows[2], stop_low)

    daily = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "ma7": ma,
            "atr7": atr,
            "rsi6": rsi,
            "slope_atr": slopes,
        },
        index=index,
    )
    terminal_ts = index[-1] + pd.Timedelta(days=1)
    book = SimpleNamespace(
        ts=index,
        terminal_ts=terminal_ts,
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        count=days,
        quality={"terminal_open": float(opens[-1] + 1.0)},
    )
    features = SimpleNamespace(
        hourly_open=hourly_open,
        hourly_high=hourly_high,
        hourly_low=hourly_low,
        funding_events=[[] for _ in range(days)],
    )
    return RESEARCH.MarketData(
        book=book,
        features=features,
        daily=daily,
        hourly=pd.DataFrame(),
        funding=pd.DataFrame(),
        audit={},
    )


def core_config():
    return RESEARCH.frozen_configs(ENGINE)["A_CORE"]


def test_harness_fills_signals_only_at_next_open_and_keeps_quantity_fixed() -> None:
    data = synthetic_market()
    result = RESEARCH.backtest(
        ENGINE,
        data,
        core_config(),
        label="SYNTH",
        terminal_index=5,
        retain=True,
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade["entry_signal_ts"] == data.daily.index[1].isoformat()
    assert trade["entry_ts"] == data.daily.index[2].isoformat()
    assert trade["exit_ts"] == data.daily.index[4].isoformat()
    assert trade["entry_price"] == pytest.approx(data.book.open[2])
    assert trade["exit_price"] == pytest.approx(data.book.open[4])
    assert trade["exit_reason"] == "long_slope_lost"
    assert trade["entry_quantity"] > 0.0
    assert [action["fills"] for action in result.actions[:2]] == [1, 1]
    assert result.path[-1]["terminal"] is True
    assert result.path[-1]["equity"] == pytest.approx(result.metrics["equity_multiple"])


def test_harness_extra_delay_advances_close_history_and_fills_one_day_later() -> None:
    data = synthetic_market()
    result = RESEARCH.backtest(
        ENGINE,
        data,
        core_config(),
        label="DELAY",
        extra_delay_days=1,
        retain=True,
    )

    first_entry = next(
        action for action in result.actions if action["target_side"] == 1
    )
    assert first_entry["signal_ts"] == data.daily.index[1].isoformat()
    assert first_entry["ts"] == data.daily.index[3].isoformat()


def test_intraday_hard_stop_marks_to_stop_and_records_true_originating_side() -> None:
    data = synthetic_market(stop_low=96.0)
    result = RESEARCH.backtest(
        ENGINE,
        data,
        core_config(),
        label="STOP",
        hard_stop_atr=0.5,
        retain=True,
    )

    trade = result.trades[0]
    entry_price = float(data.book.open[2])
    stop_price = entry_price - 0.5 * 10.0
    assert trade["exit_reason"] == "emergency_hard_stop"
    assert trade["exit_price"] == pytest.approx(stop_price)
    stop_action = next(
        action for action in result.actions if action["reason"] == "emergency_hard_stop"
    )
    assert stop_action["from_side"] == 1
    assert stop_action["target_side"] == 0

    quantity, post_entry, _, _ = RESEARCH._target_quantity(
        1.0,
        0.0,
        1,
        entry_price,
        RESEARCH.FEE + RESEARCH.BASE_SLIPPAGE,
    )
    before_exit = post_entry + quantity * (stop_price - entry_price)
    expected = before_exit - quantity * stop_price * (
        RESEARCH.FEE + RESEARCH.BASE_SLIPPAGE
    )
    assert trade["exit_equity"] == pytest.approx(expected)
    assert trade["lowest"] == pytest.approx(stop_price)


def test_backtest_window_is_invariant_to_prices_strictly_after_terminal_open() -> None:
    baseline_data = synthetic_market()
    changed_data = synthetic_market()
    changed_data.book.open[6:] *= 3.0
    changed_data.book.high[6:] *= 3.0
    changed_data.book.low[6:] *= 3.0
    changed_data.book.close[6:] *= 3.0
    changed_data.daily.iloc[
        6:, changed_data.daily.columns.get_indexer(["open", "high", "low", "close"])
    ] *= 3.0
    changed_data.features.hourly_open[6:] *= 3.0
    changed_data.features.hourly_high[6:] *= 3.0
    changed_data.features.hourly_low[6:] *= 3.0

    baseline = RESEARCH.backtest(
        ENGINE,
        baseline_data,
        core_config(),
        label="FUTURE",
        terminal_index=5,
        retain=True,
    )
    changed = RESEARCH.backtest(
        ENGINE,
        changed_data,
        core_config(),
        label="FUTURE",
        terminal_index=5,
        retain=True,
    )

    assert baseline.metrics == changed.metrics
    assert baseline.trades == changed.trades
    assert baseline.actions == changed.actions
    assert baseline.path == changed.path


def test_mc3_uses_common_random_numbers_for_identical_trade_paths() -> None:
    data = synthetic_market()
    first = RESEARCH.backtest(
        ENGINE,
        data,
        core_config(),
        label="FIRST",
        retain=True,
    )
    second = RESEARCH.BacktestResult(
        metrics={**first.metrics, "label": "SECOND"},
        trades=first.trades,
        path=first.path,
        actions=first.actions,
    )
    rows = RESEARCH.mc3_rows(
        {"FIRST": first, "SECOND": second},
        samples=100,
        seed=20260809,
    )
    first_rows = [{k: v for k, v in row.items() if k != "label"} for row in rows[:5]]
    second_rows = [{k: v for k, v in row.items() if k != "label"} for row in rows[5:]]
    assert first_rows == second_rows
