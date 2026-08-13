from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
    / "hype_1d_ma7_intent_search_engine.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_intent_search_engine", SCRIPT)
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
        "slope_lookback": 1,
        "entry_slope_required": True,
        "slope_loss_confirm_days": 1,
        "arm_expiry_days": None,
        "max_chase_atr": 0.75,
        "flat_entry_mode": ENGINE.FlatEntryMode.FRESH_CROSS,
        "direct_reversal_enabled": True,
        "hold_slope_exit_enabled": True,
        "short_rsi_exit_enabled": False,
        "short_rsi_exit_threshold": 30.0,
        "short_rsi_exit_days": 3,
        "roundtrip_cost_rate": 0.02,
        "overbought_mode": ENGINE.OverboughtMode.DISABLED,
        "overbought_threshold": 70.0,
        "overbought_days": 3,
        "strict_previous_side": False,
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


def enter_long(machine, *, fill_price: float = 102.0) -> None:
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    decision = machine.on_close(obs(1, 101.0, slope=0.1))
    assert decision is not None and decision.target_side == ENGINE.Side.LONG
    assert machine.state.side == ENGINE.Side.FLAT
    machine.on_next_open(decision.next_open_ts, fill_price)


def enter_short(machine, *, fill_price: float = 100.0) -> None:
    assert machine.on_close(obs(0, 101.0, slope=0.1)) is None
    decision = machine.on_close(obs(1, 99.0, slope=-0.1))
    assert decision is not None and decision.target_side == ENGINE.Side.SHORT
    machine.on_next_open(decision.next_open_ts, fill_price)


def test_fresh_cross_is_strict_and_fills_only_at_next_open() -> None:
    machine = ENGINE.OriginalTrendMachine(config(prior_side_days=2))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 98.0, slope=-0.1)) is None
    decision = machine.on_close(obs(2, 101.0, slope=0.021))

    assert decision.reason == "fresh_cross_long"
    assert decision.fills == 1
    assert machine.state.side == ENGINE.Side.FLAT
    with pytest.raises(RuntimeError, match="must execute"):
        machine.on_close(obs(3, 102.0, slope=0.1))
    machine.on_next_open(decision.next_open_ts, 102.0)
    assert machine.state.side == ENGINE.Side.LONG


def test_prior_equality_is_allowed_but_signal_equality_is_not_a_cross() -> None:
    machine = ENGINE.OriginalTrendMachine(config(prior_side_days=2))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 100.0, slope=-0.1)) is None
    decision = machine.on_close(obs(2, 101.0, slope=0.1))
    assert decision.reason == "fresh_cross_long"

    signal_touch = ENGINE.OriginalTrendMachine(config())
    assert signal_touch.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert signal_touch.on_close(obs(1, 100.0, slope=0.1)) is None


def test_fresh_cross_n_one_two_three_is_symmetric_for_long_and_short() -> None:
    for prior_days in (1, 2, 3):
        for target in (ENGINE.Side.LONG, ENGINE.Side.SHORT):
            machine = ENGINE.OriginalTrendMachine(
                config(prior_side_days=prior_days)
            )
            prior_close = 99.0 if target == ENGINE.Side.LONG else 101.0
            prior_slope = -0.1 if target == ENGINE.Side.LONG else 0.1
            for day in range(prior_days):
                assert machine.on_close(
                    obs(day, prior_close, slope=prior_slope)
                ) is None
            signal_close = 101.0 if target == ENGINE.Side.LONG else 99.0
            signal_slope = 0.1 if target == ENGINE.Side.LONG else -0.1
            decision = machine.on_close(
                obs(prior_days, signal_close, slope=signal_slope)
            )
            assert decision is not None
            assert decision.target_side == target


def test_flat_slope_equality_arms_then_max_chase_boundary_confirms() -> None:
    machine = ENGINE.OriginalTrendMachine(config(arm_expiry_days=1))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 101.0, slope=0.02)) is None
    assert machine.state.armed_side == ENGINE.Side.LONG
    assert machine.state.armed_origin == ENGINE.ArmOrigin.FLAT_CROSS

    decision = machine.on_close(obs(2, 107.5, slope=0.021))
    assert decision.reason == "flat_armed_slope_confirm_long"
    assert decision.arm_effect == ENGINE.ArmEffect.CLEAR


