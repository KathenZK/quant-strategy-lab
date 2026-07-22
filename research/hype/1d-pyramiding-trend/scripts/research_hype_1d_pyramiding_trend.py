from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
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
ENGINE_PATH = ROOT / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
ENGINE_SHA256 = "63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4"

FAMILY_NAME = "HYPE-1D-Pyramiding-Trend"
FAMILY_ALIAS = "HYPE-1D-PT"
SYMBOL = "HYPEUSDT"
TIMEFRAME = "1d"
BASE_FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
MAX_LEVERAGE = 3.0
OOS_DAYS = 90
EMBARGO_DAYS = 1
TARGET_ANNUAL_FACTOR = 20.0
TARGET_WIN_RATE = 0.80
TARGET_MAX_DRAWDOWN = 0.20
MIN_PREFIT_TRADES = 8
MIN_OOS_TRADES = 3
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=180),
    "1y": pd.Timedelta(days=365),
}

MECHANISM_NAMES = {
    0: "donchian_breakout",
    1: "keltner_breakout",
    2: "timeseries_momentum",
    3: "ema_cross",
}
DIRECTION_NAMES = {0: "both", 1: "long_only", 2: "short_only"}


@dataclass(frozen=True, slots=True)
class Config:
    mechanism: int
    direction: int
    entry_window: int
    exit_window: int
    ema_fast: int
    ema_slow: int
    atr_window: int
    adx_window: int
    adx_min: float
    entry_buffer_atr: float
    momentum_atr: float
    trail_atr: float
    breakeven_trigger_atr: float
    breakeven_lock_atr: float
    add_step_atr: float
    max_hold_days: int
    cooldown_days: int
    slope_window: int
    atr_pct_cap: float
    ema_filter: bool
    ema_exit: bool

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


@dataclass(slots=True)
class FeatureBook:
    ts: pd.DatetimeIndex
    terminal_ts: pd.Timestamp
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    atr: dict[int, np.ndarray]
    adx: dict[int, np.ndarray]
    ema: dict[int, np.ndarray]
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    momentum: dict[int, np.ndarray]
    funding_by_open: np.ndarray
    quality: dict[str, Any]
    funding_quality: dict[str, Any]

    @property
    def daily_count(self) -> int:
        return len(self.open)


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    path: list[dict[str, Any]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Search {FAMILY_NAME}.")
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--stage1", type=int, default=250_000)
    parser.add_argument("--stage2", type=int, default=150_000)
    parser.add_argument("--shortlist", type=int, default=120)
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--run-date", default=datetime.now(UTC).date().isoformat())
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def load_engine() -> object:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(f"shared kernel SHA mismatch: expected {ENGINE_SHA256}, got {digest}")
    spec = importlib.util.spec_from_file_location("hype_1d_pt_market_audit", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def aggregate_complete_daily(hourly: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    required = {
        "ts", "open", "high", "low", "close", "volume", "quote_volume",
        "trade_count", "vwap", "is_closed", "source",
    }
    missing_columns = sorted(required.difference(hourly.columns))
    if missing_columns:
        raise RuntimeError(f"hourly data missing required columns: {missing_columns}")
    source = hourly.copy()
    source["ts"] = pd.to_datetime(source["ts"], utc=True)
    if source["ts"].duplicated().any():
        raise RuntimeError("hourly input contains duplicate timestamps")
    if source[list(required)].isna().any(axis=None):
        raise RuntimeError("hourly input contains critical nulls")
    if not bool(source["is_closed"].astype(bool).all()):
        raise RuntimeError("hourly input contains an unclosed bar")
    source = source.sort_values("ts").reset_index(drop=True)
    source["utc_day"] = source["ts"].dt.floor("1D")
    complete_days: list[pd.Timestamp] = []
    for utc_day, group in source.groupby("utc_day", sort=True):
        expected = pd.date_range(utc_day, periods=24, freq="1h")
        if len(group) == 24 and pd.DatetimeIndex(group["ts"]).equals(expected):
            complete_days.append(pd.Timestamp(utc_day))
    total_bins = int(source["utc_day"].nunique())
    complete = source.loc[source["utc_day"].isin(complete_days)].set_index("ts")
    if complete.empty:
        raise RuntimeError("no complete UTC daily bars")
    daily = complete.resample("1D", label="left", closed="left").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"),
        close=("close", "last"), volume=("volume", "sum"),
        quote_volume=("quote_volume", "sum"), trade_count=("trade_count", "sum"),
        source_hours=("open", "count"),
    ).dropna(subset=["open", "high", "low", "close"])
    daily["vwap"] = daily["quote_volume"] / daily["volume"].replace(0.0, np.nan)
    daily["ts"] = daily.index
    daily = daily.reset_index(drop=True)
    expected_daily = pd.date_range(daily["ts"].iloc[0], daily["ts"].iloc[-1], freq="1D")
    missing_daily = expected_daily.difference(pd.DatetimeIndex(daily["ts"]))
    invalid_ohlc = int((
        (daily[["open", "high", "low", "close"]] <= 0.0).any(axis=1)
        | daily["high"].lt(daily[["open", "close", "low"]].max(axis=1))
        | daily["low"].gt(daily[["open", "close", "high"]].min(axis=1))
    ).sum())
    quality = {
        "source_timeframe": "1h",
        "aggregation": "UTC 1D; retain exactly 24 explicit closed hourly bars",
        "rows": int(len(daily)),
        "first_ts": pd.Timestamp(daily["ts"].iloc[0]).isoformat(),
        "last_ts": pd.Timestamp(daily["ts"].iloc[-1]).isoformat(),
        "expected_rows": int(len(expected_daily)),
        "missing_daily_bars": int(len(missing_daily)),
        "duplicate_ts": int(daily["ts"].duplicated().sum()),
        "critical_null_rows": int(daily.isna().any(axis=1).sum()),
        "invalid_ohlc_rows": invalid_ohlc,
        "dropped_incomplete_daily_bins": total_bins - int(len(daily)),
    }
    quality["blocker_count"] = int(
        quality["missing_daily_bars"] + quality["duplicate_ts"]
        + quality["critical_null_rows"] + quality["invalid_ohlc_rows"]
    )
    if quality["blocker_count"]:
        raise RuntimeError(f"daily aggregation quality blockers: {quality}")
    return daily, quality


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    return pd.Series(values).ewm(span=span, adjust=False, min_periods=span).mean().to_numpy("float64")


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    prior_close = np.r_[np.nan, close[:-1]]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prior_close), np.abs(low - prior_close)))
    return pd.Series(tr).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().to_numpy("float64")


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    up = np.r_[np.nan, np.diff(high)]
    down = np.r_[np.nan, -np.diff(low)]
    plus_dm = np.where((up > down) & (up > 0.0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0.0), down, 0.0)
    atr = _atr(high, low, close, window)
    plus = 100.0 * pd.Series(plus_dm).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().to_numpy() / atr
    minus = 100.0 * pd.Series(minus_dm).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().to_numpy() / atr
    dx = 100.0 * np.abs(plus - minus) / np.where(plus + minus == 0.0, np.nan, plus + minus)
    return pd.Series(dx).ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean().to_numpy("float64")


