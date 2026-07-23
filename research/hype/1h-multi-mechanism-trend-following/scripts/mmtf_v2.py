from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

import mmtf_engine as engine


@dataclass(frozen=True, slots=True)
class CleanConfig:
    entry_window: int
    ema_fast: int
    ema_slow: int
    atr_window: int
    rvol_min: float
    momentum_threshold_atr: float
    sl_atr: float
    tp_atr: float
    trail_activation_atr: float
    trail_atr: float
    cooldown_bars: int
    leverage: float

    def validate(self) -> None:
        if self.entry_window not in engine.ENTRY_WINDOWS:
            raise ValueError("unsupported entry_window")
        if self.ema_fast not in engine.EMA_SPANS or self.ema_slow not in engine.EMA_SPANS:
            raise ValueError("unsupported EMA span")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be below ema_slow")
        if self.atr_window not in engine.ATR_WINDOWS:
            raise ValueError("unsupported ATR window")
        if not 0.0 < self.leverage <= 3.0:
            raise ValueError("leverage must be in (0, 3]")
        if min(
            self.rvol_min,
            self.momentum_threshold_atr,
            self.sl_atr,
            self.tp_atr,
            self.trail_activation_atr,
            self.trail_atr,
        ) <= 0.0:
            raise ValueError("clean parameters must be positive")
        if self.cooldown_bars < 0:
            raise ValueError("cooldown cannot be negative")


def v2_baseline() -> CleanConfig:
    return CleanConfig(
        entry_window=120,
        ema_fast=96,
        ema_slow=120,
        atr_window=48,
        rvol_min=0.75,
        momentum_threshold_atr=2.0,
        sl_atr=4.0,
        tp_atr=1.5,
        trail_activation_atr=0.75,
        trail_atr=2.5,
        cooldown_bars=24,
        leverage=2.0,
    )


def to_engine_config(config: CleanConfig) -> engine.Config:
    config.validate()
    return engine.Config(
        mechanism=3,
        direction=0,
        entry_window=config.entry_window,
        exit_window=6,
        ema_fast=config.ema_fast,
        ema_slow=config.ema_slow,
        atr_window=config.atr_window,
        adx_min=0.0,
        rvol_min=config.rvol_min,
        breakout_atr=0.0,
        expansion_min=config.momentum_threshold_atr,
        sl_atr=config.sl_atr,
        tp_atr=config.tp_atr,
        trail_activation_atr=config.trail_activation_atr,
        trail_atr=config.trail_atr,
        breakeven_trigger_atr=0.0,
        max_hold_bars=1_000_000,
        cooldown_bars=config.cooldown_bars,
        leverage=config.leverage,
        trend_exit=False,
    )


def clean_dict(config: CleanConfig) -> dict[str, Any]:
    return asdict(config)


def clean_sha256(config: CleanConfig) -> str:
    canonical = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def clean_from_dict(payload: dict[str, Any]) -> CleanConfig:
    fields = set(CleanConfig.__dataclass_fields__)
    return CleanConfig(**{field: payload[field] for field in fields})
