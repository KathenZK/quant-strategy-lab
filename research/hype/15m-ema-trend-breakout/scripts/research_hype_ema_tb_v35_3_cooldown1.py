"""复测 V35.3 最终平仓后的 1 根 15m K 冷却。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_cooldown1_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def run_variant(
    name: str,
    cooldown_bars: int,
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
        cooldown_bars=cooldown_bars,
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )
    baseline, baseline_audit = run_variant(
        "v35_3_base",
        0,
        frame,
        funding,
        features,
        config,
    )
    candidate, candidate_audit = run_variant(
        "v35_3_cooldown1",
        1,
        frame,
        funding,
        features,
        config,
    )
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 final-exit cooldown1",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "only_change": (
                "After final exit on bar E, block entry on E+1; the earliest "
                "new entry is E+2 open if its delayed signal is valid."
            ),
            "partial_behavior": (
                "The short MFE4.4 reduce-only fill does not release the "
                "position and does not start cooldown."
            ),
            "unchanged": (
                "V35.3 signals, sizing, K0/K1/K2 timing, long SL6.75, "
                "short SL5.7, short MFE4.4 reduce 75%, and all exits."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
        },
        "runs": [
            {
                "name": baseline.name,
                "cooldown_bars": 0,
                "metrics": baseline.metrics,
                "standard_slices": baseline.slices,
                "open_position": baseline.open_position,
                "audit": baseline_audit,
                "comparison_to_v35_3": None,
            },
            {
                "name": candidate.name,
                "cooldown_bars": 1,
                "metrics": candidate.metrics,
                "standard_slices": candidate.slices,
                "open_position": candidate.open_position,
                "audit": candidate_audit,
                "comparison_to_v35_3": stop_engine.comparison(
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
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    print(
        f"{'variant':>20} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7}"
    )
    for run in (baseline, candidate):
        metrics = run.metrics
        print(
            f"{run.name:>20} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
