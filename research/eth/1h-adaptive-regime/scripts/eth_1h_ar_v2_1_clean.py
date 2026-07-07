from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import eth_1h_ar_v1 as v1  # noqa: E402
import eth_1h_ar_v1_clean as v1_clean  # noqa: E402
import eth_1h_ar_v2_1 as v21  # noqa: E402


ARTIFACT_DIR = ROOT / "research/eth/1h-adaptive-regime/artifacts"
CLEAN_JSON = ARTIFACT_DIR / "eth_1h_ar_v2_1_clean_config_2026-07-07.json"

# V2.1 全参数消融判定的 merged-path inert 字段，硬编码为 V2.1 冻结值。
BB_EMA_HTF_FIXED = 55
BB_MAX_ALIGNED_FUNDING_BPS_FIXED = 8.0


@dataclass(frozen=True, slots=True)
class BBBreakV21CleanConfig:
    indicator_window: int = 32
    band_k: float = 2.0
    roc_window: int = 12
    min_adx: float = 36.0
    min_rvol: float = 3.0
    min_atr_bps: float = 50.0
    min_dir_roc_bps: float = 100.0
    max_dist_ema_bps: float = 10000.0
    tp_atr: float = 3.0
    sl_atr: float = 5.0
    max_hold_bars: int = 48
    fixed_leverage: float = 3.0


@dataclass(frozen=True, slots=True)
class RSIV21CleanConfig:
    ema_htf: int = 233
    indicator_window: int = 7
    threshold_low: float = 5.0
    threshold_high: float = 75.0
    roc_window: int = 6
    min_adx: float = 20.0
    max_adx: float = 45.0
    min_atr_bps: float = 125.0
    min_dir_roc_bps: float = -300.0
    max_dist_ema_bps: float = 750.0
    tp_atr: float = 2.0
    sl_atr: float = 3.0
    max_hold_bars: int = 48
    cooldown_bars: int = 24
    fixed_leverage: float = 2.5


def bb_to_v1_clean(cfg: BBBreakV21CleanConfig) -> v1_clean.BBBreakCleanConfig:
    return v1_clean.BBBreakCleanConfig(
        ema_htf=BB_EMA_HTF_FIXED,
        indicator_window=cfg.indicator_window,
        band_k=cfg.band_k,
        roc_window=cfg.roc_window,
        min_adx=cfg.min_adx,
        min_rvol=cfg.min_rvol,
        min_atr_bps=cfg.min_atr_bps,
        min_dir_roc_bps=cfg.min_dir_roc_bps,
        max_dist_ema_bps=cfg.max_dist_ema_bps,
        max_aligned_funding_bps=BB_MAX_ALIGNED_FUNDING_BPS_FIXED,
        tp_atr=cfg.tp_atr,
        sl_atr=cfg.sl_atr,
        max_hold_bars=cfg.max_hold_bars,
        fixed_leverage=cfg.fixed_leverage,
    )


def rsi_to_v1_clean(cfg: RSIV21CleanConfig) -> v1_clean.RSICleanConfig:
    return v1_clean.RSICleanConfig(
        ema_htf=cfg.ema_htf,
        indicator_window=cfg.indicator_window,
        threshold_low=cfg.threshold_low,
        threshold_high=cfg.threshold_high,
        roc_window=cfg.roc_window,
        min_adx=cfg.min_adx,
        max_adx=cfg.max_adx,
        min_atr_bps=cfg.min_atr_bps,
        min_dir_roc_bps=cfg.min_dir_roc_bps,
        max_dist_ema_bps=cfg.max_dist_ema_bps,
        tp_atr=cfg.tp_atr,
        sl_atr=cfg.sl_atr,
        max_hold_bars=cfg.max_hold_bars,
        cooldown_bars=cfg.cooldown_bars,
        fixed_leverage=cfg.fixed_leverage,
    )


def simulate_clean(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    bb_break: BBBreakV21CleanConfig | None = None,
    rsi: RSIV21CleanConfig | None = None,
    delay: int = 1,
    fee: float | None = None,
    slippage: float | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    bb_break = bb_break or BBBreakV21CleanConfig()
    rsi = rsi or RSIV21CleanConfig()
    return v21.simulate_v2_1(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb_to_v1_clean(bb_break),
        rsi=rsi_to_v1_clean(rsi),
        delay=delay,
        fee=fee,
        slippage=slippage,
    )


def main() -> None:
    engine, frame, funding, quality = v21.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_rest = v21.simulate_v2_1(engine, frame, funding_times, funding_cumulative)
    clean_trades, _bb, _rsi, priorities = simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    if v1.trade_signature(original) != v1.trade_signature(clean_trades):
        raise RuntimeError("V2.1 clean config is not trade-path equivalent to V2.1")
    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V2.1",
        "identity": "clean_equivalent_configuration_surface",
        "status": "diagnostic_high_win_tuned_observation_no_go_not_live_ready",
        "v2_1_clean_slots": 29,
        "clean_tunable_slots": 27,
        "removed_or_hardcoded_slots": {
            "bb_break.ema_htf": BB_EMA_HTF_FIXED,
            "bb_break.max_aligned_funding_bps": BB_MAX_ALIGNED_FUNDING_BPS_FIXED,
        },
        "trade_path_equal": True,
        "bb_break": asdict(BBBreakV21CleanConfig()),
        "rsi_reversal": asdict(RSIV21CleanConfig()),
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, clean_trades),
        "data_quality": quality,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "clean_tunable_slots": payload["clean_tunable_slots"],
                "removed_or_hardcoded_slots": payload["removed_or_hardcoded_slots"],
                "trade_path_equal": payload["trade_path_equal"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
