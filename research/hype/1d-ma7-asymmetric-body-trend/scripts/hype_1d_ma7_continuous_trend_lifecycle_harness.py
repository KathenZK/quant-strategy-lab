"""Funded 1h-sequential execution harness for the CTLS research branch.

The trend machine is always observed, even while the account is flat after a
protective or profit exit.  Daily state decisions execute no earlier than the
next UTC session, while protective stops use the frozen chronological 1h
market path.  The module contains no search or performance selection logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import importlib.util
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ENGINE_PATH = Path(__file__).with_name(
    "hype_1d_ma7_continuous_trend_lifecycle_engine.py"
)
FEE = 0.001
BASE_SLIPPAGE = 0.0004
ROUNDTRIP_GUARD = 0.0028


def _load_engine() -> Any:
    name = "hype_1d_ma7_ctls_execution_engine"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import CTLS engine: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ENGINE = _load_engine()
Direction = ENGINE.Direction
Phase = ENGINE.Phase
DetectionConfig = ENGINE.DetectionConfig


class ReentryMode(str, Enum):
    OFF = "off"
    CONTINUATION = "continuation"
    PULLBACK_RESUME = "pullback_resume"


class LongOAPPMode(str, Enum):
    OFF = "off"
    V5_FIXED = "v5_fixed"


class ShortRSIMode(str, Enum):
    OFF = "off"
    RSI20X2 = "20x2"
    RSI25X2 = "25x2"


@dataclass(frozen=True, slots=True)
class LifecycleConfig:
    detection: Any
    chase_cap_atr: float = math.inf
    same_side_reentry: ReentryMode = ReentryMode.OFF
    decel_exit_days: int = 0
    hard_stop_atr: float = 2.5
    trail_atr: float = 2.5
    long_oapp: LongOAPPMode = LongOAPPMode.OFF
    short_rsi: ShortRSIMode = ShortRSIMode.OFF

    def __post_init__(self) -> None:
        if not isinstance(self.detection, DetectionConfig):
            raise TypeError("detection must be a CTLS DetectionConfig")
        if not (math.isinf(self.chase_cap_atr) or self.chase_cap_atr > 0.0):
            raise ValueError("chase_cap_atr must be positive or INF")
        if self.decel_exit_days not in (0, 1, 2):
            raise ValueError("decel_exit_days must be OFF/0, 1, or 2")
        if self.hard_stop_atr not in (0.0, 1.5, 2.5):
            raise ValueError("hard_stop_atr must be OFF/0, 1.5, or 2.5")
        if self.trail_atr not in (1.5, 2.5, 4.0):
            raise ValueError("trail_atr must be 1.5, 2.5, or 4.0")


@dataclass(frozen=True, slots=True)
class PendingAction:
    due_index: int
    signal_index: int
    signal_ts: pd.Timestamp
    target_side: int
    reason: str
    entry_phase: str | None


@dataclass(slots=True)
class ExecutionResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]
    actions: list[dict[str, Any]]
    states: list[dict[str, Any]]


def _target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float, float]:
    if equity <= 0.0 or price <= 0.0 or not math.isfinite(price):
        raise ValueError("quantity target requires positive finite equity and price")
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(30):
        target_qty = target_side * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover, equity - post_equity


def _annualized(equity: float, days: float) -> float:
    if equity <= 0.0:
        return 0.0
    return equity ** (365.25 / days) if days >= 30.0 else math.nan


def _rsi_contract(mode: ShortRSIMode) -> tuple[float, int] | None:
    if mode == ShortRSIMode.RSI20X2:
        return 20.0, 2
    if mode == ShortRSIMode.RSI25X2:
        return 25.0, 2
    return None


def _snapshot_row(snapshot: Any, features: Any) -> dict[str, Any]:
    return {
        "ts": snapshot.ts.isoformat(),
        "previous_direction": int(snapshot.previous_direction),
        "direction": int(snapshot.direction),
        "phase": snapshot.phase.value,
        "label": snapshot.label.value,
        "up_score": snapshot.up_score,
        "down_score": snapshot.down_score,
        "candidate_direction": int(snapshot.candidate_direction),
        "candidate_run": snapshot.candidate_run,
        "loss_run": snapshot.loss_run,
        "transition": snapshot.transition,
        "z": features.z,
        "s1": features.s1,
        "s3": features.s3,
        "d3": features.d3,
        "er7": features.er7,
        "acceleration": features.acceleration,
    }


def backtest(
    data: Any,
    config: LifecycleConfig,
    *,
    label: str,
    start_index: int = 0,
    terminal_index: int | None = None,
    slippage: float = BASE_SLIPPAGE,
    include_funding: bool = True,
    extra_delay_hours: int = 0,
    retain: bool = False,
) -> ExecutionResult:
    """Run one cold-flat CTLS window on a validated market bundle."""

    book = data.book
    terminal_index = book.count if terminal_index is None else terminal_index
    if not (0 <= start_index < terminal_index <= book.count):
        raise ValueError("invalid backtest window")
    if slippage < 0.0 or not math.isfinite(slippage):
        raise ValueError("slippage must be finite and non-negative")
    if extra_delay_hours not in (0, 12):
        raise ValueError("extra_delay_hours must be 0 or 12")
    required = {"open", "high", "low", "close", "ma7", "atr7", "rsi6"}
    if not required.issubset(data.daily.columns):
        raise ValueError(f"daily input is missing {sorted(required - set(data.daily.columns))}")

    daily = data.daily
    causal_frame = daily.loc[:, ["close", "ma7", "atr7"]]
    feature_map = {row.ts: row for row in ENGINE.feature_rows(causal_frame)}
    machine = ENGINE.ContinuousTrendMachine(config.detection)
    cost_rate = FEE + slippage

    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(book.open[start_index])
    peak = 1.0
    max_drawdown = 0.0
    max_effective_leverage = 0.0
    turnover_total = 0.0
    cost_total = 0.0
    funding_total = 0.0
    exposure_hours = 0
    bankrupt = False
    pending: PendingAction | None = None
    direction_epoch = 0
    exit_direction_epoch: int | None = None
    last_exit_side = 0
    reentry_signal_not_before = -1
    pullback_seen = False
    decel_run = 0
    oapp_run = 0
    rsi_run = 0
    current_trade: dict[str, Any] | None = None
    hard_stop = math.nan
    trail_stop = math.nan
    trail_anchor = math.nan
    actions: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    states: list[dict[str, Any]] = []
    equity_points = [1.0]
    suppression_count = 0
    stop_count = 0

    def observe_equity(value: float) -> None:
        nonlocal peak, max_drawdown
        if not math.isfinite(value):
            raise RuntimeError("non-finite equity")
        peak = max(peak, value)
        if peak > 0.0:
            max_drawdown = min(max_drawdown, value / peak - 1.0)

    def mark_to(price: float) -> None:
        nonlocal equity, mark_price
        if price <= 0.0 or not math.isfinite(price):
            raise RuntimeError("non-positive or non-finite mark price")
        equity += qty * (price - mark_price)
        mark_price = price
        observe_equity(equity)

    def trade_to(target: int, price: float) -> tuple[float, float]:
        nonlocal equity, qty, side, turnover_total, cost_total
        qty, equity, turnover, cost = _target_quantity(
            equity, qty, target, price, cost_rate
        )
        turnover_total += turnover
        cost_total += cost
        side = target
        observe_equity(equity)
        return turnover, cost

    def open_trade(
        target: int,
        ts: pd.Timestamp,
        price: float,
        signal_index: int,
        signal_ts: pd.Timestamp,
        reason: str,
        entry_phase: str | None,
    ) -> None:
        nonlocal current_trade, hard_stop, trail_stop, trail_anchor
        nonlocal decel_run, oapp_run, rsi_run
        if current_trade is not None or side != 0:
            raise RuntimeError("entry requires a flat ledger")
        entry_equity = equity
        _, entry_cost = trade_to(target, price)
        entry_atr = float(daily.iloc[signal_index]["atr7"])
        if not math.isfinite(entry_atr) or entry_atr <= 0.0:
            raise RuntimeError("entry signal has invalid ATR7")
        hard_stop = (
            price - target * config.hard_stop_atr * entry_atr
            if config.hard_stop_atr > 0.0
            else math.nan
        )
        trail_stop = math.nan
        trail_anchor = price
        decel_run = oapp_run = rsi_run = 0
        current_trade = {
            "trade_id": f"{label}-{len(trades) + 1:03d}",
            "entry_ts": ts.isoformat(),
            "entry_signal_ts": signal_ts.isoformat(),
            "entry_signal_index": signal_index,
            "side": "long" if target > 0 else "short",
            "entry_price": price,
            "entry_quantity": qty,
            "entry_equity": entry_equity,
            "entry_cost": entry_cost,
            "entry_reason": reason,
            "entry_phase": entry_phase,
            "entry_atr": entry_atr,
            "highest": price,
            "lowest": price,
            "highest_close": price,
            "lowest_close": price,
            "funding_payment": 0.0,
            "exposure_hours": 0,
        }

    def update_trade_range(high: float, low: float) -> None:
        if current_trade is None:
            return
        current_trade["highest"] = max(float(current_trade["highest"]), high)
        current_trade["lowest"] = min(float(current_trade["lowest"]), low)

    def append_closed_trade(
        ts: pd.Timestamp,
        price: float,
        reason: str,
        exit_cost: float,
        exit_equity_before: float,
    ) -> None:
        nonlocal current_trade
        if current_trade is None:
            raise RuntimeError("missing current trade")
        old_side = 1 if current_trade["side"] == "long" else -1
        entry_price = float(current_trade["entry_price"])
        direction = float(old_side)
        favorable = (
            float(current_trade["highest"])
            if old_side > 0
            else float(current_trade["lowest"])
        )
        adverse = (
            float(current_trade["lowest"])
            if old_side > 0
            else float(current_trade["highest"])
        )
        gross_return = direction * (price - entry_price) / entry_price
        mfe_return = direction * (favorable - entry_price) / entry_price
        mae_return = direction * (adverse - entry_price) / entry_price
        trades.append(
            {
                **current_trade,
                "exit_ts": ts.isoformat(),
                "exit_price": price,
                "exit_reason": reason,
                "exit_cost": exit_cost,
                "exit_equity_before": exit_equity_before,
                "exit_equity": equity,
                "net_pnl": equity - float(current_trade["entry_equity"]),
                "net_return": equity / float(current_trade["entry_equity"]) - 1.0,
                "gross_return": gross_return,
                "mfe_return": mfe_return,
                "mae_return": mae_return,
                "giveback_return": max(0.0, mfe_return - gross_return),
            }
        )
        current_trade = None

    def close_trade(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal hard_stop, trail_stop, trail_anchor
        if current_trade is None or side == 0:
            raise RuntimeError("exit requires an open trade")
        exit_equity_before = equity
        _, exit_cost = trade_to(0, price)
        append_closed_trade(ts, price, reason, exit_cost, exit_equity_before)
        hard_stop = trail_stop = trail_anchor = math.nan

    def freeze_bankruptcy(ts: pd.Timestamp, price: float, reason: str) -> None:
        nonlocal equity, qty, side, bankrupt, current_trade
        nonlocal hard_stop, trail_stop, trail_anchor, pending
        old_side = side
        if current_trade is not None:
            equity = 0.0
            qty = 0.0
            side = 0
            append_closed_trade(ts, price, reason, 0.0, 0.0)
        else:
            equity = 0.0
            qty = 0.0
            side = 0
        bankrupt = True
        hard_stop = trail_stop = trail_anchor = math.nan
        pending = None
        max_drawdown_value = -1.0
        observe_equity(0.0)
        actions.append(
            {
                "ts": ts.isoformat(),
                "signal_ts": None,
                "from_side": old_side,
                "target_side": 0,
                "reason": reason,
                "fills": 0,
                "price": price,
                "bankrupt": True,
                "max_drawdown": max_drawdown_value,
            }
        )

    def schedule_reentry(index: int, *, intraday: bool, old_side: int) -> None:
        nonlocal exit_direction_epoch, last_exit_side
        nonlocal reentry_signal_not_before, pullback_seen
        exit_direction_epoch = direction_epoch
        last_exit_side = old_side
        reentry_signal_not_before = index + (1 if intraday else 0)
        pullback_seen = False

    def execute_pending(
        action: PendingAction,
        index: int,
        ts: pd.Timestamp,
        price: float,
    ) -> None:
        nonlocal pending, exit_direction_epoch, last_exit_side, pullback_seen
        old_side = side
        if old_side == action.target_side:
            pending = None
            return
        fills = 0
        if old_side != 0:
            close_trade(ts, price, action.reason)
            fills += 1
        if action.target_side != 0:
            open_trade(
                action.target_side,
                ts,
                price,
                action.signal_index,
                action.signal_ts,
                action.reason,
                action.entry_phase,
            )
            fills += 1
            if old_side == -action.target_side:
                exit_direction_epoch = None
                last_exit_side = 0
                pullback_seen = False
        elif old_side != 0:
            schedule_reentry(index, intraday=False, old_side=old_side)
        actions.append(
            {
                "ts": ts.isoformat(),
                "signal_ts": action.signal_ts.isoformat(),
                "from_side": old_side,
                "target_side": action.target_side,
                "reason": action.reason,
                "fills": fills,
                "price": price,
                "delay_hours": extra_delay_hours,
            }
        )
        pending = None

    def active_stop() -> float:
        if side > 0:
            values = [value for value in (hard_stop, trail_stop) if math.isfinite(value)]
            return max(values) if values else math.nan
        if side < 0:
            values = [value for value in (hard_stop, trail_stop) if math.isfinite(value)]
            return min(values) if values else math.nan
        return math.nan

    def stop_if_hit(index: int, hour: int, *, gap_only: bool) -> bool:
        nonlocal stop_count, pending
        stop = active_stop()
        if side == 0 or current_trade is None or not math.isfinite(stop):
            return False
        old_side = side
        hour_open = float(data.features.hourly_open[index][hour])
        hour_high = float(data.features.hourly_high[index][hour])
        hour_low = float(data.features.hourly_low[index][hour])
        gap = hour_open <= stop if old_side > 0 else hour_open >= stop
        hit = hour_low <= stop if old_side > 0 else hour_high >= stop
        if not gap and (gap_only or not hit):
            return False
        fill = hour_open if gap else stop
        fill_ts = pd.Timestamp(daily.index[index]) + pd.Timedelta(
            hours=hour if gap else hour + 1
        )
        update_trade_range(max(hour_open, fill), min(hour_open, fill))
        if not math.isclose(mark_price, fill):
            mark_to(fill)
        if equity <= 0.0:
            freeze_bankruptcy(fill_ts, fill, "stop_gap_bankruptcy")
            return True
        close_trade(fill_ts, fill, "protective_stop")
        schedule_reentry(index, intraday=hour > 0 or not gap, old_side=old_side)
        stop_count += 1
        if pending is not None and pending.target_side == 0:
            pending = None
        actions.append(
            {
                "ts": fill_ts.isoformat(),
                "signal_ts": None,
                "from_side": old_side,
                "target_side": 0,
                "reason": "protective_stop",
                "fills": 1,
                "price": fill,
                "stop_level": stop,
                "gap": gap,
                "hour": hour,
            }
        )
        return True

    def update_trailing_after_completed_hour(high: float, low: float) -> None:
        nonlocal trail_anchor, trail_stop
        if side == 0 or current_trade is None:
            return
        entry_atr = float(current_trade["entry_atr"])
        if side > 0:
            trail_anchor = max(trail_anchor, high)
            candidate = trail_anchor - config.trail_atr * entry_atr
            trail_stop = candidate if not math.isfinite(trail_stop) else max(trail_stop, candidate)
        else:
            trail_anchor = min(trail_anchor, low)
            candidate = trail_anchor + config.trail_atr * entry_atr
            trail_stop = candidate if not math.isfinite(trail_stop) else min(trail_stop, candidate)

    def can_enter(
        snapshot: Any,
        features: Any,
        index: int,
    ) -> tuple[bool, str]:
        if snapshot.direction == Direction.FLAT or snapshot.phase == Phase.DECELERATING:
            return False, "no_active_direction"
        if not math.isinf(config.chase_cap_atr) and abs(features.z) > config.chase_cap_atr:
            return False, "anti_chase"
        target = int(snapshot.direction)
        is_same_epoch_reentry = (
            last_exit_side == target
            and exit_direction_epoch is not None
            and exit_direction_epoch == direction_epoch
        )
        if not is_same_epoch_reentry:
            return True, "new_direction"
        if config.same_side_reentry == ReentryMode.OFF:
            return False, "reentry_disabled"
        if index < reentry_signal_not_before:
            return False, "cooldown"
        if config.same_side_reentry == ReentryMode.PULLBACK_RESUME and not pullback_seen:
            return False, "pullback_not_seen"
        return True, "same_side_reentry"

    def schedule_from_close(
        snapshot: Any,
        features: Any,
        index: int,
    ) -> PendingAction | None:
        nonlocal decel_run, oapp_run, rsi_run, pullback_seen
        signal_ts = pd.Timestamp(daily.index[index])
        if side != 0:
            if snapshot.direction == Direction(-side):
                return PendingAction(
                    index + 1,
                    index,
                    signal_ts,
                    -side,
                    "confirmed_trend_reversal",
                    snapshot.phase.value,
                )
            if snapshot.direction == Direction.FLAT:
                return PendingAction(
                    index + 1,
                    index,
                    signal_ts,
                    0,
                    "confirmed_direction_loss",
                    None,
                )
            decel_run = decel_run + 1 if snapshot.phase == Phase.DECELERATING else 0
            if config.decel_exit_days and decel_run >= config.decel_exit_days:
                return PendingAction(
                    index + 1,
                    index,
                    signal_ts,
                    0,
                    "deceleration_exit",
                    None,
                )
            if current_trade is None:
                raise RuntimeError("position exists without a current trade")
            signal_close = float(daily.iloc[index]["close"])
            entry_price = float(current_trade["entry_price"])
            entry_atr = float(current_trade["entry_atr"])
            if side > 0:
                rsi_run = 0
                current_trade["highest_close"] = max(
                    float(current_trade["highest_close"]), signal_close
                )
                peak_profit = float(current_trade["highest_close"]) - entry_price
                current_profit = signal_close - entry_price
                giveback = float(current_trade["highest_close"]) - signal_close
                active = (
                    config.long_oapp == LongOAPPMode.V5_FIXED
                    and peak_profit / entry_atr >= 0.5
                    and current_profit / entry_price > ROUNDTRIP_GUARD
                    and peak_profit > 0.0
                    and giveback / peak_profit >= 0.10
                )
                oapp_run = oapp_run + 1 if active else 0
                if oapp_run >= 2:
                    return PendingAction(
                        index + 1,
                        index,
                        signal_ts,
                        0,
                        "long_oapp_v5_fixed_exit",
                        None,
                    )
            else:
                oapp_run = 0
                current_trade["lowest_close"] = min(
                    float(current_trade["lowest_close"]), signal_close
                )
                rsi_spec = _rsi_contract(config.short_rsi)
                rsi6 = float(daily.iloc[index]["rsi6"])
                rsi_run = (
                    rsi_run + 1
                    if rsi_spec is not None and math.isfinite(rsi6) and rsi6 < rsi_spec[0]
                    else 0
                )
                gross_profit = (entry_price - signal_close) / entry_price
                if (
                    rsi_spec is not None
                    and rsi_run >= rsi_spec[1]
                    and gross_profit > ROUNDTRIP_GUARD
                ):
                    return PendingAction(
                        index + 1,
                        index,
                        signal_ts,
                        0,
                        "short_rsi_take_profit",
                        None,
                    )
            return None

        decel_run = oapp_run = rsi_run = 0
        if snapshot.phase == Phase.DECELERATING or abs(features.z) <= 0.5:
            pullback_seen = True
        passed, reason = can_enter(snapshot, features, index)
        if not passed:
            return None
        return PendingAction(
            index + 1,
            index,
            signal_ts,
            int(snapshot.direction),
            "trend_entry" if reason == "new_direction" else reason,
            snapshot.phase.value,
        )

    for index in range(start_index, terminal_index):
        ts = pd.Timestamp(daily.index[index])
        current_open = float(book.open[index])
        if index > start_index and not math.isclose(mark_price, current_open):
            mark_to(current_open)
        else:
            mark_price = current_open
        if equity <= 0.0:
            freeze_bankruptcy(ts, current_open, "session_open_bankruptcy")
            break

        if pending is not None and pending.due_index == index and extra_delay_hours == 0:
            execute_pending(pending, index, ts, current_open)

        day_events = {
            event.ts.floor("h"): event for event in data.features.funding_events[index]
        }
        for hour in range(24):
            hour_ts = ts + pd.Timedelta(hours=hour)
            hour_open = float(data.features.hourly_open[index][hour])
            if not math.isclose(mark_price, hour_open):
                mark_to(hour_open)
            if equity <= 0.0:
                freeze_bankruptcy(hour_ts, hour_open, "hour_open_bankruptcy")
                break
            if (
                pending is not None
                and pending.due_index == index
                and extra_delay_hours == hour
                and extra_delay_hours > 0
            ):
                execute_pending(pending, index, hour_ts, hour_open)
            if stop_if_hit(index, hour, gap_only=True):
                if bankrupt:
                    break
                continue
            if side == 0:
                continue
            exposure_hours += 1
            if current_trade is not None:
                current_trade["exposure_hours"] += 1
            event = day_events.get(hour_ts)
            if include_funding and event is not None:
                payment = qty * event.price * event.rate
                equity -= payment
                funding_total += payment
                if current_trade is not None:
                    current_trade["funding_payment"] += payment
                observe_equity(equity)
                if equity <= 0.0:
                    freeze_bankruptcy(hour_ts, hour_open, "funding_bankruptcy")
                    break
            if stop_if_hit(index, hour, gap_only=False):
                if bankrupt:
                    break
                continue
            high = float(data.features.hourly_high[index][hour])
            low = float(data.features.hourly_low[index][hour])
            update_trade_range(high, low)
            favorable = high if side > 0 else low
            adverse = low if side > 0 else high
            favorable_equity = equity + qty * (favorable - hour_open)
            adverse_equity = equity + qty * (adverse - hour_open)
            observe_equity(favorable_equity)
            observe_equity(adverse_equity)
            if adverse_equity <= 0.0:
                bankruptcy_price = hour_open - equity / qty
                freeze_bankruptcy(
                    hour_ts + pd.Timedelta(hours=1),
                    bankruptcy_price,
                    "intraday_bankruptcy",
                )
                break
            if adverse_equity > 0.0:
                max_effective_leverage = max(
                    max_effective_leverage,
                    abs(qty) * adverse / adverse_equity,
                )
            update_trailing_after_completed_hour(high, low)
        if bankrupt:
            break

        day_close = float(book.close[index])
        if not math.isclose(mark_price, day_close):
            mark_to(day_close)
        if current_trade is not None:
            current_trade["highest_close"] = max(
                float(current_trade["highest_close"]), day_close
            )
            current_trade["lowest_close"] = min(
                float(current_trade["lowest_close"]), day_close
            )
        if equity <= 0.0:
            freeze_bankruptcy(ts + pd.Timedelta(days=1), day_close, "close_bankruptcy")
            break

        snapshot = None
        decision = None
        features = feature_map.get(ts)
        if features is not None:
            previous_direction = machine.state.direction
            snapshot = machine.observe(features)
            if snapshot.transition.startswith(("enter_", "reverse_to_")):
                direction_epoch += 1
            states.append(_snapshot_row(snapshot, features))
            if side == 0 and (
                snapshot.phase == Phase.DECELERATING or abs(features.z) <= 0.5
            ):
                pullback_seen = True
            if pending is not None:
                raise RuntimeError("a daily pending action crossed another close")
            decision = schedule_from_close(snapshot, features, index)
            if decision is not None:
                if decision.due_index >= terminal_index:
                    suppression_count += 1
                    decision = None
                else:
                    pending = decision
            if (
                previous_direction != Direction.FLAT
                and snapshot.direction == Direction.FLAT
                and side == 0
            ):
                exit_direction_epoch = None
                last_exit_side = 0
                pullback_seen = False

        equity_points.append(equity)
        if retain:
            row = daily.iloc[index]
            path.append(
                {
                    "ts": ts.isoformat(),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "ma7": float(row["ma7"]) if math.isfinite(float(row["ma7"])) else None,
                    "atr7": float(row["atr7"]) if math.isfinite(float(row["atr7"])) else None,
                    "rsi6": float(row["rsi6"]) if math.isfinite(float(row["rsi6"])) else None,
                    "z": features.z if features is not None else None,
                    "s1": features.s1 if features is not None else None,
                    "s3": features.s3 if features is not None else None,
                    "d3": features.d3 if features is not None else None,
                    "er7": features.er7 if features is not None else None,
                    "acceleration": features.acceleration if features is not None else None,
                    "direction": int(snapshot.direction) if snapshot is not None else 0,
                    "phase": snapshot.phase.value if snapshot is not None else "unavailable",
                    "equity": equity,
                    "side": side,
                    "hard_stop": hard_stop if math.isfinite(hard_stop) else None,
                    "trail_stop": trail_stop if math.isfinite(trail_stop) else None,
                    "active_stop": active_stop() if math.isfinite(active_stop()) else None,
                    "decel_run": decel_run,
                    "oapp_run": oapp_run,
                    "rsi_run": rsi_run,
                    "direction_epoch": direction_epoch,
                    "reentry_signal_not_before": reentry_signal_not_before,
                    "pullback_seen": pullback_seen,
                    "pending_reason": decision.reason if decision is not None else "",
                    "terminal": False,
                }
            )

    terminal_ts = (
        pd.Timestamp(book.terminal_ts)
        if terminal_index == book.count
        else pd.Timestamp(book.ts[terminal_index])
    )
    terminal_open = (
        float(book.quality["terminal_open"])
        if terminal_index == book.count
        else float(book.open[terminal_index])
    )
    if not bankrupt:
        if not math.isclose(mark_price, terminal_open):
            mark_to(terminal_open)
        if equity <= 0.0:
            freeze_bankruptcy(terminal_ts, terminal_open, "terminal_gap_bankruptcy")
        elif side != 0:
            old_side = side
            close_trade(terminal_ts, terminal_open, "terminal_flatten")
            actions.append(
                {
                    "ts": terminal_ts.isoformat(),
                    "signal_ts": None,
                    "from_side": old_side,
                    "target_side": 0,
                    "reason": "terminal_flatten",
                    "fills": 1,
                    "price": terminal_open,
                }
            )
        pending = None
        equity_points.append(equity)
        if retain:
            path.append(
                {
                    "ts": terminal_ts.isoformat(),
                    "open": terminal_open,
                    "high": terminal_open,
                    "low": terminal_open,
                    "close": terminal_open,
                    "ma7": None,
                    "atr7": None,
                    "rsi6": None,
                    "z": None,
                    "s1": None,
                    "s3": None,
                    "d3": None,
                    "er7": None,
                    "acceleration": None,
                    "direction": 0,
                    "phase": "terminal",
                    "equity": equity,
                    "side": 0,
                    "hard_stop": None,
                    "trail_stop": None,
                    "active_stop": None,
                    "decel_run": 0,
                    "oapp_run": 0,
                    "rsi_run": 0,
                    "direction_epoch": direction_epoch,
                    "reentry_signal_not_before": reentry_signal_not_before,
                    "pullback_seen": pullback_seen,
                    "pending_reason": "",
                    "terminal": True,
                }
            )

    days = max(
        1.0,
        (terminal_ts - pd.Timestamp(book.ts[start_index])).total_seconds() / 86_400.0,
    )
    trade_returns = np.asarray([trade["net_return"] for trade in trades], dtype=float)
    wins = trade_returns[trade_returns > 0.0]
    losses = trade_returns[trade_returns < 0.0]
    daily_returns = pd.Series(equity_points, dtype=float).pct_change().dropna().to_numpy()
    sharpe = (
        float(np.mean(daily_returns) / np.std(daily_returns, ddof=1) * np.sqrt(365.25))
        if len(daily_returns) > 1 and np.std(daily_returns, ddof=1) > 0.0
        else math.nan
    )
    long_trades = [trade for trade in trades if trade["side"] == "long"]
    short_trades = [trade for trade in trades if trade["side"] == "short"]
    metrics = {
        "label": label,
        "config": {
            **asdict(config),
            "same_side_reentry": config.same_side_reentry.value,
            "long_oapp": config.long_oapp.value,
            "short_rsi": config.short_rsi.value,
            "detection": asdict(config.detection),
            "chase_cap_atr": "INF" if math.isinf(config.chase_cap_atr) else config.chase_cap_atr,
        },
        "start_ts": pd.Timestamp(book.ts[start_index]).isoformat(),
        "end_ts": terminal_ts.isoformat(),
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": _annualized(equity, days),
        "max_drawdown_pct": (-100.0 if bankrupt else max_drawdown * 100.0),
        "sharpe": sharpe,
        "profit_factor": float(wins.sum() / abs(losses.sum())) if len(losses) else math.inf,
        "closed_trades": len(trades),
        "long_trades": len(long_trades),
        "short_trades": len(short_trades),
        "slow_long_entries": sum(trade["entry_phase"] == "slow" for trade in long_trades),
        "slow_short_entries": sum(trade["entry_phase"] == "slow" for trade in short_trades),
        "win_rate": float((trade_returns > 0.0).mean()) if len(trades) else math.nan,
        "exposure_pct": exposure_hours / max(1, (terminal_index - start_index) * 24) * 100.0,
        "turnover": turnover_total,
        "cost": cost_total,
        "funding_payment": funding_total,
        "max_effective_leverage": max_effective_leverage,
        "protective_stop_count": stop_count,
        "pending_terminal_suppression_count": suppression_count,
        "state_rows": len(states),
        "bankrupt": bankrupt,
        "slippage_bps": slippage * 10_000.0,
        "include_funding": include_funding,
        "extra_delay_hours": extra_delay_hours,
        "fill_count": sum(int(action["fills"]) for action in actions),
    }
    return ExecutionResult(
        metrics=metrics,
        trades=trades if retain else [],
        path=path,
        actions=actions if retain else [],
        states=states if retain else [],
    )
