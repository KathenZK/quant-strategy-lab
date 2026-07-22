"""比较 HYPE-EMA-TB-V35.1 与空头 4.4ATR 减仓 75% 变体。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_1_short_partial_4_4_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def comparison(
    candidate: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any]:
    return {
        "final_equity_retained_pct": round(
            100.0
            * (1.0 + candidate.metrics["return_pct"] / 100.0)
            / (1.0 + baseline.metrics["return_pct"] / 100.0),
            2,
        ),
        "return_delta_pp": round(
            candidate.metrics["return_pct"]
            - baseline.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            candidate.metrics["max_drawdown_pct"]
            - baseline.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            candidate.metrics["sharpe"]
            - baseline.metrics["sharpe"],
            2,
        ),
        "win_rate_delta_pp": round(
            candidate.metrics["win_rate_pct"]
            - baseline.metrics["win_rate_pct"],
            2,
        ),
    }


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
    baseline_spec = partial.PartialSpec(
        "v35_1_base",
        None,
        0.0,
    )
    candidate_spec = partial.PartialSpec(
        "v35_1_short_4_4_reduce_75",
        4.4,
        0.75,
        "short_only",
    )
    baseline, baseline_audit = partial.run_backtest(
        spec=baseline_spec,
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=0,
    )
    candidate, candidate_audit = partial.run_backtest(
        spec=candidate_spec,
        frame=frame,
        funding=funding,
        features=features,
        config=config,
        cooldown_bars=0,
    )
    canonical = base.run_backtest(
        "v35_1_canonical",
        frame,
        funding,
        features,
        config,
        base.ProfitFloorConfig(enabled=False),
    )
    parity_diff = float(
        (canonical.equity_curve - baseline.equity_curve).abs().max()
    )
    if parity_diff > 1e-12:
        raise RuntimeError(f"V35.1 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.1",
        "registered_variant": "HYPE-EMA-TB-V35.2",
        "audit_id": "V35.1 short MFE4.4ATR reduce 75%",
        "run_date": "2026-07-20",
        "status": "supporting_evidence_for_registered_v35_2",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_partial_engine_baseline_max_equity_diff": (
                parity_diff
            ),
        },
        "assumptions": {
            "test_change": (
                "Only shorts: when intrabar MFE reaches 4.4 entry ATR, "
                "reduce-only close 75% of initial allocation once; the "
                "remaining 25% keeps V35.1 TP5/SL7 and state."
            ),
            "same_bar_order": (
                "Stop-first. If stop is not hit and 4.4ATR plus TP5 are "
                "both touched, fill the partial first and TP the remainder."
            ),
            "path": (
                "The partial fill does not release the strategy position, "
                "increase trade count, permit reentry or start a cooldown."
            ),
            "unchanged": (
                "V35.1 short target 0.018, cooldown0, no short 1h EMA "
                "confirmation, K0/K1/K2 timing, TP5/SL7, ADX22 delayed3, "
                "MFE1.5 indicator-exit disable and timeout384."
            ),
            "costs": (
                "0.00085 per filled allocation on entry, partial and final "
                "exit; Binance funding applies only to remaining allocation."
            ),
            "slice_selection": (
                "1d/7d/1m/3m/6m/1y slices are anchored to the dataset end "
                "and are audit-only, not used for parameter selection."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            {
                "spec": asdict(baseline_spec),
                "metrics": baseline.metrics,
                "standard_slices": baseline.slices,
                "open_position": baseline.open_position,
                "audit": baseline_audit,
                "comparison_to_v35_1": None,
            },
            {
                "spec": asdict(candidate_spec),
                "metrics": candidate.metrics,
                "standard_slices": candidate.slices,
                "open_position": candidate.open_position,
                "audit": candidate_audit,
                "comparison_to_v35_1": comparison(
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
        f"rows={quality['rows']} quality_gate={quality_gate['passed']} "
        f"parity={parity_diff:.2e}"
    )
    for run, audit in (
        (baseline, baseline_audit),
        (candidate, candidate_audit),
    ):
        metrics = run.metrics
        print(
            f"{run.name:>32} {metrics['return_pct']:>10.2f}% "
            f"dd {metrics['max_drawdown_pct']:>7.2f}% "
            f"sh {metrics['sharpe']:>5.2f} "
            f"n {metrics['trades']:>3} "
            f"win {metrics['win_rate_pct']:>6.2f}% "
            f"partials={audit['partial_events']}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
