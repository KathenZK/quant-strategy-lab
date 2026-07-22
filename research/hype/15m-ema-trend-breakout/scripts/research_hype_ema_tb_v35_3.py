"""冻结并回测 HYPE-EMA-TB-V35.3。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


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
    baseline_spec = stop_engine.StopPartialSpec(
        name="v35_2_base",
        trigger_atr=None,
        fraction_of_remaining=0.0,
    )
    v35_3_spec = stop_engine.StopPartialSpec(
        name="v35_3",
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
    )
    baseline, baseline_audit = stop_engine.run_backtest(
        spec=baseline_spec,
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    candidate, candidate_audit = stop_engine.run_backtest(
        spec=v35_3_spec,
        frame=frame,
        funding=funding,
        features=features,
        config=config,
    )
    canonical, _ = partial.run_backtest(
        spec=partial.PartialSpec(
            "v35_2_canonical",
            stop_engine.PROFIT_TRIGGER_ATR,
            stop_engine.PROFIT_FRACTION,
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
        "registered_variant": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 asymmetric static stops",
        "run_date": "2026-07-20",
        "status": "supporting_evidence_for_registered_v35_3",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_v35_2_baseline_max_equity_diff": (
                parity_diff
            ),
        },
        "assumptions": {
            "identity": (
                "V35.2 plus long SL6.75ATR and short SL5.7ATR; short "
                "MFE4.4ATR reduce 75% remains enabled."
            ),
            "execution": (
                "Entry-ATR anchored intrabar static stops; stop-first; full "
                "exit releases the position slot; cooldown0."
            ),
            "unchanged": (
                "V35.2 entries, target sizing, TP5, ADX22 delayed3, "
                "MFE1.5 indicator-exit disable and timeout384."
            ),
            "costs": (
                "0.00085 per filled allocation on entry, partial and final "
                "exit; Binance funding applies to remaining allocation."
            ),
            "selection": (
                "Both stop values were selected on the same full sample; "
                "standard slices are audit-only and not independent OOS."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            {
                "spec": asdict(baseline_spec),
                "metrics": baseline.metrics,
                "standard_slices": baseline.slices,
                "open_position": baseline.open_position,
                "audit": baseline_audit,
                "comparison_to_v35_2": None,
            },
            {
                "spec": asdict(v35_3_spec),
                "metrics": candidate.metrics,
                "standard_slices": candidate.slices,
                "open_position": candidate.open_position,
                "audit": candidate_audit,
                "comparison_to_v35_2": stop_engine.comparison(
                    candidate,
                    baseline,
                ),
            },
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
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
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']} "
        f"parity={parity_diff:.2e}"
    )
    for run, audit in (
        (baseline, baseline_audit),
        (candidate, candidate_audit),
    ):
        metrics = run.metrics
        print(
            f"{run.name:>12} {metrics['return_pct']:>10.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"stops={audit['stop_partial_events']}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
