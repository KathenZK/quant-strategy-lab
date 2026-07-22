"""扫描 V35.3 空头上一根已完成 1h K 的 ADX / DI 确认。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

import research_hype_ema_tb_v35_2_short_partial_stop_scan as stop_engine
import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_3_short_h1_confirmation_scan_2026-07-20"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


@dataclass(frozen=True, slots=True)
class ConfirmationSpec:
    name: str
    h1_adx_min: float | None
    require_h1_bear_di: bool


def specs() -> tuple[ConfirmationSpec, ...]:
    return (
        ConfirmationSpec("v35_3_base", None, False),
        ConfirmationSpec("h1_adx_gt_14", 14.0, False),
        ConfirmationSpec("h1_adx_gt_18", 18.0, False),
        ConfirmationSpec("h1_adx_gt_22", 22.0, False),
        ConfirmationSpec("h1_bear_di", None, True),
        ConfirmationSpec("h1_adx_gt_14_bear_di", 14.0, True),
        ConfirmationSpec("h1_adx_gt_18_bear_di", 18.0, True),
        ConfirmationSpec("h1_adx_gt_22_bear_di", 22.0, True),
    )


def apply_confirmation(
    features: pd.DataFrame,
    spec: ConfirmationSpec,
) -> pd.DataFrame:
    out = features.copy()
    short_signal = out["short_signal"].copy()
    if spec.h1_adx_min is not None:
        short_signal &= out["h1_adx"].gt(spec.h1_adx_min)
    if spec.require_h1_bear_di:
        short_signal &= out["h1_minus_di"].gt(out["h1_plus_di"])
    out["short_signal"] = short_signal
    return out


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)
    config = base.V35Config()
    raw_features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        signal_engine.SignalFlags(short_use_h1_ema=False),
    )
    outputs = []
    for run_spec in specs():
        features = apply_confirmation(raw_features, run_spec)
        run, audit = stop_engine.run_backtest(
            spec=stop_engine.StopPartialSpec(
                name=run_spec.name,
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
        outputs.append((run_spec, run, audit))

    baseline = outputs[0][1]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V35.3",
        "audit_id": "V35.3 short previous-completed-1h ADX/DI confirmation scan",
        "run_date": "2026-07-20",
        "status": "diagnostic_only_v35_3_unchanged",
        "data_quality": quality,
        "gates": {"data_quality": quality_gate},
        "assumptions": {
            "only_change": (
                "Add short filters using the previous completed 1h candle: "
                "ADX21 threshold, -DI21>+DI21, or both."
            ),
            "adx_thresholds": [14.0, 18.0, 22.0],
            "unchanged": (
                "V35.3 15m entries, sizing, long SL6.75, short SL5.7, "
                "short MFE4.4 reduce 75%, and all exit rules."
            ),
            "costs": (
                "0.00085 per filled allocation; Binance funding applies to "
                "remaining allocation."
            ),
        },
        "runs": [
            {
                "spec": asdict(run_spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "comparison_to_v35_3": (
                    None
                    if run_spec.name == "v35_3_base"
                    else stop_engine.comparison(run, baseline)
                ),
            }
            for run_spec, run, audit in outputs
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
        f"rows={quality['rows']} quality_gate={quality_gate['passed']}"
    )
    print(
        f"{'variant':>26} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'shorts':>6}"
    )
    for _, run, _ in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>26} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} {metrics['short_trades']:>6}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
