from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

import numpy as np
import pandas as pd


BarsPerYear = 365 * 24 * 4


@dataclass(frozen=True, slots=True)
class CandleCountIntrabarBacktestConfig:
    """Single-symbol HYPE V10 candle-count backtest with mark-price exits."""

    min_count: int = 8
    lookback: int = 10
    allocation: float = 3.0
    allocation_atr_window: int | None = 96
    target_atr_pct: float | None = 0.004
    stop_loss_pct: float = 0.03
    stop_loss_atr_window: int | None = 288
    stop_loss_atr_multiplier: float | None = 5.0
    min_stop_loss_pct: float = 0.025
    max_stop_loss_pct: float = 0.035
    take_profit_pct: float = 0.03
    take_profit_atr_window: int | None = 192
    take_profit_atr_multiplier: float | None = 6.0
    min_take_profit_pct: float = 0.02
    max_take_profit_pct: float = 0.04
    trend_window_bars: int | None = 96
    trend_block_pct: float | None = 0.06
    cooldown_bars: int = 8
    opposite_signal_gap_bars: int = 8
    entry_mode: Literal["always", "signal_start"] = "signal_start"
    stop_loss_risk_multiplier: float = 0.5
    min_risk_multiplier: float = 0.125
    fee_rate: float = 0.00045
    slippage_rate: float = 0.0004
    annualization_bars: int = BarsPerYear


@dataclass(frozen=True, slots=True)
class CandleCountTradeEvent:
    ts: pd.Timestamp
    event: Literal["entry", "stop", "take", "flat"]
    direction: int
    equity: float


@dataclass(frozen=True, slots=True)
class CandleCountIntrabarBacktestResult:
    equity_curve: pd.Series
    period_returns: pd.Series
    weights: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, float]


def build_candle_count_signal(
    frame: pd.DataFrame, config: CandleCountIntrabarBacktestConfig
) -> pd.Series:
    """Build +1/-1/0 signal from recent bullish and bearish candle counts."""

    _validate_input_frame(frame, required_columns=("open", "close"))
    bullish_count = (
        frame["close"]
        .gt(frame["open"])
        .astype("float64")
        .rolling(
            config.lookback,
            min_periods=config.lookback,
        )
        .sum()
    )
    bearish_count = (
        frame["close"]
        .lt(frame["open"])
        .astype("float64")
        .rolling(
            config.lookback,
            min_periods=config.lookback,
        )
        .sum()
    )
    signal = pd.Series(0, index=frame.index, dtype="int64", name="signal")
    signal.loc[bullish_count.ge(config.min_count)] = -1
    signal.loc[bearish_count.ge(config.min_count)] = 1
    return signal


