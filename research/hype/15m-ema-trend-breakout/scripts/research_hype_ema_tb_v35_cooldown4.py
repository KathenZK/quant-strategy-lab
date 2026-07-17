from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_h4_rsi6_entry_filter as rsi_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_cooldown4_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


@dataclass(frozen=True, slots=True)
class RunSpec:
    name: str
    cooldown_bars: int
    use_rsi10_90: bool


RUN_SPECS = [
    RunSpec("v35_base", cooldown_bars=0, use_rsi10_90=False),
    RunSpec("v35_cooldown4", cooldown_bars=4, use_rsi10_90=False),
    RunSpec("v35_rsi10_90", cooldown_bars=0, use_rsi10_90=True),
    RunSpec("v35_rsi10_90_cooldown4", cooldown_bars=4, use_rsi10_90=True),
]


def run_backtest(
    spec: RunSpec,
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
            funding_pnl = -position.direction * position.allocation * float(
                funding.iloc[i]
            )
            equity *= 1.0 + funding_pnl
            funding_pnl_total += funding_pnl

        cooldown_complete = i > last_exit_bar + spec.cooldown_bars
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
                    config.max_allocation, target / (entry_atr / open_price)
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
                    position, high, low, config, no_floor
                )
                can_indicator_exit = (
                    position.mfe_atr < config.disable_after_mfe_atr
                )
                if can_indicator_exit and float(features["adx"].iloc[i]) < config.adx_exit:
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
            0.0 if position is None else position.direction * position.allocation
        )

    index = frame.index[start:]
    equity_curve = pd.Series(equity_values, index=index, name=spec.name)
    returns = pd.Series(period_returns, index=index, name=f"{spec.name}_return")
    weights = pd.Series(weight_values, index=index, name=f"{spec.name}_weight")
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
        name=spec.name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=base.open_position_summary(position, frame.index[-1])
        if position is not None
        else None,
    )


def comparison(run: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    final_equity = 1.0 + float(run.metrics["return_pct"]) / 100.0
    base_final_equity = 1.0 + float(baseline.metrics["return_pct"]) / 100.0
    return {
        "name": run.name,
        "final_equity_retained_pct": round(
            final_equity / base_final_equity * 100.0, 2
        ),
        "return_delta_pp": round(
            float(run.metrics["return_pct"])
            - float(baseline.metrics["return_pct"]),
            2,
        ),
        "max_drawdown_delta_pp": round(
            float(run.metrics["max_drawdown_pct"])
            - float(baseline.metrics["max_drawdown_pct"]),
            2,
        ),
        "sharpe_delta": round(
            float(run.metrics["sharpe"]) - float(baseline.metrics["sharpe"]), 2
        ),
        "win_rate_delta_pp": round(
            float(run.metrics["win_rate_pct"])
            - float(baseline.metrics["win_rate_pct"]),
            2,
        ),
        "trade_delta": int(run.metrics["trades"] - baseline.metrics["trades"]),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = rsi_diag.load_data(warehouse)
    gate = rsi_diag.quality_gate(quality)
    config = base.V35Config()
    base_features = base.build_features(frame, config)
    entry_rsi6 = rsi_diag.entry_time_h4_rsi6(frame)
    rsi_features, rsi_signal_audit = rsi_diag.filtered_features(
        base_features,
        entry_rsi6,
        config,
        rsi_diag.FilterVariant(
            "symmetric_10_90", lower=10.0, upper=90.0, mode="symmetric"
        ),
    )

    runs = [
        run_backtest(
            spec,
            frame,
            funding,
            rsi_features if spec.use_rsi10_90 else base_features,
            config,
        )
        for spec in RUN_SPECS
    ]
    baseline = runs[0]
    canonical = base.run_backtest(
        "canonical_parity",
        frame,
        funding,
        base_features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_max_equity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_max_equity_diff > 1e-12:
        raise ValueError(
            f"baseline parity failed: max equity diff={parity_max_equity_diff}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V35",
        "audit_id": "4-bar post-exit cooldown diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_not_registered",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "baseline_vs_canonical_max_equity_diff": parity_max_equity_diff,
        },
        "assumptions": {
            "cooldown4": (
                "After an exit on bar E, block entries on E+1 through E+4; "
                "the earliest new entry is E+5 open."
            ),
            "rsi10_90": (
                "At K2 open, block both long and short entries when the latest "
                "fully closed 4h Wilder RSI6 is <=10 or >=90."
            ),
            "unchanged": (
                "V35 signals, K0/K1/K2 timing, sizing, 5ATR TP, 7ATR SL, "
                "ADX22 delayed3, 384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "base_config": asdict(config),
        "run_specs": [asdict(spec) for spec in RUN_SPECS],
        "rsi_signal_audit": rsi_signal_audit,
        "runs": [
            {
                "name": run.name,
                "metrics": run.metrics,
                "slices": run.slices,
                "open_position": run.open_position,
            }
            for run in runs
        ],
        "comparison_to_v35_base": [
            comparison(run, baseline) for run in runs[1:]
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    trade_frames = []
    for run in runs:
        trades = run.trades.copy()
        trades.insert(0, "variant", run.name)
        trade_frames.append(trades)
    pd.concat(trade_frames, ignore_index=True).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs], axis=1
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={gate['passed']}"
    )
    print(f"baseline parity max equity diff: {parity_max_equity_diff:.2e}")
    print(
        f"{'variant':>28}  {'return%':>10}  {'maxDD%':>8}  {'sharpe':>6}  "
        f"{'trades':>6}  {'win%':>7}  {'retained%':>10}"
    )
    for run in runs:
        retained = (
            100.0
            if run is baseline
            else comparison(run, baseline)["final_equity_retained_pct"]
        )
        metrics = run.metrics
        print(
            f"{run.name:>28}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  {metrics['sharpe']:>6.2f}  "
            f"{metrics['trades']:>6}  {metrics['win_rate_pct']:>7.2f}  "
            f"{retained:>10.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
