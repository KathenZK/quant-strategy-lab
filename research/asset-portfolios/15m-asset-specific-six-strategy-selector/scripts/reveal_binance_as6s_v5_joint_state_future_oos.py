from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import audit_binance_as6s_clean_rsi_hf_robustness as clean
from as6s_engine import (
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
import reveal_binance_as6s_v3_future_oos as components
import verify_binance_as6s_v5_joint_state_freeze as verify


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR / "artifacts/binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
)
OUTPUT = (
    FAMILY_DIR / "artifacts/binance_as6s_v5_joint_state_future_oos_reveal_2026-10-14.json"
)
TRADES_OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v5_joint_state_future_oos_reveal_trades_2026-10-14.csv"
)
OOS_START = pd.Timestamp("2026-07-14T09:00:00Z")
OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-shot reveal for frozen AS6S V5 joint-state future OOS."
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Verify the freeze and readiness without reading future-window metrics.",
    )
    return parser.parse_args()


def load_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload["future_oos"]["start_inclusive"] != OOS_START.isoformat():
        raise RuntimeError("manifest OOS start drift")
    if payload["future_oos"]["end_exclusive"] != OOS_END.isoformat():
        raise RuntimeError("manifest OOS end drift")
    if payload["state_contract"]["account_position_owner"] != "global joint account only":
        raise RuntimeError("manifest does not freeze joint account state ownership")
    return payload


def future_ready() -> tuple[bool, str]:
    now = pd.Timestamp.now(tz="UTC")
    if now < OOS_END:
        return False, f"wall clock {now.isoformat()} is before {OOS_END.isoformat()}"
    return True, "wall-clock gate passed; data completeness is checked during load"


def convert_frontier_raw(
    sleeve: str,
    audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    config = StrategyConfig.from_dict(audit["config"])
    quality = float(audit["quality"])
    exposure = float(audit["exposure"])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in components.SCENARIOS.items():
        raw = simulate_opportunities(
            frames[symbol],
            funding[symbol],
            config,
            end=OOS_END,
            slippage=slippage,
            entry_delay_bars=delay,
        )
        output[scenario] = [
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
                strength=float(
                    0.75 * quality + 0.25 * np.clip(item.score, 0.0, 1.0)
                ),
                exposure=exposure,
                exit_reason=item.exit_reason,
            )
            for item in raw
            if STARTS[symbol] <= item.entry_ts < OOS_END and item.exit_ts < OOS_END
        ]
    return output


def convert_clean_raw(
    sleeve: str,
    audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    config = clean.Config(**audit["config"])
    strength = 0.75 * float(audit["quality"])
    exposure = float(audit["exposure"])
    raw = frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    market = clean.mii.build_market_arrays(features)
    state = clean.mii.signal_state(features, config.signal)
    times, prefix = funding_arrays(funding[symbol])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in components.SCENARIOS.items():
        trades = clean.robust_trades(
            market,
            state,
            config.exit,
            times,
            prefix,
            slippage=slippage,
            entry_delay_bars=delay,
        )
        output[scenario] = [
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
                strength=strength,
                exposure=exposure,
                exit_reason=trade.exit_reason,
            )
            for trade in trades
            if clean.mii.passes_filter(trade, config.filter)
            and STARTS[symbol] <= trade.entry_ts < OOS_END
            and trade.exit_ts < OOS_END
        ]
    return output


def build_universe(
    manifest: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    # Keep the inherited legacy 1h regeneration on this reveal's single frozen
    # end boundary.  The assignment is also exercised by the historical parity
    # test, which temporarily moves the boundary back to REUSED_END.
    components.OOS_END = OOS_END
    legacy_rows, cooldowns = components.legacy_components(funding)
    output: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for sleeve in manifest["selected_sleeves"]:
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] == "prefit_frontier_asset_first":
            output[sleeve] = convert_frontier_raw(sleeve, audit, frames, funding)
        elif audit["source"] == "asset_specific_clean_rsi_hf":
            output[sleeve] = convert_clean_raw(sleeve, audit, frames, funding)
        elif audit["source"] == "legacy_asset_specific_1h":
            output[sleeve] = components.convert_legacy(
                sleeve, audit, legacy_rows, cooldowns
            )
        else:
            raise RuntimeError(f"unknown frozen sleeve source: {audit['source']}")
    return output


def route_results(
    manifest: dict[str, Any],
    universe: dict[str, dict[str, list[UnifiedTrade]]],
    frames: dict[str, pd.DataFrame],
    funding_frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    funding = {
        symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()
    }
    results: dict[str, Any] = {}
    output_trades: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        params = manifest["routes"][mode]
        scale = float(params["account_scale"])
        results[mode] = {"params": params, "scenarios": {}}
        for scenario, (slippage, _delay) in components.SCENARIOS.items():
            items = [
                trade
                for sleeve in manifest["selected_sleeves"]
                for trade in universe[sleeve][scenario]
            ]
            if mode == "nonpreemptive":
                trades = nonpreemptive(
                    items, start=components.frozen.RESEARCH_START, end=OOS_END
                )
            else:
                trades = preemptive(
                    items,
                    start=components.frozen.RESEARCH_START,
                    end=OOS_END,
                    threshold=float(params["threshold"]),
                    margin=float(params["margin"]),
                    min_hold_hours=int(params["min_hold_hours"]),
                    bars=frames,
                    funding=funding,
                    slippage=slippage,
                )
            results[mode]["scenarios"][scenario] = components.slices(trades, scale)
            if scenario == "base":
                output_trades.extend(
                    {
                        "mode": mode,
                        "scenario": scenario,
                        "account_scale": scale,
                        **asdict(trade),
                    }
                    for trade in trades
                )
    return results, output_trades


def main() -> None:
    args = parse_args()
    manifest = load_manifest()
    verify.main()
    ready, reason = future_ready()
    if args.check_only:
        print(
            json.dumps(
                {
                    "freeze": "PASS",
                    "future_oos_ready": ready,
                    "reason": reason,
                    "future_oos_start": OOS_START.isoformat(),
                    "future_oos_end": OOS_END.isoformat(),
                    "state_contract": manifest["state_contract"],
                },
                indent=2,
            )
        )
        return
    if not ready:
        raise RuntimeError(
            "future OOS reveal refused before the complete locked window: " + reason
        )

    frames = {symbol: load_symbol_frame(symbol, end=OOS_END) for symbol in SYMBOLS}
    funding = {symbol: load_funding(symbol, end=OOS_END) for symbol in SYMBOLS}
    universe = build_universe(manifest, frames, funding)
    results, trades = route_results(manifest, universe, frames, funding)
    gates = components.final_gates(results)
    pd.DataFrame(trades).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "one_shot_v5_joint_state_future_oos_reveal",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "future_oos": [OOS_START.isoformat(), OOS_END.isoformat()],
        "state_contract": manifest["state_contract"],
        "results": results,
        "final_gates": gates,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "final_gates": gates}, indent=2))


if __name__ == "__main__":
    main()
