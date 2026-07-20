"""V39 空单单级分批止盈诊断。

复用 V35 scale-out 引擎，只替换为 V39 冻结入场与 sizing：
long_vol_min=0.35、short_target_atr_pct=0.022、移除冗余空头 1h EMA 确认。
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as signal_engine
import research_hype_ema_tb_v35_h4_rsi6_entry_filter as data_diag
import research_hype_ema_tb_v35_partial_take_profit as partial
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v39_short_partial_take_profit_2026-07-17"
SUMMARY_PATH = ARTIFACT_DIR / f"{OUT_STEM}.json"
TRADES_PATH = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
EQUITY_PATH = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"


def specs() -> tuple[partial.PartialSpec, ...]:
    rows = [partial.PartialSpec("v39_base", None, 0.0)]
    for trigger in (4.0, 4.2, 4.4):
        for fraction in (0.50, 2.0 / 3.0, 0.75):
            rows.append(
                partial.PartialSpec(
                    f"v39_short_{trigger:g}_{fraction:.3f}",
                    trigger,
                    fraction,
                    "short_only",
                )
            )
    return tuple(rows)


def payoff_stats(trades: pd.DataFrame) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for direction, label in ((1, "long"), (-1, "short")):
        side = trades.loc[trades["direction"].eq(direction)]
        tp = side.loc[side["exit_reason"].eq("take_profit")]
        sl = side.loc[side["exit_reason"].eq("stop_loss")]
        stats[label] = {
            "trades": int(len(side)),
            "wins": int(side["trade_return"].gt(0.0).sum()),
            "win_rate_pct": (
                round(float(side["trade_return"].gt(0.0).mean()) * 100.0, 2)
                if len(side)
                else None
            ),
            "avg_tp_return_pct": (
                round(float(tp["trade_return"].mean()) * 100.0, 2)
                if len(tp)
                else None
            ),
            "avg_sl_return_pct": (
                round(float(sl["trade_return"].mean()) * 100.0, 2)
                if len(sl)
                else None
            ),
            "exit_counts": {
                str(key): int(value)
                for key, value in side["exit_reason"].value_counts().items()
            },
        }
    tp = trades.loc[trades["exit_reason"].eq("take_profit")]
    sl = trades.loc[trades["exit_reason"].eq("stop_loss")]
    avg_tp = float(tp["trade_return"].mean()) if len(tp) else None
    avg_sl = float(sl["trade_return"].mean()) if len(sl) else None
    stats["overall_recovery_tp_count"] = (
        None
        if avg_tp is None or avg_sl is None or avg_tp == 0.0
        else round(abs(avg_sl) / avg_tp, 2)
    )
    return stats


def compare_to_base(
    run: base.RunResult,
    baseline: base.RunResult,
) -> dict[str, Any] | None:
    if run is baseline:
        return None
    return {
        "final_equity_retained_pct": round(
            100.0
            * (1.0 + run.metrics["return_pct"] / 100.0)
            / (1.0 + baseline.metrics["return_pct"] / 100.0),
            2,
        ),
        "return_delta_pp": round(
            run.metrics["return_pct"] - baseline.metrics["return_pct"],
            2,
        ),
        "max_drawdown_delta_pp": round(
            run.metrics["max_drawdown_pct"]
            - baseline.metrics["max_drawdown_pct"],
            2,
        ),
        "sharpe_delta": round(
            run.metrics["sharpe"] - baseline.metrics["sharpe"],
            2,
        ),
        "trade_delta": run.metrics["trades"] - baseline.metrics["trades"],
        "win_rate_delta_pp": round(
            run.metrics["win_rate_pct"]
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
    config = replace(
        base.V35Config(),
        long_vol_min=0.35,
        short_target_atr_pct=0.022,
    )
    flags = signal_engine.SignalFlags(short_use_h1_ema=False)
    features = signal_engine.build_signals(
        base.build_features(frame, config),
        config,
        flags,
    )
    run_specs = specs()
    outputs = [
        (
            spec,
            *partial.run_backtest(
                spec=spec,
                frame=frame,
                funding=funding,
                features=features,
                config=config,
            ),
        )
        for spec in run_specs
    ]
    baseline = outputs[0][1]
    canonical = base.run_backtest(
        "v39_canonical",
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
        raise ValueError(f"V39 baseline parity failed: {parity_diff}")

    summary = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "registered_reference": "HYPE-EMA-TB-V39",
        "audit_id": "V39 short-only one-stage partial take-profit",
        "run_date": "2026-07-17",
        "status": "diagnostic_only_v39_unchanged",
        "data_quality": quality,
        "gates": {
            "data_quality": quality_gate,
            "canonical_vs_custom_baseline_max_equity_diff": parity_diff,
        },
        "assumptions": {
            "partial_fill": (
                "One reduce-only short partial fill at an entry-ATR fixed "
                "target; remaining allocation keeps V39 TP5/SL7 and state."
            ),
            "same_bar_order": (
                "Stop-first; without a stop hit, partial target fills before "
                "TP5 when both are touched in one bar."
            ),
            "path": (
                "Partial fill does not close the strategy position, permit "
                "re-entry, create cooldown or add a trade-count event."
            ),
            "cost": (
                "0.00085 per filled allocation on entry, partial and final "
                "exit; funding applies to remaining allocation."
            ),
        },
        "config": asdict(config),
        "signal_flags": asdict(flags),
        "runs": [
            {
                "spec": asdict(spec),
                "metrics": run.metrics,
                "standard_slices": run.slices,
                "open_position": run.open_position,
                "audit": audit,
                "payoff": payoff_stats(run.trades),
                "comparison_to_v39": compare_to_base(run, baseline),
            }
            for spec, run, audit in outputs
        ],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=str),
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
        f"data: {quality['start']} ~ {quality['end']} rows={quality['rows']} "
        f"quality_gate={quality_gate['passed']}"
    )
    print(f"baseline parity diff={parity_diff:.2e}")
    print(
        f"{'variant':>28} {'return%':>10} {'maxDD%':>8} "
        f"{'sharpe':>7} {'trades':>6} {'win%':>7} {'partials':>8}"
    )
    for _, run, audit in outputs:
        metrics = run.metrics
        print(
            f"{run.name:>28} {metrics['return_pct']:>10.2f} "
            f"{metrics['max_drawdown_pct']:>8.2f} "
            f"{metrics['sharpe']:>7.2f} {metrics['trades']:>6} "
            f"{metrics['win_rate_pct']:>7.2f} "
            f"{audit['partial_events']:>8}"
        )
    print(f"summary -> {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
