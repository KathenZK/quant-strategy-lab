from __future__ import annotations

import itertools
from typing import Iterable

import numpy as np
import pandas as pd

from as6s_engine import FEE_PER_FILL, adverse_fill, funding_return
from combine_hybrid_asset_specific_account import UnifiedTrade


def grouped_entry_events(
    items: Iterable[UnifiedTrade],
) -> list[tuple[pd.Timestamp, list[UnifiedTrade]]]:
    """Group candidates without consulting any post-entry field."""
    ordered = sorted(
        items,
        key=lambda trade: (
            trade.entry_ts,
            -trade.strength,
            trade.sleeve,
            trade.symbol,
            -trade.side,
        ),
    )
    return [
        (timestamp, list(rows))
        for timestamp, rows in itertools.groupby(ordered, key=lambda trade: trade.entry_ts)
    ]


def choose_entry_candidate(candidates: Iterable[UnifiedTrade]) -> UnifiedTrade:
    """Choose using only values available when the entry order is decided."""
    return min(
        candidates,
        key=lambda trade: (
            -trade.strength,
            trade.sleeve,
            trade.symbol,
            -trade.side,
        ),
    )


def is_breakout(trade: UnifiedTrade) -> bool:
    return trade.mechanism in {
        "breakout",
        "donchian_break",
        "keltner_break",
        "bb_break",
    }


def nonpreemptive(
    items: list[UnifiedTrade], *, start: pd.Timestamp, end: pd.Timestamp
) -> list[UnifiedTrade]:
    """Replay an account lock; exit timestamps only advance held-position state."""
    chosen: list[UnifiedTrade] = []
    blocked_until: pd.Timestamp | None = None
    sleeve_cooldown: dict[str, pd.Timestamp] = {}
    for timestamp, candidates in grouped_entry_events(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade
            for trade in candidates
            if timestamp
            > sleeve_cooldown.get(trade.sleeve, start - pd.Timedelta(hours=1))
        ]
        if not candidates or (blocked_until is not None and timestamp <= blocked_until):
            continue
        trade = choose_entry_candidate(candidates)
        chosen.append(trade)
        # In a live Driver this transition is emitted by the eventual exit event.
        # The historical replay already has that event timestamp on the trade path.
        blocked_until = trade.exit_ts
        sleeve_cooldown[trade.sleeve] = trade.exit_ts + pd.Timedelta(
            hours=trade.cooldown_hours
        )
    return chosen


def partial_close(
    trade: UnifiedTrade,
    exit_ts: pd.Timestamp,
    *,
    bars: dict[str, pd.DataFrame],
    funding: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> UnifiedTrade:
    frame = bars[trade.symbol]
    matching = frame.loc[frame["ts"] == exit_ts, "open"]
    if matching.empty:
        raise RuntimeError(f"missing {trade.symbol} preemption open at {exit_ts}")
    exit_open = float(matching.iloc[0])
    exit_fill = adverse_fill(exit_open, trade.side, entry=False, slippage=slippage)
    price_return = trade.side * (exit_fill / trade.entry_price - 1.0)
    times, prefix = funding[trade.symbol]
    funding_ret = funding_return(trade.side, trade.entry_ts, exit_ts, times, prefix)
    segment = frame.loc[(frame["ts"] >= trade.entry_ts) & (frame["ts"] < exit_ts)]
    if segment.empty:
        adverse = price_return
    elif trade.side > 0:
        adverse = float(segment["low"].min() / trade.entry_price - 1.0)
    else:
        adverse = float(1.0 - segment["high"].max() / trade.entry_price)
    net = float(price_return + funding_ret - 2.0 * FEE_PER_FILL)
    return UnifiedTrade(
        sleeve=trade.sleeve,
        symbol=trade.symbol,
        mechanism=trade.mechanism,
        source_timeframe=trade.source_timeframe,
        side=trade.side,
        entry_ts=trade.entry_ts,
        exit_ts=exit_ts,
        entry_price=trade.entry_price,
        net_return_1x=net,
        mae_return_1x=min(adverse - 2.0 * FEE_PER_FILL, net),
        raw_strength=trade.raw_strength,
        cooldown_hours=trade.cooldown_hours,
        strength=trade.strength,
        exposure=trade.exposure,
        exit_reason="strong_breakout_preemption",
    )


def preemptive(
    items: list[UnifiedTrade],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    threshold: float,
    margin: float,
    min_hold_hours: int,
    bars: dict[str, pd.DataFrame],
    funding: dict[str, tuple[np.ndarray, np.ndarray]],
    slippage: float,
) -> list[UnifiedTrade]:
    chosen: list[UnifiedTrade] = []
    current: UnifiedTrade | None = None
    sleeve_cooldown: dict[str, pd.Timestamp] = {}
    min_hold = pd.Timedelta(hours=min_hold_hours)
    for timestamp, candidates in grouped_entry_events(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade
            for trade in candidates
            if timestamp
            > sleeve_cooldown.get(trade.sleeve, start - pd.Timedelta(hours=1))
        ]
        if not candidates:
            continue
        if current is not None and current.exit_ts <= timestamp:
            ended_on_candidate_bar = current.exit_ts == timestamp
            chosen.append(current)
            sleeve_cooldown[current.sleeve] = current.exit_ts + pd.Timedelta(
                hours=current.cooldown_hours
            )
            current = None
            if ended_on_candidate_bar:
                continue
        if current is None:
            current = choose_entry_candidate(candidates)
            continue
        challengers = [
            trade
            for trade in candidates
            if trade.symbol != current.symbol
            and is_breakout(trade)
            and trade.strength >= threshold
            and trade.strength >= current.strength + margin
            and timestamp >= current.entry_ts + min_hold
        ]
        if not challengers:
            continue
        challenger = choose_entry_candidate(challengers)
        chosen.append(
            partial_close(
                current,
                timestamp,
                bars=bars,
                funding=funding,
                slippage=slippage,
            )
        )
        sleeve_cooldown[current.sleeve] = timestamp + pd.Timedelta(
            hours=current.cooldown_hours
        )
        current = challenger
    if current is not None:
        chosen.append(current)
    return chosen
