from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from as6s_engine import BASE_SLIPPAGE, REUSED_END, SYMBOLS, funding_arrays, load_funding, load_symbol_frame
from combine_hybrid_asset_specific_account import (
    UnifiedTrade,
    nonpreemptive as legacy_nonpreemptive,
    partial_close,
    preemptive as legacy_preemptive,
    is_breakout,
)
import research_binance_as6s_asset_first_v3 as v3


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
CANDIDATE_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
)
OUTPUT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v3_future_tiebreak_audit_2026-07-14.json"
)


def grouped_live_safe(
    items: Iterable[UnifiedTrade],
) -> list[tuple[pd.Timestamp, list[UnifiedTrade]]]:
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


def choose_live_safe(candidates: Iterable[UnifiedTrade]) -> UnifiedTrade:
    return min(
        candidates,
        key=lambda trade: (
            -trade.strength,
            trade.sleeve,
            trade.symbol,
            -trade.side,
        ),
    )


def nonpreemptive_live_safe(
    items: list[UnifiedTrade], *, start: pd.Timestamp, end: pd.Timestamp
) -> list[UnifiedTrade]:
    chosen: list[UnifiedTrade] = []
    blocked_until: pd.Timestamp | None = None
    sleeve_cooldown: dict[str, pd.Timestamp] = {}
    for timestamp, candidates in grouped_live_safe(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade
            for trade in candidates
            if trade.exit_ts < end
            and timestamp
            > sleeve_cooldown.get(trade.sleeve, start - pd.Timedelta(hours=1))
        ]
        if not candidates or (blocked_until is not None and timestamp <= blocked_until):
            continue
        trade = choose_live_safe(candidates)
        chosen.append(trade)
        blocked_until = trade.exit_ts
        sleeve_cooldown[trade.sleeve] = trade.exit_ts + pd.Timedelta(
            hours=trade.cooldown_hours
        )
    return chosen


