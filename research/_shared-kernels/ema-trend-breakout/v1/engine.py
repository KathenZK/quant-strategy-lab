from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any

import numpy as np
import pandas as pd


M15_PER_YEAR = 365 * 24 * 4
RECENT_WINDOWS = {
    "1d": pd.Timedelta(days=1),
    "7d": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "3m": pd.Timedelta(days=90),
    "6m": pd.Timedelta(days=182),
    "1y": pd.Timedelta(days=365),
}


@dataclass(frozen=True, slots=True)
class V35Config:
    """Symbol-neutral configuration for the V35/V39.2 EMA trend-breakout state machine.

    ``legacy_cost`` deducts one combined rate per filled allocation and is the
    exact historical HYPE accounting contract. ``explicit`` deducts the fee and
    moves every execution price adversely by ``adverse_slippage_per_fill``.

    ``gap_open`` fills a stop crossed at the open at that worse open.
    ``legacy_exact`` preserves the historical HYPE stale-stop fill for parity.
    """

    long_target_atr_pct: float = 0.020
    short_target_atr_pct: float = 0.018
    max_allocation: float = 3.0
    ema_fast: int = 96
    ema_slow: int = 384
    adx_window: int = 28
    volume_window: int = 192
    atr_window: int = 672
    h1_adx_window: int = 21
    h1_ema_fast: int = 24
    h1_ema_slow: int = 96
    warmup_bars: int = 1600
    long_adx_min: float = 28.0
    short_adx_min: float = 36.0
    long_vol_min: float = 0.25
    short_vol_min: float = 0.50
    h1_long_adx_min: float = 18.0
    entry_delay_bars: int = 2
    take_profit_atr: float = 5.0
    hard_stop_atr: float = 7.0
    adx_exit: float = 22.0
    delayed_bars: int = 3
    disable_after_mfe_atr: float = 1.5
    max_hold_bars: int = 384
    cooldown_bars: int = 0
    cost_mode: str = "legacy_cost"
    trade_cost_rate: float = 0.00085
    fee_per_fill: float = 0.001
    adverse_slippage_per_fill: float = 0.0004
    execution_mode: str = "gap_open"

    def validate(self) -> None:
        positive_windows = (
            self.ema_fast,
            self.ema_slow,
            self.adx_window,
            self.volume_window,
            self.atr_window,
            self.h1_adx_window,
            self.h1_ema_fast,
            self.h1_ema_slow,
            self.entry_delay_bars,
            self.delayed_bars,
            self.max_hold_bars,
        )
        if any(value <= 0 for value in positive_windows):
            raise ValueError("indicator, delay, and hold windows must be positive")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be less than ema_slow")
        if self.h1_ema_fast >= self.h1_ema_slow:
            raise ValueError("h1_ema_fast must be less than h1_ema_slow")
        if self.cooldown_bars < 0 or self.warmup_bars < 0:
            raise ValueError("warmup_bars and cooldown_bars must be non-negative")
        if self.max_allocation <= 0.0:
            raise ValueError("max_allocation must be positive")
        if self.cost_mode not in {"legacy_cost", "explicit"}:
            raise ValueError("cost_mode must be 'legacy_cost' or 'explicit'")
        if self.execution_mode not in {"gap_open", "legacy_exact"}:
            raise ValueError("execution_mode must be 'gap_open' or 'legacy_exact'")
        if min(
            self.trade_cost_rate,
            self.fee_per_fill,
            self.adverse_slippage_per_fill,
        ) < 0.0:
            raise ValueError("cost rates must be non-negative")


@dataclass(frozen=True, slots=True)
class SignalFlags:
    """Structural signal switches; defaults reproduce the original V35 signal."""

    long_use_ema_spread: bool = True
    long_use_h1_di: bool = True
    short_use_ema_spread: bool = True
    short_use_h1_ema: bool = True
    allow_long: bool = True
    allow_short: bool = True


