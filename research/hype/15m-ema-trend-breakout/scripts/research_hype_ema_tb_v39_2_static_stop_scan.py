"""扫描 V39.2 的静态硬止损距离，判断 7ATR 是否可温和收窄。"""

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
import research_hype_ema_tb_v39_2_mfe15_stop5 as gap_engine
import research_hype_ema_tb_v39_cooldown1 as path_tools
import research_hype_ema_tb_v39_full_ablation as v39


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_2_static_stop_scan_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"

STOP_GRID = (
    4.0,
    4.5,
    5.0,
    5.5,
    6.0,
    6.25,
    6.5,
    6.55,
    6.6,
    6.65,
    6.7,
    6.75,
    6.8,
    6.85,
    6.9,
    6.95,
    7.0,
)
SELECTED_STOP_ATR = 6.75


def summarize_run(
    run: base.RunResult,
    reference: base.RunResult,
    stop_atr: float,
) -> dict[str, Any]:
    return {
        "stop_atr": stop_atr,
        "metrics": run.metrics,
        "standard_slices": run.slices,
        "open_position": run.open_position,
        "comparison_to_registered_v39_2": (
            None if run is reference else cooldown.comparison(run, reference)
        ),
    }


def risk_geometry(config: base.V35Config, stop_atr: float) -> dict[str, Any]:
    """未触及 3x cap 时，由 target ATR sizing 隐含的毛收益/毛亏损。"""
    result: dict[str, Any] = {}
    for side, target in (
        ("long", config.long_target_atr_pct),
        ("short", config.short_target_atr_pct),
    ):
        result[side] = {
            "uncapped_gross_tp_pct": 100.0 * target * config.take_profit_atr,
            "uncapped_gross_stop_pct": -100.0 * target * stop_atr,
            "tp_required_to_recover_one_stop": (
                stop_atr / config.take_profit_atr
            ),
        }
    return result


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = data_diag.load_data(warehouse)
    quality_gate = data_diag.quality_gate(quality)

    config = replace(v39.v39_config(), long_vol_min=0.25)
    flags = v39.v39_flags()
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )

    runs_by_stop: dict[float, base.RunResult] = {}
    for stop_atr in STOP_GRID:
        stop_config = replace(config, hard_stop_atr=stop_atr)
        runs_by_stop[stop_atr] = cooldown.run_backtest(
            spec=cooldown.RunSpec(
                name=f"v39_2_static_stop_{stop_atr:g}",
                cooldown_bars=1,
                use_rsi10_90=False,
            ),
            frame=frame,
            funding=funding,
            features=features,
            config=stop_config,
        )

    registered = runs_by_stop[7.0]
    selected = runs_by_stop[SELECTED_STOP_ATR]
    gap_selected, gap_audit = gap_engine.run_backtest(
        name="v39_2_static_stop_6_75_gap_open",
        frame=frame,
        funding=funding,
        features=features,
        config=replace(config, hard_stop_atr=SELECTED_STOP_ATR),
        cooldown_bars=1,
        trigger_mfe_atr=None,
        tightened_stop_atr=SELECTED_STOP_ATR,
        gap_open=True,
    )
    gap_equity_diff = float(
        (selected.equity_curve - gap_selected.equity_curve).abs().max()
    )

    baseline_metrics = registered.metrics
    strict_improvements = [
        stop_atr
        for stop_atr, run in runs_by_stop.items()
        if (
            stop_atr < 7.0
            and run.metrics["return_pct"] > baseline_metrics["return_pct"]
            and run.metrics["max_drawdown_pct"]
            > baseline_metrics["max_drawdown_pct"]
            and run.metrics["sharpe"] > baseline_metrics["sharpe"]
        )
    ]
    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39.2",
        "audit_id": "V39.2 static hard-stop ATR scan",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v39_2_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "selected_vs_gap_open_max_equity_diff": gap_equity_diff,
        },
        "assumptions": {
            "test_change": (
                "Change only the entry-anchored static hard stop from 7ATR "
                "to each grid value; the stop is active from entry."
            ),
            "unchanged": (
                "V39.2 long_vol_min=0.25, cooldown1, long target 0.020, "
                "short target 0.022, K0/K1/K2 timing, 5ATR TP, "
                "ADX22 delayed3, MFE1.5 indicator-exit disable, "
                "384-bar timeout, 0.00085/fill and funding."
            ),
            "same_bar_order": "stop-first, then take-profit.",
        },
        "config_at_registered_stop": asdict(config),
        "signal_flags": asdict(flags),
        "stop_grid": list(STOP_GRID),
        "selected_diagnostic_stop_atr": SELECTED_STOP_ATR,
        "strict_full_sample_improvements": strict_improvements,
        "risk_geometry": {
            "registered_7atr": risk_geometry(config, 7.0),
            "selected_6_75atr": risk_geometry(config, SELECTED_STOP_ATR),
            "note": (
                "Ignores fees, funding and the 3x cap. At the cap, changing "
                "stop distance still reduces stop loss only proportionally."
            ),
        },
        "runs": [
            summarize_run(run, registered, stop_atr)
            for stop_atr, run in runs_by_stop.items()
        ],
        "selected_path_audit": path_tools.trade_path_audit(
            registered,
            selected,
        ),
        "gap_open_audit": gap_audit,
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    pd.concat(
        [
            registered.trades.assign(variant="registered_stop_7"),
            selected.trades.assign(variant="selected_stop_6_75"),
        ],
        ignore_index=True,
    ).to_csv(TRADES_PATH, index=False)
    pd.concat(
        [
            registered.equity_curve.rename("registered_stop_7"),
            selected.equity_curve.rename("selected_stop_6_75"),
        ],
        axis=1,
    ).to_csv(EQUITY_PATH, index_label="ts")

    print(
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"selected gap-open parity diff={gap_equity_diff:.2e}")
    print(
        f"{'stop':>6}  {'return%':>10}  {'maxDD%':>8}  "
        f"{'sharpe':>7}  {'trades':>6}  {'win%':>7}"
    )
    for stop_atr, run in runs_by_stop.items():
        metrics = run.metrics
        print(
            f"{stop_atr:>6.2f}  {metrics['return_pct']:>10.2f}  "
            f"{metrics['max_drawdown_pct']:>8.2f}  "
            f"{metrics['sharpe']:>7.2f}  {metrics['trades']:>6}  "
            f"{metrics['win_rate_pct']:>7.2f}"
        )
    print(f"strict improvements: {strict_improvements}")
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
