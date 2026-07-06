from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/sol/1h-adaptive-regime"
SEARCH_SCRIPT = FAMILY_DIR / "scripts/research_sol_1h_adaptive_regime_search.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
SOURCE_JSON = ARTIFACT_DIR / "sol_1h_adaptive_regime_search_2026-07-03.json"
V1_CONFIG_JSON = ARTIFACT_DIR / "sol_1h_ar_v1_config_2026-07-03.json"

TRAIN_START = pd.Timestamp("2024-08-17T05:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-07T07:24:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T05:00:00Z")
FULL_END = pd.Timestamp("2026-07-03T05:00:00Z")

V1_DONCHIAN = {
    "name": "SOL_1H_AR_R594184",
    "style": "donchian_break",
    "side_mode": "long",
    "ema_fast": 89,
    "ema_slow": 144,
    "ema_htf": 377,
    "indicator_window": 12,
    "threshold_low": 30.0,
    "threshold_high": 65.0,
    "band_k": 1.5,
    "pullback_atr": -0.25,
    "roc_window": 3,
    "roc_threshold_bps": 200.0,
    "macd_fast": 21,
    "macd_slow": 55,
    "macd_signal": 9,
    "min_adx": 36.0,
    "max_adx": 100.0,
    "min_rvol": 1.0,
    "min_atr_bps": 100.0,
    "max_atr_bps": 10_000.0,
    "min_dir_roc_bps": 50.0,
    "max_dist_ema_bps": 10_000.0,
    "htf_mode": "none",
    "require_macd_turn": True,
    "require_body_dir": False,
    "max_aligned_funding_bps": 1.0,
    "exit_kind": "fixed",
    "tp_atr": 3.0,
    "sl_atr": 5.0,
    "trail_activation_atr": 1.5,
    "trail_atr": 3.0,
    "max_hold_bars": 6,
    "cooldown_bars": 12,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 1.5,
    "risk_fraction": 0.005,
    "max_leverage": 1.0,
}

