"""Fail-closed fair metrics for the HYPE 1D MA7 intent search.

The candidate harness observes hourly extrema in chronological hour buckets,
while registered V4 uses one conservative daily ordering: funding first, then
the session's favorable extreme, adverse extreme, and close.  This module
replays only the candidate ledger under that V4-compatible drawdown ordering.
It never changes candidate PnL, costs, funding, fills, or solvency.

R1 hard stops remain on the native hourly harness.  ``audit_r1_gap_stops``
therefore reports execution-resolution limitations (especially a funding event
at the same timestamp as a gap-open stop) without silently correcting them.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
from typing import Any

import pandas as pd


_PARITY_REL_TOL = 2e-12
_PARITY_ABS_TOL = 2e-12
_STOP_REASONS = frozenset({"emergency_hard_stop", "protective_stop"})


def _metrics(result: Any) -> Mapping[str, Any]:
    metrics = getattr(result, "metrics", None)
    if not isinstance(metrics, Mapping):
        raise RuntimeError("result.metrics must be a mapping")
    return metrics


def _rows(result: Any, field: str) -> list[dict[str, Any]]:
    rows = getattr(result, field, None)
    if rows is None:
        raise RuntimeError(f"retained result.{field} evidence is required")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise RuntimeError(f"result.{field} must be a list of dictionaries")
    return rows


def _finite_metric(metrics: Mapping[str, Any], key: str) -> float:
    if key not in metrics:
        raise RuntimeError(f"candidate metric {key!r} is missing")
    try:
        value = float(metrics[key])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"candidate metric {key!r} is not numeric") from exc
    if not math.isfinite(value):
        raise RuntimeError(f"candidate metric {key!r} must be finite")
    return value


def _raw_bankruptcy_flags(metrics: Mapping[str, Any]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for key in ("bankrupt", "bankrupt_intraday"):
        if key not in metrics:
            continue
        raw = metrics[key]
        if isinstance(raw, bool):
            flags[key] = raw
        elif isinstance(raw, int) and raw in (0, 1):
            flags[key] = bool(raw)
        else:
            raise RuntimeError(f"candidate raw solvency flag {key!r} is invalid: {raw!r}")
    return flags


def assert_candidate_solvency(result: Any) -> dict[str, Any]:
    """Reject a raw candidate when its native harness reports bankruptcy.

    At least one native flag is mandatory.  A positive final equity is checked
    as an additional ledger invariant, but it cannot override a true raw flag.
    """

    metrics = _metrics(result)
    flags = _raw_bankruptcy_flags(metrics)
    if not flags:
        raise RuntimeError("candidate is missing raw bankrupt/bankrupt_intraday flag")
    failed = sorted(key for key, value in flags.items() if value)
    if failed:
        raise RuntimeError(
            "candidate failed raw solvency: " + ", ".join(f"{key}=true" for key in failed)
        )
    equity = _finite_metric(metrics, "equity_multiple")
    if equity <= 0.0:
        raise RuntimeError(f"candidate final equity is non-positive: {equity}")
    return {"solvent": True, "raw_flags": flags, "equity_multiple": equity}


def _utc_timestamp(value: Any, *, label: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid {label} timestamp: {value!r}") from exc
    if timestamp.tzinfo is None:
        raise RuntimeError(f"{label} timestamp must be timezone-aware")
    return timestamp.tz_convert("UTC")


def _session_timestamp(data: Any, index: int) -> pd.Timestamp:
    timestamp = _utc_timestamp(data.book.ts[index], label="session")
    if any((timestamp.hour, timestamp.minute, timestamp.second, timestamp.microsecond)):
        raise RuntimeError(f"fair daily replay requires 00:00 UTC sessions: {timestamp}")
    return timestamp


def _terminal(data: Any, terminal_index: int) -> tuple[pd.Timestamp, float]:
    book = data.book
    if terminal_index == int(book.count):
        return (
            _utc_timestamp(book.terminal_ts, label="terminal"),
            float(book.quality["terminal_open"]),
        )
    return (
        _utc_timestamp(book.ts[terminal_index], label="terminal"),
        float(book.open[terminal_index]),
    )


def _action_timestamp(action: Mapping[str, Any]) -> pd.Timestamp:
    if "ts" not in action:
        raise RuntimeError("retained action is missing ts")
    timestamp = _utc_timestamp(action["ts"], label="action")
    if any((timestamp.hour, timestamp.minute, timestamp.second, timestamp.microsecond)):
        raise RuntimeError(f"intraday action is incompatible with V4 daily replay: {timestamp}")
    return timestamp


def _parity(candidate: float, replayed: float) -> dict[str, Any]:
    tolerance = max(
        _PARITY_ABS_TOL,
        _PARITY_REL_TOL * max(abs(candidate), abs(replayed)),
    )
    delta = replayed - candidate
    return {
        "candidate": candidate,
        "replayed": replayed,
        "delta": delta,
        "tolerance": tolerance,
        "pass": abs(delta) <= tolerance,
    }


def v4_compatible_daily_extreme_mdd(
    result: Any,
    data: Any,
    harness: Any,
    start_index: int,
    terminal_index: int,
    slippage: float,
) -> dict[str, Any]:
    """Replay an R0 candidate ledger with registered-V4 daily MDD semantics.

    ``gate_mdd`` and ``gate_mdd_pct`` are both percentage values, matching the
    repository's ``max_drawdown_pct`` convention.  PnL fields must reproduce
    the native candidate to near machine precision; otherwise this function
    raises instead of returning a drawdown suitable for ranking or gates.
    """

    solvency = assert_candidate_solvency(result)
    metrics = _metrics(result)
    actions = _rows(result, "actions")
    book = data.book
    if not (0 <= start_index < terminal_index <= int(book.count)):
        raise ValueError("invalid fair-replay window")
    if not math.isfinite(slippage) or slippage < 0.0:
        raise ValueError("slippage must be finite and non-negative")

    hard_stop_atr = _finite_metric(metrics, "hard_stop_atr")
    hard_stop_count = int(_finite_metric(metrics, "hard_stop_count"))
    if hard_stop_atr != 0.0 or hard_stop_count != 0:
        raise RuntimeError("V4 daily replay accepts only R0 candidates without hard stops")
    if int(_finite_metric(metrics, "extra_delay_days")) != 0:
        raise RuntimeError("V4 daily replay accepts only the zero-extra-delay candidate")
    reported_slippage = _finite_metric(metrics, "slippage_bps") / 10_000.0
    if not math.isclose(
        reported_slippage,
        slippage,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise RuntimeError(
            f"slippage drift: requested {slippage}, candidate used {reported_slippage}"
        )
    if any(str(action.get("reason", "")) in _STOP_REASONS for action in actions):
        raise RuntimeError("retained candidate actions contain an intraday hard stop")

    start_ts = _session_timestamp(data, start_index)
    terminal_ts, terminal_price = _terminal(data, terminal_index)
    if any((terminal_ts.hour, terminal_ts.minute, terminal_ts.second, terminal_ts.microsecond)):
        raise RuntimeError("fair daily replay requires a 00:00 UTC terminal")
    action_by_ts: dict[pd.Timestamp, dict[str, Any]] = {}
    for action in actions:
        timestamp = _action_timestamp(action)
        if not start_ts <= timestamp <= terminal_ts:
            raise RuntimeError(f"action outside replay window: {timestamp}")
        if timestamp in action_by_ts:
            raise RuntimeError(f"multiple retained actions at one daily open: {timestamp}")
        action_by_ts[timestamp] = action

    target_quantity = getattr(harness, "_target_quantity", None)
    fee = getattr(harness, "FEE", None)
    if not callable(target_quantity) or fee is None:
        raise RuntimeError("harness must expose _target_quantity and FEE")
    cost_rate = float(fee) + slippage
    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(book.open[start_index])
    peak = 1.0
    max_drawdown = 0.0
    turnover_total = 0.0
    cost_total = 0.0
    funding_total = 0.0
    atomic_reversals = 0
    terminal_flatten_verified = False
    audit_path: list[dict[str, Any]] = []

    def observe(value: float) -> None:
        nonlocal peak, max_drawdown
        if not math.isfinite(value) or value <= 0.0:
            raise RuntimeError(f"daily-extreme replay became insolvent: {value}")
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)

    def rebalance(target_side: int, price: float) -> dict[str, Any]:
        nonlocal equity, qty, turnover_total, cost_total
        old_equity = equity
        outcome = target_quantity(equity, qty, target_side, price, cost_rate)
        if not isinstance(outcome, tuple) or len(outcome) != 4:
            raise RuntimeError("harness._target_quantity must return four values")
        new_qty, new_equity, turnover, cost = map(float, outcome)
        if not all(math.isfinite(value) for value in outcome):
            raise RuntimeError("non-finite target-quantity result")
        if not math.isclose(
            old_equity - new_equity,
            cost,
            rel_tol=_PARITY_REL_TOL,
            abs_tol=_PARITY_ABS_TOL,
        ):
            raise RuntimeError("target-quantity cost does not reconcile to equity")
        qty = new_qty
        equity = new_equity
        turnover_total += turnover
        cost_total += cost
        observe(equity)
        return {
            "target_side": target_side,
            "quantity": qty,
            "turnover": turnover,
            "cost": cost,
            "equity": equity,
        }

    def execute_action(action: Mapping[str, Any], price: float) -> dict[str, Any]:
        nonlocal side, atomic_reversals, terminal_flatten_verified
        try:
            from_side = int(action["from_side"])
            target_side = int(action["target_side"])
            reported_fills = int(action["fills"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"malformed retained action: {action!r}") from exc
        if from_side != side:
            raise RuntimeError(
                f"action/ledger side drift: action from {from_side}, ledger {side}"
            )
        if target_side not in (-1, 0, 1) or target_side == from_side:
            raise RuntimeError(f"invalid action target transition: {from_side}->{target_side}")
        expected_fills = 2 if from_side != 0 and target_side != 0 else 1
        if reported_fills != expected_fills:
            raise RuntimeError(
                f"action fill-count drift: expected {expected_fills}, got {reported_fills}"
            )
        components: list[dict[str, Any]] = []
        if expected_fills == 2:
            components.append(rebalance(0, price))
            side = 0
            components.append(rebalance(target_side, price))
            atomic_reversals += 1
        else:
            components.append(rebalance(target_side, price))
        side = target_side
        reason = str(action.get("reason", ""))
        if reason == "terminal_flatten":
            if side != 0 or target_side != 0:
                raise RuntimeError("terminal_flatten did not leave a flat ledger")
            terminal_flatten_verified = True
        return {
            "reason": reason,
            "from_side": from_side,
            "target_side": target_side,
            "fills": expected_fills,
            "components": components,
        }

    for index in range(start_index, terminal_index):
        timestamp = _session_timestamp(data, index)
        current_open = float(book.open[index])
        if index > start_index:
            equity += qty * (current_open - mark_price)
            mark_price = current_open
            observe(equity)
        else:
            mark_price = current_open

        pre_action_equity = equity
        action_audit = None
        action = action_by_ts.pop(timestamp, None)
        if action is not None:
            action_price = float(action.get("price", math.nan))
            if not math.isclose(
                action_price,
                current_open,
                rel_tol=_PARITY_REL_TOL,
                abs_tol=_PARITY_ABS_TOL,
            ):
                raise RuntimeError(
                    f"daily-open action price drift at {timestamp}: "
                    f"action={action_price}, open={current_open}"
                )
            action_audit = execute_action(action, current_open)
        post_action_equity = equity
        peak = max(peak, pre_action_equity, post_action_equity)
        max_drawdown = min(max_drawdown, post_action_equity / peak - 1.0)

        day_funding = 0.0
        funding_events: list[dict[str, Any]] = []
        if side != 0:
            for event in data.features.funding_events[index]:
                event_ts = _utc_timestamp(event.ts, label="funding event")
                if not timestamp <= event_ts < timestamp + pd.Timedelta(days=1):
                    raise RuntimeError(f"funding event outside its session: {event_ts}")
                payment = qty * float(event.price) * float(event.rate)
                equity -= payment
                day_funding += payment
                funding_total += payment
                funding_events.append(
                    {
                        "ts": event_ts.isoformat(),
                        "price": float(event.price),
                        "rate": float(event.rate),
                        "payment": payment,
                    }
                )
        funded_open_equity = equity
        if side != 0:
            favorable_price = float(book.high[index] if side > 0 else book.low[index])
            adverse_price = float(book.low[index] if side > 0 else book.high[index])
            close_price = float(book.close[index])
            favorable_equity = funded_open_equity + qty * (
                favorable_price - current_open
            )
            adverse_equity = funded_open_equity + qty * (adverse_price - current_open)
            close_equity = funded_open_equity + qty * (close_price - current_open)
            if adverse_equity <= 0.0:
                raise RuntimeError(
                    f"daily-extreme replay found bankruptcy at {timestamp}: {adverse_equity}"
                )
            peak = max(peak, favorable_equity, close_equity)
            max_drawdown = min(
                max_drawdown,
                adverse_equity / peak - 1.0,
                close_equity / peak - 1.0,
            )
            equity = close_equity
            mark_price = close_price
        else:
            favorable_price = adverse_price = float(book.close[index])
            favorable_equity = adverse_equity = close_equity = equity
            mark_price = float(book.close[index])

        audit_path.append(
            {
                "ts": timestamp.isoformat(),
                "pre_action_equity": pre_action_equity,
                "post_action_equity": post_action_equity,
                "funded_open_equity": funded_open_equity,
                "favorable_price": favorable_price,
                "adverse_price": adverse_price,
                "favorable_equity": favorable_equity,
                "adverse_equity": adverse_equity,
                "close_equity": close_equity,
                "side": side,
                "day_funding_payment": day_funding,
                "funding_events": funding_events,
                "action": action_audit,
                "order": "funding_then_favorable_then_adverse_then_close",
            }
        )

    equity += qty * (terminal_price - mark_price)
    mark_price = terminal_price
    observe(equity)
    terminal_pre_action_equity = equity
    terminal_action_audit = None
    terminal_action = action_by_ts.pop(terminal_ts, None)
    if terminal_action is not None:
        terminal_action_price = float(terminal_action.get("price", math.nan))
        if not math.isclose(
            terminal_action_price,
            terminal_price,
            rel_tol=_PARITY_REL_TOL,
            abs_tol=_PARITY_ABS_TOL,
        ):
            raise RuntimeError("terminal action price does not match terminal open")
        terminal_action_audit = execute_action(terminal_action, terminal_price)
    if side != 0:
        raise RuntimeError("solvent candidate lacks retained terminal flatten evidence")
    if action_by_ts:
        raise RuntimeError(f"unconsumed retained actions: {sorted(action_by_ts)}")
    observe(equity)
    audit_path.append(
        {
            "ts": terminal_ts.isoformat(),
            "terminal": True,
            "price": terminal_price,
            "pre_action_equity": terminal_pre_action_equity,
            "close_equity": equity,
            "side": side,
            "action": terminal_action_audit,
        }
    )

    comparisons = {
        "equity_multiple": _parity(
            _finite_metric(metrics, "equity_multiple"), equity
        ),
        "turnover": _parity(_finite_metric(metrics, "turnover"), turnover_total),
        "cost": _parity(_finite_metric(metrics, "cost"), cost_total),
        "funding_payment": _parity(
            _finite_metric(metrics, "funding_payment"), funding_total
        ),
    }
    failed = [key for key, row in comparisons.items() if not row["pass"]]
    if failed:
        details = ", ".join(
            f"{key}: candidate={comparisons[key]['candidate']}, "
            f"replayed={comparisons[key]['replayed']}"
            for key in failed
        )
        raise RuntimeError(f"candidate/daily-replay ledger parity failed: {details}")

    gate_mdd_pct = max_drawdown * 100.0
    return {
        "status": "PASS",
        "gate_mdd": gate_mdd_pct,
        "gate_mdd_pct": gate_mdd_pct,
        "max_drawdown_pct": gate_mdd_pct,
        "native_hourly_mdd_pct": _finite_metric(metrics, "max_drawdown_pct"),
        "daily_extreme_order": "funding_then_favorable_then_adverse_then_close",
        "solvency": solvency,
        "consistency": {"all_pass": True, "fields": comparisons},
        "ledger": {
            "equity_multiple": equity,
            "turnover": turnover_total,
            "cost": cost_total,
            "funding_payment": funding_total,
            "final_quantity": qty,
            "final_side": side,
        },
        "action_count": len(actions),
        "atomic_reversal_count": atomic_reversals,
        "terminal_flatten_verified": terminal_flatten_verified,
        "audit_path": audit_path,
    }


def audit_r1_gap_stops(
    result: Any,
    data: Any,
    hard_stop_atr: float,
) -> dict[str, Any]:
    """Audit R1 hourly hard-stop fills without changing the retained ledger.

    A gap stop at the exact timestamp of a funding event is a blocker because
    the hourly harness books funding before checking the gap at that open.  The
    report exposes that ambiguity and the one reported exposure hour, but does
    not alter either funding or the performance metrics.
    """

    if not math.isfinite(hard_stop_atr) or hard_stop_atr <= 0.0:
        raise ValueError("hard_stop_atr must be finite and positive for an R1 audit")
    metrics = _metrics(result)
    actions = _rows(result, "actions")
    trades = _rows(result, "trades")
    raw_flags = _raw_bankruptcy_flags(metrics)
    if not raw_flags:
        raise RuntimeError("R1 result is missing raw bankrupt/bankrupt_intraday flag")
    bankrupt = any(raw_flags.values())
    reported_hard_stop_atr = _finite_metric(metrics, "hard_stop_atr")
    if not math.isclose(
        reported_hard_stop_atr,
        hard_stop_atr,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise RuntimeError(
            f"R1 hard-stop ATR drift: expected {hard_stop_atr}, "
            f"got {reported_hard_stop_atr}"
        )

    stop_actions = [
        action for action in actions if str(action.get("reason", "")) in _STOP_REASONS
    ]
    stop_trades = [
        trade for trade in trades if str(trade.get("exit_reason", "")) in _STOP_REASONS
    ]
    blockers: list[str] = []
    if len(stop_actions) != len(stop_trades):
        blockers.append(
            f"stop_action_trade_count_mismatch:{len(stop_actions)}!={len(stop_trades)}"
        )
    trades_by_exit: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for trade in stop_trades:
        exit_ts = _utc_timestamp(trade.get("exit_ts"), label="stop trade exit")
        trades_by_exit.setdefault(exit_ts, []).append(trade)

    daily_index = pd.DatetimeIndex(data.daily.index)
    if daily_index.tz is None:
        raise RuntimeError("daily index must be timezone-aware")
    daily_index = daily_index.tz_convert("UTC")
    stop_rows: list[dict[str, Any]] = []
    gap_count = 0
    for ordinal, action in enumerate(stop_actions, start=1):
        exit_ts = _utc_timestamp(action.get("ts"), label="stop action")
        matched = trades_by_exit.get(exit_ts, [])
        if len(matched) != 1:
            blockers.append(f"stop_trade_match_count:{exit_ts.isoformat()}:{len(matched)}")
            continue
        trade = matched[0]
        side_text = str(trade.get("side", ""))
        if side_text not in {"long", "short"}:
            raise RuntimeError(f"invalid stopped-trade side: {side_text!r}")
        side = 1 if side_text == "long" else -1
        entry_price = float(trade["entry_price"])
        entry_atr = float(trade["entry_atr"])
        theoretical_level = entry_price - side * hard_stop_atr * entry_atr
        session_ts = exit_ts.floor("D")
        locations = daily_index.get_indexer([session_ts])
        day_index = int(locations[0])
        if day_index < 0:
            raise RuntimeError(f"stop session absent from daily data: {session_ts}")
        hour = int((exit_ts - session_ts).total_seconds() // 3_600)
        if not 0 <= hour < 24 or exit_ts != session_ts + pd.Timedelta(hours=hour):
            raise RuntimeError(f"stop timestamp is not an exact hourly boundary: {exit_ts}")
        hour_open = float(data.features.hourly_open[day_index][hour])
        hour_high = float(data.features.hourly_high[day_index][hour])
        hour_low = float(data.features.hourly_low[day_index][hour])
        hit = hour_low <= theoretical_level if side > 0 else hour_high >= theoretical_level
        gap = hour_open <= theoretical_level if side > 0 else hour_open >= theoretical_level
        gap_count += int(gap)
        expected_fill = hour_open if gap else theoretical_level
        actual_fill = float(trade["exit_price"])
        action_fill = float(action.get("price", math.nan))
        fill_matches = math.isclose(
            actual_fill,
            expected_fill,
            rel_tol=_PARITY_REL_TOL,
            abs_tol=_PARITY_ABS_TOL,
        ) and math.isclose(
            action_fill,
            actual_fill,
            rel_tol=_PARITY_REL_TOL,
            abs_tol=_PARITY_ABS_TOL,
        )
        if not hit:
            blockers.append(f"stop_level_not_hit:{exit_ts.isoformat()}")
        if not fill_matches:
            blockers.append(f"stop_fill_mismatch:{exit_ts.isoformat()}")

        funding_at_exit_ts: list[dict[str, Any]] = []
        entry_quantity = float(trade["entry_quantity"])
        for event in data.features.funding_events[day_index]:
            event_ts = _utc_timestamp(event.ts, label="funding event")
            if event_ts == exit_ts:
                funding_at_exit_ts.append(
                    {
                        "ts": event_ts.isoformat(),
                        "price": float(event.price),
                        "rate": float(event.rate),
                        "reported_signed_payment": (
                            entry_quantity * float(event.price) * float(event.rate)
                        ),
                    }
                )
        funding_blocker = gap and bool(funding_at_exit_ts)
        if funding_blocker:
            blockers.append(f"gap_stop_funding_same_timestamp:{exit_ts.isoformat()}")

        max_adverse_price = float(
            trade["lowest"] if side > 0 else trade["highest"]
        )
        calculated_mae = side * (max_adverse_price - entry_price) / entry_price
        reported_mae = float(trade.get("mae_return", calculated_mae))
        stopped_equity = float(trade.get("exit_equity", math.nan))
        stop_rows.append(
            {
                "ordinal": ordinal,
                "trade_id": trade.get("trade_id"),
                "side": side_text,
                "entry_ts": str(trade.get("entry_ts")),
                "exit_ts": exit_ts.isoformat(),
                "entry_price": entry_price,
                "entry_atr": entry_atr,
                "hard_stop_atr": hard_stop_atr,
                "theoretical_stop_level": theoretical_level,
                "gap_at_hour_open": gap,
                "level_hit_in_hour": hit,
                "expected_fill": expected_fill,
                "actual_fill": actual_fill,
                "fill_matches_model": fill_matches,
                "hour": hour,
                "hour_ohlc": {
                    "open": hour_open,
                    "high": hour_high,
                    "low": hour_low,
                },
                "funding_at_exit_ts": funding_at_exit_ts,
                "gap_funding_same_timestamp_blocker": funding_blocker,
                "funding_correction_applied": False,
                "reported_exposure_hour_counted": True,
                "exposure_correction_hours": -1.0 if gap else 0.0,
                "max_adverse_price_before_exit": max_adverse_price,
                "max_adverse_return": reported_mae,
                "calculated_max_adverse_return": calculated_mae,
                "exit_equity": stopped_equity if math.isfinite(stopped_equity) else None,
                "bankrupt_at_or_after_stop": bankrupt
                or (math.isfinite(stopped_equity) and stopped_equity <= 0.0),
            }
        )

    metric_stop_count = int(_finite_metric(metrics, "hard_stop_count"))
    if metric_stop_count != len(stop_actions):
        blockers.append(
            f"metric_stop_count_mismatch:{metric_stop_count}!={len(stop_actions)}"
        )

    terminal_side = 0
    action_state_valid = True
    for action in sorted(
        actions,
        key=lambda row: _utc_timestamp(row.get("ts"), label="retained action"),
    ):
        try:
            from_side = int(action["from_side"])
            target_side = int(action["target_side"])
        except (KeyError, TypeError, ValueError):
            action_state_valid = False
            continue
        if from_side != terminal_side:
            action_state_valid = False
        terminal_side = target_side
    if not action_state_valid:
        blockers.append("retained_action_state_path_invalid")
    terminal_flat = action_state_valid and terminal_side == 0 and not bankrupt
    if not terminal_flat and not bankrupt:
        blockers.append("solvent_r1_not_terminal_flat")
    terminal_actions = [
        action for action in actions if str(action.get("reason", "")) == "terminal_flatten"
    ]

    start_ts = _utc_timestamp(metrics.get("start_ts"), label="metric start")
    end_ts = _utc_timestamp(metrics.get("end_ts"), label="metric end")
    window_hours = (end_ts - start_ts).total_seconds() / 3_600.0
    if window_hours <= 0.0:
        raise RuntimeError("R1 metric window must have positive duration")
    reported_exposure_pct = _finite_metric(metrics, "exposure_pct")
    reported_exposure_hours = reported_exposure_pct / 100.0 * window_hours
    corrected_exposure_hours = max(0.0, reported_exposure_hours - gap_count)
    corrected_exposure_pct = corrected_exposure_hours / window_hours * 100.0

    comparison_keys = (
        "equity_multiple",
        "net_return_pct",
        "max_drawdown_pct",
        "closed_trades",
        "long_trades",
        "short_trades",
        "turnover",
        "cost",
        "funding_payment",
        "exposure_pct",
        "hard_stop_count",
        "slippage_bps",
        "extra_delay_days",
        "hard_stop_atr",
    )
    comparison_fields = {
        key: metrics[key] for key in comparison_keys if key in metrics
    }
    comparison_fields.update(
        {
            "raw_bankruptcy_flags": raw_flags,
            "reported_exposure_hours": reported_exposure_hours,
            "gap_exposure_correction_hours": -float(gap_count),
            "corrected_exposure_hours": corrected_exposure_hours,
            "corrected_exposure_pct": corrected_exposure_pct,
            "terminal_flat": terminal_flat,
            "gap_stop_count": gap_count,
            "funding_correction_applied": False,
        }
    )
    worst_adverse = min(
        (float(row["max_adverse_return"]) for row in stop_rows),
        default=None,
    )
    return {
        "status": "BLOCKED" if blockers else "PASS",
        "blockers": list(dict.fromkeys(blockers)),
        "hard_stop_atr": hard_stop_atr,
        "stop_count": len(stop_rows),
        "metric_stop_count": metric_stop_count,
        "stops": stop_rows,
        "gap_stop_count": gap_count,
        "gap_funding_same_timestamp_count": sum(
            bool(row["gap_funding_same_timestamp_blocker"]) for row in stop_rows
        ),
        "funding_correction_applied": False,
        "reported_funding_payment": metrics.get("funding_payment"),
        "exposure": {
            "window_hours": window_hours,
            "reported_pct": reported_exposure_pct,
            "reported_hours": reported_exposure_hours,
            "gap_open_correction_hours": -float(gap_count),
            "corrected_hours": corrected_exposure_hours,
            "corrected_pct": corrected_exposure_pct,
        },
        "max_adverse_return": worst_adverse,
        "bankrupt": bankrupt,
        "raw_bankruptcy_flags": raw_flags,
        "terminal_flat": terminal_flat,
        "terminal_side": terminal_side,
        "terminal_flatten_action_count": len(terminal_actions),
        "r0_r1_comparison_fields": comparison_fields,
    }
