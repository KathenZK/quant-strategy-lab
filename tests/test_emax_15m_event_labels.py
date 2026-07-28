"""Unit tests for the BIN-15M-EMAX-LGBM label kernel (frozen fill rules)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "research/asset-portfolios/15m-ema-cross-lightgbm-event-selector/scripts"
)
sys.path.insert(0, str(SCRIPTS))

import emax_common as ec  # noqa: E402


def run_single(open_, high, low, side, entry_index, k_tp=2.0, k_sl=1.0, atr=1.0):
    open_ = np.asarray(open_, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    entry = np.array([entry_index])
    outcome = ec.label_bracket(
        open_, high, low, entry, side,
        entry_price=np.array([open_[entry_index]]),
        atr=np.array([atr]), k_tp=k_tp, k_sl=k_sl,
    )
    return (
        int(outcome.label[0]),
        int(outcome.exit_index[0]),
        float(outcome.exit_price[0]),
    )


def flat_bars(n, price=100.0):
    open_ = np.full(n, price)
    high = np.full(n, price + 0.1)
    low = np.full(n, price - 0.1)
    return open_, high, low


def test_long_tp_at_barrier():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    high[3] = 102.5  # TP = 100 + 2*1 = 102
    label, exit_index, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 1
    assert exit_index == 3
    assert exit_price == pytest.approx(102.0)


def test_long_sl_at_barrier():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    low[4] = 98.5  # SL = 99
    label, exit_index, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 0
    assert exit_index == 4
    assert exit_price == pytest.approx(99.0)


def test_long_same_bar_both_is_sl():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    high[2] = 103.0
    low[2] = 98.0
    label, _, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 0
    assert exit_price == pytest.approx(99.0)


def test_long_gap_through_sl_fills_at_open():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    open_[3] = 97.0  # gaps far below SL=99
    low[3] = 96.5
    high[3] = 97.5
    label, exit_index, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 0
    assert exit_index == 3
    assert exit_price == pytest.approx(97.0)  # worse than barrier


def test_long_timeout_exits_next_open():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    label, exit_index, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 2
    assert exit_index == 1 + ec.HORIZON_BARS
    assert exit_price == pytest.approx(open_[1 + ec.HORIZON_BARS])


def test_short_mirror_tp():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    low[5] = 97.0  # short TP = 100 - 2 = 98
    label, exit_index, exit_price = run_single(open_, high, low, side=-1, entry_index=1)
    assert label == 1
    assert exit_index == 5
    assert exit_price == pytest.approx(98.0)


def test_short_gap_through_sl():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    open_[2] = 102.0  # short SL = 101, gap above
    high[2] = 102.5
    low[2] = 101.5
    label, exit_index, exit_price = run_single(open_, high, low, side=-1, entry_index=1)
    assert label == 0
    assert exit_index == 2
    assert exit_price == pytest.approx(102.0)


def test_entry_bar_intrabar_counts_but_open_does_not_gap():
    open_, high, low = flat_bars(ec.HORIZON_BARS + 5)
    # entry bar itself touches TP intrabar
    high[1] = 102.5
    label, exit_index, exit_price = run_single(open_, high, low, side=1, entry_index=1)
    assert label == 1
    assert exit_index == 1
    assert exit_price == pytest.approx(102.0)


def test_funding_cost_window():
    funding_ts = np.array(
        ["2025-01-01T00:00", "2025-01-01T08:00", "2025-01-01T16:00"],
        dtype="datetime64[ns]",
    )
    cum = np.concatenate([[0.0], np.cumsum([0.0001, 0.0002, -0.0001])])
    entry = np.array(["2025-01-01T00:30"], dtype="datetime64[ns]")
    exit_ = np.array(["2025-01-01T16:00"], dtype="datetime64[ns]")
    long_cost = ec.funding_cost(funding_ts, cum, entry, exit_, side=1)
    short_cost = ec.funding_cost(funding_ts, cum, entry, exit_, side=-1)
    assert long_cost[0] == pytest.approx(0.0001)  # 08:00 and 16:00 settlements
    assert short_cost[0] == pytest.approx(-0.0001)