V1_BB_REVERT = {
    "name": "SOL_1H_AR_R736318",
    "style": "bb_revert",
    "side_mode": "both",
    "ema_fast": 144,
    "ema_slow": 233,
    "ema_htf": 89,
    "indicator_window": 72,
    "threshold_low": 35.0,
    "threshold_high": 65.0,
    "band_k": 2.0,
    "pullback_atr": 0.25,
    "roc_window": 24,
    "roc_threshold_bps": 75.0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "min_adx": 16.0,
    "max_adx": 24.0,
    "min_rvol": 1.0,
    "min_atr_bps": 0.0,
    "max_atr_bps": 200.0,
    "min_dir_roc_bps": -10_000.0,
    "max_dist_ema_bps": 750.0,
    "htf_mode": "none",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 1.0,
    "exit_kind": "trailing",
    "tp_atr": 1.25,
    "sl_atr": 2.5,
    "trail_activation_atr": 1.0,
    "trail_atr": 0.75,
    "max_hold_bars": 96,
    "cooldown_bars": 24,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 2.5,
    "risk_fraction": 0.03,
    "max_leverage": 1.5,
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_context() -> tuple[Any, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    search = load_module(SEARCH_SCRIPT, "sol_1h_ar_v1_search")
    engine = search.load_engine()
    frame, funding, quality = search.load_data()
    frame = engine.add_features(frame, funding)
    return engine, frame, funding, quality


def v1_configs(engine: Any) -> tuple[Any, Any]:
    return (
        engine.StrategyConfig(**V1_DONCHIAN),
        engine.StrategyConfig(**V1_BB_REVERT),
    )


def simulate_component(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    cfg: Any,
) -> list[Any]:
    return engine.simulate_trades(
        frame,
        engine.build_signal(frame, cfg),
        cfg,
        funding_times,
        funding_cumulative,
    )


def component_score(engine: Any, trades: list[Any]) -> float:
    train = engine.metrics(trades, TRAIN_START, TRAIN_END)
    validation = engine.metrics(trades, TRAIN_END, PREFIT_END)
    prefit = engine.metrics(trades, TRAIN_START, PREFIT_END)
    return engine.prefit_score(train, validation, prefit)


def simulate_v1(
    engine: Any,
    frame: pd.DataFrame,
    funding_times: Any,
    funding_cumulative: Any,
    *,
    configs: tuple[Any, ...] | None = None,
    frozen_priorities: tuple[float, ...] | None = None,
) -> tuple[list[Any], list[list[Any]], list[float]]:
    configs = configs or v1_configs(engine)
    legs = [
        simulate_component(engine, frame, funding_times, funding_cumulative, cfg)
        for cfg in configs
    ]
    scenario_priorities = [component_score(engine, trades) for trades in legs]
    priorities = list(frozen_priorities or tuple(scenario_priorities))
    if len(legs) != len(priorities):
        raise ValueError(f"Expected {len(legs)} priorities, got {len(priorities)}")
    if len(legs) == 0:
        merged: list[Any] = []
    elif len(legs) == 1:
        merged = legs[0]
    elif len(legs) == 2:
        merged = engine.merge_trade_sets(legs[0], legs[1], priorities[0], priorities[1])
    else:
        merged = legs[0]
        merged_priority = priorities[0]
        for trades, priority in zip(legs[1:], priorities[1:], strict=True):
            merged = engine.merge_trade_sets(merged, trades, merged_priority, priority)
            merged_priority = max(merged_priority, priority)
    return merged, legs, priorities


def trade_signature(trades: list[Any]) -> tuple[tuple[Any, ...], ...]:
    return tuple(
        (
            trade.signal_i,
            trade.entry_i,
            trade.exit_i,
            trade.side,
            round(trade.entry_price, 10),
            round(trade.exit_price, 10),
            trade.exit_reason,
            round(trade.exposure, 10),
            round(trade.equity_ret, 12),
        )
        for trade in trades
    )


def metrics(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    return {
        "train": engine.metrics(trades, TRAIN_START, TRAIN_END),
        "validation": engine.metrics(trades, TRAIN_END, PREFIT_END),
        "prefit": engine.metrics(trades, TRAIN_START, PREFIT_END),
        "reused_holdout": engine.metrics(trades, PREFIT_END, FULL_END),
        "current_full": engine.metrics(trades, TRAIN_START, FULL_END),
    }


def standard_slices(engine: Any, trades: list[Any]) -> dict[str, dict[str, float]]:
    windows = {
        "last_1d": FULL_END - pd.Timedelta(days=1),
        "last_7d": FULL_END - pd.Timedelta(days=7),
        "last_1m": FULL_END - pd.DateOffset(months=1),
        "last_3m": FULL_END - pd.DateOffset(months=3),
        "last_6m": FULL_END - pd.DateOffset(months=6),
        "last_1y": FULL_END - pd.DateOffset(years=1),
    }
    return {name: engine.metrics(trades, start, FULL_END) for name, start in windows.items()}


def config_payload(engine: Any) -> dict[str, Any]:
    donchian, bb_revert = v1_configs(engine)
    return {
        "family": "SOL-1H-Adaptive-Regime",
        "version": "SOL-1H-Adaptive-Regime-V1",
        "status": "registered_diagnostic_baseline_no_go_not_live_ready",
        "registered_at": "2026-07-03",
        "source_observation": "ENS__SOL_1H_AR_R594184__SOL_1H_AR_R736318",
        "frozen_data_end": FULL_END,
        "split": {
            "train_start": TRAIN_START,
            "train_end": TRAIN_END,
            "prefit_end_reused_holdout_start": PREFIT_END,
            "full_end": FULL_END,
        },
        "costs": {
            "fee_per_fill": engine.FEE_PER_FILL,
            "slippage_per_fill": engine.SLIPPAGE_PER_FILL,
            "funding": "actual_binance_history_per_trade",
        },
        "components": {
            "donchian_break": asdict(donchian),
            "bb_revert": asdict(bb_revert),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_score_descending_frozen_before_reused_holdout",
        },
    }


def main() -> None:
    if not SOURCE_JSON.exists():
        raise FileNotFoundError("Missing frozen 2026-07-03 SOL search evidence")
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _legs, priorities = simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    observed = metrics(engine, merged)
    source = json.loads(SOURCE_JSON.read_text(encoding="utf-8"))["best"]
    source_window = {
        "train": "train",
        "validation": "validation",
        "prefit": "prefit",
        "reused_holdout": "holdout",
        "current_full": "full",
    }
    for window, source_prefix in source_window.items():
        for metric in ("trades", "annual_multiple", "max_dd", "win_rate"):
            expected = float(source[f"{source_prefix}_{metric}"])
            actual = float(observed[window][metric])
            if abs(expected - actual) > 1e-12:
                raise RuntimeError(
                    f"V1 registration drift at {window}.{metric}: "
                    f"{actual} != {expected}"
                )
    payload = config_payload(engine)
    payload["metrics"] = observed
    payload["standard_slices"] = standard_slices(engine, merged)
    payload["component_prefit_priority_scores"] = priorities
    payload["data_quality"] = quality
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    V1_CONFIG_JSON.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