def run_candle_count_intrabar_backtest(
    frame: pd.DataFrame,
    config: CandleCountIntrabarBacktestConfig | None = None,
    *,
    trade_start: pd.Timestamp | str | None = None,
    trade_end: pd.Timestamp | str | None = None,
) -> CandleCountIntrabarBacktestResult:
    """Run candle-count strategy using close entries and mark high/low exits.

    Required columns are:
    - open, close: trade-price candles used for signals and mark-to-market PnL.
    - mark_high, mark_low: mark-price intrabar stop/take triggers.
    - funding_rate: optional per-bar funding rate settled when present.
    """

    config = config or CandleCountIntrabarBacktestConfig()
    _validate_config(config)
    frame = _normalize_frame(frame)
    _validate_input_frame(
        frame, required_columns=("open", "close", "mark_high", "mark_low")
    )

    signal = build_candle_count_signal(frame, config)
    funding_rate = (
        frame.get("funding_rate", pd.Series(0.0, index=frame.index))
        .fillna(0.0)
        .astype("float64")
    )
    close = frame["close"].astype("float64")
    mark_high = frame["mark_high"].astype("float64")
    mark_low = frame["mark_low"].astype("float64")
    allocation_atr = _atr_pct(frame, config.allocation_atr_window)
    stop_loss_atr = _atr_pct(frame, config.stop_loss_atr_window)
    take_profit_atr = _atr_pct(frame, config.take_profit_atr_window)
    trend_return = _trend_return(close, config.trend_window_bars)

    start_position, end_position = _trade_bounds(
        frame, trade_start=trade_start, trade_end=trade_end
    )
    cost_rate = config.fee_rate + config.slippage_rate
    equity = 1.0
    previous_price = float(close.iloc[start_position])
    current_direction = 0
    entry_price = np.nan
    current_allocation = 0.0
    current_stop_loss_pct = config.stop_loss_pct
    current_take_profit_pct = config.take_profit_pct
    risk_multiplier = 1.0
    cooldown_remaining = 0

    equity_values: list[float] = []
    period_returns: list[float] = []
    weights: list[float] = []
    events: list[CandleCountTradeEvent] = []
    trading_costs = 0.0
    funding_pnl = 0.0
    stops = 0
    takes = 0
    entries = 0
    exits = 0

    for position in range(start_position, end_position + 1):
        ts = frame.index[position]
        close_price = float(close.iloc[position])
        bar_return = 0.0
        exited_this_bar = False
        cooldown_at_start = cooldown_remaining

        if position > start_position and current_direction != 0:
            exit_price, exit_reason = _intrabar_exit(
                direction=current_direction,
                entry_price=float(entry_price),
                mark_high=float(mark_high.iloc[position]),
                mark_low=float(mark_low.iloc[position]),
                stop_loss_pct=current_stop_loss_pct,
                take_profit_pct=current_take_profit_pct,
            )
            if exit_price is None:
                pnl = (
                    current_direction
                    * current_allocation
                    * (close_price / previous_price - 1.0)
                )
                equity *= 1.0 + pnl
                bar_return += pnl
                previous_price = close_price
            else:
                pnl = (
                    current_direction
                    * current_allocation
                    * (exit_price / previous_price - 1.0)
                )
                cost = current_allocation * cost_rate
                equity *= 1.0 + pnl - cost
                bar_return += pnl - cost
                previous_price = close_price
                trading_costs += cost
                exits += 1
                if exit_reason == "stop":
                    stops += 1
                    risk_multiplier = max(
                        config.min_risk_multiplier,
                        risk_multiplier * config.stop_loss_risk_multiplier,
                    )
                elif exit_reason == "take":
                    takes += 1
                    risk_multiplier = 1.0
                events.append(
                    CandleCountTradeEvent(
                        ts=pd.Timestamp(ts),
                        event=exit_reason,
                        direction=current_direction,
                        equity=equity,
                    )
                )
                current_direction = 0
                entry_price = np.nan
                current_allocation = 0.0
                exited_this_bar = True
                cooldown_remaining = max(cooldown_remaining, config.cooldown_bars)
        elif position > start_position:
            previous_price = close_price

        if current_direction != 0:
            funding = (
                -current_direction
                * current_allocation
                * float(funding_rate.iloc[position])
            )
            equity *= 1.0 + funding
            bar_return += funding
            funding_pnl += funding

        if current_direction == 0 and cooldown_remaining == 0 and not exited_this_bar:
            desired_direction = int(signal.iloc[position])
            if (
                desired_direction != 0
                and _entry_allowed(signal, position, desired_direction, config)
                and _trend_filter_allows(
                    trend_return, position, desired_direction, config
                )
            ):
                allocation = (
                    _entry_allocation(allocation_atr, position, config)
                    * risk_multiplier
                )
                stop_loss_pct = _dynamic_pct(
                    stop_loss_atr,
                    position,
                    fallback=config.stop_loss_pct,
                    multiplier=config.stop_loss_atr_multiplier,
                    lower=config.min_stop_loss_pct,
                    upper=config.max_stop_loss_pct,
                )
                take_profit_pct = _dynamic_pct(
                    take_profit_atr,
                    position,
                    fallback=config.take_profit_pct,
                    multiplier=config.take_profit_atr_multiplier,
                    lower=config.min_take_profit_pct,
                    upper=config.max_take_profit_pct,
                )
                if allocation <= 0.0 or stop_loss_pct <= 0.0 or take_profit_pct <= 0.0:
                    equity_values.append(equity)
                    period_returns.append(bar_return)
                    weights.append(0.0)
                    if cooldown_at_start > 0:
                        cooldown_remaining -= 1
                    continue
                current_direction = desired_direction
                entry_price = close_price
                previous_price = close_price
                current_allocation = allocation
                current_stop_loss_pct = stop_loss_pct
                current_take_profit_pct = take_profit_pct
                cost = current_allocation * cost_rate
                equity *= 1.0 - cost
                bar_return -= cost
                trading_costs += cost
                entries += 1
                events.append(
                    CandleCountTradeEvent(
                        ts=pd.Timestamp(ts),
                        event="entry",
                        direction=current_direction,
                        equity=equity,
                    )
                )

        equity_values.append(equity)
        period_returns.append(bar_return)
        weights.append(current_direction * current_allocation)
        if cooldown_at_start > 0:
            cooldown_remaining -= 1

    trade_index = frame.index[start_position : end_position + 1]
    equity_curve = pd.Series(equity_values, index=trade_index, name="equity")
    period_return_series = pd.Series(
        period_returns, index=trade_index, name="period_return"
    )
    weight_series = pd.Series(weights, index=trade_index, name="weight")
    trades = pd.DataFrame([asdict(event) for event in events])
    metrics = _metrics(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        entries=entries,
        exits=exits,
        stops=stops,
        takes=takes,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl,
        annualization_bars=config.annualization_bars,
    )
    return CandleCountIntrabarBacktestResult(
        equity_curve=equity_curve,
        period_returns=period_return_series,
        weights=weight_series,
        trades=trades,
        metrics=metrics,
    )


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "ts" in normalized.columns:
        normalized["ts"] = pd.to_datetime(normalized["ts"], utc=True)
        normalized = normalized.set_index("ts")
    normalized.index = pd.to_datetime(normalized.index, utc=True)
    return normalized.sort_index()


