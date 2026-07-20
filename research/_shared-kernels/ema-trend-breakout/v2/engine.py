from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


V1_SHA256 = "4ce1923e5ef3e5d6f43d22304266f18155ba51da3628b63e8b8a749947101e32"
V1_PATH = Path(__file__).resolve().parents[1] / "v1/engine.py"


def _load_frozen_v1() -> Any:
    digest = hashlib.sha256(V1_PATH.read_bytes()).hexdigest()
    if digest != V1_SHA256:
        raise RuntimeError(
            f"ema-trend-breakout v1 SHA mismatch: expected {V1_SHA256}, got {digest}"
        )
    module_name = "ema_trend_breakout_frozen_v1"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, V1_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load frozen v1 kernel from {V1_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_V1 = _load_frozen_v1()

M15_PER_YEAR = _V1.M15_PER_YEAR
RECENT_WINDOWS = _V1.RECENT_WINDOWS
SignalFlags = _V1.SignalFlags
Position = _V1.Position
RunResult = _V1.RunResult
true_range = _V1.true_range
adx_di = _V1.adx_di
resample_ohlcv = _V1.resample_ohlcv
build_features = _V1.build_features
build_signals = _V1.build_signals
check_intrabar_exit = _V1.check_intrabar_exit
update_position_on_close = _V1.update_position_on_close
metrics_from_series = _V1.metrics_from_series
slice_metrics = _V1.slice_metrics
open_position_summary = _V1.open_position_summary
trade_signatures = _V1.trade_signatures
parity_report = _V1.parity_report
config_dict = _V1.config_dict
pct = _V1.pct


@dataclass(frozen=True, slots=True)
class V35Config(_V1.V35Config):
    """V2 adds an explicit sizing mode and explicit-cost stress multipliers."""

    sizing_mode: str = "atr_risk"
    fixed_allocation: float = 1.0
    fee_multiplier: float = 1.0
    slippage_multiplier: float = 1.0

    def validate(self) -> None:
        _V1.V35Config.validate(self)
        if self.sizing_mode not in {"atr_risk", "fixed"}:
            raise ValueError("sizing_mode must be 'atr_risk' or 'fixed'")
        if self.fixed_allocation <= 0.0:
            raise ValueError("fixed_allocation must be positive")
        if (
            self.sizing_mode == "fixed"
            and self.fixed_allocation > self.max_allocation
        ):
            raise ValueError(
                "fixed_allocation cannot exceed max_allocation in fixed mode"
            )
        if self.fee_multiplier < 0.0 or self.slippage_multiplier < 0.0:
            raise ValueError("cost stress multipliers must be non-negative")


def v39_2_config(**changes: Any) -> V35Config:
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


def effective_fee_per_fill(config: V35Config) -> float:
    """Return the fee deduction used per filled allocation."""

    config.validate()
    if config.cost_mode == "legacy_cost":
        return config.trade_cost_rate
    return config.fee_per_fill * config.fee_multiplier


def effective_slippage_per_fill(config: V35Config) -> float:
    """Return adverse price slippage; legacy combined-cost mode has none."""

    config.validate()
    if config.cost_mode == "legacy_cost":
        return 0.0
    return config.adverse_slippage_per_fill * config.slippage_multiplier


def explicit_cost_stress(config: V35Config) -> dict[str, float]:
    """Expose effective explicit costs for search metadata and audit output."""

    if config.cost_mode != "explicit":
        raise ValueError("explicit_cost_stress requires cost_mode='explicit'")
    return {
        "fee_per_fill": config.fee_per_fill,
        "fee_multiplier": config.fee_multiplier,
        "effective_fee_per_fill": effective_fee_per_fill(config),
        "adverse_slippage_per_fill": config.adverse_slippage_per_fill,
        "slippage_multiplier": config.slippage_multiplier,
        "effective_adverse_slippage_per_fill": effective_slippage_per_fill(
            config
        ),
    }


def allocation_for_entry(
    *,
    direction: int,
    entry_atr: float,
    entry_price: float,
    config: V35Config,
) -> float:
    """Calculate allocation without conflating fixed sizing with ATR targets."""

    config.validate()
    if direction not in {-1, 1}:
        raise ValueError("direction must be -1 or 1")
    if not np.isfinite(entry_atr) or entry_atr <= 0.0:
        raise ValueError("entry_atr must be finite and positive")
    if not np.isfinite(entry_price) or entry_price <= 0.0:
        raise ValueError("entry_price must be finite and positive")
    if config.sizing_mode == "fixed":
        return float(config.fixed_allocation)
    target = (
        config.long_target_atr_pct
        if direction == 1
        else config.short_target_atr_pct
    )
    return float(
        min(
            config.max_allocation,
            target / (entry_atr / entry_price),
        )
    )


def _fill_price(
    raw_price: float,
    direction: int,
    *,
    is_entry: bool,
    config: V35Config,
) -> float:
    slippage = effective_slippage_per_fill(config)
    sign = direction if is_entry else -direction
    return raw_price * (1.0 + sign * slippage)


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
    cost = effective_fee_per_fill(config) * position.allocation
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
    """Run V35/V39.2 with independent ATR-risk or fixed allocation sizing."""

    config.validate()
    market = _V1._indexed_market(frame)
    if not market.index.equals(features.index):
        raise ValueError("market and feature indices must match exactly")
    required = {"atr", "adx", "long_signal", "short_signal"}
    missing = sorted(required.difference(features.columns))
    if missing:
        raise ValueError(f"feature frame missing backtest columns: {missing}")
    aligned_funding = _V1._aligned_funding(funding, market.index)
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
            direction = (
                1
                if long_signal and not short_signal
                else -1
                if short_signal and not long_signal
                else 0
            )
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
                allocation = allocation_for_entry(
                    direction=direction,
                    entry_atr=entry_atr,
                    entry_price=entry_price,
                    config=config,
                )
                cost = effective_fee_per_fill(config) * allocation
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
