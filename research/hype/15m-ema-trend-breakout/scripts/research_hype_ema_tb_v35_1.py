"""登记 HYPE-EMA-TB-V35.1：移除样本内冗余的空头 1h EMA 确认。"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_cooldown4 as runner
import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_1_2026-07-20"


def run_variant(
    name: str,
    frame: pd.DataFrame,
    funding: pd.Series,
    config: base.V35Config,
    flags: ab.SignalFlags,
) -> base.RunResult:
    features = ab.build_signals(base.build_features(frame, config), config, flags)
    return runner.run_backtest(
        runner.RunSpec(name=name, cooldown_bars=0, use_rsi10_90=False),
        frame,
        funding,
        features,
        config,
    )


def trade_signature(run: base.RunResult) -> list[tuple[Any, ...]]:
    if run.trades.empty:
        return []
    columns = (
        "entry_ts",
        "exit_ts",
        "direction",
        "entry_price",
        "exit_price",
        "allocation",
        "exit_reason",
        "trade_return",
    )
    return [
        tuple(row[column] for column in columns)
        for row in run.trades.to_dict(orient="records")
    ]


def summarize(run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "long_side": ab.side_stats(run, 1),
        "short_side": ab.side_stats(run, -1),
        "open_position": run.open_position,
    }


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(
        base.DataLakeLayout.from_settings(base.load_settings(None))
    )
    frame, funding, quality = base.load_data(warehouse)
    config = base.V35Config()

    v35 = run_variant(
        "v35_reference",
        frame,
        funding,
        config,
        ab.SignalFlags(),
    )
    v35_1 = run_variant(
        "v35_1",
        frame,
        funding,
        config,
        ab.SignalFlags(short_use_h1_ema=False),
    )

    signature_equal = trade_signature(v35) == trade_signature(v35_1)
    max_equity_abs_diff = float(
        np.max(np.abs(v35.equity_curve.to_numpy() - v35_1.equity_curve.to_numpy()))
    )
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "strategy_id": "HYPE-EMA-TB-V35.1",
        "status": "registered / not promoted / not live-ready",
        "definition": {
            "base": "HYPE-EMA-TB-V35",
            "only_change": "remove short h1 EMA confirmation",
            "retained": [
                "short_target_atr_pct=0.018",
                "cooldown_bars=0",
                "TP5/SL7",
                "ADX22 delayed3",
                "disable indicator exit after MFE1.5",
                "max_hold_bars=384",
            ],
        },
        "data_quality": quality,
        "cost_model": (
            "Binance USD-M perp, 0.00085 per fill "
            "(fee + 4bps adverse slippage combined), funding included."
        ),
        "equivalence_audit": {
            "trade_signatures_equal": signature_equal,
            "signature_fields": [
                "entry_ts",
                "exit_ts",
                "direction",
                "entry_price",
                "exit_price",
                "allocation",
                "exit_reason",
                "trade_return",
            ],
            "max_equity_abs_diff": max_equity_abs_diff,
            "interpretation": (
                "The removed short h1 EMA confirmation is sample-redundant "
                "on the frozen window."
            ),
        },
        "config": asdict(config),
        "flags": {
            "v35": asdict(ab.SignalFlags()),
            "v35_1": asdict(ab.SignalFlags(short_use_h1_ema=False)),
        },
        "rows": [summarize(v35), summarize(v35_1)],
    }

    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    base.write_artifacts(
        [v35, v35_1],
        trades_path=ARTIFACT_DIR / f"{OUT_STEM}_trades.csv",
        equity_path=ARTIFACT_DIR / f"{OUT_STEM}_equity.csv",
    )
    print(
        f"V35   {v35.metrics['return_pct']:+.2f}% / "
        f"{v35.metrics['max_drawdown_pct']:.2f}% / "
        f"Sharpe {v35.metrics['sharpe']:.2f} / {v35.metrics['trades']} trades"
    )
    print(
        f"V35.1 {v35_1.metrics['return_pct']:+.2f}% / "
        f"{v35_1.metrics['max_drawdown_pct']:.2f}% / "
        f"Sharpe {v35_1.metrics['sharpe']:.2f} / {v35_1.metrics['trades']} trades"
    )
    print(
        f"trade_signatures_equal={signature_equal} "
        f"max_equity_abs_diff={max_equity_abs_diff:.12g}"
    )
    print(f"summary -> {summary_path}")


if __name__ == "__main__":
    main()
