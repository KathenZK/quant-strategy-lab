from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "hype_1d_ma7_original_trend_engine.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_original_engine", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ENGINE = load_module()


def config(**overrides):
    values = {
        "prior_side_days": 1,
        "session_open_hour": 0,
        "tolerance_atr": 0.75,
        "slope_min_atr": 0.02,
        "entry_requires_slope": False,
        "band_requires_slope": True,
        "slope_loss_action": ENGINE.SlopeLossAction.HOLD,
        "arm_cross_while_held": True,
        "arm_expiry_days": None,
        "flat_cross_waits_for_confirmation": False,
        "short_rsi_exit_enabled": False,
        "short_rsi_exit_threshold": 30.0,
        "short_rsi_exit_days": 3,
        "short_rsi_exit_requires_profit": False,
        "overbought_mode": ENGINE.OverboughtMode.DISABLED,
        "overbought_threshold": 70.0,
        "overbought_days": 3,
        "overbought_requires_short_slope": True,
        "strict_previous_side": True,
    }
    values.update(overrides)
    return ENGINE.StrategyConfig(**values)


def obs(day: int, close: float, *, slope: float, rsi: float = 50.0):
    return ENGINE.CloseObservation(
        ts=pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=day),
        close=close,
        ma7=100.0,
        atr7=10.0,
        slope_atr=slope,
        rsi6=rsi,
    )


def enter_long(machine) -> None:
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    decision = machine.on_close(obs(1, 101.0, slope=0.0))
    assert decision is not None and decision.target_side == ENGINE.Side.LONG
    assert machine.state.side == ENGINE.Side.FLAT
    machine.on_next_open(decision.next_open_ts, 102.0)


def enter_short(machine) -> None:
    assert machine.on_close(obs(0, 101.0, slope=0.1)) is None
    decision = machine.on_close(obs(1, 99.0, slope=0.0))
    assert decision is not None and decision.target_side == ENGINE.Side.SHORT
    machine.on_next_open(decision.next_open_ts, 98.0)


def test_fresh_cross_decision_is_not_filled_until_next_open() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    decision = machine.on_close(obs(1, 101.0, slope=0.0))

    assert decision.reason == "fresh_cross_long"
    assert decision.fills == 1
    assert machine.state.side == ENGINE.Side.FLAT
    with pytest.raises(RuntimeError, match="must execute"):
        machine.on_close(obs(2, 102.0, slope=0.1))

    assert decision.next_open_ts == pd.Timestamp("2026-01-03", tz="UTC")
    machine.on_next_open(decision.next_open_ts, 103.0)
    assert machine.state.side == ENGINE.Side.LONG
    assert machine.state.entry_price == pytest.approx(103.0)


def test_strict_two_day_cross_rejects_equality_with_ma7() -> None:
    machine = ENGINE.OriginalTrendMachine(config(prior_side_days=2))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 100.0, slope=0.0)) is None
    assert machine.on_close(obs(2, 101.0, slope=0.1)) is None


