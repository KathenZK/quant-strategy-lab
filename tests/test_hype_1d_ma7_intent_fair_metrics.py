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
    "hype_ma7_intent_engine_fair_metrics_test",
    SCRIPT_DIR / "hype_1d_ma7_intent_search_engine.py",
)
HARNESS = load_module(
    "hype_ma7_intent_harness_fair_metrics_test",
    SCRIPT_DIR / "research_hype_1d_ma7_original_trend.py",
)
FAIR = load_module(
    "hype_ma7_intent_fair_metrics_test",
    SCRIPT_DIR / "hype_1d_ma7_intent_fair_metrics.py",
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
    funding_events: dict[int, list[SimpleNamespace]] | None = None,
):
    days = len(opens)
    index = pd.date_range("2026-01-01", periods=days, freq="1D", tz="UTC")
    open_values = np.asarray(opens, dtype=float)
    close_values = np.asarray(closes, dtype=float)
    high_values = np.maximum(open_values, close_values) + 1.0
    low_values = np.minimum(open_values, close_values) - 1.0
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
            "rsi6": np.full(days, 50.0),
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


def run(data, *, hard_stop_atr: float = 0.0):
    return HARNESS.backtest(
        ENGINE,
        data,
        config(hold_slope_exit_enabled=False),
        label="FAIR-METRICS",
        hard_stop_atr=hard_stop_atr,
        retain=True,
    )


def test_daily_extreme_mdd_differs_from_native_hourly_and_reconciles_ledger() -> None:
    data = market(
        opens=[99.0, 100.0, 100.0, 110.0, 111.0],
        closes=[99.0, 101.0, 110.0, 111.0, 112.0],
        slopes=[-0.1, 0.1, 0.1, 0.1, 0.1],
    )
    session = data.daily.index[2]
    data.features.funding_events[2] = [
        SimpleNamespace(
            ts=session + pd.Timedelta(hours=8),
            price=105.0,
            rate=0.0001,
        )
    ]
    data.features.hourly_open[2, 0] = 100.0
    data.features.hourly_high[2, 0] = 101.0
    data.features.hourly_low[2, 0] = 90.0
    data.features.hourly_open[2, 1] = 91.0
    data.features.hourly_high[2, 1] = 92.0
    data.features.hourly_low[2, 1] = 90.5
    data.features.hourly_open[2, 10] = 119.0
    data.features.hourly_high[2, 10] = 120.0
    data.features.hourly_low[2, 10] = 118.0
    data.book.high[2] = 120.0
    data.book.low[2] = 90.0
    result = run(data)

    fair = FAIR.v4_compatible_daily_extreme_mdd(
        result,
        data,
        HARNESS,
        start_index=0,
        terminal_index=data.book.count,
        slippage=HARNESS.BASE_SLIPPAGE,
    )

    assert fair["status"] == "PASS"
    assert fair["consistency"]["all_pass"] is True
    assert all(row["pass"] for row in fair["consistency"]["fields"].values())
    assert fair["ledger"]["final_side"] == 0
    assert fair["ledger"]["final_quantity"] == pytest.approx(0.0)
    assert fair["gate_mdd_pct"] < result.metrics["max_drawdown_pct"]
    assert fair["gate_mdd"] == fair["max_drawdown_pct"]

    drifted = SimpleNamespace(
        metrics={**result.metrics, "equity_multiple": result.metrics["equity_multiple"] + 1e-5},
        actions=result.actions,
        trades=result.trades,
        path=result.path,
    )
    with pytest.raises(RuntimeError, match="ledger parity failed"):
        FAIR.v4_compatible_daily_extreme_mdd(
            drifted,
            data,
            HARNESS,
            0,
            data.book.count,
            HARNESS.BASE_SLIPPAGE,
        )


