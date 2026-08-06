from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import importlib.util
import json
import math
from pathlib import Path
import random
import sys
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
BASE_SCRIPT = (
    FAMILY_DIR / "scripts/research_hype_1d_ma7_asymmetric_body_trend.py"
)

FAMILY = "HYPE-1D-MA7-Asymmetric-Body-Trend"
BRANCH = "separated-trend-search"
FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MA_WINDOW = 7
HOLDOUT_START = pd.Timestamp("2026-05-01T00:00:00Z")
ENTRY_MODES = (
    "regime",
    "reclaim",
    "pullback_reclaim",
    "breakout",
    "open_regime",
)
RECENT_WINDOWS = {
    "1d": 1,
    "7d": 7,
    "1m": 30,
    "3m": 90,
    "6m": 182,
    "1y": 365,
}


@dataclass(frozen=True, slots=True)
class Config:
    side: int
    entry_mode: str
    slope_lookback: int
    slope_min_atr: float
    confirm_days: int
    entry_buffer_atr: float
    pullback_lookback: int
    pullback_touch_atr: float
    breakout_lookback: int
    exit_confirm_days: int
    exit_buffer_atr: float
    slope_exit_lookback: int
    hard_stop_atr: float
    trail_atr: float
    max_hold_days: int
    cooldown_days: int

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


@dataclass(slots=True)
class Features:
    ma7: np.ndarray
    atr7: np.ndarray
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    hourly_open: np.ndarray
    hourly_high: np.ndarray
    hourly_low: np.ndarray
    funding_events: list[list["FundingEvent"]]


@dataclass(frozen=True, slots=True)
class FundingEvent:
    ts: pd.Timestamp
    rate: float
    price: float