def test_held_cross_arms_then_reverses_only_after_lower_band_confirmation() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    enter_long(machine)

    assert machine.on_close(obs(2, 99.0, slope=-0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.SHORT
    decision = machine.on_close(obs(3, 92.0, slope=-0.1))

    assert decision.reason == "armed_short_band_confirm"
    assert decision.fills == 2
    assert machine.state.side == ENGINE.Side.LONG
    machine.on_next_open(decision.next_open_ts, 91.0)
    assert machine.state.side == ENGINE.Side.SHORT


def test_armed_short_is_cancelled_when_price_recovers_above_ma7() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    enter_long(machine)
    assert machine.on_close(obs(2, 99.0, slope=-0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.SHORT

    assert machine.on_close(obs(3, 101.0, slope=0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.FLAT


def test_three_rsi6_closes_below_30_exit_short_to_flat() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(short_rsi_exit_enabled=True, short_rsi_exit_threshold=30.0)
    )
    enter_short(machine)

    assert machine.on_close(obs(2, 97.0, slope=-0.1, rsi=29.0)) is None
    assert machine.on_close(obs(3, 96.0, slope=-0.1, rsi=28.0)) is None
    decision = machine.on_close(obs(4, 95.0, slope=-0.1, rsi=27.0))

    assert decision.reason == "short_rsi_take_profit"
    assert decision.target_side == ENGINE.Side.FLAT
    assert decision.fills == 1


def test_rsi_profit_requirement_prevents_a_losing_short_exit() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            short_rsi_exit_enabled=True,
            short_rsi_exit_requires_profit=True,
        )
    )
    enter_short(machine)
    assert machine.state.entry_price == pytest.approx(98.0)

    assert machine.on_close(obs(2, 101.0, slope=-0.1, rsi=29.0)) is None
    assert machine.on_close(obs(3, 100.0, slope=-0.1, rsi=28.0)) is None
    assert machine.on_close(obs(4, 99.0, slope=-0.1, rsi=27.0)) is None


def test_rsi_flat_exit_preserves_an_opposite_cross_arm() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            short_rsi_exit_enabled=True,
            short_rsi_exit_requires_profit=True,
        )
    )
    assert machine.on_close(obs(0, 101.0, slope=0.1)) is None
    entry = machine.on_close(obs(1, 99.0, slope=-0.1))
    machine.on_next_open(entry.next_open_ts, 108.0)
    assert machine.on_close(obs(2, 97.0, slope=-0.1, rsi=29.0)) is None
    assert machine.on_close(obs(3, 96.0, slope=-0.1, rsi=28.0)) is None

    decision = machine.on_close(obs(4, 101.0, slope=0.01, rsi=27.0))
    assert decision.reason == "short_rsi_take_profit"
    assert machine.state.armed_side == ENGINE.Side.LONG
    machine.on_next_open(decision.next_open_ts, 100.0)
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.armed_side == ENGINE.Side.LONG


def test_delayed_fill_observation_advances_history_without_replacing_decision() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    decision = machine.on_close(obs(1, 101.0, slope=0.1))
    assert decision.reason == "fresh_cross_long"

    machine.observe_pending_close(obs(2, 102.0, slope=0.1, rsi=55.0))
    assert machine.state.pending is decision
    assert machine.state.last_close_ts == obs(2, 102.0, slope=0.1).ts
    machine.on_next_open(
        decision.next_open_ts + pd.Timedelta(days=1), 103.0, extra_delay_days=1
    )
    assert machine.state.side == ENGINE.Side.LONG
    assert machine.on_close(obs(3, 104.0, slope=0.1)) is None


def test_overbought_memory_can_reverse_before_lower_band() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(overbought_mode=ENGINE.OverboughtMode.EARLY_REVERSAL)
    )
    enter_long(machine)
    assert machine.on_close(obs(2, 102.0, slope=0.1, rsi=75.0)) is None
    assert machine.on_close(obs(3, 103.0, slope=0.1, rsi=76.0)) is None
    assert machine.on_close(obs(4, 104.0, slope=0.1, rsi=77.0)) is None

    decision = machine.on_close(obs(5, 99.0, slope=-0.1, rsi=65.0))
    assert 99.0 > 100.0 - 0.75 * 10.0
    assert decision.reason == "overbought_fresh_down"
    assert decision.target_side == ENGINE.Side.SHORT


def test_slope_loss_is_explicitly_hold_or_flat() -> None:
    hold_machine = ENGINE.OriginalTrendMachine(config())
    enter_long(hold_machine)
    assert hold_machine.on_close(obs(2, 101.0, slope=-0.1)) is None
    assert hold_machine.state.side == ENGINE.Side.LONG

    flat_machine = ENGINE.OriginalTrendMachine(
        config(slope_loss_action=ENGINE.SlopeLossAction.FLAT)
    )
    enter_long(flat_machine)
    decision = flat_machine.on_close(obs(2, 101.0, slope=-0.1))
    assert decision.reason == "long_slope_lost"
    assert decision.target_side == ENGINE.Side.FLAT


def test_slope_flat_preserves_cross_arm_until_band_confirmation() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            slope_min_atr=0.0,
            slope_loss_action=ENGINE.SlopeLossAction.FLAT,
        )
    )
    enter_long(machine)

    exit_decision = machine.on_close(obs(2, 99.0, slope=-0.01))
    assert exit_decision.reason == "long_slope_lost"
    assert machine.state.armed_side == ENGINE.Side.SHORT
    machine.on_next_open(exit_decision.next_open_ts, 98.0)
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.armed_side == ENGINE.Side.SHORT

    short_decision = machine.on_close(obs(3, 92.0, slope=-0.01))
    assert short_decision.reason == "armed_band_confirm_short"
    assert short_decision.target_side == ENGINE.Side.SHORT


