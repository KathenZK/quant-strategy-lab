"""Run the frozen SNC02 single-variable risk-overlay attribution study."""

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
from types import ModuleType, SimpleNamespace
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
CONTRACT_PATH = (
    FAMILY_DIR
    / "specs/hype-1d-ma7-snc02-risk-overlay-oat-contract-2026-08-20.md"
)
CONTROL_SCRIPT_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_symmetric_naked_cross_slope.py"
)
RISK_PATH = SCRIPT_DIR / "hype_1d_ma7_trend_phase_risk_metrics.py"
CONTROL_ARTIFACT_PATH = (
    ARTIFACT_DIR / "hype_1d_ma7_symmetric_naked_cross_slope_2026-08-20.json"
)
OUTPUT_PATH = ARTIFACT_DIR / "hype_1d_ma7_snc02_risk_overlay_oat_2026-08-20.json"

BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
CANONICAL_RIGHT = 432
RECENT_SLICES = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}


@dataclass(frozen=True, slots=True)
class Arm:
    arm_id: str
    fail_fast_days: int = 0
    ma_exit_buffer_atr: float | None = None
    hard_stop_atr: float | None = None
    breakeven_activation_atr: float | None = None
    partial_activation_atr: float | None = None
    partial_fraction: float = 0.0


ARMS = (
    Arm("CTRL_SNC02"),
    Arm("FF3", fail_fast_days=3),
    Arm("MA05", ma_exit_buffer_atr=0.5),
    Arm("HS25", hard_stop_atr=2.5),
    Arm("BE20", breakeven_activation_atr=2.0),
    Arm("PT25_A3", partial_activation_atr=3.0, partial_fraction=0.25),
)


@dataclass(slots=True)
class Position:
    trade_id: int
    side: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_equity: float
    entry_atr: float
    signal_ts: pd.Timestamp
    quantity: float
    held_days: int = 0
    highest_close: float = -math.inf
    lowest_close: float = math.inf
    be_active: bool = False
    partial_done: bool = False
    funding_pnl: float = 0.0
    trade_cost: float = 0.0
    trade_turnover: float = 0.0
    partial_quantity: float = 0.0


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


def load_context(control: ModuleType) -> Any:
    adapter = control.load_module(control.ADAPTER_PATH, "snc02_oat_adapter")
    frozen = adapter.load_context()
    original = frozen.original_harness
    original.HOURLY_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    original.FUNDING_CUTOFF = pd.Timestamp("2100-01-01T00:00:00Z")
    market = original.load_market(0)
    return SimpleNamespace(
        market=market,
        book=market.book,
        features=market.features,
        engine=frozen.engine,
    )


def funding_by_hour(context: Any) -> dict[pd.Timestamp, list[Any]]:
    grouped: dict[pd.Timestamp, list[Any]] = defaultdict(list)
    events = [event for daily in context.features.funding_events for event in daily]
    for event in sorted(events, key=lambda row: pd.Timestamp(row.ts)):
        grouped[pd.Timestamp(event.ts).floor("h")].append(event)
    return grouped


def stop_fill(
    side: int,
    stop: float,
    hour_open: float,
    hour_high: float,
    hour_low: float,
) -> float | None:
    """Return an executable stop reference with adverse gap handling."""

    if side > 0:
        if hour_open <= stop:
            return hour_open
        if hour_low <= stop:
            return stop
    else:
        if hour_open >= stop:
            return hour_open
        if hour_high >= stop:
            return stop
    return None


def breakeven_price(entry_price: float, side: int, cost_rate: float) -> float:
    if side > 0:
        return entry_price * (1.0 + cost_rate) / (1.0 - cost_rate)
    return entry_price * (1.0 - cost_rate) / (1.0 + cost_rate)