def _trade_bounds(
    frame: pd.DataFrame,
    *,
    trade_start: pd.Timestamp | str | None,
    trade_end: pd.Timestamp | str | None,
) -> tuple[int, int]:
    index = frame.index
    mask = pd.Series(True, index=index)
    if trade_start is not None:
        mask &= index >= _as_utc_timestamp(trade_start)
    if trade_end is not None:
        mask &= index <= _as_utc_timestamp(trade_end)
    positions = np.flatnonzero(mask.to_numpy())
    if len(positions) == 0:
        raise ValueError("trade window has no rows")
    return int(positions[0]), int(positions[-1])


def _as_utc_timestamp(value: pd.Timestamp | str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def _atr_pct(frame: pd.DataFrame, window: int | None) -> pd.Series | None:
    if window is None:
        return None
    high = frame["high"] if "high" in frame else frame["mark_high"]
    low = frame["low"] if "low" in frame else frame["mark_low"]
    close = frame["close"]
    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(window, min_periods=window).mean()
    return (atr / close.replace(0.0, np.nan)).astype("float64")


def _trend_return(close: pd.Series, window: int | None) -> pd.Series | None:
    if window is None:
        return None
    return close.pct_change(window).astype("float64")


def _validate_config(config: CandleCountIntrabarBacktestConfig) -> None:
    if config.min_count <= 0:
        raise ValueError("min_count must be positive")
    if config.lookback <= 0:
        raise ValueError("lookback must be positive")
    if config.min_count > config.lookback:
        raise ValueError("min_count must be less than or equal to lookback")
    if config.allocation < 0.0:
        raise ValueError("allocation must be non-negative")
    if config.allocation_atr_window is not None and config.allocation_atr_window <= 0:
        raise ValueError("allocation_atr_window must be positive when configured")
    if config.target_atr_pct is not None and config.target_atr_pct <= 0.0:
        raise ValueError("target_atr_pct must be positive when configured")
    if config.stop_loss_pct <= 0.0:
        raise ValueError("stop_loss_pct must be positive")
    if config.stop_loss_atr_window is not None and config.stop_loss_atr_window <= 0:
        raise ValueError("stop_loss_atr_window must be positive when configured")
    if (
        config.stop_loss_atr_multiplier is not None
        and config.stop_loss_atr_multiplier <= 0.0
    ):
        raise ValueError("stop_loss_atr_multiplier must be positive when configured")
    if config.min_stop_loss_pct <= 0.0 or config.max_stop_loss_pct <= 0.0:
        raise ValueError("stop-loss bounds must be positive")
    if config.min_stop_loss_pct > config.max_stop_loss_pct:
        raise ValueError(
            "min_stop_loss_pct must be less than or equal to max_stop_loss_pct"
        )
    if config.take_profit_pct <= 0.0:
        raise ValueError("take_profit_pct must be positive")
    if config.take_profit_atr_window is not None and config.take_profit_atr_window <= 0:
        raise ValueError("take_profit_atr_window must be positive when configured")
    if (
        config.take_profit_atr_multiplier is not None
        and config.take_profit_atr_multiplier <= 0.0
    ):
        raise ValueError("take_profit_atr_multiplier must be positive when configured")
    if config.min_take_profit_pct <= 0.0 or config.max_take_profit_pct <= 0.0:
        raise ValueError("take-profit bounds must be positive")
    if config.min_take_profit_pct > config.max_take_profit_pct:
        raise ValueError(
            "min_take_profit_pct must be less than or equal to max_take_profit_pct"
        )
    if config.trend_window_bars is not None and config.trend_window_bars <= 0:
        raise ValueError("trend_window_bars must be positive when configured")
    if config.trend_block_pct is not None and config.trend_block_pct <= 0.0:
        raise ValueError("trend_block_pct must be positive when configured")
    if config.cooldown_bars < 0:
        raise ValueError("cooldown_bars must be non-negative")
    if config.opposite_signal_gap_bars < 0:
        raise ValueError("opposite_signal_gap_bars must be non-negative")
    if config.entry_mode not in {"always", "signal_start"}:
        raise ValueError("entry_mode must be one of: always, signal_start")
    if config.fee_rate < 0.0:
        raise ValueError("fee_rate must be non-negative")
    if config.slippage_rate < 0.0:
        raise ValueError("slippage_rate must be non-negative")
    if not 0.0 < config.stop_loss_risk_multiplier <= 1.0:
        raise ValueError("stop_loss_risk_multiplier must be in (0, 1]")
    if not 0.0 < config.min_risk_multiplier <= 1.0:
        raise ValueError("min_risk_multiplier must be in (0, 1]")


def _validate_input_frame(
    frame: pd.DataFrame, *, required_columns: tuple[str, ...]
) -> None:
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"missing columns for candle-count intrabar backtest: {missing}"
        )


