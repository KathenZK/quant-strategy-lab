"""Run frozen SNC02 MA05 equity-drawdown governor Stage D."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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
    / "specs/hype-1d-ma7-snc02-ma05-equity-drawdown-governor-stage-d-contract-2026-08-20.md"
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
    / "hype_1d_ma7_snc02_ma05_equity_drawdown_governor_stage_d_2026-08-20.json"
)

BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
MA_EXIT_BUFFER_ATR = 0.5
RETURN_RETENTION_FRACTION = 0.50
LATEST_CAPTURE_FRACTION = 0.60
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


@dataclass(frozen=True, slots=True)
class Arm:
    arm_id: str
    trigger_drawdown: float | None
    low_leverage: float = 1.0
    recovery_drawdown: float | None = None


ARMS = (
    Arm("MA05_CTRL", None),
    Arm("DG08_L50_R04", -0.08, 0.50, -0.04),
    Arm("DG10_L50_R05", -0.10, 0.50, -0.05),
    Arm("DG08_L25_R04", -0.08, 0.25, -0.04),
    Arm("DG10_L25_R05", -0.10, 0.25, -0.05),
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
    funding_pnl: float = 0.0
    trade_cost: float = 0.0
    trade_turnover: float = 0.0
    resize_events: list[dict[str, Any]] = field(default_factory=list)


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
        "trigger_drawdown": arm.trigger_drawdown,
        "low_leverage": arm.low_leverage,
        "recovery_drawdown": arm.recovery_drawdown,
        "normal_leverage": 1.0,
        "ma_exit_buffer_atr": MA_EXIT_BUFFER_ATR,
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


def make_control_schedule(
    context: Any,
    control: ModuleType,
    stage_a: ModuleType,
    risk: ModuleType,
    *,
    start: int,
    right: int,
    slippage: float,
    daily_action_lag: int,
    include_funding: bool,
) -> tuple[dict[pd.Timestamp, list[dict[str, Any]]], dict[str, Any]]:
    engine_arm = stage_a.Arm(
        arm_id="MA05_SCHEDULE",
        ma_exit_buffer_atr=MA_EXIT_BUFFER_ATR,
    )
    result = stage_a.run_arm(
        context,
        control,
        risk,
        engine_arm,
        start=start,
        right=right,
        slippage=slippage,
        daily_action_lag=daily_action_lag,
        include_funding=include_funding,
    )
    schedule: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    for action in result["actions"]:
        if action.get("reason") == "terminal_flatten":
            continue
        schedule[pd.Timestamp(action["ts"])].append(action)
    return dict(schedule), result["metrics"]


def run_arm(
    context: Any,
    control: ModuleType,
    stage_a: ModuleType,
    risk: ModuleType,
    arm: Arm,
    *,
    start: int,
    right: int,
    slippage: float = BASE_SLIPPAGE,
    daily_action_lag: int = 0,
    include_funding: bool = True,
) -> dict[str, Any]:
    if not 0 <= start < right <= context.book.count:
        raise ValueError("invalid backtest window")
    if daily_action_lag < 0:
        raise ValueError("daily_action_lag must be nonnegative")

    control_schedule, schedule_metrics = make_control_schedule(
        context,
        control,
        stage_a,
        risk,
        start=start,
        right=right,
        slippage=slippage,
        daily_action_lag=daily_action_lag,
        include_funding=include_funding,
    )
    hourly_funding = funding_by_hour(context) if include_funding else {}
    cost_rate = float(context.engine.FEE) + slippage

    equity = 1.0
    quantity = 0.0
    mark_price = float(context.book.open[start])
    position: Position | None = None
    trade_sequence = 0
    peak = 1.0
    mdd = 0.0
    worst_ts: str | None = None
    max_marked_leverage = 0.0
    total_cost = 0.0
    total_funding = 0.0
    total_turnover = 0.0
    exposure_hours = 0
    low_state_hours = 0
    low_exposure_hours = 0
    daily_hwm = 1.0
    desired_leverage = 1.0
    effective_leverage = 1.0
    risk_queue: dict[int, list[dict[str, Any]]] = defaultdict(list)
    trades: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    def observe(ts: pd.Timestamp, price: float | None = None) -> None:
        nonlocal peak, mdd, worst_ts, max_marked_leverage
        if not math.isfinite(equity):
            raise RuntimeError("nonfinite equity")
        peak = max(peak, equity)
        drawdown = -1.0 if equity <= 0.0 else equity / peak - 1.0
        if drawdown < mdd:
            mdd = drawdown
            worst_ts = ts.isoformat()
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
        target_leverage: float,
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
            target_leverage,
        )
        cost = before - after
        equity = after
        quantity = new_qty
        mark_price = price
        total_cost += cost
        total_turnover += turnover
        observe(ts, price)
        return cost, turnover

    def enter(ts: pd.Timestamp, price: float, source: dict[str, Any]) -> None:
        nonlocal position, trade_sequence
        if position is not None or quantity:
            raise RuntimeError("cannot enter while positioned")
        target_side = 1 if source["action"] == "enter_long" else -1
        entry_equity = equity
        cost, turnover = rebalance(
            ts,
            price,
            target_side,
            effective_leverage,
        )
        trade_sequence += 1
        position = Position(
            trade_id=trade_sequence,
            side=target_side,
            signal_ts=pd.Timestamp(source["signal_ts"]),
            entry_ts=ts,
            entry_price=price,
            entry_equity=entry_equity,
            entry_leverage=effective_leverage,
            trade_cost=cost,
            trade_turnover=turnover,
        )
        actions.append(
            {
                "action": source["action"],
                "ts": ts.isoformat(),
                "price": price,
                "signal_ts": source["signal_ts"],
                "trade_id": trade_sequence,
                "target_leverage": effective_leverage,
            }
        )

    def close(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal position, quantity
        if position is None:
            raise RuntimeError("cannot execute scheduled exit while flat")
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
                "resize_events": old.resize_events,
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

    def resize_for_state(ts: pd.Timestamp, price: float, target: float) -> None:
        if position is None:
            return
        before_leverage = (
            abs(quantity) * price / equity if equity > 0.0 else math.inf
        )
        cost, turnover = rebalance(ts, price, position.side, target)
        event = {
            "action": "risk_resize",
            "ts": ts.isoformat(),
            "price": price,
            "trade_id": position.trade_id,
            "previous_marked_leverage": before_leverage,
            "target_leverage": target,
            "cost_equity_units": cost,
            "turnover_multiple": turnover,
        }
        position.trade_cost += cost
        position.trade_turnover += turnover
        position.resize_events.append(event)
        actions.append(event)

    def execute_open(index: int, ts: pd.Timestamp, price: float) -> None:
        nonlocal effective_leverage
        due = risk_queue.pop(index, [])
        if due:
            previous = effective_leverage
            effective_leverage = float(due[-1]["target_leverage"])
            actions.append(
                {
                    "action": "risk_state_effective",
                    "ts": ts.isoformat(),
                    "previous_leverage": previous,
                    "target_leverage": effective_leverage,
                    "source_day_ts": due[-1]["source_day_ts"],
                    "source_drawdown": due[-1]["source_drawdown"],
                }
            )

        scheduled = control_schedule.get(ts, [])
        entered_at_open = False
        for item in scheduled:
            reference_price = float(item["price"])
            if not math.isclose(reference_price, price, rel_tol=0.0, abs_tol=1e-10):
                raise RuntimeError("control schedule/open price mismatch")
            if item["action"] in ("exit_long", "exit_short"):
                close(ts, price, str(item["reason"]))
            elif item["action"] in ("enter_long", "enter_short"):
                enter(ts, price, item)
                entered_at_open = True
            else:
                raise RuntimeError(f"unknown control action: {item['action']}")

        if due and position is not None and not entered_at_open:
            resize_for_state(ts, price, effective_leverage)

    observe(pd.Timestamp(context.book.ts[start]), mark_price)
    for index in range(start, right):
        day_ts = pd.Timestamp(context.book.ts[index])
        for hour in range(24):
            hour_ts = day_ts + pd.Timedelta(hours=hour)
            hour_open = float(context.features.hourly_open[index, hour])
            mark_to(hour_ts, hour_open)
            if hour == 0:
                execute_open(index, hour_ts, hour_open)

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

            if effective_leverage < 1.0:
                low_state_hours += 1
            if position is not None:
                exposure_hours += 1
                if effective_leverage < 1.0:
                    low_exposure_hours += 1

        close_value = float(context.book.close[index])
        daily_marked_equity = equity + quantity * (close_value - mark_price)
        if not math.isfinite(daily_marked_equity) or daily_marked_equity <= 0.0:
            raise RuntimeError("invalid daily marked equity")
        daily_hwm = max(daily_hwm, daily_marked_equity)
        daily_drawdown = daily_marked_equity / daily_hwm - 1.0

        target = desired_leverage
        reason = None
        if arm.trigger_drawdown is not None:
            if desired_leverage == 1.0 and daily_drawdown <= arm.trigger_drawdown:
                target = arm.low_leverage
                reason = "drawdown_trigger"
            elif (
                desired_leverage < 1.0
                and arm.recovery_drawdown is not None
                and daily_drawdown >= arm.recovery_drawdown
            ):
                target = 1.0
                reason = "drawdown_recovery"

        if target != desired_leverage:
            desired_leverage = target
            due_index = index + 1 + daily_action_lag
            signal = {
                "action": "risk_state_signal",
                "source_day_ts": day_ts.isoformat(),
                "source_drawdown": daily_drawdown,
                "daily_marked_equity": daily_marked_equity,
                "daily_hwm": daily_hwm,
                "target_leverage": target,
                "reason": reason,
                "due_index": due_index,
            }
            actions.append(signal)
            if due_index < right:
                risk_queue[due_index].append(signal)

    end_ts, end_price = terminal_point(context, right)
    mark_to(end_ts, end_price)
    terminal_effective_leverage = effective_leverage
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
        "low_risk_state_pct": low_state_hours / duration_hours * 100.0,
        "low_risk_exposure_pct": low_exposure_hours / duration_hours * 100.0,
        "max_marked_leverage": max_marked_leverage,
        "long_net_pnl_equity_units": side_pnl["long"],
        "short_net_pnl_equity_units": side_pnl["short"],
        "exit_counts": dict(exit_counts),
        "action_counts": dict(action_counts),
        "derisk_signals": sum(
            row.get("reason") == "drawdown_trigger" for row in actions
        ),
        "recovery_signals": sum(
            row.get("reason") == "drawdown_recovery" for row in actions
        ),
        "risk_resizes": action_counts.get("risk_resize", 0),
        "terminal_effective_leverage": terminal_effective_leverage,
        "terminal_desired_leverage": desired_leverage,
        "terminal_daily_hwm": daily_hwm,
        "terminal_censored_trades": exit_counts.get("terminal_flatten", 0),
    }
    return {
        "metrics": metrics,
        "trades": trades,
        "actions": actions,
        "schedule_metrics": schedule_metrics,
    }


def run(force: bool = False) -> dict[str, Any]:
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_stage_d_control")
    stage_a = load_module(STAGE_A_SCRIPT_PATH, "snc02_stage_d_engine")
    risk = load_module(RISK_PATH, "snc02_stage_d_risk")
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
            stage_a,
            risk,
            arm,
            start=0,
            right=context.book.count,
        )
        canonical_run = run_arm(
            context,
            control,
            stage_a,
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
                stage_a,
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
                stage_a,
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
                stage_a,
                risk,
                arm,
                start=left,
                right=right,
            )
            calendar[arm.arm_id][label] = result["metrics"]

    parity: dict[str, dict[str, bool]] = {}
    for label, actual, expected in (
        (
            "extended",
            primary["MA05_CTRL"],
            retained_stage_a["primary_extended"]["MA05"],
        ),
        (
            "canonical",
            canonical["MA05_CTRL"],
            retained_stage_a["canonical"]["MA05"],
        ),
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

    baseline_return = float(primary["MA05_CTRL"]["net_return_pct"])
    baseline_latest = next(
        row
        for row in ledgers["MA05_CTRL"]["trades"]
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
        "schema": "hype-1d-ma7-snc02-ma05-equity-dd-governor-stage-d-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-MA05-EQUITY-DD-GOVERNOR-STAGE-D",
        "arms": {arm.arm_id: arm_config(arm) for arm in ARMS},
        "execution": {
            "risk_signal": "closed UTC daily marked equity versus actual HWM",
            "risk_execution": "next UTC open; current position and future entries",
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate on actual quantity",
            "control_path": "exact SNC02 plus MA05 schedule",
        },
        "gates": {
            "mdd_floor_pct": -20.0,
            "return_retention_fraction_of_ma05_control": RETURN_RETENTION_FRACTION,
            "latest_capture_fraction_of_ma05_control": LATEST_CAPTURE_FRACTION,
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
            "stage_d_governor_only": True,
            "signal_or_exit_path_changed": False,
            "grid_extended_after_reveal": False,
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "stage_a_engine_sha256": sha256(STAGE_A_SCRIPT_PATH),
            "stage_a_artifact_sha256": sha256(STAGE_A_ARTIFACT_PATH),
            "risk_engine_sha256": sha256(RISK_PATH),
        },
        "notes": [
            "All outcomes are revealed-history diagnostic evidence.",
            "The governor changes risk exposure, not the underlying alpha path.",
            "Every flat-start slice resets equity and HWM to 1.0.",
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