def terminal_point(context: Any, right: int) -> tuple[pd.Timestamp, float]:
    if right < context.book.count:
        return pd.Timestamp(context.book.ts[right]), float(context.book.open[right])
    return (
        pd.Timestamp(context.book.terminal_ts),
        float(context.book.quality["terminal_open"]),
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
    retain_path: bool = False,
) -> dict[str, Any]:
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
    mdd = 0.0
    worst_ts: str | None = None
    max_marked_leverage = 0.0
    total_cost = 0.0
    total_funding = 0.0
    total_turnover = 0.0
    exposure_hours = 0
    trades: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []

    def observe(ts: pd.Timestamp, kind: str, price: float | None = None) -> None:
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
        if retain_path:
            path.append(
                {
                    "ts": ts.isoformat(),
                    "equity": equity,
                    "kind": kind,
                    "price": price,
                    "side": 0 if position is None else position.side,
                    "quantity": quantity,
                }
            )

    def mark_to(ts: pd.Timestamp, price: float, kind: str) -> None:
        nonlocal equity, mark_price
        if not math.isfinite(price) or price <= 0.0:
            raise RuntimeError("invalid mark price")
        if quantity:
            equity += quantity * (price - mark_price)
        mark_price = price
        observe(ts, kind, price)

    def rebalance(
        ts: pd.Timestamp,
        price: float,
        target_side: int,
        leverage: float,
        kind: str,
    ) -> tuple[float, float]:
        nonlocal equity, quantity, mark_price, total_cost, total_turnover
        mark_to(ts, price, f"{kind}_pre")
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
        observe(ts, f"{kind}_post", price)
        return cost, turnover

    def enter(ts: pd.Timestamp, price: float, signal: Any) -> None:
        nonlocal position, trade_sequence
        if position is not None or quantity:
            raise RuntimeError("cannot enter while positioned")
        target_side = int(signal.target_side)
        entry_equity = equity
        cost, turnover = rebalance(ts, price, target_side, 1.0, "entry")
        trade_sequence += 1
        entry_atr = float(context.features.atr7[signal.index])
        if not math.isfinite(entry_atr) or entry_atr <= 0.0:
            raise RuntimeError("invalid entry ATR")
        position = Position(
            trade_id=trade_sequence,
            side=target_side,
            entry_ts=ts,
            entry_price=price,
            entry_equity=entry_equity,
            entry_atr=entry_atr,
            signal_ts=pd.Timestamp(signal.ts),
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
            }
        )

    def close(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal position, quantity
        if position is None:
            return
        old = position
        old_side = old.side
        cost, turnover = rebalance(ts, price, 0, 1.0, "exit")
        old.trade_cost += cost
        old.trade_turnover += turnover
        net_pnl = equity - old.entry_equity
        trades.append(
            {
                "trade_id": old.trade_id,
                "side": "long" if old_side > 0 else "short",
                "signal_ts": old.signal_ts.isoformat(),
                "entry_ts": old.entry_ts.isoformat(),
                "entry_price": old.entry_price,
                "entry_atr": old.entry_atr,
                "exit_ts": ts.isoformat(),
                "exit_price": price,
                "exit_reason": reason,
                "bars": (ts - old.entry_ts).total_seconds() / 86_400.0,
                "gross_return_pct": old_side
                * (price / old.entry_price - 1.0)
                * 100.0,
                "net_return_pct": net_pnl / old.entry_equity * 100.0,
                "net_pnl": net_pnl,
                "funding_pnl": old.funding_pnl,
                "cost_equity_units": old.trade_cost,
                "turnover_multiple": old.trade_turnover,
                "partial_done": old.partial_done,
                "partial_quantity": old.partial_quantity,
                "be_active": old.be_active,
            }
        )
        actions.append(
            {
                "action": "exit_long" if old_side > 0 else "exit_short",
                "ts": ts.isoformat(),
                "price": price,
                "reason": reason,
                "trade_id": old.trade_id,
            }
        )
        quantity = 0.0
        position = None

    def partial_reduce(ts: pd.Timestamp, price: float) -> None:
        nonlocal equity, quantity, mark_price, total_cost, total_turnover
        if position is None or position.partial_done:
            return
        mark_to(ts, price, "partial_pre")
        reduction = quantity * arm.partial_fraction
        turnover = abs(reduction) * price
        cost = turnover * cost_rate
        equity -= cost
        quantity -= reduction
        mark_price = price
        total_cost += cost
        total_turnover += turnover
        position.quantity = quantity
        position.trade_cost += cost
        position.trade_turnover += turnover
        position.partial_quantity = reduction
        position.partial_done = True
        actions.append(
            {
                "action": "partial_reduce_25pct",
                "ts": ts.isoformat(),
                "price": price,
                "trade_id": position.trade_id,
                "quantity_reduced": reduction,
                "quantity_remaining": quantity,
            }
        )
        observe(ts, "partial_post", price)

    def active_stop() -> tuple[float, str] | None:
        if position is None:
            return None
        if arm.hard_stop_atr is not None:
            return (
                position.entry_price
                - position.side * arm.hard_stop_atr * position.entry_atr,
                "hard_stop_2p5atr",
            )
        if arm.breakeven_activation_atr is not None and position.be_active:
            return (
                breakeven_price(position.entry_price, position.side, cost_rate),
                "breakeven_stop_after_2atr",
            )
        return None

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
        elif item.kind == "partial":
            if position is not None and position.trade_id == item.trade_id:
                partial_reduce(ts, price)
        else:
            raise RuntimeError(f"unknown pending kind: {item.kind}")

    observe(pd.Timestamp(context.book.ts[start]), "start", mark_price)
    for index in range(start, right):
        day_ts = pd.Timestamp(context.book.ts[index])
        for hour in range(24):
            hour_ts = day_ts + pd.Timedelta(hours=hour)
            hour_open = float(context.features.hourly_open[index, hour])
            hour_high = float(context.features.hourly_high[index, hour])
            hour_low = float(context.features.hourly_low[index, hour])
            mark_to(hour_ts, hour_open, "hourly_open")
            if hour == 0:
                execute_pending(index, hour_ts, hour_open)

            stop = active_stop()
            if stop is not None and position is not None:
                level, reason = stop
                gap_fill = None
                if position.side > 0 and hour_open <= level:
                    gap_fill = hour_open
                elif position.side < 0 and hour_open >= level:
                    gap_fill = hour_open
                if gap_fill is not None:
                    close(hour_ts, gap_fill, reason)

            for event in hourly_funding.get(hour_ts, []):
                if position is None:
                    break
                event_ts = pd.Timestamp(event.ts)
                event_price = float(event.price)
                mark_to(event_ts, event_price, "funding_pre")
                payment = quantity * event_price * float(event.rate)
                equity -= payment
                total_funding += payment
                position.funding_pnl -= payment
                observe(event_ts, "funding_post", event_price)

            stop = active_stop()
            if stop is not None and position is not None:
                level, reason = stop
                fill = stop_fill(
                    position.side,
                    level,
                    hour_open,
                    hour_high,
                    hour_low,
                )
                if fill is not None:
                    close(hour_ts, fill, reason)
            if position is not None:
                exposure_hours += 1

        close_value = float(context.book.close[index])
        signal = control.qualified_signal(context, index)
        if position is not None:
            position.held_days += 1
            position.highest_close = max(position.highest_close, close_value)
            position.lowest_close = min(position.lowest_close, close_value)
            if (
                arm.breakeven_activation_atr is not None
                and not position.be_active
            ):
                best_close = (
                    position.highest_close
                    if position.side > 0
                    else position.lowest_close
                )
                directional_mfe = position.side * (best_close - position.entry_price)
                if directional_mfe >= (
                    arm.breakeven_activation_atr * position.entry_atr
                ):
                    position.be_active = True
                    actions.append(
                        {
                            "action": "activate_breakeven",
                            "ts": day_ts.isoformat(),
                            "trade_id": position.trade_id,
                            "directional_close_mfe_atr": directional_mfe
                            / position.entry_atr,
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

        previous_ma = float(context.features.ma7[index - 1]) if index else math.nan
        ma7 = float(context.features.ma7[index])
        atr7 = float(context.features.atr7[index])
        slope = ma7 - previous_ma
        fail_fast = False
        if arm.fail_fast_days and position.held_days <= arm.fail_fast_days:
            fail_fast = (
                position.side > 0 and close_value < ma7 and slope <= 0.0
            ) or (
                position.side < 0 and close_value > ma7 and slope >= 0.0
            )
        ma_exit = False
        if arm.ma_exit_buffer_atr is not None:
            buffer = arm.ma_exit_buffer_atr * atr7
            ma_exit = (
                position.side > 0
                and close_value < ma7 - buffer
                and slope <= 0.0
            ) or (
                position.side < 0
                and close_value > ma7 + buffer
                and slope >= 0.0
            )
        if fail_fast or ma_exit:
            pending = Pending(
                due_index=due,
                kind="exit",
                reason="fail_fast_ma7" if fail_fast else "ma7_structure_exit_0p5atr",
                trade_id=position.trade_id,
            )
            continue

        if (
            arm.partial_activation_atr is not None
            and not position.partial_done
        ):
            best_close = (
                position.highest_close
                if position.side > 0
                else position.lowest_close
            )
            directional_mfe = position.side * (best_close - position.entry_price)
            if directional_mfe >= arm.partial_activation_atr * position.entry_atr:
                pending = Pending(
                    due_index=due,
                    kind="partial",
                    reason="partial_25pct_after_3atr",
                    trade_id=position.trade_id,
                )

    end_ts, end_price = terminal_point(context, right)
    mark_to(end_ts, end_price, "terminal_mark")
    if position is not None:
        close(end_ts, end_price, "terminal_flatten")

    positive = sum(max(0.0, float(row["net_pnl"])) for row in trades)
    negative = -sum(min(0.0, float(row["net_pnl"])) for row in trades)
    duration_hours = (right - start) * 24
    side_pnl = {
        side: sum(float(row["net_pnl"]) for row in trades if row["side"] == side)
        for side in ("long", "short")
    }
    counts = Counter(str(row["exit_reason"]) for row in trades)
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
        "max_marked_leverage": max_marked_leverage,
        "long_net_pnl_equity_units": side_pnl["long"],
        "short_net_pnl_equity_units": side_pnl["short"],
        "exit_counts": dict(counts),
        "action_counts": dict(action_counts),
        "terminal_censored_trades": counts.get("terminal_flatten", 0),
    }
    return {
        "metrics": metrics,
        "trades": trades,
        "actions": actions,
        "path": path if retain_path else [],
    }


def index_at_or_after(context: Any, ts: str) -> int:
    target = pd.Timestamp(ts)
    return next(
        index
        for index, value in enumerate(context.book.ts)
        if pd.Timestamp(value) >= target
    )


def arm_config(arm: Arm) -> dict[str, Any]:
    return {
        "arm_id": arm.arm_id,
        "fail_fast_days": arm.fail_fast_days,
        "ma_exit_buffer_atr": arm.ma_exit_buffer_atr,
        "hard_stop_atr": arm.hard_stop_atr,
        "breakeven_activation_atr": arm.breakeven_activation_atr,
        "partial_activation_atr": arm.partial_activation_atr,
        "partial_fraction": arm.partial_fraction,
    }


def run(force: bool = False) -> dict[str, Any]:
    control = load_module(CONTROL_SCRIPT_PATH, "snc02_oat_control")
    risk = load_module(RISK_PATH, "snc02_oat_risk")
    context = load_context(control)
    retained_control = json.loads(CONTROL_ARTIFACT_PATH.read_text(encoding="utf-8"))

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
            retain_path=True,
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
            "path": extended_run["path"],
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

    control_checks = {}
    for window, actual, expected in (
        ("extended", primary["CTRL_SNC02"], retained_control["extended"]),
        ("canonical", canonical["CTRL_SNC02"], retained_control["canonical"]),
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
            raise RuntimeError(f"{window} control parity failed: {checks}")
        control_checks[window] = checks

    control_metrics = primary["CTRL_SNC02"]
    verdict: dict[str, Any] = {}
    for arm in ARMS:
        arm_id = arm.arm_id
        metrics = primary[arm_id]
        mdd20 = float(metrics["chronological_1h_mdd_pct"]) >= -20.0
        risk_pass = (
            mdd20
            and float(metrics["net_return_pct"]) > 0.0
            and float(metrics["profit_factor"]) >= 1.0
            and float(stress[arm_id]["slippage_8bps"]["net_return_pct"]) > 0.0
            and float(stress[arm_id]["lag_1d"]["net_return_pct"]) > 0.0
        )
        dual = (
            float(metrics["net_return_pct"])
            > float(control_metrics["net_return_pct"])
            and float(metrics["chronological_1h_mdd_pct"])
            > float(control_metrics["chronological_1h_mdd_pct"])
        )
        latest_trade = next(
            (
                row
                for row in reversed(ledgers[arm_id]["trades"])
                if row["entry_ts"] == "2026-08-09T00:00:00+00:00"
            ),
            None,
        )
        verdict[arm_id] = {
            "mdd20_pass": mdd20,
            "risk_overlay_pass": risk_pass,
            "dual_improvement": dual,
            "latest_august_long": latest_trade,
            "status": "POST_REVEAL_DIAGNOSTIC_ONLY",
        }

    payload = {
        "schema": "hype-1d-ma7-snc02-risk-overlay-oat-v1",
        "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "status": "DIAGNOSTIC_ONLY_EXPLORE_NOT_PROMOTED_NOT_LIVE_READY",
        "strategy_id": "HYPE-1D-MA7-SNC02-RISK-OAT",
        "arms": {arm.arm_id: arm_config(arm) for arm in ARMS},
        "execution": {
            "daily_conditions": "closed UTC day, next UTC open",
            "stop_path": "1h OHLC; adverse gap open else stop reference",
            "fee_per_fill": float(context.engine.FEE),
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": "actual Binance event timestamp/rate",
            "partial": "close exactly 25% of current quantity once",
        },
        "data_audit": sanitize(context.market.audit),
        "primary_extended": primary,
        "canonical": canonical,
        "stress": stress,
        "recent_slices": recent,
        "calendar_flat_start": calendar,
        "ledgers": ledgers,
        "control_parity": control_checks,
        "verdict": verdict,
        "decision": {
            "stage_a_only": True,
            "combination_run": False,
            "registered_version": None,
            "changes_v7_1": False,
            "runner_change_authorized": False,
        },
        "pins": {
            "contract_sha256": sha256(CONTRACT_PATH),
            "script_sha256": sha256(Path(__file__).resolve()),
            "control_script_sha256": sha256(CONTROL_SCRIPT_PATH),
            "risk_engine_sha256": sha256(RISK_PATH),
            "control_artifact_sha256": sha256(CONTROL_ARTIFACT_PATH),
        },
        "notes": [
            "All candidate outcomes are revealed-history diagnostic evidence.",
            "Stage A contains only frozen single-variable arms; no combination was selected after reveal.",
            "Terminal flatten is censoring, not a mature strategy exit.",
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
                "canonical": payload["canonical"],
                "verdict": payload["verdict"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