def test_entry_slope_oat_can_remove_gate_and_lookback_is_explicit_metadata() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(entry_slope_required=False, slope_lookback=3)
    )
    assert machine.config.slope_lookback == 3
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None

    decision = machine.on_close(obs(1, 101.0, slope=-0.1))
    assert decision.reason == "fresh_cross_long"


def test_nonfinite_observation_fails_closed_before_state_mutation() -> None:
    machine = ENGINE.OriginalTrendMachine(config())
    with pytest.raises(ValueError, match="finite"):
        machine.on_close(obs(0, 99.0, slope=float("nan")))
    assert machine.state.last_close_ts is None
    assert machine.state.side == ENGINE.Side.FLAT


def test_flat_arm_does_not_chase_and_recross_replaces_it_with_new_intent() -> None:
    machine = ENGINE.OriginalTrendMachine(config(arm_expiry_days=2))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 101.0, slope=0.0)) is None
    assert machine.on_close(obs(2, 108.0, slope=0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.LONG

    assert machine.on_close(obs(3, 99.0, slope=0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.SHORT
    assert machine.state.armed_signal_ts == obs(3, 99.0, slope=0.1).ts


def test_touching_ma_cancels_an_armed_intent() -> None:
    machine = ENGINE.OriginalTrendMachine(config(arm_expiry_days=2))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 101.0, slope=0.0)) is None
    assert machine.state.armed_side == ENGINE.Side.LONG

    assert machine.on_close(obs(2, 100.0, slope=0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.FLAT


@pytest.mark.parametrize("expiry", [0, None])
def test_failed_flat_cross_does_not_arm_without_finite_wait(expiry) -> None:
    machine = ENGINE.OriginalTrendMachine(config(arm_expiry_days=expiry))
    assert machine.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert machine.on_close(obs(1, 101.0, slope=0.02)) is None
    assert machine.state.armed_side == ENGINE.Side.FLAT
    assert machine.on_close(obs(2, 102.0, slope=0.1)) is None


def test_arm_expiry_one_and_two_count_subsequent_closes_exactly() -> None:
    expiry_one = ENGINE.OriginalTrendMachine(config(arm_expiry_days=1))
    assert expiry_one.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert expiry_one.on_close(obs(1, 101.0, slope=0.0)) is None
    assert expiry_one.on_close(obs(2, 102.0, slope=0.0)) is None
    assert expiry_one.state.armed_age == 1
    assert expiry_one.on_close(obs(3, 103.0, slope=0.1)) is None
    assert expiry_one.state.armed_side == ENGINE.Side.FLAT

    expiry_two = ENGINE.OriginalTrendMachine(config(arm_expiry_days=2))
    assert expiry_two.on_close(obs(0, 99.0, slope=-0.1)) is None
    assert expiry_two.on_close(obs(1, 101.0, slope=0.0)) is None
    assert expiry_two.on_close(obs(2, 102.0, slope=0.0)) is None
    decision = expiry_two.on_close(obs(3, 103.0, slope=0.1))
    assert decision.reason == "flat_armed_slope_confirm_long"
    assert expiry_two.state.armed_age == 2


def test_persistent_regime_is_structurally_distinct_from_fresh_cross() -> None:
    fresh = ENGINE.OriginalTrendMachine(config())
    persistent = ENGINE.OriginalTrendMachine(
        config(flat_entry_mode=ENGINE.FlatEntryMode.PERSISTENT_REGIME)
    )

    assert fresh.on_close(obs(0, 101.0, slope=0.1)) is None
    decision = persistent.on_close(obs(0, 101.0, slope=0.1))
    assert decision.reason == "persistent_regime_long"


def test_held_band_must_be_crossed_then_reverses_atomically() -> None:
    machine = ENGINE.OriginalTrendMachine(config(hold_slope_exit_enabled=False))
    enter_long(machine)

    assert machine.on_close(obs(2, 92.5, slope=-0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.SHORT
    decision = machine.on_close(obs(3, 92.0, slope=-0.021))
    assert decision.reason == "held_arm_band_confirm_short"
    assert decision.fills == 2
    machine.on_next_open(decision.next_open_ts, 91.0)
    assert machine.state.side == ENGINE.Side.SHORT
    assert machine.state.slope_loss_run == 0
    assert machine.state.short_rsi_run == 0


def test_direct_reversal_disabled_flattens_and_preserves_held_arm() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(direct_reversal_enabled=False, arm_expiry_days=1)
    )
    enter_long(machine)
    decision = machine.on_close(obs(2, 92.0, slope=-0.1))

    assert decision.target_side == ENGINE.Side.FLAT
    assert decision.arm_effect == ENGINE.ArmEffect.PRESERVE
    machine.on_next_open(decision.next_open_ts, 91.0)
    assert machine.state.armed_origin == ENGINE.ArmOrigin.HELD_CROSS
    short_entry = machine.on_close(obs(3, 91.0, slope=-0.1))
    assert short_entry.reason == "held_arm_band_confirm_short"
    assert short_entry.target_side == ENGINE.Side.SHORT


def test_held_arm_expiry_zero_has_no_later_confirmation() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(arm_expiry_days=0, hold_slope_exit_enabled=False)
    )
    enter_long(machine)
    assert machine.on_close(obs(2, 99.0, slope=-0.1)) is None
    assert machine.state.armed_side == ENGINE.Side.FLAT
    assert machine.on_close(obs(3, 92.0, slope=-0.1)) is None


def test_overbought_uses_only_history_before_the_fresh_down_close() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            overbought_mode=ENGINE.OverboughtMode.EARLY_REVERSAL,
            hold_slope_exit_enabled=False,
        )
    )
    enter_long(machine)
    assert machine.on_close(obs(2, 102.0, slope=0.1, rsi=71.0)) is None
    assert machine.on_close(obs(3, 103.0, slope=0.1, rsi=72.0)) is None

    # Current RSI=99 must not complete a three-day *prior* streak.
    assert machine.on_close(obs(4, 99.0, slope=0.0, rsi=99.0)) is None
    assert machine.state.armed_overbought_qualified is False
    # The later band cannot recompute qualification from the now-updated RSI
    # window; only the fresh-cross-day snapshot may be consumed.
    assert machine.on_close(obs(5, 92.0, slope=0.0, rsi=50.0)) is None


def test_flat_fresh_short_accepts_prior_overbought_as_slope_alternative() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(overbought_mode=ENGINE.OverboughtMode.EARLY_REVERSAL)
    )
    assert machine.on_close(obs(0, 101.0, slope=0.1, rsi=71.0)) is None
    assert machine.on_close(obs(1, 102.0, slope=0.1, rsi=72.0)) is None
    assert machine.on_close(obs(2, 103.0, slope=0.1, rsi=73.0)) is None

    decision = machine.on_close(obs(3, 99.0, slope=0.0, rsi=50.0))
    assert decision.reason == "fresh_cross_short_overbought"
    assert decision.target_side == ENGINE.Side.SHORT


def test_held_overbought_is_frozen_but_still_requires_adverse_band() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            overbought_mode=ENGINE.OverboughtMode.EARLY_REVERSAL,
            hold_slope_exit_enabled=False,
        )
    )
    enter_long(machine)
    assert machine.on_close(obs(2, 102.0, slope=0.1, rsi=71.0)) is None
    assert machine.on_close(obs(3, 103.0, slope=0.1, rsi=72.0)) is None
    assert machine.on_close(obs(4, 104.0, slope=0.1, rsi=73.0)) is None

    # Fresh down freezes the prior overbought qualification, but 99 has not
    # crossed the 0.75 ATR adverse band and therefore cannot reverse early.
    assert machine.on_close(obs(5, 99.0, slope=0.0, rsi=50.0)) is None
    assert machine.state.armed_overbought_qualified is True

    decision = machine.on_close(obs(6, 92.0, slope=0.0, rsi=50.0))
    assert decision.reason == "held_arm_band_confirm_short_overbought"
    assert decision.target_side == ENGINE.Side.SHORT


