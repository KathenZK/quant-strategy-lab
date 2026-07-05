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


ARTIFACT_DIR = ROOT / "research/eth/1h-adaptive-regime/artifacts"
CLEAN_JSON = ARTIFACT_DIR / "eth_1h_ar_v1_clean_config_2026-07-03.json"


@dataclass(frozen=True, slots=True)
class BBBreakCleanConfig:
    ema_htf: int = 89
    indicator_window: int = 72
    band_k: float = 2.0
    roc_window: int = 12
    min_adx: float = 16.0
    min_rvol: float = 2.0
    min_atr_bps: float = 75.0
    min_dir_roc_bps: float = -200.0
    max_dist_ema_bps: float = 750.0
    max_aligned_funding_bps: float = 2.0
    tp_atr: float = 3.0
    sl_atr: float = 2.5
    max_hold_bars: int = 18
    fixed_leverage: float = 2.5


@dataclass(frozen=True, slots=True)
class RSICleanConfig:
    ema_htf: int = 89
    indicator_window: int = 21
    threshold_low: float = 15.0
    threshold_high: float = 60.0
    roc_window: int = 3
    min_adx: float = 0.0
    max_adx: float = 45.0
    min_atr_bps: float = 100.0
    min_dir_roc_bps: float = 50.0
    max_dist_ema_bps: float = 750.0
    tp_atr: float = 3.0
    sl_atr: float = 2.0
    max_hold_bars: int = 12
    cooldown_bars: int = 6
    fixed_leverage: float = 1.0


def bb_break_to_base(engine: Any, clean: BBBreakCleanConfig) -> Any:
    baseline, _rsi = v1.v1_configs(engine)
    return replace(
        baseline,
        ema_htf=clean.ema_htf,
        indicator_window=clean.indicator_window,
        band_k=clean.band_k,
        roc_window=clean.roc_window,
        min_adx=clean.min_adx,
        min_rvol=clean.min_rvol,
        min_atr_bps=clean.min_atr_bps,
        min_dir_roc_bps=clean.min_dir_roc_bps,
        max_dist_ema_bps=clean.max_dist_ema_bps,
        max_aligned_funding_bps=clean.max_aligned_funding_bps,
        tp_atr=clean.tp_atr,
        sl_atr=clean.sl_atr,
        max_hold_bars=clean.max_hold_bars,
        fixed_leverage=clean.fixed_leverage,
    )


def rsi_to_base(engine: Any, clean: RSICleanConfig) -> Any:
    _bb_break, baseline = v1.v1_configs(engine)
    return replace(
        baseline,
        ema_htf=clean.ema_htf,
        indicator_window=clean.indicator_window,
        threshold_low=clean.threshold_low,
        threshold_high=clean.threshold_high,
        roc_window=clean.roc_window,
        min_adx=clean.min_adx,
        max_adx=clean.max_adx,
        min_atr_bps=clean.min_atr_bps,
        min_dir_roc_bps=clean.min_dir_roc_bps,
        max_dist_ema_bps=clean.max_dist_ema_bps,
        tp_atr=clean.tp_atr,
        sl_atr=clean.sl_atr,
        max_hold_bars=clean.max_hold_bars,
        cooldown_bars=clean.cooldown_bars,
        fixed_leverage=clean.fixed_leverage,
    )


def simulate_clean(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    bb_break: BBBreakCleanConfig | None = None,
    rsi: RSICleanConfig | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    bb_break = bb_break or BBBreakCleanConfig()
    rsi = rsi or RSICleanConfig()
    return v1.simulate_v1(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        bb_break=bb_break_to_base(engine, bb_break),
        rsi=rsi_to_base(engine, rsi),
    )


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_rest = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    clean_trades, _bb_break, _rsi, priorities = simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    original_signature = v1.trade_signature(original)
    clean_signature = v1.trade_signature(clean_trades)
    if original_signature != clean_signature:
        raise RuntimeError("V1 clean config is not trade-path equivalent to V1")
    payload = {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V1",
        "identity": "clean_equivalent_configuration_surface",
        "status": "diagnostic_baseline_no_go_not_live_ready",
        "original_strategy_config_slots": 78,
        "clean_tunable_slots": 29,
        "removed_or_hardcoded_slots": 49,
        "trade_path_equal": True,
        "bb_break": asdict(BBBreakCleanConfig()),
        "rsi_reversal": asdict(RSICleanConfig()),
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, clean_trades),
        "data_quality": quality,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
