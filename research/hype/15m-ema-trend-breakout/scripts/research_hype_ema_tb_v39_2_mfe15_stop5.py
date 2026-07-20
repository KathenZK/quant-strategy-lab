"""V39.2 在 MFE 达到 1.5ATR 后把硬止损从 7ATR 收紧到 5ATR。

时序口径：
- MFE 只在 15m bar 收盘后更新；
- K0 收盘首次确认 MFE>=1.5ATR，5ATR 止损从 K1 开始生效；
- K0 内即使同时触及 1.5ATR 与 5ATR 止损，也不会回看式触发新止损；
- 生效后若 bar open 已越过止损，按更差的 open 成交；
- 同 bar 同时触发 stop 与 TP 时采用 stop-first。
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_cooldown1 as path_tools
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_mfe15_stop5_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def check_intrabar_exit(
    *,
    position: base.Position,
    open_price: float,
    high: float,
    low: float,
    stop_atr: float,
    take_profit_atr: float,
    gap_open: bool,
    tightened: bool,
) -> tuple[str, float] | None:
    take = (
        position.entry_price
        + position.direction * take_profit_atr * position.entry_atr
    )
    stop = (
        position.entry_price
        - position.direction * stop_atr * position.entry_atr
    )
    reason = "mfe15_stop5" if tightened else "stop_loss"

    if position.direction == 1:
        if low <= stop:
            exit_price = min(open_price, stop) if gap_open else stop
            return reason, exit_price
        if high >= take:
            return "take_profit", take
    else:
        if high >= stop:
            exit_price = max(open_price, stop) if gap_open else stop
            return reason, exit_price
        if low <= take:
            return "take_profit", take
    return None


def annotate_last_trade(
    trades: list[dict[str, Any]],
    *,
    activation_signal_ts: pd.Timestamp | None,
    active_from_bar: int | None,
    tightened_on_exit: bool,
) -> None:
    trades[-1]["mfe15_stop5_activated"] = active_from_bar is not None
    trades[-1]["mfe15_activation_signal_ts"] = activation_signal_ts
    trades[-1]["mfe15_stop5_active_on_exit"] = tightened_on_exit


def run_backtest(
    *,
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    cooldown_bars: int,
    trigger_mfe_atr: float | None,
    tightened_stop_atr: float,
    gap_open: bool,
) -> tuple[base.RunResult, dict[str, Any]]:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    active_from_bar: int | None = None
    activation_signal_ts: pd.Timestamp | None = None
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)
    activation_events = 0

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            tightened = active_from_bar is not None and i >= active_from_bar
            equity, cost = base.close_position(
                equity=equity,
                position=position,
                exit_price=open_price,
                exit_ts=ts,
                exit_bar=i,
                reason=pending_exit,
                trades=trades,
                config=config,
            )
            annotate_last_trade(
                trades,
                activation_signal_ts=activation_signal_ts,
                active_from_bar=active_from_bar,
                tightened_on_exit=tightened,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            last_exit_bar = i
            active_from_bar = None
            activation_signal_ts = None
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
                active_from_bar = None
                activation_signal_ts = None

        if position is not None:
            tightened = active_from_bar is not None and i >= active_from_bar
            stop_atr = tightened_stop_atr if tightened else config.hard_stop_atr
            intrabar = check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                stop_atr=stop_atr,
                take_profit_atr=config.take_profit_atr,
                gap_open=gap_open,
                tightened=tightened,
            )
            if intrabar is not None:
                reason, exit_price = intrabar
                equity, cost = base.close_position(
                    equity=equity,
                    position=position,
                    exit_price=exit_price,
                    exit_ts=ts,
                    exit_bar=i,
                    reason=reason,
                    trades=trades,
                    config=config,
                )
                annotate_last_trade(
                    trades,
                    activation_signal_ts=activation_signal_ts,
                    active_from_bar=active_from_bar,
                    tightened_on_exit=tightened,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                last_exit_bar = i
                active_from_bar = None
                activation_signal_ts = None
            else:
                pnl = position.direction * position.allocation * (
                    close / position.previous_price - 1.0
                )
                equity *= 1.0 + pnl
                position.previous_price = close
                prior_mfe = position.mfe_atr
                base.update_position_on_close(
                    position,
                    high,
                    low,
                    config,
                    no_floor,
                )
                if (
                    trigger_mfe_atr is not None
                    and active_from_bar is None
                    and prior_mfe < trigger_mfe_atr
                    and position.mfe_atr >= trigger_mfe_atr
                ):
                    active_from_bar = i + 1
                    activation_signal_ts = ts
                    activation_events += 1

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

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=name)
    returns = pd.Series(period_returns, index=index, name=f"{name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{name}_weight")
    trades_frame = pd.DataFrame(trades)
    metrics = base.metrics_from_series(
        equity_curve=equity_curve,
        returns=returns,
        weights=weights,
        trades=trades_frame,
        trading_costs=trading_costs,
        funding_pnl=funding_pnl_total,
    )
    result = base.RunResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=(
            base.open_position_summary(position, frame.index[-1])
            if position is not None
            else None
        ),
    )
    audit = {
        "activation_events": activation_events,
        "closed_activated_trades": int(
            trades_frame["mfe15_stop5_activated"].sum()
        ),
        "tightened_stop_exits": int(
            trades_frame["exit_reason"].eq("mfe15_stop5").sum()
        ),
        "active_on_other_exit": int(
            (
                trades_frame["mfe15_stop5_active_on_exit"]
                & trades_frame["exit_reason"].ne("mfe15_stop5")
            ).sum()
        ),
    }
    return result, audit


def affected_trade_audit(
    baseline: base.RunResult,
    candidate: base.RunResult,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    affected = candidate.trades[
        candidate.trades["exit_reason"].eq("mfe15_stop5")
    ]
    for trade in affected.itertuples():
        matched = baseline.trades[
            baseline.trades["entry_ts"].eq(trade.entry_ts)
            & baseline.trades["direction"].eq(trade.direction)
        ]
        baseline_trade = matched.iloc[0] if len(matched) == 1 else None
        rows.append(
            {
                "entry_ts": pd.Timestamp(trade.entry_ts).isoformat(),
                "direction": int(trade.direction),
                "activation_signal_ts": (
                    pd.Timestamp(trade.mfe15_activation_signal_ts).isoformat()
                ),
                "candidate_exit_ts": pd.Timestamp(trade.exit_ts).isoformat(),
                "candidate_exit_price": float(trade.exit_price),
                "candidate_trade_return_pct": base.pct(
                    float(trade.trade_return)
                ),
                "baseline_exit_ts": (
                    pd.Timestamp(baseline_trade["exit_ts"]).isoformat()
                    if baseline_trade is not None
                    else None
                ),
                "baseline_exit_reason": (
                    str(baseline_trade["exit_reason"])
                    if baseline_trade is not None
                    else None
                ),
                "baseline_trade_return_pct": (
                    base.pct(float(baseline_trade["trade_return"]))
                    if baseline_trade is not None
                    else None
                ),
            }
        )
    return rows


def summarize_affected_trades(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [
        row
        for row in rows
        if row["baseline_trade_return_pct"] is not None
    ]
    baseline_exit_counts = pd.Series(
        [row["baseline_exit_reason"] for row in matched],
        dtype="object",
    ).value_counts()
    deltas = [
        float(row["candidate_trade_return_pct"])
        - float(row["baseline_trade_return_pct"])
        for row in matched
    ]
    return {
        "tightened_stop_exits": len(rows),
        "matched_same_entry_in_baseline": len(matched),
        "candidate_path_only": len(rows) - len(matched),
        "matched_baseline_exit_counts": {
            str(key): int(value)
            for key, value in baseline_exit_counts.to_dict().items()
        },
        "matched_candidate_better": sum(delta > 0.0 for delta in deltas),
        "matched_candidate_worse": sum(delta < 0.0 for delta in deltas),
        "matched_mean_return_delta_pp": (
            round(float(np.mean(deltas)), 2) if deltas else None
        ),
    }


def summarize_run(
    run: base.RunResult,
    reference: base.RunResult,
    audit: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "dynamic_stop_audit": audit,
        "comparison_to_registered_v39_2": (
            None if run is reference else cooldown.comparison(run, reference)
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)

    config = replace(v39.v39_config(), long_vol_min=0.25)
    flags = v39.v39_flags()
    indicator_features = base.build_features(frame, config)
    features = signal_engine.build_signals(
        indicator_features,
        config,
        flags,
    )
    run_spec = cooldown.RunSpec(
        "v39_2_registered_reference",
        cooldown_bars=1,
        use_rsi10_90=False,
    )
    registered = cooldown.run_backtest(
        spec=run_spec,
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    gap_baseline, gap_baseline_audit = run_backtest(
        name="v39_2_gap_open_baseline",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=1,
        trigger_mfe_atr=None,
        tightened_stop_atr=5.0,
        gap_open=True,
    )
    candidate, candidate_audit = run_backtest(
        name="v39_2_mfe15_stop5",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=1,
        trigger_mfe_atr=1.5,
        tightened_stop_atr=5.0,
        gap_open=True,
    )
    runs = [registered, gap_baseline, candidate]

    gap_baseline_equity_diff = float(
        (
            registered.equity_curve
            - gap_baseline.equity_curve
        ).abs().max()
    )
    affected = affected_trade_audit(gap_baseline, candidate)
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "audit_id": "V39.2 MFE1.5 then hard-stop 7ATR to 5ATR",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v39_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "registered_vs_gap_open_baseline_max_equity_diff": (
                gap_baseline_equity_diff
            ),
        },
        "assumptions": {
            "test_change": (
                "After a completed bar first confirms MFE>=1.5ATR, "
                "tighten the entry-anchored hard stop from 7ATR to 5ATR "
                "starting on the next 15m bar."
            ),
            "gap_open": (
                "If the next bar opens beyond the active stop, fill at "
                "the adverse open; otherwise fill at the stop."
            ),
            "same_bar_order": "stop-first, then take-profit.",
            "unchanged": (
                "V39.2 long_vol_min=0.25, cooldown1, long target 0.020, "
                "short target 0.022, K0/K1/K2 timing, 5ATR TP, "
                "ADX22 delayed3, 384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            summarize_run(
                run,
                registered,
                (
                    gap_baseline_audit
                    if run is gap_baseline
                    else candidate_audit
                    if run is candidate
                    else None
                ),
            )
            for run in runs
        ],
        "path_audit": {
            "gap_baseline_vs_candidate": path_tools.trade_path_audit(
                gap_baseline,
                candidate,
            ),
            "tightened_stop_summary": summarize_affected_trades(affected),
            "tightened_stop_exits": affected,
        },
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(variant=run.name)
            for run in runs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"gap-baseline parity diff={gap_baseline_equity_diff:.2e}")
    print(
        f"{'variant':>30}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}"
    )
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>30}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}"
        )
    print("candidate audit", candidate_audit)
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
