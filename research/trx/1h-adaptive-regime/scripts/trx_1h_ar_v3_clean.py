from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import trx_1h_ar_v1 as v1  # noqa: E402
import trx_1h_ar_v3 as v3  # noqa: E402


ARTIFACT_DIR = ROOT / "research/trx/1h-adaptive-regime/artifacts"
CLEAN_CONFIG_JSON = ARTIFACT_DIR / "trx_1h_ar_v3_clean_config_2026-07-07.json"

# Dormant fields per V3 full ablation 2026-07-07: no value in the tested domain
# changes the merged trade path. They are fixed at V3 values and removed from
# the tunable surface.
MACD_FIXED = {
    "ema_htf": 89,
    "max_atr_bps": 150.0,
    "max_hold_bars": 120,
    "require_macd_turn": False,
}
STOCH_FIXED = {
    "ema_htf": 233,
}


@dataclass(frozen=True, slots=True)
class MACDV3CleanConfig:
    roc_window: int = 6
    macd_fast: int = 34
    macd_slow: int = 89
    macd_signal: int = 13
    min_adx: float = 20.0
    max_adx: float = 24.0
    min_rvol: float = 0.0
    min_dir_roc_bps: float = -100.0
    max_dist_ema_bps: float = 10_000.0
    htf_mode: str = "h12"
    tp_atr: float = 2.0
    sl_atr: float = 5.0
    cooldown_bars: int = 3
    entry_delay_bars: int = 1
    fixed_leverage: float = 5.0


@dataclass(frozen=True, slots=True)
class StochV3CleanConfig:
    side_mode: str = "both"
    indicator_window: int = 21
    threshold_low: float = 25.0
    threshold_high: float = 90.0
    roc_window: int = 3
    max_adx: float = 24.0
    min_rvol: float = 1.0
    min_dir_roc_bps: float = -300.0
    require_body_dir: bool = True
    sl_atr: float = 6.0
    trail_activation_atr: float = 3.0
    trail_atr: float = 2.0
    max_hold_bars: int = 120
    cooldown_bars: int = 6
    entry_delay_bars: int = 2
    fixed_leverage: float = 3.5


def macd_to_v3(config: MACDV3CleanConfig) -> v3.MACDV3Config:
    return v3.MACDV3Config(**asdict(config), **MACD_FIXED)


def stoch_to_v3(config: StochV3CleanConfig) -> v3.StochV3Config:
    return v3.StochV3Config(**asdict(config), **STOCH_FIXED)


def simulate_clean(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    macd: MACDV3CleanConfig | None = None,
    stoch: StochV3CleanConfig | None = None,
    frozen_priorities: tuple[float, float] | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    macd = macd or MACDV3CleanConfig()
    stoch = stoch or StochV3CleanConfig()
    return v3.simulate_v3(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd=macd_to_v3(macd),
        stoch=stoch_to_v3(stoch),
        frozen_priorities=frozen_priorities,
    )


def main() -> None:
    engine, frame, funding, quality = v3.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_ = v3.simulate_v3(engine, frame, funding_times, funding_cumulative)
    clean_trades, _macd_trades, _stoch_trades, priorities = simulate_clean(
        engine,
        frame,
        funding_times,
        funding_cumulative,
    )
    if v1.trade_signature(original) != v1.trade_signature(clean_trades):
        raise RuntimeError("V3 clean surface is not trade-path equivalent to V3")
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "identity": "v3_clean_parameter_surface",
        "status": "diagnostic_clean_surface_no_go_not_live_ready",
        "source_version": "TRX-1H-Adaptive-Regime-V3",
        "trade_path_equal_to_v3": True,
        "v3_exposed_parameter_slots": 36,
        "clean_tunable_slots": 31,
        "dormant_fixed_slots": 5,
        "macd_flip_tunable": asdict(MACDV3CleanConfig()),
        "stoch_reversal_tunable": asdict(StochV3CleanConfig()),
        "macd_flip_fixed": MACD_FIXED,
        "stoch_reversal_fixed": STOCH_FIXED,
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, clean_trades),
        "standard_slices": v1.standard_slices(engine, clean_trades),
        "data_quality": quality,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "trade_path_equal_to_v3": True,
                "clean_tunable_slots": 31,
                "dormant_fixed_slots": 5,
                "current_full": payload["metrics"]["current_full"],
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
