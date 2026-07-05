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
CLEAN_JSON = ARTIFACT_DIR / "trx_1h_ar_v1_clean_config_2026-07-05.json"


@dataclass(frozen=True, slots=True)
class MACDCleanConfig:
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
class StochCleanConfig:
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


def macd_to_base(engine: Any, clean: MACDCleanConfig) -> Any:
    baseline, _stoch = v1.v1_configs(engine)
    return replace(
        baseline,
        ema_htf=clean.ema_htf,
        roc_window=clean.roc_window,
        macd_fast=clean.macd_fast,
        macd_slow=clean.macd_slow,
        macd_signal=clean.macd_signal,
        min_adx=clean.min_adx,
        max_adx=clean.max_adx,
        min_rvol=clean.min_rvol,
        max_atr_bps=clean.max_atr_bps,
        min_dir_roc_bps=clean.min_dir_roc_bps,
        max_dist_ema_bps=clean.max_dist_ema_bps,
        htf_mode=clean.htf_mode,
        require_macd_turn=clean.require_macd_turn,
        tp_atr=clean.tp_atr,
        sl_atr=clean.sl_atr,
        max_hold_bars=clean.max_hold_bars,
        cooldown_bars=clean.cooldown_bars,
        entry_delay_bars=clean.entry_delay_bars,
        fixed_leverage=clean.fixed_leverage,
    )


def stoch_to_base(engine: Any, clean: StochCleanConfig) -> Any:
    _macd, baseline = v1.v1_configs(engine)
    return replace(
        baseline,
        side_mode=clean.side_mode,
        ema_htf=clean.ema_htf,
        indicator_window=clean.indicator_window,
        threshold_low=clean.threshold_low,
        threshold_high=clean.threshold_high,
        roc_window=clean.roc_window,
        max_adx=clean.max_adx,
        min_rvol=clean.min_rvol,
        min_dir_roc_bps=clean.min_dir_roc_bps,
        require_body_dir=clean.require_body_dir,
        sl_atr=clean.sl_atr,
        trail_activation_atr=clean.trail_activation_atr,
        trail_atr=clean.trail_atr,
        max_hold_bars=clean.max_hold_bars,
        cooldown_bars=clean.cooldown_bars,
        entry_delay_bars=clean.entry_delay_bars,
        fixed_leverage=clean.fixed_leverage,
    )


def simulate_clean(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    macd: MACDCleanConfig | None = None,
    stoch: StochCleanConfig | None = None,
    frozen_priorities: tuple[float, float] | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    macd = macd or MACDCleanConfig()
    stoch = stoch or StochCleanConfig()
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
    engine, frame, funding, quality = v1.load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    original, *_rest = v1.simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    clean_trades, _macd, _stoch, priorities = simulate_clean(
        engine, frame, funding_times, funding_cumulative
    )
    if v1.trade_signature(original) != v1.trade_signature(clean_trades):
        raise RuntimeError("V1 clean config is not trade-path equivalent to V1")
    payload = {
        "family": "TRX-1H-Adaptive-Regime",
        "version": "TRX-1H-Adaptive-Regime-V1",
        "identity": "clean_equivalent_configuration_surface",
        "status": "registered_diagnostic_baseline_no_go_not_live_ready",
        "original_strategy_config_slots": 78,
        "clean_decision_slots": 36,
        "hardcoded_contract_slots": 9,
        "removed_dormant_or_neutral_slots": 33,
        "trade_path_equal": True,
        "macd_flip": asdict(MACDCleanConfig()),
        "stoch_reversal": asdict(StochCleanConfig()),
        "component_prefit_priority_scores": priorities,
        "metrics": v1.metrics(engine, clean_trades),
        "standard_slices": v1.standard_slices(engine, clean_trades),
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
