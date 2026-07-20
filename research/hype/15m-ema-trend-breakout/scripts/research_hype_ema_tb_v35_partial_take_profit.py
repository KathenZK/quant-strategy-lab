"""V35 单次分批止盈诊断。

分批单使用 entry ATR 固定价格；触发后仓位仍保持占用，剩余仓位继续
原始 TP5/SL7/indicator/timeout，不产生新的入场或 cooldown 路径。
同 bar 同时触发 stop 与有利价格时采用 stop-first。
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
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_partial_take_profit_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


@dataclass(frozen=True, slots=True)
class PartialSpec:
    name: str
    trigger_atr: float | None
    fraction: float
    side_mode: str = "both"


def specs() -> list[PartialSpec]:
    rows = [PartialSpec("v35_base", None, 0.0)]
    for trigger in (3.5, 4.0, 4.5):
        for fraction in (0.25, 1.0 / 3.0, 0.50):
            rows.append(
                PartialSpec(
                    f"partial_{trigger:g}_{fraction:.3f}_both",
                    trigger,
                    fraction,
                    "both",
                )
            )
    for fraction in (0.25, 1.0 / 3.0, 0.50):
        rows.append(
            PartialSpec(
                f"partial_4_{fraction:.3f}_long_only",
                4.0,
                fraction,
                "long_only",
            )
        )
    for trigger in (3.5, 4.0, 4.5):
        for fraction in (0.25, 1.0 / 3.0, 0.50):
            rows.append(
                PartialSpec(
                    f"partial_{trigger:g}_{fraction:.3f}_short_only",
                    trigger,
                    fraction,
                    "short_only",
                )
            )
    for trigger in (4.0, 4.2, 4.4):
        for fraction in (2.0 / 3.0, 0.75):
            rows.append(
                PartialSpec(
                    f"partial_{trigger:g}_{fraction:.3f}_short_only",
                    trigger,
                    fraction,
                    "short_only",
                )
            )
    for trigger in (4.2, 4.4):
        rows.append(
            PartialSpec(
                f"partial_{trigger:g}_0.500_short_only",
                trigger,
                0.50,
                "short_only",
            )
        )
    return rows


def side_enabled(spec: PartialSpec, direction: int) -> bool:
    return (
        spec.trigger_atr is not None
        and (
            spec.side_mode == "both"
            or (spec.side_mode == "long_only" and direction == 1)
            or (spec.side_mode == "short_only" and direction == -1)
        )
    )


def apply_partial_fill(
    *,
    equity: float,
    position: base.Position,
    fill_price: float,
    initial_allocation: float,
    fraction: float,
    config: base.V35Config,
) -> tuple[float, float, float]:
    allocation_closed = initial_allocation * fraction
    pnl = position.direction * position.allocation * (
        fill_price / position.previous_price - 1.0
    )
    cost = config.trade_cost_rate * allocation_closed
    equity *= 1.0 + pnl - cost
    position.allocation -= allocation_closed
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
    trades: list[dict[str, Any]],
    config: base.V35Config,
    partial_taken: bool,
    partial_ts: pd.Timestamp | None,
    partial_price: float | None,
    partial_fraction: float,
    partial_allocation: float,
) -> tuple[float, float]:
    pnl = position.direction * position.allocation * (
        exit_price / position.previous_price - 1.0
    )
    cost = config.trade_cost_rate * position.allocation
    exit_equity = equity * (1.0 + pnl - cost)
    raw_price_return = position.direction * (
        exit_price / position.entry_price - 1.0
    )
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
            "floor_offset_atr": position.floor_offset_atr,
            "exit_reason": reason,
            "entry_bar": position.entry_bar,
            "exit_bar": exit_bar,
            "hold_bars": exit_bar - position.entry_bar,
            "raw_price_return": raw_price_return,
            "trade_return": (
                exit_equity / position.entry_equity - 1.0
            ),
            "entry_equity": position.entry_equity,
            "exit_equity": exit_equity,
            "partial_taken": partial_taken,
            "partial_ts": partial_ts,
            "partial_price": partial_price,
            "partial_fraction": (
                partial_fraction if partial_taken else 0.0
            ),
            "partial_allocation": (
                partial_allocation if partial_taken else 0.0
            ),
        }
    )
    return exit_equity, cost


def run_backtest(
    *,
    spec: PartialSpec,
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
    partial_taken = False
    partial_ts: pd.Timestamp | None = None
    partial_price: float | None = None
    partial_allocation = 0.0
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)
    partial_events = 0

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
                trades=trades,
                config=config,
                partial_taken=partial_taken,
                partial_ts=partial_ts,
                partial_price=partial_price,
                partial_fraction=spec.fraction,
                partial_allocation=partial_allocation,
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
                allocation = min(
                    config.max_allocation,
                    target / (entry_atr / open_price),
                )
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
                partial_taken = False
                partial_ts = None
                partial_price = None
                partial_allocation = 0.0

        if position is not None:
            take_price = (
                position.entry_price
                + position.direction
                * config.take_profit_atr
                * position.entry_atr
            )
            stop_price = (
                position.entry_price
                - position.direction
                * config.hard_stop_atr
                * position.entry_atr
            )
            partial_target = (
                None
                if not side_enabled(spec, position.direction)
                else position.entry_price
                + position.direction
                * float(spec.trigger_atr)
                * position.entry_atr
            )
            stop_hit = (
                low <= stop_price
                if position.direction == 1
                else high >= stop_price
            )
            take_hit = (
                high >= take_price
                if position.direction == 1
                else low <= take_price
            )
            partial_hit = (
                not partial_taken
                and partial_target is not None
                and (
                    high >= partial_target
                    if position.direction == 1
                    else low <= partial_target
                )
            )

            if stop_hit:
                equity, cost = close_position(
                    equity=equity,
                    position=position,
                    initial_allocation=initial_allocation,
                    exit_price=stop_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason="stop_loss",
                    trades=trades,
                    config=config,
                    partial_taken=partial_taken,
                    partial_ts=partial_ts,
                    partial_price=partial_price,
                    partial_fraction=spec.fraction,
                    partial_allocation=partial_allocation,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
            else:
                if partial_hit:
                    equity, cost, closed_allocation = apply_partial_fill(
                        equity=equity,
                        position=position,
                        fill_price=float(partial_target),
                        initial_allocation=initial_allocation,
                        fraction=spec.fraction,
                        config=config,
                    )
                    trading_costs += cost
                    partial_taken = True
                    partial_ts = ts
                    partial_price = float(partial_target)
                    partial_allocation = closed_allocation
                    partial_events += 1

                if take_hit:
                    equity, cost = close_position(
                        equity=equity,
                        position=position,
                        initial_allocation=initial_allocation,
                        exit_price=take_price,
                        exit_ts=ts,
                        exit_bar=i,
                        reason="take_profit",
                        trades=trades,
                        config=config,
                        partial_taken=partial_taken,
                        partial_ts=partial_ts,
                        partial_price=partial_price,
                        partial_fraction=spec.fraction,
                        partial_allocation=partial_allocation,
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
    metrics["partial_events"] = partial_events
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(
            position,
            frame.index[-1],
        )
        open_position.update(
            {
                "initial_allocation": initial_allocation,
                "partial_taken": partial_taken,
                "partial_ts": partial_ts,
                "partial_price": partial_price,
                "partial_fraction": (
                    spec.fraction if partial_taken else 0.0
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
        "partial_events": partial_events,
        "closed_partial_trades": int(
            trades_frame.get(
                "partial_taken",
                pd.Series(dtype=bool),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "partial_final_exit_counts": (
            trades_frame.loc[
                trades_frame.get(
                    "partial_taken",
                    pd.Series(False, index=trades_frame.index),
                )
                .fillna(False)
                .astype(bool),
                "exit_reason",
            ]
            .value_counts()
            .to_dict()
        ),
    }
    return run, audit


def comparison(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any] | None:
    if run is baseline:
        return None
    return {
        "final_equity_retained_pct": round(
            100.0
            * (1.0 + run.metrics["return_pct"] / 100.0)
            / (1.0 + baseline.metrics["return_pct"] / 100.0),
            2,
        ),
        "return_delta_pp": round(
            run.metrics["return_pct"]
            - baseline.metrics["return_pct"],
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
    flags = signal_engine.SignalFlags()
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
    canonical = base.run_backtest(
        "v35_canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise ValueError(f"V35 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35",
        "audit_id": "V35 one-stage partial take-profit scan",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v35_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_baseline_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "partial_fill": (
                "One reduce-only partial fill at an entry-ATR fixed target; "
                "the remaining position keeps original TP5/SL7 and state."
            ),
            "same_bar_order": (
                "Stop-first. Without a stop hit, partial target fills before "
                "TP5 when both favorable levels are touched in one bar."
            ),
            "path": (
                "A partial fill does not close the strategy position, create "
                "a trade-count event, permit re-entry or start cooldown."
            ),
            "cost": (
                "0.00085 per filled allocation on entry, partial fill and "
                "final exit; Binance funding applies to remaining allocation."
            ),
            "unchanged": (
                "V35 signals, K0/K1/K2 timing, target sizing, ADX22 delayed3, "
                "MFE1.5 indicator-exit disable and 384-bar timeout."
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
                "comparison_to_v35": comparison(run, baseline),
            }
            for spec, run, audit in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
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
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"baseline parity diff={parity_diff:.2e}")
    print(
        f"{'variant':>34} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'partials':>8}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>34} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['partial_events']:>8}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
