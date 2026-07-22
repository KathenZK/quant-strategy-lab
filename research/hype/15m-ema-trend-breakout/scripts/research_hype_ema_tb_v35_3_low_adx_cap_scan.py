"""扫描 V35.3 低 ADX 入场仓位 cap。"""

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
OUT_STEM = "hype_ema_tb_v35_3_low_adx_cap_scan_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def spec(
    name: str,
    threshold: float | None = None,
    cap: float | None = None,
) -> stop_engine.StopPartialSpec:
    return stop_engine.StopPartialSpec(
        name=name,
        trigger_atr=None,
        fraction_of_remaining=1.0,
        long_trigger_atr=6.75,
        short_trigger_atr=5.70,
        low_adx_threshold=threshold,
        low_adx_max_allocation=cap,
    )


def specs() -> tuple[stop_engine.StopPartialSpec, ...]:
    return (
        spec("v35_3_base"),
        spec("adx32_cap25", 32.0, 2.5),
        spec("adx34_cap25", 34.0, 2.5),
        spec("adx35_cap275", 35.0, 2.75),
        spec("adx35_cap25", 35.0, 2.5),
        spec("adx35_cap225", 35.0, 2.25),
        spec("adx35_cap2", 35.0, 2.0),
        spec("adx36_cap25", 36.0, 2.5),
    )


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
            run_spec,
            *stop_engine.run_backtest(
                spec=run_spec,
                frame=frame,
                funding=funding,
                features=features,
                config=config,
            ),
        )
        for run_spec in run_specs
    ]
    baseline = outputs[0][1]
    v35_2_reference, _ = stop_engine.run_backtest(
        spec=stop_engine.StopPartialSpec(
            "v35_2_reference",
            None,
            0.0,
        ),
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
        (
            canonical.equity_curve
            - v35_2_reference.equity_curve
        )
        .abs()
        .max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35.2 engine parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 low-ADX allocation cap scan",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "v35_2_canonical_vs_shared_engine_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "overlay": (
                "At K0 signal close, if ADX28 is below the threshold, cap "
                "the K2 entry allocation; signals and exits are unchanged."
            ),
            "base": (
                "Registered V35.3: long SL6.75, short SL5.7, short "
                "MFE4.4 reduce 75%, cooldown0."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
            "selection": (
                "Grid and all standard slices use the same full sample; "
                "results are diagnostic, not independent OOS."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            {
                "spec": asdict(run_spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "comparison_to_v35_3": (
                    None
                    if run is baseline
                    else stop_engine.comparison(run, baseline)
                ),
            }
            for run_spec, run, audit in outputs
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
        f"{'variant':>18} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'capped':>7}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>18} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['low_adx_capped_entries']:>7}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