def _prior_roll(values: np.ndarray, window: int, kind: str) -> np.ndarray:
    shifted = pd.Series(values).shift(1)
    rolling = shifted.rolling(window, min_periods=window)
    return (rolling.max() if kind == "max" else rolling.min()).to_numpy("float64")


def _funding_by_open(opens: pd.DatetimeIndex, funding: pd.DataFrame) -> np.ndarray:
    open_ns = pd.DatetimeIndex(opens).as_unit("ns").asi8
    funding_ns = pd.DatetimeIndex(pd.to_datetime(funding["ts"], utc=True)).as_unit("ns").asi8
    rates = funding["funding_rate"].to_numpy("float64")
    output = np.zeros(len(opens), dtype="float64")
    for index in range(1, len(opens)):
        left = np.searchsorted(funding_ns, open_ns[index - 1], side="right")
        right = np.searchsorted(funding_ns, open_ns[index], side="right")
        if right > left:
            output[index] = float(rates[left:right].sum())
    return output


def build_feature_book() -> FeatureBook:
    engine = load_engine()
    hourly, hourly_quality = engine.audit_and_load_market(ROOT, "1h")
    funding, funding_quality = engine.load_and_audit_funding(ROOT)
    daily, daily_quality = aggregate_complete_daily(hourly)
    last_day = pd.Timestamp(daily["ts"].iloc[-1])
    terminal_ts = last_day + pd.Timedelta(days=1)
    terminal_rows = hourly.loc[pd.to_datetime(hourly["ts"], utc=True).eq(terminal_ts)]
    if len(terminal_rows) != 1:
        raise RuntimeError(f"expected one terminal daily open at {terminal_ts}, got {len(terminal_rows)}")
    open_values = daily["open"].to_numpy("float64")
    high = daily["high"].to_numpy("float64")
    low = daily["low"].to_numpy("float64")
    close = daily["close"].to_numpy("float64")
    atr_windows = (5, 7, 10, 14, 20, 30)
    adx_windows = (5, 7, 10, 14, 20, 30)
    ema_spans = (3, 5, 8, 10, 13, 15, 20, 30, 40, 55, 80, 120, 160)
    roll_windows = (2, 3, 4, 5, 7, 10, 14, 20, 30, 40, 55, 80)
    open_index = pd.DatetimeIndex([*pd.to_datetime(daily["ts"], utc=True), terminal_ts])
    quality = {
        "hourly": hourly_quality,
        "daily": daily_quality,
        "terminal_open_ts": terminal_ts.isoformat(),
        "terminal_open": float(terminal_rows["open"].iloc[0]),
    }
    return FeatureBook(
        ts=pd.DatetimeIndex(pd.to_datetime(daily["ts"], utc=True)),
        terminal_ts=terminal_ts,
        open=open_values,
        high=high,
        low=low,
        close=close,
        atr={window: _atr(high, low, close, window) for window in atr_windows},
        adx={window: _adx(high, low, close, window) for window in adx_windows},
        ema={span: _ema(close, span) for span in ema_spans},
        prior_high={window: _prior_roll(high, window, "max") for window in roll_windows},
        prior_low={window: _prior_roll(low, window, "min") for window in roll_windows},
        momentum={
            window: np.r_[np.full(window, np.nan), close[window:] / close[:-window] - 1.0]
            for window in roll_windows
        },
        funding_by_open=_funding_by_open(open_index, funding),
        quality=quality,
        funding_quality=funding_quality,
    )


