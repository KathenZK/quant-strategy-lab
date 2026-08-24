from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
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
    "hype_ma7_intent_engine_harness_test",
    SCRIPT_DIR / "hype_1d_ma7_intent_search_engine.py",
)
HARNESS = load_module(
    "hype_ma7_intent_research_harness_test",
    SCRIPT_DIR / "research_hype_1d_ma7_original_trend.py",
)
TRACE = load_module(
    "hype_ma7_intent_state_trace_harness_test",
    SCRIPT_DIR / "hype_1d_ma7_intent_state_trace.py",
)
INDICATORS = load_module(
    "hype_ma7_intent_indicator_contract_test",
    SCRIPT_DIR / "hype_1d_ma7_original_trend_engine.py",
)


def config(**overrides):
    values = {
        "prior_side_days": 1,
        "session_open_hour": 0,
        "tolerance_atr": 0.75,
        "slope_min_atr": 0.0,
        "slope_lookback": 1,
        "entry_slope_required": True,
        "slope_loss_confirm_days": 1,
        "arm_expiry_days": 0,
        "max_chase_atr": 0.75,
        "flat_entry_mode": ENGINE.FlatEntryMode.FRESH_CROSS,
        "direct_reversal_enabled": True,
        "hold_slope_exit_enabled": True,
        "short_rsi_exit_enabled": False,
        "short_rsi_exit_threshold": 30.0,
        "short_rsi_exit_days": 3,
        "roundtrip_cost_rate": 0.0028,
        "overbought_mode": ENGINE.OverboughtMode.DISABLED,
        "overbought_threshold": 70.0,
        "overbought_days": 3,
        "strict_previous_side": False,
    }
    values.update(overrides)
    return ENGINE.StrategyConfig(**values)


def market(
    *,
    opens: list[float],
    closes: list[float],
    slopes: list[float],
    rsi: list[float] | None = None,
    funding_events: dict[int, list[SimpleNamespace]] | None = None,
):
    days = len(opens)
    assert len(closes) == len(slopes) == days
    index = pd.date_range("2026-01-01", periods=days, freq="1D", tz="UTC")
    open_values = np.asarray(opens, dtype=float)
    close_values = np.asarray(closes, dtype=float)
    high_values = np.maximum(open_values, close_values) + 1.0
    low_values = np.minimum(open_values, close_values) - 1.0
    rsi_values = np.asarray(rsi if rsi is not None else [50.0] * days)
    hourly_open = np.repeat(open_values[:, None], 24, axis=1)
    hourly_high = hourly_open + 0.5
    hourly_low = hourly_open - 0.5
    daily = pd.DataFrame(
        {
            "open": open_values,
            "high": high_values,
            "low": low_values,
            "close": close_values,
            "ma7": np.full(days, 100.0),
            "atr7": np.full(days, 10.0),
            "rsi6": rsi_values,
            "slope_atr": np.asarray(slopes, dtype=float),
        },
        index=index,
    )
    events = [[] for _ in range(days)]
    for day, rows in (funding_events or {}).items():
        events[day] = rows
    book = SimpleNamespace(
        ts=index,
        terminal_ts=index[-1] + pd.Timedelta(days=1),
        open=open_values,
        high=high_values,
        low=low_values,
        close=close_values,
        count=days,
        quality={"terminal_open": float(open_values[-1] + 1.0)},
    )
    features = SimpleNamespace(
        hourly_open=hourly_open,
        hourly_high=hourly_high,
        hourly_low=hourly_low,
        funding_events=events,
    )
    return HARNESS.MarketData(
        book=book,
        features=features,
        daily=daily,
        hourly=pd.DataFrame(),
        funding=pd.DataFrame(),
        audit={},
    )


def test_atomic_reversal_charges_two_fills_and_opens_the_new_side_once() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 90.0, 89.0],
        closes=[99.0, 101.0, 91.0, 89.0, 88.0],
        slopes=[-0.1, 0.1, -0.1, -0.1, -0.1],
    )
    result = HARNESS.backtest(
        ENGINE,
        data,
        config(hold_slope_exit_enabled=False),
        label="ATOMIC",
        retain=True,
    )

    reversal = next(action for action in result.actions if action["fills"] == 2)
    assert reversal["from_side"] == 1
    assert reversal["target_side"] == -1
    long_trade, short_trade = result.trades
    assert long_trade["exit_ts"] == short_trade["entry_ts"] == reversal["ts"]
    assert long_trade["exit_cost"] > 0.0
    assert short_trade["entry_cost"] > 0.0
    ledger_cost = sum(
        float(trade["entry_cost"]) + float(trade["exit_cost"])
        for trade in result.trades
    )
    assert result.metrics["cost"] == pytest.approx(ledger_cost)


