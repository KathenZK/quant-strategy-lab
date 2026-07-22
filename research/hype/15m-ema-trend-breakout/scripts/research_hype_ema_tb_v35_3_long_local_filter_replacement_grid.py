"""用更严格的 15m ADX/成交量替代 V35.3 多头两项 1h 确认。"""

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
OUT_STEM = "hype_ema_tb_v35_3_long_local_filter_replacement_grid_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
ADX_THRESHOLDS = tuple(float(value) for value in range(28, 37))
VOLUME_THRESHOLDS = (0.25, 0.35, 0.50, 0.75, 1.00)


def run_one(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    features: pd.DataFrame,
    config: base.V35Config,
) -> tuple[base.RunResult, dict[str, object]]:
    return stop_engine.run_backtest(
        spec=stop_engine.StopPartialSpec(
            name=name,
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


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    base_config = base.V35Config()
    raw_features = base.build_features(frame, base_config)

    baseline_features = signal_engine.build_signals(
        raw_features,
        base_config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )
    baseline, baseline_audit = run_one(
        "v35_3_base",
        frame,
        funding,
        baseline_features,
        base_config,
    )

    outputs = []
    replacement_flags = signal_engine.SignalFlags(
        long_use_h1_di=False,
        short_use_h1_ema=False,
    )
    for adx_threshold in ADX_THRESHOLDS:
        for volume_threshold in VOLUME_THRESHOLDS:
            config = replace(
                base_config,
                long_adx_min=adx_threshold,
                long_vol_min=volume_threshold,
                h1_long_adx_min=-1.0,
            )
            features = signal_engine.build_signals(
                raw_features,
                config,
                replacement_flags,
            )
            name = (
                f"local_adx_{adx_threshold:g}_"
                f"vol_{volume_threshold:g}"
            )
            run, audit = run_one(
                name,
                frame,
                funding,
                features,
                config,
            )
            outputs.append(
                (adx_threshold, volume_threshold, config, run, audit)
            )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 replace long 1h confirmations with local ADX/volume grid",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "removed": [
                "previous completed 1h ADX21>18",
                "previous completed 1h +DI21>-DI21",
            ],
            "grid": {
                "long_15m_adx28_min": list(ADX_THRESHOLDS),
                "long_volume_surge_min": list(VOLUME_THRESHOLDS),
                "volume_ratio_equivalent": [
                    1.0 + value for value in VOLUME_THRESHOLDS
                ],
            },
            "unchanged": (
                "V35.3 short entry, sizing, long SL6.75, short SL5.7, "
                "short MFE4.4 reduce 75%, and all exit rules."
            ),
            "selection_note": (
                "The full window is used for this diagnostic grid search; "
                "recent slices are audit only. Any winner is in-sample."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
        },
        "baseline": {
            "config": asdict(base_config),
            "metrics": baseline.metrics,
            "standard_slices": baseline.slices,
            "audit": baseline_audit,
        },
        "runs": [
            {
                "long_adx_min": adx_threshold,
                "long_volume_surge_min": volume_threshold,
                "volume_ratio_equivalent": 1.0 + volume_threshold,
                "config": asdict(config),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "comparison_to_v35_3": stop_engine.comparison(run, baseline),
            }
            for adx_threshold, volume_threshold, config, run, audit in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    pd.concat(
        [
            baseline.trades.assign(variant=baseline.name),
            *[
                run.trades.assign(variant=run.name)
                for _, _, _, run, _ in outputs
            ],
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [
            baseline.equity_curve.rename(baseline.name),
            *[
                run.equity_curve.rename(run.name)
                for _, _, _, run, _ in outputs
            ],
        ],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    ranked = sorted(
        outputs,
        key=lambda item: (
            item[3].metrics["return_pct"],
            item[3].metrics["sharpe"],
        ),
        reverse=True,
    )
    metrics = baseline.metrics
    print(
        f"data: {quality['start']} ~ {quality['end']} "
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    print(
        f"baseline return={metrics['return_pct']:.2f}% "
        f"maxDD={metrics['max_drawdown_pct']:.2f}% "
        f"sharpe={metrics['sharpe']:.2f} trades={metrics['trades']}"
    )
    print(
        f"{'adx':>5} {'volume':>7} {'ratio':>6} {'return%':>10} "
        f"{'maxDD%':>8} {'sharpe':>7} {'trades':>6} {'win%':>7}"
    )
    for adx_threshold, volume_threshold, _, run, _ in ranked[:15]:
        metrics = run.metrics
        print(
            f"{adx_threshold:>5.1f} {volume_threshold:>7.2f} "
            f"{1.0 + volume_threshold:>6.2f} "
            f"{metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f}"
        )
    strict_winners = [
        item
        for item in outputs
        if item[3].metrics["return_pct"] >= baseline.metrics["return_pct"]
        and item[3].metrics["max_drawdown_pct"]
        >= baseline.metrics["max_drawdown_pct"]
        and item[3].metrics["sharpe"] >= baseline.metrics["sharpe"]
    ]
    print(f"strict_winners={len(strict_winners)}")
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