def _entry_side(config: Config, book: FeatureBook, index: int) -> int:
    if index < 1:
        return 0
    close = book.close[index]
    atr = book.atr[config.atr_window][index]
    fast = book.ema[config.ema_fast][index]
    slow = book.ema[config.ema_slow][index]
    adx = book.adx[config.adx_window][index]
    if not all(np.isfinite(value) for value in (close, atr, fast, slow, adx)) or atr <= 0.0:
        return 0
    atr_pct = atr / close
    if config.adx_min > 0.0 and adx < config.adx_min:
        return 0
    if config.atr_pct_cap > 0.0 and atr_pct > config.atr_pct_cap:
        return 0
    slope_long = slope_short = True
    if config.slope_window > 0:
        prior_index = index - config.slope_window
        if prior_index < 0 or not np.isfinite(book.ema[config.ema_slow][prior_index]):
            return 0
        slope_long = slow > book.ema[config.ema_slow][prior_index]
        slope_short = slow < book.ema[config.ema_slow][prior_index]
    long_signal = short_signal = False
    if config.mechanism == 0:
        upper = book.prior_high[config.entry_window][index]
        lower = book.prior_low[config.entry_window][index]
        if not np.isfinite(upper) or not np.isfinite(lower):
            return 0
        long_signal = close > upper + config.entry_buffer_atr * atr
        short_signal = close < lower - config.entry_buffer_atr * atr
    elif config.mechanism == 1:
        long_signal = close > slow + config.entry_buffer_atr * atr
        short_signal = close < slow - config.entry_buffer_atr * atr
    elif config.mechanism == 2:
        momentum = book.momentum[config.entry_window][index]
        if not np.isfinite(momentum):
            return 0
        threshold = config.momentum_atr * atr_pct
        long_signal = momentum > threshold
        short_signal = momentum < -threshold
    else:
        prior_fast = book.ema[config.ema_fast][index - 1]
        prior_slow = book.ema[config.ema_slow][index - 1]
        if not np.isfinite(prior_fast) or not np.isfinite(prior_slow):
            return 0
        long_signal = fast > slow and prior_fast <= prior_slow
        short_signal = fast < slow and prior_fast >= prior_slow
    if config.ema_filter or config.mechanism in {1, 3}:
        long_signal = long_signal and fast > slow and close > slow
        short_signal = short_signal and fast < slow and close < slow
    long_signal = long_signal and slope_long and config.direction != 2
    short_signal = short_signal and slope_short and config.direction != 1
    if long_signal == short_signal:
        return 0
    return 1 if long_signal else -1


def _signal_exit(
    config: Config,
    book: FeatureBook,
    index: int,
    side: int,
    entry_price: float,
    entry_atr: float,
    peak_close: float,
    trough_close: float,
    bars_held: int,
) -> tuple[bool, str]:
    close = book.close[index]
    atr = book.atr[config.atr_window][index]
    if not np.isfinite(atr):
        return True, "indicator_unavailable"
    if side > 0:
        channel = book.prior_low[config.exit_window][index]
        if np.isfinite(channel) and close < channel:
            return True, "donchian_exit"
        if config.trail_atr > 0.0 and close < peak_close - config.trail_atr * atr:
            return True, "atr_trail"
        if config.breakeven_trigger_atr > 0.0 and peak_close >= entry_price + config.breakeven_trigger_atr * entry_atr:
            if close < entry_price + config.breakeven_lock_atr * entry_atr:
                return True, "profit_lock"
        if config.ema_exit and close < book.ema[config.ema_fast][index]:
            return True, "ema_exit"
    else:
        channel = book.prior_high[config.exit_window][index]
        if np.isfinite(channel) and close > channel:
            return True, "donchian_exit"
        if config.trail_atr > 0.0 and close > trough_close + config.trail_atr * atr:
            return True, "atr_trail"
        if config.breakeven_trigger_atr > 0.0 and trough_close <= entry_price - config.breakeven_trigger_atr * entry_atr:
            if close > entry_price - config.breakeven_lock_atr * entry_atr:
                return True, "profit_lock"
        if config.ema_exit and close > book.ema[config.ema_fast][index]:
            return True, "ema_exit"
    if config.max_hold_days > 0 and bars_held >= config.max_hold_days:
        return True, "max_hold"
    return False, ""


def _annual_factor(equity: float, days: float) -> float:
    if equity <= 0.0 or days <= 0.0:
        return 0.0
    exponent = min(20.0, 365.25 / days)
    return float(equity**exponent)


