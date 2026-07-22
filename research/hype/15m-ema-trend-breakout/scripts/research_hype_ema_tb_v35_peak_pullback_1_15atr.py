"""V35：距最高点回撤 1～1.5ATR 退出回测。

规则：跟踪单笔最高有利浮盈（MFE），当价格自峰值回撤达到
trail_distance ATR 时退出。扫描启动线，避免把初始硬止损直接
收成 1ATR。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import research_hype_ema_tb_v35_full_ablation_recent_tune as ab
import research_hype_ema_tb_v35_mfe4_trailing as prev
import research_hype_ema_tb_v35_profit_floor as base
import research_hype_ema_tb_v39_trailing_stop as trail


ROOT = Path("research/hype/15m-ema-trend-breakout")
ARTIFACT_DIR = ROOT / "artifacts"
OUT_STEM = "hype_ema_tb_v35_peak_pullback_1_15atr_2026-07-20"


def trail_variants() -> list[trail.TrailConfig]:
    variants = [
        trail.TrailConfig(
            "v35_base",
            enabled=False,
            note="V35 baseline without trailing stop",
        ),
    ]
    # 主扫：回撤距离固定 1.0 / 1.5ATR；启动线从刚够形成保护线开始。
    for distance in [1.0, 1.5]:
        for activation in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
            if activation < distance:
                # 启动前无法形成非负保护线，跳过。
                continue
            variants.append(
                trail.TrailConfig(
                    name=f"pb_a{trail.fmt(activation)}_d{trail.fmt(distance)}",
                    enabled=True,
                    activation_mfe_atr=activation,
                    trail_distance_atr=distance,
                    note=(
                        f"MFE>={activation:g}ATR 后启用；自峰值回撤 "
                        f"{distance:g}ATR 退出；收盘更新，下一根生效"
                    ),
                )
            )
    return variants


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
        row = prev.summarize(trail_cfg, run)
        rows.append(row)
        prev.print_row(row)

    prev.add_deltas(rows)
    payload = {
        "strategy_family": "HYPE-EMA-Trend-Breakout",
        "audit_id": "HYPE-EMA-TB-V35 peak-pullback 1.0-1.5ATR exit diagnostic",
        "baseline": "HYPE-EMA-TB-V35",
        "data_quality": quality,
        "cost_model": (
            "Binance USD-M perp, 0.00085 per fill (fee + 4bps slippage combined), funding included."
        ),
        "execution_assumptions": {
            "entry": "K0 close signal, K2 open entry, entry ATR from K1 completed bar.",
            "rule": (
                "After activation, exit when price pulls back trail_distance ATR from "
                "the trade's best favorable excursion (peak). Updated on 15m close, "
                "active next bar; gap-open fill at open; stop-first vs TP."
            ),
            "focus": "Primary distances 1.0ATR and 1.5ATR; activation scanned 1.0-4.0ATR.",
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
