from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
import sys

import numpy as np
import pandas as pd


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts"
)
sys.path.insert(0, str(SCRIPTS))

from as6s_live_safe_router import (  # noqa: E402
    choose_entry_candidate,
    grouped_entry_events,
    nonpreemptive,
    preemptive,
)
from combine_hybrid_asset_specific_account import UnifiedTrade  # noqa: E402


UTC = "UTC"


def trade(
    sleeve: str,
    symbol: str,
    entry: str,
    exit_: str,
    *,
    strength: float = 0.8,
    mechanism: str = "breakout",
) -> UnifiedTrade:
    return UnifiedTrade(
        sleeve=sleeve,
        symbol=symbol,
        mechanism=mechanism,
        source_timeframe="15m",
        side=1,
        entry_ts=pd.Timestamp(entry, tz=UTC),
        exit_ts=pd.Timestamp(exit_, tz=UTC),
        entry_price=100.0,
        net_return_1x=0.01,
        mae_return_1x=-0.01,
        raw_strength=0.5,
        strength=strength,
        exposure=1.0,
        exit_reason="take_profit",
    )


def test_entry_choice_is_invariant_to_future_exit_timestamp() -> None:
    first = trade("a_sleeve", "ETHUSDT", "2026-01-01 00:00", "2026-01-02 00:00")
    second = trade("b_sleeve", "SOLUSDT", "2026-01-01 00:00", "2026-01-01 01:00")
    assert choose_entry_candidate([second, first]).sleeve == "a_sleeve"

    swapped_first = replace(first, exit_ts=second.exit_ts)
    swapped_second = replace(second, exit_ts=first.exit_ts)
    assert choose_entry_candidate([swapped_second, swapped_first]).sleeve == "a_sleeve"


def test_entry_ordering_code_cannot_read_post_entry_fields() -> None:
    source = inspect.getsource(choose_entry_candidate) + inspect.getsource(
        grouped_entry_events
    )
    for forbidden in ("exit_ts", "exit_reason", "net_return_1x", "mae_return_1x"):
        assert forbidden not in source


def test_nonpreemptive_ledger_is_invariant_to_blocked_candidate_exit() -> None:
    accepted = trade(
        "a_sleeve", "ETHUSDT", "2026-01-01 00:00", "2026-01-01 04:00"
    )
    blocked = trade(
        "b_sleeve", "SOLUSDT", "2026-01-01 00:00", "2026-01-01 01:00"
    )
    start = pd.Timestamp("2025-12-31", tz=UTC)
    end = pd.Timestamp("2026-01-03", tz=UTC)
    first = nonpreemptive([blocked, accepted], start=start, end=end)

    changed_blocked = replace(
        blocked, exit_ts=pd.Timestamp("2026-01-02 12:00", tz=UTC)
    )
    second = nonpreemptive([changed_blocked, accepted], start=start, end=end)
    assert [row.sleeve for row in first] == ["a_sleeve"]
    assert [row.sleeve for row in second] == ["a_sleeve"]


def test_preemptive_challenger_choice_ignores_future_exit() -> None:
    current = trade(
        "current",
        "HYPEUSDT",
        "2026-01-01 00:00",
        "2026-01-02 00:00",
        strength=0.5,
        mechanism="clean_rsi_reversal",
    )
    first = trade(
        "a_breakout", "ETHUSDT", "2026-01-01 01:00", "2026-01-01 10:00"
    )
    second = trade(
        "b_breakout", "SOLUSDT", "2026-01-01 01:00", "2026-01-01 02:00"
    )
    bars = {
        "HYPEUSDT": pd.DataFrame(
            {
                "ts": [pd.Timestamp("2026-01-01 01:00", tz=UTC)],
                "open": [101.0],
                "high": [101.0],
                "low": [101.0],
            }
        )
    }
    funding = {"HYPEUSDT": (np.array([], dtype=np.int64), np.array([0.0]))}
    kwargs = {
        "start": pd.Timestamp("2025-12-31", tz=UTC),
        "end": pd.Timestamp("2026-01-03", tz=UTC),
        "threshold": 0.75,
        "margin": 0.05,
        "min_hold_hours": 1,
        "bars": bars,
        "funding": funding,
        "slippage": 0.0004,
    }
    before = preemptive([current, second, first], **kwargs)

    swapped_first = replace(first, exit_ts=second.exit_ts)
    swapped_second = replace(second, exit_ts=first.exit_ts)
    after = preemptive([current, swapped_second, swapped_first], **kwargs)
    assert [row.sleeve for row in before] == ["current", "a_breakout"]
    assert [row.sleeve for row in after] == ["current", "a_breakout"]
