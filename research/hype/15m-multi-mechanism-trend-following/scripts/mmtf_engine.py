from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.data import DataLakeLayout, DuckDBWarehouse, MarketType
from strategy_lab.data.settings import load_settings

ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-multi-mechanism-trend-following"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
MANIFEST_PATH = ARTIFACT_DIR / "hype_15m_mmtf_dataset_freeze_2026-07-22.json"
FUNDING_PATH = (
    ROOT
    / "data/normalized/funding/exchange=binance/market_type=perp"
    / "symbol=hype_usdt_usdt/funding.parquet"
)

BASE_FEE = 0.001
BASE_SLIPPAGE = 0.0004
STRESS_SLIPPAGE = 0.0008
HOURS_PER_YEAR = 365.25 * 24.0

MECHANISMS = {
    0: "donchian_breakout",
    1: "keltner_breakout",
    2: "ema_pullback_continuation",
    3: "timeseries_momentum",
    4: "range_expansion_breakout",
}
DIRECTIONS = {0: "both", 1: "long_only", 2: "short_only"}

ENTRY_WINDOWS = (16, 24, 32, 48, 64, 96, 144, 192, 288, 384, 672)
EXIT_WINDOWS = (8, 12, 16, 24, 32, 48, 72, 96, 144, 192)
EMA_SPANS = (8, 12, 16, 24, 32, 48, 72, 96, 144, 192, 288, 384, 672, 960, 1536)
ATR_WINDOWS = (14, 28, 48, 96, 192)


@dataclass(frozen=True, slots=True)
class Config:
    mechanism: int
    direction: int
    entry_window: int
    exit_window: int
    ema_fast: int
    ema_slow: int
    atr_window: int
    adx_min: float
    rvol_min: float
    breakout_atr: float
    expansion_min: float
    sl_atr: float
    tp_atr: float
    trail_activation_atr: float
    trail_atr: float
    breakeven_trigger_atr: float
    max_hold_bars: int
    cooldown_bars: int
    leverage: float
    trend_exit: bool

    def validate(self) -> None:
        if self.mechanism not in MECHANISMS:
            raise ValueError("unknown mechanism")
        if self.direction not in DIRECTIONS:
            raise ValueError("unknown direction")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be below ema_slow")
        if not 0.0 < self.leverage <= 3.0:
            raise ValueError("leverage must be in (0, 3]")
        if self.sl_atr <= 0.0 or self.trail_atr <= 0.0:
            raise ValueError("stop and trailing distances must be positive")
        if min(self.entry_window, self.exit_window, self.atr_window, self.max_hold_bars) <= 0:
            raise ValueError("window lengths must be positive")

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
    volume: np.ndarray
    atr: dict[int, np.ndarray]
    adx: np.ndarray
    ema: dict[int, np.ndarray]
    prior_high: dict[int, np.ndarray]
    prior_low: dict[int, np.ndarray]
    momentum_atr: dict[tuple[int, int], np.ndarray]
    rvol: np.ndarray
    tr_over_atr: dict[int, np.ndarray]
    funding_by_bar: np.ndarray
    source_start: pd.Timestamp
    selection_end: pd.Timestamp

    @property
    def rows(self) -> int:
        return len(self.ts)


@dataclass(slots=True)
class BacktestResult:
    metrics: dict[str, Any]
    trades: list[dict[str, Any]]
    equity_path: list[dict[str, Any]]


def config_from_dict(payload: dict[str, Any]) -> Config:
    fields = set(Config.__dataclass_fields__)
    return Config(**{key: payload[key] for key in fields})


def config_dict(config: Config) -> dict[str, Any]:
    payload = asdict(config)
    payload["mechanism_name"] = MECHANISMS[config.mechanism]
    payload["direction_name"] = DIRECTIONS[config.direction]
    return payload


def config_sha256(config: Config) -> str:
    canonical = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest["quality"]["blocker_count"] != 0:
        raise RuntimeError("frozen dataset has quality blockers")
    return manifest