@dataclass(slots=True)
class Position:
    direction: int
    entry_bar: int
    entry_ts: pd.Timestamp
    entry_price: float
    entry_atr: float
    allocation: float
    entry_equity: float
    previous_price: float
    mfe_atr: float = 0.0
    weak_bars: int = 0


@dataclass(frozen=True, slots=True)
class RunResult:
    name: str
    metrics: dict[str, Any]
    slices: list[dict[str, Any]]
    trades: pd.DataFrame
    equity_curve: pd.Series
    period_returns: pd.Series
    open_position: dict[str, Any] | None


def v39_2_config(**changes: Any) -> V35Config:
    """Return the V39.2/V40 parameter identity, with optional explicit overrides."""

    config = replace(
        V35Config(),
        short_target_atr_pct=0.022,
        long_vol_min=0.25,
        cooldown_bars=1,
    )
    return replace(config, **changes) if changes else config


def v39_2_flags() -> SignalFlags:
    return SignalFlags(short_use_h1_ema=False)


def v40_config(**changes: Any) -> V35Config:
    return v39_2_config(**changes)


def v40_flags() -> SignalFlags:
    return v39_2_flags()


def _indexed_market(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"market frame missing columns: {missing}")
    result = frame.copy()
    if "ts" in result.columns:
        result["ts"] = pd.to_datetime(result["ts"], utc=True)
        result = result.set_index("ts")
    elif not isinstance(result.index, pd.DatetimeIndex):
        raise ValueError("market frame must have a UTC DatetimeIndex or ts column")
    result.index = pd.to_datetime(result.index, utc=True)
    if result.index.has_duplicates:
        raise ValueError("market frame contains duplicate timestamps")
    if not result.index.is_monotonic_increasing:
        raise ValueError("market frame timestamps must be increasing")
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    if result[list(required)].isna().any().any():
        raise ValueError("market frame contains null/non-numeric OHLCV values")
    if (result[["open", "high", "low", "close"]] <= 0.0).any().any():
        raise ValueError("market frame contains non-positive OHLC values")
    invalid = (
        result["high"].lt(result[["open", "close", "low"]].max(axis=1))
        | result["low"].gt(result[["open", "close", "high"]].min(axis=1))
        | result["volume"].lt(0.0)
    )
    if bool(invalid.any()):
        raise ValueError("market frame contains invalid OHLCV rows")
    return result


def true_range(frame: pd.DataFrame) -> pd.Series:
    previous_close = frame["close"].shift(1)
    return pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def adx_di(
    frame: pd.DataFrame,
    window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tr = true_range(frame)
    up_move = frame["high"].diff()
    down_move = -frame["low"].diff()
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0.0), up_move, 0.0),
        index=frame.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0.0), down_move, 0.0),
        index=frame.index,
    )
    alpha = 1.0 / window
    atr_wilder = tr.ewm(
        alpha=alpha,
        adjust=False,
        min_periods=window,
    ).mean()
    plus_di = (
        100.0
        * plus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
        / atr_wilder
    )
    minus_di = (
        100.0
        * minus_dm.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
        / atr_wilder
    )
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    adx = dx.ewm(alpha=alpha, adjust=False, min_periods=window).mean()
    return adx, plus_di, minus_di


def resample_ohlcv(frame: pd.DataFrame, rule: str = "1h") -> pd.DataFrame:
    return (
        frame[["open", "high", "low", "close", "volume"]]
        .resample(rule, label="left", closed="left")
        .agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }
        )
        .dropna(subset=["open", "high", "low", "close"])
    )


