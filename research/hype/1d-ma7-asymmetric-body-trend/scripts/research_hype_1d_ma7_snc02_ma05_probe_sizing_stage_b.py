"""Run frozen SNC02 MA05 probe-entry and confirmation-promotion Stage B."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-snc02-ma05-probe-sizing-stage-b-contract-2026-08-20.md"
)
CONTROL_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
)
STAGE_A_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_snc02_risk_overlay_oat.py"
)
STAGE_A_ARTIFACT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_snc02_risk_overlay_oat_2026-08-20.json"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
OUTPUT_PATH = (
    ARTIFACT_DIR
    / "hype_1d_ma7_snc02_ma05_probe_sizing_stage_b_2026-08-20.json"
)

BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
MA_EXIT_BUFFER_ATR = 0.5
CONFIRM_SLOPE_ATR = 0.02
RETURN_RETENTION_FRACTION = 0.50
LATEST_CAPTURE_FRACTION = 0.60
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


@dataclass(frozen=True, slots=True)
class Arm:
    arm_id: str
    entry_leverage: float
    confirmation_days: int = 0
    promotion_leverage: float | None = None


ARMS = (
    Arm("MA05_1X", 1.00),
    Arm("MA05_FIXED75", 0.75),
    Arm("MA05_FIXED50", 0.50),
    Arm("MA05_P50_C1", 0.50, 1, 1.00),
    Arm("MA05_P50_C2", 0.50, 2, 1.00),
    Arm("MA05_P25_C2", 0.25, 2, 1.00),
)


@dataclass(slots=True)
class Position:
    trade_id: int
    side: int
    signal_ts: pd.Timestamp
    entry_ts: pd.Timestamp
    entry_price: float
    entry_equity: float
    entry_leverage: float
    quantity: float
    confirmation_count: int = 0
    promoted: bool = False
    promotion_ts: pd.Timestamp | None = None
    promotion_price: float | None = None
    funding_pnl: float = 0.0
    trade_cost: float = 0.0
    trade_turnover: float = 0.0


@dataclass(frozen=True, slots=True)
class Pending:
    due_index: int
    kind: str
    reason: str
    target_side: int = 0
    signal: Any | None = None
    trade_id: int | None = None


def load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def arm_config(arm: Arm) -> dict[str, Any]:
    return {
        "arm_id": arm.arm_id,
        "entry_leverage": arm.entry_leverage,
        "confirmation_days": arm.confirmation_days,
        "promotion_leverage": arm.promotion_leverage,
    }


def funding_by_hour(context: Any) -> dict[pd.Timestamp, list[Any]]:
    grouped: dict[pd.Timestamp, list[Any]] = defaultdict(list)
    events = [event for daily in context.features.funding_events for event in daily]
    for event in sorted(events, key=lambda row: pd.Timestamp(row.ts)):
        grouped[pd.Timestamp(event.ts).floor("h")].append(event)
    return grouped


def terminal_point(context: Any, right: int) -> tuple[pd.Timestamp, float]:
    if right < context.book.count:
        return pd.Timestamp(context.book.ts[right]), float(context.book.open[right])
    return (
        pd.Timestamp(context.book.terminal_ts),
        float(context.book.quality["terminal_open"]),
    )


def index_at_or_after(context: Any, ts: str) -> int:
    target = pd.Timestamp(ts)
    return next(
        index
        for index, value in enumerate(context.book.ts)
        if pd.Timestamp(value) >= target
    )


def run_arm(
    context: Any,
    control: ModuleType,
    risk: ModuleType,
    arm: Arm,
    *,
    start: int,
    right: int,
    slippage: float = BASE_SLIPPAGE,
    daily_action_lag: int = 0,
    include_funding: bool = True,
) -> dict[str, Any]:
    """Replay one fixed sizing arm on the exact SNC02 plus MA05 path."""

    if not 0 <= start < right <= context.book.count:
        raise ValueError("invalid backtest window")
    if daily_action_lag < 0:
        raise ValueError("daily_action_lag must be nonnegative")
    cost_rate = float(context.engine.FEE) + slippage
    hourly_funding = funding_by_hour(context) if include_funding else {}

    equity = 1.0
    quantity = 0.0
    mark_price = float(context.book.open[start])
    position: Position | None = None
    pending: Pending | None = None
    trade_sequence = 0
    peak = 1.0
    peak_ts = pd.Timestamp(context.book.ts[start]).isoformat()
    mdd = 0.0
    worst_ts: str | None = None
    worst_peak_ts: str | None = None
    max_marked_leverage = 0.0
    total_cost = 0.0
    total_funding = 0.0
    total_turnover = 0.0
    exposure_hours = 0
    trades: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    def observe(ts: pd.Timestamp, price: float | None = None) -> None:
        nonlocal peak, peak_ts, mdd, worst_ts, worst_peak_ts, max_marked_leverage
        if not math.isfinite(equity):
            raise RuntimeError("nonfinite equity")
        if equity > peak:
            peak = equity
            peak_ts = ts.isoformat()
        drawdown = -1.0 if equity <= 0.0 else equity / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
            worst_peak_ts = peak_ts
        if price is not None and equity > 0.0:
            max_marked_leverage = max(
                max_marked_leverage,
                abs(quantity) * price / equity,
            )

    def mark_to(ts: pd.Timestamp, price: float) -> None:
        nonlocal equity, mark_price
        if not math.isfinite(price) or price <= 0.0:
            raise RuntimeError("invalid mark price")
        if quantity:
            equity += quantity * (price - mark_price)
        mark_price = price
        observe(ts, price)

    def rebalance(
        ts: pd.Timestamp,
        price: float,
        target_side: int,
        leverage: float,
    ) -> tuple[float, float]:
        nonlocal equity, quantity, mark_price, total_cost, total_turnover
        mark_to(ts, price)
        before = equity
        new_qty, after, turnover = risk.target_quantity(
            equity,
            quantity,
            target_side,
            price,
            cost_rate,
            leverage,
        )
        cost = before - after
        equity = after
        quantity = new_qty
        mark_price = price
        total_cost += cost
        total_turnover += turnover
        observe(ts, price)
        return cost, turnover

    def enter(ts: pd.Timestamp, price: float, signal: Any) -> None:
        nonlocal position, trade_sequence
        if position is not None or quantity:
            raise RuntimeError("cannot enter while positioned")
        entry_equity = equity
        target_side = int(signal.target_side)
        cost, turnover = rebalance(
            ts,
            price,
            target_side,
            arm.entry_leverage,
        )
        trade_sequence += 1
        position = Position(
            trade_id=trade_sequence,
            side=target_side,
            signal_ts=pd.Timestamp(signal.ts),
            entry_ts=ts,
            entry_price=price,
            entry_equity=entry_equity,
            entry_leverage=arm.entry_leverage,
            quantity=quantity,
            trade_cost=cost,
            trade_turnover=turnover,
        )
        actions.append(
            {
                "action": "enter_long" if target_side > 0 else "enter_short",
                "ts": ts.isoformat(),
                "price": price,
                "signal_ts": pd.Timestamp(signal.ts).isoformat(),
                "trade_id": trade_sequence,
                "target_leverage": arm.entry_leverage,
            }
        )

    def promote(ts: pd.Timestamp, price: float, trade_id: int) -> None:
        if position is None or position.trade_id != trade_id or position.promoted:
            return
        if arm.promotion_leverage is None:
            raise RuntimeError("promotion requested for fixed arm")
        cost, turnover = rebalance(
            ts,
            price,
            position.side,
            arm.promotion_leverage,
        )
        position.quantity = quantity
        position.trade_cost += cost
        position.trade_turnover += turnover
        position.promoted = True
        position.promotion_ts = ts
        position.promotion_price = price
        actions.append(
            {
                "action": "promote_to_1x",
                "ts": ts.isoformat(),
                "price": price,
                "trade_id": position.trade_id,
                "target_leverage": arm.promotion_leverage,
                "confirmation_days": arm.confirmation_days,
            }
        )

    def close(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal position, quantity
        if position is None:
            return
        old = position
        cost, turnover = rebalance(ts, price, 0, 1.0)
        old.trade_cost += cost
        old.trade_turnover += turnover
        net_pnl = equity - old.entry_equity
        trades.append(
            {
                "trade_id": old.trade_id,
                "side": "long" if old.side > 0 else "short",
                "signal_ts": old.signal_ts.isoformat(),
                "entry_ts": old.entry_ts.isoformat(),
                "entry_price": old.entry_price,
                "entry_leverage": old.entry_leverage,
                "exit_ts": ts.isoformat(),
                "exit_price": price,
                "exit_reason": reason,
                "bars": (ts - old.entry_ts).total_seconds() / 86_400.0,
                "gross_return_pct": old.side
                * (price / old.entry_price - 1.0)
                * 100.0,
                "net_return_pct": net_pnl / old.entry_equity * 100.0,
                "net_pnl": net_pnl,
                "funding_pnl": old.funding_pnl,
                "cost_equity_units": old.trade_cost,
                "turnover_multiple": old.trade_turnover,
                "promoted": old.promoted,
                "promotion_ts": (
                    None if old.promotion_ts is None else old.promotion_ts.isoformat()
                ),
                "promotion_price": old.promotion_price,
            }
        )
        actions.append(
            {
                "action": "exit_long" if old.side > 0 else "exit_short",
                "ts": ts.isoformat(),
                "price": price,
                "reason": reason,
                "trade_id": old.trade_id,
            }
        )
        quantity = 0.0
        position = None

    def execute_pending(index: int, ts: pd.Timestamp, price: float) -> None:
        nonlocal pending
        if pending is None or pending.due_index != index:
            return
        item = pending
        pending = None
        if item.kind == "signal":
            if position is not None and position.side != item.target_side:
                close(ts, price, "opposite_qualified_cross")
            if position is None and item.signal is not None:
                enter(ts, price, item.signal)
        elif item.kind == "exit":
            if position is not None and position.trade_id == item.trade_id:
                close(ts, price, item.reason)
        elif item.kind == "promotion":
            if item.trade_id is not None:
                promote(ts, price, item.trade_id)
        else:
            raise RuntimeError(f"unknown pending kind: {item.kind}")

    observe(pd.Timestamp(context.book.ts[start]), mark_price)
    for index in range(start, right):
        day_ts = pd.Timestamp(context.book.ts[index])
        for hour in range(24):
            hour_ts = day_ts + pd.Timedelta(hours=hour)
            hour_open = float(context.features.hourly_open[index, hour])
            mark_to(hour_ts, hour_open)
            if hour == 0:
                execute_pending(index, hour_ts, hour_open)

            for event in hourly_funding.get(hour_ts, []):
                if position is None:
                    break
                event_ts = pd.Timestamp(event.ts)
                event_price = float(event.price)
                mark_to(event_ts, event_price)
                payment = quantity * event_price * float(event.rate)
                equity -= payment
                total_funding += payment
                position.funding_pnl -= payment
                observe(event_ts, event_price)
            if position is not None:
                exposure_hours += 1

        close_value = float(context.book.close[index])
        signal = control.qualified_signal(context, index)

        if position is not None and not position.promoted and arm.confirmation_days:
            ma7 = float(context.features.ma7[index])
            previous_ma7 = (
                float(context.features.ma7[index - 1]) if index else math.nan
            )
            atr7 = float(context.features.atr7[index])
            confirmation = (
                all(
                    math.isfinite(value)
                    for value in (close_value, ma7, previous_ma7, atr7)
                )
                and atr7 > 0.0
                and position.side * (close_value - position.entry_price) > 0.0
                and position.side * (close_value - ma7) >= 0.0
                and position.side * (ma7 - previous_ma7) / atr7
                >= CONFIRM_SLOPE_ATR
            )
            if confirmation:
                position.confirmation_count += 1
            else:
                position.confirmation_count = 0
            actions.append(
                {
                    "action": "confirmation_observation",
                    "ts": day_ts.isoformat(),
                    "trade_id": position.trade_id,
                    "passed": confirmation,
                    "consecutive": position.confirmation_count,
                }
            )

        if pending is not None:
            continue
        due = index + 1 + daily_action_lag
        if due >= right:
            continue
        current_side = 0 if position is None else position.side
        if signal is not None and signal.target_side != current_side:
            pending = Pending(
                due_index=due,
                kind="signal",
                reason="opposite_qualified_cross",
                target_side=signal.target_side,
                signal=signal,
                trade_id=None if position is None else position.trade_id,
            )
            continue
        if position is None:
            continue

        ma7 = float(context.features.ma7[index])
        previous_ma7 = float(context.features.ma7[index - 1]) if index else math.nan
        atr7 = float(context.features.atr7[index])
        slope = ma7 - previous_ma7
        buffer = MA_EXIT_BUFFER_ATR * atr7
        ma_exit = (
            position.side > 0
            and close_value < ma7 - buffer
            and slope <= 0.0
        ) or (
            position.side < 0
            and close_value > ma7 + buffer
            and slope >= 0.0
        )
        if ma_exit:
            pending = Pending(
                due_index=due,
                kind="exit",
                reason="ma7_structure_exit_0p5atr",
                trade_id=position.trade_id,
            )
            continue

        if (
            not position.promoted
            and arm.confirmation_days
            and position.confirmation_count >= arm.confirmation_days
        ):
            pending = Pending(
                due_index=due,
                kind="promotion",
                reason=f"promotion_after_{arm.confirmation_days}d_confirmation",
                trade_id=position.trade_id,
            )

    end_ts, end_price = terminal_point(context, right)
    mark_to(end_ts, end_price)
    if position is not None:
        close(end_ts, end_price, "terminal_flatten")

    positive = sum(max(0.0, float(row["net_pnl"])) for row in trades)
    negative = -sum(min(0.0, float(row["net_pnl"])) for row in trades)
    duration_hours = (right - start) * 24
    side_pnl = {
        side: sum(float(row["net_pnl"]) for row in trades if row["side"] == side)
        for side in ("long", "short")
    }
    exit_counts = Counter(str(row["exit_reason"]) for row in trades)
    action_counts = Counter(str(row["action"]) for row in actions)
    metrics = {
        "arm_id": arm.arm_id,
        "start_ts": pd.Timestamp(context.book.ts[start]).isoformat(),
        "end_ts": end_ts.isoformat(),
        "days": right - start,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "chronological_1h_mdd_pct": mdd * 100.0,
        "worst_peak_ts": worst_peak_ts,
        "worst_ts": worst_ts,
        "closed_trades": len(trades),
        "long_trades": sum(row["side"] == "long" for row in trades),
        "short_trades": sum(row["side"] == "short" for row in trades),
        "win_rate": (
            sum(float(row["net_pnl"]) > 0.0 for row in trades) / len(trades)
            if trades
            else 0.0
        ),
        "profit_factor": positive / negative if negative > 0.0 else math.inf,
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "exposure_pct": exposure_hours / duration_hours * 100.0,
        "max_marked_leverage": max_marked_leverage,
        "long_net_pnl_equity_units": side_pnl["long"],
        "short_net_pnl_equity_units": side_pnl["short"],
        "exit_counts": dict(exit_counts),
        "action_counts": dict(action_counts),
        "promoted_trades": sum(bool(row["promoted"]) for row in trades),
        "terminal_censored_trades": exit_counts.get("terminal_flatten", 0),
    }
    return {"metrics": metrics, "trades": trades, "actions": actions}


def run(force: bool = False) -> dict[str, Any]:
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_stage_b_control")
    stage_a = load_module(STAGE_A_SCRIPT_PATH, "snc02_stage_b_stage_a")
    risk = load_module(RISK_PATH, "snc02_stage_b_risk")
    context = stage_a.load_context(control)
    retained_stage_a = json.loads(STAGE_A_ARTIFACT_PATH.read_text(encoding="utf-8"))

    primary: dict[str, Any] = {}
    canonical: dict[str, Any] = {}
    stress: dict[str, Any] = {}
    recent: dict[str, Any] = {}
    calendar: dict[str, Any] = {}
    ledgers: dict[str, Any] = {}
    for arm in ARMS:
        extended_run = run_arm(
            context,
            control,
            risk,
            arm,
            start=0,
            right=context.book.count,
        )
        canonical_run = run_arm(
            context,
            control,
            risk,
            arm,
            start=0,
            right=CANONICAL_RIGHT,
        )
        primary[arm.arm_id] = extended_run["metrics"]
        canonical[arm.arm_id] = canonical_run["metrics"]
        ledgers[arm.arm_id] = {
            "trades": extended_run["trades"],
            "actions": extended_run["actions"],
        }

        stress[arm.arm_id] = {}
        for label, slippage, lag, funding in (
            ("slippage_8bps", STRESS_SLIPPAGE, 0, True),
            ("lag_1d", BASE_SLIPPAGE, 1, True),
            ("funding_off", BASE_SLIPPAGE, 0, False),
        ):
            result = run_arm(
                context,
                control,
                risk,
                arm,
                start=0,
                right=context.book.count,
                slippage=slippage,
                daily_action_lag=lag,
                include_funding=funding,
            )
            stress[arm.arm_id][label] = result["metrics"]

        recent[arm.arm_id] = {}
        for label, days in RECENT_SLICES.items():
            result = run_arm(
                context,
                control,
                risk,
                arm,
                start=max(0, context.book.count - days),
                right=context.book.count,
            )
            recent[arm.arm_id][label] = result["metrics"]

        calendar[arm.arm_id] = {}
        for label, (left, right) in {
            "2025_partial": (
                0,
                index_at_or_after(context, "2026-01-01T00:00:00Z"),
            ),
            "2026_ytd": (
                index_at_or_after(context, "2026-01-01T00:00:00Z"),
                context.book.count,
            ),
        }.items():
            result = run_arm(
                context,
                control,
                risk,
                arm,
                start=left,
                right=right,
            )
            calendar[arm.arm_id][label] = result["metrics"]

    baseline_expected = retained_stage_a["primary_extended"]["MA05"]
    canonical_expected = retained_stage_a["canonical"]["MA05"]
    parity: dict[str, dict[str, bool]] = {}
    for label, actual, expected in (
        ("extended", primary["MA05_1X"], baseline_expected),
        ("canonical", canonical["MA05_1X"], canonical_expected),
    ):
        checks = {
            key: math.isclose(
                float(actual[key]),
                float(expected[key]),
                rel_tol=0.0,
                abs_tol=2e-10,
            )
            for key in (
                "net_return_pct",
                "chronological_1h_mdd_pct",
                "closed_trades",
                "cost_pct_initial",
                "funding_pct_initial",
            )
        }
        if not all(checks.values()):
            raise RuntimeError(f"{label} MA05 parity failed: {checks}")
        parity[label] = checks

    baseline_return = float(primary["MA05_1X"]["net_return_pct"])
    baseline_latest = next(
        row
        for row in ledgers["MA05_1X"]["trades"]
        if row["entry_ts"] == "2026-08-09T00:00:00+00:00"
    )
    baseline_latest_return = float(baseline_latest["net_return_pct"])
    verdict: dict[str, Any] = {}
    for arm in ARMS:
        arm_id = arm.arm_id
        metrics = primary[arm_id]
        latest_trade = next(
            (
                row
                for row in reversed(ledgers[arm_id]["trades"])
                if row["entry_ts"] == "2026-08-09T00:00:00+00:00"
            ),
            None,
        )
        mdd20 = float(metrics["chronological_1h_mdd_pct"]) >= -20.0
        robust = (
            float(metrics["net_return_pct"]) > 0.0
            and float(metrics["profit_factor"]) >= 1.0
            and float(stress[arm_id]["slippage_8bps"]["net_return_pct"]) > 0.0
            and float(stress[arm_id]["lag_1d"]["net_return_pct"]) > 0.0
        )
        return_retention = (
            float(metrics["net_return_pct"])
            >= RETURN_RETENTION_FRACTION * baseline_return
        )
        latest_capture = (
            latest_trade is not None
            and latest_trade["exit_reason"] == "terminal_flatten"
            and float(latest_trade["net_return_pct"])
            >= LATEST_CAPTURE_FRACTION * baseline_latest_return
        )
        verdict[arm_id] = {
            "mdd20_pass": mdd20,
            "robustness_pass": robust,
            "return_retention_pass": return_retention,
            "latest_trend_capture_pass": latest_capture,
            "continuation_candidate": (
                mdd20 and robust and return_retention and latest_capture
            ),
            "latest_august_long": latest_trade,
            "status": "POST_REVEAL_DIAGNOSTIC_ONLY",
        }

    payload = {
        "schema": "hype-1d-ma7-snc02-ma05-probe-sizing-stage-b-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-MA05-SIZING-STAGE-B",
        "arms": {arm.arm_id: arm_config(arm) for arm in ARMS},
        "frozen_mechanism": {
            "signal": "SNC02 exact",
            "ma_exit_buffer_atr": MA_EXIT_BUFFER_ATR,
            "confirmation_slope_atr": CONFIRM_SLOPE_ATR,
            "confirmation": [
                "directional close versus original entry > 0",
                "close remains on directional SMA7 side",
                "directional SMA7 slope / ATR7 >= 0.02",
            ],
            "promotion": "next UTC open rebalance to 1x at current equity",
        },
        "execution": {
            "daily_conditions": "closed UTC day, next UTC open",
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
            "priority": "opposite SNC02 signal > MA05 exit > promotion",
        },
        "gates": {
            "mdd_floor_pct": -20.0,
            "return_retention_fraction_of_ma05_1x": RETURN_RETENTION_FRACTION,
            "latest_capture_fraction_of_ma05_1x": LATEST_CAPTURE_FRACTION,
            "baseline_return_pct": baseline_return,
            "baseline_latest_august_long_return_pct": baseline_latest_return,
        },
        "data_audit": sanitize(context.market.audit),
        "primary_extended": primary,
        "canonical": canonical,
        "stress": stress,
        "recent_slices": recent,
        "calendar_flat_start": calendar,
        "ledgers": ledgers,
        "ma05_parity": parity,
        "verdict": verdict,
        "decision": {
            "stage_b_sizing_only": True,
            "exit_overlay_changed": False,
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "stage_a_script_sha256": sha256(STAGE_A_SCRIPT_PATH),
            "stage_a_artifact_sha256": sha256(STAGE_A_ARTIFACT_PATH),
            "risk_engine_sha256": sha256(RISK_PATH),
        },
        "notes": [
            "All outcomes are revealed-history diagnostic evidence.",
            "Fixed sizing arms are risk-scaling references and do not create alpha.",
            "Terminal flatten is censoring and a common valuation cut, not mature take-profit logic.",
        ],
    }
    document = (
        json.dumps(sanitize(payload), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n"
    )
    sidecar = Path(f"{OUTPUT_PATH}.sha256")
    if (OUTPUT_PATH.exists() or sidecar.exists()) and not force:
        raise RuntimeError(f"locked artifact exists: {OUTPUT_PATH.name}")
    OUTPUT_PATH.write_text(document, encoding="utf-8")
    digest = hashlib.sha256(document.encode()).hexdigest()
    sidecar.write_text(f"{digest}  {OUTPUT_PATH.name}\n", encoding="utf-8")
    return {"output": str(OUTPUT_PATH), "sha256": digest, "payload": payload}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "CONTRACT_FROZEN_NOT_RUN",
                    "contract": str(CONTRACT_PATH),
                    "arms": [arm_config(arm) for arm in ARMS],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    result = run(force=args.force)
    payload = result["payload"]
    print(
        json.dumps(
            {
                "output": result["output"],
                "sha256": result["sha256"],
                "primary_extended": payload["primary_extended"],
                "stress": payload["stress"],
                "verdict": payload["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
