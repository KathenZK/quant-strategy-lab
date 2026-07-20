"""回测 V39.2 的 SL6.75ATR + TP4.8ATR 组合及分项贡献。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_2_mfe15_stop5 as gap_engine
import research_hype_ema_tb_v39_cooldown1 as path_tools
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_sl675_tp48_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"

TP_NEIGHBORHOOD = (4.7, 4.75, 4.8, 4.85, 4.9, 4.95, 5.0)


def summarize_run(
    run: base.RunResult,
    reference: base.RunResult,
    *,
    stop_atr: float,
    take_profit_atr: float,
) -> dict[str, Any]:
    return {
        "name": run.name,
        "stop_atr": stop_atr,
        "take_profit_atr": take_profit_atr,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "comparison_to_registered_v39_2": (
            None if run is reference else cooldown.comparison(run, reference)
        ),
    }


def risk_geometry(
    config: base.V35Config,
    *,
    stop_atr: float,
    take_profit_atr: float,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "stop_to_take_ratio": stop_atr / take_profit_atr,
    }
    for side, target in (
        ("long", config.long_target_atr_pct),
        ("short", config.short_target_atr_pct),
    ):
        result[side] = {
            "uncapped_gross_tp_pct": 100.0 * target * take_profit_atr,
            "uncapped_gross_stop_pct": -100.0 * target * stop_atr,
        }
    return result


def audit_latest_registered_open_position(
    registered: base.RunResult,
    combined: base.RunResult,
    frame: pd.DataFrame,
) -> dict[str, Any] | None:
    position = registered.open_position
    if position is None:
        return None
    entry_ts = pd.Timestamp(position["entry_ts"])
    direction = int(position["direction"])
    entry_price = float(position["entry_price"])
    entry_atr = float(position["entry_atr"])
    allocation = float(position["allocation"])
    path = frame.loc[entry_ts:]
    if direction == 1:
        best_ts = pd.Timestamp(path["high"].idxmax())
        best_price = float(path.loc[best_ts, "high"])
    else:
        best_ts = pd.Timestamp(path["low"].idxmin())
        best_price = float(path.loc[best_ts, "low"])
    latest_ts = pd.Timestamp(path.index[-1])
    latest_close = float(path["close"].iloc[-1])
    mfe_atr = direction * (best_price - entry_price) / entry_atr
    current_excursion_atr = (
        direction * (latest_close - entry_price) / entry_atr
    )
    if direction == 1:
        gross_unrealized = allocation * (latest_close / entry_price - 1.0)
    else:
        gross_unrealized = allocation * (entry_price / latest_close - 1.0)
    matching = combined.trades.loc[
        (pd.to_datetime(combined.trades["entry_ts"], utc=True) == entry_ts)
        & (combined.trades["direction"] == direction)
    ]
    combined_exit = (
        None
        if matching.empty
        else {
            "exit_ts": matching.iloc[0]["exit_ts"],
            "exit_price": float(matching.iloc[0]["exit_price"]),
            "exit_reason": str(matching.iloc[0]["exit_reason"]),
            "trade_return": float(matching.iloc[0]["trade_return"]),
        }
    )
    return {
        "entry_ts": entry_ts,
        "direction": direction,
        "entry_price": entry_price,
        "entry_atr": entry_atr,
        "allocation": allocation,
        "best_ts": best_ts,
        "best_price": best_price,
        "mfe_atr": mfe_atr,
        "tp5_price": entry_price + direction * 5.0 * entry_atr,
        "tp48_price": entry_price + direction * 4.8 * entry_atr,
        "distance_remaining_to_tp5_atr": 5.0 - mfe_atr,
        "latest_ts": latest_ts,
        "latest_close": latest_close,
        "current_excursion_atr": current_excursion_atr,
        "gross_unrealized_pct": 100.0 * gross_unrealized,
        "tp48_would_have_triggered": mfe_atr >= 4.8,
        "tp5_would_have_triggered": mfe_atr >= 5.0,
        "combined_matching_exit": combined_exit,
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
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    run_specs = (
        ("v39_2_registered", 7.0, 5.0),
        ("v39_2_sl675", 6.75, 5.0),
        ("v39_2_tp48", 7.0, 4.8),
        ("v39_2_sl675_tp48", 6.75, 4.8),
    )
    runs: list[tuple[base.RunResult, float, float]] = []
    for name, stop_atr, take_profit_atr in run_specs:
        variant_config = replace(
            config,
            hard_stop_atr=stop_atr,
            take_profit_atr=take_profit_atr,
        )
        run = cooldown.run_backtest(
            spec=cooldown.RunSpec(
                name=name,
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            frame=frame,
            funding=funding,
            features=features,
            config=variant_config,
        )
        runs.append((run, stop_atr, take_profit_atr))

    registered = runs[0][0]
    stop_only = runs[1][0]
    take_only = runs[2][0]
    combined = runs[3][0]

    neighborhood_runs: list[tuple[base.RunResult, float]] = []
    for take_profit_atr in TP_NEIGHBORHOOD:
        variant_config = replace(
            config,
            hard_stop_atr=6.75,
            take_profit_atr=take_profit_atr,
        )
        run = cooldown.run_backtest(
            spec=cooldown.RunSpec(
                name=f"v39_2_sl675_tp{take_profit_atr:g}",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            frame=frame,
            funding=funding,
            features=features,
            config=variant_config,
        )
        neighborhood_runs.append((run, take_profit_atr))

    gap_combined, gap_audit = gap_engine.run_backtest(
        name="v39_2_sl675_tp48_gap_open",
        frame=frame,
        funding=funding,
        features=features,
        config=replace(
            config,
            hard_stop_atr=6.75,
            take_profit_atr=4.8,
        ),
        cooldown_bars=1,
        trigger_mfe_atr=None,
        tightened_stop_atr=6.75,
        gap_open=True,
    )
    gap_equity_diff = float(
        (combined.equity_curve - gap_combined.equity_curve).abs().max()
    )
    latest_open_position_audit = audit_latest_registered_open_position(
        registered,
        combined,
        frame,
    )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "registered_variant": "HYPE-EMA-TB-V39.3",
        "audit_id": "V39.3 SL6.75ATR and TP4.8ATR factorial evidence",
        "run_date": "2026-07-17",
        "status": "supporting_evidence_for_registered_v39_3",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "combined_vs_gap_open_max_equity_diff": gap_equity_diff,
        },
        "assumptions": {
            "test_change": (
                "Test static SL7->6.75ATR and fixed TP5->4.8ATR "
                "separately and together."
            ),
            "unchanged": (
                "V39.2 long_vol_min=0.25, cooldown1, long target 0.020, "
                "short target 0.022, K0/K1/K2 timing, ADX22 delayed3, "
                "MFE1.5 indicator-exit disable, 384-bar timeout, "
                "0.00085/fill and funding."
            ),
            "same_bar_order": "stop-first, then take-profit.",
            "slice_use": "Recent slices are audit-only, not selection windows.",
        },
        "config_at_registered_parameters": asdict(config),
        "signal_flags": asdict(flags),
        "risk_geometry": {
            "registered_sl7_tp5": risk_geometry(
                config,
                stop_atr=7.0,
                take_profit_atr=5.0,
            ),
            "combined_sl675_tp48": risk_geometry(
                config,
                stop_atr=6.75,
                take_profit_atr=4.8,
            ),
            "note": (
                "Ignores fees, funding and the 3x cap; it is only the "
                "uncapped target-ATR sizing geometry."
            ),
        },
        "factorial_runs": [
            summarize_run(
                run,
                registered,
                stop_atr=stop_atr,
                take_profit_atr=take_profit_atr,
            )
            for run, stop_atr, take_profit_atr in runs
        ],
        "tp_neighborhood_with_sl675": [
            summarize_run(
                run,
                registered,
                stop_atr=6.75,
                take_profit_atr=take_profit_atr,
            )
            for run, take_profit_atr in neighborhood_runs
        ],
        "path_audits": {
            "registered_vs_stop_only": path_tools.trade_path_audit(
                registered,
                stop_only,
            ),
            "registered_vs_take_only": path_tools.trade_path_audit(
                registered,
                take_only,
            ),
            "registered_vs_combined": path_tools.trade_path_audit(
                registered,
                combined,
            ),
            "stop_only_vs_combined": path_tools.trade_path_audit(
                stop_only,
                combined,
            ),
        },
        "latest_registered_open_position_audit": (
            latest_open_position_audit
        ),
        "gap_open_audit": gap_audit,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(variant=run.name)
            for run, _, _ in runs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for run, _, _ in runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"combined gap-open parity diff={gap_equity_diff:.2e}")
    print(
        f"{'variant':>24}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}"
    )
    for run, _, _ in runs:
        metrics = run.metrics
        print(
            f"{run.name:>24}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}"
        )
    print("TP neighborhood with SL6.75:")
    for run, take_profit_atr in neighborhood_runs:
        metrics = run.metrics
        print(
            f"TP{take_profit_atr:.2f}: "
            f"{metrics['return_pct']:.2f} / "
            f"{metrics['max_drawdown_pct']:.2f} / "
            f"{metrics['sharpe']:.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
