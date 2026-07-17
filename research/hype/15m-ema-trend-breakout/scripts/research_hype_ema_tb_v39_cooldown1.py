from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_cooldown1_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def summarize_run(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "comparison_to_v39_base": (
            None if run is baseline else cooldown.comparison(run, baseline)
        ),
    }


def trade_path_audit(
    baseline: base.RunResult,
    candidate: base.RunResult,
) -> dict[str, Any]:
    base_trades = baseline.trades.copy()
    candidate_trades = candidate.trades.copy()
    for trades in (base_trades, candidate_trades):
        trades["_key"] = (
            pd.to_datetime(trades["entry_ts"], utc=True).astype(str)
            + "|"
            + trades["direction"].astype(str)
        )
    base_keys = set(base_trades["_key"])
    candidate_keys = set(candidate_trades["_key"])
    common_keys = base_keys & candidate_keys
    common_base = base_trades.loc[
        base_trades["_key"].isin(common_keys)
    ].set_index("_key")
    common_candidate = candidate_trades.loc[
        candidate_trades["_key"].isin(common_keys)
    ].set_index("_key")
    common_return_max_abs_diff = (
        float(
            (
                common_base["trade_return"]
                - common_candidate["trade_return"]
            )
            .abs()
            .max()
        )
        if common_keys
        else 0.0
    )
    return {
        "common_entry_direction_trades": len(common_keys),
        "v39_base_only_trades": len(base_keys - candidate_keys),
        "v39_cooldown1_only_trades": len(candidate_keys - base_keys),
        "common_trade_return_max_abs_diff": common_return_max_abs_diff,
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    gate = data_diag.quality_gate(quality)
    config = v39.v39_config()
    flags = v39.v39_flags()
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )

    specs = [
        cooldown.RunSpec(
            "v39_base",
            cooldown_bars=0,
            use_rsi10_90=False,
        ),
        cooldown.RunSpec(
            "v39_cooldown1",
            cooldown_bars=1,
            use_rsi10_90=False,
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
        for spec in specs
    ]
    baseline, candidate = runs

    canonical = base.run_backtest(
        "v39_canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_max_equity_diff = float(
        (baseline.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_max_equity_diff > 1e-12:
        raise ValueError(
            f"baseline parity failed: max equity diff={parity_max_equity_diff}"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V39",
        "audit_id": "one-bar post-exit cooldown diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_not_registered",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "baseline_vs_canonical_max_equity_diff": parity_max_equity_diff,
        },
        "assumptions": {
            "cooldown1": (
                "After an exit on bar E, block entry on E+1; "
                "the earliest permitted new entry is E+2 open."
            ),
            "unchanged": (
                "V39 signals and parameters, K0/K1/K2 timing, sizing, "
                "5ATR TP, 7ATR SL, ADX22 delayed3, 384-bar timeout, "
                "0.00085/fill and funding."
            ),
        },
        "v39_config": asdict(config),
        "v39_signal_flags": asdict(flags),
        "run_specs": [asdict(spec) for spec in specs],
        "runs": [summarize_run(run, baseline) for run in runs],
        "trade_path_audit": trade_path_audit(baseline, candidate),
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
    print(f"baseline parity max equity diff: {parity_max_equity_diff:.2e}")
    print(
        f"{'variant':>18}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}  {'retained%':>10}"
    )
    for run in runs:
        retained = (
            100.0
            if run is baseline
            else cooldown.comparison(run, baseline)[
                "final_equity_retained_pct"
            ]
        )
        metrics = run.metrics
        print(
            f"{run.name:>18}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  {retained:>10.2f}"
        )
    print(f"path audit: {trade_path_audit(baseline, candidate)}")
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
