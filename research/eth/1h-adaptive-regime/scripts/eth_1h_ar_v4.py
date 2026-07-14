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
import eth_1h_ar_v2_1 as v21  # noqa: E402
import eth_1h_ar_v2_1_clean as clean21  # noqa: E402


ARTIFACT_DIR = ROOT / "research/eth/1h-adaptive-regime/artifacts"
V4_CONFIG_JSON = ARTIFACT_DIR / "eth_1h_ar_v4_config_2026-07-13.json"


V4_BB_BREAK = clean21.BBBreakV21CleanConfig(
    indicator_window=72,
    band_k=2.5,
    roc_window=12,
    min_adx=16.0,
    min_rvol=3.5,
    min_atr_bps=25.0,
    min_dir_roc_bps=100.0,
    max_dist_ema_bps=10_000.0,
    tp_atr=3.0,
    sl_atr=5.0,
    max_hold_bars=96,
    fixed_leverage=1.5,
)

V4_RSI = clean21.RSIV21CleanConfig(
    ema_htf=144,
    indicator_window=7,
    threshold_low=10.0,
    threshold_high=75.0,
    roc_window=12,
    min_adx=12.0,
    max_adx=55.0,
    min_atr_bps=125.0,
    min_dir_roc_bps=-500.0,
    max_dist_ema_bps=1500.0,
    tp_atr=2.5,
    sl_atr=2.5,
    max_hold_bars=36,
    cooldown_bars=36,
    fixed_leverage=2.0,
)


def load_context() -> tuple[Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    return v21.load_context()


def simulate_v4(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    delay: int = 1,
    fee: float | None = None,
    slippage: float | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    return clean21.simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=V4_BB_BREAK,
        rsi=V4_RSI,
        delay=delay,
        fee=fee,
        slippage=slippage,
    )


def metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v1.metrics(engine, trades)


def standard_slices(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return v21.standard_slices(engine, trades)


def config_payload(engine: Any) -> dict[str, Any]:
    return {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V4",
        "status": "registered_high_win_strategy_refined_observation_no_go_not_live_ready",
        "source_observation": "ETH-1H-AR-V3-HIGH-WIN-STRATEGY-REFINE-2026-07-13",
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
            "bb_break": {
                **asdict(V4_BB_BREAK),
                "ema_htf_hardcoded": clean21.BB_EMA_HTF_FIXED,
                "max_aligned_funding_bps_hardcoded": (
                    clean21.BB_MAX_ALIGNED_FUNDING_BPS_FIXED
                ),
            },
            "rsi_reversal": asdict(V4_RSI),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_leg_score_descending",
        },
    }


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _bb_break, _rsi, priorities = simulate_v4(
        engine, frame, funding_times, funding_cumulative
    )
    payload = config_payload(engine)
    payload["metrics"] = metrics(engine, merged)
    payload["standard_slices"] = standard_slices(engine, merged)
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V4_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload["metrics"], indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
