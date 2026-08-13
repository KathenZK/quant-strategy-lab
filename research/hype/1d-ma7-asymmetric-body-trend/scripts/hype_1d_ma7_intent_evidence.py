"""Pure, label-free evidence helpers for the HYPE 1D MA7 intent search.

The functions in this module only transform already-produced trades, actions,
and state traces.  They do not load market data, run a backtest, write an
artifact, or use plotting-only path fields as behavioral evidence.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
from functools import lru_cache
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_IDENTITY_KEYS = frozenset(
    {
        "id",
        "label",
        "run_id",
        "run_label",
        "strategy_label",
        "trade_id",
        "trial_id",
    }
)

ACTIVATION_KEYS = (
    "fresh_cross_rooted_entries",
    "arm_create",
    "arm_confirm",
    "entry_slope_qualified_decisions",
    "held_band_confirms",
    "slope_loss_exits",
    "short_rsi_take_profit_exits",
    "overbought_qualified_decisions",
    "atomic_reversals",
)

# Each ablation must first prove that the removed mechanism activated in the
# frozen champion.  CHAMPION_FULL is the anchor and therefore has no removal
# activation requirement of its own.
CHAMPION_OAT_REQUIRED_ACTIVATION: dict[str, tuple[str, ...]] = {
    "CHAMPION_FULL": (),
    "CHAMPION_PERSISTENT_REGIME": ("fresh_cross_rooted_entries",),
    "CHAMPION_NO_ARMED": ("arm_create", "arm_confirm"),
    "CHAMPION_NO_ENTRY_SLOPE": ("entry_slope_qualified_decisions",),
    "CHAMPION_NO_SLOPE_LOSS": ("slope_loss_exits",),
    "CHAMPION_NO_BAND": ("held_band_confirms",),
    "CHAMPION_NO_RSI_TP": ("short_rsi_take_profit_exits",),
    "CHAMPION_NO_OVERBOUGHT": ("overbought_qualified_decisions",),
    "CHAMPION_NO_REVERSAL": ("atomic_reversals",),
}


def _json_value(value: Any) -> Any:
    """Return a deterministic JSON value while removing run identities."""

    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _IDENTITY_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "item") and type(value).__module__.startswith("numpy"):
        return _json_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported evidence value: {type(value).__name__}")


def _signature_key(signature: Mapping[str, Any]) -> str:
    return json.dumps(
        signature,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def trade_signatures(trades: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return ordered, JSON-friendly trades with all run identities removed."""

    signatures: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, Mapping):
            raise TypeError("each trade must be a mapping")
        signature = _json_value(trade)
        if not isinstance(signature, dict):
            raise TypeError("trade signature must be a mapping")
        signatures.append(signature)
    return signatures