def preemptive_live_safe(
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
    for timestamp, candidates in grouped_live_safe(items):
        if timestamp < start or timestamp >= end:
            continue
        candidates = [
            trade
            for trade in candidates
            if trade.exit_ts < end
            and timestamp
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
            current = choose_live_safe(candidates)
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
        challenger = choose_live_safe(challengers)
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
    if current is not None and current.exit_ts < end:
        chosen.append(current)
    return chosen


def trade_key(trade: UnifiedTrade) -> tuple[str, str, str, int, str]:
    return (
        trade.sleeve,
        trade.entry_ts.isoformat(),
        trade.exit_ts.isoformat(),
        trade.side,
        trade.exit_reason,
    )


def tie_inventory(items: list[UnifiedTrade]) -> dict[str, Any]:
    simultaneous = 0
    top_strength_ties = 0
    future_exit_ties = 0
    examples: list[dict[str, Any]] = []
    for timestamp, candidates in grouped_live_safe(items):
        if len(candidates) < 2:
            continue
        simultaneous += 1
        max_strength = max(trade.strength for trade in candidates)
        tied = [
            trade
            for trade in candidates
            if abs(trade.strength - max_strength) <= 1e-12
        ]
        if len(tied) < 2:
            continue
        top_strength_ties += 1
        if len({trade.exit_ts for trade in tied}) > 1:
            future_exit_ties += 1
        if len(examples) < 20:
            old = max(tied, key=lambda trade: (trade.strength, -trade.exit_ts.value))
            safe = choose_live_safe(tied)
            examples.append(
                {
                    "entry_ts": timestamp.isoformat(),
                    "old_choice": old.sleeve,
                    "live_safe_choice": safe.sleeve,
                    "choice_changed": old.sleeve != safe.sleeve,
                    "candidates": [
                        {
                            "sleeve": trade.sleeve,
                            "strength": trade.strength,
                            "exit_ts": trade.exit_ts.isoformat(),
                        }
                        for trade in tied
                    ],
                }
            )
    return {
        "simultaneous_entry_groups": simultaneous,
        "top_strength_tie_groups": top_strength_ties,
        "top_ties_with_different_future_exit": future_exit_ties,
        "examples": examples,
    }


def compare_routes(
    old: list[UnifiedTrade], safe: list[UnifiedTrade], scale: float
) -> dict[str, Any]:
    old_keys = [trade_key(trade) for trade in old]
    safe_keys = [trade_key(trade) for trade in safe]
    old_set = set(old_keys)
    safe_set = set(safe_keys)
    first_diff = next(
        (
            index
            for index, pair in enumerate(itertools.zip_longest(old_keys, safe_keys))
            if pair[0] != pair[1]
        ),
        None,
    )
    return {
        "old_metrics": v3.metric_with_frequency(
            old, v3.RESEARCH_START, REUSED_END, scale
        ),
        "live_safe_metrics": v3.metric_with_frequency(
            safe, v3.RESEARCH_START, REUSED_END, scale
        ),
        "old_trade_count": len(old),
        "live_safe_trade_count": len(safe),
        "common_trade_keys": len(old_set & safe_set),
        "old_only_trade_keys": len(old_set - safe_set),
        "live_safe_only_trade_keys": len(safe_set - old_set),
        "first_ordered_difference_index": first_diff,
        "identical_ordered_trade_ledger": old_keys == safe_keys,
    }


def main() -> None:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding_frames = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding = {symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()}

    legacy, legacy_audit = v3.legacy_universe()
    frontier, frontier_audit = v3.frontier_universe(frames, funding_frames)
    clean, clean_audit = v3.clean_rsi_universe(frames, funding_frames)
    universe = {**legacy, **frontier, **clean}
    audit = {**legacy_audit, **frontier_audit, **clean_audit}
    universe = v3.normalize_strengths(universe, audit)

    selected = tuple(candidate["selected_sleeves"])
    if any(sleeve not in universe for sleeve in selected):
        raise RuntimeError("selected V3 sleeve is missing from reconstructed universe")

    result: dict[str, Any] = {
        "family": candidate["family"],
        "audit": "V3 exit_ts arbitration future-information audit",
        "finding": (
            "FAIL if any routing function uses exit_ts to choose among entry-time candidates, "
            "regardless of whether the historical ledger changes"
        ),
        "selected_sleeves": list(selected),
        "scenarios": {},
    }
    route_params = candidate["comparisons"]
    for scenario, slippage in (
        ("base", BASE_SLIPPAGE),
        ("stress_8bps", 0.0008),
        ("k_plus_2", BASE_SLIPPAGE),
    ):
        items = [trade for sleeve in selected for trade in universe[sleeve][scenario]]
        old_non = legacy_nonpreemptive(
            items, start=v3.RESEARCH_START, end=REUSED_END
        )
        safe_non = nonpreemptive_live_safe(
            items, start=v3.RESEARCH_START, end=REUSED_END
        )
        preempt_params = route_params["strong_breakout_preemptive"]["frozen_params"]
        old_pre = legacy_preemptive(
            items,
            start=v3.RESEARCH_START,
            end=REUSED_END,
            threshold=preempt_params["threshold"],
            margin=preempt_params["margin"],
            min_hold_hours=preempt_params["min_hold_hours"],
            bars=frames,
            funding=funding,
            slippage=slippage,
        )
        safe_pre = preemptive_live_safe(
            items,
            start=v3.RESEARCH_START,
            end=REUSED_END,
            threshold=preempt_params["threshold"],
            margin=preempt_params["margin"],
            min_hold_hours=preempt_params["min_hold_hours"],
            bars=frames,
            funding=funding,
            slippage=slippage,
        )
        old_expected_non = route_params["nonpreemptive"]["scenarios"][scenario]["full"]
        old_expected_pre = route_params["strong_breakout_preemptive"]["scenarios"][scenario][
            "full"
        ]
        old_non_metrics = v3.metric_with_frequency(
            old_non,
            v3.RESEARCH_START,
            REUSED_END,
            route_params["nonpreemptive"]["frozen_params"]["account_scale"],
        )
        old_pre_metrics = v3.metric_with_frequency(
            old_pre,
            v3.RESEARCH_START,
            REUSED_END,
            preempt_params["account_scale"],
        )
        for label, observed, expected in (
            ("nonpreemptive", old_non_metrics, old_expected_non),
            ("preemptive", old_pre_metrics, old_expected_pre),
        ):
            if observed["trades"] != expected["trades"] or abs(
                observed["total_return"] - expected["total_return"]
            ) > 1e-10:
                raise RuntimeError(f"{scenario} {label} failed frozen V3 reconstruction")

        result["scenarios"][scenario] = {
            "tie_inventory": tie_inventory(items),
            "nonpreemptive": compare_routes(
                old_non,
                safe_non,
                route_params["nonpreemptive"]["frozen_params"]["account_scale"],
            ),
            "strong_breakout_preemptive": compare_routes(
                old_pre,
                safe_pre,
                preempt_params["account_scale"],
            ),
        }

    result["conclusion"] = {
        "future_information_present": True,
        "historical_ledger_changed": any(
            not route["identical_ordered_trade_ledger"]
            for scenario in result["scenarios"].values()
            for route in (
                scenario["nonpreemptive"],
                scenario["strong_breakout_preemptive"],
            )
        ),
        "v3_live_executable_gate": "FAIL",
        "required_action": (
            "Do not mutate frozen V3. Create a new observation whose arbitration tie-break "
            "uses only entry-time-known fields and freeze a new one-shot future OOS reveal."
        ),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH)
    print(json.dumps(result["conclusion"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
