"""V35 多空达到 4.5ATR MFE 后，在四项方向特征任一失效时退出。

可执行时序：
- MFE 和当前方向特征只在已完成 15m bar 收盘后判断；
- 15m EMA、1h EMA、ADX、量能任一不再满足当前方向即下一根 open 平仓；
- 原始 TP5/SL7 盘中 bracket 优先，不回看式在触发 bar close 成交；
- 仅在历史 MFE>=4.5ATR 后启用该退出。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_cooldown1 as path_tools


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_mfe45_feature_loss_exit_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
ACTIVATION_MFE_ATR = 4.5


def annotate_last_trade(
    trades: list[dict[str, Any]],
    *,
    feature_exit_triggered: bool,
    trigger_signal_ts: pd.Timestamp | None,
    trigger_failed_features: tuple[str, ...],
) -> None:
    trades[-1]["mfe45_feature_loss_exit_triggered"] = (
        feature_exit_triggered
    )
    trades[-1]["mfe45_feature_loss_exit_signal_ts"] = trigger_signal_ts
    trades[-1]["mfe45_failed_features"] = ",".join(
        trigger_failed_features
    )


def directional_feature_state(
    features: pd.DataFrame,
    config: base.V35Config,
    bar: int,
    direction: int,
) -> dict[str, bool]:
    row = features.iloc[bar]
    if direction == 1:
        return {
            "ema_15m": float(row["ema_spread"]) > 0.0,
            "ema_1h": float(row["h1_ema_spread"]) > 0.0,
            "adx": float(row["adx"]) >= config.long_adx_min,
            "volume": (
                float(row["volume_surge"]) >= config.long_vol_min
            ),
        }
    return {
        "ema_15m": float(row["ema_spread"]) < 0.0,
        "ema_1h": float(row["h1_ema_spread"]) < 0.0,
        "adx": float(row["adx"]) >= config.short_adx_min,
        "volume": float(row["volume_surge"]) >= config.short_vol_min,
    }


def run_backtest(
    *,
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
    enable_mfe45_feature_loss_exit: bool,
) -> tuple[base.RunResult, dict[str, Any]]:
    start = max(config.warmup_bars, config.entry_delay_bars + 1)
    equity = 1.0
    position: base.Position | None = None
    pending_exit: str | None = None
    last_exit_bar = -1
    trigger_signal_ts: pd.Timestamp | None = None
    trigger_failed_features: tuple[str, ...] = ()
    equity_values: list[float] = []
    period_returns: list[float] = []
    weight_values: list[float] = []
    trades: list[dict[str, Any]] = []
    trading_costs = 0.0
    funding_pnl_total = 0.0
    no_floor = base.ProfitFloorConfig(enabled=False)
    trigger_events = 0

    for i in range(start, len(frame)):
        start_equity = equity
        ts = pd.Timestamp(frame.index[i])
        open_price = float(frame["open"].iloc[i])
        high = float(frame["high"].iloc[i])
        low = float(frame["low"].iloc[i])
        close = float(frame["close"].iloc[i])
        exited_this_bar = False

        if position is not None and pending_exit is not None:
            feature_exit_triggered = (
                pending_exit == "high_mfe_feature_loss_exit"
            )
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
                feature_exit_triggered=feature_exit_triggered,
                trigger_signal_ts=trigger_signal_ts,
                trigger_failed_features=trigger_failed_features,
            )
            trading_costs += cost
            position = None
            pending_exit = None
            trigger_signal_ts = None
            trigger_failed_features = ()
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
                trigger_signal_ts = None
                trigger_failed_features = ()

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
                annotate_last_trade(
                    trades,
                    feature_exit_triggered=False,
                    trigger_signal_ts=trigger_signal_ts,
                    trigger_failed_features=trigger_failed_features,
                )
                trading_costs += cost
                position = None
                pending_exit = None
                trigger_signal_ts = None
                trigger_failed_features = ()
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
                    position.mfe_atr < config.disable_after_mfe_atr
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
                    enable_mfe45_feature_loss_exit
                    and pending_exit is None
                    and position.mfe_atr >= ACTIVATION_MFE_ATR
                ):
                    feature_state = directional_feature_state(
                        features,
                        config,
                        i,
                        position.direction,
                    )
                    failed_features = tuple(
                        key
                        for key, is_present in feature_state.items()
                        if not is_present
                    )
                    if failed_features:
                        pending_exit = "high_mfe_feature_loss_exit"
                        trigger_signal_ts = ts
                        trigger_failed_features = failed_features
                        trigger_events += 1

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
    open_position = None
    if position is not None:
        open_position = base.open_position_summary(position, frame.index[-1])
        open_position["pending_exit"] = pending_exit
        open_position["mfe45_feature_loss_exit_signal_ts"] = (
            trigger_signal_ts
        )
        open_position["mfe45_failed_features"] = list(
            trigger_failed_features
        )
    result = base.RunResult(
        name=name,
        metrics=metrics,
        slices=base.slice_metrics(equity_curve, trades_frame),
        trades=trades_frame,
        equity_curve=equity_curve,
        period_returns=returns,
        open_position=open_position,
    )
    audit = {
        "trigger_events": trigger_events,
        "closed_signal_exits": int(
            trades_frame.get(
                "mfe45_feature_loss_exit_triggered",
                pd.Series(dtype=bool),
            )
            .fillna(False)
            .astype(bool)
            .sum()
        ),
        "pending_at_data_end": (
            pending_exit == "high_mfe_feature_loss_exit"
        ),
    }
    return result, audit


def affected_trade_audit(
    baseline: base.RunResult,
    candidate: base.RunResult,
) -> list[dict[str, Any]]:
    exits = candidate.trades.loc[
        candidate.trades["exit_reason"].eq("high_mfe_feature_loss_exit")
    ].copy()
    if exits.empty:
        return []
    baseline_lookup = {
        (pd.Timestamp(row["entry_ts"]), int(row["direction"])): row
        for _, row in baseline.trades.iterrows()
    }
    rows: list[dict[str, Any]] = []
    for _, row in exits.iterrows():
        key = (pd.Timestamp(row["entry_ts"]), int(row["direction"]))
        base_row = baseline_lookup.get(key)
        rows.append(
            {
                "entry_ts": key[0],
                "direction": key[1],
                "trigger_signal_ts": row[
                    "mfe45_feature_loss_exit_signal_ts"
                ],
                "failed_features": row["mfe45_failed_features"],
                "candidate_exit_ts": row["exit_ts"],
                "candidate_exit_price": float(row["exit_price"]),
                "candidate_trade_return_pct": 100.0
                * float(row["trade_return"]),
                "candidate_mfe_atr": float(row["mfe_atr"]),
                "baseline_exit_ts": (
                    None if base_row is None else base_row["exit_ts"]
                ),
                "baseline_exit_reason": (
                    None if base_row is None else base_row["exit_reason"]
                ),
                "baseline_trade_return_pct": (
                    None
                    if base_row is None
                    else 100.0 * float(base_row["trade_return"])
                ),
                "baseline_mfe_atr": (
                    None
                    if base_row is None
                    else float(base_row["mfe_atr"])
                ),
            }
        )
    return rows


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
        "audit": audit,
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
                    run.metrics["sharpe"] - reference.metrics["sharpe"],
                    2,
                ),
                "win_rate_delta_pp": round(
                    run.metrics["win_rate_pct"]
                    - reference.metrics["win_rate_pct"],
                    2,
                ),
            }
        ),
    }


def summarize_affected_trades(
    affected: list[dict[str, Any]],
) -> dict[str, Any]:
    if not affected:
        return {
            "count": 0,
            "by_direction": {},
            "by_failed_features": {},
            "matched_baseline_exit_reasons": {},
        }
    frame = pd.DataFrame(affected)
    matched = frame.loc[frame["baseline_exit_reason"].notna()]
    return {
        "count": int(len(frame)),
        "by_direction": {
            str(key): int(value)
            for key, value in frame["direction"].value_counts().items()
        },
        "by_failed_features": {
            str(key): int(value)
            for key, value in frame["failed_features"].value_counts().items()
        },
        "matched_baseline_exit_reasons": {
            str(key): int(value)
            for key, value in matched[
                "baseline_exit_reason"
            ].value_counts().items()
        },
        "matched_candidate_avg_trade_return_pct": float(
            matched["candidate_trade_return_pct"].mean()
        ),
        "matched_baseline_avg_trade_return_pct": float(
            matched["baseline_trade_return_pct"].mean()
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

    canonical = base.run_backtest(
        "v35_canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    baseline, baseline_audit = run_backtest(
        name="v35_custom_baseline",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        enable_mfe45_feature_loss_exit=False,
    )
    candidate, candidate_audit = run_backtest(
        name="v35_mfe45_feature_loss_exit",
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        enable_mfe45_feature_loss_exit=True,
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise ValueError(f"V35 baseline parity failed: {parity_diff}")

    affected = affected_trade_audit(baseline, candidate)
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35",
        "audit_id": "V35 MFE4.5 then directional feature-loss exit",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v35_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_baseline_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "test_change": (
                "For both long and short positions, after a completed 15m "
                "bar confirms historical MFE>=4.5ATR, exit at the next "
                "bar open if any directional retention feature is false."
            ),
            "signal_definition": (
                "Long requires 15m EMA spread>0, 1h EMA spread>0, "
                "ADX>=28 and volume_surge>=0.25. Short requires 15m EMA "
                "spread<0, 1h EMA spread<0, ADX>=36 and "
                "volume_surge>=0.50. This intentionally adds 1h EMA as a "
                "long retention feature although original V35 long entry "
                "uses 1h ADX/DI instead."
            ),
            "execution": (
                "Original intrabar TP5/SL7 remains first; conditional exit "
                "is close-confirmed and next-open filled with no lookahead."
            ),
            "unchanged": (
                "Sizing, K0/K1/K2 entry, ADX22 delayed3 early exit, "
                "MFE1.5 indicator-exit disable, 384-bar timeout, "
                "0.00085/fill and funding."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            summarize_run(baseline, baseline, baseline_audit),
            summarize_run(candidate, baseline, candidate_audit),
        ],
        "path_audit": path_tools.trade_path_audit(baseline, candidate),
        "affected_summary": summarize_affected_trades(affected),
        "affected_signal_exits": affected,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat(
        [
            baseline.trades.assign(variant=baseline.name),
            candidate.trades.assign(variant=candidate.name),
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [
            baseline.equity_curve.rename(baseline.name),
            candidate.equity_curve.rename(candidate.name),
        ],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"baseline parity diff={parity_diff:.2e}")
    for run in (baseline, candidate):
        metrics = run.metrics
        print(
            f"{run.name:>32}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  "
            f"{metrics['exit_counts']}"
        )
    print(f"candidate audit={candidate_audit}")
    print(f"affected exits={len(affected)}")
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