def test_zero_slope_does_not_count_as_directional_trend() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            slope_min_atr=0.0,
            slope_loss_action=ENGINE.SlopeLossAction.FLAT,
        )
    )
    enter_long(machine)
    decision = machine.on_close(obs(2, 101.0, slope=0.0))
    assert decision.reason == "long_slope_lost"


def test_indicator_history_is_unchanged_when_future_prices_change() -> None:
    index = pd.date_range("2026-01-01", periods=16, freq="1D", tz="UTC")
    close = pd.Series(range(100, 116), index=index, dtype=float)
    frame = pd.DataFrame(
        {
            "open": close - 0.25,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
        },
        index=index,
    )
    baseline = ENGINE.add_daily_indicators(frame)
    changed = frame.copy()
    changed.loc[index[-1], ["open", "high", "low", "close"]] = [
        199.0,
        201.0,
        198.0,
        200.0,
    ]
    changed_result = ENGINE.add_daily_indicators(changed)

    pd.testing.assert_frame_equal(
        baseline.loc[: index[-2], ["ma7", "atr7", "rsi6", "slope_atr"]],
        changed_result.loc[: index[-2], ["ma7", "atr7", "rsi6", "slope_atr"]],
    )


def test_indicator_builder_rejects_naive_or_invalid_daily_data() -> None:
    frame = pd.DataFrame(
        {"open": [100.0], "high": [99.0], "low": [98.0], "close": [100.0]},
        index=pd.DatetimeIndex([pd.Timestamp("2026-01-01")]),
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        ENGINE.add_daily_indicators(frame)

    frame.index = frame.index.tz_localize("UTC")
    with pytest.raises(ValueError, match="invalid OHLC"):
        ENGINE.add_daily_indicators(frame)


def test_next_open_and_daily_gap_fail_closed() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    decision = machine.on_close(obs(1, 101.0, slope=0.1))
    with pytest.raises(RuntimeError, match="must fill"):
        machine.on_next_open(decision.next_open_ts + pd.Timedelta(hours=1), 102.0)
    machine.on_next_open(decision.next_open_ts, 102.0)

    with pytest.raises(RuntimeError, match="consecutive UTC"):
        machine.on_close(obs(3, 103.0, slope=0.1))


def test_indicator_builder_rejects_nulls_and_non_daily_utc_labels() -> None:
    index = pd.date_range("2026-01-01", periods=8, freq="1D", tz="UTC")
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        index=index,
    )
    frame.loc[index[3], "close"] = float("nan")
    with pytest.raises(ValueError, match="invalid OHLC"):
        ENGINE.add_daily_indicators(frame)

    shifted = frame.fillna(100.0)
    shifted.index = shifted.index + pd.Timedelta(hours=12)
    with pytest.raises(ValueError, match="expected UTC session opens"):
        ENGINE.add_daily_indicators(shifted)


def test_history_priming_and_external_stop_are_explicit() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    machine.prime_history(
        [
            obs(0, 99.0, slope=-0.1, rsi=40.0),
            obs(1, 98.0, slope=-0.1, rsi=35.0),
        ]
    )
    decision = machine.on_close(obs(2, 101.0, slope=0.1, rsi=50.0))
    assert decision.reason == "fresh_cross_long"
    machine.on_next_open(decision.next_open_ts, 102.0)
    machine.force_flat()
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.entry_price is None


def test_nonzero_phase_is_supported_only_when_explicitly_configured() -> None:
    machine = ENGINE.OriginalTrendMachine(config(session_open_hour=12))
    phased = ENGINE.CloseObservation(
        ts=pd.Timestamp("2026-01-01T12:00:00Z"),
        close=99.0,
        ma7=100.0,
        atr7=10.0,
        slope_atr=-0.1,
        rsi6=40.0,
    )
    assert machine.on_close(phased) is None

    index = pd.date_range("2026-01-01T12:00:00Z", periods=8, freq="1D")
    frame = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0},
        index=index,
    )
    result = ENGINE.add_daily_indicators(frame, expected_phase_hour=12)
    assert result.index[0].hour == 12