def test_reverse_band_beats_short_rsi_take_profit_and_slope_loss() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(short_rsi_exit_enabled=True, slope_loss_confirm_days=1)
    )
    enter_short(machine)
    assert machine.on_close(obs(2, 95.0, slope=-0.1, rsi=20.0)) is None
    assert machine.on_close(obs(3, 94.0, slope=-0.1, rsi=20.0)) is None

    decision = machine.on_close(obs(4, 108.0, slope=0.1, rsi=20.0))
    assert machine.state.short_rsi_run == 3
    assert machine.state.slope_loss_run == 1
    assert decision.reason == "held_arm_band_confirm_long"
    assert decision.target_side == ENGINE.Side.LONG


def test_short_rsi_take_profit_beats_same_close_slope_loss() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(
            short_rsi_exit_enabled=True,
            short_rsi_exit_days=2,
            slope_loss_confirm_days=1,
        )
    )
    enter_short(machine, fill_price=100.0)
    assert machine.on_close(obs(2, 95.0, slope=-0.1, rsi=20.0)) is None

    decision = machine.on_close(obs(3, 94.0, slope=0.0, rsi=20.0))
    assert machine.state.short_rsi_run == 2
    assert machine.state.slope_loss_run == 1
    assert decision.reason == "short_rsi_take_profit"
    assert decision.target_side == ENGINE.Side.FLAT