def build_features(frame: pd.DataFrame, config: V35Config) -> pd.DataFrame:
    """Build causal 15m and prior-completed-1h features.

    ATR672 is an arithmetic rolling mean of true range. ADX/DI uses Wilder
    EWMA with alpha=1/window and min_periods=window. The 1h aggregate is shifted
    by one complete 1h bin before being forward-filled onto the base index.
    """

    config.validate()
    features = _indexed_market(frame)
    features["atr"] = true_range(features).rolling(
        config.atr_window,
        min_periods=config.atr_window,
    ).mean()
    features["ema_fast"] = features["close"].ewm(
        span=config.ema_fast,
        adjust=False,
        min_periods=config.ema_fast,
    ).mean()
    features["ema_slow"] = features["close"].ewm(
        span=config.ema_slow,
        adjust=False,
        min_periods=config.ema_slow,
    ).mean()
    features["ema_spread"] = features["ema_fast"] / features["ema_slow"] - 1.0
    features["adx"], features["plus_di"], features["minus_di"] = adx_di(
        features,
        config.adx_window,
    )
    volume_mean = features["volume"].rolling(
        config.volume_window,
        min_periods=config.volume_window,
    ).mean()
    features["volume_surge"] = features["volume"] / volume_mean - 1.0

    h1 = resample_ohlcv(features, "1h")
    h1_adx, h1_plus_di, h1_minus_di = adx_di(h1, config.h1_adx_window)
    h1_ema_fast = h1["close"].ewm(
        span=config.h1_ema_fast,
        adjust=False,
        min_periods=config.h1_ema_fast,
    ).mean()
    h1_ema_slow = h1["close"].ewm(
        span=config.h1_ema_slow,
        adjust=False,
        min_periods=config.h1_ema_slow,
    ).mean()
    h1_features = pd.DataFrame(
        {
            "h1_adx": h1_adx,
            "h1_plus_di": h1_plus_di,
            "h1_minus_di": h1_minus_di,
            "h1_ema_spread": h1_ema_fast / h1_ema_slow - 1.0,
        },
        index=h1.index,
    ).shift(1)
    return features.join(h1_features.reindex(features.index, method="ffill"))


def build_signals(
    features: pd.DataFrame,
    config: V35Config,
    flags: SignalFlags | None = None,
) -> pd.DataFrame:
    config.validate()
    selected = flags or SignalFlags()
    out = features.copy()
    required = {
        "ema_spread",
        "adx",
        "volume_surge",
        "h1_adx",
        "h1_plus_di",
        "h1_minus_di",
        "h1_ema_spread",
    }
    missing = sorted(required.difference(out.columns))
    if missing:
        raise ValueError(f"feature frame missing signal columns: {missing}")

    long_signal = (
        out["adx"].ge(config.long_adx_min)
        & out["volume_surge"].ge(config.long_vol_min)
        & out["h1_adx"].gt(config.h1_long_adx_min)
    )
    if selected.long_use_ema_spread:
        long_signal &= out["ema_spread"].gt(0.0)
    if selected.long_use_h1_di:
        long_signal &= out["h1_plus_di"].gt(out["h1_minus_di"])

    short_signal = (
        out["adx"].ge(config.short_adx_min)
        & out["volume_surge"].ge(config.short_vol_min)
    )
    if selected.short_use_ema_spread:
        short_signal &= out["ema_spread"].lt(0.0)
    if selected.short_use_h1_ema:
        short_signal &= out["h1_ema_spread"].lt(0.0)
    if not selected.allow_long:
        long_signal &= False
    if not selected.allow_short:
        short_signal &= False
    conflict = long_signal & short_signal
    out["long_signal"] = long_signal & ~conflict
    out["short_signal"] = short_signal & ~conflict
    return out


def _aligned_funding(
    funding: pd.Series | pd.DataFrame | None,
    index: pd.DatetimeIndex,
) -> pd.Series:
    if funding is None:
        return pd.Series(0.0, index=index, name="funding_rate")
    if isinstance(funding, pd.DataFrame):
        if "funding_rate" not in funding.columns:
            raise ValueError("funding frame missing funding_rate")
        values = funding.copy()
        if "ts" in values.columns:
            values["ts"] = pd.to_datetime(values["ts"], utc=True).dt.floor("15min")
            series = values.set_index("ts")["funding_rate"]
        elif isinstance(values.index, pd.DatetimeIndex):
            series = values["funding_rate"]
        else:
            raise ValueError("funding frame must have a DatetimeIndex or ts column")
    else:
        series = funding.copy()
    series.index = pd.to_datetime(series.index, utc=True).floor("15min")
    series = pd.to_numeric(series, errors="coerce")
    if series.isna().any():
        raise ValueError("funding contains null/non-numeric rates")
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.reindex(index).fillna(0.0).rename("funding_rate")