def test_atomic_reversal_replays_as_close_then_open() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 90.0, 89.0],
        closes=[99.0, 101.0, 91.0, 89.0, 88.0],
        slopes=[-0.1, 0.1, -0.1, -0.1, -0.1],
    )
    result = run(data)
    fair = FAIR.v4_compatible_daily_extreme_mdd(
        result,
        data,
        HARNESS,
        0,
        data.book.count,
        HARNESS.BASE_SLIPPAGE,
    )

    assert fair["atomic_reversal_count"] == 1
    reversal = next(
        row["action"]
        for row in fair["audit_path"]
        if row.get("action") and row["action"]["fills"] == 2
    )
    assert [part["target_side"] for part in reversal["components"]] == [0, -1]
    assert sum(part["cost"] for part in reversal["components"]) > 0.0
    assert fair["consistency"]["fields"]["cost"]["pass"] is True


@pytest.mark.parametrize("field", ["bankrupt", "bankrupt_intraday"])
def test_raw_bankruptcy_is_rejected(field: str) -> None:
    result = SimpleNamespace(metrics={field: True, "equity_multiple": 1.0})
    with pytest.raises(RuntimeError, match="failed raw solvency"):
        FAIR.assert_candidate_solvency(result)


def test_gap_stop_audit_flags_same_timestamp_funding_and_exposure() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 103.0],
        closes=[99.0, 101.0, 103.0, 104.0],
        slopes=[-0.1, 0.1, 0.1, 0.1],
    )
    stop_ts = data.daily.index[2] + pd.Timedelta(hours=1)
    data.features.hourly_open[2, 1] = 80.0
    data.features.hourly_high[2, 1] = 200.0
    data.features.hourly_low[2, 1] = 70.0
    data.features.funding_events[2] = [
        SimpleNamespace(ts=stop_ts, price=80.0, rate=0.001)
    ]
    result = run(data, hard_stop_atr=1.5)

    audit = FAIR.audit_r1_gap_stops(result, data, 1.5)

    assert audit["status"] == "BLOCKED"
    assert audit["gap_stop_count"] == 1
    assert audit["gap_funding_same_timestamp_count"] == 1
    stopped = audit["stops"][0]
    assert stopped["theoretical_stop_level"] == pytest.approx(87.0)
    assert stopped["gap_at_hour_open"] is True
    assert stopped["actual_fill"] == pytest.approx(80.0)
    assert stopped["hour_ohlc"] == {"open": 80.0, "high": 200.0, "low": 70.0}
    assert len(stopped["funding_at_exit_ts"]) == 1
    assert stopped["funding_correction_applied"] is False
    assert audit["exposure"]["gap_open_correction_hours"] == -1.0
    assert audit["funding_correction_applied"] is False
    assert audit["terminal_flat"] is True


def test_intrahour_stop_audit_matches_level_without_gap_correction() -> None:
    data = market(
        opens=[99.0, 100.0, 102.0, 103.0],
        closes=[99.0, 101.0, 103.0, 104.0],
        slopes=[-0.1, 0.1, 0.1, 0.1],
    )
    data.features.hourly_open[2, 1] = 100.0
    data.features.hourly_high[2, 1] = 101.0
    data.features.hourly_low[2, 1] = 80.0
    result = run(data, hard_stop_atr=1.5)

    audit = FAIR.audit_r1_gap_stops(result, data, 1.5)

    assert audit["status"] == "PASS"
    assert audit["gap_stop_count"] == 0
    stopped = audit["stops"][0]
    assert stopped["gap_at_hour_open"] is False
    assert stopped["level_hit_in_hour"] is True
    assert stopped["expected_fill"] == pytest.approx(87.0)
    assert stopped["actual_fill"] == pytest.approx(87.0)
    assert stopped["fill_matches_model"] is True
    assert stopped["funding_at_exit_ts"] == []
    assert stopped["exposure_correction_hours"] == 0.0
    assert audit["max_adverse_return"] == pytest.approx(stopped["max_adverse_return"])
    assert audit["bankrupt"] is False
    assert audit["terminal_flat"] is True
