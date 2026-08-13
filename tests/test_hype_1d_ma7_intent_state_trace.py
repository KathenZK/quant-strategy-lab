from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pandas as pd


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "research/hype/1d-ma7-asymmetric-body-trend/scripts"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ENGINE = load_module(
    SCRIPT_DIR / "hype_1d_ma7_intent_search_engine.py",
    "hype_1d_ma7_trace_test_engine",
)
TRACE = load_module(
    SCRIPT_DIR / "hype_1d_ma7_intent_state_trace.py",
    "hype_1d_ma7_intent_state_trace",
)


class FakeHarness:
    def __init__(self) -> None:
        self.observation_calls: list[tuple[int, bool]] = []

    def _first_valid_index(self, data) -> int:
        columns = ["ma7", "atr7", "rsi6", "slope_atr"]
        valid = np.isfinite(data.daily[columns].to_numpy()).all(axis=1)
        return int(np.flatnonzero(valid)[0])

    def _observation(self, engine, data, index: int, *, prime: bool = False):
        self.observation_calls.append((index, prime))
        row = data.daily.iloc[index]
        slope = float(row["slope_atr"])
        if prime and not np.isfinite(slope):
            slope = 0.0
        return engine.CloseObservation(
            ts=pd.Timestamp(data.daily.index[index]),
            close=float(row["close"]),
            ma7=float(row["ma7"]),
            atr7=float(row["atr7"]),
            slope_atr=slope,
            rsi6=float(row["rsi6"]),
        )


def make_data(
    closes: list[float],
    slopes: list[float],
    rsis: list[float],
    *,
    opens: list[float] | None = None,
):
    count = len(closes)
    assert len(slopes) == len(rsis) == count
    index = pd.date_range("2026-01-01", periods=count, freq="1D", tz="UTC")
    daily = pd.DataFrame(
        {
            "close": closes,
            "ma7": [100.0] * count,
            "atr7": [10.0] * count,
            "slope_atr": slopes,
            "rsi6": rsis,
        },
        index=index,
    )
    open_values = np.asarray(opens if opens is not None else closes, dtype=float)
    book = SimpleNamespace(
        count=count,
        open=open_values,
        ts=index,
        terminal_ts=index[-1] + pd.Timedelta(days=1),
        quality={"terminal_open": float(open_values[-1] + 1.0)},
    )
    return SimpleNamespace(daily=daily, book=book)


