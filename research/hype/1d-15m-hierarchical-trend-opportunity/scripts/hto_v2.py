from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import hto_engine as engine


@dataclass(frozen=True, slots=True)
class CleanConfig:
    direction: int
    daily_fast: int
    daily_slow: int
    daily_mom_window: int
    daily_dmi_window: int
    daily_channel_window: int
    micro_fast: int
    micro_slow: int
    entry_window: int
    exit_window: int
    atr_window: int
    micro_adx_min: float
    rvol_min: float
    breakout_atr: float
    sl_atr: float
    tp_atr: float
    trail_activation_atr: float
    trail_atr: float
    breakeven_trigger_atr: float
    cooldown_bars: int
    leverage: float

    @property
    def key(self) -> tuple[Any, ...]:
        return tuple(asdict(self).values())


def from_dict(payload: dict[str, Any]) -> CleanConfig:
    fields = set(CleanConfig.__dataclass_fields__)
    return CleanConfig(**{key: payload[key] for key in fields})


def from_v1(config: engine.Config) -> CleanConfig:
    return CleanConfig(
        direction=config.direction,
        daily_fast=config.daily_fast,
        daily_slow=config.daily_slow,
        daily_mom_window=config.daily_mom_window,
        daily_dmi_window=config.daily_adx_window,
        daily_channel_window=config.daily_channel_window,
        micro_fast=config.micro_fast,
        micro_slow=config.micro_slow,
        entry_window=config.entry_window,
        exit_window=config.exit_window,
        atr_window=config.atr_window,
        micro_adx_min=config.micro_adx_min,
        rvol_min=config.rvol_min,
        breakout_atr=config.breakout_atr,
        sl_atr=config.sl_atr,
        tp_atr=config.tp_atr,
        trail_activation_atr=config.trail_activation_atr,
        trail_atr=config.trail_atr,
        breakeven_trigger_atr=config.breakeven_trigger_atr,
        cooldown_bars=config.cooldown_bars,
        leverage=config.leverage,
    )


def to_engine(config: CleanConfig) -> engine.Config:
    return engine.Config(
        daily_mode=6,
        direction=config.direction,
        daily_fast=config.daily_fast,
        daily_slow=config.daily_slow,
        daily_mom_window=config.daily_mom_window,
        daily_adx_window=config.daily_dmi_window,
        daily_adx_min=0.0,
        daily_channel_window=config.daily_channel_window,
        daily_atr_window=14,
        daily_supertrend_mult=2.0,
        daily_vote_min=4,
        entry_mode=0,
        micro_fast=config.micro_fast,
        micro_slow=config.micro_slow,
        entry_window=config.entry_window,
        exit_window=config.exit_window,
        atr_window=config.atr_window,
        micro_adx_min=config.micro_adx_min,
        rvol_min=config.rvol_min,
        rsi_window=14,
        rsi_trigger=45.0,
        rsi_reclaim=50.0,
        pullback_atr=0.0,
        breakout_atr=config.breakout_atr,
        expansion_min=1.0,
        sl_atr=config.sl_atr,
        tp_atr=config.tp_atr,
        trail_activation_atr=config.trail_activation_atr,
        trail_atr=config.trail_atr,
        breakeven_trigger_atr=config.breakeven_trigger_atr,
        max_hold_bars=672,
        cooldown_bars=config.cooldown_bars,
        leverage=config.leverage,
        exit_mode=4,
    )
