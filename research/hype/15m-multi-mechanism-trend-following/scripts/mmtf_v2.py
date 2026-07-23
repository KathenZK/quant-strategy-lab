from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

import mmtf_engine as engine


@dataclass(frozen=True, slots=True)
class CleanConfig:
    ema_fast: int
    ema_slow: int
    atr_window: int
    adx_min: float
    rvol_min: float
    keltner_atr: float
    sl_atr: float
    tp_atr: float
    max_hold_bars: int
    leverage: float
    trend_exit_window: int | None

    def validate(self) -> None:
        if self.ema_fast not in engine.EMA_SPANS or self.ema_slow not in engine.EMA_SPANS:
            raise ValueError("unsupported EMA span")
        if self.ema_fast >= self.ema_slow:
            raise ValueError("ema_fast must be below ema_slow")
        if self.atr_window not in engine.ATR_WINDOWS:
            raise ValueError("unsupported ATR window")
        if self.trend_exit_window is not None and self.trend_exit_window not in engine.EXIT_WINDOWS:
            raise ValueError("unsupported trend exit window")
        if not 0.0 < self.leverage <= 3.0:
            raise ValueError("leverage must be in (0, 3]")
        if min(
            self.adx_min,
            self.rvol_min,
            self.keltner_atr,
            self.sl_atr,
            self.tp_atr,
            self.max_hold_bars,
        ) <= 0.0:
            raise ValueError("clean parameters must be positive")


def v2_baseline() -> CleanConfig:
    return CleanConfig(
        ema_fast=24,
        ema_slow=384,
        atr_window=14,
        adx_min=26.0,
        rvol_min=1.0,
        keltner_atr=1.25,
        sl_atr=6.0,
        tp_atr=0.75,
        max_hold_bars=24,
        leverage=2.0,
        trend_exit_window=None,
    )


def to_engine_config(config: CleanConfig) -> engine.Config:
    config.validate()
    return engine.Config(
        mechanism=1,
        direction=0,
        entry_window=16,
        exit_window=config.trend_exit_window or 8,
        ema_fast=config.ema_fast,
        ema_slow=config.ema_slow,
        atr_window=config.atr_window,
        adx_min=config.adx_min,
        rvol_min=config.rvol_min,
        breakout_atr=0.0,
        expansion_min=config.keltner_atr,
        sl_atr=config.sl_atr,
        tp_atr=config.tp_atr,
        trail_activation_atr=1_000_000.0,
        trail_atr=1.0,
        breakeven_trigger_atr=0.0,
        max_hold_bars=config.max_hold_bars,
        cooldown_bars=0,
        leverage=config.leverage,
        trend_exit=config.trend_exit_window is not None,
    )


def clean_dict(config: CleanConfig) -> dict[str, Any]:
    return asdict(config)


def clean_sha256(config: CleanConfig) -> str:
    canonical = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def clean_from_dict(payload: dict[str, Any]) -> CleanConfig:
    fields = set(CleanConfig.__dataclass_fields__)
    values = {field: payload[field] for field in fields}
    raw_exit = values["trend_exit_window"]
    if raw_exit is not None and raw_exit == raw_exit:
        values["trend_exit_window"] = int(raw_exit)
    else:
        values["trend_exit_window"] = None
    for field in ("ema_fast", "ema_slow", "atr_window", "max_hold_bars"):
        values[field] = int(values[field])
    return CleanConfig(**values)