def test_funding_is_charged_only_after_the_entry_open_boundary() -> None:
    index = pd.date_range("2026-01-01", periods=5, freq="1D", tz="UTC")
    rate = 0.001
    before_entry = SimpleNamespace(ts=index[1] + pd.Timedelta(hours=8), price=101.0, rate=rate)
    after_entry = SimpleNamespace(ts=index[2] + pd.Timedelta(hours=8), price=102.0, rate=rate)
    data = market(
        opens=[99.0, 100.0, 102.0, 103.0, 104.0],
        closes=[99.0, 101.0, 102.0, 103.0, 104.0],
        slopes=[-0.1, 0.1, 0.1, 0.1, 0.1],
        funding_events={1: [before_entry], 2: [after_entry]},
    )
    result = HARNESS.backtest(
        ENGINE,
        data,
        config(hold_slope_exit_enabled=False),
        label="FUNDING",
        retain=True,
    )

    trade = result.trades[0]
    expected = float(trade["entry_quantity"]) * after_entry.price * rate
    assert result.metrics["funding_payment"] == pytest.approx(expected)
    assert trade["funding_payment"] == pytest.approx(expected)


def test_short_rsi_signal_exits_at_the_real_gap_open_even_when_it_loses() -> None:
    data = market(
        opens=[101.0, 100.0, 100.0, 96.0, 95.0, 110.0, 109.0],
        closes=[101.0, 99.0, 95.0, 94.0, 93.0, 109.0, 108.0],
        slopes=[0.1, -0.1, -0.1, -0.1, -0.1, 0.1, 0.1],
        rsi=[50.0, 50.0, 20.0, 20.0, 20.0, 50.0, 50.0],
    )
    result = HARNESS.backtest(
        ENGINE,
        data,
        config(
            short_rsi_exit_enabled=True,
            hold_slope_exit_enabled=False,
        ),
        label="RSI-GAP",
        retain=True,
    )

    short_trade = result.trades[0]
    assert short_trade["exit_reason"] == "short_rsi_take_profit"
    assert short_trade["exit_ts"] == data.daily.index[5].isoformat()
    assert short_trade["exit_price"] == pytest.approx(110.0)
    assert short_trade["net_return"] < 0.0


def test_r1_gap_stop_uses_worse_hour_open_and_ignores_later_hour_extremes() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 103.0],
        closes=[99.0, 101.0, 103.0, 104.0],
        slopes=[-0.1, 0.1, 0.1, 0.1],
    )
    data.features.hourly_open[2, 1] = 80.0
    data.features.hourly_high[2, 1] = 200.0
    data.features.hourly_low[2, 1] = 70.0
    result = HARNESS.backtest(
        ENGINE,
        data,
        config(hold_slope_exit_enabled=False),
        label="R1-GAP",
        hard_stop_atr=1.5,
        retain=True,
    )

    stopped = result.trades[0]
    assert stopped["exit_reason"] == "emergency_hard_stop"
    assert stopped["exit_price"] == pytest.approx(80.0)
    assert stopped["highest"] < 200.0
    assert stopped["lowest"] == pytest.approx(80.0)


def test_r0_state_trace_matches_the_harness_path_and_action_schedule() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 90.0, 89.0],
        closes=[99.0, 101.0, 91.0, 89.0, 88.0],
        slopes=[-0.1, 0.1, -0.1, -0.1, -0.1],
    )
    strategy = config(hold_slope_exit_enabled=False)
    result = HARNESS.backtest(
        ENGINE,
        data,
        strategy,
        label="TRACE-PARITY",
        retain=True,
    )
    trace = TRACE.replay_state_trace(
        ENGINE,
        HARNESS,
        data,
        strategy,
        start_index=0,
        terminal_index=data.book.count,
    )

    daily_path = [row for row in result.path if not row["terminal"]]
    assert len(trace["rows"]) == len(daily_path)
    for traced, ledger in zip(trace["rows"], daily_path, strict=True):
        assert traced["ts"] == ledger["ts"]
        assert traced["side"] == ledger["side"]
        assert traced["armed_side"] == ledger["armed_side"]
        assert (traced["pending_reason"] or "") == ledger["pending_reason"]

    traced_actions = []
    for event in trace["events"]:
        if event["event"] == "decision_fill":
            decision = event["decision"]
            traced_actions.append(
                {
                    "ts": event["ts"],
                    "signal_ts": decision["signal_ts"],
                    "from_side": decision["from_side"],
                    "target_side": decision["target_side"],
                    "reason": decision["reason"],
                    "fills": decision["fills"],
                    "price": event["price"],
                }
            )
        elif event["event"] == "terminal_flatten":
            traced_actions.append(
                {
                    "ts": event["ts"],
                    "signal_ts": None,
                    "from_side": event["from_side"],
                    "target_side": event["target_side"],
                    "reason": "terminal_flatten",
                    "fills": event["fills"],
                    "price": event["price"],
                }
            )
    assert traced_actions == result.actions