def _fill_price(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    config: V35Config,
) -> float:
    if config.cost_mode == "legacy_cost":
        return raw_price
    sign = direction if is_entry else -direction
    return raw_price * (1.0 + sign * config.adverse_slippage_per_fill)


def _fee_rate(config: V35Config) -> float:
    return (
        config.trade_cost_rate
        if config.cost_mode == "legacy_cost"
        else config.fee_per_fill
    )


def check_intrabar_exit(
    *,
    position: Position,
    open_price: float,
    high: float,
    low: float,
    config: V35Config,
) -> tuple[str, float] | None:
    """Return stop-first bracket exit using raw (pre-cost) execution price."""

    take = (
        position.entry_price
        + position.direction * config.take_profit_atr * position.entry_atr
    )
    stop = (
        position.entry_price
        - position.direction * config.hard_stop_atr * position.entry_atr
    )
    if position.direction == 1:
        if low <= stop:
            raw_exit = (
                min(open_price, stop)
                if config.execution_mode == "gap_open"
                else stop
            )
            return "stop_loss", raw_exit
        if high >= take:
            return "take_profit", take
    else:
        if high >= stop:
            raw_exit = (
                max(open_price, stop)
                if config.execution_mode == "gap_open"
                else stop
            )
            return "stop_loss", raw_exit
        if low <= take:
            return "take_profit", take
    return None


def update_position_on_close(
    position: Position,
    high: float,
    low: float,
) -> None:
    excursion = (
        (high - position.entry_price) / position.entry_atr
        if position.direction == 1
        else (position.entry_price - low) / position.entry_atr
    )
    position.mfe_atr = max(position.mfe_atr, float(excursion))


def close_position(
    *,
    equity: float,
    position: Position,
    raw_exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: V35Config,
) -> tuple[float, float]:
    exit_price = _fill_price(
        raw_exit_price,
        position.direction,
        is_entry=False,
        config=config,
    )
    pnl = (
        position.direction
        * position.allocation
        * (exit_price / position.previous_price - 1.0)
    )
    cost = _fee_rate(config) * position.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    raw_price_return = (
        position.direction * (exit_price / position.entry_price - 1.0)
    )
    trades.append(
        {
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": position.allocation,
            "mfe_atr": position.mfe_atr,
            "exit_reason": reason,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "raw_price_return": raw_price_return,
            "trade_return": exit_equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": exit_equity,
        }
    )
    return exit_equity, cost


