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

import trx_1h_ar_v1 as v1  # noqa: E402


ARTIFACT_DIR = ROOT / "research/trx/1h-adaptive-regime/artifacts"
V2_CONFIG_JSON = ARTIFACT_DIR / "trx_1h_ar_v2_config_2026-07-06.json"


@dataclass(frozen=True, slots=True)
class MACDV2Config:
    ema_htf: int = 377
    roc_window: int = 12
    macd_fast: int = 34
    macd_slow: int = 89
    macd_signal: int = 13
    min_adx: float = 12.0
    max_adx: float = 28.0
    min_rvol: float = 1.5
    max_atr_bps: float = 200.0
    min_dir_roc_bps: float = -100.0
    max_dist_ema_bps: float = 1000.0
    htf_mode: str = "h12"
    require_macd_turn: bool = True
    tp_atr: float = 2.0
    sl_atr: float = 4.0
    max_hold_bars: int = 168
    cooldown_bars: int = 3
    entry_delay_bars: int = 1
    fixed_leverage: float = 4.0


@dataclass(frozen=True, slots=True)
class StochV2Config:
    side_mode: str = "long"
    ema_htf: int = 55
    indicator_window: int = 21
    threshold_low: float = 25.0
    threshold_high: float = 85.0
    roc_window: int = 3
    max_adx: float = 30.0
    min_rvol: float = 1.0
    min_dir_roc_bps: float = -200.0
    require_body_dir: bool = True
    sl_atr: float = 5.0
    trail_activation_atr: float = 3.0
    trail_atr: float = 1.25
    max_hold_bars: int = 168
    cooldown_bars: int = 24
    entry_delay_bars: int = 1
    fixed_leverage: float = 3.0


def load_context() -> tuple[Any, Any, Any, dict[str, Any]]:
    return v1.load_context()


def macd_to_base(engine: Any, config: MACDV2Config) -> Any:
    baseline, _stoch = v1.v1_configs(engine)
    return replace(
        baseline,
        name="TRX_1H_AR_V2_MACD",
        ema_htf=config.ema_htf,
        roc_window=config.roc_window,
        macd_fast=config.macd_fast,
        macd_slow=config.macd_slow,
        macd_signal=config.macd_signal,
        min_adx=config.min_adx,
        max_adx=config.max_adx,
        min_rvol=config.min_rvol,
        max_atr_bps=config.max_atr_bps,
        min_dir_roc_bps=config.min_dir_roc_bps,
        max_dist_ema_bps=config.max_dist_ema_bps,
        htf_mode=config.htf_mode,
        require_macd_turn=config.require_macd_turn,
        tp_atr=config.tp_atr,
        sl_atr=config.sl_atr,
        max_hold_bars=config.max_hold_bars,
        cooldown_bars=config.cooldown_bars,
        entry_delay_bars=config.entry_delay_bars,
        fixed_leverage=config.fixed_leverage,
    )


def stoch_to_base(engine: Any, config: StochV2Config) -> Any:
    _macd, baseline = v1.v1_configs(engine)
    return replace(
        baseline,
        name="TRX_1H_AR_V2_STOCH",
        side_mode=config.side_mode,
        ema_htf=config.ema_htf,
        indicator_window=config.indicator_window,
        threshold_low=config.threshold_low,
        threshold_high=config.threshold_high,
        roc_window=config.roc_window,
        max_adx=config.max_adx,
        min_rvol=config.min_rvol,
        min_dir_roc_bps=config.min_dir_roc_bps,
        require_body_dir=config.require_body_dir,
        sl_atr=config.sl_atr,
        trail_activation_atr=config.trail_activation_atr,
        trail_atr=config.trail_atr,
        max_hold_bars=config.max_hold_bars,
        cooldown_bars=config.cooldown_bars,
        entry_delay_bars=config.entry_delay_bars,
        fixed_leverage=config.fixed_leverage,
    )


def simulate_v2(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    macd: MACDV2Config | None = None,
    stoch: StochV2Config | None = None,
    frozen_priorities: tuple[float, float] | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    macd = macd or MACDV2Config()
    stoch = stoch or StochV2Config()
    return v1.simulate_v1(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        macd=macd_to_base(engine, macd),
        stoch=stoch_to_base(engine, stoch),
        frozen_priorities=frozen_priorities,
    )


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_ = v1.simulate_v1(engine, frame, funding_times, funding_cumulative)
    v2_trades, _macd_trades, _stoch_trades, priorities = simulate_v2(
        engine,
        frame,
        funding_times,
        funding_cumulative,
    )
    if v1.trade_signature(original) != v1.trade_signature(v2_trades):
        raise RuntimeError("V2 clean config is not trade-path equivalent to V1")
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V2",
        "identity": "registered_clean_parameter_version",
        "status": "registered_clean_equivalent_diagnostic_no_go_not_live_ready",
        "registered_at": "2026-07-06",
        "source_version": "TRX-1H-Adaptive-Regime-V1",
        "trade_path_equal_to_v1": True,
        "original_strategy_config_slots": 78,
        "v2_exposed_parameter_slots": 36,
        "hardcoded_contract_slots": 9,
        "removed_dormant_or_neutral_slots": 33,
        "macd_flip": asdict(MACDV2Config()),
        "stoch_reversal": asdict(StochV2Config()),
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, v2_trades),
        "standard_slices": v1.standard_slices(engine, v2_trades),
        "data_quality": quality,
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V2_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
