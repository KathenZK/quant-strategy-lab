"""扫描 V35.2 仅多头静态硬止损距离。"""

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
OUT_STEM = "hype_ema_tb_v35_2_long_static_stop_scan_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def specs() -> tuple[stop_engine.StopPartialSpec, ...]:
    rows = [
        stop_engine.StopPartialSpec(
            "v35_2_base_long_sl7",
            None,
            0.0,
        )
    ]
    for trigger in (
        4.0,
        4.5,
        5.0,
        5.5,
        5.7,
        6.0,
        6.25,
        6.5,
        6.6,
        6.7,
        6.75,
        6.8,
        6.9,
    ):
        rows.append(
            stop_engine.StopPartialSpec(
                name=f"long_sl_{trigger:g}",
                trigger_atr=trigger,
                fraction_of_remaining=1.0,
                side_mode="long_only",
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
            spec,
            *stop_engine.run_backtest(
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
        "audit_id": "V35.2 long-only static stop scan",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_v35_2_baseline_max_equity_diff": (
                parity_diff
            ),
        },
        "assumptions": {
            "only_change": (
                "Long static hard stop distance; shorts keep SL7 and V35.2 "
                "MFE4.4ATR reduce 75%, all other rules unchanged."
            ),
            "execution": (
                "Entry-ATR anchored intrabar stop; stop-first; a long stop "
                "fully exits and releases the position slot; cooldown0."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
            "selection": (
                "All metrics are in-sample diagnostics; recent slices are "
                "audit-only."
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
                "comparison_to_v35_2": (
                    None
                    if run is baseline
                    else stop_engine.comparison(run, baseline)
                ),
            }
            for spec, run, audit in outputs
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
        f"{'variant':>22} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'stopN':>6}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>22} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['stop_partial_events']:>6}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