def test_slope_loss_needs_consecutive_held_closes_and_clears_reverse_arm() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(slope_loss_confirm_days=2, arm_expiry_days=None)
    )
    enter_long(machine)
    assert machine.on_close(obs(2, 99.0, slope=-0.1)) is None
    assert machine.state.slope_loss_run == 1

    decision = machine.on_close(obs(3, 98.0, slope=-0.1))
    assert decision.reason == "long_slope_loss"
    assert decision.arm_effect == ENGINE.ArmEffect.CLEAR
    machine.on_next_open(decision.next_open_ts, 97.0)
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.armed_side == ENGINE.Side.FLAT


def test_hold_slope_exit_can_be_disabled() -> None:
    machine = ENGINE.OriginalTrendMachine(config(hold_slope_exit_enabled=False))
    enter_long(machine)
    assert machine.on_close(obs(2, 101.0, slope=-0.1)) is None
    assert machine.on_close(obs(3, 102.0, slope=-0.1)) is None
    assert machine.state.side == ENGINE.Side.LONG


def test_hold_slope_at_threshold_counts_as_loss() -> None:
    machine = ENGINE.OriginalTrendMachine(config(slope_loss_confirm_days=1))
    enter_long(machine)

    decision = machine.on_close(obs(2, 101.0, slope=0.02))
    assert decision.reason == "long_slope_loss"
    assert decision.arm_effect == ENGINE.ArmEffect.CLEAR


def test_short_rsi_streak_starts_only_after_actual_short_fill() -> None:
    machine = ENGINE.OriginalTrendMachine(config(short_rsi_exit_enabled=True))
    assert machine.on_close(obs(0, 101.0, slope=0.1, rsi=20.0)) is None
    decision = machine.on_close(obs(1, 99.0, slope=-0.1, rsi=20.0))
    machine.on_next_open(decision.next_open_ts, 100.0)

    assert machine.on_close(obs(2, 97.0, slope=-0.1, rsi=20.0)) is None
    assert machine.state.short_rsi_run == 1
    assert machine.on_close(obs(3, 96.0, slope=-0.1, rsi=20.0)) is None
    decision = machine.on_close(obs(4, 95.0, slope=-0.1, rsi=20.0))
    assert decision.reason == "short_rsi_take_profit"
    assert decision.arm_effect == ENGINE.ArmEffect.CLEAR


def test_short_rsi_exit_clears_a_same_day_opposite_arm() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(short_rsi_exit_enabled=True, arm_expiry_days=1)
    )
    enter_short(machine, fill_price=110.0)
    assert machine.on_close(obs(2, 95.0, slope=-0.1, rsi=20.0)) is None
    assert machine.on_close(obs(3, 94.0, slope=-0.1, rsi=20.0)) is None

    decision = machine.on_close(obs(4, 101.0, slope=0.0, rsi=20.0))
    assert machine.state.armed_side == ENGINE.Side.LONG
    assert decision.reason == "short_rsi_take_profit"
    assert decision.arm_effect == ENGINE.ArmEffect.CLEAR
    machine.on_next_open(decision.next_open_ts, 100.0)
    assert machine.state.armed_side == ENGINE.Side.FLAT


