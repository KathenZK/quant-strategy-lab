from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/btc/1h-adaptive-regime"
SEARCH_SCRIPT = FAMILY_DIR / "scripts/research_btc_1h_adaptive_regime_search.py"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
V1_CONFIG_JSON = ARTIFACT_DIR / "btc_1h_ar_v1_config_2026-07-02.json"

TRAIN_START = pd.Timestamp("2024-08-16T10:00:00Z")
TRAIN_END = pd.Timestamp("2025-09-06T12:24:00Z")
PREFIT_END = pd.Timestamp("2026-04-02T10:00:00Z")
FULL_END = pd.Timestamp("2026-07-02T10:00:00Z")

V1_KELTNER = {
    "name": "BTC_1H_AR_V1_KELTNER",
    "style": "keltner_break",
    "side_mode": "both",
    "ema_fast": 55,
    "ema_slow": 144,
    "ema_htf": 55,
    "indicator_window": 20,
    "threshold_low": 20.0,
    "threshold_high": 85.0,
    "band_k": 2.5,
    "pullback_atr": 0.75,
    "roc_window": 24,
    "roc_threshold_bps": 300.0,
    "macd_fast": 8,
    "macd_slow": 21,
    "macd_signal": 5,
    "min_adx": 36.0,
    "max_adx": 100.0,
    "min_rvol": 0.8,
    "min_atr_bps": 0.0,
    "max_atr_bps": 200.0,
    "min_dir_roc_bps": 0.0,
    "max_dist_ema_bps": 10000.0,
    "htf_mode": "d1",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 2.0,
    "exit_kind": "fixed",
    "tp_atr": 1.5,
    "sl_atr": 4.0,
    "trail_activation_atr": 3.0,
    "trail_atr": 1.5,
    "max_hold_bars": 120,
    "cooldown_bars": 6,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 3.0,
    "risk_fraction": 0.015,
    "max_leverage": 2.0,
}

V1_CCI = {
    "name": "BTC_1H_AR_V1_CCI",
    "style": "cci_reversal",
    "side_mode": "long",
    "ema_fast": 89,
    "ema_slow": 233,
    "ema_htf": 144,
    "indicator_window": 20,
    "threshold_low": 40.0,
    "threshold_high": 125.0,
    "band_k": 1.5,
    "pullback_atr": -0.25,
    "roc_window": 48,
    "roc_threshold_bps": 300.0,
    "macd_fast": 21,
    "macd_slow": 55,
    "macd_signal": 9,
    "min_adx": 0.0,
    "max_adx": 36.0,
    "min_rvol": 1.5,
    "min_atr_bps": 50.0,
    "max_atr_bps": 300.0,
    "min_dir_roc_bps": -10000.0,
    "max_dist_ema_bps": 1000.0,
    "htf_mode": "none",
    "require_macd_turn": False,
    "require_body_dir": False,
    "max_aligned_funding_bps": 10000.0,
    "exit_kind": "fixed",
    "tp_atr": 4.0,
    "sl_atr": 1.25,
    "trail_activation_atr": 0.75,
    "trail_atr": 1.25,
    "max_hold_bars": 96,
    "cooldown_bars": 24,
    "entry_delay_bars": 1,
    "sizing_kind": "fixed",
    "fixed_leverage": 4.0,
    "risk_fraction": 0.01,
    "max_leverage": 2.5,
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
    search = load_module(SEARCH_SCRIPT, "btc_1h_ar_v1_search")
    engine = search.load_engine()
    frame, funding, quality = search.load_data()
    frame = engine.add_features(frame, funding)
    return engine, frame, funding, quality


def v1_configs(engine: Any) -> tuple[Any, Any]:
    return (
        engine.StrategyConfig(**V1_KELTNER),
        engine.StrategyConfig(**V1_CCI),
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
    keltner: Any | None = None,
    cci: Any | None = None,
) -> tuple[list[Any], list[Any], list[Any], tuple[float, float]]:
    base_keltner, base_cci = v1_configs(engine)
    keltner = keltner or base_keltner
    cci = cci or base_cci
    keltner_trades = simulate_component(
        engine, frame, funding_times, funding_cumulative, keltner
    )
    cci_trades = simulate_component(
        engine, frame, funding_times, funding_cumulative, cci
    )
    priorities = (
        component_score(engine, keltner_trades),
        component_score(engine, cci_trades),
    )
    merged = engine.merge_trade_sets(
        keltner_trades,
        cci_trades,
        priorities[0],
        priorities[1],
    )
    return merged, keltner_trades, cci_trades, priorities


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
    engine: Any, keltner: Any, cci: Any, suffix: str
) -> tuple[Any, Any]:
    return (
        replace(keltner, name=f"BTC_1H_AR_{suffix}_KELTNER"),
        replace(cci, name=f"BTC_1H_AR_{suffix}_CCI"),
    )


def config_payload(engine: Any) -> dict[str, Any]:
    keltner, cci = v1_configs(engine)
    return {
        "family": "BTC-1H-Adaptive-Regime",
        "version": "BTC-1H-Adaptive-Regime-V1",
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
            "keltner_break": asdict(keltner),
            "cci_reversal": asdict(cci),
        },
        "ensemble": {
            "position_mode": "single_position_no_pyramiding",
            "priority": "prefit_score_descending",
        },
    }


def main() -> None:
    engine, frame, funding, quality = load_context()
    funding_times, funding_cumulative = engine.funding_prefix(funding)
    merged, _keltner, _cci, priorities = simulate_v1(
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
