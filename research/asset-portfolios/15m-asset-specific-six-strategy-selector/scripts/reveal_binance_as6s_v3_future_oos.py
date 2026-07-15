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
import audit_legacy_asset_specific_1h_sleeves as legacy
import research_binance_as6s_asset_first_v3 as frozen
import verify_binance_as6s_v3_freeze as verify
from as6s_engine import (
    STARTS,
    SYMBOLS,
    StrategyConfig,
    funding_arrays,
    load_funding,
    load_symbol_frame,
    select_nonoverlap,
    simulate_opportunities,
)
from combine_hybrid_asset_specific_account import (
    UnifiedTrade,
    nonpreemptive,
    preemptive,
    strict_metrics,
)


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = FAMILY_DIR / "artifacts/binance_as6s_v3_future_oos_freeze_2026-07-14.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v3_future_oos_reveal_2026-10-14.json"
TRADES_OUTPUT = (
    FAMILY_DIR / "artifacts/binance_as6s_v3_future_oos_reveal_trades_2026-10-14.csv"
)
OOS_START = pd.Timestamp("2026-07-14T09:00:00Z")
OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")
SCENARIOS = {
    "base": (0.0004, 1),
    "stress_8bps": (0.0008, 1),
    "k_plus_2": (0.0004, 2),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-shot reveal for frozen BIN-15M-AS6S-V3 future OOS."
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
    return payload


def future_ready() -> tuple[bool, str]:
    now = pd.Timestamp.now(tz="UTC")
    if now < OOS_END:
        return False, f"wall clock {now.isoformat()} is before {OOS_END.isoformat()}"
    return True, "wall-clock gate passed; data completeness is checked during load"


def convert_frontier(
    sleeve: str,
    audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    mechanism = audit["mechanism"]
    config = StrategyConfig.from_dict(audit["config"])
    exposure = float(audit["exposure"])
    quality = float(audit["quality"])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in SCENARIOS.items():
        opportunities = select_nonoverlap(
            simulate_opportunities(
                frames[symbol],
                funding[symbol],
                config,
                end=OOS_END,
                slippage=slippage,
                entry_delay_bars=delay,
            ),
            start=STARTS[symbol],
            end=OOS_END,
        )
        output[scenario] = [
            UnifiedTrade(
                sleeve=sleeve,
                symbol=symbol,
                mechanism=mechanism,
                source_timeframe="15m",
                side=item.side,
                entry_ts=item.entry_ts,
                exit_ts=item.exit_ts,
                entry_price=item.entry_fill,
                net_return_1x=item.net_return_1x,
                mae_return_1x=item.mae_return_1x,
                raw_strength=item.score,
                strength=float(0.75 * quality + 0.25 * np.clip(item.score, 0.0, 1.0)),
                exposure=exposure,
                exit_reason=item.exit_reason,
            )
            for item in opportunities
        ]
    return output


def convert_clean(
    sleeve: str,
    audit: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    config = clean.Config(**audit["config"])
    exposure = float(audit["exposure"])
    strength = 0.75 * float(audit["quality"])
    raw = frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
    features = clean.evolution.add_rsi_features(clean.evolution.add_features(raw, []))
    market = clean.mii.build_market_arrays(features)
    state = clean.mii.signal_state(features, config.signal)
    times, prefix = funding_arrays(funding[symbol])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, (slippage, delay) in SCENARIOS.items():
        trades = clean.robust_trades(
            market,
            state,
            config.exit,
            times,
            prefix,
            slippage=slippage,
            entry_delay_bars=delay,
        )
        selected = clean.select_nonoverlap(trades, config.filter)
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
            for trade in selected
            if trade.exit_ts < OOS_END
        ]
    return output


def legacy_components(
    funding: dict[str, pd.DataFrame],
) -> tuple[dict[str, dict[str, list[Any]]], dict[str, int]]:
    # The dependency hash is checked before this controlled end-date override.
    legacy.REUSED_END = OOS_END
    first, contexts = legacy.prepare_legacy()
    frames = {symbol: legacy.aggregate_h1(symbol) for symbol in SYMBOLS}
    scenario_rows: dict[str, dict[str, list[Any]]] = {}
    cooldowns: dict[str, int] | None = None
    for scenario, (slippage, delay) in SCENARIOS.items():
        rows, scenario_cooldowns = legacy.simulate_components(
            first,
            contexts,
            frames,
            funding,
            slippage=slippage,
            delay=delay,
        )
        scenario_rows[scenario] = rows
        if cooldowns is None:
            cooldowns = scenario_cooldowns
        elif cooldowns != scenario_cooldowns:
            raise RuntimeError("legacy cooldown drift across scenarios")
    if cooldowns is None:
        raise RuntimeError("legacy scenarios were not generated")
    return scenario_rows, cooldowns


def convert_legacy(
    sleeve: str,
    audit: dict[str, Any],
    scenario_rows: dict[str, dict[str, list[Any]]],
    cooldowns: dict[str, int],
) -> dict[str, list[UnifiedTrade]]:
    symbol = audit["symbol"]
    asset = symbol.removesuffix("USDT")
    style = audit["mechanism"]
    key = f"{asset}:{style}"
    exposure = float(audit["exposure"])
    strength = 0.75 * float(audit["quality"])
    output: dict[str, list[UnifiedTrade]] = {}
    for scenario, rows in scenario_rows.items():
        output[scenario] = [
            UnifiedTrade(
                sleeve=sleeve,
                symbol=symbol,
                mechanism=style,
                source_timeframe="1h",
                side=int(trade.side),
                entry_ts=trade.entry_ts,
                exit_ts=trade.exit_ts,
                entry_price=float(trade.entry_price),
                net_return_1x=float(trade.net_ret_1x),
                mae_return_1x=float(trade.mae_1x),
                raw_strength=0.0,
                cooldown_hours=int(cooldowns[key]),
                strength=strength,
                exposure=exposure,
                exit_reason=str(trade.exit_reason),
            )
            for trade in rows[key]
            if trade.exit_ts < OOS_END
        ]
    return output


def build_universe(
    manifest: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
) -> dict[str, dict[str, list[UnifiedTrade]]]:
    selected = manifest["selected_sleeves"]
    audits = manifest["sleeve_configs"]
    legacy_rows, cooldowns = legacy_components(funding)
    universe: dict[str, dict[str, list[UnifiedTrade]]] = {}
    for sleeve in selected:
        audit = audits[sleeve]
        source = audit["source"]
        if source == "prefit_frontier_asset_first":
            universe[sleeve] = convert_frontier(sleeve, audit, frames, funding)
        elif source == "asset_specific_clean_rsi_hf":
            universe[sleeve] = convert_clean(sleeve, audit, frames, funding)
        elif source == "legacy_asset_specific_1h":
            universe[sleeve] = convert_legacy(
                sleeve, audit, legacy_rows, cooldowns
            )
        else:
            raise RuntimeError(f"unknown frozen sleeve source: {source}")
    return universe


def metric(
    trades: list[UnifiedTrade], start: pd.Timestamp, end: pd.Timestamp, scale: float
) -> dict[str, Any]:
    result = strict_metrics(trades, start, end, scale)
    days = max((end - start).total_seconds() / 86400.0, 1.0)
    return {**result, "trades_per_day": result["trades"] / days}


def slices(trades: list[UnifiedTrade], scale: float) -> dict[str, Any]:
    starts = {
        "1d": OOS_END - pd.Timedelta(days=1),
        "7d": OOS_END - pd.Timedelta(days=7),
        "1m": OOS_END - pd.DateOffset(months=1),
        "3m_future_oos": OOS_START,
        "6m": OOS_END - pd.DateOffset(months=6),
        "1y": OOS_END - pd.DateOffset(years=1),
        "full": frozen.RESEARCH_START,
    }
    return {
        name: metric(trades, start, OOS_END, scale)
        for name, start in starts.items()
    }


def route_results(
    manifest: dict[str, Any],
    universe: dict[str, dict[str, list[UnifiedTrade]]],
    frames: dict[str, pd.DataFrame],
    funding_frames: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    funding = {symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()}
    results: dict[str, Any] = {}
    output_trades: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        params = manifest["routes"][mode]
        scale = float(params["account_scale"])
        results[mode] = {"params": params, "scenarios": {}}
        for scenario, (slippage, _delay) in SCENARIOS.items():
            items = [
                trade
                for sleeve in manifest["selected_sleeves"]
                for trade in universe[sleeve][scenario]
            ]
            if mode == "nonpreemptive":
                trades = nonpreemptive(
                    items, start=frozen.RESEARCH_START, end=OOS_END
                )
            else:
                trades = preemptive(
                    items,
                    start=frozen.RESEARCH_START,
                    end=OOS_END,
                    threshold=float(params["threshold"]),
                    margin=float(params["margin"]),
                    min_hold_hours=int(params["min_hold_hours"]),
                    bars=frames,
                    funding=funding,
                    slippage=slippage,
                )
            results[mode]["scenarios"][scenario] = slices(trades, scale)
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


def final_gates(results: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mode, rows in results.items():
        base = rows["scenarios"]["base"]
        stress = rows["scenarios"]["stress_8bps"]["3m_future_oos"]
        delayed = rows["scenarios"]["k_plus_2"]["3m_future_oos"]
        full = base["full"]
        oos = base["3m_future_oos"]
        checks = {
            "full_trades_ge_200": full["trades"] >= 200,
            "future_oos_trades_ge_30": oos["trades"] >= 30,
            "full_win_rate_ge_80pct": full["win_rate"] >= 0.80,
            "future_oos_win_rate_ge_80pct": oos["win_rate"] >= 0.80,
            "full_max_dd_lt_20pct": full["max_dd"] > -0.20,
            "future_oos_max_dd_lt_20pct": oos["max_dd"] > -0.20,
            "full_return_positive": full["total_return"] > 0.0,
            "future_oos_return_positive": oos["total_return"] > 0.0,
            "stress_oos_positive_dd_lt_20pct": (
                stress["total_return"] > 0.0 and stress["max_dd"] > -0.20
            ),
            "k_plus_2_oos_positive_dd_lt_20pct": (
                delayed["total_return"] > 0.0 and delayed["max_dd"] > -0.20
            ),
        }
        output[mode] = {"checks": checks, "final_future_oos_pass": all(checks.values())}
    return output


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
    gates = final_gates(results)
    pd.DataFrame(trades).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "one_shot_frozen_future_oos_reveal",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "future_oos": [OOS_START.isoformat(), OOS_END.isoformat()],
        "results": results,
        "final_gates": gates,
        "trades_csv": str(TRADES_OUTPUT.relative_to(ROOT)),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(OUTPUT), "final_gates": gates}, indent=2))


if __name__ == "__main__":
    main()
