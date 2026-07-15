from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean_audit
from as6s_engine import (
    BASE_SLIPPAGE,
    REUSED_END,
    STARTS,
    SYMBOLS,
    StrategyConfig,
    funding_arrays,
    load_funding,
    load_symbol_frame,
    simulate_opportunities,
)
from as6s_live_safe_router import nonpreemptive, preemptive
from combine_hybrid_asset_specific_account import UnifiedTrade
import research_binance_as6s_asset_first_v3 as v3


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
V4_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json"
)
V4_TRADES_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v4_live_safe_candidate_trades_2026-07-14.csv"
)
OUTPUT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v4_joint_state_audit_2026-07-14.json"
)
TRADES_OUTPUT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v4_joint_state_audit_trades_2026-07-14.csv"
)


def frozen_trade(
    trade: UnifiedTrade, sleeve_row: dict[str, Any]
) -> UnifiedTrade:
    quality = float(sleeve_row["quality"])
    return replace(
        trade,
        exposure=float(sleeve_row["exposure"]),
        strength=float(
            0.75 * quality + 0.25 * np.clip(trade.raw_strength, 0.0, 1.0)
        ),
    )


def legacy_raw_universe(
    selected: tuple[str, ...], sleeve_audit: dict[str, Any]
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    universe, _ = v3.legacy_universe()
    return {
        sleeve: {
            scenario: [
                frozen_trade(trade, sleeve_audit[sleeve]) for trade in rows
            ]
            for scenario, rows in universe[sleeve].items()
        }
        for sleeve in selected
        if sleeve.startswith("legacy1h:")
    }


def frontier_raw_universe(
    selected: tuple[str, ...],
    sleeve_audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding_frames: dict[str, pd.DataFrame],
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for sleeve in selected:
        if not sleeve.startswith("frontier15m:"):
            continue
        audit = sleeve_audit[sleeve]
        symbol = audit["symbol"]
        config = StrategyConfig.from_dict(audit["config"])
        scenarios: dict[str, list[UnifiedTrade]] = {}
        for scenario, slippage, delay in (
            ("base", BASE_SLIPPAGE, 1),
            ("stress_8bps", 0.0008, 1),
            ("k_plus_2", BASE_SLIPPAGE, 2),
        ):
            raw = simulate_opportunities(
                frames[symbol],
                funding_frames[symbol],
                config,
                end=REUSED_END,
                slippage=slippage,
                entry_delay_bars=delay,
            )
            rows = [
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=symbol,
                    mechanism=config.mechanism,
                    source_timeframe="15m",
                    side=item.side,
                    entry_ts=item.entry_ts,
                    exit_ts=item.exit_ts,
                    entry_price=item.entry_fill,
                    net_return_1x=item.net_return_1x,
                    mae_return_1x=item.mae_return_1x,
                    raw_strength=item.score,
                    exit_reason=item.exit_reason,
                )
                for item in raw
                if STARTS[symbol] <= item.entry_ts < REUSED_END
                and item.exit_ts < REUSED_END
            ]
            scenarios[scenario] = [frozen_trade(row, audit) for row in rows]
        universe[sleeve] = scenarios
    return universe


def clean_rsi_raw_universe(
    selected: tuple[str, ...],
    sleeve_audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding_frames: dict[str, pd.DataFrame],
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    scenario_map = {
        "base": clean_audit.Scenario("base", BASE_SLIPPAGE, 1),
        "stress_8bps": clean_audit.Scenario("stress_8bps", 0.0008, 1),
        "k_plus_2": clean_audit.Scenario("k_plus_2", BASE_SLIPPAGE, 2),
    }
    for sleeve in selected:
        if not sleeve.startswith("cleanrsi15m:"):
            continue
        audit = sleeve_audit[sleeve]
        symbol = audit["symbol"]
        config = clean_audit.Config(**audit["config"])
        raw = frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
        features = clean_audit.evolution.add_rsi_features(
            clean_audit.evolution.add_features(raw, [])
        )
        market = clean_audit.mii.build_market_arrays(features)
        state = clean_audit.mii.signal_state(features, config.signal)
        funding_times, funding_prefix = funding_arrays(funding_frames[symbol])
        scenarios: dict[str, list[UnifiedTrade]] = {}
        for scenario_name, scenario in scenario_map.items():
            raw_trades = clean_audit.robust_trades(
                market,
                state,
                config.exit,
                funding_times,
                funding_prefix,
                slippage=scenario.slippage,
                entry_delay_bars=scenario.entry_delay_bars,
            )
            # The signal filter is entry-known and remains part of the strategy.
            # Only virtual sleeve occupancy is removed: account acceptance is the
            # sole event allowed to create position/cooldown state.
            filtered = [
                trade
                for trade in raw_trades
                if clean_audit.mii.passes_filter(trade, config.filter)
                and STARTS[symbol] <= trade.entry_ts < REUSED_END
                and trade.exit_ts < REUSED_END
            ]
            rows = [
                UnifiedTrade(
                    sleeve=sleeve,
                    symbol=symbol,
                    mechanism="clean_rsi_reversal",
                    source_timeframe="15m",
                    side=trade.direction,
                    entry_ts=trade.entry_ts,
                    exit_ts=trade.exit_ts,
                    entry_price=trade.entry_price,
                    net_return_1x=trade.raw_return,
                    mae_return_1x=trade.min_path_return,
                    raw_strength=0.0,
                    exit_reason=trade.exit_reason,
                )
                for trade in filtered
            ]
            scenarios[scenario_name] = [frozen_trade(row, audit) for row in rows]
        universe[sleeve] = scenarios
    return universe


def route_signature(frame: pd.DataFrame) -> list[tuple[str, str, int]]:
    return [
        (str(row.sleeve), pd.Timestamp(row.entry_ts).isoformat(), int(row.side))
        for row in frame.itertuples()
    ]


def main() -> None:
    v4 = json.loads(V4_PATH.read_text(encoding="utf-8"))
    selected = tuple(v4["selected_sleeves"])
    sleeve_audit = v4["sleeve_audit"]
    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding_frames = {
        symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS
    }
    universe = {
        **legacy_raw_universe(selected, sleeve_audit),
        **frontier_raw_universe(selected, sleeve_audit, frames, funding_frames),
        **clean_rsi_raw_universe(selected, sleeve_audit, frames, funding_frames),
    }
    if set(universe) != set(selected):
        raise RuntimeError("joint-state reconstruction is missing selected sleeves")

    funding = {symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()}
    old_trades = pd.read_csv(V4_TRADES_PATH)
    old_trades["entry_ts"] = pd.to_datetime(old_trades["entry_ts"], utc=True)
    old_trades["exit_ts"] = pd.to_datetime(old_trades["exit_ts"], utc=True)
    output_rows: list[dict[str, Any]] = []
    comparisons: dict[str, Any] = {}
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        params = v4["comparisons"][mode]["frozen_params"]
        comparisons[mode] = {"frozen_params": params, "scenarios": {}}
        for scenario in v3.SCENARIOS:
            items = [
                trade
                for sleeve in selected
                for trade in universe[sleeve][scenario]
            ]
            if mode == "nonpreemptive":
                trades = nonpreemptive(
                    items, start=v3.RESEARCH_START, end=REUSED_END
                )
            else:
                trades = preemptive(
                    items,
                    start=v3.RESEARCH_START,
                    end=REUSED_END,
                    threshold=params["threshold"],
                    margin=params["margin"],
                    min_hold_hours=params["min_hold_hours"],
                    bars=frames,
                    funding=funding,
                    slippage=(
                        0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE
                    ),
                )
            metrics = v3.all_slices(trades, params["account_scale"])
            old_metrics = v4["comparisons"][mode]["scenarios"][scenario]
            comparisons[mode]["scenarios"][scenario] = {
                "joint_state": metrics,
                "v4_virtual_sleeve_state": old_metrics,
                "full_delta": {
                    key: metrics["full"][key] - old_metrics["full"][key]
                    for key in (
                        "trades",
                        "wins",
                        "win_rate",
                        "total_return",
                        "annual_multiple",
                        "max_dd",
                    )
                },
            }
            if scenario == "base":
                output_rows.extend(
                    {
                        "mode": mode,
                        "scenario": scenario,
                        "account_scale": params["account_scale"],
                        **asdict(trade),
                    }
                    for trade in trades
                )

        old_base = old_trades.loc[
            (old_trades["mode"] == mode) & (old_trades["scenario"] == "base")
        ]
        new_base = pd.DataFrame(
            [row for row in output_rows if row["mode"] == mode]
        )
        comparisons[mode]["base_ledger_changed"] = (
            route_signature(old_base) != route_signature(new_base)
        )
        comparisons[mode]["base_old_trades"] = len(old_base)
        comparisons[mode]["base_new_trades"] = len(new_base)

    pd.DataFrame(output_rows).to_csv(TRADES_OUTPUT_PATH, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": v4["family"],
        "stage": "v4_joint_state_live_semantics_audit",
        "post_selection_data_read": False,
        "change_under_test": (
            "remove frontier15m and cleanrsi15m virtual sleeve occupancy; only an "
            "account-accepted entry may create position or cooldown state"
        ),
        "selection_parameters_strength_exposure_unchanged": True,
        "selected_sleeves": list(selected),
        "candidate_counts": {
            sleeve: {
                scenario: len(rows) for scenario, rows in scenarios.items()
            }
            for sleeve, scenarios in universe.items()
        },
        "comparisons": comparisons,
        "conclusion": {
            "historical_ledger_changed": any(
                row["base_ledger_changed"] for row in comparisons.values()
            ),
            "v4_live_executable_gate": "FAIL",
            "reason": (
                "V4 candidate streams pre-applied counterfactual sleeve occupancy; "
                "the joint account must own the only executable position state"
            ),
        },
        "trades_csv": str(TRADES_OUTPUT_PATH.relative_to(ROOT)),
    }
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "conclusion": payload["conclusion"],
                "full_base": {
                    mode: row["scenarios"]["base"]["joint_state"]["full"]
                    for mode, row in comparisons.items()
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
