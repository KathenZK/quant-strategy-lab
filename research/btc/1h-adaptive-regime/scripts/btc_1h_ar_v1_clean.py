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

import btc_1h_ar_v1 as v1  # noqa: E402


ARTIFACT_DIR = ROOT / "research/btc/1h-adaptive-regime/artifacts"
CLEAN_JSON = ARTIFACT_DIR / "btc_1h_ar_v1_clean_config_2026-07-02.json"


@dataclass(frozen=True, slots=True)
class KeltnerCleanConfig:
    indicator_window: int = 20
    band_k: float = 2.5
    roc_window: int = 24
    min_adx: float = 36.0
    min_rvol: float = 0.8
    max_atr_bps: float = 200.0
    min_dir_roc_bps: float = 0.0
    htf_mode: str = "d1"
    max_aligned_funding_bps: float = 2.0
    tp_atr: float = 1.5
    sl_atr: float = 4.0
    max_hold_bars: int = 120
    cooldown_bars: int = 6
    fixed_leverage: float = 3.0


@dataclass(frozen=True, slots=True)
class CCICleanConfig:
    ema_htf: int = 144
    indicator_window: int = 20
    threshold_high: float = 125.0
    max_adx: float = 36.0
    min_rvol: float = 1.5
    min_atr_bps: float = 50.0
    max_atr_bps: float = 300.0
    max_dist_ema_bps: float = 1000.0
    tp_atr: float = 4.0
    sl_atr: float = 1.25
    max_hold_bars: int = 96
    cooldown_bars: int = 24
    fixed_leverage: float = 4.0


def keltner_to_base(engine: Any, clean: KeltnerCleanConfig) -> Any:
    baseline, _cci = v1.v1_configs(engine)
    return replace(
        baseline,
        indicator_window=clean.indicator_window,
        band_k=clean.band_k,
        roc_window=clean.roc_window,
        min_adx=clean.min_adx,
        min_rvol=clean.min_rvol,
        max_atr_bps=clean.max_atr_bps,
        min_dir_roc_bps=clean.min_dir_roc_bps,
        htf_mode=clean.htf_mode,
        max_aligned_funding_bps=clean.max_aligned_funding_bps,
        tp_atr=clean.tp_atr,
        sl_atr=clean.sl_atr,
        max_hold_bars=clean.max_hold_bars,
        cooldown_bars=clean.cooldown_bars,
        fixed_leverage=clean.fixed_leverage,
    )


def cci_to_base(engine: Any, clean: CCICleanConfig) -> Any:
    _keltner, baseline = v1.v1_configs(engine)
    return replace(
        baseline,
        ema_htf=clean.ema_htf,
        indicator_window=clean.indicator_window,
        threshold_high=clean.threshold_high,
        max_adx=clean.max_adx,
        min_rvol=clean.min_rvol,
        min_atr_bps=clean.min_atr_bps,
        max_atr_bps=clean.max_atr_bps,
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
    keltner: KeltnerCleanConfig | None = None,
    cci: CCICleanConfig | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    keltner = keltner or KeltnerCleanConfig()
    cci = cci or CCICleanConfig()
    return v1.simulate_v1(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        keltner=keltner_to_base(engine, keltner),
        cci=cci_to_base(engine, cci),
    )


def main() -> None:
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_rest = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    clean_trades, _keltner, _cci, priorities = simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    original_signature = v1.trade_signature(original)
    clean_signature = v1.trade_signature(clean_trades)
    if original_signature != clean_signature:
        raise RuntimeError("V1 clean config is not trade-path equivalent to V1")
    payload = {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V1",
        "identity": "clean_equivalent_configuration_surface",
        "status": "diagnostic_baseline_no_go_not_live_ready",
        "original_strategy_config_slots": 78,
        "clean_tunable_slots": 27,
        "removed_or_hardcoded_slots": 51,
        "trade_path_equal": True,
        "keltner": asdict(KeltnerCleanConfig()),
        "cci": asdict(CCICleanConfig()),
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
