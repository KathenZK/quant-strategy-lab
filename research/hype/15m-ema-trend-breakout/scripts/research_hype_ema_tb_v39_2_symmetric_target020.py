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
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_symmetric_target020_2026-07-17"
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


def trade_signature(trades: pd.DataFrame) -> list[tuple[Any, ...]]:
    columns = [
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "exit_reason",
        "entry_atr",
        "hold_bars",
    ]
    return list(trades[columns].itertuples(index=False, name=None))


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    gate = data_diag.quality_gate(quality)

    v39_2_config = replace(v39.v39_config(), long_vol_min=0.25)
    symmetric_config = replace(
        v39_2_config,
        short_target_atr_pct=0.020,
    )
    flags = v39.v39_flags()
    indicator_features = base.build_features(frame, v39_2_config)
    features = signal_engine.build_signals(
        indicator_features,
        v39_2_config,
        flags,
    )

    specs = [
        (
            cooldown.RunSpec(
                "v39_2_short_target022",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            v39_2_config,
        ),
        (
            cooldown.RunSpec(
                "v39_2_symmetric_target020",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            symmetric_config,
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
        for spec, config in specs
    ]
    baseline, symmetric = runs

    no_cooldown = cooldown.run_backtest(
        spec=cooldown.RunSpec(
            "v39_2_no_cooldown_parity",
            cooldown_bars=0,
            use_rsi10_90=False,
        ),
        frame=frame,
        funding=funding,
        features=features,
        config=v39_2_config,
    )
    canonical = base.run_backtest(
        "v39_2_canonical",
        frame,
        funding,
        features,
        v39_2_config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_max_equity_diff = float(
        (no_cooldown.equity_curve - canonical.equity_curve).abs().max()
    )
    if parity_max_equity_diff > 1e-12:
        raise ValueError(
            f"baseline parity failed: max diff={parity_max_equity_diff}"
        )

    signatures_match = (
        trade_signature(baseline.trades)
        == trade_signature(symmetric.trades)
    )
    if not signatures_match:
        raise ValueError(
            "sizing-only change unexpectedly changed the trade signature"
        )

    long_mask = baseline.trades["direction"].eq(1)
    short_mask = baseline.trades["direction"].eq(-1)
    trade_return_audit = {
        "long_trade_count": int(long_mask.sum()),
        "short_trade_count": int(short_mask.sum()),
        "long_trade_return_max_abs_diff": float(
            (
                baseline.trades.loc[long_mask, "trade_return"]
                - symmetric.trades.loc[long_mask, "trade_return"]
            )
            .abs()
            .max()
        ),
        "short_trade_return_mean_v39_2": float(
            baseline.trades.loc[short_mask, "trade_return"].mean()
        ),
        "short_trade_return_mean_symmetric020": float(
            symmetric.trades.loc[short_mask, "trade_return"].mean()
        ),
    }

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "audit_id": "V39.2 symmetric long/short target 0.020 diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v39_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "no_cooldown_engine_vs_canonical_max_equity_diff": (
                parity_max_equity_diff
            ),
            "sizing_only_trade_signatures_match": signatures_match,
        },
        "assumptions": {
            "test_change": (
                "Change only V39.2 short_target_atr_pct from 0.022 to 0.020, "
                "making long and short target ATR percentages symmetric."
            ),
            "unchanged": (
                "V39.2 long_vol_min=0.25, cooldown1, signal filters, "
                "K0/K1/K2 timing, 5ATR TP, 7ATR SL, ADX22 delayed3, "
                "384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "configs": {
            "v39_2": asdict(v39_2_config),
            "symmetric020": asdict(symmetric_config),
            "signal_flags": asdict(flags),
        },
        "runs": [
            summarize_run(run, baseline)
            for run in runs
        ],
        "trade_return_audit": trade_return_audit,
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
        f"parity={parity_max_equity_diff:.2e} "
        f"trade_signatures_match={signatures_match}"
    )
    print(
        f"{'variant':>30}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}  "
        f"{'retained%':>10}"
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
            f"{run.name:>30}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  {retained:>10.2f}"
        )
    print(f"trade return audit: {trade_return_audit}")
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