def _load_market() -> pd.DataFrame:
    warehouse = DuckDBWarehouse(
        DataLakeLayout.from_settings(load_settings(None))
    )
    return warehouse.load_trusted_ohlcv(
        exchange="binance",
        market_type=MarketType.PERP,
        symbol="HYPE/USDT:USDT",
        timeframe="15m",
    ).reset_index(drop=True)


def _ema(values: np.ndarray, span: int) -> np.ndarray:
    return (
        pd.Series(values)
        .ewm(span=span, adjust=False, min_periods=span)
        .mean()
        .to_numpy("float64")
    )


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int) -> np.ndarray:
    prior_close = np.r_[np.nan, close[:-1]]
    true_range = np.maximum(
        high - low,
        np.maximum(np.abs(high - prior_close), np.abs(low - prior_close)),
    )
    return (
        pd.Series(true_range)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )


def _adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 14) -> np.ndarray:
    up = np.r_[np.nan, np.diff(high)]
    down = np.r_[np.nan, -np.diff(low)]
    plus_dm = np.where((up > down) & (up > 0.0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0.0), down, 0.0)
    atr = _atr(high, low, close, window)
    plus = (
        100.0
        * pd.Series(plus_dm)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
        / atr
    )
    minus = (
        100.0
        * pd.Series(minus_dm)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
        / atr
    )
    denominator = plus + minus
    dx = 100.0 * np.abs(plus - minus) / np.where(denominator == 0.0, np.nan, denominator)
    return (
        pd.Series(dx)
        .ewm(alpha=1.0 / window, adjust=False, min_periods=window)
        .mean()
        .to_numpy("float64")
    )


def _prior_roll(values: np.ndarray, window: int, kind: str) -> np.ndarray:
    rolling = pd.Series(values).shift(1).rolling(window, min_periods=window)
    return (rolling.max() if kind == "max" else rolling.min()).to_numpy("float64")


def _funding_by_bar(ts: pd.DatetimeIndex, funding: pd.DataFrame) -> np.ndarray:
    event_ts = pd.DatetimeIndex(pd.to_datetime(funding["ts"], utc=True)).as_unit("ns").asi8
    event_rates = funding["funding_rate"].to_numpy("float64")
    opens = ts.as_unit("ns").asi8
    closes = (ts + pd.Timedelta(minutes=15)).as_unit("ns").asi8
    output = np.zeros(len(ts), dtype="float64")
    for index, (left_ts, right_ts) in enumerate(zip(opens, closes, strict=True)):
        left = int(np.searchsorted(event_ts, left_ts, side="left"))
        right = int(np.searchsorted(event_ts, right_ts, side="left"))
        if right > left:
            output[index] = float(event_rates[left:right].sum())
    return output


def build_book(*, include_locked_oos: bool = False) -> FeatureBook:
    manifest = load_manifest()
    frame = _load_market()
    terminal = pd.Timestamp(manifest["freeze_contract"]["data_terminal_exclusive"])
    oos_start = pd.Timestamp(manifest["freeze_contract"]["locked_oos_start_inclusive"])
    frame = frame.loc[frame["ts"] < terminal].copy()
    if not include_locked_oos:
        frame = frame.loc[frame["ts"] < oos_start].copy()
        terminal = oos_start
    expected_rows = (
        manifest["rows"]["all"] if include_locked_oos else manifest["rows"]["prefit"]
    )
    if len(frame) != expected_rows:
        raise RuntimeError(f"frozen row-count mismatch: {len(frame)} != {expected_rows}")

    funding = pd.read_parquet(FUNDING_PATH)
    funding["ts"] = pd.to_datetime(funding["ts"], utc=True)
    funding = funding.loc[funding["ts"] < terminal].sort_values("ts").reset_index(drop=True)
    ts = pd.DatetimeIndex(frame["ts"])
    open_values = frame["open"].to_numpy("float64")
    high = frame["high"].to_numpy("float64")
    low = frame["low"].to_numpy("float64")
    close = frame["close"].to_numpy("float64")
    volume = frame["volume"].to_numpy("float64")
    atr = {window: _atr(high, low, close, window) for window in ATR_WINDOWS}
    ema = {span: _ema(close, span) for span in EMA_SPANS}
    prior_high = {window: _prior_roll(high, window, "max") for window in ENTRY_WINDOWS + EXIT_WINDOWS}
    prior_low = {window: _prior_roll(low, window, "min") for window in ENTRY_WINDOWS + EXIT_WINDOWS}
    momentum_atr: dict[tuple[int, int], np.ndarray] = {}
    for window in sorted(set(ENTRY_WINDOWS + EXIT_WINDOWS)):
        delta = close - np.r_[np.full(window, np.nan), close[:-window]]
        for atr_window, values in atr.items():
            momentum_atr[(window, atr_window)] = delta / values
    prior_close = np.r_[np.nan, close[:-1]]
    true_range = np.maximum(
        high - low,
        np.maximum(np.abs(high - prior_close), np.abs(low - prior_close)),
    )
    tr_over_atr = {window: true_range / values for window, values in atr.items()}
    rvol = volume / (
        pd.Series(volume).shift(1).rolling(96, min_periods=96).median().to_numpy("float64")
    )
    return FeatureBook(
        ts=ts,
        terminal_ts=terminal,
        open=open_values,
        high=high,
        low=low,
        close=close,
        volume=volume,
        atr=atr,
        adx=_adx(high, low, close),
        ema=ema,
        prior_high=prior_high,
        prior_low=prior_low,
        momentum_atr=momentum_atr,
        rvol=rvol,
        tr_over_atr=tr_over_atr,
        funding_by_bar=_funding_by_bar(ts, funding),
        source_start=pd.Timestamp(ts[0]),
        selection_end=oos_start,
    )


