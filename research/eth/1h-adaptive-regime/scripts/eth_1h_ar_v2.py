from __future__ import annotations

import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v1_clean as clean  # noqa: E402
import research_eth_1h_ar_v1_clean_tune as tune  # noqa: E402


ARTIFACT_DIR = ROOT / "research/eth/1h-adaptive-regime/artifacts"
V2_CONFIG_JSON = ARTIFACT_DIR / "eth_1h_ar_v2_config_2026-07-06.json"


V2_BB_BREAK = clean.BBBreakCleanConfig(
    ema_htf=89,
    indicator_window=32,
    band_k=2.0,
    roc_window=48,
    min_adx=28.0,
    min_rvol=2.5,
    min_atr_bps=50.0,
    min_dir_roc_bps=-200.0,
    max_dist_ema_bps=10000.0,
    max_aligned_funding_bps=10000.0,
    tp_atr=3.0,
    sl_atr=4.0,
    max_hold_bars=48,
    fixed_leverage=2.0,
)

V2_RSI = clean.RSICleanConfig(
    ema_htf=377,
    indicator_window=14,
    threshold_low=10.0,
    threshold_high=65.0,
    roc_window=6,
    min_adx=16.0,
    max_adx=100.0,
    min_atr_bps=100.0,
    min_dir_roc_bps=-10000.0,
    max_dist_ema_bps=1000.0,
    tp_atr=2.5,
    sl_atr=2.0,
    max_hold_bars=24,
    cooldown_bars=0,
    fixed_leverage=1.5,
)


def load_context() -> tuple[Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    return v1.load_context()


def v2_configs() -> tuple[clean.BBBreakCleanConfig, clean.RSICleanConfig]:
    return V2_BB_BREAK, V2_RSI


def standard_slices(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    windows = {
        "last_1d": v1.FULL_END - pd.Timedelta(days=1),
        "last_7d": v1.FULL_END - pd.Timedelta(days=7),
        "last_1m": v1.FULL_END - pd.DateOffset(months=1),
        "last_3m": v1.FULL_END - pd.DateOffset(months=3),
        "last_6m": v1.FULL_END - pd.DateOffset(months=6),
        "last_1y": v1.FULL_END - pd.DateOffset(years=1),
    }
    return {
        name: engine.metrics(trades, start, v1.FULL_END)
        for name, start in windows.items()
    }


def simulate_v2(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    bb_break: clean.BBBreakCleanConfig | None = None,
    rsi: clean.RSICleanConfig | None = None,
    delay: int = 1,
    fee: float | None = None,
    slippage: float | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    bb_break = bb_break or V2_BB_BREAK
    rsi = rsi or V2_RSI
    original_fee = engine.FEE_PER_FILL
    original_slippage = engine.SLIPPAGE_PER_FILL
    if fee is not None:
        engine.FEE_PER_FILL = fee
    if slippage is not None:
        engine.SLIPPAGE_PER_FILL = slippage
    try:
        bb_cfg = replace(clean.bb_break_to_base(engine, bb_break), entry_delay_bars=delay)
        rsi_cfg = replace(clean.rsi_to_base(engine, rsi), entry_delay_bars=delay)
        bb_trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, bb_cfg
        )
        rsi_trades = v1.simulate_component(
            engine, frame, funding_times, funding_cumulative, rsi_cfg
        )
        priorities = (
            tune.leg_score(tune.prefit_metrics(engine, bb_trades)),
            tune.leg_score(tune.prefit_metrics(engine, rsi_trades)),
        )
        merged = engine.merge_trade_sets(
            bb_trades,
            rsi_trades,
            priorities[0],
            priorities[1],
        )
        return merged, bb_trades, rsi_trades, priorities
    finally:
        engine.FEE_PER_FILL = original_fee
        engine.SLIPPAGE_PER_FILL = original_slippage


def metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def config_payload(engine: Any) -> dict[str, Any]:
    return {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V2",
        "status": "registered_diagnostic_tuned_observation_no_go_not_live_ready",
        "split": {
            "train_start": v1.TRAIN_START,
            "train_end": v1.TRAIN_END,
            "prefit_end_reused_holdout_start": v1.PREFIT_END,
            "full_end": v1.FULL_END,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "components": {
            "bb_break": asdict(V2_BB_BREAK),
            "rsi_reversal": asdict(V2_RSI),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_leg_score_descending",
        },
    }


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _bb_break, _rsi, priorities = simulate_v2(
        engine, frame, funding_times, funding_cumulative
    )
    payload = config_payload(engine)
    payload["metrics"] = metrics(engine, merged)
    payload["standard_slices"] = standard_slices(engine, merged)
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V2_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
