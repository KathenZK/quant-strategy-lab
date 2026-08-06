from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(
    "research/asset-portfolios/1d-ma7-deviation-continuation/scripts/"
    "research_binance_1d_ma7dc.py"
)
TRACK_SCRIPT = Path(
    "research/asset-portfolios/1d-ma7-deviation-continuation/scripts/"
    "audit_binance_1d_ma7dc_campaign_tracking.py"
)
TOLERANCE_SCRIPT = Path(
    "research/asset-portfolios/1d-ma7-deviation-continuation/scripts/"
    "audit_binance_1d_ma7dc_tolerance_exit.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("test_binance_1d_ma7dc_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_track_module():
    spec = importlib.util.spec_from_file_location("test_binance_1d_ma7dc_track_module", TRACK_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_tolerance_module():
    spec = importlib.util.spec_from_file_location(
        "test_binance_1d_ma7dc_tolerance_module", TOLERANCE_SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def synthetic_daily(closes: list[float]) -> pd.DataFrame:
    close = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "source_bars": 24,
        },
        index=pd.date_range("2026-01-01", periods=len(close), freq="1D", tz="UTC"),
    )


def test_daily_aggregation_uses_completed_source_day() -> None:
    module = load_module()
    source_index = pd.date_range("2026-01-01", periods=48, freq="1h", tz="UTC")
    visible_index = source_index + pd.Timedelta(hours=1)
    close = np.arange(48, dtype=float) + 100.0
    hourly = pd.DataFrame(
        {"open": close, "high": close + 1.0, "low": close - 1.0, "close": close},
        index=visible_index,
    )
    daily, quality = module.build_complete_daily(hourly)
    assert quality["accepted"] is True
    assert list(daily.index) == [
        pd.Timestamp("2026-01-02", tz="UTC"),
        pd.Timestamp("2026-01-03", tz="UTC"),
    ]
    assert daily.iloc[0]["close"] == 123.0


def test_rising_path_builds_positive_ma7_direction_and_deviation() -> None:
    module = load_module()
    states = module.build_states(synthetic_daily(list(np.arange(1.0, 25.0))))
    labelled = module.add_future_labels(states)
    row = states.iloc[-1]
    assert row["direction"] == 1.0
    assert row["ma7_slope_strength_atr"] > 0.0
    assert row["signed_deviation_atr"] > 0.0
    assert row["slope_persistence_days"] >= 2.0
    assert labelled["future_signed_log_return_7d"].notna().any()
    valid = labelled["future_signed_log_return_7d"].notna()
    assert np.allclose(
        labelled.loc[valid, "future_signed_log_return_7d"],
        labelled.loc[valid, "future_log_return_7d"],
    )


def test_restart_requires_prior_contraction_and_current_expansion() -> None:
    module = load_module()
    daily = synthetic_daily([10, 11, 12, 13, 14, 15, 16, 17, 16.8, 17.5, 18.5])
    states = module.build_states(daily)
    assert "restart" in set(states["state"])


def test_same_day_target_and_stop_is_conservative_failure() -> None:
    module = load_module()
    result = module._first_passage(
        highs=np.array([102.0]),
        lows=np.array([98.0]),
        entry=100.0,
        atr=1.0,
        side=1,
    )
    assert result == 0.0


def test_causal_quintile_does_not_use_current_or_future_value() -> None:
    module = load_module()
    values = pd.Series([1.0, 2.0, 3.0, 1000.0, -1000.0])
    quintiles = module._causal_quintile(values, min_history=3)
    assert pd.isna(quintiles.iloc[2])
    assert quintiles.iloc[3] == 5
    assert quintiles.iloc[4] == 1


def test_zigzag_records_only_reversal_confirmed_swings() -> None:
    module = load_track_module()
    frame = synthetic_daily([10, 11, 12, 13, 12, 11, 10, 11, 12])
    frame["atr7"] = 0.5
    swings = module.detect_completed_swings(frame, reversal_atr=2.0)
    assert len(swings) >= 1
    first = swings.iloc[0]
    assert first["side"] == 1
    assert first["end_index"] < first["confirmation_index"]


def test_campaign_entry_and_exit_use_signal_next_open() -> None:
    base = load_module()
    track = load_track_module()
    daily = synthetic_daily([10, 11, 12, 13, 14, 15, 14, 13, 12, 11, 10, 9, 8, 9, 10])
    states = base.build_states(daily)
    states["sma7"] = pd.Series([9.0] * 7 + [12.5] * 8, index=states.index)
    states["direction"] = pd.Series([1.0] * 10 + [-1.0] * 5, index=states.index)
    swing = pd.Series(
        {
            "swing_id": 1,
            "reversal_atr": 2.0,
            "side": 1,
            "direction": "long",
            "start_index": 6,
            "end_index": 9,
            "start_visible_ts": states.index[6],
            "end_visible_ts": states.index[9],
            "duration_days": 3,
            "swing_log_amplitude": np.log(states.iloc[9]["close"] / states.iloc[6]["close"]),
            "swing_atr_start": 2.0,
        }
    )
    funding = pd.Series(0.0, index=states.index)
    result = track.track_swing("TEST", states, funding, swing, "cross1")
    assert result["admitted"] is True
    assert result["entry_ts"] == result["entry_signal_visible_ts"]
    assert result["raw_entry"] == states.iloc[7]["open"]
    assert result["exit_ts"] == result["exit_signal_visible_ts"]


def test_cross2_requires_two_consecutive_opposite_closes() -> None:
    module = load_track_module()
    frame = synthetic_daily([10, 11, 12])
    frame["sma7"] = [9.0, 11.5, 12.5]
    assert module._exit_signal(frame, 1, side=1, mode="cross1") is True
    assert module._exit_signal(frame, 1, side=1, mode="cross2") is False
    assert module._exit_signal(frame, 2, side=1, mode="cross2") is True


def test_reentry_tracker_accumulates_multiple_round_trips() -> None:
    base = load_module()
    track = load_track_module()
    daily = synthetic_daily([10, 11, 12, 13, 14, 13, 15, 16, 15, 17, 18, 16, 15, 14, 13, 12])
    states = base.build_states(daily)
    states["sma7"] = pd.Series(
        [9, 9, 9, 9, 12, 13.5, 13, 13, 15.5, 15, 16, 16.5, 16, 15, 14, 13],
        index=states.index,
        dtype=float,
    )
    states["direction"] = 1.0
    swing = pd.Series(
        {
            "swing_id": 1,
            "reversal_atr": 2.0,
            "side": 1,
            "direction": "long",
            "start_index": 3,
            "end_index": 10,
            "start_visible_ts": states.index[3],
            "end_visible_ts": states.index[10],
            "duration_days": 7,
            "swing_log_amplitude": np.log(states.iloc[10]["close"] / states.iloc[3]["close"]),
            "swing_atr_start": 3.0,
        }
    )
    funding = pd.Series(0.0, index=states.index)
    result = track.track_swing_with_reentries("TEST", states, funding, swing, "cross1")
    assert result["round_trips"] >= 2
    assert result["reentries"] >= 1


def test_tolerance_band_ignores_one_shallow_breach_but_confirms_two() -> None:
    module = load_tolerance_module()
    frame = synthetic_daily([10.0, 9.4, 9.3, 8.8])
    frame["sma7"] = 10.0
    frame["atr7"] = 1.0
    frame["direction"] = 1.0
    assert (
        module.daily_exit_reason(
            frame,
            1,
            side=1,
            arm="band05_confirm2_risk",
            mfe_r=0.0,
            close_profit_r=0.0,
        )
        is None
    )
    assert module.daily_exit_reason(
        frame,
        2,
        side=1,
        arm="band05_confirm2_risk",
        mfe_r=0.0,
        close_profit_r=0.0,
    ) == "band_gt_05atr_twice"
    assert module.daily_exit_reason(
        frame,
        3,
        side=1,
        arm="band05_confirm2_risk",
        mfe_r=0.0,
        close_profit_r=0.0,
    ) == "band_gt_1atr"


def test_mfe50_only_activates_after_two_r() -> None:
    module = load_tolerance_module()
    frame = synthetic_daily([10.0, 10.0])
    frame["sma7"] = 9.5
    frame["atr7"] = 1.0
    frame["direction"] = 1.0
    assert (
        module.daily_exit_reason(
            frame,
            1,
            side=1,
            arm="band05_confirm2_mfe50_risk",
            mfe_r=1.9,
            close_profit_r=0.8,
        )
        is None
    )
    assert module.daily_exit_reason(
        frame,
        1,
        side=1,
        arm="band05_confirm2_mfe50_risk",
        mfe_r=3.0,
        close_profit_r=1.4,
    ) == "mfe50"


def test_hard_stop_gap_uses_worse_open_fill() -> None:
    module = load_tolerance_module()
    frame = pd.DataFrame(
        {
            "open": [10.0, 10.0, 8.0, 12.0, 13.0, 14.0, 13.0],
            "high": [10.5, 10.6, 8.5, 12.5, 13.5, 14.5, 13.5],
            "low": [9.5, 9.5, 7.5, 11.5, 12.5, 13.5, 12.5],
            "close": [10.0, 10.5, 8.0, 12.0, 13.0, 14.0, 13.0],
            "sma7": [9.0] * 7,
            "atr7": [1.0] * 7,
            "direction": [1.0] * 7,
        },
        index=pd.date_range("2026-01-01", periods=7, freq="1D", tz="UTC"),
    )
    swing = pd.Series(
        {
            "swing_id": 1,
            "reversal_atr": 2.0,
            "side": 1,
            "direction": "long",
            "start_index": 0,
            "end_index": 5,
            "start_visible_ts": frame.index[0],
            "end_visible_ts": frame.index[5],
            "duration_days": 5,
            "swing_log_amplitude": np.log(frame.iloc[5]["close"] / frame.iloc[0]["close"]),
        }
    )
    funding = pd.Series(0.0, index=frame.index)
    result = module.track_leg(
        "TEST",
        frame,
        funding,
        swing,
        "band05_confirm2_mfe50_risk",
    )
    assert result["exit_reason"] == "hard_stop"
    assert result["exit_fill"] < result["stop_price"]
    assert result["holding_days"] == 1
