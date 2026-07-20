"""V39.2 空单单级分批止盈诊断。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39
import research_hype_ema_tb_v39_short_partial_take_profit as v39_partial


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_short_partial_take_profit_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def specs() -> tuple[partial.PartialSpec, ...]:
    rows = [partial.PartialSpec("v39_2_base", None, 0.0)]
    for trigger in (4.0, 4.2, 4.4):
        for fraction in (0.50, 2.0 / 3.0, 0.75):
            rows.append(
                partial.PartialSpec(
                    f"v39_2_short_{trigger:g}_{fraction:.3f}",
                    trigger,
                    fraction,
                    "short_only",
                )
            )
    return tuple(rows)


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
    run_specs = specs()
    outputs = [
        (
            spec,
            *partial.run_backtest(
                spec=spec,
                frame=frame,
                funding=funding,
                features=features,
                config=config,
                cooldown_bars=1,
            ),
        )
        for spec in run_specs
    ]
    baseline = outputs[0][1]
    canonical = cooldown.run_backtest(
        spec=cooldown.RunSpec(
            name="v39_2_canonical",
            cooldown_bars=1,
            use_rsi10_90=False,
        ),
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise ValueError(f"V39.2 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "registered_variant": "HYPE-EMA-TB-V39.4",
        "audit_id": "V39.2 short-only one-stage partial take-profit",
        "run_date": "2026-07-17",
        "status": "supporting_evidence_for_registered_v39_4",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_baseline_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "partial_fill": (
                "One reduce-only short partial fill at an entry-ATR fixed "
                "target; remaining allocation keeps V39.2 TP5/SL7."
            ),
            "same_bar_order": (
                "Stop-first; without a stop hit, partial target fills before "
                "TP5 when both are touched in one bar."
            ),
            "path": (
                "Partial fill does not close the strategy position; V39.2 "
                "cooldown1 starts only after the final exit."
            ),
            "unchanged": (
                "V39.2 long_vol_min=0.25, short target 0.022, no short 1h "
                "EMA confirm, K0/K1/K2 timing, TP5/SL7, ADX22 delayed3, "
                "MFE1.5 indicator-exit disable, timeout384 and cooldown1."
            ),
            "cost": (
                "0.00085 per filled allocation on entry, partial and final "
                "exit; funding applies to remaining allocation."
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
                "payoff": v39_partial.payoff_stats(run.trades),
                "comparison_to_v39_2": v39_partial.compare_to_base(
                    run,
                    baseline,
                ),
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
        f"{'variant':>30} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'partials':>8}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>30} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['partial_events']:>8}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