def backtest(
    config: Config,
    book: FeatureBook,
    *,
    start_open_index: int,
    terminal_open_index: int,
    slippage: float = BASE_SLIPPAGE,
    signal_delay_days: int = 1,
    retain_path: bool = False,
) -> BacktestResult:
    n = book.daily_count
    if not (0 <= start_open_index < terminal_open_index <= n):
        raise ValueError("invalid backtest boundary")
    if signal_delay_days not in {1, 2}:
        raise ValueError("signal_delay_days must be 1 or 2")
    terminal_open = float(book.quality["terminal_open"])
    opens = np.r_[book.open, terminal_open]
    timestamps = pd.DatetimeIndex([*book.ts, book.terminal_ts])
    cost_rate = BASE_FEE + slippage
    equity = 1.0
    peak_equity = 1.0
    max_drawdown = 0.0
    position = 0.0
    side = 0
    layers = 0
    entry_price = math.nan
    average_entry = math.nan
    last_add_price = math.nan
    entry_atr = math.nan
    entry_ts: pd.Timestamp | None = None
    entry_equity = math.nan
    peak_close = -math.inf
    trough_close = math.inf
    bars_held = 0
    cooldown_left = 0
    total_turnover = 0.0
    total_cost = 0.0
    total_funding = 0.0
    add_count = 0
    pending: dict[int, tuple[float, str]] = {}
    trades: list[dict[str, Any]] = []
    path: list[dict[str, Any]] = []

    first_signal_index = start_open_index - signal_delay_days
    if first_signal_index >= 0:
        initial_side = _entry_side(config, book, first_signal_index)
        if initial_side:
            pending[start_open_index] = (float(initial_side), "entry")

    previous_open = opens[start_open_index]
    for open_index in range(start_open_index, terminal_open_index + 1):
        current_open = float(opens[open_index])
        ts = pd.Timestamp(timestamps[open_index])
        if open_index > start_open_index:
            market_return = current_open / previous_open - 1.0
            equity *= 1.0 + position * market_return
            funding_amount = equity * position * book.funding_by_open[open_index]
            equity -= funding_amount
            total_funding += funding_amount
            if equity <= 0.0:
                max_drawdown = -1.0
                equity = 0.0
                break
        action = pending.pop(open_index, None)
        action_name = "hold"
        if action is not None:
            target, action_name = action
            old_position = position
            turnover = abs(target - old_position)
            equity_before_cost = equity
            cost_amount = equity * turnover * cost_rate
            equity -= cost_amount
            total_cost += cost_amount
            total_turnover += turnover
            position = target
            if action_name == "entry":
                side = 1 if target > 0 else -1
                layers = 1
                entry_price = current_open
                average_entry = current_open
                last_add_price = current_open
                entry_atr = float(book.atr[config.atr_window][max(0, open_index - signal_delay_days)])
                entry_ts = ts
                entry_equity = equity_before_cost
                peak_close = -math.inf
                trough_close = math.inf
                bars_held = 0
            elif action_name == "add":
                new_layers = int(abs(target))
                average_entry = (average_entry * layers + current_open * (new_layers - layers)) / new_layers
                layers = new_layers
                last_add_price = current_open
                add_count += 1
            elif action_name.startswith("exit"):
                if entry_ts is not None:
                    trades.append({
                        "entry_ts": entry_ts.isoformat(),
                        "exit_ts": ts.isoformat(),
                        "side": "long" if side > 0 else "short",
                        "entry_price": entry_price,
                        "exit_price": current_open,
                        "max_layers": layers,
                        "bars_held": bars_held,
                        "exit_reason": action_name.removeprefix("exit:"),
                        "net_return": equity / entry_equity - 1.0,
                    })
                side = 0
                layers = 0
                position = 0.0
                entry_price = average_entry = last_add_price = entry_atr = math.nan
                entry_ts = None
                entry_equity = math.nan
                peak_close = -math.inf
                trough_close = math.inf
                bars_held = 0
                cooldown_left = config.cooldown_days
        peak_equity = max(peak_equity, equity)
        max_drawdown = min(max_drawdown, equity / peak_equity - 1.0)

        if open_index < n and position != 0.0:
            leverage = abs(position)
            if position > 0.0:
                favorable = book.high[open_index] / current_open - 1.0
                adverse = book.low[open_index] / current_open - 1.0
            else:
                favorable = 1.0 - book.low[open_index] / current_open
                adverse = 1.0 - book.high[open_index] / current_open
            favorable_equity = equity * (1.0 + leverage * favorable)
            adverse_equity = equity * (1.0 + leverage * adverse)
            peak_equity = max(peak_equity, favorable_equity)
            max_drawdown = min(max_drawdown, adverse_equity / peak_equity - 1.0)

        if retain_path:
            path.append({
                "ts": ts.isoformat(), "equity": equity, "position": position,
                "action": action_name, "peak_equity_conservative": peak_equity,
                "max_drawdown_conservative": max_drawdown,
            })

        if open_index >= n:
            previous_open = current_open
            continue
        close = float(book.close[open_index])
        if position != 0.0:
            bars_held += 1
            peak_close = max(peak_close, close)
            trough_close = min(trough_close, close)
            if pending:
                previous_open = current_open
                continue
            should_exit, exit_reason = _signal_exit(
                config, book, open_index, side, entry_price, entry_atr,
                peak_close, trough_close, bars_held,
            )
            target_open_index = open_index + signal_delay_days
            if should_exit and target_open_index <= terminal_open_index:
                pending[target_open_index] = (0.0, f"exit:{exit_reason}")
            elif layers < int(MAX_LEVERAGE) and target_open_index <= terminal_open_index:
                atr = book.atr[config.atr_window][open_index]
                floating_profitable = side * (close / average_entry - 1.0) > 0.0
                threshold_hit = (
                    close >= last_add_price + config.add_step_atr * atr
                    if side > 0
                    else close <= last_add_price - config.add_step_atr * atr
                )
                if floating_profitable and np.isfinite(atr) and threshold_hit:
                    pending[target_open_index] = (float(side * (layers + 1)), "add")
        else:
            if cooldown_left > 0:
                cooldown_left -= 1
            else:
                target_open_index = open_index + signal_delay_days
                if target_open_index <= terminal_open_index and target_open_index not in pending:
                    new_side = _entry_side(config, book, open_index)
                    if new_side:
                        pending[target_open_index] = (float(new_side), "entry")
        previous_open = current_open

    days = max(1.0, (timestamps[terminal_open_index] - timestamps[start_open_index]).total_seconds() / 86400.0)
    returns = [float(row["net_return"]) for row in trades]
    wins = sum(value > 0.0 for value in returns)
    gross_profit = sum(value for value in returns if value > 0.0)
    gross_loss = -sum(value for value in returns if value < 0.0)
    metrics = {
        "start_ts": pd.Timestamp(timestamps[start_open_index]).isoformat(),
        "end_ts": pd.Timestamp(timestamps[terminal_open_index]).isoformat(),
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
        "max_leverage": MAX_LEVERAGE,
        "ending_position": position,
        "total_turnover": total_turnover,
        "cost_pct_initial": total_cost * 100.0,
        "funding_paid_pct_initial": total_funding * 100.0,
        "bankrupt": equity <= 0.0,
    }
    return BacktestResult(metrics=metrics, trades=trades, path=path)