def _intrabar_exit(
    *,
    direction: int,
    entry_price: float,
    mark_high: float,
    mark_low: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> tuple[float | None, Literal["stop", "take"] | None]:
    if direction > 0:
        stop_price = entry_price * (1.0 - stop_loss_pct)
        take_price = entry_price * (1.0 + take_profit_pct)
        if mark_low <= stop_price:
            return stop_price, "stop"
        if mark_high >= take_price:
            return take_price, "take"
    else:
        stop_price = entry_price * (1.0 + stop_loss_pct)
        take_price = entry_price * (1.0 - take_profit_pct)
        if mark_high >= stop_price:
            return stop_price, "stop"
        if mark_low <= take_price:
            return take_price, "take"
    return None, None


def _entry_allowed(
    signal: pd.Series,
    position: int,
    desired_direction: int,
    config: CandleCountIntrabarBacktestConfig,
) -> bool:
    if (
        config.entry_mode == "signal_start"
        and position > 0
        and int(signal.iloc[position - 1]) == desired_direction
    ):
        return False
    if config.opposite_signal_gap_bars == 0 or position == 0:
        return True
    start = max(0, position - config.opposite_signal_gap_bars)
    recent = signal.iloc[start:position]
    return not recent.eq(-desired_direction).any()


def _trend_filter_allows(
    trend_return: pd.Series | None,
    position: int,
    desired_direction: int,
    config: CandleCountIntrabarBacktestConfig,
) -> bool:
    if trend_return is None or config.trend_block_pct is None:
        return True
    value = trend_return.iloc[position]
    if pd.isna(value):
        return False
    if desired_direction < 0 and float(value) > config.trend_block_pct:
        return False
    if desired_direction > 0 and float(value) < -config.trend_block_pct:
        return False
    return True


def _entry_allocation(
    allocation_atr: pd.Series | None,
    position: int,
    config: CandleCountIntrabarBacktestConfig,
) -> float:
    if allocation_atr is None or config.target_atr_pct is None:
        return float(config.allocation)
    value = allocation_atr.iloc[position]
    if pd.isna(value) or float(value) <= 0.0:
        return 0.0
    return float(
        min(config.allocation, config.allocation * config.target_atr_pct / float(value))
    )


def _dynamic_pct(
    factor: pd.Series | None,
    position: int,
    *,
    fallback: float,
    multiplier: float | None,
    lower: float,
    upper: float,
) -> float:
    if factor is None or multiplier is None:
        return float(fallback)
    value = factor.iloc[position]
    if pd.isna(value) or float(value) <= 0.0:
        return 0.0
    return float(np.clip(float(value) * multiplier, lower, upper))


def _metrics(
    *,
    equity_curve: pd.Series,
    period_returns: pd.Series,
    entries: int,
    exits: int,
    stops: int,
    takes: int,
    trading_costs: float,
    funding_pnl: float,
    annualization_bars: int,
) -> dict[str, float]:
    cumulative_return = float(equity_curve.iloc[-1] - 1.0)
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    volatility = float(period_returns.std(ddof=0) * np.sqrt(annualization_bars))
    sharpe = 0.0
    if period_returns.std(ddof=0) > 0.0:
        sharpe = float(
            period_returns.mean()
            / period_returns.std(ddof=0)
            * np.sqrt(annualization_bars)
        )
    return {
        "cumulative_return": cumulative_return,
        "max_drawdown": float(drawdown.min()),
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "entries": float(entries),
        "exits": float(exits),
        "stops": float(stops),
        "takes": float(takes),
        "trading_costs": float(trading_costs),
        "funding_pnl": float(funding_pnl),
    }