@dataclass(slots=True)
class Result:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Search {FAMILY} {BRANCH}.")
    parser.add_argument("--samples-per-side", type=int, default=20_000)
    parser.add_argument("--shortlist", type=int, default=120)
    parser.add_argument("--pair-pool", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_base() -> Any:
    spec = importlib.util.spec_from_file_location("hype_1d_ma7_abt_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import base research script: {BASE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_features(
    book: Any,
    hourly: pd.DataFrame,
    funding: pd.DataFrame,
) -> Features:
    close = pd.Series(book.close, dtype=float)
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            pd.Series(book.high - book.low),
            pd.Series(book.high).sub(previous_close).abs(),
            pd.Series(book.low).sub(previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    windows = (2, 3, 5, 7, 10, 14)
    hourly_frame = hourly.copy()
    hourly_frame["ts"] = pd.to_datetime(hourly_frame["ts"], utc=True)
    hourly_frame = hourly_frame.set_index("ts").sort_index()
    funding_frame = funding.copy()
    funding_frame["ts"] = pd.to_datetime(funding_frame["ts"], utc=True)
    funding_frame = funding_frame.sort_values("ts")
    hourly_open: list[np.ndarray] = []
    hourly_high: list[np.ndarray] = []
    hourly_low: list[np.ndarray] = []
    funding_events: list[list[FundingEvent]] = []
    for day_start in book.ts:
        day_end = pd.Timestamp(day_start) + pd.Timedelta(days=1)
        bars = hourly_frame.loc[
            (hourly_frame.index >= day_start) & (hourly_frame.index < day_end)
        ]
        if len(bars) != 24:
            raise RuntimeError(
                f"expected 24 hourly bars from {day_start}, got {len(bars)}"
            )
        hourly_open.append(bars["open"].to_numpy("float64"))
        hourly_high.append(bars["high"].to_numpy("float64"))
        hourly_low.append(bars["low"].to_numpy("float64"))
        day_funding = funding_frame.loc[
            funding_frame["ts"].ge(day_start)
            & funding_frame["ts"].lt(day_end)
        ]
        events: list[FundingEvent] = []
        for row in day_funding.itertuples(index=False):
            event_ts = pd.Timestamp(row.ts)
            event_hour = event_ts.floor("h")
            if event_hour not in bars.index:
                raise RuntimeError(
                    f"funding event {event_ts} has no event-hour candle"
                )
            events.append(
                FundingEvent(
                    ts=event_ts,
                    rate=float(row.funding_rate),
                    price=float(bars.loc[event_hour, "open"]),
                )
            )
        funding_events.append(events)
    return Features(
        ma7=close.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean().to_numpy(),
        atr7=true_range.rolling(MA_WINDOW, min_periods=MA_WINDOW).mean().to_numpy(),
        prior_high={
            window: pd.Series(book.high)
            .shift(1)
            .rolling(window, min_periods=window)
            .max()
            .to_numpy()
            for window in windows
        },
        prior_low={
            window: pd.Series(book.low)
            .shift(1)
            .rolling(window, min_periods=window)
            .min()
            .to_numpy()
            for window in windows
        },
        hourly_open=np.asarray(hourly_open, dtype=float),
        hourly_high=np.asarray(hourly_high, dtype=float),
        hourly_low=np.asarray(hourly_low, dtype=float),
        funding_events=funding_events,
    )


def _trend_ok(
    config: Config,
    book: Any,
    features: Features,
    index: int,
) -> bool:
    prior = index - config.slope_lookback
    if prior < 0:
        return False
    values = (
        features.ma7[index],
        features.ma7[prior],
        features.atr7[index],
        book.close[index],
    )
    if not all(np.isfinite(value) for value in values) or features.atr7[index] <= 0:
        return False
    slope = (
        config.side
        * (features.ma7[index] - features.ma7[prior])
        / features.atr7[index]
    )
    return slope >= config.slope_min_atr


def _confirmed_side(
    config: Config,
    book: Any,
    features: Features,
    index: int,
) -> bool:
    left = index - config.confirm_days + 1
    if left < 0:
        return False
    for offset in range(left, index + 1):
        ma = features.ma7[offset]
        atr = features.atr7[offset]
        if not np.isfinite(ma) or not np.isfinite(atr):
            return False
        if config.side * (book.close[offset] - ma) <= config.entry_buffer_atr * atr:
            return False
    return True


def close_entry_signal(
    config: Config,
    book: Any,
    features: Features,
    index: int,
) -> bool:
    if index < 1 or config.entry_mode == "open_regime":
        return False
    if not _trend_ok(config, book, features, index):
        return False
    if not _confirmed_side(config, book, features, index):
        return False
    ma = features.ma7[index]
    atr = features.atr7[index]
    signed = config.side * (book.close[index] - ma)
    if config.entry_mode == "regime":
        return signed > config.entry_buffer_atr * atr
    if config.entry_mode == "reclaim":
        prior_ma = features.ma7[index - 1]
        prior_atr = features.atr7[index - 1]
        return (
            np.isfinite(prior_ma)
            and np.isfinite(prior_atr)
            and config.side * (book.close[index - 1] - prior_ma)
            <= config.pullback_touch_atr * prior_atr
        )
    if config.entry_mode == "pullback_reclaim":
        left = max(0, index - config.pullback_lookback)
        touched = False
        for offset in range(left, index):
            offset_ma = features.ma7[offset]
            offset_atr = features.atr7[offset]
            if (
                np.isfinite(offset_ma)
                and np.isfinite(offset_atr)
                and config.side * (book.close[offset] - offset_ma)
                <= config.pullback_touch_atr * offset_atr
            ):
                touched = True
                break
        return touched
    if config.entry_mode == "breakout":
        boundary = (
            features.prior_high[config.breakout_lookback][index]
            if config.side > 0
            else features.prior_low[config.breakout_lookback][index]
        )
        return bool(
            np.isfinite(boundary)
            and config.side * (book.close[index] - boundary)
            > config.entry_buffer_atr * atr
        )
    raise ValueError(config.entry_mode)


def open_entry_signal(
    config: Config,
    book: Any,
    features: Features,
    index: int,
) -> bool:
    if config.entry_mode != "open_regime" or index < 1:
        return False
    prior = index - 1
    if not _trend_ok(config, book, features, prior):
        return False
    ma = features.ma7[prior]
    atr = features.atr7[prior]
    return bool(
        np.isfinite(ma)
        and np.isfinite(atr)
        and config.side * (book.open[index] - ma)
        > config.entry_buffer_atr * atr
    )


def signal_exit(
    config: Config,
    book: Any,
    features: Features,
    index: int,
    bars_held: int,
) -> str:
    left = index - config.exit_confirm_days + 1
    if left >= 0:
        crossed = True
        for offset in range(left, index + 1):
            ma = features.ma7[offset]
            atr = features.atr7[offset]
            if (
                not np.isfinite(ma)
                or not np.isfinite(atr)
                or config.side * (book.close[offset] - ma)
                >= -config.exit_buffer_atr * atr
            ):
                crossed = False
                break
        if crossed:
            return "ma7_hysteresis_exit"
    if config.slope_exit_lookback > 0:
        prior = index - config.slope_exit_lookback
        if (
            prior >= 0
            and np.isfinite(features.ma7[index])
            and np.isfinite(features.ma7[prior])
            and config.side * (features.ma7[index] - features.ma7[prior]) <= 0.0
        ):
            return "ma7_slope_exit"
    if config.max_hold_days > 0 and bars_held >= config.max_hold_days:
        return "max_hold"
    return ""


def _target_quantity(
    equity: float,
    old_qty: float,
    target_side: int,
    price: float,
    cost_rate: float,
) -> tuple[float, float, float]:
    post_equity = equity
    target_qty = old_qty
    turnover = 0.0
    for _ in range(20):
        target_qty = target_side * post_equity / price
        turnover = abs(target_qty - old_qty) * price
        updated = equity - turnover * cost_rate
        if math.isclose(updated, post_equity, rel_tol=0.0, abs_tol=1e-14):
            post_equity = updated
            break
        post_equity = updated
    return target_qty, post_equity, turnover


def buy_and_hold(
    book: Any,
    features: Features,
    *,
    slippage: float = BASE_SLIPPAGE,
) -> dict[str, Any]:
    cost_rate = FEE + slippage
    entry_price = float(book.open[0])
    exit_price = float(book.quality["terminal_open"])
    qty, equity, entry_turnover = _target_quantity(
        1.0,
        0.0,
        1,
        entry_price,
        cost_rate,
    )
    funding_payment = 0.0
    for events in features.funding_events:
        for event in events:
            payment = qty * event.price * event.rate
            equity -= payment
            funding_payment += payment
    equity += qty * (exit_price - entry_price)
    exit_turnover = abs(qty) * exit_price
    exit_cost = exit_turnover * cost_rate
    equity -= exit_cost
    days = (
        pd.Timestamp(book.terminal_ts) - pd.Timestamp(book.ts[0])
    ).total_seconds() / 86_400.0
    annualized = equity ** (365.25 / days) if equity > 0.0 else 0.0
    return {
        "start_ts": pd.Timestamp(book.ts[0]).isoformat(),
        "end_ts": pd.Timestamp(book.terminal_ts).isoformat(),
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "annualized_factor": annualized,
        "funding_pct_initial": funding_payment * 100.0,
        "cost_pct_initial": (
            entry_turnover * cost_rate + exit_cost
        )
        * 100.0,
    }


def backtest(
    book: Any,
    features: Features,
    *,
    long_config: Config | None,
    short_config: Config | None,
    start_index: int,
    terminal_index: int,
    slippage: float = BASE_SLIPPAGE,
    signal_lag: int = 0,
    include_funding: bool = True,
    retain: bool = False,
) -> Result:
    if long_config is not None and long_config.side != 1:
        raise ValueError("long config must have side=1")
    if short_config is not None and short_config.side != -1:
        raise ValueError("short config must have side=-1")
    if not (0 <= start_index < terminal_index <= book.count):
        raise ValueError("invalid window")
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    opens = np.r_[book.open, float(book.quality["terminal_open"])]
    configs = {1: long_config, -1: short_config}
    cost_rate = FEE + slippage
    equity = 1.0
    qty = 0.0
    side = 0
    mark_price = float(opens[start_index])
    peak = 1.0
    max_drawdown = 0.0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    max_intraday_leverage = 0.0
    cooldown_left = 0
    bars_held = 0
    stop_price = math.nan
    highest_close = -math.inf
    lowest_close = math.inf
    entry_ts: pd.Timestamp | None = None
    entry_price = math.nan
    entry_equity = math.nan
    entry_side = 0
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []
    equity_points: list[float] = [1.0]
    bankrupt = False

    def trade_to(target_side: int, price: float) -> None:
        nonlocal equity, qty, side, total_turnover, total_cost
        old_equity = equity
        qty, equity, turnover = _target_quantity(
            equity, qty, target_side, price, cost_rate
        )
        total_turnover += turnover
        total_cost += old_equity - equity
        side = target_side

    def enter(
        config: Config,
        ts: pd.Timestamp,
        price: float,
        index: int,
        signal_index: int,
    ) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_side
        nonlocal bars_held, stop_price, highest_close, lowest_close, mark_price
        before = equity
        trade_to(config.side, price)
        entry_ts = ts
        entry_price = price
        entry_equity = before
        entry_side = config.side
        bars_held = 0
        highest_close = -math.inf
        lowest_close = math.inf
        atr = features.atr7[signal_index]
        stop_price = (
            price - config.side * config.hard_stop_atr * atr
            if config.hard_stop_atr > 0.0 and np.isfinite(atr)
            else math.nan
        )
        mark_price = price

    def settle_funding(
        index: int,
        start_ts: pd.Timestamp,
        end_ts: pd.Timestamp,
    ) -> None:
        nonlocal equity, total_funding
        if not include_funding or qty == 0.0:
            return
        for event in features.funding_events[index]:
            if start_ts <= event.ts < end_ts:
                payment = qty * event.price * event.rate
                equity -= payment
                total_funding += payment

    def close(
        ts: pd.Timestamp,
        price: float,
        reason: str,
        index: int,
    ) -> None:
        nonlocal entry_ts, entry_price, entry_equity, entry_side
        nonlocal bars_held, stop_price, highest_close, lowest_close
        if entry_ts is None:
            raise RuntimeError("cannot close absent position")
        old_side = entry_side
        trade_to(0, price)
        trades.append(
            {
                "entry_ts": entry_ts.isoformat(),
                "exit_ts": ts.isoformat(),
                "side": "long" if old_side > 0 else "short",
                "entry_price": entry_price,
                "exit_price": price,
                "bars_held": index - int(
                    pd.DatetimeIndex(timestamps).searchsorted(entry_ts.floor("1D"))
                ),
                "exit_reason": reason,
                "net_return": equity / entry_equity - 1.0,
                "net_pnl": equity - entry_equity,
            }
        )
        entry_ts = None
        entry_price = entry_equity = math.nan
        entry_side = 0
        bars_held = 0
        stop_price = math.nan
        highest_close = -math.inf
        lowest_close = math.inf

    for index in range(start_index, terminal_index + 1):
        ts = pd.Timestamp(timestamps[index])
        current_open = float(opens[index])
        if index > start_index and qty != 0.0:
            equity += qty * (current_open - mark_price)
        mark_price = current_open
        if equity <= 0.0:
            bankrupt = True
            equity = 0.0
            max_drawdown = -1.0
            break

        pre_action_equity = equity
        action = "hold"
        entered_after_open = False
        exited_at_open = False
        decision_index = index - 1 - signal_lag
        if index < terminal_index and side != 0 and decision_index >= 0:
            config = configs[side]
            if config is None:
                raise RuntimeError("active side has no config")
            reason = signal_exit(
                config,
                book,
                features,
                decision_index,
                bars_held,
            )
            if reason:
                close(ts, current_open, reason, index)
                cooldown_left = config.cooldown_days
                exited_at_open = True
                action = reason

        if index < terminal_index and side == 0:
            if cooldown_left > 0:
                if not exited_at_open:
                    cooldown_left -= 1
            else:
                selected: Config | None = None
                signal_index = max(0, decision_index)
                if long_config is not None and close_entry_signal(
                    long_config,
                    book,
                    features,
                    signal_index,
                ):
                    selected = long_config
                elif short_config is not None and close_entry_signal(
                    short_config,
                    book,
                    features,
                    signal_index,
                ):
                    selected = short_config
                elif (
                    short_config is not None
                    and open_entry_signal(
                        short_config,
                        book,
                        features,
                        index - signal_lag,
                    )
                ):
                    selected = short_config
                if selected is not None:
                    fill_ts = ts
                    fill_price = current_open
                    if selected.entry_mode == "open_regime" and signal_lag == 0:
                        fill_ts = ts + pd.Timedelta(hours=1)
                        fill_price = float(book.short_entry_open[index])
                        entered_after_open = True
                    enter(selected, fill_ts, fill_price, index, signal_index)
                    action = "enter_long" if selected.side > 0 else "enter_short"

        post_action_equity = equity
        peak = max(peak, pre_action_equity, post_action_equity)
        max_drawdown = min(max_drawdown, post_action_equity / peak - 1.0)
        if index >= terminal_index:
            equity_points.append(post_action_equity)
            if retain:
                path.append(
                    {
                        "ts": ts.isoformat(),
                        "pre_action_equity": pre_action_equity,
                        "post_action_equity": post_action_equity,
                        "close_equity": post_action_equity,
                        "favorable_equity": post_action_equity,
                        "adverse_equity": post_action_equity,
                        "position": side,
                        "action": "terminal",
                    }
                )
            continue

        if side != 0:
            config = configs[side]
            if config is None:
                raise RuntimeError("active side has no config")
            position_mark = mark_price if entered_after_open else current_open
            day_high = (
                float(book.post_short_entry_high[index])
                if entered_after_open
                else float(book.high[index])
            )
            day_low = (
                float(book.post_short_entry_low[index])
                if entered_after_open
                else float(book.low[index])
            )
            if post_action_equity > 0.0:
                max_intraday_leverage = max(
                    max_intraday_leverage,
                    abs(qty) * position_mark / post_action_equity,
                )
            gap_hit = np.isfinite(stop_price) and (
                (side > 0 and position_mark <= stop_price)
                or (side < 0 and position_mark >= stop_price)
            )
            start_hour = 1 if entered_after_open else 0
            hourly_high = features.hourly_high[index, start_hour:]
            hourly_low = features.hourly_low[index, start_hour:]
            stop_crosses = (
                hourly_low <= stop_price
                if side > 0
                else hourly_high >= stop_price
            )
            crossed = (
                np.flatnonzero(stop_crosses)
                if np.isfinite(stop_price)
                else np.array([], dtype=int)
            )
            hit_hour = (
                start_hour + int(crossed[0]) if len(crossed) else None
            )
            intraday_hit = hit_hour is not None
            holding_start = (
                max(ts, entry_ts)
                if entry_ts is not None
                else ts
            )
            if gap_hit or intraday_hit:
                hour_gap_hit = (
                    hit_hour is not None
                    and (
                        (
                            side > 0
                            and features.hourly_open[index, hit_hour]
                            <= stop_price
                        )
                        or (
                            side < 0
                            and features.hourly_open[index, hit_hour]
                            >= stop_price
                        )
                    )
                )
                fill = (
                    position_mark
                    if gap_hit
                    else (
                        float(features.hourly_open[index, hit_hour])
                        if hour_gap_hit
                        else float(stop_price)
                    )
                )
                stop_fill_ts = (
                    holding_start
                    if gap_hit
                    else (
                        ts + pd.Timedelta(hours=hit_hour)
                        if hour_gap_hit
                        else ts + pd.Timedelta(hours=hit_hour + 1)
                    )
                )
                settle_funding(index, holding_start, stop_fill_ts)
                position_qty = qty
                position_side = side
                funded_open_equity = equity
                completed_end = 0 if gap_hit else int(hit_hour)
                completed_high = features.hourly_high[
                    index, start_hour:completed_end
                ]
                completed_low = features.hourly_low[
                    index, start_hour:completed_end
                ]
                if len(completed_high):
                    favorable = (
                        max(position_mark, fill, float(completed_high.max()))
                        if position_side > 0
                        else min(position_mark, fill, float(completed_low.min()))
                    )
                    adverse = (
                        min(position_mark, fill, float(completed_low.min()))
                        if position_side > 0
                        else max(position_mark, fill, float(completed_high.max()))
                    )
                    favorable_equity = funded_open_equity + position_qty * (
                        favorable - position_mark
                    )
                    adverse_equity = funded_open_equity + position_qty * (
                        adverse - position_mark
                    )
                else:
                    favorable_equity = adverse_equity = funded_open_equity
                equity += qty * (fill - position_mark)
                close(stop_fill_ts, fill, "protective_stop", index)
                cooldown_left = config.cooldown_days
                mark_price = fill
                action = "protective_stop"
                favorable_equity = max(favorable_equity, equity)
                adverse_equity = min(adverse_equity, equity)
                close_equity = equity
            else:
                settle_funding(
                    index,
                    holding_start,
                    ts + pd.Timedelta(days=1),
                )
                favorable = day_high if side > 0 else day_low
                adverse = day_low if side > 0 else day_high
                favorable_equity = equity + qty * (favorable - position_mark)
                adverse_equity = equity + qty * (adverse - position_mark)
                close_equity = equity + qty * (
                    float(book.close[index]) - position_mark
                )
                if adverse_equity <= 0.0:
                    bankrupt = True
                    equity = 0.0
                    qty = 0.0
                    side = 0
                    close_equity = 0.0
                    max_drawdown = -1.0
                    action = "intraday_bankruptcy"
                else:
                    bars_held += 1
                    highest_close = max(highest_close, float(book.close[index]))
                    lowest_close = min(lowest_close, float(book.close[index]))
                    atr = features.atr7[index]
                    if config.trail_atr > 0.0 and np.isfinite(atr):
                        anchor = highest_close if side > 0 else lowest_close
                        candidate = anchor - side * config.trail_atr * atr
                        if not np.isfinite(stop_price):
                            stop_price = candidate
                        elif side > 0:
                            stop_price = max(stop_price, candidate)
                        else:
                            stop_price = min(stop_price, candidate)
            peak = max(peak, favorable_equity, close_equity)
            max_drawdown = min(
                max_drawdown,
                adverse_equity / peak - 1.0,
                close_equity / peak - 1.0,
            )
        else:
            favorable_equity = adverse_equity = close_equity = equity

        if retain:
            path.append(
                {
                    "ts": ts.isoformat(),
                    "pre_action_equity": pre_action_equity,
                    "post_action_equity": post_action_equity,
                    "close_equity": close_equity,
                    "favorable_equity": favorable_equity,
                    "adverse_equity": adverse_equity,
                    "position": side,
                    "action": action,
                }
            )
        equity_points.append(float(close_equity))
        if bankrupt:
            break

    if qty != 0.0 and equity > 0.0:
        terminal_price = float(opens[terminal_index])
        close(
            pd.Timestamp(timestamps[terminal_index]),
            terminal_price,
            "terminal_flatten",
            terminal_index,
        )
        if retain and path and path[-1]["action"] == "terminal":
            path[-1]["post_action_equity"] = equity
            path[-1]["close_equity"] = equity
            path[-1]["favorable_equity"] = equity
            path[-1]["adverse_equity"] = equity
            path[-1]["position"] = 0
            path[-1]["action"] = "terminal_flatten"
        equity_points[-1] = equity
        peak = max(peak, equity)
        max_drawdown = min(max_drawdown, equity / peak - 1.0)
    days = max(
        1.0,
        (timestamps[terminal_index] - timestamps[start_index]).total_seconds()
        / 86_400.0,
    )
    trade_pnl = np.array(
        [float(row["net_pnl"]) for row in trades],
        dtype=float,
    )
    gross_profit = (
        float(trade_pnl[trade_pnl > 0.0].sum())
        if len(trade_pnl)
        else 0.0
    )
    gross_loss = (
        float(-trade_pnl[trade_pnl < 0.0].sum())
        if len(trade_pnl)
        else 0.0
    )
    equity_series = pd.Series(equity_points, dtype=float)
    returns = (
        equity_series.pct_change()
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    sharpe = (
        float(np.sqrt(365.25) * returns.mean() / returns.std(ddof=1))
        if len(returns) >= 30 and returns.std(ddof=1) > 0.0
        else math.nan
    )
    metrics = {
        "start_ts": pd.Timestamp(timestamps[start_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_index]).isoformat(),
        "days": days,
        "equity_multiple": equity,
        "net_return_pct": (equity - 1.0) * 100.0,
        "max_drawdown_pct": max_drawdown * 100.0,
        "sharpe": sharpe,
        "closed_trades": len(trades),
        "long_trades": sum(row["side"] == "long" for row in trades),
        "short_trades": sum(row["side"] == "short" for row in trades),
        "win_rate": (
            float((trade_pnl > 0.0).mean())
            if len(trade_pnl)
            else math.nan
        ),
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0.0
            else (math.inf if gross_profit > 0.0 else math.nan)
        ),
        "turnover_multiple": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_pct_initial": total_funding * 100.0,
        "max_intraday_leverage": max_intraday_leverage,
        "bankrupt_intraday": bankrupt,
    }
    return Result(metrics=metrics, trades=trades, path=path)


def random_config(side: int, rng: random.Random) -> Config:
    entry_modes = (
        ("regime", "reclaim", "pullback_reclaim", "breakout")
        if side > 0
        else ENTRY_MODES
    )
    return Config(
        side=side,
        entry_mode=rng.choice(entry_modes),
        slope_lookback=rng.choice((1, 2, 3, 5, 7)),
        slope_min_atr=rng.choice((0.0, 0.02, 0.05, 0.10, 0.20)),
        confirm_days=rng.choice((1, 1, 2, 3)),
        entry_buffer_atr=rng.choice((0.0, 0.10, 0.25, 0.50)),
        pullback_lookback=rng.choice((2, 3, 5, 7, 10)),
        pullback_touch_atr=rng.choice((-0.50, -0.25, 0.0, 0.10, 0.25)),
        breakout_lookback=rng.choice((2, 3, 5, 7, 10, 14)),
        exit_confirm_days=rng.choice((1, 1, 2, 3)),
        exit_buffer_atr=rng.choice((0.0, 0.10, 0.25, 0.50, 0.75, 1.0)),
        slope_exit_lookback=rng.choice((0, 0, 1, 2, 3, 5)),
        hard_stop_atr=rng.choice((0.0, 0.0, 1.5, 2.0, 3.0, 4.0, 5.0)),
        trail_atr=rng.choice((0.0, 0.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0)),
        max_hold_days=rng.choice((0, 0, 10, 20, 30, 60, 90)),
        cooldown_days=rng.choice((0, 0, 1, 2, 3, 5)),
    )


def unique_configs(
    side: int,
    rng: random.Random,
    count: int,
) -> list[Config]:
    output: list[Config] = []
    seen: set[tuple[Any, ...]] = set()
    while len(output) < count:
        config = random_config(side, rng)
        if config.key not in seen:
            seen.add(config.key)
            output.append(config)
    return output


def _run_single(
    config: Config,
    book: Any,
    features: Features,
    start: int,
    end: int,
) -> Result:
    return backtest(
        book,
        features,
        long_config=config if config.side > 0 else None,
        short_config=config if config.side < 0 else None,
        start_index=start,
        terminal_index=end,
    )


def stage1_search(
    configs: Iterable[Config],
    book: Any,
    features: Features,
    *,
    end: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, config in enumerate(configs, start=1):
        result = _run_single(config, book, features, 0, end)
        metrics = result.metrics
        drawdown = abs(min(0.0, metrics["max_drawdown_pct"] / 100.0))
        eligible = (
            metrics["closed_trades"] >= 5
            and not metrics["bankrupt_intraday"]
            and metrics["equity_multiple"] > 0.0
        )
        score = (
            math.log(max(metrics["equity_multiple"], 1e-12))
            - 2.0 * max(0.0, drawdown - 0.50)
            + 0.01 * min(20, metrics["closed_trades"])
            if eligible
            else -math.inf
        )
        rows.append(
            {
                "config": config,
                "score": score,
                **metrics,
            }
        )
        if index % 5_000 == 0:
            print(f"stage1 side={config.side}: {index}", flush=True)
    return pd.DataFrame(rows)


def stability_audit(
    configs: Iterable[Config],
    book: Any,
    features: Features,
    *,
    prefit_end: int,
) -> pd.DataFrame:
    midpoint = prefit_end // 2
    windows = {
        "prefit": (0, prefit_end),
        "early_half": (0, midpoint),
        "late_half": (midpoint, prefit_end),
        "recent_prefit_90d": (max(0, prefit_end - 90), prefit_end),
    }
    rows: list[dict[str, Any]] = []
    for config in configs:
        row: dict[str, Any] = {"config": config}
        log_equities: list[float] = []
        profitable = 0
        total_trades = 0
        worst_drawdown = 0.0
        valid = True
        for label, (start, end) in windows.items():
            result = _run_single(config, book, features, start, end)
            metrics = result.metrics
            equity = float(metrics["equity_multiple"])
            row[f"{label}_equity"] = equity
            row[f"{label}_mdd_pct"] = metrics["max_drawdown_pct"]
            row[f"{label}_trades"] = metrics["closed_trades"]
            profitable += int(equity > 1.0)
            total_trades += int(metrics["closed_trades"])
            worst_drawdown = min(worst_drawdown, metrics["max_drawdown_pct"])
            valid = valid and equity > 0.0 and not metrics["bankrupt_intraday"]
            log_equities.append(math.log(max(equity, 1e-12)))
        row["profitable_windows"] = profitable
        row["worst_window_mdd_pct"] = worst_drawdown
        row["total_window_trades"] = total_trades
        delayed = backtest(
            book,
            features,
            long_config=config if config.side > 0 else None,
            short_config=config if config.side < 0 else None,
            start_index=0,
            terminal_index=prefit_end,
            signal_lag=1,
        ).metrics
        stressed = backtest(
            book,
            features,
            long_config=config if config.side > 0 else None,
            short_config=config if config.side < 0 else None,
            start_index=0,
            terminal_index=prefit_end,
            slippage=STRESS_SLIPPAGE,
        ).metrics
        row["prefit_delayed_equity"] = delayed["equity_multiple"]
        row["prefit_stressed_equity"] = stressed["equity_multiple"]
        row["prefit_delayed_mdd_pct"] = delayed["max_drawdown_pct"]
        row["prefit_stressed_mdd_pct"] = stressed["max_drawdown_pct"]
        robust_logs = [
            *log_equities,
            math.log(max(float(delayed["equity_multiple"]), 1e-12)),
            math.log(max(float(stressed["equity_multiple"]), 1e-12)),
        ]
        row["robust_score"] = (
            min(robust_logs)
            + 0.5 * float(np.median(robust_logs))
            + 0.25 * log_equities[0]
            - 1.5 * max(0.0, abs(worst_drawdown) / 100.0 - 0.50)
            + 0.05 * profitable
            if valid and row["prefit_trades"] >= 5
            else -math.inf
        )
        rows.append(row)
    return pd.DataFrame(rows)


def serialize_config(config: Config | None) -> dict[str, Any] | None:
    return None if config is None else asdict(config)


def rank_stable(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    return frame.sort_values(
        ["robust_score", "prefit_equity", "worst_window_mdd_pct"],
        ascending=[False, False, False],
    ).head(limit)


def audit_candidate(
    label: str,
    long_config: Config | None,
    short_config: Config | None,
    book: Any,
    features: Features,
    *,
    prefit_end: int,
    retain_full: bool,
) -> dict[str, Any]:
    windows = {
        "prefit": (0, prefit_end),
        "researcher_exposed_last_90d_flat": (prefit_end, book.count),
        "full": (0, book.count),
    }
    output: dict[str, Any] = {
        "label": label,
        "long_config": serialize_config(long_config),
        "short_config": serialize_config(short_config),
        "windows": {},
    }
    retained: dict[str, Result] = {}
    for name, (start, end) in windows.items():
        result = backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
            retain=retain_full and name == "full",
        )
        stress = backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
            slippage=STRESS_SLIPPAGE,
        )
        delayed = backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
            signal_lag=1,
        )
        output["windows"][name] = {
            "base": result.metrics,
            "stress_8bps": stress.metrics,
            "one_day_extra_delay": delayed.metrics,
        }
        retained[name] = result
    output["historical_profit_check"] = {
        "prefit_positive": output["windows"]["prefit"]["base"]["equity_multiple"] > 1.0,
        "last_90d_positive": (
            output["windows"]["researcher_exposed_last_90d_flat"]["base"][
                "equity_multiple"
            ]
            > 1.0
        ),
        "full_positive": output["windows"]["full"]["base"]["equity_multiple"] > 1.0,
        "last_90d_stress_positive": (
            output["windows"]["researcher_exposed_last_90d_flat"]["stress_8bps"][
                "equity_multiple"
            ]
            > 1.0
        ),
        "full_stress_positive": (
            output["windows"]["full"]["stress_8bps"]["equity_multiple"] > 1.0
        ),
        "prefit_delay_positive": (
            output["windows"]["prefit"]["one_day_extra_delay"][
                "equity_multiple"
            ]
            > 1.0
        ),
        "full_delay_positive": (
            output["windows"]["full"]["one_day_extra_delay"][
                "equity_multiple"
            ]
            > 1.0
        ),
        "full_mdd_better_than_50pct": (
            output["windows"]["full"]["base"]["max_drawdown_pct"] >= -50.0
        ),
    }
    output["retained"] = retained
    return output


def historical_score(audit: dict[str, Any]) -> float:
    if not all(audit["historical_profit_check"].values()):
        return -math.inf
    windows = audit["windows"]
    equities = [
        windows["prefit"]["base"]["equity_multiple"],
        windows["researcher_exposed_last_90d_flat"]["base"]["equity_multiple"],
        windows["full"]["base"]["equity_multiple"],
        windows["researcher_exposed_last_90d_flat"]["stress_8bps"][
            "equity_multiple"
        ],
        windows["full"]["stress_8bps"]["equity_multiple"],
        windows["prefit"]["one_day_extra_delay"]["equity_multiple"],
        windows["full"]["one_day_extra_delay"]["equity_multiple"],
    ]
    return min(math.log(float(value)) for value in equities) + 0.25 * math.log(
        float(windows["full"]["base"]["equity_multiple"])
    )


def find_historical_observation(
    candidates: Iterable[tuple[str, Config | None, Config | None]],
    book: Any,
    features: Features,
    *,
    prefit_end: int,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_score = -math.inf
    for label, long_config, short_config in candidates:
        audit = audit_candidate(
            label,
            long_config,
            short_config,
            book,
            features,
            prefit_end=prefit_end,
            retain_full=False,
        )
        score = historical_score(audit)
        if score > best_score:
            best = audit
            best_score = score
    if best is None or not np.isfinite(best_score):
        return None
    return audit_candidate(
        best["label"],
        (
            Config(**best["long_config"])
            if best["long_config"] is not None
            else None
        ),
        (
            Config(**best["short_config"])
            if best["short_config"] is not None
            else None
        ),
        book,
        features,
        prefit_end=prefit_end,
        retain_full=True,
    )


def pair_search(
    long_configs: list[Config],
    short_configs: list[Config],
    book: Any,
    features: Features,
    *,
    prefit_end: int,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    midpoint = prefit_end // 2
    windows = (
        (0, prefit_end),
        (0, midpoint),
        (midpoint, prefit_end),
        (max(0, prefit_end - 90), prefit_end),
    )
    for long_config in long_configs:
        for short_config in short_configs:
            metrics = [
                backtest(
                    book,
                    features,
                    long_config=long_config,
                    short_config=short_config,
                    start_index=start,
                    terminal_index=end,
                ).metrics
                for start, end in windows
            ]
            equities = [float(item["equity_multiple"]) for item in metrics]
            delayed_prefit = backtest(
                book,
                features,
                long_config=long_config,
                short_config=short_config,
                start_index=0,
                terminal_index=prefit_end,
                signal_lag=1,
            ).metrics
            stressed_prefit = backtest(
                book,
                features,
                long_config=long_config,
                short_config=short_config,
                start_index=0,
                terminal_index=prefit_end,
                slippage=STRESS_SLIPPAGE,
            ).metrics
            robust_equities = [
                *equities,
                float(delayed_prefit["equity_multiple"]),
                float(stressed_prefit["equity_multiple"]),
            ]
            profitable = sum(value > 1.0 for value in equities)
            worst_mdd = min(
                *[float(item["max_drawdown_pct"]) for item in metrics],
                float(delayed_prefit["max_drawdown_pct"]),
                float(stressed_prefit["max_drawdown_pct"]),
            )
            score = (
                min(math.log(max(value, 1e-12)) for value in robust_equities)
                + 0.5
                * float(
                    np.median(np.log(np.maximum(robust_equities, 1e-12)))
                )
                + 0.25 * math.log(max(equities[0], 1e-12))
                - 1.5 * max(0.0, abs(worst_mdd) / 100.0 - 0.50)
                + 0.05 * profitable
            )
            rows.append(
                {
                    "long_config": long_config,
                    "short_config": short_config,
                    "robust_score": score,
                    "prefit_equity": equities[0],
                    "early_half_equity": equities[1],
                    "late_half_equity": equities[2],
                    "recent_prefit_90d_equity": equities[3],
                    "prefit_delayed_equity": delayed_prefit["equity_multiple"],
                    "prefit_stressed_equity": stressed_prefit["equity_multiple"],
                    "profitable_windows": profitable,
                    "worst_window_mdd_pct": worst_mdd,
                    "prefit_trades": metrics[0]["closed_trades"],
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["robust_score", "prefit_equity"],
        ascending=[False, False],
    )


def recent_slices(result: Result) -> list[dict[str, Any]]:
    path = pd.DataFrame(result.path)
    if path.empty:
        return []
    path["ts"] = pd.to_datetime(path["ts"], utc=True)
    end = path["ts"].max()
    rows: list[dict[str, Any]] = []
    for label, days in RECENT_WINDOWS.items():
        start = end - pd.Timedelta(days=days)
        part = path.loc[path["ts"].ge(start)].copy()
        if part.empty:
            continue
        initial = float(part.iloc[0]["pre_action_equity"])
        final = float(part.iloc[-1]["close_equity"])
        peak = initial
        drawdown = 0.0
        for row in part.itertuples(index=False):
            peak = max(
                peak,
                float(row.pre_action_equity),
                float(row.post_action_equity),
                float(row.favorable_equity),
            )
            drawdown = min(
                drawdown,
                float(row.post_action_equity) / peak - 1.0,
                float(row.adverse_equity) / peak - 1.0,
                float(row.close_equity) / peak - 1.0,
            )
            peak = max(peak, float(row.close_equity))
        rows.append(
            {
                "window": label,
                "start_ts": part.iloc[0]["ts"].isoformat(),
                "end_ts": part.iloc[-1]["ts"].isoformat(),
                "return_pct": (final / initial - 1.0) * 100.0,
                "path_mdd_pct": drawdown * 100.0,
            }
        )
    return rows


def clean_audit(audit: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in audit.items() if key != "retained"}


def _config_json(value: Config) -> str:
    return json.dumps(asdict(value), sort_keys=True, ensure_ascii=False)


def config_neighborhood(config: Config) -> list[tuple[str, Config]]:
    variants = [
        (
            "entry_buffer_down",
            replace(
                config,
                entry_buffer_atr=max(0.0, config.entry_buffer_atr - 0.10),
            ),
        ),
        (
            "entry_buffer_up",
            replace(config, entry_buffer_atr=config.entry_buffer_atr + 0.10),
        ),
        (
            "slope_min_down",
            replace(config, slope_min_atr=max(0.0, config.slope_min_atr - 0.02)),
        ),
        (
            "slope_min_up",
            replace(config, slope_min_atr=config.slope_min_atr + 0.02),
        ),
        (
            "exit_buffer_down",
            replace(
                config,
                exit_buffer_atr=max(0.0, config.exit_buffer_atr - 0.10),
            ),
        ),
        (
            "exit_buffer_up",
            replace(config, exit_buffer_atr=config.exit_buffer_atr + 0.10),
        ),
        (
            "hard_stop_down",
            replace(config, hard_stop_atr=max(0.0, config.hard_stop_atr - 1.0)),
        ),
        (
            "hard_stop_up",
            replace(config, hard_stop_atr=config.hard_stop_atr + 1.0),
        ),
        (
            "max_hold_down",
            replace(config, max_hold_days=max(0, config.max_hold_days - 5)),
        ),
        (
            "max_hold_up",
            replace(config, max_hold_days=config.max_hold_days + 5),
        ),
    ]
    output: list[tuple[str, Config]] = []
    seen = {config.key}
    for label, variant in variants:
        if variant.key not in seen:
            seen.add(variant.key)
            output.append((label, variant))
    return output


def neighborhood_rows(
    long_config: Config | None,
    short_config: Config | None,
    book: Any,
    features: Features,
    *,
    prefit_end: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    variants: list[tuple[str, Config | None, Config | None]] = [
        ("base", long_config, short_config)
    ]
    if long_config is not None:
        variants.extend(
            (f"long_{label}", variant, short_config)
            for label, variant in config_neighborhood(long_config)
        )
    if short_config is not None:
        variants.extend(
            (f"short_{label}", long_config, variant)
            for label, variant in config_neighborhood(short_config)
        )
    for label, long_variant, short_variant in variants:
        for window, start, end in (
            ("prefit", 0, prefit_end),
            ("last_90d_flat", prefit_end, book.count),
            ("full", 0, book.count),
        ):
            metrics = backtest(
                book,
                features,
                long_config=long_variant,
                short_config=short_variant,
                start_index=start,
                terminal_index=end,
            ).metrics
            rows.append(
                {
                    "variant": label,
                    "window": window,
                    **metrics,
                }
            )
    return rows


def phase_rows(
    long_config: Config | None,
    short_config: Config | None,
    books: dict[int, Any],
    features_by_phase: dict[int, Features],
) -> list[dict[str, Any]]:
    common_start = max(book.ts[0] for book in books.values())
    common_end = min(book.terminal_ts for book in books.values())
    rows: list[dict[str, Any]] = []
    for phase, book in sorted(books.items()):
        features = features_by_phase[phase]
        start = int(book.ts.searchsorted(common_start, side="left"))
        timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
        end = int(timestamps.searchsorted(common_end, side="right") - 1)
        metrics = backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
        ).metrics
        rows.append(
            {
                "phase_hours": phase,
                "common_overlap_start": common_start.isoformat(),
                "common_overlap_end": common_end.isoformat(),
                **metrics,
            }
        )
    return rows


def component_rows(
    long_config: Config | None,
    short_config: Config | None,
    book: Any,
    features: Features,
    *,
    prefit_end: int,
) -> list[dict[str, Any]]:
    variants = [
        ("combined", long_config, short_config),
        ("long_only", long_config, None),
        ("short_only", None, short_config),
    ]
    rows: list[dict[str, Any]] = []
    for label, long_variant, short_variant in variants:
        if long_variant is None and short_variant is None:
            continue
        for window, start, end in (
            ("prefit", 0, prefit_end),
            ("last_90d_flat", prefit_end, book.count),
            ("full", 0, book.count),
        ):
            metrics = backtest(
                book,
                features,
                long_config=long_variant,
                short_config=short_variant,
                start_index=start,
                terminal_index=end,
            ).metrics
            rows.append(
                {
                    "variant": label,
                    "window": window,
                    **metrics,
                }
            )
    return rows


def rolling_rows(
    long_config: Config | None,
    short_config: Config | None,
    book: Any,
    features: Features,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    while start + 90 <= book.count:
        end = start + 90
        metrics = backtest(
            book,
            features,
            long_config=long_config,
            short_config=short_config,
            start_index=start,
            terminal_index=end,
        ).metrics
        rows.append(
            {
                "window_index": len(rows),
                **metrics,
            }
        )
        start += 30
    return rows


def write_outputs(
    *,
    run_date: str,
    seed: int,
    samples_per_side: int,
    books: dict[int, Any],
    features_by_phase: dict[int, Features],
    prefit_end: int,
    long_stage1: pd.DataFrame,
    short_stage1: pd.DataFrame,
    long_stable: pd.DataFrame,
    short_stable: pd.DataFrame,
    pairs: pd.DataFrame,
    audits: list[dict[str, Any]],
    benchmark: dict[str, Any],
    bootstrap: dict[str, Any],
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    book = books[0]
    features = features_by_phase[0]
    primary = audits[0]
    primary_full = primary["retained"]["full"]
    primary_recent = recent_slices(primary_full)
    primary_long = (
        Config(**primary["long_config"])
        if primary["long_config"] is not None
        else None
    )
    primary_short = (
        Config(**primary["short_config"])
        if primary["short_config"] is not None
        else None
    )
    local_neighborhood = neighborhood_rows(
        primary_long,
        primary_short,
        book,
        features,
        prefit_end=prefit_end,
    )
    phases = phase_rows(
        primary_long,
        primary_short,
        books,
        features_by_phase,
    )
    components = component_rows(
        primary_long,
        primary_short,
        book,
        features,
        prefit_end=prefit_end,
    )
    rolling = rolling_rows(primary_long, primary_short, book, features)
    frontier_rows: list[dict[str, Any]] = []
    for side_name, frame in (("long", long_stable), ("short", short_stable)):
        export = frame.head(120).copy()
        export.insert(0, "side_name", side_name)
        export["config"] = export["config"].map(_config_json)
        frontier_rows.extend(export.to_dict(orient="records"))
    frontier = pd.DataFrame(frontier_rows)
    pair_export = pairs.head(120).copy()
    pair_export["long_config"] = pair_export["long_config"].map(_config_json)
    pair_export["short_config"] = pair_export["short_config"].map(_config_json)

    frontier.to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_frontier_{run_date}.csv",
        index=False,
    )
    pair_export.to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_pairs_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(primary_full.trades).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_primary_trades_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(primary_full.path).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_primary_path_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(primary_recent).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_primary_recent_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(local_neighborhood).to_csv(
        ARTIFACT_DIR
        / f"hype_1d_ma7_separated_primary_neighborhood_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(phases).to_csv(
        ARTIFACT_DIR / f"hype_1d_ma7_separated_primary_phase_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(components).to_csv(
        ARTIFACT_DIR
        / f"hype_1d_ma7_separated_primary_components_{run_date}.csv",
        index=False,
    )
    pd.DataFrame(rolling).to_csv(
        ARTIFACT_DIR
        / f"hype_1d_ma7_separated_primary_rolling_90d_{run_date}.csv",
        index=False,
    )

    audit_payload = [clean_audit(item) for item in audits]
    profitable = [
        item
        for item in audit_payload
        if all(item["historical_profit_check"].values())
    ]
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY,
        "branch": BRANCH,
        "status": "explore / not promoted / not live-ready",
        "run_date": run_date,
        "contract": {
            "fixed_ma": "SMA7",
            "long_short_parameters_searched_separately": True,
            "stage1_samples_per_side": samples_per_side,
            "seed": seed,
            "prefit_end_exclusive": HOLDOUT_START.isoformat(),
            "last_90d_role": "researcher_exposed_flat_start_validation",
            "fee_per_fill": FEE,
            "base_slippage_per_fill": BASE_SLIPPAGE,
            "stress_slippage_per_fill": STRESS_SLIPPAGE,
            "funding": (
                "actual Binance event timestamps and rates; event-hour open "
                "notional approximation, settled only while position is held"
            ),
            "short_open_entry": (
                "observe daily open, execute at next 1h open"
            ),
        },
        "data_quality": book.quality,
        "funding_quality": book.funding_quality,
        "search_counts": {
            "long_stage1": int(len(long_stage1)),
            "short_stage1": int(len(short_stage1)),
            "long_stability_audited": int(len(long_stable)),
            "short_stability_audited": int(len(short_stable)),
            "pairs_audited": int(len(pairs)),
        },
        "audited_candidates": audit_payload,
        "historically_profitable_all_checks": profitable,
        "buy_and_hold": benchmark,
        "primary_recent_slices": primary_recent,
        "primary_neighborhood": local_neighborhood,
        "primary_phase_audit": phases,
        "primary_components": components,
        "primary_rolling_90d": rolling,
        "primary_trade_bootstrap": bootstrap,
        "warning": (
            "all history is researcher-exposed; profitable historical rows "
            "are observations, not clean OOS or promotion evidence"
        ),
    }
    summary_path = (
        ARTIFACT_DIR / f"hype_1d_ma7_separated_summary_{run_date}.json"
    )
    clean_payload = _clean_json(payload)
    summary_path.write_text(
        json.dumps(
            clean_payload,
            ensure_ascii=False,
            indent=2,
            default=_json_default,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            _clean_json({
                "summary": str(summary_path.relative_to(ROOT)),
                "search_counts": payload["search_counts"],
                "audited_candidates": audit_payload,
                "historically_profitable_all_checks": len(profitable),
                "primary_recent_slices": primary_recent,
            }),
            ensure_ascii=False,
            indent=2,
            default=_json_default,
            allow_nan=False,
        ),
        flush=True,
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json(item) for item in value]
    if isinstance(value, np.generic):
        return _clean_json(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def self_test() -> None:
    rng = random.Random(7)
    long_config = random_config(1, rng)
    short_config = random_config(-1, rng)
    assert long_config.side == 1 and short_config.side == -1
    assert long_config.entry_mode != "open_regime"
    quantity, post, turnover = _target_quantity(
        1.0,
        0.0,
        1,
        10.0,
        FEE + BASE_SLIPPAGE,
    )
    assert post < 1.0 and turnover > 0.0
    assert math.isclose(
        quantity * 10.0 / post,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    )
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    base = load_base()
    books = base.load_books()
    book = books[0]
    parent = base.load_parent()
    engine = parent.load_engine()
    hourly, _ = engine.audit_and_load_market(ROOT, "1h")
    funding, _ = engine.load_and_audit_funding(ROOT)
    features_by_phase = {
        phase: build_features(phase_book, hourly, funding)
        for phase, phase_book in books.items()
    }
    features = features_by_phase[0]
    prefit_end = int(book.ts.searchsorted(HOLDOUT_START, side="left"))
    if prefit_end <= 180 or pd.Timestamp(book.ts[prefit_end]) != HOLDOUT_START:
        raise RuntimeError("prefit/holdout boundary unavailable")
    rng = random.Random(args.seed)
    long_configs = unique_configs(1, rng, args.samples_per_side)
    short_configs = unique_configs(-1, rng, args.samples_per_side)
    long_stage1 = stage1_search(
        long_configs,
        book,
        features,
        end=prefit_end,
    )
    short_stage1 = stage1_search(
        short_configs,
        book,
        features,
        end=prefit_end,
    )
    long_shortlist = list(
        long_stage1.sort_values("score", ascending=False)
        .head(args.shortlist)["config"]
    )
    short_shortlist = list(
        short_stage1.sort_values("score", ascending=False)
        .head(args.shortlist)["config"]
    )
    long_stable = rank_stable(
        stability_audit(
            long_shortlist,
            book,
            features,
            prefit_end=prefit_end,
        ),
        args.shortlist,
    )
    short_stable = rank_stable(
        stability_audit(
            short_shortlist,
            book,
            features,
            prefit_end=prefit_end,
        ),
        args.shortlist,
    )
    long_pool = list(long_stable.head(args.pair_pool)["config"])
    short_pool = list(short_stable.head(args.pair_pool)["config"])
    pairs = pair_search(
        long_pool,
        short_pool,
        book,
        features,
        prefit_end=prefit_end,
    )
    primary_pair = pairs.iloc[0]
    primary_long = long_stable.iloc[0]["config"]
    primary_short = short_stable.iloc[0]["config"]
    prefit_audits = [
        audit_candidate(
            "prefit_selected_combined_primary",
            primary_pair["long_config"],
            primary_pair["short_config"],
            book,
            features,
            prefit_end=prefit_end,
            retain_full=False,
        ),
        audit_candidate(
            "prefit_selected_long_only",
            primary_long,
            None,
            book,
            features,
            prefit_end=prefit_end,
            retain_full=False,
        ),
        audit_candidate(
            "prefit_selected_short_only",
            None,
            primary_short,
            book,
            features,
            prefit_end=prefit_end,
            retain_full=False,
        ),
    ]
    historical_candidates: list[
        tuple[str, Config | None, Config | None]
    ] = []
    historical_candidates.extend(
        (f"post_reveal_long_observation_{index:03d}", config, None)
        for index, config in enumerate(long_stable.head(args.shortlist)["config"])
    )
    historical_candidates.extend(
        (f"post_reveal_short_observation_{index:03d}", None, config)
        for index, config in enumerate(short_stable.head(args.shortlist)["config"])
    )
    historical_candidates.extend(
        (
            f"post_reveal_combined_observation_{index:03d}",
            row["long_config"],
            row["short_config"],
        )
        for index, (_, row) in enumerate(pairs.head(args.shortlist).iterrows())
    )
    historical = find_historical_observation(
        historical_candidates,
        book,
        features,
        prefit_end=prefit_end,
    )
    audits = (
        [historical, *prefit_audits]
        if historical is not None
        else [
            audit_candidate(
                "prefit_selected_combined_primary",
                primary_pair["long_config"],
                primary_pair["short_config"],
                book,
                features,
                prefit_end=prefit_end,
                retain_full=True,
            ),
            *prefit_audits[1:],
        ]
    )
    benchmark = buy_and_hold(book, features)
    bootstrap = base.bootstrap_trades(
        audits[0]["retained"]["full"].trades,
        samples=5_000,
        seed=args.seed + 99,
    )
    bootstrap["drawdown_scope"] = "closed_trade_boundaries_only"
    bootstrap["closed_trade_boundary_drawdown_pct_p05"] = bootstrap.pop(
        "max_drawdown_pct_p05"
    )
    bootstrap["closed_trade_boundary_drawdown_pct_median"] = bootstrap.pop(
        "max_drawdown_pct_median"
    )
    write_outputs(
        run_date=args.run_date,
        seed=args.seed,
        samples_per_side=args.samples_per_side,
        books=books,
        features_by_phase=features_by_phase,
        prefit_end=prefit_end,
        long_stage1=long_stage1,
        short_stage1=short_stage1,
        long_stable=long_stable,
        short_stable=short_stable,
        pairs=pairs,
        audits=audits,
        benchmark=benchmark,
        bootstrap=bootstrap,
    )


if __name__ == "__main__":
    main()
