"""V35：MFE 达到 4ATR 后启动 trailing 跟踪保护回测。

口径沿用 V39 trailing 诊断：
- MFE / trailing stop 仅在 15m 收盘后更新，下一根起生效；
- 下一根 open 已穿越则按 open 成交，否则按 trailing stop 价；
- 同 bar stop 与 TP 同时触发时 stop-first。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_trailing_stop as trail


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_mfe4_trailing_2026-07-20"


def trail_variants() -> list[trail.TrailConfig]:
    variants = [
        trail.TrailConfig("v35_base", enabled=False, note="V35 baseline without trailing stop"),
    ]
    # 启动线固定 4ATR；回撤距离从紧到松，覆盖近保本到接近原 TP 尾部。
    for distance in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        variants.append(
            trail.TrailConfig(
                name=f"trail_a40_d{trail.fmt(distance)}",
                enabled=True,
                activation_mfe_atr=4.0,
                trail_distance_atr=distance,
                note=(
                    f"MFE>=4ATR 后启用，stop = best favorable excursion - {distance:g}ATR；"
                    "收盘更新，下一根生效"
                ),
            )
        )
    # 相邻启动线对照，确认 4ATR 不是偶然尖峰。
    for activation, distance in [(3.5, 3.0), (4.5, 3.5), (4.5, 4.0)]:
        variants.append(
            trail.TrailConfig(
                name=f"trail_a{trail.fmt(activation)}_d{trail.fmt(distance)}",
                enabled=True,
                activation_mfe_atr=activation,
                trail_distance_atr=distance,
                note=(
                    f"对照：MFE>={activation:g}ATR 后，stop = best - {distance:g}ATR"
                ),
            )
        )
    return variants


def summarize(cfg: trail.TrailConfig, run: base.RunResult) -> dict[str, Any]:
    return {
        "name": run.name,
        "trail_config": asdict(cfg),
        "metrics": run.metrics,
        "slices": run.slices,
        "d90": ab.window_stats(run, 90),
        "d30": ab.window_stats(run, 30),
        "long_side": ab.side_stats(run, 1),
        "short_side": ab.side_stats(run, -1),
        "open_position": run.open_position,
    }


def add_deltas(rows: list[dict[str, Any]]) -> None:
    base_row = next(row for row in rows if row["name"] == "v35_base")
    for row in rows:
        row["delta_vs_v35"] = {
            "full_return_pp": round(row["metrics"]["return_pct"] - base_row["metrics"]["return_pct"], 2),
            "full_maxdd_pp": round(
                row["metrics"]["max_drawdown_pct"] - base_row["metrics"]["max_drawdown_pct"], 2
            ),
            "sharpe": round(row["metrics"]["sharpe"] - base_row["metrics"]["sharpe"], 4),
            "trades": row["metrics"]["trades"] - base_row["metrics"]["trades"],
            "win_rate_pp": round(
                row["metrics"]["win_rate_pct"] - base_row["metrics"]["win_rate_pct"], 2
            ),
            "d90_return_pp": round(row["d90"]["return_pct"] - base_row["d90"]["return_pct"], 2),
            "d90_maxdd_pp": round(
                row["d90"]["max_drawdown_pct"] - base_row["d90"]["max_drawdown_pct"], 2
            ),
            "d90_win_rate_pp": round(
                (row["d90"]["win_rate_pct"] or 0.0) - (base_row["d90"]["win_rate_pct"] or 0.0), 2
            ),
        }


def print_row(row: dict[str, Any]) -> None:
    metrics = row["metrics"]
    d90 = row["d90"]
    print(
        f"{row['name']:>18} | full {metrics['return_pct']:>9.2f}% dd {metrics['max_drawdown_pct']:>7.2f}% "
        f"sh {metrics['sharpe']:>5.2f} n {metrics['trades']:>3} win {metrics['win_rate_pct']:>6.2f}% "
        f"| 90d {d90['return_pct']:>8.2f}% dd {d90['max_drawdown_pct']:>7.2f}% "
        f"win {d90['win_rate_pct'] or 0:>6.2f}% "
        f"| exits {metrics['exit_counts']}"
    )


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    warehouse = base.DuckDBWarehouse(base.DataLakeLayout.from_settings(base.load_settings(None)))
    frame, funding, quality = base.load_data(warehouse)
    config = base.V35Config()
    features = ab.build_signals(base.build_features(frame, config), config, ab.SignalFlags())

    rows: list[dict[str, Any]] = []
    runs: list[base.RunResult] = []
    for trail_cfg in trail_variants():
        run = trail.run_backtest_trailing(
            trail_cfg.name, frame, funding, features, config, trail_cfg
        )
        runs.append(run)
        row = summarize(trail_cfg, run)
        rows.append(row)
        print_row(row)

    add_deltas(rows)
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V35 MFE>=4ATR trailing protection diagnostic",
        "baseline": "HYPE-EMA-TB-V35",
        "data_quality": quality,
        "cost_model": (
            "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included."
        ),
        "execution_assumptions": {
            "entry": "K0 close signal, K2 open entry, entry ATR from K1 completed bar.",
            "tp_sl": (
                "TP/SL/trailing checked intrabar by 15m high/low; "
                "stop first when both stop and TP are crossed."
            ),
            "trailing_timing": (
                "MFE and trailing stop level are updated only after a 15m bar closes; "
                "the updated trailing stop is active from the next bar."
            ),
            "trailing_gap_fill": (
                "If next bar open has crossed the trailing stop, fill at open; "
                "otherwise fill at the trailing stop price."
            ),
            "focus": "Primary scan fixes activation_mfe_atr=4.0 and varies trail_distance_atr.",
        },
        "v35_config": asdict(config),
        "rows": rows,
    }

    summary_path = ARTIFACT_DIR / f"{OUT_STEM}.json"
    summary_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    trades_path = ARTIFACT_DIR / f"{OUT_STEM}_trades.csv"
    equity_path = ARTIFACT_DIR / f"{OUT_STEM}_equity.csv"
    base.write_artifacts(runs, trades_path=trades_path, equity_path=equity_path)
    print(f"\nsummary -> {summary_path}")
    print(f"trades  -> {trades_path}")
    print(f"equity  -> {equity_path}")


if __name__ == "__main__":
    main()