def test_wilder_rsi6_initialization_and_boundary_vectors_are_frozen() -> None:
    index = pd.RangeIndex(8)
    rising = INDICATORS.wilder_rsi(pd.Series(range(100, 108), index=index), 6)
    falling = INDICATORS.wilder_rsi(pd.Series(range(108, 100, -1), index=index), 6)
    flat = INDICATORS.wilder_rsi(pd.Series([100.0] * 8, index=index), 6)
    mixed = INDICATORS.wilder_rsi(
        pd.Series([100.0, 102.0, 101.0, 104.0, 102.0, 105.0, 104.0, 108.0]),
        6,
    )

    assert rising.iloc[:6].isna().all()
    assert falling.iloc[:6].isna().all()
    assert flat.iloc[:6].isna().all()
    assert rising.iloc[6] == pytest.approx(100.0)
    assert falling.iloc[6] == pytest.approx(0.0)
    assert flat.iloc[6] == pytest.approx(50.0)
    assert mixed.iloc[6] == pytest.approx(66.66666666666667)
    assert mixed.iloc[7] == pytest.approx(76.19047619047619)


def test_funding_at_entry_reversal_and_exit_opens_uses_the_post_action_side() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="1D", tz="UTC")
    rate = 0.001
    entry_event = SimpleNamespace(ts=index[2], price=102.0, rate=rate)
    reversal_event = SimpleNamespace(ts=index[3], price=90.0, rate=rate)
    reversing = market(
        opens=[99.0, 100.0, 102.0, 90.0, 89.0, 88.0],
        closes=[99.0, 101.0, 91.0, 89.0, 88.0, 87.0],
        slopes=[-0.1, 0.1, -0.1, -0.1, -0.1, -0.1],
        funding_events={2: [entry_event], 3: [reversal_event]},
    )
    reversal_result = HARNESS.backtest(
        ENGINE,
        reversing,
        config(hold_slope_exit_enabled=False),
        label="FUNDING-REVERSAL",
        retain=True,
    )
    long_trade, short_trade = reversal_result.trades
    expected_reversal = (
        float(long_trade["entry_quantity"]) * entry_event.price * rate
        + float(short_trade["entry_quantity"]) * reversal_event.price * rate
    )
    assert reversal_result.metrics["funding_payment"] == pytest.approx(
        expected_reversal
    )

    exit_event = SimpleNamespace(ts=index[3], price=103.0, rate=rate)
    exiting = market(
        opens=[99.0, 100.0, 102.0, 103.0, 104.0, 105.0],
        closes=[99.0, 101.0, 101.0, 103.0, 104.0, 105.0],
        slopes=[-0.1, 0.1, -0.1, 0.1, 0.1, 0.1],
        funding_events={3: [exit_event]},
    )
    exit_result = HARNESS.backtest(
        ENGINE,
        exiting,
        config(),
        label="FUNDING-EXIT",
        retain=True,
    )
    assert exit_result.actions[1]["target_side"] == 0
    assert exit_result.actions[1]["ts"] == index[3].isoformat()
    assert exit_result.metrics["funding_payment"] == pytest.approx(0.0)


def test_segmented_candidate_flat_start_primes_history_but_not_position_state() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 98.0, 97.0, 96.0],
        closes=[99.0, 101.0, 99.0, 98.0, 97.0, 96.0],
        slopes=[-0.1, 0.1, -0.1, -0.1, -0.1, -0.1],
    )
    strategy = config(hold_slope_exit_enabled=False)
    result = HARNESS.backtest(
        ENGINE,
        data,
        strategy,
        label="SEGMENTED",
        start_index=2,
        terminal_index=6,
        retain=True,
    )
    trace = TRACE.replay_state_trace(
        ENGINE,
        HARNESS,
        data,
        strategy,
        start_index=2,
        terminal_index=6,
    )

    first_action = result.actions[0]
    assert first_action["signal_ts"] == data.daily.index[2].isoformat()
    assert first_action["ts"] == data.daily.index[3].isoformat()
    assert first_action["from_side"] == 0
    assert first_action["target_side"] == -1
    first_trace = trace["rows"][0]
    assert first_trace["side"] == 0
    assert first_trace["slope_loss_run"] == 0
    assert first_trace["short_rsi_run"] == 0
    assert first_trace["pending_reason"] == "fresh_cross_short"