def test_short_rsi_profit_guard_is_strictly_beyond_roundtrip_cost() -> None:
    machine = ENGINE.OriginalTrendMachine(config(short_rsi_exit_enabled=True))
    enter_short(machine, fill_price=100.0)
    assert machine.on_close(obs(2, 99.0, slope=-0.1, rsi=20.0)) is None
    assert machine.on_close(obs(3, 98.5, slope=-0.1, rsi=20.0)) is None
    assert machine.on_close(obs(4, 98.0, slope=-0.1, rsi=20.0)) is None

    decision = machine.on_close(obs(5, 97.9, slope=-0.1, rsi=20.0))
    assert decision.reason == "short_rsi_take_profit"


def test_short_rsi_threshold_equality_resets_the_held_streak() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(short_rsi_exit_enabled=True, short_rsi_exit_days=2)
    )
    enter_short(machine)
    assert machine.on_close(obs(2, 95.0, slope=-0.1, rsi=20.0)) is None
    assert machine.state.short_rsi_run == 1
    assert machine.on_close(obs(3, 94.0, slope=-0.1, rsi=30.0)) is None
    assert machine.state.short_rsi_run == 0
    assert machine.on_close(obs(4, 93.0, slope=-0.1, rsi=20.0)) is None
    decision = machine.on_close(obs(5, 92.0, slope=-0.1, rsi=20.0))
    assert decision.reason == "short_rsi_take_profit"


def test_direct_reversal_fill_resets_all_held_close_streaks() -> None:
    machine = ENGINE.OriginalTrendMachine(config(short_rsi_exit_enabled=True))
    enter_short(machine)
    assert machine.on_close(obs(2, 95.0, slope=-0.1, rsi=20.0)) is None
    assert machine.on_close(obs(3, 94.0, slope=-0.1, rsi=20.0)) is None
    assert machine.state.short_rsi_run == 2

    decision = machine.on_close(obs(4, 108.0, slope=0.1, rsi=20.0))
    machine.on_next_open(decision.next_open_ts, 109.0)
    assert machine.state.side == ENGINE.Side.LONG
    assert machine.state.short_rsi_run == 0
    assert machine.state.slope_loss_run == 0


def test_external_exit_requires_explicit_pending_cancel_and_arm_effect() -> None:
    machine = ENGINE.OriginalTrendMachine(config(arm_expiry_days=1))
    enter_long(machine)
    decision = machine.on_close(obs(2, 92.0, slope=-0.1))
    assert decision is not None

    with pytest.raises(RuntimeError, match="pending"):
        machine.external_exit(cancel_pending=False)
    cancelled = machine.external_exit(
        cancel_pending=True,
        arm_effect=ENGINE.ArmEffect.PRESERVE,
    )
    assert cancelled is decision
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.pending is None
    assert machine.state.armed_side == ENGINE.Side.SHORT

    machine.external_exit(cancel_pending=False, arm_effect=ENGINE.ArmEffect.CLEAR)
    assert machine.state.armed_side == ENGINE.Side.FLAT


def test_delayed_close_ages_arm_without_replacing_pending_decision() -> None:
    machine = ENGINE.OriginalTrendMachine(
        config(direct_reversal_enabled=False, arm_expiry_days=1)
    )
    enter_long(machine)
    decision = machine.on_close(obs(2, 92.0, slope=-0.1))
    machine.observe_pending_close(obs(3, 91.0, slope=-0.1))

    assert machine.state.pending is decision
    assert machine.state.armed_age == 1
    machine.on_next_open(
        decision.next_open_ts + pd.Timedelta(days=1),
        90.0,
        extra_delay_days=1,
    )
    assert machine.state.side == ENGINE.Side.FLAT
    assert machine.state.armed_side == ENGINE.Side.SHORT
