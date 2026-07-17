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
import research_hype_ema_tb_v39_cooldown1 as path_engine
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_long_vol020_2026-07-17"
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
        "comparison_to_v39_2": (
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
    v39_2_config = replace(current_config, long_vol_min=0.25)
    vol020_config = replace(current_config, long_vol_min=0.20)
    flags = v39.v39_flags()
    indicator_features = base.build_features(frame, current_config)
    current_features = signal_engine.build_signals(
        indicator_features,
        current_config,
        flags,
    )
    v39_2_features = signal_engine.build_signals(
        indicator_features,
        v39_2_config,
        flags,
    )
    vol020_features = signal_engine.build_signals(
        indicator_features,
        vol020_config,
        flags,
    )

    run_inputs = [
        (
            cooldown.RunSpec(
                "v39_current",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            current_features,
            current_config,
        ),
        (
            cooldown.RunSpec(
                "v39_2_long_vol025_cooldown1",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            v39_2_features,
            v39_2_config,
        ),
        (
            cooldown.RunSpec(
                "long_vol020_no_cooldown",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            vol020_features,
            vol020_config,
        ),
        (
            cooldown.RunSpec(
                "long_vol020_cooldown1",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            vol020_features,
            vol020_config,
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
    current, v39_2, vol020_no_cooldown, vol020_cooldown1 = runs

    canonical_runs = [
        base.run_backtest(
            f"{run.name}_canonical",
            frame,
            funding,
            features,
            config,
            base.ProfitFloorConfig(enabled=False),
        )
        for run, (_, features, config) in zip(
            (current, vol020_no_cooldown),
            (run_inputs[0], run_inputs[2]),
            strict=True,
        )
    ]
    parity_current = float(
        (
            current.equity_curve
            - canonical_runs[0].equity_curve
        )
        .abs()
        .max()
    )
    parity_vol020 = float(
        (
            vol020_no_cooldown.equity_curve
            - canonical_runs[1].equity_curve
        )
        .abs()
        .max()
    )
    if max(parity_current, parity_vol020) > 1e-12:
        raise ValueError(
            "baseline parity failed: "
            f"current={parity_current}, vol020={parity_vol020}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "audit_id": "V39.2 long volume threshold 0.20 diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_not_registered",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "current_v39_parity_max_equity_diff": parity_current,
            "long_vol020_no_cooldown_parity_max_equity_diff": (
                parity_vol020
            ),
        },
        "assumptions": {
            "v39_2": (
                "V39 with long_vol_min=0.25 and one-bar post-exit cooldown."
            ),
            "test_change": (
                "Change only V39.2 long_vol_min from 0.25 to 0.20. "
                "The primary test retains cooldown1; a no-cooldown row "
                "isolates the volume-threshold effect."
            ),
            "unchanged": (
                "V39 short_target_atr_pct=0.022, short_use_h1_ema=False, "
                "K0/K1/K2 timing, sizing, 5ATR TP, 7ATR SL, ADX22 delayed3, "
                "384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "configs": {
            "v39_current": asdict(current_config),
            "v39_2": asdict(v39_2_config),
            "long_vol020": asdict(vol020_config),
            "signal_flags": asdict(flags),
        },
        "runs": [summarize_run(run, v39_2) for run in runs],
        "path_audits": {
            "v39_2_vs_long_vol020_cooldown1": (
                path_engine.trade_path_audit(
                    v39_2,
                    vol020_cooldown1,
                )
            ),
            "long_vol020_no_cooldown_vs_cooldown1": (
                path_engine.trade_path_audit(
                    vol020_no_cooldown,
                    vol020_cooldown1,
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
        f"parity current={parity_current:.2e} vol020={parity_vol020:.2e}"
    )
    print(
        f"{'variant':>32}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}  "
        f"{'vsV39.2%':>10}"
    )
    for run in runs:
        retained = (
            100.0
            if run is v39_2
            else cooldown.comparison(run, v39_2)[
                "final_equity_retained_pct"
            ]
        )
        metrics = run.metrics
        print(
            f"{run.name:>32}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  {retained:>10.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
