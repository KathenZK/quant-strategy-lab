"""比较 V35 基准、全程 ADX 退出与完整入场信号失效退出。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_continuous_indicator_exit_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"

ExitMode = Literal["baseline", "always_adx", "entry_signal"]


def run_variant(
    *,
    name: str,
    mode: ExitMode,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> base.RunResult:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
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

        if position is None and not exited_this_bar and i > last_exit_bar:
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
                    if direction > 0
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

        if position is not None:
            intrabar = base.check_intrabar_exit(
                position=position,
                open_price=open_price,
                high=high,
                low=low,
                config=config,
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

                if mode in {"baseline", "always_adx"}:
                    can_indicator_exit = (
                        mode == "always_adx"
                        or position.mfe_atr
                        < config.disable_after_mfe_atr
                    )
                    adx_is_weak = (
                        float(features["adx"].iloc[i])
                        < config.adx_exit
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
                else:
                    signal_column = (
                        "long_signal"
                        if position.direction > 0
                        else "short_signal"
                    )
                    signal_alive = bool(
                        features[signal_column].iloc[i]
                    )
                    position.weak_bars = 0
                    if not signal_alive:
                        pending_exit = "entry_signal_lost_exit"

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
    return base.RunResult(
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


def summarize(
    run: base.RunResult,
    reference: base.RunResult,
) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "comparison_to_v35": (
            None
            if run is reference
            else {
                "final_equity_retained_pct": round(
                    100.0
                    * (1.0 + run.metrics["return_pct"] / 100.0)
                    / (1.0 + reference.metrics["return_pct"] / 100.0),
                    2,
                ),
                "return_delta_pp": round(
                    run.metrics["return_pct"]
                    - reference.metrics["return_pct"],
                    2,
                ),
                "max_drawdown_delta_pp": round(
                    run.metrics["max_drawdown_pct"]
                    - reference.metrics["max_drawdown_pct"],
                    2,
                ),
                "sharpe_delta": round(
                    run.metrics["sharpe"]
                    - reference.metrics["sharpe"],
                    2,
                ),
            }
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = base.load_data(warehouse)
    config = base.V35Config()
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        signal_engine.SignalFlags(),
    )
    no_floor = base.ProfitFloorConfig(enabled=False)
    canonical = base.run_backtest(
        "v35_canonical",
        frame,
        funding,
        features,
        config,
        no_floor,
    )
    baseline = run_variant(
        name="v35_custom_baseline",
        mode="baseline",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    always_adx = run_variant(
        name="v35_always_adx_exit",
        mode="always_adx",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    entry_signal = run_variant(
        name="v35_entry_signal_lost_exit",
        mode="entry_signal",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35 baseline parity failed: {parity_diff}")

    runs = [baseline, always_adx, entry_signal]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35",
        "audit_id": "continuous indicator presence exits",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_unchanged",
        "data_quality": quality,
        "gates": {
            "canonical_vs_custom_baseline_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "always_adx": (
                "Keep the existing ADX28<22 for 3 completed bars exit "
                "active for the whole trade; do not disable it after MFE1.5."
            ),
            "entry_signal": (
                "After every completed 15m bar, require the current "
                "direction's full V35 entry signal to remain true; if false, "
                "exit at the next bar open."
            ),
            "execution": (
                "TP5/SL7 intrabar remains first; indicator exits are "
                "close-confirmed and next-open filled. No same-bar reentry."
            ),
            "costs": (
                "0.00085 per fill, including the frozen adverse-slippage "
                "allowance; Binance funding included."
            ),
            "slice_selection": (
                "1d/7d/1m/3m/6m/1y slices are audit-only and were not used "
                "to select either rule."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(signal_engine.SignalFlags()),
        "runs": [summarize(run, baseline) for run in runs],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    base.write_artifacts(
        runs,
        trades_path=TRADES_PATH,
        equity_path=EQUITY_PATH,
    )

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} parity={parity_diff:.2e}"
    )
    for run in runs:
        metrics = run.metrics
        print(
            f"{run.name:>32} {metrics['return_pct']:>10.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"{metrics['exit_counts']}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
