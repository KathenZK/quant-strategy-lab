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
import research_hype_ema_tb_v39_cooldown1 as v39_cooldown
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_long_vol025_cooldown1_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def summarize_run(
    run: base.RunResult,
    reference: base.RunResult,
) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "comparison_to_current_v39_base": (
            None
            if run is reference
            else cooldown.comparison(run, reference)
        ),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    gate = data_diag.quality_gate(quality)

    current_config = v39.v39_config()
    aligned_config = replace(current_config, long_vol_min=0.25)
    flags = v39.v39_flags()
    indicator_features = base.build_features(frame, current_config)
    current_features = signal_engine.build_signals(
        indicator_features,
        current_config,
        flags,
    )
    aligned_features = signal_engine.build_signals(
        indicator_features,
        aligned_config,
        flags,
    )

    run_inputs = [
        (
            cooldown.RunSpec(
                "v39_base",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            current_features,
            current_config,
        ),
        (
            cooldown.RunSpec(
                "v39_cooldown1",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            current_features,
            current_config,
        ),
        (
            cooldown.RunSpec(
                "v39_long_vol025",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            aligned_features,
            aligned_config,
        ),
        (
            cooldown.RunSpec(
                "v39_long_vol025_cooldown1",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            aligned_features,
            aligned_config,
        ),
    ]
    runs = [
        cooldown.run_backtest(
            spec=spec,
            frame=frame,
            funding=funding,
            features=features,
            config=config,
        )
        for spec, features, config in run_inputs
    ]
    current_base, current_cooldown1, aligned_base, aligned_cooldown1 = runs

    canonical_current = base.run_backtest(
        "v39_canonical",
        frame,
        funding,
        current_features,
        current_config,
        base.ProfitFloorConfig(enabled=False),
    )
    canonical_aligned = base.run_backtest(
        "v39_long_vol025_canonical",
        frame,
        funding,
        aligned_features,
        aligned_config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_current = float(
        (
            current_base.equity_curve
            - canonical_current.equity_curve
        )
        .abs()
        .max()
    )
    parity_aligned = float(
        (
            aligned_base.equity_curve
            - canonical_aligned.equity_curve
        )
        .abs()
        .max()
    )
    if max(parity_current, parity_aligned) > 1e-12:
        raise ValueError(
            "baseline parity failed: "
            f"current={parity_current}, aligned={parity_aligned}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V39 diagnostic variant",
        "registered_variant": "HYPE-EMA-TB-V39.2",
        "registered_run_name": "v39_long_vol025_cooldown1",
        "audit_id": "V39 long volume threshold 0.25 and cooldown1 interaction",
        "run_date": "2026-07-17",
        "status": "supporting_evidence_for_registered_v39_2",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "current_v39_baseline_vs_canonical_max_equity_diff": (
                parity_current
            ),
            "long_vol025_baseline_vs_canonical_max_equity_diff": (
                parity_aligned
            ),
        },
        "assumptions": {
            "long_volume_alignment": (
                "Change only V39 long_vol_min from 0.35 to the V35 value "
                "0.25; retain V39 short_target_atr_pct=0.022 and "
                "short_use_h1_ema=False."
            ),
            "cooldown1": (
                "After an exit on bar E, block entry on E+1; "
                "the earliest permitted new entry is E+2 open."
            ),
            "unchanged": (
                "K0/K1/K2 timing, sizing, 5ATR TP, 7ATR SL, "
                "ADX22 delayed3, 384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "current_v39_config": asdict(current_config),
        "long_vol025_config": asdict(aligned_config),
        "v39_signal_flags": asdict(flags),
        "runs": [
            summarize_run(run, current_base)
            for run in runs
        ],
        "path_audits": {
            "current_v39_base_vs_long_vol025": (
                v39_cooldown.trade_path_audit(
                    current_base,
                    aligned_base,
                )
            ),
            "current_v39_cooldown1_vs_long_vol025_cooldown1": (
                v39_cooldown.trade_path_audit(
                    current_cooldown1,
                    aligned_cooldown1,
                )
            ),
            "long_vol025_base_vs_cooldown1": (
                v39_cooldown.trade_path_audit(
                    aligned_base,
                    aligned_cooldown1,
                )
            ),
        },
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
    pd.concat(trade_frames, ignore_index=True).to_csv(
        TRADES_PATH,
        index=False,
    )
    pd.concat(
        [run.equity_curve.rename(run.name) for run in runs],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={gate['passed']}"
    )
    print(
        f"parity current={parity_current:.2e} "
        f"long_vol025={parity_aligned:.2e}"
    )
    print(
        f"{'variant':>30}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}  {'retained%':>10}"
    )
    for run in runs:
        retained = (
            100.0
            if run is current_base
            else cooldown.comparison(run, current_base)[
                "final_equity_retained_pct"
            ]
        )
        metrics = run.metrics
        print(
            f"{run.name:>30}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  {retained:>10.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
