"""扫描 V35.2 空头分批止损参数与 SL5.7 全平。

V35.2 原有空头 4.4ATR/75% 分批止盈保持启用。新增分批止损在空头
不利波动达到固定 entry-ATR 阈值时，按当时剩余 allocation 减仓一次；
剩余仓位继续原始 TP5/SL7 与退出状态机。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_2_short_partial_stop_scan_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
PROFIT_TRIGGER_ATR = 4.4
PROFIT_FRACTION = 0.75


@dataclass(frozen=True, slots=True)
class StopPartialSpec:
    name: str
    trigger_atr: float | None
    fraction_of_remaining: float
    side_mode: str = "short_only"
    long_trigger_atr: float | None = None
    short_trigger_atr: float | None = None
    low_adx_threshold: float | None = None
    low_adx_max_allocation: float | None = None
    directional_stop_replaces_hard_stop: bool = False


@dataclass(slots=True)
class PartialState:
    profit_taken: bool = False
    profit_ts: pd.Timestamp | None = None
    profit_price: float | None = None
    profit_allocation: float = 0.0
    stop_taken: bool = False
    stop_ts: pd.Timestamp | None = None
    stop_price: float | None = None
    stop_allocation: float = 0.0


def specs() -> tuple[StopPartialSpec, ...]:
    rows = [StopPartialSpec("v35_2_base", None, 0.0)]
    for trigger in (5.25, 5.50, 5.60, 5.70, 5.75, 5.80, 5.90, 6.00):
        for fraction in (1.0 / 3.0, 0.50, 2.0 / 3.0):
            rows.append(
                StopPartialSpec(
                    name=f"short_stop_{trigger:g}_{fraction:.3f}",
                    trigger_atr=trigger,
                    fraction_of_remaining=fraction,
                )
            )
    rows.append(
        StopPartialSpec(
            name="short_sl_5.7_full_exit",
            trigger_atr=5.70,
            fraction_of_remaining=1.0,
        )
    )
    return tuple(rows)


def reduce_position(
    *,
    equity: float,
    position: base.Position,
    fill_price: float,
    fraction_of_remaining: float,
    config: base.V35Config,
) -> tuple[float, float, float]:
    allocation_before = position.allocation
    allocation_closed = allocation_before * fraction_of_remaining
    pnl = position.direction * allocation_before * (
        fill_price / position.previous_price - 1.0
    )
    cost = config.trade_cost_rate * allocation_closed
    equity *= 1.0 + pnl - cost
    position.allocation = allocation_before - allocation_closed
    position.previous_price = fill_price
    return equity, cost, allocation_closed


def close_position(
    *,
    equity: float,
    position: base.Position,
    initial_allocation: float,
    exit_price: float,
    exit_ts: pd.Timestamp,
    exit_bar: int,
    reason: str,
    state: PartialState,
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
            "allocation": initial_allocation,
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
            "profit_partial_taken": state.profit_taken,
            "profit_partial_ts": state.profit_ts,
            "profit_partial_price": state.profit_price,
            "profit_partial_allocation": state.profit_allocation,
            "stop_partial_taken": state.stop_taken,
            "stop_partial_ts": state.stop_ts,
            "stop_partial_price": state.stop_price,
            "stop_partial_allocation": state.stop_allocation,
        }
    )
    return exit_equity, cost


def run_backtest(
    *,
    spec: StopPartialSpec,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    cooldown_bars: int = 0,
) -> tuple[base.RunResult, dict[str, Any]]:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    initial_allocation = 0.0
    pending_exit: str | None = None
    last_exit_bar = -1
    state = PartialState()
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    profit_partial_events = 0
    stop_partial_events = 0
    low_adx_capped_entries = 0
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
                initial_allocation=initial_allocation,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                state=state,
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
                * float(funding.iloc[i])
            )
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        cooldown_complete = i > last_exit_bar + cooldown_bars
        if position is None and not exited_this_bar and cooldown_complete:
            signal_i = i - config.entry_delay_bars
            direction = 0
            if bool(features["long_signal"].iloc[signal_i]) and not bool(
                features["short_signal"].iloc[signal_i]
            ):
                direction = 1
            elif bool(features["short_signal"].iloc[signal_i]) and not bool(
                features["long_signal"].iloc[signal_i]
            ):
                direction = -1
            entry_atr = float(features["atr"].iloc[i - 1])
            if (
                direction != 0
                and np.isfinite(entry_atr)
                and entry_atr > 0.0
                and open_price > 0.0
            ):
                target = (
                    config.long_target_atr_pct
                    if direction == 1
                    else config.short_target_atr_pct
                )
                dynamic_cap = config.max_allocation
                if (
                    spec.low_adx_threshold is not None
                    and float(features["adx"].iloc[signal_i])
                    < spec.low_adx_threshold
                ):
                    dynamic_cap = min(
                        dynamic_cap,
                        spec.low_adx_max_allocation or dynamic_cap,
                    )
                uncapped_allocation = target / (entry_atr / open_price)
                allocation = min(
                    dynamic_cap,
                    uncapped_allocation,
                )
                if allocation < min(
                    config.max_allocation,
                    uncapped_allocation,
                ):
                    low_adx_capped_entries += 1
                cost = config.trade_cost_rate * allocation
                equity *= 1.0 - cost
                trading_costs += cost
                position = base.Position(
                    direction=direction,
                    entry_bar=i,
                    entry_ts=ts,
                    entry_price=open_price,
                    entry_atr=entry_atr,
                    allocation=allocation,
                    entry_equity=equity,
                    previous_price=open_price,
                )
                initial_allocation = allocation
                state = PartialState()

        if position is not None:
            directional_trigger_atr = (
                spec.long_trigger_atr
                if position.direction == 1
                else spec.short_trigger_atr
            )
            directional_stop_replaces_hard_stop = (
                spec.directional_stop_replaces_hard_stop
                and directional_trigger_atr is not None
            )
            stop_side_enabled = (
                not directional_stop_replaces_hard_stop
                and (
                    directional_trigger_atr is not None
                    or (
                        spec.trigger_atr is not None
                        and (
                            (
                                spec.side_mode == "short_only"
                                and position.direction == -1
                            )
                            or (
                                spec.side_mode == "long_only"
                                and position.direction == 1
                            )
                        )
                    )
                )
            )
            hard_stop_atr = (
                float(directional_trigger_atr)
                if directional_stop_replaces_hard_stop
                else config.hard_stop_atr
            )
            effective_stop_trigger_atr = (
                directional_trigger_atr
                if directional_trigger_atr is not None
                else spec.trigger_atr
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
                + position.direction
                * PROFIT_TRIGGER_ATR
                * position.entry_atr
                if position.direction == -1
                else None
            )
            stop_partial_price = (
                position.entry_price
                - position.direction
                * float(effective_stop_trigger_atr)
                * position.entry_atr
                if stop_side_enabled
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
            profit_partial_hit = (
                position.direction == -1
                and not state.profit_taken
                and profit_partial_price is not None
                and low <= profit_partial_price
            )
            stop_partial_hit = (
                stop_side_enabled
                and not state.stop_taken
                and stop_partial_price is not None
                and (
                    low <= stop_partial_price
                    if position.direction == 1
                    else high >= stop_partial_price
                )
            )

            if hard_stop_hit:
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    initial_allocation=initial_allocation,
                    exit_price=hard_stop_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="stop_loss",
                    state=state,
                    trades=trades,
                    config=config,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                full_stop_exit = False
                if stop_partial_hit:
                    state.stop_taken = True
                    state.stop_ts = ts
                    state.stop_price = float(stop_partial_price)
                    if spec.fraction_of_remaining >= 1.0:
                        state.stop_allocation = position.allocation
                        equity, cost = close_position(
                            equity=equity,
                            position=position,
                            initial_allocation=initial_allocation,
                            exit_price=float(stop_partial_price),
                            exit_ts=ts,
                            exit_bar=i,
                            reason="stop_loss",
                            state=state,
                            trades=trades,
                            config=config,
                        )
                        trading_costs += cost
                        position = None
                        pending_exit = None
                        last_exit_bar = i
                        full_stop_exit = True
                    else:
                        equity, cost, allocation_closed = reduce_position(
                            equity=equity,
                            position=position,
                            fill_price=float(stop_partial_price),
                            fraction_of_remaining=(
                                spec.fraction_of_remaining
                            ),
                            config=config,
                        )
                        trading_costs += cost
                        state.stop_allocation = allocation_closed
                    stop_partial_events += 1

                if not full_stop_exit and profit_partial_hit:
                    equity, cost, allocation_closed = reduce_position(
                        equity=equity,
                        position=position,
                        fill_price=float(profit_partial_price),
                        fraction_of_remaining=PROFIT_FRACTION,
                        config=config,
                    )
                    trading_costs += cost
                    state.profit_taken = True
                    state.profit_ts = ts
                    state.profit_price = float(profit_partial_price)
                    state.profit_allocation = allocation_closed
                    profit_partial_events += 1

                if full_stop_exit:
                    pass
                elif take_hit:
                    equity, cost = close_position(
                        equity=equity,
                        position=position,
                        initial_allocation=initial_allocation,
                        exit_price=take_price,
                        exit_ts=ts,
                        exit_bar=i,
                        reason="take_profit",
                        state=state,
                        trades=trades,
                        config=config,
                    )
                    trading_costs += cost
                    position = None
                    pending_exit = None
                    last_exit_bar = i
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
                        float(features["adx"].iloc[i]) < config.adx_exit
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
                    if (
                        pending_exit is None
                        and i - position.entry_bar
                        >= config.max_hold_bars
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
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
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
    metrics["stop_partial_events"] = stop_partial_events
    metrics["low_adx_capped_entries"] = low_adx_capped_entries
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(
            position,
            frame.index[-1],
        )
        open_position.update(
            {
                "initial_allocation": initial_allocation,
                "profit_partial_taken": state.profit_taken,
                "stop_partial_taken": state.stop_taken,
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
    stop_mask = (
        trades_frame.get(
            "stop_partial_taken",
            pd.Series(False, index=trades_frame.index),
        )
        .fillna(False)
        .astype(bool)
    )
    profit_mask = (
        trades_frame.get(
            "profit_partial_taken",
            pd.Series(False, index=trades_frame.index),
        )
        .fillna(False)
        .astype(bool)
    )
    audit = {
        "profit_partial_events": profit_partial_events,
        "stop_partial_events": stop_partial_events,
        "low_adx_capped_entries": low_adx_capped_entries,
        "closed_stop_partial_trades": int(stop_mask.sum()),
        "both_partials_trades": int((stop_mask & profit_mask).sum()),
        "stop_partial_final_exit_counts": (
            trades_frame.loc[stop_mask, "exit_reason"]
            .value_counts()
            .to_dict()
        ),
    }
    return run, audit


def comparison(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, float]:
    return {
        "final_equity_retained_pct": round(
            100.0
            * (1.0 + run.metrics["return_pct"] / 100.0)
            / (1.0 + baseline.metrics["return_pct"] / 100.0),
            2,
        ),
        "return_delta_pp": round(
            run.metrics["return_pct"] - baseline.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            run.metrics["max_drawdown_pct"]
            - baseline.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            run.metrics["sharpe"] - baseline.metrics["sharpe"],
            2,
        ),
        "win_rate_delta_pp": round(
            run.metrics["win_rate_pct"]
            - baseline.metrics["win_rate_pct"],
            2,
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    run_specs = specs()
    outputs = [
        (
            spec,
            *run_backtest(
                spec=spec,
                frame=frame,
                funding=funding,
                features=features,
                config=config,
            ),
        )
        for spec in run_specs
    ]
    baseline = outputs[0][1]
    canonical, _ = partial.run_backtest(
        spec=partial.PartialSpec(
            "v35_2_canonical",
            PROFIT_TRIGGER_ATR,
            PROFIT_FRACTION,
            "short_only",
        ),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=0,
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35.2 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.2",
        "audit_id": "V35.2 short-only partial stop scan",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_v35_2_baseline_max_equity_diff": (
                parity_diff
            ),
        },
        "assumptions": {
            "profit_partial": (
                "V35.2 short MFE4.4ATR reduce 75% of current remaining "
                "allocation once; baseline is identical to the registered "
                "V35.2 because no prior stop partial exists."
            ),
            "stop_partial": (
                "Short-only, one reduce-only fill at an entry-ATR fixed "
                "adverse level; fraction applies to current remaining "
                "allocation and the rest keeps TP5/SL7."
            ),
            "same_bar_order": (
                "Hard SL7 first, then adverse stop partial, favorable "
                "profit partial, and TP5."
            ),
            "path": (
                "Neither partial releases the strategy position, creates "
                "a trade-count event, permits reentry or starts cooldown."
            ),
            "costs": (
                "0.00085 per filled allocation on entry, each partial and "
                "final exit; funding applies to remaining allocation."
            ),
            "slice_selection": (
                "Recent slices are audit-only and were not used to choose "
                "the scan grid."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            {
                "spec": asdict(spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "comparison_to_v35_2": (
                    None
                    if run is baseline
                    else comparison(run, baseline)
                ),
            }
            for spec, run, audit in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(variant=run.name)
            for _, run, _ in outputs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for _, run, _ in outputs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']} "
        f"parity={parity_diff:.2e}"
    )
    print(
        f"{'variant':>28} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'win%':>7} {'stopN':>6} {'bothN':>6}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>28} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['stop_partial_events']:>6} "
            f"{audit['both_partials_trades']:>6}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
