from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as cooldown
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_symmetric_target022_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


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


def leverage_stats(trades: pd.DataFrame) -> dict[str, Any]:
    def stats_for(mask: pd.Series) -> dict[str, Any]:
        allocation = trades.loc[mask, "allocation"].astype(float)
        return {
            "trades": int(len(allocation)),
            "mean": round(float(allocation.mean()), 4),
            "median": round(float(allocation.median()), 4),
            "p90": round(float(allocation.quantile(0.90)), 4),
            "max": round(float(allocation.max()), 4),
            "cap_3x_count": int(np.isclose(allocation, 3.0).sum()),
            "cap_3x_pct": round(
                float(np.isclose(allocation, 3.0).mean() * 100.0),
                2,
            ),
        }

    return {
        "all": stats_for(pd.Series(True, index=trades.index)),
        "long": stats_for(trades["direction"].eq(1)),
        "short": stats_for(trades["direction"].eq(-1)),
    }


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
        "entry_leverage": leverage_stats(run.trades),
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    gate = data_diag.quality_gate(quality)

    v35_config = base.V35Config()
    v39_config = v39.v39_config()
    v39_2_config = replace(v39_config, long_vol_min=0.25)
    symmetric022_config = replace(
        v39_2_config,
        long_target_atr_pct=0.022,
    )
    flags = v39.v39_flags()

    v35_features = base.build_features(frame, v35_config)
    indicator_features = base.build_features(frame, v39_config)
    v39_features = signal_engine.build_signals(
        indicator_features,
        v39_config,
        flags,
    )
    v39_2_features = signal_engine.build_signals(
        indicator_features,
        v39_2_config,
        flags,
    )

    run_inputs = [
        (
            cooldown.RunSpec(
                "v35",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            v35_features,
            v35_config,
        ),
        (
            cooldown.RunSpec(
                "v39",
                cooldown_bars=0,
                use_rsi10_90=False,
            ),
            v39_features,
            v39_config,
        ),
        (
            cooldown.RunSpec(
                "v39_2",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            v39_2_features,
            v39_2_config,
        ),
        (
            cooldown.RunSpec(
                "symmetric_target022_candidate",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            v39_2_features,
            symmetric022_config,
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
    v35_run, v39_run, v39_2_run, symmetric022_run = runs

    canonical_v35 = base.run_backtest(
        "v35_canonical",
        frame,
        funding,
        v35_features,
        v35_config,
        base.ProfitFloorConfig(enabled=False),
    )
    canonical_v39 = base.run_backtest(
        "v39_canonical",
        frame,
        funding,
        v39_features,
        v39_config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_v35 = float(
        (v35_run.equity_curve - canonical_v35.equity_curve).abs().max()
    )
    parity_v39 = float(
        (v39_run.equity_curve - canonical_v39.equity_curve).abs().max()
    )
    if max(parity_v35, parity_v39) > 1e-12:
        raise ValueError(
            f"baseline parity failed: v35={parity_v35}, v39={parity_v39}"
        )

    signatures_match = (
        trade_signature(v39_2_run.trades)
        == trade_signature(symmetric022_run.trades)
    )
    if not signatures_match:
        raise ValueError(
            "long sizing-only change unexpectedly changed trade signatures"
        )

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "candidate_label": "symmetric target 0.022, not registered as V39.3",
        "audit_id": "V39.2 symmetric long/short target 0.022 diagnostic",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v39_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": gate,
            "v35_engine_vs_canonical_max_equity_diff": parity_v35,
            "v39_engine_vs_canonical_max_equity_diff": parity_v39,
            "v39_2_vs_candidate_trade_signatures_match": signatures_match,
        },
        "assumptions": {
            "test_change": (
                "Change only V39.2 long_target_atr_pct from 0.020 to 0.022, "
                "making long and short target ATR percentages symmetric."
            ),
            "candidate_identity": (
                "The symmetric 0.022 row is diagnostic only. It is not "
                "registered as HYPE-EMA-TB-V39.3."
            ),
            "unchanged": (
                "V39.2 long_vol_min=0.25, cooldown1, short target 0.022, "
                "signal filters, K0/K1/K2 timing, 5ATR TP, 7ATR SL, "
                "ADX22 delayed3, 384-bar timeout, 0.00085/fill and funding."
            ),
        },
        "configs": {
            "v35": asdict(v35_config),
            "v39": asdict(v39_config),
            "v39_2": asdict(v39_2_config),
            "symmetric022_candidate": asdict(symmetric022_config),
            "v39_signal_flags": asdict(flags),
        },
        "runs": [
            summarize_run(run, v39_2_run)
            for run in runs
        ],
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
        f"parity v35={parity_v35:.2e} v39={parity_v39:.2e} "
        f"candidate_signatures_match={signatures_match}"
    )
    print(
        f"{'variant':>34}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}  "
        f"{'meanLev':>8}  {'longLev':>8}  {'shortLev':>9}"
    )
    for run in runs:
        metrics = run.metrics
        leverage = leverage_stats(run.trades)
        print(
            f"{run.name:>34}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}  "
            f"{leverage['all']['mean']:>8.4f}  "
            f"{leverage['long']['mean']:>8.4f}  "
            f"{leverage['short']['mean']:>9.4f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
