from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "research/mu/15m-donchian-trend-breakout/scripts/research_mu_15m_dtb.py"
)


def load_script() -> Any:
    spec = importlib.util.spec_from_file_location("mu_15m_dtb_test_module", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DTB = load_script()


def feature_frame(
    *,
    open_: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    funding: list[float] | None = None,
    entry_signal_bars: set[int] | None = None,
    exit_signal_bars: set[int] | None = None,
) -> pd.DataFrame:
    rows = len(open_)
    entry_signal_bars = entry_signal_bars or set()
    exit_signal_bars = exit_signal_bars or set()
    frame = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "funding_rate": funding or [0.0] * rows,
            "ema96": [2.0] * rows,
            "ema384": [1.0] * rows,
            "ema384_slope16": [0.01] * rows,
            "atr96": [1.0] * rows,
        }
    )
    for window in DTB.ENTRY_WINDOWS:
        frame[f"donchian_high_{window}"] = [
            close[index] - 1.0 if index in entry_signal_bars else close[index] + 1.0
            for index in range(rows)
        ]
        exit_window = window // 2
        frame[f"donchian_low_{exit_window}"] = [
            close[index] + 1.0 if index in exit_signal_bars else close[index] - 10.0
            for index in range(rows)
        ]
    return frame


def run_fixture(frame: pd.DataFrame) -> Any:
    return DTB.simulate(
        frame,
        DTB.StrategyConfig(
            entry_window=48,
            stop_atr=4.0,
            use_ema_regime=True,
        ),
        start=frame["ts"].iloc[0],
        end_exclusive=frame["ts"].iloc[-1] + DTB.BAR,
    )


def test_stop_wins_when_channel_exit_conflicts_same_bar() -> None:
    frame = feature_frame(
        open_=[100.0, 100.0, 100.0],
        high=[101.0, 103.0, 101.0],
        low=[99.0, 95.0, 99.0],
        close=[101.0, 98.0, 100.0],
        entry_signal_bars={0},
        exit_signal_bars={1},
    )
    result = run_fixture(frame)
    assert result.metrics["closed_trades"] == 1
    assert result.metrics["exit_stop_conflicts"] == 1
    assert result.trades.iloc[0]["exit_reason"] == "stop"


def test_gap_stop_uses_worse_open() -> None:
    frame = feature_frame(
        open_=[100.0, 100.0, 95.0],
        high=[101.0, 101.0, 96.0],
        low=[99.0, 99.0, 94.0],
        close=[101.0, 100.0, 95.0],
        entry_signal_bars={0},
    )
    result = run_fixture(frame)
    trade = result.trades.iloc[0]
    assert result.metrics["gap_stops"] == 1
    assert trade["exit_reason"] == "stop_gap"
    assert trade["exit_fill"] == 95.0 * (1.0 - DTB.SLIPPAGE_PER_FILL)


def test_exit_bar_does_not_rearm() -> None:
    frame = feature_frame(
        open_=[100.0, 100.0, 100.0, 100.0],
        high=[101.0, 103.0, 101.0, 101.0],
        low=[99.0, 95.0, 99.0, 99.0],
        close=[101.0, 102.0, 100.0, 100.0],
        entry_signal_bars={0, 1},
    )
    result = run_fixture(frame)
    assert result.metrics["closed_trades"] == 1
    assert result.metrics["open_position_at_end"] is False


def test_funding_reduces_carried_long_equity() -> None:
    plain = feature_frame(
        open_=[100.0, 100.0, 100.0],
        high=[101.0, 101.0, 101.0],
        low=[99.0, 99.0, 99.0],
        close=[101.0, 100.0, 100.0],
        entry_signal_bars={0},
    )
    funded = plain.copy()
    funded["funding_rate"] = [0.0, 0.0, 0.01]
    plain_result = run_fixture(plain)
    funded_result = run_fixture(funded)
    assert funded_result.metrics["return"] < plain_result.metrics["return"]


def test_candidate_evaluation_never_reads_final_window(monkeypatch: Any) -> None:
    calls: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def fake_simulate(
        features: pd.DataFrame,
        config: Any,
        *,
        start: pd.Timestamp,
        end_exclusive: pd.Timestamp,
        liquidate_at_end: bool = True,
    ) -> Any:
        del features, config, liquidate_at_end
        calls.append((start, end_exclusive))
        metrics = {
            "return": 0.1,
            "max_drawdown": -0.1,
            "closed_trades": 10,
            "win_rate": 0.6,
            "profit_factor": 1.5,
        }
        return DTB.SimulationResult(
            metrics=metrics,
            trades=pd.DataFrame(),
            equity=pd.DataFrame(),
        )

    monkeypatch.setattr(DTB, "simulate", fake_simulate)
    config = DTB.StrategyConfig(48, 3.0, True)
    DTB.evaluate_candidate(pd.DataFrame(), config)
    assert len(calls) == 4
    assert all(end <= DTB.FINAL_START for _, end in calls)
    assert all(start < DTB.FINAL_START for start, _ in calls)


def test_feature_builder_is_prefix_causal() -> None:
    rows = 700
    close = 100.0 + np.linspace(0.0, 30.0, rows) + np.sin(np.arange(rows) / 9.0)
    raw = pd.DataFrame(
        {
            "ts": pd.date_range("2026-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": np.r_[close[0], close[:-1]],
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "funding_rate": np.zeros(rows),
        }
    )
    full = DTB.build_features(raw)
    audit = DTB.prefix_causality_audit(raw, full)
    assert audit["pass"] is True
    assert audit["mismatch_count"] == 0
