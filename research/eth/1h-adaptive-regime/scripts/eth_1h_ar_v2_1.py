from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v1_clean as clean  # noqa: E402
import eth_1h_ar_v2 as v2  # noqa: E402


ARTIFACT_DIR = ROOT / "research/eth/1h-adaptive-regime/artifacts"
V2_1_CONFIG_JSON = ARTIFACT_DIR / "eth_1h_ar_v2_1_config_2026-07-07.json"


V2_1_BB_BREAK = clean.BBBreakCleanConfig(
    ema_htf=55,
    indicator_window=32,
    band_k=2.0,
    roc_window=12,
    min_adx=36.0,
    min_rvol=3.0,
    min_atr_bps=50.0,
    min_dir_roc_bps=100.0,
    max_dist_ema_bps=10000.0,
    max_aligned_funding_bps=8.0,
    tp_atr=3.0,
    sl_atr=5.0,
    max_hold_bars=48,
    fixed_leverage=3.0,
)

V2_1_RSI = clean.RSICleanConfig(
    ema_htf=233,
    indicator_window=7,
    threshold_low=5.0,
    threshold_high=75.0,
    roc_window=6,
    min_adx=20.0,
    max_adx=45.0,
    min_atr_bps=125.0,
    min_dir_roc_bps=-300.0,
    max_dist_ema_bps=750.0,
    tp_atr=2.0,
    sl_atr=3.0,
    max_hold_bars=48,
    cooldown_bars=24,
    fixed_leverage=2.5,
)


def load_context() -> tuple[Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    return v1.load_context()


def v2_1_configs() -> tuple[clean.BBBreakCleanConfig, clean.RSICleanConfig]:
    return V2_1_BB_BREAK, V2_1_RSI


def standard_slices(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v2.standard_slices(engine, trades)


def simulate_v2_1(
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
    return v2.simulate_v2(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb_break or V2_1_BB_BREAK,
        rsi=rsi or V2_1_RSI,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )


def metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def config_payload(engine: Any) -> dict[str, Any]:
    return {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V2.1",
        "status": "registered_diagnostic_high_win_tuned_observation_no_go_not_live_ready",
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
            "bb_break": asdict(V2_1_BB_BREAK),
            "rsi_reversal": asdict(V2_1_RSI),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_leg_score_descending",
        },
    }


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _bb_break, _rsi, priorities = simulate_v2_1(
        engine, frame, funding_times, funding_cumulative
    )
    payload = config_payload(engine)
    payload["metrics"] = metrics(engine, merged)
    payload["standard_slices"] = standard_slices(engine, merged)
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V2_1_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload["metrics"], indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
