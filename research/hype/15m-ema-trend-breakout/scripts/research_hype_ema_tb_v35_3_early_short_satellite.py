"""回测 V35.3 空头趋势转折卫星仓与 ADX36 确认加仓。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_early_short_satellite_2026-07-22"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
FREEZE_DATA_END = pd.Timestamp("2026-06-01T03:00:00Z")
CURRENT_WINDOW_START = pd.Timestamp("2026-07-22T04:00:00Z")
PROFIT_TRIGGER_ATR = 4.4
PROFIT_FRACTION = 0.75


@dataclass(frozen=True, slots=True)
class EarlySpec:
    name: str
    enabled: bool
    satellite_fraction: float = 0.25
    satellite_stop_atr: float = 2.0
    confirmation_window_bars: int = 4
    adx_min: float = 30.0
    adx_delta3_min: float = 1.0
    di_ratio_min: float = 2.0
    volume_multiple_min: float = 3.0
    breakout_lookback: int = 20
    ema_expand_bars: int = 3


SPECS = (
    EarlySpec("custom_v35_3_control", enabled=False),
    EarlySpec("early_short_primary", enabled=True),
    EarlySpec(
        "early_short_stop1_5",
        enabled=True,
        satellite_stop_atr=1.5,
    ),
    EarlySpec(
        "early_short_stop2_5",
        enabled=True,
        satellite_stop_atr=2.5,
    ),
    EarlySpec(
        "early_short_window2",
        enabled=True,
        confirmation_window_bars=2,
    ),
    EarlySpec(
        "early_short_window6",
        enabled=True,
        confirmation_window_bars=6,
    ),
    EarlySpec(
        "early_short_fraction12_5",
        enabled=True,
        satellite_fraction=0.125,
    ),
    EarlySpec(
        "early_short_fraction50",
        enabled=True,
        satellite_fraction=0.50,
    ),
)


@dataclass(slots=True)
class StageState:
    mode: str = "base"
    initial_allocation: float = 0.0
    satellite_allocation: float = 0.0
    satellite_entry_bar: int | None = None
    satellite_entry_ts: pd.Timestamp | None = None
    satellite_entry_price: float | None = None
    satellite_entry_atr: float | None = None
    early_signal_bar: int | None = None
    early_signal_ts: pd.Timestamp | None = None
    confirmation_signal_bar: int | None = None
    confirmation_signal_ts: pd.Timestamp | None = None
    pending_add_bar: int | None = None
    add_bar: int | None = None
    add_ts: pd.Timestamp | None = None
    add_price: float | None = None
    add_allocation: float = 0.0
    full_entry_bar: int | None = None
    partial: stop_engine.PartialState = field(
        default_factory=stop_engine.PartialState
    )


def v35_3_stop_spec(name: str) -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        directional_stop_replaces_hard_stop=True,
    )


def build_early_signal(
    *,
    frame: pd.DataFrame,
    features: pd.DataFrame,
    base_signals: pd.DataFrame,
    spec: EarlySpec,
) -> tuple[pd.Series, dict[str, Any]]:
    if not spec.enabled:
        signal = pd.Series(False, index=features.index)
        return signal, {"signal_bars": 0}

    ema_expanding = features["ema_spread"].lt(
        features["ema_spread"].shift(1)
    )
    for lag in range(1, spec.ema_expand_bars - 1):
        ema_expanding &= features["ema_spread"].shift(lag).lt(
            features["ema_spread"].shift(lag + 1)
        )
    adx_rising = features["adx"].gt(features["adx"].shift(1))
    adx_rising &= features["adx"].shift(1).gt(
        features["adx"].shift(2)
    )
    previous_low = (
        frame["low"]
        .rolling(spec.breakout_lookback)
        .min()
        .shift(1)
    )
    signal = (
        features["ema_spread"].lt(0.0)
        & ema_expanding
        & frame["close"].lt(previous_low)
        & features["minus_di"].gt(
            spec.di_ratio_min * features["plus_di"]
        )
        & features["adx"].ge(spec.adx_min)
        & adx_rising
        & features["adx"].sub(features["adx"].shift(3)).ge(
            spec.adx_delta3_min
        )
        & features["volume_surge"].ge(
            spec.volume_multiple_min - 1.0
        )
        & ~base_signals["short_signal"].astype(bool)
        & ~base_signals["long_signal"].astype(bool)
    )
    signal = signal.fillna(False)
    return signal, {
        "signal_bars": int(signal.sum()),
        "first_signal": (
            None
            if not signal.any()
            else pd.Timestamp(signal.index[signal][0]).isoformat()
        ),
        "last_signal": (
            None
            if not signal.any()
            else pd.Timestamp(signal.index[signal][-1]).isoformat()
        ),
    }


def planned_allocation(
    *,
    direction: int,
    open_price: float,
    entry_atr: float,
    config: base.V35Config,
) -> float:
    target = (
        config.long_target_atr_pct
        if direction == 1
        else config.short_target_atr_pct
    )
    return min(
        config.max_allocation,
        target / (entry_atr / open_price),
    )


def stop_market_fill(
    *,
    direction: int,
    open_price: float,
    stop_price: float,
) -> tuple[float, bool]:
    if direction == 1 and open_price < stop_price:
        return open_price, True
    if direction == -1 and open_price > stop_price:
        return open_price, True
    return stop_price, False


def close_position(
    *,
    equity: float,
    position: base.Position,
    stage: StageState,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    trades: list[dict[str, Any]],
    config: base.V35Config,
) -> tuple[float, float]:
    pnl = position.direction * position.allocation * (
        exit_price / position.previous_price - 1.0
    )
    cost = config.trade_cost_rate * position.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    trades.append(
        {
            "entry_ts": position.entry_ts,
            "exit_ts": exit_ts,
            "direction": position.direction,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "entry_atr": position.entry_atr,
            "allocation": stage.initial_allocation,
            "remaining_allocation_at_exit": position.allocation,
            "mfe_atr": position.mfe_atr,
            "exit_reason": reason,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "raw_price_return": position.direction
            * (exit_price / position.entry_price - 1.0),
            "trade_return": exit_equity / position.entry_equity - 1.0,
            "entry_equity": position.entry_equity,
            "exit_equity": exit_equity,
            "stage_mode": stage.mode,
            "satellite_allocation": stage.satellite_allocation,
            "satellite_entry_bar": stage.satellite_entry_bar,
            "satellite_entry_ts": stage.satellite_entry_ts,
            "satellite_entry_price": stage.satellite_entry_price,
            "satellite_entry_atr": stage.satellite_entry_atr,
            "early_signal_bar": stage.early_signal_bar,
            "early_signal_ts": stage.early_signal_ts,
            "confirmation_signal_bar": (
                stage.confirmation_signal_bar
            ),
            "confirmation_signal_ts": stage.confirmation_signal_ts,
            "add_bar": stage.add_bar,
            "add_ts": stage.add_ts,
            "add_price": stage.add_price,
            "add_allocation": stage.add_allocation,
            "profit_partial_taken": stage.partial.profit_taken,
            "profit_partial_ts": stage.partial.profit_ts,
            "profit_partial_price": stage.partial.profit_price,
            "profit_partial_allocation": (
                stage.partial.profit_allocation
            ),
        }
    )
    return exit_equity, cost


def enter_position(
    *,
    equity: float,
    direction: int,
    entry_bar: int,
    entry_ts: pd.Timestamp,
    entry_price: float,
    entry_atr: float,
    allocation: float,
    signal_bar: int,
    signal_ts: pd.Timestamp,
    satellite: bool,
    spec: EarlySpec,
    config: base.V35Config,
) -> tuple[float, float, base.Position, StageState]:
    cost = config.trade_cost_rate * allocation
    equity *= 1.0 - cost
    position = base.Position(
        direction=direction,
        entry_bar=entry_bar,
        entry_ts=entry_ts,
        entry_price=entry_price,
        entry_atr=entry_atr,
        allocation=allocation,
        entry_equity=equity,
        previous_price=entry_price,
    )
    if not satellite:
        return (
            equity,
            cost,
            position,
            StageState(
                mode="base",
                initial_allocation=allocation,
                full_entry_bar=entry_bar,
            ),
        )
    return (
        equity,
        cost,
        position,
        StageState(
            mode="satellite",
            initial_allocation=allocation,
            satellite_allocation=allocation,
            satellite_entry_bar=entry_bar,
            satellite_entry_ts=entry_ts,
            satellite_entry_price=entry_price,
            satellite_entry_atr=entry_atr,
            early_signal_bar=signal_bar,
            early_signal_ts=signal_ts,
        ),
    )


def add_confirmation_position(
    *,
    equity: float,
    position: base.Position,
    stage: StageState,
    open_price: float,
    entry_atr: float,
    bar_index: int,
    ts: pd.Timestamp,
    config: base.V35Config,
) -> tuple[float, float]:
    gap_pnl = position.direction * position.allocation * (
        open_price / position.previous_price - 1.0
    )
    equity *= 1.0 + gap_pnl
    position.previous_price = open_price
    planned_total = planned_allocation(
        direction=-1,
        open_price=open_price,
        entry_atr=entry_atr,
        config=config,
    )
    add_allocation = max(planned_total - position.allocation, 0.0)
    cost = config.trade_cost_rate * add_allocation
    equity *= 1.0 - cost
    if add_allocation > 0.0:
        combined_allocation = position.allocation + add_allocation
        weighted_entry_price = combined_allocation / (
            position.allocation / position.entry_price
            + add_allocation / open_price
        )
        position.entry_price = weighted_entry_price
        position.allocation = combined_allocation
    position.entry_atr = entry_atr
    position.previous_price = open_price
    position.mfe_atr = 0.0
    position.weak_bars = 0
    stage.mode = "confirmed"
    stage.initial_allocation = position.allocation
    stage.add_bar = bar_index
    stage.add_ts = ts
    stage.add_price = open_price
    stage.add_allocation = add_allocation
    stage.full_entry_bar = bar_index
    stage.pending_add_bar = None
    return equity, cost


def run_staged_backtest(
    *,
    spec: EarlySpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    base_signals: pd.DataFrame,
    early_signal: pd.Series,
    config: base.V35Config,
) -> tuple[base.RunResult, dict[str, Any]]:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    stage = StageState()
    pending_exit: str | None = None
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    early_entries = 0
    confirmed_entries = 0
    base_entries = 0
    profit_partial_events = 0
    gap_stop_events = 0
    no_floor = base.ProfitFloorConfig(enabled=False)

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            equity, cost = close_position(
                equity=equity,
                position=position,
                stage=stage,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            trading_costs += cost
            position = None
            stage = StageState()
            pending_exit = None
            exited_this_bar = True

        if position is not None:
            funding_pnl = (
                -position.direction
                * position.allocation
                * float(funding.iloc[i])
            )
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        if (
            position is not None
            and stage.mode == "satellite"
            and stage.pending_add_bar == i
        ):
            entry_atr = float(features["atr"].iloc[i - 1])
            if np.isfinite(entry_atr) and entry_atr > 0.0:
                equity, cost = add_confirmation_position(
                    equity=equity,
                    position=position,
                    stage=stage,
                    open_price=open_price,
                    entry_atr=entry_atr,
                    bar_index=i,
                    ts=ts,
                    config=config,
                )
                trading_costs += cost
                confirmed_entries += 1

        if position is None and not exited_this_bar:
            signal_i = i - config.entry_delay_bars
            long_signal = bool(
                base_signals["long_signal"].iloc[signal_i]
            )
            short_signal = bool(
                base_signals["short_signal"].iloc[signal_i]
            )
            early_short = bool(early_signal.iloc[signal_i])
            direction = 0
            satellite = False
            if long_signal and not short_signal:
                direction = 1
            elif short_signal and not long_signal:
                direction = -1
            elif early_short:
                direction = -1
                satellite = True
            entry_atr = float(features["atr"].iloc[i - 1])
            if (
                direction != 0
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                full_allocation = planned_allocation(
                    direction=direction,
                    open_price=open_price,
                    entry_atr=entry_atr,
                    config=config,
                )
                allocation = (
                    full_allocation * spec.satellite_fraction
                    if satellite
                    else full_allocation
                )
                equity, cost, position, stage = enter_position(
                    equity=equity,
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    signal_bar=signal_i,
                    signal_ts=pd.Timestamp(frame.index[signal_i]),
                    satellite=satellite,
                    spec=spec,
                    config=config,
                )
                trading_costs += cost
                if satellite:
                    early_entries += 1
                else:
                    base_entries += 1

        if position is not None and stage.mode == "satellite":
            stop_price = float(stage.satellite_entry_price) + (
                spec.satellite_stop_atr
                * float(stage.satellite_entry_atr)
            )
            if high >= stop_price:
                fill_price, gap_crossed = stop_market_fill(
                    direction=-1,
                    open_price=open_price,
                    stop_price=stop_price,
                )
                gap_stop_events += int(gap_crossed)
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    stage=stage,
                    exit_price=fill_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="satellite_stop",
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                stage = StageState()
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                base.update_position_on_close(
                    position,
                    high,
                    low,
                    config,
                    no_floor,
                )
                if (
                    stage.confirmation_signal_bar is None
                    and bool(base_signals["short_signal"].iloc[i])
                ):
                    stage.confirmation_signal_bar = i
                    stage.confirmation_signal_ts = ts
                    stage.pending_add_bar = (
                        i + config.entry_delay_bars
                    )
                completed_bars = (
                    i - int(stage.satellite_entry_bar) + 1
                )
                if (
                    stage.confirmation_signal_bar is None
                    and completed_bars
                    >= spec.confirmation_window_bars
                ):
                    pending_exit = "satellite_timeout"

        elif position is not None:
            hard_stop_atr = (
                6.75 if position.direction == 1 else 5.70
            )
            take_price = (
                position.entry_price
                + position.direction
                * config.take_profit_atr
                * position.entry_atr
            )
            hard_stop_price = (
                position.entry_price
                - position.direction
                * hard_stop_atr
                * position.entry_atr
            )
            profit_partial_price = (
                position.entry_price
                - PROFIT_TRIGGER_ATR * position.entry_atr
                if position.direction == -1
                else None
            )
            hard_stop_hit = (
                low <= hard_stop_price
                if position.direction == 1
                else high >= hard_stop_price
            )
            take_hit = (
                high >= take_price
                if position.direction == 1
                else low <= take_price
            )
            partial_hit = (
                position.direction == -1
                and not stage.partial.profit_taken
                and profit_partial_price is not None
                and low <= profit_partial_price
            )
            if hard_stop_hit:
                fill_price, gap_crossed = stop_market_fill(
                    direction=position.direction,
                    open_price=open_price,
                    stop_price=hard_stop_price,
                )
                gap_stop_events += int(gap_crossed)
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    stage=stage,
                    exit_price=fill_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="stop_loss",
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                stage = StageState()
                pending_exit = None
            else:
                if partial_hit:
                    equity, cost, allocation_closed = (
                        stop_engine.reduce_position(
                            equity=equity,
                            position=position,
                            fill_price=float(profit_partial_price),
                            fraction_of_remaining=PROFIT_FRACTION,
                            config=config,
                        )
                    )
                    trading_costs += cost
                    stage.partial.profit_taken = True
                    stage.partial.profit_ts = ts
                    stage.partial.profit_price = float(
                        profit_partial_price
                    )
                    stage.partial.profit_allocation = (
                        allocation_closed
                    )
                    profit_partial_events += 1

                if take_hit:
                    equity, cost = close_position(
                        equity=equity,
                        position=position,
                        stage=stage,
                        exit_price=take_price,
                        exit_ts=ts,
                        exit_bar=i,
                        reason="take_profit",
                        trades=trades,
                        config=config,
                    )
                    trading_costs += cost
                    position = None
                    stage = StageState()
                    pending_exit = None
                else:
                    pnl = position.direction * position.allocation * (
                        close / position.previous_price - 1.0
                    )
                    equity *= 1.0 + pnl
                    position.previous_price = close
                    base.update_position_on_close(
                        position,
                        high,
                        low,
                        config,
                        no_floor,
                    )
                    adx_is_weak = (
                        float(features["adx"].iloc[i])
                        < config.adx_exit
                    )
                    can_indicator_exit = (
                        position.mfe_atr
                        < config.disable_after_mfe_atr
                    )
                    position.weak_bars = (
                        position.weak_bars + 1
                        if can_indicator_exit and adx_is_weak
                        else 0
                    )
                    if (
                        can_indicator_exit
                        and position.weak_bars >= config.delayed_bars
                    ):
                        pending_exit = "indicator_exit"
                    hold_start = (
                        stage.full_entry_bar
                        if stage.full_entry_bar is not None
                        else position.entry_bar
                    )
                    if (
                        pending_exit is None
                        and i - hold_start >= config.max_hold_bars
                    ):
                        pending_exit = "timeout"

        equity_values.append(equity)
        period_returns.append(equity / start_equity - 1.0)
        weight_values.append(
            0.0
            if position is None
            else position.direction * position.allocation
        )

    index = frame.index[start:]
    equity_curve = pd.Series(
        equity_values,
        index=index,
        name=spec.name,
    )
    returns = pd.Series(
        period_returns,
        index=index,
        name=f"{spec.name}_return",
    )
    weights = pd.Series(
        weight_values,
        index=index,
        name=f"{spec.name}_weight",
    )
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    metrics["profit_partial_events"] = profit_partial_events
    metrics["early_entries"] = early_entries
    metrics["confirmed_entries"] = confirmed_entries
    metrics["base_entries"] = base_entries
    metrics["gap_stop_events"] = gap_stop_events
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(
            position,
            frame.index[-1],
        )
        open_position.update(
            {
                "stage_mode": stage.mode,
                "initial_allocation": stage.initial_allocation,
                "satellite_allocation": stage.satellite_allocation,
                "satellite_entry_ts": stage.satellite_entry_ts,
                "satellite_entry_price": stage.satellite_entry_price,
                "confirmation_signal_ts": (
                    stage.confirmation_signal_ts
                ),
                "pending_add_bar": stage.pending_add_bar,
                "add_ts": stage.add_ts,
                "add_price": stage.add_price,
                "add_allocation": stage.add_allocation,
                "profit_partial_taken": (
                    stage.partial.profit_taken
                ),
            }
        )
    run = base.RunResult(
        name=spec.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )
    audit = {
        "early_entries": early_entries,
        "confirmed_entries": confirmed_entries,
        "base_entries": base_entries,
        "satellite_stop_exits": int(
            trades_frame["exit_reason"].eq("satellite_stop").sum()
        ),
        "satellite_timeout_exits": int(
            trades_frame["exit_reason"].eq(
                "satellite_timeout"
            ).sum()
        ),
        "unconfirmed_satellite_exits": int(
            trades_frame["stage_mode"].eq("satellite").sum()
        ),
        "confirmed_trade_exits": int(
            trades_frame["stage_mode"].eq("confirmed").sum()
        ),
        "gap_stop_events": gap_stop_events,
    }
    return run, audit


def closed_trade_metrics(
    trades: pd.DataFrame,
    *,
    trade_cost_rate: float,
) -> dict[str, Any]:
    if trades.empty:
        return {
            "return_pct": 0.0,
            "trades": 0,
            "win_rate_pct": 0.0,
        }
    staged = trades["stage_mode"].isin(["satellite", "confirmed"])
    initial_fill_allocation = trades["allocation"].where(
        ~staged,
        trades["satellite_allocation"],
    )
    returns = (
        (1.0 + trades["trade_return"].astype(float))
        * (1.0 - trade_cost_rate * initial_fill_allocation)
        - 1.0
    )
    wins = int(returns.gt(0.0).sum())
    return {
        "return_pct": round(
            float((1.0 + returns).prod() - 1.0) * 100.0,
            4,
        ),
        "trades": int(len(trades)),
        "win_rate_pct": round(wins / len(trades) * 100.0, 2),
        "exit_counts": {
            str(key): int(value)
            for key, value in trades["exit_reason"].value_counts().items()
        },
    }


def parity_audit(
    official: base.RunResult,
    control: base.RunResult,
) -> dict[str, Any]:
    keys = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
    ]
    official_rows = official.trades[keys].reset_index(drop=True)
    control_rows = control.trades[keys].reset_index(drop=True)
    return {
        "official_metrics": official.metrics,
        "control_metrics": control.metrics,
        "trade_count_equal": len(official_rows) == len(control_rows),
        "exact_trade_rows_equal": official_rows.equals(control_rows),
        "max_equity_abs_diff": float(
            official.equity_curve.sub(control.equity_curve).abs().max()
        ),
    }


def path_audit(
    candidate: pd.DataFrame,
    control: pd.DataFrame,
) -> dict[str, Any]:
    keys = ["entry_ts", "direction"]
    shared = control[keys].merge(candidate[keys], on=keys)
    control_only = control.merge(
        candidate[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda rows: rows["_merge"].eq("left_only")]
    candidate_only = candidate.merge(
        control[keys],
        on=keys,
        how="left",
        indicator=True,
    ).loc[lambda rows: rows["_merge"].eq("left_only")]
    return {
        "shared_entries": int(len(shared)),
        "control_only_entries": int(len(control_only)),
        "candidate_only_entries": int(len(candidate_only)),
    }


def current_signal_rows(
    *,
    frame: pd.DataFrame,
    features: pd.DataFrame,
    base_signals: pd.DataFrame,
    early_signal: pd.Series,
    spec: EarlySpec,
) -> list[dict[str, Any]]:
    rows = features.loc[
        (features.index >= CURRENT_WINDOW_START) & early_signal,
        ["ema_spread", "adx", "plus_di", "minus_di", "volume_surge"],
    ].copy()
    previous_low = (
        frame["low"]
        .rolling(spec.breakout_lookback)
        .min()
        .shift(1)
    )
    rows["close"] = frame.loc[rows.index, "close"]
    rows["previous_20_low"] = previous_low.loc[rows.index]
    rows["adx_delta3"] = (
        features["adx"] - features["adx"].shift(3)
    ).loc[rows.index]
    rows["volume_multiple"] = rows["volume_surge"] + 1.0
    rows["planned_satellite_k2"] = (
        rows.index + pd.Timedelta(minutes=30)
    )
    rows["base_short_signal"] = base_signals.loc[
        rows.index,
        "short_signal",
    ]
    return json.loads(
        rows.to_json(orient="table", date_format="iso")
    )["data"]


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    features = base.build_features(frame, config)
    base_signals = signal_engine.build_signals(
        features,
        config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )
    official, official_audit = stop_engine.run_backtest(
        spec=v35_3_stop_spec("official_v35_3"),
        frame=frame,
        funding=funding,
        features=base_signals,
        config=config,
    )

    runs: list[base.RunResult] = []
    run_audits: dict[str, Any] = {}
    signal_audits: dict[str, Any] = {}
    signals: dict[str, pd.Series] = {}
    for spec in SPECS:
        early_signal, signal_audit = build_early_signal(
            frame=frame,
            features=features,
            base_signals=base_signals,
            spec=spec,
        )
        run, run_audit = run_staged_backtest(
            spec=spec,
            frame=frame,
            funding=funding,
            features=features,
            base_signals=base_signals,
            early_signal=early_signal,
            config=config,
        )
        runs.append(run)
        signals[spec.name] = early_signal
        signal_audits[spec.name] = signal_audit
        run_audits[spec.name] = run_audit

    control = runs[0]
    primary = runs[1]
    summary: dict[str, Any] = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "run_date": "2026-07-22",
        "status": "diagnostic_only_not_registered_not_promoted",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "custom_control_parity": parity_audit(
                official,
                control,
            ),
        },
        "assumptions": {
            "early_signal": (
                "EMA spread<0 and expands for 3 bars; close below the "
                "previous 20-bar low; -DI > 2*+DI; ADX28>=30, rises "
                "for 3 bars and delta3>=1; volume/MA192>=3; exclude "
                "bars already accepted by the normal V35.3 signal."
            ),
            "execution": (
                "Early K0 close signal, skip K1, open satellite at K2. "
                "A normal V35.3 short signal observed within the "
                "confirmation window schedules the add at its K2 open."
            ),
            "sizing": (
                "Primary opens 25% of the normal planned allocation. "
                "At confirmation, add up to the normal K2 planned total."
            ),
            "satellite_exit": (
                "Primary uses an entry-ATR 2.0 stop-market with "
                "gap-aware open fill. If no normal short signal appears "
                "within 4 completed bars, exit at the next open."
            ),
            "confirmed_exit": (
                "After add, use weighted entry price and the confirming "
                "K1 ATR; then V35.3 short MFE4.4 reduce75%, TP5/SL5.7."
            ),
            "costs": (
                "0.00085 per filled allocation plus Binance funding."
            ),
            "selection": (
                "Primary parameters came from the prior user-approved "
                "proposal. Stop 1.5/2.5, window 2/6, and fraction "
                "12.5%/50% are audit-only sensitivity variants."
            ),
        },
        "config": asdict(config),
        "specs": [asdict(spec) for spec in SPECS],
        "signal_audits": signal_audits,
        "run_audits": run_audits,
        "current_primary_signal_rows": current_signal_rows(
            frame=frame,
            features=features,
            base_signals=base_signals,
            early_signal=signals["early_short_primary"],
            spec=SPECS[1],
        ),
        "runs": [],
    }
    for spec, run in zip(SPECS, runs, strict=True):
        post_freeze = run.trades.loc[
            pd.to_datetime(run.trades["entry_ts"], utc=True).gt(
                FREEZE_DATA_END
            )
        ]
        early_trades = run.trades.loc[
            run.trades["stage_mode"].isin(
                ["satellite", "confirmed"]
            )
        ]
        unconfirmed_trades = run.trades.loc[
            run.trades["stage_mode"].eq("satellite")
        ]
        confirmed_trades = run.trades.loc[
            run.trades["stage_mode"].eq("confirmed")
        ]
        summary["runs"].append(
            {
                "spec": asdict(spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "post_freeze_closed_trade_metrics": (
                    closed_trade_metrics(
                        post_freeze,
                        trade_cost_rate=config.trade_cost_rate,
                    )
                ),
                "early_path_closed_trade_metrics": (
                    closed_trade_metrics(
                        early_trades,
                        trade_cost_rate=config.trade_cost_rate,
                    )
                ),
                "unconfirmed_satellite_metrics": (
                    closed_trade_metrics(
                        unconfirmed_trades,
                        trade_cost_rate=config.trade_cost_rate,
                    )
                ),
                "confirmed_satellite_metrics": (
                    closed_trade_metrics(
                        confirmed_trades,
                        trade_cost_rate=config.trade_cost_rate,
                    )
                ),
                "path_audit": path_audit(
                    run.trades,
                    control.trades,
                ),
                "open_position": run.open_position,
                "comparison_to_control": {
                    "return_delta_pp": round(
                        run.metrics["return_pct"]
                        - control.metrics["return_pct"],
                        2,
                    ),
                    "max_drawdown_delta_pp": round(
                        run.metrics["max_drawdown_pct"]
                        - control.metrics["max_drawdown_pct"],
                        2,
                    ),
                    "sharpe_delta": round(
                        run.metrics["sharpe"]
                        - control.metrics["sharpe"],
                        2,
                    ),
                    "trade_delta": int(
                        run.metrics["trades"]
                        - control.metrics["trades"]
                    ),
                },
            }
        )
    summary["primary_vs_control"] = {
        "return_delta_pp": round(
            primary.metrics["return_pct"]
            - control.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            primary.metrics["max_drawdown_pct"]
            - control.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            primary.metrics["sharpe"]
            - control.metrics["sharpe"],
            2,
        ),
    }
    SUMMARY_PATH.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    trade_frames = []
    for run in runs:
        rows = run.trades.copy()
        rows.insert(0, "variant", run.name)
        trade_frames.append(rows)
    pd.concat(trade_frames, ignore_index=True).to_csv(
        TRADES_PATH,
        index=False,
    )

    print(
        f"data {quality['start']} ~ {quality['end']} "
        f"quality_gate={quality_gate['passed']}"
    )
    parity = summary["gates"]["custom_control_parity"]
    print(
        "control parity "
        f"trades={parity['exact_trade_rows_equal']} "
        f"max_equity_diff={parity['max_equity_abs_diff']:.3g}"
    )
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>26} ret {metrics['return_pct']:>9.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"early {metrics['early_entries']:>3} "
            f"confirmed {metrics['confirmed_entries']:>3}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