def _crossed_above(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    condition = left > right
    return condition & ~np.r_[False, condition[:-1]]


def _crossed_below(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    condition = left < right
    return condition & ~np.r_[False, condition[:-1]]


def build_signals(
    book: FeatureBook,
    config: Config,
    *,
    disabled_components: frozenset[str] = frozenset(),
) -> np.ndarray:
    config.validate()
    close = book.close
    atr = book.atr[config.atr_window]
    ema_fast = book.ema[config.ema_fast]
    ema_slow = book.ema[config.ema_slow]
    directional_regime_long = ema_fast > ema_slow
    directional_regime_short = ema_fast < ema_slow

    if config.mechanism == 0:
        long_signal = close > book.prior_high[config.entry_window] + config.breakout_atr * atr
        short_signal = close < book.prior_low[config.entry_window] - config.breakout_atr * atr
    elif config.mechanism == 1:
        upper = ema_slow + config.expansion_min * atr
        lower = ema_slow - config.expansion_min * atr
        long_signal = _crossed_above(close, upper)
        short_signal = _crossed_below(close, lower)
    elif config.mechanism == 2:
        long_signal = directional_regime_long & _crossed_above(close, ema_fast)
        short_signal = directional_regime_short & _crossed_below(close, ema_fast)
    elif config.mechanism == 3:
        normalized_momentum = book.momentum_atr[(config.entry_window, config.atr_window)]
        long_signal = _crossed_above(normalized_momentum, np.full(book.rows, config.expansion_min))
        short_signal = _crossed_below(normalized_momentum, np.full(book.rows, -config.expansion_min))
    else:
        expansion = book.tr_over_atr[config.atr_window] >= config.expansion_min
        long_signal = (
            close > book.prior_high[config.entry_window] + config.breakout_atr * atr
        ) & expansion
        short_signal = (
            close < book.prior_low[config.entry_window] - config.breakout_atr * atr
        ) & expansion

    if "primary_entry" in disabled_components:
        long_signal[:] = False
        short_signal[:] = False
    if config.mechanism != 2 and "ema_regime" not in disabled_components:
        long_signal &= directional_regime_long
        short_signal &= directional_regime_short
    common = (
        np.isfinite(atr)
        & np.isfinite(book.adx)
        & np.isfinite(book.rvol)
    )
    if "adx_filter" not in disabled_components:
        common &= book.adx >= config.adx_min
    if "rvol_filter" not in disabled_components:
        common &= book.rvol >= config.rvol_min
    long_signal &= common
    short_signal &= common
    if config.direction == 1:
        short_signal[:] = False
    elif config.direction == 2:
        long_signal[:] = False
    signal = np.zeros(book.rows, dtype="int8")
    signal[long_signal] = 1
    signal[short_signal] = -1
    return signal


def _trend_exit_signal(book: FeatureBook, config: Config, index: int, side: int) -> bool:
    if not config.trend_exit:
        return False
    close = book.close[index]
    if config.mechanism in {0, 4}:
        boundary = (
            book.prior_low[config.exit_window][index]
            if side == 1
            else book.prior_high[config.exit_window][index]
        )
        return bool(close < boundary) if side == 1 else bool(close > boundary)
    if config.mechanism in {1, 2}:
        fast = book.ema[config.ema_fast][index]
        slow = book.ema[config.ema_slow][index]
        return bool(fast < slow) if side == 1 else bool(fast > slow)
    momentum = book.momentum_atr[(config.exit_window, config.atr_window)][index]
    return bool(momentum < 0.0) if side == 1 else bool(momentum > 0.0)


def _adverse_fill(raw_price: float, side: int, *, is_entry: bool, slippage: float) -> float:
    signed = side if is_entry else -side
    return float(raw_price * (1.0 + signed * slippage))


def _metrics(
    *,
    equity_points: list[float],
    trades: list[dict[str, Any]],
    start_ts: pd.Timestamp,
    end_ts: pd.Timestamp,
    liquidated: bool,
) -> dict[str, Any]:
    equity_array = np.asarray(equity_points if equity_points else [1.0], dtype="float64")
    peaks = np.maximum.accumulate(equity_array)
    drawdowns = equity_array / peaks - 1.0
    ending_equity = float(equity_array[-1])
    hours = max(1.0, (end_ts - start_ts).total_seconds() / 3600.0)
    annual_log = (
        math.log(ending_equity) * HOURS_PER_YEAR / hours
        if ending_equity > 0.0
        else -math.inf
    )
    annual_factor = float(math.exp(min(annual_log, 690.0))) if np.isfinite(annual_log) else 0.0
    returns = np.asarray([trade["net_return"] for trade in trades], dtype="float64")
    wins = returns[returns > 0.0]
    losses = returns[returns <= 0.0]
    profit_factor = (
        float(wins.sum() / abs(losses.sum()))
        if len(losses) and losses.sum() < 0.0
        else (float("inf") if len(wins) else 0.0)
    )
    return {
        "start_ts": start_ts.isoformat(),
        "end_ts": end_ts.isoformat(),
        "hours": hours,
        "ending_equity": ending_equity,
        "total_return": ending_equity - 1.0,
        "annual_factor": annual_factor,
        "max_drawdown": float(-drawdowns.min()),
        "win_rate": float((returns > 0.0).mean()) if len(returns) else 0.0,
        "trades": int(len(trades)),
        "profit_factor": profit_factor,
        "average_trade": float(returns.mean()) if len(returns) else 0.0,
        "median_trade": float(np.median(returns)) if len(returns) else 0.0,
        "fee_return": float(sum(trade["fee_return"] for trade in trades)),
        "slippage_return": float(sum(trade["slippage_return"] for trade in trades)),
        "funding_return": float(sum(trade["funding_return"] for trade in trades)),
        "liquidated": liquidated,
    }


def run_backtest(
    book: FeatureBook,
    config: Config,
    *,
    start_ts: pd.Timestamp | None = None,
    end_ts: pd.Timestamp | None = None,
    entry_delay_bars: int = 1,
    slippage_per_fill: float = BASE_SLIPPAGE,
    detailed: bool = False,
    disabled_components: frozenset[str] = frozenset(),
) -> BacktestResult:
    config.validate()
    if entry_delay_bars < 1:
        raise ValueError("entry_delay_bars must be at least one")
    start_ts = pd.Timestamp(start_ts) if start_ts is not None else book.source_start
    end_ts = pd.Timestamp(end_ts) if end_ts is not None else book.terminal_ts
    if start_ts.tzinfo is None:
        start_ts = start_ts.tz_localize("UTC")
    if end_ts.tzinfo is None:
        end_ts = end_ts.tz_localize("UTC")
    start_index = int(np.searchsorted(book.ts.as_unit("ns").asi8, start_ts.value, side="left"))
    end_index = int(np.searchsorted(book.ts.as_unit("ns").asi8, end_ts.value, side="left"))
    end_index = min(end_index, book.rows)
    signal = build_signals(
        book, config, disabled_components=disabled_components
    )

    equity = 1.0
    equity_points = [equity]
    equity_path: list[dict[str, Any]] = []
    trades: list[dict[str, Any]] = []
    next_allowed_signal = start_index
    cursor = start_index
    liquidated = False

    while cursor < end_index - entry_delay_bars:
        candidates = np.flatnonzero(signal[max(cursor, next_allowed_signal): end_index - entry_delay_bars])
        if not len(candidates):
            break
        signal_index = max(cursor, next_allowed_signal) + int(candidates[0])
        entry_index = signal_index + entry_delay_bars
        if entry_index >= end_index:
            break
        side = int(signal[signal_index])
        entry_atr = float(book.atr[config.atr_window][signal_index])
        if not np.isfinite(entry_atr) or entry_atr <= 0.0:
            cursor = signal_index + 1
            continue

        raw_entry = float(book.open[entry_index])
        entry_fill = _adverse_fill(
            raw_entry, side, is_entry=True, slippage=slippage_per_fill
        )
        entry_equity = equity
        entry_fee = config.leverage * BASE_FEE
        stop = raw_entry - side * config.sl_atr * entry_atr
        target = (
            raw_entry + side * config.tp_atr * entry_atr
            if config.tp_atr > 0.0
            else (math.inf if side == 1 else -math.inf)
        )
        trailing_stop = stop
        favorable_extreme = raw_entry
        funding_sum = 0.0
        pending_exit = False
        exit_reason = "terminal"
        exit_index = end_index - 1
        raw_exit_used = float(book.close[exit_index])
        exit_fill = raw_exit_used
        trade_mark_points: list[tuple[pd.Timestamp, float]] = []

        equity_after_entry = entry_equity * (1.0 - entry_fee)
        equity_points.append(equity_after_entry)
        if detailed:
            trade_mark_points.append((pd.Timestamp(book.ts[entry_index]), equity_after_entry))

        for bar in range(entry_index, end_index):
            raw_exit: float | None = None
            reason: str | None = None
            if pending_exit:
                raw_exit = float(book.open[bar])
                reason = exit_reason
            else:
                bar_open = float(book.open[bar])
                bar_high = float(book.high[bar])
                bar_low = float(book.low[bar])
                active_stop = trailing_stop
                if side == 1:
                    if bar_open <= active_stop:
                        raw_exit, reason = bar_open, "stop_gap_open"
                    elif bar_low <= active_stop:
                        raw_exit, reason = active_stop, "stop"
                    elif config.tp_atr > 0.0 and bar_open >= target:
                        raw_exit, reason = target, "take_profit_gap"
                    elif config.tp_atr > 0.0 and bar_high >= target:
                        raw_exit, reason = target, "take_profit"
                else:
                    if bar_open >= active_stop:
                        raw_exit, reason = bar_open, "stop_gap_open"
                    elif bar_high >= active_stop:
                        raw_exit, reason = active_stop, "stop"
                    elif config.tp_atr > 0.0 and bar_open <= target:
                        raw_exit, reason = target, "take_profit_gap"
                    elif config.tp_atr > 0.0 and bar_low <= target:
                        raw_exit, reason = target, "take_profit"

            if raw_exit is not None and reason is not None:
                raw_exit_used = raw_exit
                exit_fill = _adverse_fill(
                    raw_exit, side, is_entry=False, slippage=slippage_per_fill
                )
                exit_index = bar
                exit_reason = reason
                break

            funding_sum += float(book.funding_by_bar[bar])
            adverse_mark = float(book.low[bar] if side == 1 else book.high[bar])
            adverse_factor = (
                1.0
                + config.leverage * side * (adverse_mark / entry_fill - 1.0)
                - entry_fee
                - config.leverage * side * funding_sum
            )
            marked_equity = entry_equity * adverse_factor
            equity_points.append(max(0.0, marked_equity))
            if detailed:
                trade_mark_points.append((pd.Timestamp(book.ts[bar]), max(0.0, marked_equity)))
            if marked_equity <= 0.0:
                liquidated = True
                equity = 0.0
                exit_index = bar
                exit_fill = adverse_mark
                exit_reason = "liquidation"
                break

            favorable_extreme = (
                max(favorable_extreme, float(book.high[bar]))
                if side == 1
                else min(favorable_extreme, float(book.low[bar]))
            )
            favorable_atr = side * (favorable_extreme - raw_entry) / entry_atr
            if favorable_atr >= config.trail_activation_atr:
                proposed = favorable_extreme - side * config.trail_atr * entry_atr
                trailing_stop = max(trailing_stop, proposed) if side == 1 else min(trailing_stop, proposed)
            if (
                config.breakeven_trigger_atr > 0.0
                and favorable_atr >= config.breakeven_trigger_atr
            ):
                trailing_stop = max(trailing_stop, raw_entry) if side == 1 else min(trailing_stop, raw_entry)

            held_bars = bar - entry_index + 1
            if held_bars >= config.max_hold_bars:
                pending_exit = True
                exit_reason = "timeout"
            elif _trend_exit_signal(book, config, bar, side):
                pending_exit = True
                exit_reason = "trend_exit"

        if liquidated:
            break
        if exit_index == end_index - 1 and exit_reason == "terminal":
            raw_exit = float(book.close[exit_index])
            raw_exit_used = raw_exit
            exit_fill = _adverse_fill(
                raw_exit, side, is_entry=False, slippage=slippage_per_fill
            )
        exit_fee = config.leverage * BASE_FEE
        price_return = side * (exit_fill / entry_fill - 1.0)
        net_return = config.leverage * (price_return - side * funding_sum) - entry_fee - exit_fee
        equity = entry_equity * (1.0 + net_return)
        equity_points.append(max(0.0, equity))
        raw_price_return = side * (raw_exit_used / raw_entry - 1.0)
        slippage_return = config.leverage * (price_return - raw_price_return)
        trade = {
            "signal_ts": pd.Timestamp(book.ts[signal_index]).isoformat(),
            "entry_ts": pd.Timestamp(book.ts[entry_index]).isoformat(),
            "exit_ts": pd.Timestamp(book.ts[exit_index]).isoformat(),
            "side": side,
            "entry_price": entry_fill,
            "exit_price": exit_fill,
            "entry_atr": entry_atr,
            "leverage": config.leverage,
            "bars_held": int(exit_index - entry_index + 1),
            "exit_reason": exit_reason,
            "net_return": float(net_return),
            "fee_return": float(-(entry_fee + exit_fee)),
            "slippage_return": float(slippage_return),
            "funding_return": float(-config.leverage * side * funding_sum),
            "entry_equity": float(entry_equity),
            "exit_equity": float(equity),
        }
        trades.append(trade)
        if detailed:
            equity_path.extend(
                {"ts": ts.isoformat(), "equity": value, "trade": len(trades)}
                for ts, value in trade_mark_points
            )
            equity_path.append(
                {
                    "ts": pd.Timestamp(book.ts[exit_index]).isoformat(),
                    "equity": float(equity),
                    "trade": len(trades),
                }
            )
        if equity <= 0.0:
            liquidated = True
            break
        next_allowed_signal = exit_index + 1 + config.cooldown_bars
        cursor = max(exit_index + 1, next_allowed_signal)

    metrics = _metrics(
        equity_points=equity_points,
        trades=trades,
        start_ts=start_ts,
        end_ts=end_ts,
        liquidated=liquidated,
    )
    return BacktestResult(metrics=metrics, trades=trades, equity_path=equity_path)


def replace_config(config: Config, **changes: Any) -> Config:
    return replace(config, **changes)


def trade_signature(result: BacktestResult) -> str:
    canonical = json.dumps(
        [
            (
                trade["signal_ts"], trade["entry_ts"], trade["exit_ts"],
                trade["side"], trade["exit_reason"],
                round(trade["entry_price"], 12), round(trade["exit_price"], 12),
                round(trade["net_return"], 12),
            )
            for trade in result.trades
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