def run_backtest(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series | pd.DataFrame | None,
    features: pd.DataFrame,
    config: V35Config,
) -> RunResult:
    """Run the K0-close/K1-wait/K2-open single-position state machine."""

    config.validate()
    market = _indexed_market(frame)
    if not market.index.equals(features.index):
        raise ValueError("market and feature indices must match exactly")
    required = {"atr", "adx", "long_signal", "short_signal"}
    missing = sorted(required.difference(features.columns))
    if missing:
        raise ValueError(f"feature frame missing backtest columns: {missing}")
    aligned_funding = _aligned_funding(funding, market.index)
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    if start >= len(market):
        raise ValueError("market does not contain enough rows after warmup")

    equity = 1.0
    position: Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0

    for i in range(start, len(market)):
        start_equity = equity
        ts = pd.Timestamp(market.index[i])
        open_price = float(market["open"].iloc[i])
        high = float(market["high"].iloc[i])
        low = float(market["low"].iloc[i])
        close = float(market["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = close_position(
                equity=equity,
                position=position,
                raw_exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            exited_this_bar = True

        if position is not None:
            funding_pnl = (
                -position.direction
                * position.allocation
                * float(aligned_funding.iloc[i])
            )
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        cooldown_complete = i > last_exit_bar + config.cooldown_bars
        if position is None and not exited_this_bar and cooldown_complete:
            signal_i = i - config.entry_delay_bars
            long_signal = bool(features["long_signal"].iloc[signal_i])
            short_signal = bool(features["short_signal"].iloc[signal_i])
            direction = 1 if long_signal and not short_signal else -1 if short_signal and not long_signal else 0
            entry_atr = float(features["atr"].iloc[i - 1])
            if (
                direction != 0
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                entry_price = _fill_price(
                    open_price,
                    direction,
                    is_entry=True,
                    config=config,
                )
                target = (
                    config.long_target_atr_pct
                    if direction == 1
                    else config.short_target_atr_pct
                )
                allocation = min(
                    config.max_allocation,
                    target / (entry_atr / entry_price),
                )
                cost = _fee_rate(config) * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=entry_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=entry_price,
                )

        if position is not None:
            intrabar = check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
            )
            if intrabar is not None:
                reason, raw_exit_price = intrabar
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    raw_exit_price=raw_exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                pnl = (
                    position.direction
                    * position.allocation
                    * (close / position.previous_price - 1.0)
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                update_position_on_close(position, high, low)
                can_indicator_exit = (
                    position.mfe_atr < config.disable_after_mfe_atr
                )
                if (
                    can_indicator_exit
                    and float(features["adx"].iloc[i]) < config.adx_exit
                ):
                    position.weak_bars += 1
                else:
                    position.weak_bars = 0
                if (
                    can_indicator_exit
                    and position.weak_bars >= config.delayed_bars
                ):
                    pending_exit = "indicator_exit"
                if (
                    pending_exit is None
                    and i - position.entry_bar >= config.max_hold_bars
                ):
                    pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(
            0.0
            if position is None
            else position.direction * position.allocation
        )

    index = market.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=name)
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    return RunResult(
        name=name,
        metrics=metrics,
        slices=slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=(
            open_position_summary(position, market.index[-1])
            if position is not None
            else None
        ),
    )


def metrics_from_series(
    *,
    equity_curve: pd.Series,
    returns: pd.Series,
    weights: pd.Series,
    trades: pd.DataFrame,
    trading_costs: float,
    funding_pnl: float,
) -> dict[str, Any]:
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    volatility = float(returns.std(ddof=0))
    exit_counts = (
        trades["exit_reason"].value_counts().to_dict()
        if not trades.empty
        else {}
    )
    wins = int(trades["trade_return"].gt(0.0).sum()) if not trades.empty else 0
    return {
        "start": equity_curve.index.min().isoformat(),
        "end": equity_curve.index.max().isoformat(),
        "bars": int(len(equity_curve)),
        "return_pct": pct(float(equity_curve.iloc[-1] - 1.0)),
        "max_drawdown_pct": pct(float(drawdown.min())),
        "sharpe": round(
            float(
                0.0
                if volatility == 0.0
                else returns.mean() / volatility * math.sqrt(M15_PER_YEAR)
            ),
            2,
        ),
        "trades": int(len(trades)),
        "wins": wins,
        "win_rate_pct": pct(wins / len(trades)) if len(trades) else 0.0,
        "long_trades": (
            int(trades["direction"].eq(1).sum()) if not trades.empty else 0
        ),
        "short_trades": (
            int(trades["direction"].eq(-1).sum()) if not trades.empty else 0
        ),
        "exit_counts": {str(key): int(value) for key, value in exit_counts.items()},
        "avg_abs_allocation": round(float(weights.abs().mean()), 4),
        "max_abs_allocation": round(float(weights.abs().max()), 4),
        "trading_costs_pct": pct(trading_costs),
        "funding_pnl_pct": pct(funding_pnl),
    }


def slice_metrics(
    equity_curve: pd.Series,
    trades: pd.DataFrame,
) -> list[dict[str, Any]]:
    end = equity_curve.index.max()
    windows: dict[str, pd.Timedelta | None] = {**RECENT_WINDOWS, "full": None}
    rows: list[dict[str, Any]] = []
    for label, delta in windows.items():
        start = equity_curve.index.min() if delta is None else end - delta
        sliced = equity_curve.loc[equity_curve.index >= start]
        if sliced.empty:
            continue
        normalized = sliced / float(sliced.iloc[0])
        drawdown = normalized / normalized.cummax() - 1.0
        trade_count = (
            0
            if trades.empty
            else int(
                pd.to_datetime(trades["exit_ts"], utc=True)
                .ge(sliced.index.min())
                .sum()
            )
        )
        rows.append(
            {
                "window": label,
                "start": sliced.index.min().isoformat(),
                "end": sliced.index.max().isoformat(),
                "return_pct": pct(float(normalized.iloc[-1] - 1.0)),
                "max_drawdown_pct": pct(float(drawdown.min())),
                "closed_trades": trade_count,
            }
        )
    return rows


def open_position_summary(
    position: Position,
    data_end: pd.Timestamp,
) -> dict[str, Any]:
    return {
        "data_end": pd.Timestamp(data_end).isoformat(),
        "direction": position.direction,
        "entry_ts": position.entry_ts.isoformat(),
        "entry_price": position.entry_price,
        "entry_atr": position.entry_atr,
        "allocation": position.allocation,
        "mfe_atr": position.mfe_atr,
        "weak_bars": position.weak_bars,
    }


def trade_signatures(trades: pd.DataFrame) -> list[tuple[Any, ...]]:
    """Stable path signature used by migration/parity checks."""

    if trades.empty:
        return []
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "entry_atr",
        "allocation",
        "exit_reason",
        "entry_bar",
        "exit_bar",
    ]
    missing = sorted(set(columns).difference(trades.columns))
    if missing:
        raise ValueError(f"trade frame missing signature columns: {missing}")
    rows: list[tuple[Any, ...]] = []
    for row in trades[columns].itertuples(index=False, name=None):
        rows.append(
            (
                pd.Timestamp(row[0]).isoformat(),
                pd.Timestamp(row[1]).isoformat(),
                int(row[2]),
                float(row[3]),
                float(row[4]),
                float(row[5]),
                float(row[6]),
                str(row[7]),
                int(row[8]),
                int(row[9]),
            )
        )
    return rows


