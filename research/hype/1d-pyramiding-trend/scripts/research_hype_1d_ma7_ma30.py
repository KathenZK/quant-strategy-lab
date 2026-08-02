from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-pyramiding-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
PARENT_SCRIPT = FAMILY_DIR / "scripts/research_hype_1d_pyramiding_trend.py"

FAMILY = "HYPE-1D-Pyramiding-Trend"
BRANCH = "MA7/MA30"
FEE = 0.001
SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MAX_LEVERAGE = 3.0
TARGET_FACTOR = 20.0
TARGET_DRAWDOWN = 0.20
MIN_PREFIT_TRADES = 8
MIN_HOLDOUT_TRADES = 3
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
PREFIT_END = pd.Timestamp("2026-04-30T00:00:00Z")

MA_NAMES = {0: "sma", 1: "ema"}
ENTRY_NAMES = {0: "cross", 1: "regime_follow", 2: "ma7_reclaim", 3: "regime_breakout"}
DIRECTION_NAMES = {0: "both", 1: "long_only", 2: "short_only"}
EXIT_NAMES = {0: "opposite_cross", 1: "close_through_ma7", 2: "close_through_ma30", 3: "ma7_or_slope_reversal"}
ADD_NAMES = {0: "layers", 1: "reset_to_3x"}


@dataclass(frozen=True, slots=True)
class Config:
    ma_type: int
    entry_mode: int
    direction: int
    confirm_days: int
    slope_days: int
    breakout_window: int
    entry_buffer_atr: float
    exit_mode: int
    atr_window: int
    adx_min: float
    atr_pct_cap: float
    initial_leverage: float
    add_mode: int
    add_step_atr: float
    add_increment: float
    stop_atr: float
    trail_atr: float
    profit_trigger_atr: float
    profit_lock_atr: float
    max_hold_days: int
    cooldown_days: int
    allow_flip: bool

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


@dataclass(slots=True)
class Book:
    ts: pd.DatetimeIndex
    terminal_ts: pd.Timestamp
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    ma7: dict[int, np.ndarray]
    ma30: dict[int, np.ndarray]
    atr: dict[int, np.ndarray]
    adx: dict[int, np.ndarray]
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    funding_by_open: np.ndarray
    quality: dict[str, Any]
    funding_quality: dict[str, Any]

    @property
    def daily_count(self) -> int:
        return len(self.open)


