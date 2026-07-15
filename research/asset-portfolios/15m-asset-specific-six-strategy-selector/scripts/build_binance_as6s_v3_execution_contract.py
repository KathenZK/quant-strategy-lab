from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
FREEZE_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v3_future_oos_freeze_2026-07-14.json"
)
CANDIDATE_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
)
OUTPUT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v3_execution_contract_2026-07-14.json"
)

SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "TRXUSDT", "HYPEUSDT")
CCXT_SYMBOLS = {symbol: f"{symbol[:-4]}/USDT:USDT" for symbol in SYMBOLS}

LEGACY_RUNNER_LEGS = {
    "legacy1h:BNBUSDT:wick_reject": "BNB_1H_AR_V2_WICK_REJECT_T01080",
    "legacy1h:BTCUSDT:keltner_break": "BTC_1H_AR_V4_KELTNER",
    "legacy1h:ETHUSDT:rsi_reversal": "ETH_1H_AR_V1_RSI",
    "legacy1h:HYPEUSDT:di_cross": "HYPE_1H_AR_V4_DI",
    "legacy1h:SOLUSDT:donchian_break": "SOL_1H_AR_HW_R132002",
    "legacy1h:TRXUSDT:macd_flip": "TRX_1H_AR_V2_MACD",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metric_slice(candidate: dict[str, Any], route: str, scenario: str) -> dict[str, Any]:
    source = candidate["comparisons"][route]["scenarios"][scenario]
    return {
        window: {
            key: source[window][key]
            for key in (
                "trades",
                "trades_per_day",
                "win_rate",
                "total_return",
                "annual_multiple",
                "max_dd",
                "preemptions",
            )
        }
        for window in ("full", "all_six_active", "3m")
    }


def main() -> None:
    freeze = load_json(FREEZE_PATH)
    candidate = load_json(CANDIDATE_PATH)

    selected = freeze["selected_sleeves"]
    configs = freeze["sleeve_configs"]
    if len(selected) != 15 or set(selected) != set(candidate["selected_sleeves"]):
        raise RuntimeError("V3 selected-sleeve boundary drifted")
    if any(sleeve not in configs for sleeve in selected):
        raise RuntimeError("V3 freeze is missing selected sleeve config")

    sleeves: list[dict[str, Any]] = []
    for sleeve_id in selected:
        frozen = configs[sleeve_id]
        timeframe = "1h" if sleeve_id.startswith("legacy1h:") else "15m"
        symbol = frozen["symbol"]
        exposure = float(frozen["exposure"])
        sleeve = {
            "sleeve_id": sleeve_id,
            "symbol": symbol,
            "ccxt_symbol": CCXT_SYMBOLS[symbol],
            "source_timeframe": timeframe,
            "source": frozen["source"],
            "mechanism": frozen["mechanism"],
            "exposure": exposure,
            "quality": float(frozen["quality"]),
            "quality_raw": float(frozen["quality_raw"]),
            "config": frozen.get("config"),
            "effective_allocation": {
                route: round(exposure * float(params["account_scale"]), 12)
                for route, params in freeze["routes"].items()
            },
        }
        if timeframe == "1h":
            sleeve["legacy_runner_reference"] = {
                "strategy_id": "BIN-1H-AR-MAE-V1",
                "runner_leg_id": LEGACY_RUNNER_LEGS[sleeve_id],
                "note": "reference only; V3 must use its own joint state machine",
            }
        sleeves.append(sleeve)

    assets = {sleeve["symbol"] for sleeve in sleeves}
    if assets != set(SYMBOLS):
        raise RuntimeError(f"unexpected V3 asset universe: {sorted(assets)}")

    requirements = []
    for symbol in SYMBOLS:
        requirements.extend(
            [
                {
                    "exchange": "binance",
                    "symbol": CCXT_SYMBOLS[symbol],
                    "timeframe": "15m",
                    "warmup_bars_min": 1200,
                    "include_mark_price": True,
                    "include_funding": True,
                    "role": "decision_clock_and_native_15m_or_preemption_exit",
                },
                {
                    "exchange": "binance",
                    "symbol": CCXT_SYMBOLS[symbol],
                    "timeframe": "1h",
                    "warmup_bars_min": 1200,
                    "include_mark_price": False,
                    "include_funding": False,
                    "role": "native_1h_signal_and_exit_state",
                },
            ]
        )

    routes = freeze["routes"]
    max_effective = {
        route: max(row["effective_allocation"][route] for row in sleeves)
        for route in routes
    }
    if max_effective["nonpreemptive"] > 1.20 + 1e-12:
        raise RuntimeError("nonpreemptive leverage drift")
    if max_effective["strong_breakout_preemptive"] > 0.99 + 1e-12:
        raise RuntimeError("preemptive leverage drift")

    contract = {
        "contract_version": 1,
        "family": freeze["family"],
        "observation_id": "AS6S-ASSET-FIRST-V3-2026-07-14",
        "status": freeze["status"],
        "promotion_boundary": {
            "registered": False,
            "promoted": False,
            "live_ready": False,
            "future_oos": freeze["future_oos"],
        },
        "source_integrity": {
            "freeze_path": str(FREEZE_PATH.relative_to(ROOT)),
            "freeze_sha256": sha256(FREEZE_PATH),
            "candidate_path": str(CANDIDATE_PATH.relative_to(ROOT)),
            "candidate_sha256": sha256(CANDIDATE_PATH),
        },
        "decision_clock": {
            "timeframe": "15m",
            "primary_symbol": "BTC/USDT:USDT",
            "closed_bars_only": True,
            "entry_timing": "K+1 next open",
            "stress_timing": "K+2 research-only stress",
            "all_15m_dependencies_must_share_latest_closed_bar": True,
            "one_hour_signal_due_rule": (
                "eligible only at the first 15m open after its 1h bar closes; "
                "persist last_due_open_ts_by_sleeve to reject stale repeats"
            ),
        },
        "market_requirements": requirements,
        "sleeves": sleeves,
        "strength_contract": {
            "formula": "0.7 * frozen_sleeve_quality + 0.3 * signal_raw_strength",
            "tie_break": ["strength_desc", "exit_ts_asc", "sleeve_id_asc"],
            "recompute_while_held": False,
            "current_position_strength": "frozen at accepted entry candidate strength",
        },
        "routes": {
            "nonpreemptive": {
                **routes["nonpreemptive"],
                "max_effective_allocation": max_effective["nonpreemptive"],
                "position_policy": "never preempt; other signals are discarded",
            },
            "strong_breakout_preemptive": {
                **routes["strong_breakout_preemptive"],
                "max_effective_allocation": max_effective[
                    "strong_breakout_preemptive"
                ],
                "challenger_policy": (
                    "different symbol, breakout family, strength >= threshold, "
                    "strength >= current + margin, minimum hold satisfied"
                ),
                "replacement_timing": (
                    "close current and open challenger sequentially at the challenger due open; "
                    "never allow overlapping venue positions"
                ),
            },
        },
        "global_state_schema": {
            "active_position": [
                "symbol",
                "sleeve_id",
                "side",
                "entry_ts",
                "entry_price",
                "entry_strength",
                "entry_risk",
                "native_timeframe",
                "bars_held_native",
                "stop_price",
                "target_price",
                "best_price",
            ],
            "pending_transition": ["entry", "replacement", "protection_update"],
            "sleeve_cooldown_until": "keyed by sleeve_id, not asset",
            "last_due_open_ts_by_sleeve": "required for mixed-timeframe dedupe",
            "last_processed_15m_clock": "required for idempotency",
            "route_mode": "immutable for one strategy instance",
        },
        "execution_semantics": {
            "fee_per_fill": 0.001,
            "base_slippage_per_fill": 0.0004,
            "stress_slippage_per_fill": 0.0008,
            "gap_stop": "adverse actual open",
            "same_bar_stop_and_target": "stop first",
            "timeout": "native-timeframe target bar open before reading its high/low",
            "funding_interval": "entry inclusive, exit exclusive; direction signed",
            "flat_to_new_entry_same_timestamp": False,
            "signals_while_held": "discarded except qualified preemptive challengers",
        },
        "diagnostic_metrics": {
            route: {
                "base": metric_slice(candidate, route, "base"),
                "stress_8bps": metric_slice(candidate, route, "stress_8bps"),
                "k_plus_2": metric_slice(candidate, route, "k_plus_2"),
            }
            for route in ("nonpreemptive", "strong_breakout_preemptive")
        },
        "runner_compatibility": {
            "reusable_platform_capabilities": [
                "multi-market MarketRequirement bundle",
                "15m bundle cadence with 1h secondary dependencies",
                "persistent versioned driver state",
                "TargetPosition NextOpen",
                "Replace AfterFlat",
                "restart reconciliation and fail-closed dependency handling",
            ],
            "required_new_strategy_module": "asset_specific_six_selector",
            "must_not_mutate_existing_module": "six_asset_ensemble/BIN-1H-AR-MAE-V1",
            "live_readiness_blockers": [
                "V3 future OOS is unavailable and the observation is not registered",
                "15 heterogeneous sleeve engines are not implemented in quant-runner",
                "mixed-timeframe stale-signal dedupe has no V3 implementation or test",
                "nonpreemptive and preemptive runner replays have not matched the frozen trade ledger",
                "trade-price backtest protection versus exchange mark-price protection is unaudited",
                "preemptive two-symbol close-then-open fill parity is unaudited",
            ],
        },
        "parity_gates_before_any_promotion": [
            "candidate identity and route params exactly match this contract",
            "runner replay trade count and sleeve identity match frozen V3 by route/scenario",
            "entry_ts, exit_ts, side, exit_reason and preemption flags match trade by trade",
            "net return differences are explained only by an explicitly approved execution model",
            "restart snapshots reproduce uninterrupted decisions",
            "missing any required 15m or 1h series cannot increase risk",
            "exchange reconciliation proves global position count never exceeds one",
            "complete future OOS passes the frozen hard gates",
        ],
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