def _ordered_multiset_difference(
    source: Sequence[dict[str, Any]], subtract: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    remaining = Counter(_signature_key(item) for item in source) - Counter(
        _signature_key(item) for item in subtract
    )
    output: list[dict[str, Any]] = []
    for item in source:
        key = _signature_key(item)
        if remaining[key] > 0:
            output.append(item)
            remaining[key] -= 1
    return output


def diff_trade_signatures(
    anchor: Iterable[Mapping[str, Any]], variant: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Return an order-preserving multiset diff, including duplicate trades."""

    anchor_signatures = trade_signatures(anchor)
    variant_signatures = trade_signatures(variant)
    anchor_counter = Counter(_signature_key(item) for item in anchor_signatures)
    variant_counter = Counter(_signature_key(item) for item in variant_signatures)
    unchanged = sum((anchor_counter & variant_counter).values())
    return {
        "anchor_signatures": anchor_signatures,
        "variant_signatures": variant_signatures,
        "added": _ordered_multiset_difference(
            variant_signatures, anchor_signatures
        ),
        "removed": _ordered_multiset_difference(
            anchor_signatures, variant_signatures
        ),
        "unchanged_count": int(unchanged),
    }


def _timestamp(value: Any, field: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"invalid {field}: {value!r}") from exc
    else:
        raise TypeError(f"{field} must be an ISO timestamp")
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _side(value: Any) -> int:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"long", "buy", "+1", "1"}:
            return 1
        if normalized in {"short", "sell", "-1"}:
            return -1
    if isinstance(value, (int, float)) and int(value) in (-1, 1):
        return int(value)
    raise ValueError(f"trade side must be long/short or +/-1, got {value!r}")


def _side_name(value: int) -> str:
    return "long" if value == 1 else "short"


@dataclass(frozen=True)
class _TradeView:
    original_index: int
    signature: dict[str, Any]
    side: int
    entry: datetime
    exit: datetime


def _trade_views(trades: Iterable[Mapping[str, Any]]) -> list[_TradeView]:
    views: list[_TradeView] = []
    for index, signature in enumerate(trade_signatures(trades)):
        entry = _timestamp(signature.get("entry_ts"), "entry_ts")
        exit_ts = _timestamp(signature.get("exit_ts"), "exit_ts")
        if exit_ts < entry:
            raise ValueError("trade exit_ts precedes entry_ts")
        views.append(
            _TradeView(
                original_index=index,
                signature=signature,
                side=_side(signature.get("side")),
                entry=entry,
                exit=exit_ts,
            )
        )
    return views


def _microseconds(seconds: float) -> int:
    return int(round(seconds * 1_000_000.0))


def _pair_score(left: _TradeView, right: _TradeView) -> tuple[int, int, int]:
    overlap = max(
        0.0,
        (min(left.exit, right.exit) - max(left.entry, right.entry)).total_seconds(),
    )
    entry_gap = abs((left.entry - right.entry).total_seconds())
    exit_gap = abs((left.exit - right.exit).total_seconds())
    return (
        _microseconds(overlap),
        -_microseconds(entry_gap),
        -_microseconds(exit_gap),
    )


def _chronological_side_pairs(
    left: Sequence[_TradeView], right: Sequence[_TradeView]
) -> list[tuple[int, int]]:
    """Maximum-overlap chronological one-to-one pairing for one direction."""

    ordered_left = sorted(left, key=lambda row: (row.entry, row.exit, row.original_index))
    ordered_right = sorted(
        right, key=lambda row: (row.entry, row.exit, row.original_index)
    )

    # The leading score component maximizes the number of matched trades, so
    # unmatched trades represent only a side-specific count imbalance.  Among
    # those complete matchings, overlap dominates nearest-entry and exit ties.
    @lru_cache(maxsize=None)
    def solve(
        left_index: int, right_index: int
    ) -> tuple[tuple[int, int, int, int], tuple[tuple[int, int], ...]]:
        if left_index == len(ordered_left) or right_index == len(ordered_right):
            return (0, 0, 0, 0), ()

        overlap, entry_score, exit_score = _pair_score(
            ordered_left[left_index], ordered_right[right_index]
        )
        tail_score, tail_pairs = solve(left_index + 1, right_index + 1)
        choices = [
            (
                (
                    tail_score[0] + 1,
                    tail_score[1] + overlap,
                    tail_score[2] + entry_score,
                    tail_score[3] + exit_score,
                ),
                ((left_index, right_index), *tail_pairs),
            ),
            solve(left_index + 1, right_index),
            solve(left_index, right_index + 1),
        ]
        # Fixed choice order resolves complete score ties toward the earliest
        # chronological pair, making duplicate trades deterministic.
        best = choices[0]
        for choice in choices[1:]:
            if choice[0] > best[0]:
                best = choice
        return best

    _, local_pairs = solve(0, 0)
    return [
        (
            ordered_left[left_index].original_index,
            ordered_right[right_index].original_index,
        )
        for left_index, right_index in local_pairs
    ]


def _matched_indices(
    left: Sequence[_TradeView], right: Sequence[_TradeView]
) -> tuple[list[tuple[int, int]], list[int], list[int]]:
    pairs: list[tuple[int, int]] = []
    for side in (1, -1):
        pairs.extend(
            _chronological_side_pairs(
                [row for row in left if row.side == side],
                [row for row in right if row.side == side],
            )
        )
    pairs.sort(key=lambda pair: (left[pair[0]].entry, pair[0], pair[1]))
    matched_left = {pair[0] for pair in pairs}
    matched_right = {pair[1] for pair in pairs}
    left_only = sorted(
        (index for index in range(len(left)) if index not in matched_left),
        key=lambda index: (left[index].entry, index),
    )
    right_only = sorted(
        (index for index in range(len(right)) if index not in matched_right),
        key=lambda index: (right[index].entry, index),
    )
    return pairs, left_only, right_only


def _reason(trade: Mapping[str, Any], field: str) -> str | None:
    value = trade.get(field)
    return None if value is None else str(value)


def _action_side(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number in (-1, 0, 1) else 0


def _action_timestamp(action: Mapping[str, Any]) -> datetime | None:
    value = action.get("ts")
    if value is None:
        return None
    try:
        return _timestamp(value, "action ts")
    except (TypeError, ValueError):
        return None


def _trade_classification(
    trade: _TradeView,
    all_trades: Sequence[_TradeView],
    actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    entry_reason = (_reason(trade.signature, "entry_reason") or "").lower()
    entry_source = (_reason(trade.signature, "entry_source") or "").lower()
    exit_reason = (_reason(trade.signature, "exit_reason") or "").lower()
    armed = "armed" in entry_reason or "held_arm" in entry_reason or "arm" in entry_source
    rsi_take_profit = "rsi" in exit_reason and "profit" in exit_reason
    slope_loss = "slope_loss" in exit_reason
    hard_stop = "hard_stop" in exit_reason

    atomic_entry = False
    atomic_exit = False
    for action in actions:
        action_ts = _action_timestamp(action)
        if action_ts is None:
            continue
        from_side = _action_side(action.get("from_side"))
        target_side = _action_side(action.get("target_side"))
        if from_side == 0 or target_side == 0:
            continue
        if action_ts == trade.entry and target_side == trade.side:
            atomic_entry = True
        if action_ts == trade.exit and from_side == trade.side:
            atomic_exit = True

    # Actions are preferred, but exact same-open adjacent legs provide a
    # deterministic inference for comparator ledgers that do not retain them.
    for other in all_trades:
        if other.original_index == trade.original_index or other.side == trade.side:
            continue
        if other.exit == trade.entry:
            atomic_entry = True
        if other.entry == trade.exit:
            atomic_exit = True

    if atomic_entry and atomic_exit:
        atomic_role = "entry_and_exit_leg"
    elif atomic_entry:
        atomic_role = "entry_leg"
    elif atomic_exit:
        atomic_role = "exit_leg"
    else:
        atomic_role = "none"

    if entry_reason.startswith("fresh_cross_"):
        entry_class = "fresh_cross"
    elif armed:
        entry_class = "armed_confirmation"
    elif entry_reason.startswith("persistent_regime_"):
        entry_class = "persistent_regime"
    else:
        entry_class = "other"

    if rsi_take_profit:
        exit_class = "rsi_take_profit"
    elif slope_loss:
        exit_class = "slope_loss"
    elif hard_stop:
        exit_class = "hard_stop"
    elif exit_reason == "terminal_flatten":
        exit_class = "terminal_flatten"
    elif atomic_exit:
        exit_class = "atomic_reversal"
    else:
        exit_class = "other"

    return {
        "entry_class": entry_class,
        "exit_class": exit_class,
        "armed_entry": armed,
        "rsi_take_profit_exit": rsi_take_profit,
        "slope_loss_exit": slope_loss,
        "hard_stop_exit": hard_stop,
        "overbought_qualified": "overbought" in entry_reason
        or "overbought" in exit_reason,
        "atomic_reversal": atomic_entry or atomic_exit,
        "atomic_reversal_role": atomic_role,
    }


def _timing(left: datetime, right: datetime, *, prefix: str) -> dict[str, Any]:
    delta_days = (left - right).total_seconds() / 86_400.0
    if delta_days < 0.0:
        relation = "earlier"
    elif delta_days > 0.0:
        relation = "later"
    else:
        relation = "same"
    return {
        f"{prefix}_days": delta_days,
        "relative": relation,
    }


def _unmatched_record(
    trade: _TradeView,
    all_trades: Sequence[_TradeView],
    actions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "trade": trade.signature,
        "classification": _trade_classification(trade, all_trades, actions),
    }


def candidate_v4_trade_attribution(
    candidate_trades: Iterable[Mapping[str, Any]],
    exact_v4_trades: Iterable[Mapping[str, Any]],
    *,
    candidate_actions: Iterable[Mapping[str, Any]] = (),
    exact_v4_actions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Attribute candidate trades to exact V4 without using trial labels.

    Matching is direction-specific, chronological, and one-to-one.  It first
    maximizes matched count, then total interval overlap, then nearest entry
    and exit timestamps.  The returned list is in candidate chronology.
    """

    candidate = _trade_views(candidate_trades)
    exact_v4 = _trade_views(exact_v4_trades)
    candidate_action_rows = list(candidate_actions)
    v4_action_rows = list(exact_v4_actions)
    pairs, candidate_only, v4_only = _matched_indices(candidate, exact_v4)
    matched: list[dict[str, Any]] = []
    for candidate_index, v4_index in pairs:
        candidate_trade = candidate[candidate_index]
        v4_trade = exact_v4[v4_index]
        overlap_days = max(
            0.0,
            (
                min(candidate_trade.exit, v4_trade.exit)
                - max(candidate_trade.entry, v4_trade.entry)
            ).total_seconds()
            / 86_400.0,
        )
        matched.append(
            {
                "side": _side_name(candidate_trade.side),
                "match_basis": (
                    "maximum_interval_overlap"
                    if overlap_days > 0.0
                    else "nearest_entry_fallback"
                ),
                "overlap_days": overlap_days,
                "candidate": candidate_trade.signature,
                "exact_v4": v4_trade.signature,
                "entry_timing": _timing(
                    candidate_trade.entry,
                    v4_trade.entry,
                    prefix="candidate_minus_v4",
                ),
                "exit_timing": _timing(
                    candidate_trade.exit,
                    v4_trade.exit,
                    prefix="candidate_minus_v4",
                ),
                "entry_reason": {
                    "candidate": _reason(candidate_trade.signature, "entry_reason"),
                    "exact_v4": _reason(v4_trade.signature, "entry_reason"),
                },
                "exit_reason": {
                    "candidate": _reason(candidate_trade.signature, "exit_reason"),
                    "exact_v4": _reason(v4_trade.signature, "exit_reason"),
                },
                "candidate_classification": _trade_classification(
                    candidate_trade, candidate, candidate_action_rows
                ),
                "exact_v4_classification": _trade_classification(
                    v4_trade, exact_v4, v4_action_rows
                ),
            }
        )

    entry_relations = Counter(row["entry_timing"]["relative"] for row in matched)
    exit_relations = Counter(row["exit_timing"]["relative"] for row in matched)
    return {
        "matching_contract": {
            "same_direction": True,
            "chronological_one_to_one": True,
            "priority": [
                "maximum_matched_count",
                "maximum_interval_overlap",
                "nearest_entry",
                "nearest_exit",
                "earliest_chronological_tie",
            ],
        },
        "matched": matched,
        "candidate_unmatched": [
            _unmatched_record(candidate[index], candidate, candidate_action_rows)
            for index in candidate_only
        ],
        "exact_v4_unmatched": [
            _unmatched_record(exact_v4[index], exact_v4, v4_action_rows)
            for index in v4_only
        ],
        "summary": {
            "candidate_trade_count": len(candidate),
            "exact_v4_trade_count": len(exact_v4),
            "matched_count": len(matched),
            "candidate_unmatched_count": len(candidate_only),
            "exact_v4_unmatched_count": len(v4_only),
            "candidate_entry_earlier_count": int(entry_relations["earlier"]),
            "candidate_entry_same_count": int(entry_relations["same"]),
            "candidate_entry_later_count": int(entry_relations["later"]),
            "candidate_exit_earlier_count": int(exit_relations["earlier"]),
            "candidate_exit_same_count": int(exit_relations["same"]),
            "candidate_exit_later_count": int(exit_relations["later"]),
            "candidate_armed_entry_count": sum(
                row["candidate_classification"]["armed_entry"] for row in matched
            ),
            "candidate_rsi_take_profit_count": sum(
                row["candidate_classification"]["rsi_take_profit_exit"]
                for row in matched
            ),
            "candidate_slope_loss_count": sum(
                row["candidate_classification"]["slope_loss_exit"]
                for row in matched
            ),
            "candidate_atomic_reversal_leg_count": sum(
                row["candidate_classification"]["atomic_reversal"]
                for row in matched
            ),
        },
    }


def r0_r1_trade_diff(
    r0_trades: Iterable[Mapping[str, Any]],
    r1_trades: Iterable[Mapping[str, Any]],
    *,
    r0_actions: Iterable[Mapping[str, Any]] = (),
    r1_actions: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Return a per-trade R0-versus-R1 hard-stop attribution summary."""

    r0 = _trade_views(r0_trades)
    r1 = _trade_views(r1_trades)
    r0_action_rows = list(r0_actions)
    r1_action_rows = list(r1_actions)
    pairs, r0_only, r1_only = _matched_indices(r0, r1)
    matched: list[dict[str, Any]] = []
    for r0_index, r1_index in pairs:
        r0_trade = r0[r0_index]
        r1_trade = r1[r1_index]
        r0_classification = _trade_classification(r0_trade, r0, r0_action_rows)
        r1_classification = _trade_classification(r1_trade, r1, r1_action_rows)
        matched.append(
            {
                "side": _side_name(r0_trade.side),
                "r0": r0_trade.signature,
                "r1": r1_trade.signature,
                "entry_timing": _timing(
                    r1_trade.entry, r0_trade.entry, prefix="r1_minus_r0"
                ),
                "exit_timing": _timing(
                    r1_trade.exit, r0_trade.exit, prefix="r1_minus_r0"
                ),
                "entry_reason": {
                    "r0": _reason(r0_trade.signature, "entry_reason"),
                    "r1": _reason(r1_trade.signature, "entry_reason"),
                },
                "exit_reason": {
                    "r0": _reason(r0_trade.signature, "exit_reason"),
                    "r1": _reason(r1_trade.signature, "exit_reason"),
                },
                "r0_classification": r0_classification,
                "r1_classification": r1_classification,
                "r1_hard_stop_changed_exit": bool(
                    r1_classification["hard_stop_exit"]
                    and not r0_classification["hard_stop_exit"]
                ),
            }
        )

    return {
        "matched": matched,
        "r0_unmatched": [
            _unmatched_record(r0[index], r0, r0_action_rows) for index in r0_only
        ],
        "r1_unmatched": [
            _unmatched_record(r1[index], r1, r1_action_rows) for index in r1_only
        ],
        "summary": {
            "r0_trade_count": len(r0),
            "r1_trade_count": len(r1),
            "matched_count": len(matched),
            "r0_unmatched_count": len(r0_only),
            "r1_unmatched_count": len(r1_only),
            "r1_hard_stop_exit_count": sum(
                row["r1_classification"]["hard_stop_exit"] for row in matched
            )
            + sum(
                _trade_classification(r1[index], r1, r1_action_rows)[
                    "hard_stop_exit"
                ]
                for index in r1_only
            ),
            "matched_hard_stop_changed_exit_count": sum(
                row["r1_hard_stop_changed_exit"] for row in matched
            ),
            "r1_earlier_exit_count": sum(
                row["exit_timing"]["relative"] == "earlier" for row in matched
            ),
            "r1_later_exit_count": sum(
                row["exit_timing"]["relative"] == "later" for row in matched
            ),
        },
    }


def _compact_decision(
    row: Mapping[str, Any], *, nested: bool = False
) -> dict[str, Any] | None:
    decision = row.get("decision") if nested else row
    if not isinstance(decision, Mapping):
        return None
    from_side = _action_side(decision.get("from_side"))
    target_side = _action_side(decision.get("target_side"))
    reason = decision.get("reason")
    if reason is None or (from_side == 0 and target_side == 0):
        return None
    signal_ts = decision.get("signal_ts", row.get("signal_ts"))
    ts = row.get("ts", decision.get("ts"))
    return {
        "ts": None if ts is None else str(ts),
        "signal_ts": None if signal_ts is None else str(signal_ts),
        "from_side": from_side,
        "target_side": target_side,
        "reason": str(reason),
        "fills": int(decision.get("fills", row.get("fills", 0)) or 0),
    }


def _decision_key(decision: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        decision.get("signal_ts"),
        decision.get("from_side"),
        decision.get("target_side"),
        decision.get("reason"),
    )


def _actual_decisions(
    actions: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for action in actions:
        decision = _compact_decision(action)
        if decision is not None:
            decisions.append(decision)
    if not decisions:
        for event in events:
            if event.get("event") != "decision_fill":
                continue
            decision = _compact_decision(event, nested=True)
            if decision is not None:
                decisions.append(decision)
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for decision in decisions:
        key = _decision_key(decision)
        if key not in seen:
            seen.add(key)
            unique.append(decision)
    return unique


def _event_evidence(event: Mapping[str, Any]) -> dict[str, Any]:
    evidence = {
        "event": str(event.get("event")),
        "ts": None if event.get("ts") is None else str(event.get("ts")),
        "index": (
            None if event.get("index") is None else int(event.get("index"))
        ),
    }
    if event.get("reason") is not None:
        evidence["reason"] = str(event.get("reason"))
    return evidence


def _decision_evidence(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "ts": decision.get("ts"),
        "signal_ts": decision.get("signal_ts"),
        "from_side": int(decision["from_side"]),
        "target_side": int(decision["target_side"]),
        "reason": str(decision["reason"]),
        "fills": int(decision["fills"]),
    }


def _applicable_champion_oat_ids(config: Mapping[str, Any]) -> set[str]:
    applicable = {
        "CHAMPION_FULL",
        "CHAMPION_PERSISTENT_REGIME",
    }
    if bool(config.get("entry_slope_required", True)):
        applicable.add("CHAMPION_NO_ENTRY_SLOPE")
    if bool(config.get("hold_slope_exit_enabled", True)):
        applicable.add("CHAMPION_NO_SLOPE_LOSS")
    if float(config.get("tolerance_atr", 0.0) or 0.0) > 0.0:
        applicable.add("CHAMPION_NO_BAND")
    if bool(config.get("direct_reversal_enabled", True)):
        applicable.add("CHAMPION_NO_REVERSAL")
    expiry = config.get("arm_expiry_days")
    if expiry is None or int(expiry) > 0:
        applicable.add("CHAMPION_NO_ARMED")
    if bool(config.get("short_rsi_exit_enabled", False)):
        applicable.add("CHAMPION_NO_RSI_TP")
    overbought_mode = str(config.get("overbought_mode", "disabled")).lower()
    if overbought_mode not in {"disabled", "none", "false"}:
        applicable.add("CHAMPION_NO_OVERBOUGHT")
    return applicable


def champion_module_activation(anchor_oat_row: Mapping[str, Any]) -> dict[str, Any]:
    """Build module activation and CHAMPION_* ablation gate evidence.

    Only ``actions`` and ``state_trace.events/rows`` are consumed.  Plotting
    ``path`` fields, their hashes, trial ids, and labels are intentionally
    ignored.  Counts refer to filled decisions whenever actions/fill events are
    available, so a terminal-suppressed signal cannot satisfy a module gate.
    """

    if not isinstance(anchor_oat_row, Mapping):
        raise TypeError("anchor_oat_row must be a mapping")
    config = anchor_oat_row.get("config", {})
    if not isinstance(config, Mapping):
        raise TypeError("anchor config must be a mapping")
    actions_value = anchor_oat_row.get("actions", [])
    trace_value = anchor_oat_row.get("state_trace", {})
    if not isinstance(actions_value, Sequence) or isinstance(actions_value, (str, bytes)):
        raise TypeError("anchor actions must be a sequence")
    if not isinstance(trace_value, Mapping):
        raise TypeError("anchor state_trace must be a mapping")
    events_value = trace_value.get("events", [])
    rows_value = trace_value.get("rows", [])
    if not isinstance(events_value, Sequence) or isinstance(events_value, (str, bytes)):
        raise TypeError("state_trace events must be a sequence")
    if not isinstance(rows_value, Sequence) or isinstance(rows_value, (str, bytes)):
        raise TypeError("state_trace rows must be a sequence")
    actions = [row for row in actions_value if isinstance(row, Mapping)]
    events = [row for row in events_value if isinstance(row, Mapping)]
    rows = [row for row in rows_value if isinstance(row, Mapping)]
    decisions = _actual_decisions(actions, events)
    actual_keys = {_decision_key(decision) for decision in decisions}

    evidence: dict[str, list[dict[str, Any]]] = {
        key: [] for key in ACTIVATION_KEYS
    }
    overbought_keys: set[tuple[Any, ...]] = set()

    for decision in decisions:
        reason = str(decision["reason"]).lower()
        target_side = int(decision["target_side"])
        from_side = int(decision["from_side"])
        decision_evidence = _decision_evidence(decision)
        if target_side != 0 and reason.startswith(
            ("fresh_cross_", "flat_armed_slope_confirm_", "held_arm_band_confirm_")
        ):
            evidence["fresh_cross_rooted_entries"].append(decision_evidence)
        if reason.startswith("held_arm_band_confirm_"):
            evidence["held_band_confirms"].append(decision_evidence)
        if "slope_loss" in reason and target_side == 0:
            evidence["slope_loss_exits"].append(decision_evidence)
        if reason == "short_rsi_take_profit" and target_side == 0:
            evidence["short_rsi_take_profit_exits"].append(decision_evidence)
        if "overbought" in reason:
            evidence["overbought_qualified_decisions"].append(decision_evidence)
            overbought_keys.add(_decision_key(decision))
        if from_side != 0 and target_side != 0:
            evidence["atomic_reversals"].append(decision_evidence)

    for event in events:
        event_type = str(event.get("event", ""))
        if event_type == "arm_create":
            evidence["arm_create"].append(_event_evidence(event))
        elif event_type == "arm_confirm":
            event_decision = _compact_decision(event, nested=True)
            if event_decision is None or _decision_key(event_decision) not in actual_keys:
                continue
            compact_event = _event_evidence(event)
            compact_event["decision_reason"] = event_decision["reason"]
            evidence["arm_confirm"].append(compact_event)
            if bool(event.get("armed_overbought_qualified", False)):
                decision_key = _decision_key(event_decision)
                if decision_key not in overbought_keys:
                    evidence["overbought_qualified_decisions"].append(
                        _decision_evidence(event_decision)
                    )
                    overbought_keys.add(decision_key)

    rows_by_ts = {
        str(row.get("ts")): row for row in rows if row.get("ts") is not None
    }
    threshold = float(config.get("slope_min_atr", 0.0) or 0.0)
    for decision in decisions:
        target_side = int(decision["target_side"])
        if target_side == 0 or decision.get("signal_ts") is None:
            continue
        trace_row = rows_by_ts.get(str(decision["signal_ts"]))
        if trace_row is None or trace_row.get("slope_atr") is None:
            continue
        try:
            slope_atr = float(trace_row["slope_atr"])
        except (TypeError, ValueError):
            continue
        if math.isfinite(slope_atr) and target_side * slope_atr > threshold:
            row = _decision_evidence(decision)
            row["slope_atr"] = slope_atr
            row["slope_min_atr"] = threshold
            evidence["entry_slope_qualified_decisions"].append(row)

    counts = {key: len(evidence[key]) for key in ACTIVATION_KEYS}
    applicable_ids = _applicable_champion_oat_ids(config)
    gate_evidence: dict[str, dict[str, Any]] = {}
    for oat_id, required in CHAMPION_OAT_REQUIRED_ACTIVATION.items():
        applicable = oat_id in applicable_ids
        observed = {key: int(counts[key]) for key in required}
        gate_evidence[oat_id] = {
            "applicable": applicable,
            "required_activation": list(required),
            "observed_counts": observed,
            "pass": (
                all(value > 0 for value in observed.values())
                if applicable
                else None
            ),
        }

    applicable_gates = [
        gate
        for oat_id, gate in gate_evidence.items()
        if oat_id != "CHAMPION_FULL" and gate["applicable"]
    ]
    return {
        "counts": counts,
        "evidence": evidence,
        "required_activation": {
            key: list(value)
            for key, value in CHAMPION_OAT_REQUIRED_ACTIVATION.items()
        },
        "gate_evidence": gate_evidence,
        "all_applicable_module_gates_pass": all(
            gate["pass"] is True for gate in applicable_gates
        ),
        "source_contract": {
            "uses_actions": True,
            "uses_state_trace_events": True,
            "uses_state_trace_rows": True,
            "uses_display_path": False,
            "uses_trial_id_or_label": False,
        },
    }