def random_config(rng: random.Random) -> Config:
    mechanism = rng.choices((0, 1, 2, 3), weights=(4, 3, 3, 1), k=1)[0]
    fast = rng.choice((3, 5, 8, 10, 13, 15, 20, 30, 40))
    slow_choices = [value for value in (10, 15, 20, 30, 40, 55, 80, 120, 160) if value > fast]
    slow = rng.choice(slow_choices)
    entry_window = rng.choice((2, 3, 4, 5, 7, 10, 14, 20, 30, 40, 55, 80))
    exit_window = rng.choice((2, 3, 4, 5, 7, 10, 14, 20, 30, 40))
    return Config(
        mechanism=mechanism,
        direction=rng.choices((0, 1, 2), weights=(5, 4, 2), k=1)[0],
        entry_window=entry_window,
        exit_window=exit_window,
        ema_fast=fast,
        ema_slow=slow,
        atr_window=rng.choice((5, 7, 10, 14, 20, 30)),
        adx_window=rng.choice((5, 7, 10, 14, 20, 30)),
        adx_min=rng.choice((0.0, 0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0)),
        entry_buffer_atr=rng.choice((0.0, 0.0, 0.1, 0.25, 0.5, 0.75, 1.0, 1.5)),
        momentum_atr=rng.choice((0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0)),
        trail_atr=rng.choice((0.0, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0)),
        breakeven_trigger_atr=rng.choice((0.0, 0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0)),
        breakeven_lock_atr=rng.choice((0.0, 0.25, 0.5, 0.75, 1.0)),
        add_step_atr=rng.choice((0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)),
        max_hold_days=rng.choice((0, 0, 10, 15, 20, 30, 45, 60, 90, 120, 180)),
        cooldown_days=rng.choice((0, 0, 1, 2, 3, 5, 7, 10)),
        slope_window=rng.choice((0, 0, 3, 5, 10, 20)),
        atr_pct_cap=rng.choice((0.0, 0.0, 0.05, 0.08, 0.12, 0.16)),
        ema_filter=rng.choice((False, False, True)),
        ema_exit=rng.choice((False, False, True)),
    )


def mutate_config(parent: Config, rng: random.Random) -> Config:
    child = random_config(rng)
    parent_values = asdict(parent)
    child_values = asdict(child)
    for key in parent_values:
        if rng.random() < 0.72:
            child_values[key] = parent_values[key]
    if child_values["ema_slow"] <= child_values["ema_fast"]:
        child_values["ema_slow"] = next(
            value for value in (10, 15, 20, 30, 40, 55, 80, 120, 160)
            if value > child_values["ema_fast"]
        )
    return Config(**child_values)


