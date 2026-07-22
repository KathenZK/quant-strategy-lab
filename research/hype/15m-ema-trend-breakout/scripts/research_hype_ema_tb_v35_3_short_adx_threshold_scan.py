"""扫描 V35.3 空头 15m ADX28 入场阈值。"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_short_adx_threshold_scan_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
THRESHOLDS = (28.0, 30.0, 32.0, 34.0, 35.0, 36.0, 37.0, 38.0)


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    base_config = base.V35Config()
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    outputs = []
    for threshold in THRESHOLDS:
        config = replace(base_config, short_adx_min=threshold)
        features = signal_engine.build_signals(
            base.build_features(frame, config),
            config,
            flags,
        )
        run, audit = stop_engine.run_backtest(
            spec=stop_engine.StopPartialSpec(
                name=f"short_adx_{threshold:g}",
                trigger_atr=None,
                fraction_of_remaining=1.0,
                long_trigger_atr=6.75,
                short_trigger_atr=5.70,
            ),
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        outputs.append((threshold, config, run, audit))

    baseline = next(run for threshold, _, run, _ in outputs if threshold == 36.0)
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 short 15m ADX28 threshold scan",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "only_change": "Short 15m ADX28 entry threshold.",
            "thresholds": list(THRESHOLDS),
            "unchanged": (
                "V35.3 long ADX28, 1h long filters, sizing, long SL6.75, "
                "short SL5.7, short MFE4.4 reduce 75%, and all other rules."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
        },
        "runs": [
            {
                "threshold": threshold,
                "config": asdict(config),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "comparison_to_adx36": (
                    None
                    if threshold == 36.0
                    else stop_engine.comparison(run, baseline)
                ),
            }
            for threshold, config, run, audit in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            run.trades.assign(short_adx_threshold=threshold)
            for threshold, _, run, _ in outputs
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [run.equity_curve.rename(run.name) for _, _, run, _ in outputs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    print(
        f"{'threshold':>9} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'shorts':>6}"
    )
    for threshold, _, run, _ in outputs:
        metrics = run.metrics
        print(
            f"{threshold:>9.1f} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} {metrics['short_trades']:>6}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
