"""诊断 HYPE-EMA-TB-V35.3 将 15m ADX28 改为 ADX14 的影响。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial_engine
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_adx14_2026-07-21"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def v35_3_spec(name: str) -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
    )


def entry_signatures(trades: pd.DataFrame) -> set[tuple[str, int]]:
    if trades.empty:
        return set()
    return {
        (str(row.entry_ts), int(row.direction))
        for row in trades[["entry_ts", "direction"]].itertuples(index=False)
    }


def path_comparison(candidate: base.RunResult, baseline: base.RunResult) -> dict[str, Any]:
    base_entries = entry_signatures(baseline.trades)
    candidate_entries = entry_signatures(candidate.trades)
    return {
        "exact_entry_direction_matches": len(base_entries & candidate_entries),
        "baseline_only_entries": len(base_entries - candidate_entries),
        "candidate_only_entries": len(candidate_entries - base_entries),
        "baseline_entry_count": len(base_entries),
        "candidate_entry_count": len(candidate_entries),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    if not quality_gate["passed"]:
        raise RuntimeError(f"data quality gate failed: {quality_gate}")

    config28 = base.V35Config()
    config14 = replace(config28, adx_window=14)
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features28 = signal_engine.build_signals(
        base.build_features(frame, config28),
        config28,
        flags,
    )
    features14 = signal_engine.build_signals(
        base.build_features(frame, config14),
        config14,
        flags,
    )

    entry14_exit28 = features14.copy()
    entry14_exit28["adx"] = features28["adx"]
    entry28_exit14 = features28.copy()
    entry28_exit14["adx"] = features14["adx"]

    v35_1_results: list[base.RunResult] = []
    for name, config, features in (
        ("v35_1_adx28_base", config28, features28),
        ("v35_1_adx14_full", config14, features14),
    ):
        result, _ = partial_engine.run_backtest(
            spec=partial_engine.PartialSpec(name, None, 0.0, "short_only"),
            frame=frame,
            funding=funding,
            features=features,
            config=config,
            cooldown_bars=0,
        )
        v35_1_results.append(result)

    run_inputs = (
        ("v35_3_adx28_base", config28, features28),
        ("v35_3_adx14_full", config14, features14),
        ("v35_3_adx14_entry_only", config14, entry14_exit28),
        ("v35_3_adx14_exit_only", config28, entry28_exit14),
    )
    results: list[tuple[base.RunResult, dict[str, Any], base.V35Config]] = []
    for name, config, features in run_inputs:
        result, audit = stop_engine.run_backtest(
            spec=v35_3_spec(name),
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        results.append((result, audit, config))

    baseline = results[0][0]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "reference_versions": ["HYPE-EMA-TB-V35.1", "HYPE-EMA-TB-V35.3"],
        "audit_id": "V35.1/V35.3 ADX14 replacement",
        "run_date": "2026-07-21",
        "status": "diagnostic_only_not_promoted",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "market": "Binance USD-M HYPEUSDT perpetual 15m",
            "change_under_test": (
                "Replace the 15m ADX/DI calculation window 28 with 14 while "
                "keeping long>=28, short>=36 and exit<22 thresholds unchanged."
            ),
            "decomposition": (
                "Full replacement plus entry-only and exit-only hybrids; "
                "hybrids are attribution diagnostics, not deployable versions."
            ),
            "unchanged": (
                "V35.3 EMA/volume/1h confirms, sizing, TP5, long SL6.75, "
                "short SL5.7, short MFE4.4 reduce75%, timeout384 and cooldown0."
            ),
            "costs": (
                "0.00085 per filled allocation on entry, partial and final "
                "exit; Binance funding on remaining allocation."
            ),
            "selection": (
                "ADX14 was user-requested; standard recent slices are audit-only. "
                "No ADX14 threshold recalibration was performed."
            ),
        },
        "signal_flags": asdict(flags),
        "v35_1_reference_check": [
            {
                "name": result.name,
                "metrics": result.metrics,
                "standard_slices": result.slices,
                "open_position": result.open_position,
                "comparison_to_v35_1_adx28_base": (
                    None
                    if index == 0
                    else stop_engine.comparison(result, v35_1_results[0])
                ),
                "entry_path_comparison": (
                    None
                    if index == 0
                    else path_comparison(result, v35_1_results[0])
                ),
            }
            for index, result in enumerate(v35_1_results)
        ],
        "runs": [],
    }
    for result, audit, config in results:
        summary["runs"].append(
            {
                "name": result.name,
                "config": asdict(config),
                "metrics": result.metrics,
                "standard_slices": result.slices,
                "open_position": result.open_position,
                "audit": audit,
                "comparison_to_adx28_base": (
                    None
                    if result is baseline
                    else stop_engine.comparison(result, baseline)
                ),
                "entry_path_comparison": (
                    None
                    if result is baseline
                    else path_comparison(result, baseline)
                ),
            }
        )

    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            result.trades.assign(variant=result.name)
            for result in v35_1_results
        ]
        + [result.trades.assign(variant=result.name) for result, _, _ in results],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [result.equity_curve.rename(result.name) for result in v35_1_results]
        + [result.equity_curve.rename(result.name) for result, _, _ in results],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    for result in v35_1_results:
        metrics = result.metrics
        print(
            f"{result.name:>26} {metrics['return_pct']:>10.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"L/S {metrics['long_trades']}/{metrics['short_trades']}"
        )
    for result, _, _ in results:
        metrics = result.metrics
        print(
            f"{result.name:>26} {metrics['return_pct']:>10.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"L/S {metrics['long_trades']}/{metrics['short_trades']}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