@dataclass(slots=True)
class Result:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Research {FAMILY} {BRANCH}.")
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--stage1", type=int, default=300_000)
    parser.add_argument("--stage2", type=int, default=200_000)
    parser.add_argument("--shortlist", type=int, default=160)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def _load_parent() -> object:
    spec = importlib.util.spec_from_file_location("hype_1d_pt_parent", PARENT_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {PARENT_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sma(values: np.ndarray, window: int) -> np.ndarray:
    return pd.Series(values).rolling(window, min_periods=window).mean().to_numpy("float64")


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(values).ewm(span=span, adjust=False, min_periods=span).mean().to_numpy("float64")


def build_book() -> Book:
    parent = _load_parent()
    source = parent.build_feature_book()
    close = source.close
    return Book(
        ts=source.ts,
        terminal_ts=source.terminal_ts,
        open=source.open,
        high=source.high,
        low=source.low,
        close=close,
        ma7={0: _sma(close, 7), 1: _ema(close, 7)},
        ma30={0: _sma(close, 30), 1: _ema(close, 30)},
        atr=source.atr,
        adx=source.adx,
        prior_high=source.prior_high,
        prior_low=source.prior_low,
        funding_by_open=source.funding_by_open,
        quality=source.quality,
        funding_quality=source.funding_quality,
    )


def _regime(config: Config, book: Book, index: int) -> int:
    fast = book.ma7[config.ma_type][index]
    slow = book.ma30[config.ma_type][index]
    if not np.isfinite(fast) or not np.isfinite(slow) or math.isclose(fast, slow, rel_tol=0.0, abs_tol=1e-12):
        return 0
    return 1 if fast > slow else -1


def _along(config: Config, book: Book, index: int, side: int) -> bool:
    if index - config.slope_days < 0:
        return False
    fast = book.ma7[config.ma_type]
    current = fast[index]
    prior = fast[index - config.slope_days]
    close = book.close[index]
    atr = book.atr[config.atr_window][index]
    if not all(np.isfinite(value) for value in (current, prior, close, atr)):
        return False
    if side > 0:
        return close > current + config.entry_buffer_atr * atr and current > prior
    return close < current - config.entry_buffer_atr * atr and current < prior


def _confirmed_along(config: Config, book: Book, index: int, side: int) -> bool:
    left = index - config.confirm_days + 1
    if left < 0:
        return False
    return all(_regime(config, book, offset) == side and _along(config, book, offset, side) for offset in range(left, index + 1))


def entry_side(config: Config, book: Book, index: int) -> int:
    if index < 1:
        return 0
    atr = book.atr[config.atr_window][index]
    adx = book.adx[config.atr_window][index]
    close = book.close[index]
    if not all(np.isfinite(value) for value in (atr, adx, close)) or atr <= 0.0 or close <= 0.0:
        return 0
    if config.adx_min > 0.0 and adx < config.adx_min:
        return 0
    if config.atr_pct_cap > 0.0 and atr / close > config.atr_pct_cap:
        return 0
    side = _regime(config, book, index)
    if side == 0 or (side > 0 and config.direction == 2) or (side < 0 and config.direction == 1):
        return 0
    prior_side = _regime(config, book, index - 1)
    signal = False
    if config.entry_mode == 0:
        signal = prior_side == -side and _confirmed_along(config, book, index, side)
    elif config.entry_mode == 1:
        signal = _confirmed_along(config, book, index, side)
    elif config.entry_mode == 2:
        fast = book.ma7[config.ma_type]
        if side > 0:
            signal = (
                book.close[index] > fast[index] + config.entry_buffer_atr * atr
                and book.close[index - 1] <= fast[index - 1]
                and _along(config, book, index, side)
            )
        else:
            signal = (
                book.close[index] < fast[index] - config.entry_buffer_atr * atr
                and book.close[index - 1] >= fast[index - 1]
                and _along(config, book, index, side)
            )
    else:
        boundary = (
            book.prior_high[config.breakout_window][index]
            if side > 0
            else book.prior_low[config.breakout_window][index]
        )
        if np.isfinite(boundary):
            signal = (
                close > boundary + config.entry_buffer_atr * atr
                if side > 0
                else close < boundary - config.entry_buffer_atr * atr
            )
            signal = signal and _confirmed_along(config, book, index, side)
    return side if signal else 0


def exit_reason(config: Config, book: Book, index: int, side: int, bars_held: int) -> str:
    regime = _regime(config, book, index)
    if regime == -side:
        return "opposite_cross"
    close = book.close[index]
    fast = book.ma7[config.ma_type][index]
    slow = book.ma30[config.ma_type][index]
    if not all(np.isfinite(value) for value in (close, fast, slow)):
        return "indicator_unavailable"
    if config.exit_mode == 1 and side * (close - fast) < 0.0:
        return "close_through_ma7"
    if config.exit_mode == 2 and side * (close - slow) < 0.0:
        return "close_through_ma30"
    if config.exit_mode == 3:
        prior_index = index - config.slope_days
        if side * (close - fast) < 0.0:
            return "close_through_ma7"
        if prior_index >= 0 and side * (fast - book.ma7[config.ma_type][prior_index]) <= 0.0:
            return "ma7_slope_reversal"
    if config.max_hold_days > 0 and bars_held >= config.max_hold_days:
        return "max_hold"
    return ""


def _annual_factor(equity: float, days: float) -> float:
    if equity <= 0.0 or days <= 0.0:
        return 0.0
    return float(equity ** min(20.0, 365.25 / days))


def _target_quantity(
    equity: float,
    old_qty: float,
    target_leverage: float,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float]:
    post_equity = equity
    target_qty = target_leverage * post_equity / price
    turnover = 0.0
    for _ in range(12):
        target_qty = target_leverage * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover


def backtest(
    config: Config,
    book: Book,
    *,
    start_index: int,
    terminal_index: int,
    slippage: float = SLIPPAGE,
    delay_days: int = 1,
    retain: bool = False,
) -> Result:
    if not (0 <= start_index < terminal_index <= book.daily_count):
        raise ValueError("invalid window")
    if delay_days not in {1, 2}:
        raise ValueError("delay_days must be 1 or 2")
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    opens = np.r_[book.open, float(book.quality["terminal_open"])]
    cost_rate = FEE + slippage
    equity = 1.0
    qty = 0.0
    mark_price = float(opens[start_index])
    side = 0
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    average_entry = math.nan
    entry_atr = math.nan
    entry_equity = math.nan
    last_add_price = math.nan
    highest_close = -math.inf
    lowest_close = math.inf
    stop_price = math.nan
    target_level = 0.0
    bars_held = 0
    cooldown_left = 0
    pending: dict[int, tuple[str, int]] = {}
    peak = 1.0
    max_drawdown = 0.0
    max_leverage_seen = 0.0
    max_effective_open_leverage = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    add_count = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []

    def record_close(ts: pd.Timestamp, price: float, reason: str, campaign_equity: float) -> None:
        nonlocal side, entry_ts, entry_price, average_entry, entry_atr, entry_equity
        nonlocal last_add_price, highest_close, lowest_close, stop_price, target_level, bars_held
        if entry_ts is not None:
            trades.append({
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "side": "long" if side > 0 else "short",
                "entry_price": entry_price,
                "exit_price": price,
                "bars_held": bars_held,
                "exit_reason": reason,
                "net_return": campaign_equity / entry_equity - 1.0,
            })
        side = 0
        entry_ts = None
        entry_price = average_entry = entry_atr = entry_equity = last_add_price = math.nan
        highest_close = -math.inf
        lowest_close = math.inf
        stop_price = math.nan
        target_level = 0.0
        bars_held = 0

    def trade_to_leverage(target: float, price: float) -> float:
        nonlocal equity, qty, total_turnover, total_cost, max_leverage_seen
        old_equity = equity
        new_qty, post_equity, turnover = _target_quantity(equity, qty, target, price, cost_rate)
        equity = post_equity
        qty = new_qty
        total_turnover += turnover
        total_cost += old_equity - post_equity
        if equity > 0.0:
            leverage = abs(qty) * price / equity
            max_leverage_seen = max(max_leverage_seen, leverage)
            if leverage > MAX_LEVERAGE + 1e-9:
                raise RuntimeError(f"leverage cap breached: {leverage}")
        return turnover

    def enter(new_side: int, ts: pd.Timestamp, price: float, signal_index: int) -> None:
        nonlocal side, entry_ts, entry_price, average_entry, entry_atr, entry_equity
        nonlocal last_add_price, highest_close, lowest_close, stop_price, target_level
        entry_equity = equity
        target_level = config.initial_leverage
        trade_to_leverage(new_side * target_level, price)
        side = new_side
        entry_ts = ts
        entry_price = average_entry = last_add_price = price
        entry_atr = float(book.atr[config.atr_window][signal_index])
        highest_close = -math.inf
        lowest_close = math.inf
        if config.stop_atr > 0.0:
            stop_price = price - new_side * config.stop_atr * entry_atr

    for index in range(start_index, terminal_index + 1):
        ts = pd.Timestamp(timestamps[index])
        current_open = float(opens[index])
        if index > start_index and qty != 0.0:
            equity += qty * (current_open - mark_price)
            funding = qty * current_open * book.funding_by_open[index]
            equity -= funding
            total_funding += funding
        mark_price = current_open
        if equity <= 0.0:
            equity = 0.0
            max_drawdown = -1.0
            break
        if qty != 0.0:
            max_effective_open_leverage = max(
                max_effective_open_leverage,
                abs(qty) * current_open / equity,
            )

        action_label = "hold"
        pending_action = pending.pop(index, None)
        if pending_action is not None:
            action, action_side = pending_action
            if action == "exit":
                trade_to_leverage(0.0, current_open)
                record_close(ts, current_open, "signal_exit", equity)
                cooldown_left = config.cooldown_days
                action_label = "exit"
            elif action == "flip":
                trade_to_leverage(0.0, current_open)
                record_close(ts, current_open, "opposite_cross", equity)
                enter(action_side, ts, current_open, max(start_index, index - delay_days))
                action_label = "flip"
            elif action == "entry":
                enter(action_side, ts, current_open, max(start_index, index - delay_days))
                action_label = "entry"
            elif action == "add" and side == action_side and qty != 0.0:
                old_qty = qty
                if config.add_mode == 1:
                    target_level = MAX_LEVERAGE
                else:
                    target_level = min(MAX_LEVERAGE, target_level + config.add_increment)
                trade_to_leverage(side * target_level, current_open)
                if abs(qty) > abs(old_qty) + 1e-12:
                    average_entry = (
                        abs(old_qty) * average_entry + abs(qty - old_qty) * current_open
                    ) / abs(qty)
                    last_add_price = current_open
                    add_count += 1
                    action_label = "add"

        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)

        if index < book.daily_count and qty != 0.0:
            day_high = float(book.high[index])
            day_low = float(book.low[index])
            gap_stop = (
                np.isfinite(stop_price)
                and ((side > 0 and current_open <= stop_price) or (side < 0 and current_open >= stop_price))
            )
            stop_hit = (
                np.isfinite(stop_price)
                and ((side > 0 and day_low <= stop_price) or (side < 0 and day_high >= stop_price))
            )
            if not gap_stop:
                favorable_price = day_high if side > 0 else day_low
                peak_candidate = equity + qty * (favorable_price - current_open)
                peak = max(peak, peak_candidate)
            if stop_hit:
                fill = (
                    min(current_open, stop_price)
                    if side > 0
                    else max(current_open, stop_price)
                )
                equity += qty * (fill - current_open)
                mark_price = fill
                trade_to_leverage(0.0, fill)
                max_drawdown = min(max_drawdown, equity / peak - 1.0)
                record_close(ts, fill, "protective_stop", equity)
                pending.clear()
                cooldown_left = config.cooldown_days
                action_label = "protective_stop"
            else:
                adverse_price = day_low if side > 0 else day_high
                trough_candidate = equity + qty * (adverse_price - current_open)
                max_drawdown = min(max_drawdown, trough_candidate / peak - 1.0)

        if retain:
            path.append({
                "ts": ts.isoformat(),
                "equity": equity,
                "position_qty": qty,
                "leverage": abs(qty) * current_open / equity if equity > 0.0 else math.inf,
                "action": action_label,
                "max_drawdown_conservative": max_drawdown,
            })

        if index >= book.daily_count or equity <= 0.0:
            continue
        close = float(book.close[index])
        if qty != 0.0:
            bars_held += 1
            highest_close = max(highest_close, close)
            lowest_close = min(lowest_close, close)
            if not pending:
                reason = exit_reason(config, book, index, side, bars_held)
                target_index = index + delay_days
                if reason and target_index <= terminal_index:
                    next_side = (
                        entry_side(config, book, index)
                        if config.allow_flip and reason == "opposite_cross" and target_index < terminal_index
                        else 0
                    )
                    pending[target_index] = ("flip", next_side) if next_side == -side else ("exit", 0)
                elif target_index < terminal_index:
                    atr = book.atr[config.atr_window][index]
                    close_equity = equity + qty * (close - current_open)
                    floating_profit = close_equity > entry_equity and side * (close - average_entry) > 0.0
                    along = _regime(config, book, index) == side and _along(config, book, index, side)
                    threshold = (
                        close >= last_add_price + config.add_step_atr * atr
                        if side > 0
                        else close <= last_add_price - config.add_step_atr * atr
                    )
                    can_add = (
                        floating_profit
                        and along
                        and threshold
                        and target_level < MAX_LEVERAGE - 1e-12
                    )
                    if can_add:
                        pending[target_index] = ("add", side)
            atr = book.atr[config.atr_window][index]
            candidate_stops: list[float] = []
            if config.stop_atr > 0.0:
                candidate_stops.append(entry_price - side * config.stop_atr * entry_atr)
            if config.trail_atr > 0.0 and np.isfinite(atr):
                anchor = highest_close if side > 0 else lowest_close
                candidate_stops.append(anchor - side * config.trail_atr * atr)
            favorable_move = side * ((highest_close if side > 0 else lowest_close) - entry_price)
            if config.profit_trigger_atr > 0.0 and favorable_move >= config.profit_trigger_atr * entry_atr:
                candidate_stops.append(entry_price + side * config.profit_lock_atr * entry_atr)
            if candidate_stops:
                stop_price = (
                    max([value for value in candidate_stops if np.isfinite(value)], default=math.nan)
                    if side > 0
                    else min([value for value in candidate_stops if np.isfinite(value)], default=math.nan)
                )
        elif not pending:
            if cooldown_left > 0:
                cooldown_left -= 1
            else:
                new_side = entry_side(config, book, index)
                target_index = index + delay_days
                if new_side and target_index < terminal_index:
                    pending[target_index] = ("entry", new_side)

    ending_position = qty
    if qty != 0.0 and equity > 0.0:
        terminal_price = float(opens[min(terminal_index, len(opens) - 1)])
        trade_to_leverage(0.0, terminal_price)
        record_close(pd.Timestamp(timestamps[terminal_index]), terminal_price, "terminal_flatten", equity)
    peak = max(peak, equity)
    max_drawdown = min(max_drawdown, equity / peak - 1.0)
    days = max(1.0, (timestamps[terminal_index] - timestamps[start_index]).total_seconds() / 86400.0)
    trade_returns = [float(row["net_return"]) for row in trades]
    wins = sum(value > 0.0 for value in trade_returns)
    gross_profit = sum(value for value in trade_returns if value > 0.0)
    gross_loss = -sum(value for value in trade_returns if value < 0.0)
    metrics = {
        "start_ts": pd.Timestamp(timestamps[start_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_index]).isoformat(),
        "days": days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": _annual_factor(equity, days),
        "cagr_pct": (_annual_factor(equity, days) - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "closed_trades": len(trades),
        "win_rate": wins / len(trades) if trades else math.nan,
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else (math.inf if gross_profit > 0.0 else math.nan),
        "add_count": add_count,
        "max_leverage": max_leverage_seen,
        "max_effective_open_leverage": max_effective_open_leverage,
        "ending_position_before_forced_flatten": ending_position,
        "total_turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "bankrupt": equity <= 0.0,
    }
    return Result(metrics=metrics, trades=trades, path=path)


def example_config() -> Config:
    return Config(
        ma_type=0,
        entry_mode=0,
        direction=0,
        confirm_days=1,
        slope_days=1,
        breakout_window=3,
        entry_buffer_atr=0.0,
        exit_mode=1,
        atr_window=7,
        adx_min=0.0,
        atr_pct_cap=0.0,
        initial_leverage=1.0,
        add_mode=1,
        add_step_atr=1.0,
        add_increment=1.0,
        stop_atr=0.0,
        trail_atr=0.0,
        profit_trigger_atr=0.0,
        profit_lock_atr=0.0,
        max_hold_days=0,
        cooldown_days=0,
        allow_flip=True,
    )


def random_config(rng: random.Random) -> Config:
    profit_trigger = rng.choice((0.0, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0))
    return Config(
        ma_type=rng.choice((0, 1)),
        entry_mode=rng.choices((0, 1, 2, 3), weights=(2, 4, 3, 4), k=1)[0],
        direction=rng.choices((0, 1, 2), weights=(5, 4, 2), k=1)[0],
        confirm_days=rng.choice((1, 1, 2, 3)),
        slope_days=rng.choice((1, 1, 2, 3, 5)),
        breakout_window=rng.choice((2, 3, 5, 7, 10, 14, 20)),
        entry_buffer_atr=rng.choice((0.0, 0.0, 0.1, 0.25, 0.5)),
        exit_mode=rng.choice((0, 1, 2, 3)),
        atr_window=rng.choice((5, 7, 10, 14, 20, 30)),
        adx_min=rng.choice((0.0, 0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0)),
        atr_pct_cap=rng.choice((0.0, 0.0, 0.06, 0.08, 0.10, 0.12, 0.16)),
        initial_leverage=rng.choice((0.5, 0.75, 1.0, 1.25, 1.5)),
        add_mode=rng.choice((0, 1)),
        add_step_atr=rng.choice((0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)),
        add_increment=rng.choice((0.5, 0.75, 1.0, 1.5)),
        stop_atr=rng.choice((0.0, 0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0)),
        trail_atr=rng.choice((0.0, 0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0)),
        profit_trigger_atr=profit_trigger,
        profit_lock_atr=(0.0 if profit_trigger == 0.0 else rng.choice((0.0, 0.25, 0.5, 0.75, 1.0))),
        max_hold_days=rng.choice((0, 0, 5, 7, 10, 15, 20, 30, 45, 60, 90)),
        cooldown_days=rng.choice((0, 0, 1, 2, 3, 5, 7, 10)),
        allow_flip=rng.choice((False, True)),
    )


def mutate(parent: Config, rng: random.Random) -> Config:
    fresh = asdict(random_config(rng))
    source = asdict(parent)
    for key, value in source.items():
        if rng.random() < 0.72:
            fresh[key] = value
    if fresh["profit_trigger_atr"] == 0.0:
        fresh["profit_lock_atr"] = 0.0
    return Config(**fresh)


def compact(config: Config, result: Result) -> dict[str, Any]:
    metrics = result.metrics
    factor = metrics["annualized_factor"]
    drawdown = abs(min(0.0, metrics["max_drawdown_pct"] / 100.0))
    return {
        "config": config,
        "annualized_factor": factor,
        "equity_multiple": metrics["equity_multiple"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "win_rate": metrics["win_rate"],
        "closed_trades": metrics["closed_trades"],
        "add_count": metrics["add_count"],
        "max_leverage": metrics["max_leverage"],
        "joint_gap": (
            max(0.0, math.log(TARGET_FACTOR) - math.log(max(factor, 1e-12)))
            + 6.0 * max(0.0, drawdown - TARGET_DRAWDOWN)
            + 0.12 * max(0, MIN_PREFIT_TRADES - metrics["closed_trades"])
            + (0.5 if metrics["add_count"] == 0 else 0.0)
        ),
    }


_WORKER_BOOK: Book | None = None


def _init_worker(book: Book) -> None:
    global _WORKER_BOOK
    _WORKER_BOOK = book


def _batch(configs: list[Config], start: int, end: int) -> list[dict[str, Any]]:
    if _WORKER_BOOK is None:
        raise RuntimeError("worker book not initialized")
    return [
        compact(config, backtest(config, _WORKER_BOOK, start_index=start, terminal_index=end))
        for config in configs
    ]


def search(
    configs: Iterable[Config],
    book: Book,
    *,
    start: int,
    end: int,
    workers: int,
    label: str,
    batch_size: int = 2_000,
) -> pd.DataFrame:
    unique: list[Config] = []
    seen: set[tuple[Any, ...]] = set()
    for config in configs:
        if config.key not in seen:
            seen.add(config.key)
            unique.append(config)
    batches = [unique[offset:offset + batch_size] for offset in range(0, len(unique), batch_size)]
    if workers <= 1:
        _init_worker(book)
        return pd.DataFrame(row for batch in batches for row in _batch(batch, start, end))
    rows: list[dict[str, Any]] = []
    completed = 0
    next_report = 25_000
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(book,)) as executor:
        futures = {executor.submit(_batch, batch, start, end): len(batch) for batch in batches}
        for future in as_completed(futures):
            rows.extend(future.result())
            completed += futures[future]
            if completed >= next_report or completed == len(unique):
                print(f"{label}: {completed}/{len(unique)}", flush=True)
                next_report += 25_000
    return pd.DataFrame(rows)


def rank(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    eligible = frame.loc[
        (frame["closed_trades"] >= MIN_PREFIT_TRADES)
        & (frame["add_count"] >= 1)
        & (frame["max_leverage"] <= MAX_LEVERAGE + 1e-9)
        & (frame["max_drawdown_pct"] > -100.0)
    ].copy()
    if eligible.empty:
        eligible = frame.copy()
    joint_quota = max(1, limit // 2)
    safe_quota = max(1, limit // 4)
    return_quota = max(1, limit // 8)
    drawdown_quota = max(1, limit - joint_quota - safe_quota - return_quota)
    groups = [
        eligible.sort_values(["joint_gap", "annualized_factor"], ascending=[True, False]).head(joint_quota),
    ]
    safe = eligible.loc[eligible["max_drawdown_pct"] >= -20.0]
    if not safe.empty:
        groups.append(
            safe.sort_values(["annualized_factor", "closed_trades"], ascending=[False, False]).head(safe_quota)
        )
    groups.extend([
        eligible.sort_values(["annualized_factor", "max_drawdown_pct"], ascending=[False, False]).head(return_quota),
        eligible.sort_values(["max_drawdown_pct", "annualized_factor"], ascending=[False, False]).head(drawdown_quota),
    ])
    output = pd.concat(groups, ignore_index=True)
    output["key"] = output["config"].map(lambda value: value.key)
    output = output.drop_duplicates("key").drop(columns="key")
    return output.head(limit)


def serialize_config(config: Config) -> dict[str, Any]:
    payload = asdict(config)
    payload.update({
        "ma_type_name": MA_NAMES[config.ma_type],
        "entry_mode_name": ENTRY_NAMES[config.entry_mode],
        "direction_name": DIRECTION_NAMES[config.direction],
        "exit_mode_name": EXIT_NAMES[config.exit_mode],
        "add_mode_name": ADD_NAMES[config.add_mode],
        "ma_fast": 7,
        "ma_slow": 30,
        "max_leverage": MAX_LEVERAGE,
    })
    return payload


def checks(metrics: dict[str, Any], min_trades: int) -> dict[str, bool]:
    return {
        "annualized_factor_gt_20x": metrics["annualized_factor"] > TARGET_FACTOR,
        "max_drawdown_lte_20pct": metrics["max_drawdown_pct"] >= -20.0,
        "minimum_closed_trades": metrics["closed_trades"] >= min_trades,
        "pyramiding_observed": metrics["add_count"] >= 1,
        "leverage_cap": metrics["max_leverage"] <= MAX_LEVERAGE + 1e-9,
    }


def audit(config: Config, book: Book, prefit_end: int, holdout_start: int, retain: bool) -> dict[str, Any]:
    windows = {
        "prefit": (0, prefit_end, MIN_PREFIT_TRADES),
        "researcher_exposed_locked_holdout_flat": (holdout_start, book.daily_count, MIN_HOLDOUT_TRADES),
        "full": (0, book.daily_count, MIN_PREFIT_TRADES),
    }
    output: dict[str, Any] = {}
    retained: dict[str, Result] = {}
    for label, (start, end, min_trades) in windows.items():
        base = backtest(config, book, start_index=start, terminal_index=end, retain=retain)
        stress = backtest(config, book, start_index=start, terminal_index=end, slippage=STRESS_SLIPPAGE)
        delayed = backtest(config, book, start_index=start, terminal_index=end, delay_days=2)
        gate = checks(base.metrics, min_trades)
        output[label] = {
            "base": base.metrics,
            "stress_8bps": stress.metrics,
            "k_plus_2": delayed.metrics,
            "checks": gate,
            "evidence_pass": all(gate.values()),
        }
        retained[label] = base
    return {"config": serialize_config(config), "windows": output, "retained": retained}


def recent_slices(path: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path:
        return []
    frame = pd.DataFrame(path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    end = frame["ts"].iloc[-1]
    windows = {"1d": 1, "7d": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365}
    output: list[dict[str, Any]] = []
    for label, days in windows.items():
        sliced = frame.loc[frame["ts"] >= end - pd.Timedelta(days=days)]
        if len(sliced) < 2:
            continue
        normalized = sliced["equity"] / float(sliced["equity"].iloc[0])
        output.append({
            "window": label,
            "start_ts": sliced["ts"].iloc[0].isoformat(),
            "end_ts": sliced["ts"].iloc[-1].isoformat(),
            "return_pct": float((normalized.iloc[-1] - 1.0) * 100.0),
            "open_path_mdd_pct": float((normalized / normalized.cummax() - 1.0).min() * 100.0),
        })
    return output


def prefit_ablations(config: Config, book: Book, end: int) -> list[dict[str, Any]]:
    variants = {
        "full": config,
        "no_pyramiding_proxy": replace(config, add_step_atr=1e9),
        "no_adx": replace(config, adx_min=0.0),
        "no_atr_cap": replace(config, atr_pct_cap=0.0),
        "no_protective_stop": replace(config, stop_atr=0.0),
        "no_trailing": replace(config, trail_atr=0.0),
        "no_profit_lock": replace(config, profit_trigger_atr=0.0, profit_lock_atr=0.0),
        "no_timeout": replace(config, max_hold_days=0),
        "no_cooldown": replace(config, cooldown_days=0),
        "no_flip": replace(config, allow_flip=False),
    }
    rows: list[dict[str, Any]] = []
    full_signature: list[tuple[str, str, str]] | None = None
    for name, variant in variants.items():
        result = backtest(variant, book, start_index=0, terminal_index=end)
        signature = [(row["entry_ts"], row["exit_ts"], row["side"]) for row in result.trades]
        if name == "full":
            full_signature = signature
        rows.append({
            "variant": name,
            **result.metrics,
            "campaign_boundary_equal_to_full": signature == full_signature,
        })
    return rows


def rolling_audit(config: Config, book: Book, days: int = 90, step: int = 30) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = max(0, 30)
    while start + days <= book.daily_count:
        result = backtest(config, book, start_index=start, terminal_index=start + days)
        rows.append(result.metrics)
        start += step
    return rows


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _config_json(config: Config) -> str:
    return json.dumps(serialize_config(config), ensure_ascii=False, sort_keys=True)


def write_outputs(
    *,
    run_date: str,
    seed: int,
    book: Book,
    prefit_end: int,
    holdout_start: int,
    stage1: pd.DataFrame,
    combined: pd.DataFrame,
    example_audits: dict[str, Any],
    audits: list[dict[str, Any]],
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-search-{run_date}.json"
    frontier_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-prefit-frontier-{run_date}.csv"
    trades_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-primary-trades-{run_date}.csv"
    path_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-primary-path-{run_date}.csv"
    ablation_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-prefit-ablation-{run_date}.csv"
    rolling_path = ARTIFACT_DIR / f"hype-1d-pt-ma7-ma30-rolling-audit-{run_date}.csv"

    primary = audits[0]
    primary_config = Config(**{
        key: primary["config"][key]
        for key in Config.__dataclass_fields__
    })
    clean_audits = [{"config": item["config"], "windows": item["windows"]} for item in audits]
    safe = combined.loc[combined["max_drawdown_pct"] >= -20.0]
    literal_hits = combined.loc[
        (combined["annualized_factor"] > TARGET_FACTOR)
        & (combined["max_drawdown_pct"] >= -20.0)
    ]
    evidence_hits = literal_hits.loc[
        (literal_hits["closed_trades"] >= MIN_PREFIT_TRADES)
        & (literal_hits["add_count"] >= 1)
        & (literal_hits["max_leverage"] <= MAX_LEVERAGE + 1e-9)
    ]
    joint_final = [
        item for item in audits
        if all(window["evidence_pass"] for window in item["windows"].values())
    ]
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "branch": BRANCH,
        "status": "explore / not promoted / not live-ready",
        "contract": {
            "fixed_ma_lengths": [7, 30],
            "max_leverage": MAX_LEVERAGE,
            "target_annualized_factor_strictly_greater_than": TARGET_FACTOR,
            "target_max_drawdown": TARGET_DRAWDOWN,
            "fee_per_fill_notional": FEE,
            "base_slippage_per_fill_notional": SLIPPAGE,
            "stress_slippage_per_fill_notional": STRESS_SLIPPAGE,
            "execution": "closed UTC daily signal; next-open fill; K+2 audited",
            "ledger": "fixed quantity between fills; no free daily leverage reset",
            "holdout_warning": "researcher-exposed due overlap with 2026-07-22 family research",
        },
        "data_quality": book.quality,
        "funding_quality": book.funding_quality,
        "boundaries": {
            "dataset_start": book.ts[0],
            "dataset_end": book.terminal_ts,
            "prefit_end_exclusive": pd.Timestamp([*book.ts, book.terminal_ts][prefit_end]),
            "embargo": "2026-04-30 UTC",
            "holdout_start": pd.Timestamp([*book.ts, book.terminal_ts][holdout_start]),
            "holdout_end": book.terminal_ts,
        },
        "search": {
            "seed": seed,
            "stage1_unique": int(len(stage1)),
            "combined_unique": int(len(combined)),
            "holdout_used_for_selection": False,
            "entry_modes": list(ENTRY_NAMES.values()),
            "ma_types": list(MA_NAMES.values()),
            "add_modes": list(ADD_NAMES.values()),
        },
        "prefit_surface": {
            "literal_factor_drawdown_hits": int(len(literal_hits)),
            "evidence_hits": int(len(evidence_hits)),
            "best_annualized_factor_dd_safe": float(safe["annualized_factor"].max()) if not safe.empty else None,
            "best_annualized_factor_any_drawdown": float(combined["annualized_factor"].max()),
            "best_drawdown_at_factor_gt_20": float(literal_hits["max_drawdown_pct"].max()) if not literal_hits.empty else None,
        },
        "user_example_variants": example_audits,
        "frozen_prefit_primary": primary["config"],
        "frozen_primary_recent_slices": recent_slices(primary["retained"]["full"].path),
        "audited_shortlist": clean_audits,
        "joint_final_pass_count": len(joint_final),
    }
    summary_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default), encoding="utf-8")
    frontier = rank(combined, 300).copy()
    frontier["config"] = frontier["config"].map(_config_json)
    frontier.to_csv(frontier_path, index=False)
    pd.DataFrame(primary["retained"]["full"].trades).to_csv(trades_path, index=False)
    pd.DataFrame(primary["retained"]["full"].path).to_csv(path_path, index=False)
    pd.DataFrame(prefit_ablations(primary_config, book, prefit_end)).to_csv(ablation_path, index=False)
    pd.DataFrame(rolling_audit(primary_config, book)).to_csv(rolling_path, index=False)
    print(json.dumps({
        "summary": str(summary_path.relative_to(ROOT)),
        "frontier": str(frontier_path.relative_to(ROOT)),
        "trades": str(trades_path.relative_to(ROOT)),
        "path": str(path_path.relative_to(ROOT)),
        "ablation": str(ablation_path.relative_to(ROOT)),
        "rolling": str(rolling_path.relative_to(ROOT)),
        "prefit_surface": payload["prefit_surface"],
        "joint_final_pass_count": len(joint_final),
        "primary_windows": primary["windows"],
    }, indent=2, ensure_ascii=False, default=_json_default), flush=True)


def self_test() -> None:
    q, post, turnover = _target_quantity(1.0, 0.0, 3.0, 10.0, FEE + SLIPPAGE)
    assert post > 0.0
    assert abs(q) * 10.0 / post <= 3.0 + 1e-10
    assert turnover > 0.0
    assert math.isclose(_annual_factor(4.0, 730.5), 2.0)
    config = example_config()
    assert config.initial_leverage <= MAX_LEVERAGE
    synthetic_ts = pd.date_range("2026-01-01", periods=4, freq="1D", tz="UTC")
    synthetic_fast = np.array([math.nan, 10.0, 12.0, 11.0])
    synthetic_slow = np.array([math.nan, 11.0, 11.0, 11.0])
    synthetic = Book(
        ts=synthetic_ts,
        terminal_ts=synthetic_ts[-1] + pd.Timedelta(days=1),
        open=np.full(4, 12.0),
        high=np.full(4, 14.0),
        low=np.full(4, 9.0),
        close=np.array([10.0, 10.0, 13.0, 11.0]),
        ma7={0: synthetic_fast, 1: synthetic_fast},
        ma30={0: synthetic_slow, 1: synthetic_slow},
        atr={7: np.ones(4)},
        adx={7: np.full(4, 25.0)},
        prior_high={3: np.full(4, 13.0)},
        prior_low={3: np.full(4, 10.0)},
        funding_by_open=np.zeros(5),
        quality={"terminal_open": 12.0},
        funding_quality={},
    )
    assert entry_side(config, synthetic, 1) == 0  # warmup / prior equality
    assert entry_side(config, synthetic, 2) == 1  # confirmed golden cross
    assert entry_side(config, synthetic, 3) == 0  # exact MA equality stays flat
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    book = build_book()
    prefit_end = int(book.ts.searchsorted(PREFIT_END, side="left"))
    holdout_start = int(book.ts.searchsorted(HOLDOUT_START, side="left"))
    if pd.Timestamp(book.ts[holdout_start]) != HOLDOUT_START:
        raise RuntimeError("locked holdout boundary is absent")
    if pd.Timestamp(book.ts[prefit_end]) != PREFIT_END:
        raise RuntimeError("prefit boundary is absent")

    base = example_config()
    example_variants = {
        "sma_reset_to_3x": base,
        "sma_layers": replace(base, add_mode=0),
        "sma_no_add_proxy": replace(base, add_step_atr=1e9),
        "ema_reset_to_3x": replace(base, ma_type=1),
        "sma_cross_exit_only": replace(base, exit_mode=0),
    }
    example_audits = {
        name: {
            "config": serialize_config(config),
            "windows": audit(config, book, prefit_end, holdout_start, False)["windows"],
        }
        for name, config in example_variants.items()
    }

    rng = random.Random(args.seed)
    seeds = [*example_variants.values()]
    stage1_configs = iter([*seeds, *(random_config(rng) for _ in range(args.stage1))])
    stage1 = search(
        stage1_configs,
        book,
        start=0,
        end=prefit_end,
        workers=args.workers,
        label="stage1",
    )
    parents = list(rank(stage1, max(80, min(args.shortlist, 400)))["config"])
    if not parents:
        raise RuntimeError("stage1 returned no parents")
    stage2 = search(
        (mutate(rng.choice(parents), rng) for _ in range(args.stage2)),
        book,
        start=0,
        end=prefit_end,
        workers=args.workers,
        label="stage2",
    )
    combined = pd.concat([stage1, stage2], ignore_index=True)
    combined["key"] = combined["config"].map(lambda value: value.key)
    combined = combined.drop_duplicates("key").drop(columns="key")
    frozen = list(rank(combined, args.shortlist)["config"])
    audits = [audit(config, book, prefit_end, holdout_start, retain=index == 0) for index, config in enumerate(frozen)]
    write_outputs(
        run_date=args.run_date,
        seed=args.seed,
        book=book,
        prefit_end=prefit_end,
        holdout_start=holdout_start,
        stage1=stage1,
        combined=combined,
        example_audits=example_audits,
        audits=audits,
    )


if __name__ == "__main__":
    main()