def config(**overrides):
    values = {
        "prior_side_days": 1,
        "session_open_hour": 0,
        "tolerance_atr": 0.75,
        "slope_min_atr": 0.02,
        "slope_lookback": 1,
        "entry_slope_required": True,
        "slope_loss_confirm_days": 2,
        "arm_expiry_days": 2,
        "max_chase_atr": 0.75,
        "flat_entry_mode": ENGINE.FlatEntryMode.FRESH_CROSS,
        "direct_reversal_enabled": True,
        "hold_slope_exit_enabled": False,
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


def test_replay_matches_no_delay_open_fills_and_traces_arm_counter_state() -> None:
    data = make_data(
        [99.0, 101.0, 102.0, 101.0, 99.0, 92.0, 95.0, 96.0],
        [-0.1, 0.0, 0.1, 0.1, -0.1, -0.1, -0.1, -0.1],
        [50.0] * 8,
        opens=[99.0, 100.0, 101.0, 103.0, 100.0, 93.0, 91.0, 96.0],
    )
    harness = FakeHarness()
    result = TRACE.replay_state_trace(
        ENGINE,
        harness,
        data,
        config(),
        start_index=1,
        terminal_index=7,
    )

    assert result["prime_history_indices"] == [0]
    assert harness.observation_calls[0] == (0, True)
    rows = {row["index"]: row for row in result["rows"]}
    assert rows[1]["armed_side"] == 1
    assert rows[2]["pending_reason"] == "flat_armed_slope_confirm_long"
    assert rows[2]["side"] == 0
    assert rows[3]["open_fill_target_side"] == 1
    assert rows[3]["side"] == 1
    assert rows[4]["armed_side"] == -1
    assert rows[4]["slope_loss_run"] == 1
    assert rows[5]["pending_reason"] == "held_arm_band_confirm_short"
    assert rows[6]["open_fill_fills"] == 2
    assert rows[6]["side"] == -1

    counts = result["activation_counts"]
    assert counts["arm_create"] == 2
    assert counts["arm_confirm"] == 2
    assert counts["decision_fill_events"] == 2
    assert counts["decision_fills"] == 3
    assert counts["slope_loss_day"] == 2
    assert counts["slope_loss_threshold"] == 1
    assert counts["terminal_flatten"] == 1


def test_arm_touch_cancel_is_recorded_without_reimplementing_a_decision() -> None:
    data = make_data(
        [99.0, 101.0, 100.0, 101.0],
        [-0.1, 0.0, 0.1, 0.1],
        [50.0] * 4,
    )
    result = TRACE.replay_state_trace(
        ENGINE,
        FakeHarness(),
        data,
        config(),
        start_index=1,
        terminal_index=3,
    )

    assert result["rows"][0]["armed_side"] == 1
    assert result["rows"][1]["relation"] == 0
    assert result["rows"][1]["armed_side"] == 0
    assert result["activation_counts"]["arm_create"] == 1
    assert result["activation_counts"]["arm_cancel"] == 1


def test_short_counter_and_terminal_pending_suppression_are_explicit() -> None:
    data = make_data(
        [101.0, 99.0, 95.0, 94.0, 93.0],
        [0.1, -0.1, -0.1, -0.1, -0.1],
        [50.0, 50.0, 20.0, 20.0, 20.0],
        opens=[101.0, 100.0, 100.0, 95.0, 94.0],
    )
    result = TRACE.replay_state_trace(
        ENGINE,
        FakeHarness(),
        data,
        config(
            short_rsi_exit_enabled=True,
            short_rsi_exit_days=2,
        ),
        start_index=0,
        terminal_index=4,
    )

    assert result["rows"][2]["short_rsi_run"] == 1
    assert result["rows"][3]["short_rsi_run"] == 2
    assert result["rows"][3]["pending_reason"] == "short_rsi_take_profit"
    assert result["activation_counts"]["short_rsi_day"] == 2
    assert result["activation_counts"]["short_rsi_threshold"] == 1
    assert result["activation_counts"]["terminal_pending_suppressed"] == 1
    assert result["activation_counts"]["decision_fill_events"] == 1
    assert result["terminal"]["pending_suppressed"] is True
    assert result["terminal"]["pending"]["reason"] == "short_rsi_take_profit"
    assert result["terminal"]["state_before"]["side"] == -1
    assert result["terminal"]["state_after"]["side"] == 0


def test_trace_is_invariant_to_data_strictly_after_terminal_boundary() -> None:
    baseline = make_data(
        [101.0, 99.0, 95.0, 94.0, 93.0, 92.0],
        [0.1, -0.1, -0.1, -0.1, -0.1, -0.1],
        [50.0, 50.0, 20.0, 20.0, 20.0, 20.0],
        opens=[101.0, 100.0, 100.0, 95.0, 94.0, 93.0],
    )
    changed = make_data(
        [101.0, 99.0, 95.0, 94.0, 93.0, 999.0],
        [0.1, -0.1, -0.1, -0.1, -0.1, 999.0],
        [50.0, 50.0, 20.0, 20.0, 20.0, 99.0],
        opens=[101.0, 100.0, 100.0, 95.0, 94.0, 999.0],
    )
    replay_config = config(short_rsi_exit_enabled=True, short_rsi_exit_days=2)

    left = TRACE.replay_state_trace(
        ENGINE, FakeHarness(), baseline, replay_config, 0, 4
    )
    right = TRACE.replay_state_trace(
        ENGINE, FakeHarness(), changed, replay_config, 0, 4
    )
    assert left == right


def test_trade_signature_diff_ignores_ids_and_labels_but_keeps_multiplicity() -> None:
    common = {
        "entry_ts": pd.Timestamp("2026-01-02", tz="UTC"),
        "exit_ts": "2026-01-04T00:00:00+00:00",
        "side": "long",
        "entry_price": np.float64(101.0),
        "exit_price": 104.0,
        "meta": {"label": "ignored-nested", "reason": "cross"},
    }
    anchor = [
        {"trade_id": "ANCHOR-001", "label": "ANCHOR", **common},
        {"trade_id": "ANCHOR-002", "label": "ANCHOR", **common},
    ]
    changed_trade = {**common, "exit_price": 105.0}
    variant = [
        {"trade_id": "VARIANT-901", "label": "VARIANT", **common},
        {"trade_id": "VARIANT-902", "label": "VARIANT", **changed_trade},
    ]

    signatures = TRACE.trade_signatures(anchor)
    assert signatures[0] == signatures[1]
    assert "trade_id" not in signatures[0]
    assert "label" not in signatures[0]
    assert "label" not in signatures[0]["meta"]

    difference = TRACE.diff_trade_signatures(anchor, variant)
    assert len(difference["removed"]) == 1
    assert difference["removed"][0]["exit_price"] == 104.0
    assert len(difference["added"]) == 1
    assert difference["added"][0]["exit_price"] == 105.0
