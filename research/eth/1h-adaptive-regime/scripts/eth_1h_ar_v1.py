from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/eth/1h-adaptive-regime"
SEARCH_SCRIPT = FAMILY_DIR / "scripts/research_eth_1h_adaptive_regime_search.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V1_CONFIG_JSON = ARTIFACT_DIR / "eth_1h_ar_v1_config_2026-07-03.json"

TRAIN_START = pd.Timestamp("2024-08-17T05:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-07T07:24:00Z")
PREFIT_END = pd.Timestamp("2026-04-03T05:00:00Z")
FULL_END = pd.Timestamp("2026-07-03T05:00:00Z")

V1_BB_BREAK = {
    "name": "ETH_1H_AR_V1_BB_BREAK",
    "style": "bb_break",
    "side_mode": "long",
    "ema_fast": 13,
    "ema_slow": 34,
    "ema_htf": 89,
    "indicator_window": 72,
    "threshold_low": 40.0,
    "threshold_high": 85.0,
    "band_k": 2.0,
    "pullback_atr": 0.25,
    "roc_window": 12,
    "roc_threshold_bps": 50.0,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "min_adx": 16.0,
    "max_adx": 100.0,
    "min_rvol": 2.0,
    "min_atr_bps": 75.0,
    "max_atr_bps": 250.0,
    "min_dir_roc_bps": -200.0,
    "max_dist_ema_bps": 750.0,
    "htf_mode": "none",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 2.0,
    "exit_kind": "fixed",
    "tp_atr": 3.0,
    "sl_atr": 2.5,
    "trail_activation_atr": 0.75,
    "trail_atr": 0.75,
    "max_hold_bars": 18,
    "cooldown_bars": 0,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 2.5,
    "risk_fraction": 0.015,
    "max_leverage": 3.0,
}

V1_RSI = {
    "name": "ETH_1H_AR_V1_RSI",
    "style": "rsi_reversal",
    "side_mode": "both",
    "ema_fast": 55,
    "ema_slow": 233,
    "ema_htf": 89,
    "indicator_window": 21,
    "threshold_low": 15.0,
    "threshold_high": 60.0,
    "band_k": 1.5,
    "pullback_atr": 0.0,
    "roc_window": 3,
    "roc_threshold_bps": 100.0,
    "macd_fast": 21,
    "macd_slow": 55,
    "macd_signal": 9,
    "min_adx": 0.0,
    "max_adx": 45.0,
    "min_rvol": 0.0,
    "min_atr_bps": 100.0,
    "max_atr_bps": 600.0,
    "min_dir_roc_bps": 50.0,
    "max_dist_ema_bps": 750.0,
    "htf_mode": "none",
    "require_macd_turn": False,
    "require_body_dir": True,
    "max_aligned_funding_bps": 2.0,
    "exit_kind": "fixed",
    "tp_atr": 3.0,
    "sl_atr": 2.0,
    "trail_activation_atr": 0.75,
    "trail_atr": 2.0,
    "max_hold_bars": 12,
    "cooldown_bars": 6,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 1.0,
    "risk_fraction": 0.03,
    "max_leverage": 4.0,
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
    search = load_module(SEARCH_SCRIPT, "eth_1h_ar_v1_search")
    engine = search.load_engine()
    frame, funding, quality = search.load_data()
    frame = engine.add_features(frame, funding)
    return engine, frame, funding, quality


def v1_configs(engine: Any) -> tuple[Any, Any]:
    return (
        engine.StrategyConfig(**V1_BB_BREAK),
        engine.StrategyConfig(**V1_RSI),
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
    bb_break: Any | None = None,
    rsi: Any | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    base_bb_break, base_rsi = v1_configs(engine)
    bb_break = bb_break or base_bb_break
    rsi = rsi or base_rsi
    bb_break_trades = simulate_component(
        engine, frame, funding_times, funding_cumulative, bb_break
    )
    rsi_trades = simulate_component(
        engine, frame, funding_times, funding_cumulative, rsi
    )
    priorities = (
        component_score(engine, bb_break_trades),
        component_score(engine, rsi_trades),
    )
    merged = engine.merge_trade_sets(
        bb_break_trades,
        rsi_trades,
        priorities[0],
        priorities[1],
    )
    return merged, bb_break_trades, rsi_trades, priorities


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


def named_configs(
    engine: Any, bb_break: Any, rsi: Any, suffix: str
) -> tuple[Any, Any]:
    return (
        replace(bb_break, name=f"ETH_1H_AR_{suffix}_BB_BREAK"),
        replace(rsi, name=f"ETH_1H_AR_{suffix}_RSI"),
    )


def config_payload(engine: Any) -> dict[str, Any]:
    bb_break, rsi = v1_configs(engine)
    return {
        "family": "ETH-1H-Adaptive-Regime",
        "version": "ETH-1H-Adaptive-Regime-V1",
        "status": "diagnostic_baseline_no_go_not_live_ready",
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
            "bb_break": asdict(bb_break),
            "rsi_reversal": asdict(rsi),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_score_descending",
        },
    }


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _bb_break, _rsi, priorities = simulate_v1(
        engine, frame, funding_times, funding_cumulative
    )
    payload = config_payload(engine)
    payload["metrics"] = metrics(engine, merged)
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
