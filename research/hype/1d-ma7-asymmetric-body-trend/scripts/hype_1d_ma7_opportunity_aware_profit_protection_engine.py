"""Expanded long-profit-protection and short-RSI grid on the exact-V4 WTL kernel."""

from __future__ import annotations

import importlib.util
from itertools import product
from pathlib import Path
import sys
from typing import Any, Iterable


BASE_PATH = Path(__file__).with_name("hype_1d_ma7_wide_trend_lifecycle_engine.py")


def _load_base() -> Any:
    spec = importlib.util.spec_from_file_location("hype_oapp_base_wtl_engine", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_BASE = _load_base()

# Frozen OAPP grids. The base kernel reads these module globals at construction
# and neighbor generation time; no WTL source or locked WTL artifact is changed.
TRAIL_ACTIVATIONS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0)
TRAIL_ATR_GIVEBACKS = (0.15, 0.25, 0.35, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)
TRAIL_FRACTIONS = (0.10, 0.15, 0.20, 0.25, 0.35, 0.50, 0.65, 0.80)
TRAIL_CONFIRM_DAYS = (1, 2, 3, 4)
RSI_THRESHOLDS = (10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0)
RSI_DAYS = (1, 2, 3, 4, 5)

_BASE.TRAIL_ACTIVATIONS = TRAIL_ACTIVATIONS
_BASE.TRAIL_ATR_GIVEBACKS = TRAIL_ATR_GIVEBACKS
_BASE.TRAIL_FRACTIONS = TRAIL_FRACTIONS
_BASE.TRAIL_CONFIRM_DAYS = TRAIL_CONFIRM_DAYS
_BASE.RSI_THRESHOLDS = RSI_THRESHOLDS
_BASE.RSI_DAYS = RSI_DAYS

EntryFilter = _BASE.EntryFilter
TrailExit = _BASE.TrailExit
ShortRSIExit = _BASE.ShortRSIExit
WTLConfig = _BASE.WTLConfig
LeverageSpec = _BASE.LeverageSpec

config_from_dict = _BASE.config_from_dict
config_sha256 = _BASE.config_sha256
disable_module = _BASE.disable_module
keep_only_module = _BASE.keep_only_module
adjacent_neighbors = _BASE.adjacent_neighbors
leverage_specs = _BASE.leverage_specs
signed_efficiency = _BASE.signed_efficiency
wilder_rsi6 = _BASE.wilder_rsi6
lifecycle_exit_decision = _BASE.lifecycle_exit_decision
run_variant = _BASE.run_variant


def trail_specs() -> list[Any]:
    return [
        *[
            TrailExit("atr", activation, giveback, confirm)
            for activation, giveback, confirm in product(
                TRAIL_ACTIVATIONS,
                TRAIL_ATR_GIVEBACKS,
                TRAIL_CONFIRM_DAYS,
            )
        ],
        *[
            TrailExit("fraction", activation, giveback, confirm)
            for activation, giveback, confirm in product(
                TRAIL_ACTIVATIONS,
                TRAIL_FRACTIONS,
                TRAIL_CONFIRM_DAYS,
            )
        ],
    ]


def rsi_specs() -> list[Any]:
    return [
        ShortRSIExit(threshold, days)
        for threshold, days in product(RSI_THRESHOLDS, RSI_DAYS)
    ]


def stage_a_configs() -> list[Any]:
    return [
        *[
            WTLConfig(f"A_LONG_{index:04d}", long_exit=spec)
            for index, spec in enumerate(trail_specs(), 1)
        ],
        *[
            WTLConfig(f"A_RSI_{index:03d}", short_rsi=spec)
            for index, spec in enumerate(rsi_specs(), 1)
        ],
    ]


def build_combo_configs(
    long_exits: Iterable[Any],
    short_rsis: Iterable[Any],
) -> list[Any]:
    rows: dict[str, Any] = {}
    for long_exit, short_rsi in product(long_exits, short_rsis):
        if not long_exit.enabled or not short_rsi.enabled:
            raise ValueError("OAPP Stage C requires both modules enabled")
        provisional = WTLConfig("OAPP_DEDUP", long_exit=long_exit, short_rsi=short_rsi)
        digest = config_sha256(provisional)[:12].upper()
        config = WTLConfig(f"C_{digest}", long_exit=long_exit, short_rsi=short_rsi)
        rows[config_sha256(WTLConfig("OAPP_DEDUP", long_exit=long_exit, short_rsi=short_rsi))] = config
    return sorted(rows.values(), key=lambda row: row.arm_id)


def __getattr__(name: str) -> Any:
    return getattr(_BASE, name)

