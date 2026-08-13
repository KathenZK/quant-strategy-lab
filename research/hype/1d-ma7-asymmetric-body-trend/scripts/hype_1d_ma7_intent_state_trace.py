"""Read-only state tracing and trade-path comparison for MA7 intent research.

The replay deliberately delegates every strategy decision to the supplied
engine and every observation boundary to the supplied frozen harness.  It
models only the R0, zero-delay close-to-next-open schedule and does not load
data, write artifacts, calculate PnL, or alter either implementation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, is_dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd


_ACTIVATION_KEYS = (
    "arm_create",
    "arm_cancel",
    "arm_confirm",
    "slope_loss_day",
    "slope_loss_threshold",
    "slope_loss_reset",
    "short_rsi_day",
    "short_rsi_threshold",
    "short_rsi_reset",
    "decision_signal",
    "decision_fill_events",
    "decision_fills",
    "terminal_pending_suppressed",
    "terminal_flatten",
)
_IGNORED_TRADE_KEYS = frozenset({"label", "trade_id"})


def _enum_value(value: Any) -> Any:
    if value is None:
        return None
    return value.value if isinstance(value, Enum) else value


def _state_snapshot(state: Any) -> dict[str, Any]:
    origin = getattr(state, "armed_origin", None)
    return {
        "side": int(state.side),
        "armed_side": int(state.armed_side),
        "armed_age": int(state.armed_age),
        "armed_origin": _enum_value(origin),
        "armed_overbought_qualified": bool(
            getattr(state, "armed_overbought_qualified", False)
        ),
        "slope_loss_run": int(getattr(state, "slope_loss_run", 0)),
        "short_rsi_run": int(getattr(state, "short_rsi_run", 0)),
    }


def _decision_snapshot(decision: Any | None) -> dict[str, Any] | None:
    if decision is None:
        return None
    return {
        "signal_ts": pd.Timestamp(decision.signal_ts).isoformat(),
        "reason": str(decision.reason),
        "from_side": int(decision.from_side),
        "target_side": int(decision.target_side),
        "fills": int(decision.fills),
        "arm_effect": _enum_value(getattr(decision, "arm_effect", None)),
    }


def _event(
    events: list[dict[str, Any]],
    event_type: str,
    ts: pd.Timestamp,
    index: int,
    **payload: Any,
) -> dict[str, Any]:
    row = {
        "event": event_type,
        "ts": pd.Timestamp(ts).isoformat(),
        "index": int(index),
        **payload,
    }
    events.append(row)
    return row


def _arm_payload(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "armed_side": int(snapshot["armed_side"]),
        "armed_age": int(snapshot["armed_age"]),
        "armed_origin": snapshot["armed_origin"],
        "armed_overbought_qualified": bool(
            snapshot["armed_overbought_qualified"]
        ),
    }


def _decision_confirms_arm(decision: Any | None, snapshot: Mapping[str, Any]) -> bool:
    if decision is None or int(snapshot["armed_side"]) == 0:
        return False
    armed_side = int(snapshot["armed_side"])
    if int(decision.target_side) == armed_side:
        return True
    effect = _enum_value(getattr(decision, "arm_effect", None))
    return (
        int(decision.from_side) != 0
        and int(decision.target_side) == 0
        and effect == "preserve"
    )


def _record_close_arm_events(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    decision: Any | None,
    *,
    ts: pd.Timestamp,
    index: int,
    events: list[dict[str, Any]],
    counts: dict[str, int],
) -> bool:
    before_side = int(before["armed_side"])
    after_side = int(after["armed_side"])
    if before_side != 0 and before_side != after_side:
        _event(
            events,
            "arm_cancel",
            ts,
            index,
            reason="close_state_transition",
            **_arm_payload(before),
        )
        counts["arm_cancel"] += 1
    if after_side != 0 and after_side != before_side:
        _event(events, "arm_create", ts, index, **_arm_payload(after))
        counts["arm_create"] += 1

    confirmed = _decision_confirms_arm(decision, after)
    if confirmed:
        decision_fields = _decision_snapshot(decision)
        assert decision_fields is not None
        _event(
            events,
            "arm_confirm",
            ts,
            index,
            **_arm_payload(after),
            decision=decision_fields,
        )
        counts["arm_confirm"] += 1
    return confirmed


def _record_counter_close_events(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    config: Any,
    *,
    ts: pd.Timestamp,
    index: int,
    events: list[dict[str, Any]],
    counts: dict[str, int],
) -> None:
    definitions = (
        (
            "slope_loss",
            "slope_loss_run",
            int(config.slope_loss_confirm_days),
        ),
        (
            "short_rsi",
            "short_rsi_run",
            int(config.short_rsi_exit_days),
        ),
    )
    for prefix, state_key, threshold in definitions:
        previous = int(before[state_key])
        current = int(after[state_key])
        if current > previous:
            _event(
                events,
                f"{prefix}_day",
                ts,
                index,
                before=previous,
                after=current,
            )
            counts[f"{prefix}_day"] += 1
            if previous < threshold <= current:
                _event(
                    events,
                    f"{prefix}_threshold",
                    ts,
                    index,
                    threshold=threshold,
                )
                counts[f"{prefix}_threshold"] += 1
        elif previous > 0 and current == 0:
            _event(
                events,
                f"{prefix}_reset",
                ts,
                index,
                before=previous,
                reason="close_state_transition",
            )
            counts[f"{prefix}_reset"] += 1


def _record_nonclose_resets(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    *,
    reason: str,
    ts: pd.Timestamp,
    index: int,
    events: list[dict[str, Any]],
    counts: dict[str, int],
) -> None:
    for prefix, state_key in (
        ("slope_loss", "slope_loss_run"),
        ("short_rsi", "short_rsi_run"),
    ):
        previous = int(before[state_key])
        current = int(after[state_key])
        if previous > 0 and current == 0:
            _event(
                events,
                f"{prefix}_reset",
                ts,
                index,
                before=previous,
                reason=reason,
            )
            counts[f"{prefix}_reset"] += 1


def _finite_or_none(value: Any) -> float | None:
    number = float(value)
    return number if math.isfinite(number) else None


def _relation_or_none(close: Any, ma7: Any) -> int | None:
    close_value = _finite_or_none(close)
    ma_value = _finite_or_none(ma7)
    if close_value is None or ma_value is None:
        return None
    if close_value > ma_value:
        return 1
    if close_value < ma_value:
        return -1
    return 0


def replay_state_trace(
    engine: Any,
    harness: Any,
    data: Any,
    config: Any,
    start_index: int,
    terminal_index: int,
) -> dict[str, Any]:
    """Replay the candidate machine on the harness's R0/no-delay schedule.

    The returned mapping is JSON-compatible.  ``rows`` contains one record per
    daily close in ``[start_index, terminal_index)``.  ``terminal`` separately
    records the boundary open and whether a last-close decision was suppressed,
    matching the harness rule that no order may fill at or beyond the terminal.
    """

    book = data.book
    if not (0 <= start_index < terminal_index <= int(book.count)):
        raise ValueError("invalid trace window")
    if len(data.daily) < terminal_index:
        raise ValueError("daily data does not cover terminal_index")

    machine = engine.OriginalTrendMachine(config)
    first_valid = int(harness._first_valid_index(data))
    active_start = max(start_index, first_valid)
    history_days = max(
        int(config.prior_side_days),
        int(config.short_rsi_exit_days),
        int(config.overbought_days),
    )
    prime_rows: list[Any] = []
    prime_indices: list[int] = []
    for index in range(max(0, active_start - history_days), active_start):
        row = data.daily.iloc[index]
        if np.isfinite(row[["ma7", "atr7", "rsi6"]].to_numpy()).all():
            prime_rows.append(harness._observation(engine, data, index, prime=True))
            prime_indices.append(index)
    if prime_rows:
        consecutive_rows: list[Any] = [prime_rows[-1]]
        consecutive_indices = [prime_indices[-1]]
        for index, value in reversed(list(zip(prime_indices[:-1], prime_rows[:-1]))):
            if value.ts + pd.Timedelta(days=1) != consecutive_rows[0].ts:
                break
            consecutive_rows.insert(0, value)
            consecutive_indices.insert(0, index)
        machine.prime_history(consecutive_rows)
        prime_indices = consecutive_indices

    counts = {key: 0 for key in _ACTIVATION_KEYS}
    events: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    pending_due_index: int | None = None
    pending_arm_confirmed = False

    for index in range(start_index, terminal_index):
        ts = pd.Timestamp(data.daily.index[index])
        current_open = float(book.open[index])
        fill_event: dict[str, Any] | None = None

        if pending_due_index is not None and index == pending_due_index:
            decision = machine.state.pending
            if decision is None:
                raise RuntimeError("missing pending decision at due open")
            if int(machine.state.side) != int(decision.from_side):
                raise RuntimeError("machine side drift before trace decision fill")
            before_fill = _state_snapshot(machine.state)
            decision_fields = _decision_snapshot(decision)
            assert decision_fields is not None
            machine.on_next_open(ts, current_open)
            after_fill = _state_snapshot(machine.state)
            fill_event = _event(
                events,
                "decision_fill",
                ts,
                index,
                price=current_open,
                decision=decision_fields,
            )
            counts["decision_fill_events"] += 1
            counts["decision_fills"] += int(decision.fills)
            if int(before_fill["armed_side"]) != 0 and int(after_fill["armed_side"]) == 0:
                if pending_arm_confirmed:
                    _event(
                        events,
                        "arm_consume",
                        ts,
                        index,
                        reason="confirmed_decision_fill",
                        **_arm_payload(before_fill),
                    )
                else:
                    _event(
                        events,
                        "arm_cancel",
                        ts,
                        index,
                        reason="decision_fill_clear",
                        **_arm_payload(before_fill),
                    )
                    counts["arm_cancel"] += 1
            _record_nonclose_resets(
                before_fill,
                after_fill,
                reason="decision_fill",
                ts=ts,
                index=index,
                events=events,
                counts=counts,
            )
            pending_due_index = None
            pending_arm_confirmed = False

        row = data.daily.iloc[index]
        complete = bool(
            np.isfinite(
                row[["ma7", "atr7", "rsi6", "slope_atr"]].to_numpy()
            ).all()
        )
        decision = None
        if index >= active_start:
            if machine.state.pending is not None:
                raise RuntimeError("zero-delay trace retained a pending close decision")
            if complete:
                before_close = _state_snapshot(machine.state)
                decision = machine.on_close(harness._observation(engine, data, index))
                after_close = _state_snapshot(machine.state)
                pending_arm_confirmed = _record_close_arm_events(
                    before_close,
                    after_close,
                    decision,
                    ts=ts,
                    index=index,
                    events=events,
                    counts=counts,
                )
                _record_counter_close_events(
                    before_close,
                    after_close,
                    config,
                    ts=ts,
                    index=index,
                    events=events,
                    counts=counts,
                )
                if decision is not None:
                    decision_fields = _decision_snapshot(decision)
                    assert decision_fields is not None
                    _event(
                        events,
                        "decision_signal",
                        ts,
                        index,
                        decision=decision_fields,
                    )
                    counts["decision_signal"] += 1
                    pending_due_index = index + 1

        state = _state_snapshot(machine.state)
        pending = _decision_snapshot(machine.state.pending)
        rows.append(
            {
                "index": int(index),
                "ts": ts.isoformat(),
                **state,
                "pending_reason": None if pending is None else pending["reason"],
                "pending_from_side": None if pending is None else pending["from_side"],
                "pending_target_side": (
                    None if pending is None else pending["target_side"]
                ),
                "pending_fills": None if pending is None else pending["fills"],
                "open_fill_reason": (
                    None
                    if fill_event is None
                    else fill_event["decision"]["reason"]
                ),
                "open_fill_from_side": (
                    None
                    if fill_event is None
                    else fill_event["decision"]["from_side"]
                ),
                "open_fill_target_side": (
                    None
                    if fill_event is None
                    else fill_event["decision"]["target_side"]
                ),
                "open_fill_fills": (
                    None if fill_event is None else fill_event["decision"]["fills"]
                ),
                "relation": _relation_or_none(row["close"], row["ma7"]),
                "slope_atr": _finite_or_none(row["slope_atr"]),
                "rsi6": _finite_or_none(row["rsi6"]),
                "complete": complete,
            }
        )

    terminal_ts = (
        pd.Timestamp(book.terminal_ts)
        if terminal_index == int(book.count)
        else pd.Timestamp(book.ts[terminal_index])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if terminal_index == int(book.count)
        else float(book.open[terminal_index])
    )
    before_terminal = _state_snapshot(machine.state)
    terminal_pending = _decision_snapshot(machine.state.pending)
    if terminal_pending is not None:
        _event(
            events,
            "terminal_pending_suppressed",
            terminal_ts,
            terminal_index,
            decision=terminal_pending,
        )
        counts["terminal_pending_suppressed"] += 1
    if int(before_terminal["side"]) != 0:
        _event(
            events,
            "terminal_flatten",
            terminal_ts,
            terminal_index,
            from_side=int(before_terminal["side"]),
            target_side=0,
            fills=1,
            price=terminal_open,
        )
        counts["terminal_flatten"] += 1

    machine.state.pending = None
    machine.force_flat()
    after_terminal = _state_snapshot(machine.state)
    if int(before_terminal["armed_side"]) != 0:
        _event(
            events,
            "arm_cancel",
            terminal_ts,
            terminal_index,
            reason="terminal_suppression_or_flatten",
            **_arm_payload(before_terminal),
        )
        counts["arm_cancel"] += 1
    _record_nonclose_resets(
        before_terminal,
        after_terminal,
        reason="terminal_suppression_or_flatten",
        ts=terminal_ts,
        index=terminal_index,
        events=events,
        counts=counts,
    )

    return {
        "start_index": int(start_index),
        "active_start": int(active_start),
        "terminal_index": int(terminal_index),
        "prime_history_indices": [int(value) for value in prime_indices],
        "rows": rows,
        "events": events,
        "activation_counts": counts,
        "terminal": {
            "ts": terminal_ts.isoformat(),
            "open": terminal_open,
            "pending_suppressed": terminal_pending is not None,
            "pending": terminal_pending,
            "pending_arm_confirmed": bool(
                terminal_pending is not None and pending_arm_confirmed
            ),
            "state_before": before_terminal,
            "state_after": after_terminal,
        },
    }


def _canonical_trade_value(value: Any) -> Any:
    if is_dataclass(value):
        return _canonical_trade_value(asdict(value))
    if isinstance(value, Enum):
        return _canonical_trade_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_trade_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _IGNORED_TRADE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_trade_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.generic):
        return _canonical_trade_value(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def trade_signatures(trades: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic trade records with only label/trade_id removed."""

    signatures: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, Mapping):
            raise TypeError("each trade must be a mapping")
        signature = _canonical_trade_value(trade)
        if not isinstance(signature, dict):
            raise TypeError("canonical trade signature must be a mapping")
        signatures.append(signature)
    return signatures


def _signature_key(signature: Mapping[str, Any]) -> str:
    return json.dumps(
        signature,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _ordered_multiset_difference(
    source: list[dict[str, Any]],
    subtract: list[dict[str, Any]],
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
    anchor: Iterable[Mapping[str, Any]],
    variant: Iterable[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Return chronological multiset additions/removals for two trade paths."""

    anchor_signatures = trade_signatures(anchor)
    variant_signatures = trade_signatures(variant)
    return {
        "added": _ordered_multiset_difference(
            variant_signatures, anchor_signatures
        ),
        "removed": _ordered_multiset_difference(
            anchor_signatures, variant_signatures
        ),
    }
