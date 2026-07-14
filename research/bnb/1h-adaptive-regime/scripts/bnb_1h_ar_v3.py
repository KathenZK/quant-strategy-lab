"""Executable definition for BNB-1H-Adaptive-Regime-V3.

V3 is a registered diagnostic observation. This module exposes the frozen
configuration without evaluating or reporting the reused locked OOS window.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import bnb_1h_ar_v2 as v2


MAX_EXPOSURE = 2.5
PRIORITIES = (2.445774012147314, 1.6307399812929821)
EXPECTED_PREFIT = {
    "annual_multiple": 3.3672197013915555,
    "max_dd": -0.18235391961740977,
    "win_rate": 0.8942307692307693,
    "trades": 104.0,
}


def v3_configs(engine: Any) -> tuple[Any, Any]:
    """Return the two frozen V3 component configurations."""
    base_ema, base_wick = v2.v2_configs(engine)
    ema = replace(
        base_ema,
        name="BNB_1H_AR_V3_EMA_PULLBACK",
        ema_slow=144,
        exit_kind="trailing",
        trail_activation_atr=2.0,
        trail_atr=1.5,
        max_hold_bars=240,
        cooldown_bars=12,
        fixed_leverage=2.5,
    )
    wick = replace(
        base_wick,
        name="BNB_1H_AR_V3_WICK_REJECT",
        threshold_low=0.40,
        threshold_high=0.75,
        min_adx=28.0,
        max_hold_bars=48,
        fixed_leverage=1.0,
    )
    return ema, wick


def simulate_component(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    config: Any,
) -> list[Any]:
    return v2.simulate_component(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        config,
    )


def simulate_strategy(
    engine: Any,
    frame: Any,
    funding_times: Any,
    funding_cumulative: Any,
    configs: tuple[Any, Any] | None = None,
    priorities: tuple[float, float] = PRIORITIES,
) -> list[Any]:
    selected = configs if configs is not None else v3_configs(engine)
    return v2.simulate_strategy(
        engine,
        frame,
        funding_times,
        funding_cumulative,
        selected,
        priorities,
    )


def prefit_metrics(engine: Any, trades: list[Any], split: dict[str, Any]) -> dict[str, float]:
    return engine.metrics(trades, split["train_start"], split["oos_start"])


def assert_prefit_reproduction(metrics: dict[str, float]) -> None:
    for key, expected in EXPECTED_PREFIT.items():
        actual = float(metrics[key])
        tolerance = 0.0 if key == "trades" else 1e-12
        if abs(actual - expected) > tolerance:
            raise RuntimeError(
                f"V3 prefit reproduction drift for {key}: expected {expected}, got {actual}"
            )


def main() -> None:
    context = v2.load_context()
    trades = simulate_strategy(
        context["engine"],
        context["frame"],
        context["funding_times"],
        context["funding_cumulative"],
    )
    metrics = prefit_metrics(context["engine"], trades, context["split"])
    assert_prefit_reproduction(metrics)
    print(
        json.dumps(
            {
                "version": "BNB-1H-Adaptive-Regime-V3",
                "status": "registered_not_promoted_not_live_ready",
                "selection_window": "prefit_only",
                "max_exposure": MAX_EXPOSURE,
                "prefit": v2.json_safe(metrics),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