def compact_row(config: Config, result: BacktestResult) -> dict[str, Any]:
    metrics = result.metrics
    win_rate = metrics["win_rate"]
    factor = metrics["annualized_factor"]
    drawdown = abs(min(0.0, metrics["max_drawdown_pct"] / 100.0))
    win_gap = max(0.0, TARGET_WIN_RATE - (win_rate if np.isfinite(win_rate) else 0.0))
    return {
        "config": config,
        "annualized_factor": factor,
        "equity_multiple": metrics["equity_multiple"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "win_rate": win_rate,
        "closed_trades": metrics["closed_trades"],
        "add_count": metrics["add_count"],
        "joint_gap": (
            max(0.0, math.log(TARGET_ANNUAL_FACTOR) - math.log(max(factor, 1e-12)))
            + 4.0 * win_gap
            + 4.0 * max(0.0, drawdown - TARGET_MAX_DRAWDOWN)
            + 0.1 * max(0, MIN_PREFIT_TRADES - metrics["closed_trades"])
            + (0.5 if metrics["add_count"] == 0 else 0.0)
        ),
    }


_WORKER_BOOK: FeatureBook | None = None


def _init_search_worker(book: FeatureBook) -> None:
    global _WORKER_BOOK
    _WORKER_BOOK = book


def _search_batch(
    configs: list[Config], prefit_start: int, prefit_terminal: int
) -> list[dict[str, Any]]:
    if _WORKER_BOOK is None:
        raise RuntimeError("search worker was not initialized")
    rows: list[dict[str, Any]] = []
    for config in configs:
        result = backtest(
            config, _WORKER_BOOK, start_open_index=prefit_start,
            terminal_open_index=prefit_terminal,
        )
        rows.append(compact_row(config, result))
    return rows


def search_stage(
    configs: Iterable[Config],
    book: FeatureBook,
    *,
    prefit_start: int,
    prefit_terminal: int,
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
    batches = [unique[index:index + batch_size] for index in range(0, len(unique), batch_size)]
    if workers <= 1:
        _init_search_worker(book)
        rows = [
            row
            for batch in batches
            for row in _search_batch(batch, prefit_start, prefit_terminal)
        ]
        return pd.DataFrame(rows)
    rows: list[dict[str, Any]] = []
    completed = 0
    next_progress = 25_000
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_search_worker,
        initargs=(book,),
    ) as executor:
        futures = {
            executor.submit(_search_batch, batch, prefit_start, prefit_terminal): len(batch)
            for batch in batches
        }
        for future in as_completed(futures):
            rows.extend(future.result())
            completed += futures[future]
            if completed >= next_progress or completed == len(unique):
                print(f"{label}: {completed}/{len(unique)}", flush=True)
                next_progress += 25_000
    return pd.DataFrame(rows)


def rank_prefit(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    valid = frame.loc[
        (frame["closed_trades"] >= MIN_PREFIT_TRADES)
        & (frame["add_count"] >= 1)
        & (frame["max_drawdown_pct"] >= -100.0)
    ].copy()
    if valid.empty:
        valid = frame.copy()
    roles: list[pd.DataFrame] = []
    roles.append(valid.sort_values(["joint_gap", "annualized_factor"], ascending=[True, False]).head(limit))
    dd_safe = valid.loc[valid["max_drawdown_pct"] >= -20.0]
    if not dd_safe.empty:
        roles.append(dd_safe.sort_values(["annualized_factor", "win_rate"], ascending=False).head(limit))
        roles.append(dd_safe.sort_values(["win_rate", "annualized_factor"], ascending=False).head(limit))
    roles.append(valid.sort_values(["max_drawdown_pct", "annualized_factor"], ascending=False).head(limit))
    ranked = pd.concat(roles, ignore_index=True)
    ranked["config_key"] = ranked["config"].map(lambda value: value.key)
    ranked = ranked.drop_duplicates("config_key").drop(columns="config_key")
    return ranked.sort_values(["joint_gap", "annualized_factor"], ascending=[True, False]).head(limit)


def boundaries(book: FeatureBook) -> dict[str, Any]:
    end = book.terminal_ts
    oos_start_ts = end - pd.Timedelta(days=OOS_DAYS)
    oos_start_index = int(book.ts.searchsorted(oos_start_ts, side="left"))
    prefit_terminal_ts = oos_start_ts - pd.Timedelta(days=EMBARGO_DAYS)
    prefit_terminal_index = int(book.ts.searchsorted(prefit_terminal_ts, side="left"))
    warmup_start = 0
    return {
        "dataset_start": book.ts[0],
        "dataset_end": end,
        "oos_start": oos_start_ts,
        "oos_start_index": oos_start_index,
        "prefit_terminal": prefit_terminal_ts,
        "prefit_terminal_index": prefit_terminal_index,
        "prefit_start_index": warmup_start,
    }


def metric_pass(metrics: dict[str, Any], *, min_trades: int) -> dict[str, bool]:
    win = metrics["win_rate"]
    return {
        "annualized_factor_ge_20x": metrics["annualized_factor"] >= TARGET_ANNUAL_FACTOR,
        "win_rate_ge_80pct": bool(np.isfinite(win) and win >= TARGET_WIN_RATE),
        "max_drawdown_lte_20pct": metrics["max_drawdown_pct"] >= -TARGET_MAX_DRAWDOWN * 100.0,
        "minimum_closed_trades": metrics["closed_trades"] >= min_trades,
        "pyramiding_observed": metrics["add_count"] >= 1,
    }


def serialize_config(config: Config) -> dict[str, Any]:
    payload = asdict(config)
    payload["mechanism_name"] = MECHANISM_NAMES[config.mechanism]
    payload["direction_name"] = DIRECTION_NAMES[config.direction]
    payload["initial_leverage"] = 1.0
    payload["pyramid_layer_leverage"] = 1.0
    payload["max_leverage"] = MAX_LEVERAGE
    return payload


def audit_candidate(
    config: Config,
    book: FeatureBook,
    bounds: dict[str, Any],
    *,
    retain_path: bool,
) -> dict[str, Any]:
    windows = {
        "prefit": (bounds["prefit_start_index"], bounds["prefit_terminal_index"]),
        "locked_oos_flat": (bounds["oos_start_index"], book.daily_count),
        "full": (0, book.daily_count),
    }
    results: dict[str, Any] = {}
    retained: dict[str, BacktestResult] = {}
    for name, (start, end) in windows.items():
        base = backtest(config, book, start_open_index=start, terminal_open_index=end, retain_path=retain_path)
        stress = backtest(config, book, start_open_index=start, terminal_open_index=end, slippage=STRESS_SLIPPAGE)
        delay = backtest(config, book, start_open_index=start, terminal_open_index=end, signal_delay_days=2)
        min_trades = MIN_OOS_TRADES if name == "locked_oos_flat" else MIN_PREFIT_TRADES
        checks = metric_pass(base.metrics, min_trades=min_trades)
        results[name] = {
            "base": base.metrics,
            "stress_8bps": stress.metrics,
            "k_plus_2": delay.metrics,
            "checks": checks,
            "literal_metric_pass": all(checks[key] for key in (
                "annualized_factor_ge_20x", "win_rate_ge_80pct", "max_drawdown_lte_20pct"
            )),
            "evidence_pass": all(checks.values()),
        }
        retained[name] = base
    return {"config": serialize_config(config), "windows": results, "retained": retained}


def recent_slices(full: BacktestResult) -> list[dict[str, Any]]:
    if not full.path:
        return []
    frame = pd.DataFrame(full.path)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    end = frame["ts"].iloc[-1]
    output: list[dict[str, Any]] = []
    for label, delta in RECENT_WINDOWS.items():
        sliced = frame.loc[frame["ts"] >= end - delta].copy()
        if len(sliced) < 2:
            continue
        normalized = sliced["equity"] / float(sliced["equity"].iloc[0])
        output.append({
            "window": label,
            "start_ts": sliced["ts"].iloc[0].isoformat(),
            "end_ts": sliced["ts"].iloc[-1].isoformat(),
            "return_pct": float((normalized.iloc[-1] - 1.0) * 100.0),
            "max_drawdown_pct": float((normalized / normalized.cummax() - 1.0).min() * 100.0),
            "ending_position": float(sliced["position"].iloc[-1]),
        })
    return output


def _config_json(config: Config) -> str:
    return json.dumps(serialize_config(config), sort_keys=True, ensure_ascii=False)


def _json_default(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def write_outputs(
    *,
    run_date: str,
    seed: int,
    stage1_count: int,
    stage2_count: int,
    book: FeatureBook,
    bounds: dict[str, Any],
    stage1: pd.DataFrame,
    combined: pd.DataFrame,
    audits: list[dict[str, Any]],
) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = ARTIFACT_DIR / f"hype-1d-pt-search-{run_date}.json"
    frontier_path = ARTIFACT_DIR / f"hype-1d-pt-prefit-frontier-{run_date}.csv"
    trades_path = ARTIFACT_DIR / f"hype-1d-pt-frozen-candidate-trades-{run_date}.csv"
    path_path = ARTIFACT_DIR / f"hype-1d-pt-frozen-candidate-path-{run_date}.csv"

    serializable_audits: list[dict[str, Any]] = []
    for audit in audits:
        clean = {"config": audit["config"], "windows": audit["windows"]}
        serializable_audits.append(clean)
    frozen = audits[0]
    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "family": FAMILY_NAME,
        "alias": FAMILY_ALIAS,
        "status": "explore / not promoted / not live-ready",
        "market": "Binance USD-M Futures",
        "symbol": SYMBOL,
        "timeframe": TIMEFRAME,
        "contract": {
            "max_leverage": MAX_LEVERAGE,
            "pyramiding": "1x initial plus up to two 1x adds, only after favorable close and ATR step",
            "target_annualized_factor": TARGET_ANNUAL_FACTOR,
            "target_win_rate": TARGET_WIN_RATE,
            "target_max_drawdown": TARGET_MAX_DRAWDOWN,
            "fee_per_filled_notional": BASE_FEE,
            "base_slippage_per_filled_notional": BASE_SLIPPAGE,
            "stress_slippage_per_filled_notional": STRESS_SLIPPAGE,
            "execution": "closed UTC daily signal at t; market-equivalent fill at t+1 open; K+2 audited",
            "drawdown": "conservative daily intrabar high-before-low or low-before-high bound including costs/funding",
            "trade_unit": "one campaign from initial entry through final flat; adds are fills, not separate wins",
            "oos_days": OOS_DAYS,
            "embargo_days": EMBARGO_DAYS,
            "minimum_prefit_trades": MIN_PREFIT_TRADES,
            "minimum_locked_oos_trades": MIN_OOS_TRADES,
        },
        "data_quality": book.quality,
        "funding_quality": book.funding_quality,
        "boundaries": {key: value.isoformat() if isinstance(value, pd.Timestamp) else value for key, value in bounds.items()},
        "search": {
            "seed": seed,
            "stage1_requested": stage1_count,
            "stage1_unique": int(len(stage1)),
            "stage2_requested": stage2_count,
            "combined_unique": int(len(combined)),
            "oos_used_for_selection": False,
            "families": list(MECHANISM_NAMES.values()),
        },
        "prefit_surface": {
            "literal_metric_hits": int((
                (combined["annualized_factor"] >= TARGET_ANNUAL_FACTOR)
                & (combined["win_rate"] >= TARGET_WIN_RATE)
                & (combined["max_drawdown_pct"] >= -20.0)
            ).sum()),
            "evidence_hits": int((
                (combined["annualized_factor"] >= TARGET_ANNUAL_FACTOR)
                & (combined["win_rate"] >= TARGET_WIN_RATE)
                & (combined["max_drawdown_pct"] >= -20.0)
                & (combined["closed_trades"] >= MIN_PREFIT_TRADES)
                & (combined["add_count"] >= 1)
            ).sum()),
            "best_annualized_factor_dd_safe": float(combined.loc[combined["max_drawdown_pct"] >= -20.0, "annualized_factor"].max()) if (combined["max_drawdown_pct"] >= -20.0).any() else None,
            "best_win_rate_dd_safe_min_trades": float(combined.loc[(combined["max_drawdown_pct"] >= -20.0) & (combined["closed_trades"] >= MIN_PREFIT_TRADES), "win_rate"].max()) if ((combined["max_drawdown_pct"] >= -20.0) & (combined["closed_trades"] >= MIN_PREFIT_TRADES)).any() else None,
        },
        "frozen_prefit_primary": frozen["config"],
        "frozen_primary_recent_slices": recent_slices(frozen["retained"]["full"]),
        "audited_candidates": serializable_audits,
        "joint_final_pass_count": sum(
            audit["windows"]["prefit"]["evidence_pass"]
            and audit["windows"]["locked_oos_flat"]["evidence_pass"]
            and audit["windows"]["full"]["evidence_pass"]
            for audit in audits
        ),
    }
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )

    frontier = rank_prefit(combined, 250).copy()
    frontier["config"] = frontier["config"].map(_config_json)
    frontier.to_csv(frontier_path, index=False)
    pd.DataFrame(frozen["retained"]["full"].trades).to_csv(trades_path, index=False)
    pd.DataFrame(frozen["retained"]["full"].path).to_csv(path_path, index=False)
    print(json.dumps({
        "summary": str(summary_path.relative_to(ROOT)),
        "frontier": str(frontier_path.relative_to(ROOT)),
        "trades": str(trades_path.relative_to(ROOT)),
        "path": str(path_path.relative_to(ROOT)),
        "prefit_surface": payload["prefit_surface"],
        "joint_final_pass_count": payload["joint_final_pass_count"],
        "frozen_primary_windows": frozen["windows"],
    }, indent=2, ensure_ascii=False, default=_json_default), flush=True)


def self_test() -> None:
    values = np.array([100.0, 101.0, 102.0, 103.0, 104.0])
    assert np.isnan(_prior_roll(values, 2, "max")[1])
    assert _prior_roll(values, 2, "max")[2] == 101.0
    assert math.isclose(_annual_factor(2.0, 365.25), 2.0)
    assert math.isclose(_annual_factor(4.0, 730.5), 2.0)
    print("self-test: PASS")


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    book = build_feature_book()
    bounds = boundaries(book)
    rng = random.Random(args.seed)
    stage1_configs = (random_config(rng) for _ in range(args.stage1))
    stage1 = search_stage(
        stage1_configs, book,
        prefit_start=bounds["prefit_start_index"],
        prefit_terminal=bounds["prefit_terminal_index"],
        workers=args.workers,
        label="stage1",
    )
    parents_frame = rank_prefit(stage1, max(40, min(args.shortlist, 400)))
    parents = list(parents_frame["config"])
    if not parents:
        raise RuntimeError("stage 1 produced no parent candidates")
    stage2_configs = (mutate_config(rng.choice(parents), rng) for _ in range(args.stage2))
    stage2 = search_stage(
        stage2_configs, book,
        prefit_start=bounds["prefit_start_index"],
        prefit_terminal=bounds["prefit_terminal_index"],
        workers=args.workers,
        label="stage2",
    )
    combined = pd.concat([stage1, stage2], ignore_index=True)
    combined["config_key"] = combined["config"].map(lambda value: value.key)
    combined = combined.drop_duplicates("config_key").drop(columns="config_key")
    frozen_frame = rank_prefit(combined, args.shortlist)
    frozen_configs = list(frozen_frame["config"])
    audits = [
        audit_candidate(config, book, bounds, retain_path=index == 0)
        for index, config in enumerate(frozen_configs)
    ]
    write_outputs(
        run_date=args.run_date, seed=args.seed,
        stage1_count=args.stage1, stage2_count=args.stage2,
        book=book, bounds=bounds, stage1=stage1,
        combined=combined, audits=audits,
    )


if __name__ == "__main__":
    main()