def parity_report(
    *,
    reference_features: pd.DataFrame,
    candidate_features: pd.DataFrame,
    reference_run: Any,
    candidate_run: RunResult,
) -> dict[str, Any]:
    """Compare signal bars, trade path, and equity without writing artifacts."""

    signal_columns = ["long_signal", "short_signal"]
    signal_equal = (
        reference_features[signal_columns]
        .astype(bool)
        .equals(candidate_features[signal_columns].astype(bool))
    )
    reference_signature = trade_signatures(reference_run.trades)
    candidate_signature = trade_signatures(candidate_run.trades)
    aligned = pd.concat(
        [
            reference_run.equity_curve.rename("reference"),
            candidate_run.equity_curve.rename("candidate"),
        ],
        axis=1,
    )
    max_equity_diff = float(
        (aligned["reference"] - aligned["candidate"]).abs().max()
    )
    return {
        "signal_equal": signal_equal,
        "reference_trades": len(reference_signature),
        "candidate_trades": len(candidate_signature),
        "trade_signatures_equal": reference_signature == candidate_signature,
        "max_equity_diff": max_equity_diff,
        "exact": bool(
            signal_equal
            and reference_signature == candidate_signature
            and max_equity_diff == 0.0
        ),
    }


def config_dict(config: V35Config) -> dict[str, Any]:
    return asdict(config)


def pct(value: float) -> float:
    return round(float(value) * 100.0, 2)
