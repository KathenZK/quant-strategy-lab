from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts"
)
sys.path.insert(0, str(SCRIPTS))

from as6s_live_safe_router import nonpreemptive  # noqa: E402
from combine_hybrid_asset_specific_account import UnifiedTrade  # noqa: E402


UTC = "UTC"


def trade(sleeve: str, symbol: str, entry: str, exit_: str) -> UnifiedTrade:
    return UnifiedTrade(
        sleeve=sleeve,
        symbol=symbol,
        mechanism="breakout",
        source_timeframe="15m",
        side=1,
        entry_ts=pd.Timestamp(entry, tz=UTC),
        exit_ts=pd.Timestamp(exit_, tz=UTC),
        entry_price=100.0,
        net_return_1x=0.01,
        mae_return_1x=-0.01,
        raw_strength=0.5,
        strength=0.8,
        exposure=1.0,
        exit_reason="take_profit",
    )


def test_blocked_signal_does_not_create_virtual_sleeve_occupancy() -> None:
    current = trade(
        "current", "ETHUSDT", "2026-01-01 00:00", "2026-01-01 04:00"
    )
    blocked = trade(
        "later_sleeve", "SOLUSDT", "2026-01-01 01:00", "2026-01-02 12:00"
    )
    later = trade(
        "later_sleeve", "SOLUSDT", "2026-01-01 05:00", "2026-01-01 06:00"
    )
    rows = nonpreemptive(
        [current, blocked, later],
        start=pd.Timestamp("2025-12-31", tz=UTC),
        end=pd.Timestamp("2026-01-03", tz=UTC),
    )
    assert [(row.sleeve, row.entry_ts.hour) for row in rows] == [
        ("current", 0),
        ("later_sleeve", 5),
    ]


def test_only_accepted_trade_starts_explicit_sleeve_cooldown() -> None:
    first = replace(
        trade("sleeve", "ETHUSDT", "2026-01-01 00:00", "2026-01-01 02:00"),
        cooldown_hours=3,
    )
    blocked_by_cooldown = trade(
        "sleeve", "ETHUSDT", "2026-01-01 04:00", "2026-01-01 05:00"
    )
    available = trade(
        "sleeve", "ETHUSDT", "2026-01-01 06:00", "2026-01-01 07:00"
    )
    rows = nonpreemptive(
        [first, blocked_by_cooldown, available],
        start=pd.Timestamp("2025-12-31", tz=UTC),
        end=pd.Timestamp("2026-01-03", tz=UTC),
    )
    assert [row.entry_ts.hour for row in rows] == [0, 6]
