from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import STARTS, load_funding, load_symbol_frame
import combine_binance_as6s_v6_microtuned_account as account
from combine_hybrid_asset_specific_account import UnifiedTrade
import replay_binance_as6s_v6_mark_price_account as mark_replay
import research_binance_as6s_v5_legacy_exact_full_ablation as legacy_full
import verify_binance_as6s_v6_mark_joint_freeze as verify


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json"
)
OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_joint_future_oos_reveal_2026-10-14.json"
)
TRADES_OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_joint_future_oos_reveal_trades_2026-10-14.csv"
)
OOS_START = pd.Timestamp("2026-07-14T09:00:00Z")
OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")
MODES = ("nonpreemptive", "strong_breakout_preemptive")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-shot reveal for frozen AS6S V6 mark-price joint state."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--check-only",
        action="store_true",
        help="Verify freeze/readiness without loading future-window market data.",
    )
    group.add_argument(
        "--historical-parity",
        action="store_true",
        help="Reconstruct only the frozen history ending at OOS_START.",
    )
    return parser.parse_args()


def load_manifest() -> dict[str, Any]:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if payload["future_oos"]["start_inclusive"] != OOS_START.isoformat():
        raise RuntimeError("manifest OOS start drift")
    if payload["future_oos"]["end_exclusive"] != OOS_END.isoformat():
        raise RuntimeError("manifest OOS end drift")
    if payload["arbitration"]["account_position_owner"] != "global joint account only":
        raise RuntimeError("manifest does not freeze global joint account state")
    return payload


def future_ready() -> tuple[bool, str]:
    now = pd.Timestamp.now(tz="UTC")
    if now < OOS_END:
        return False, f"wall clock {now.isoformat()} is before {OOS_END.isoformat()}"
    return True, "wall-clock gate passed; data completeness is checked during load"


def set_reconstruction_end(end: pd.Timestamp) -> None:
    account.REUSED_END = end
    mark_replay.REUSED_END = end
    legacy_full.REUSED_END = end
    legacy_full.legacy.REUSED_END = end


def assert_complete_market_data(
    end: pd.Timestamp,
    frames: dict[str, pd.DataFrame],
    marks: dict[str, pd.DataFrame],
) -> None:
    expected_last = end - pd.Timedelta(minutes=15)
    failures: list[str] = []
    for symbol in STARTS:
        if frames[symbol]["ts"].max() != expected_last:
            failures.append(
                f"trade:{symbol}:{frames[symbol]['ts'].max()}:{expected_last}"
            )
        if marks[symbol]["ts"].max() != expected_last:
            failures.append(
                f"mark:{symbol}:{marks[symbol]['ts'].max()}:{expected_last}"
            )
    if failures:
        raise RuntimeError("future market data incomplete:\n" + "\n".join(failures))


def route_config(manifest: dict[str, Any], mode: str, sleeve: str) -> dict[str, Any]:
    return manifest["sleeve_configs"][sleeve]["config_by_route"][mode]


def reconstruct(
    manifest: dict[str, Any], end: pd.Timestamp
) -> tuple[
    dict[str, dict[str, list[UnifiedTrade]]],
    dict[str, pd.DataFrame],
    dict[str, pd.DataFrame],
]:
    set_reconstruction_end(end)
    frames = {symbol: load_symbol_frame(symbol, end=end) for symbol in STARTS}
    funding = {symbol: load_funding(symbol, end=end) for symbol in STARTS}
    marks = {symbol: mark_replay.load_mark(symbol) for symbol in STARTS}
    if end == OOS_END:
        assert_complete_market_data(end, frames, marks)
    contexts, captured, featured, prefixes = legacy_full.prepare()
    routed_by_mode: dict[str, dict[str, list[UnifiedTrade]]] = {}
    sleeves = tuple(manifest["selected_sleeves"])
    for mode in MODES:
        options: dict[str, list[dict[str, Any]]] = {}
        for sleeve in sleeves:
            audit = manifest["sleeve_configs"][sleeve]
            config = route_config(manifest, mode, sleeve)
            symbol = audit["symbol"]
            if audit["source"] == "prefit_frontier_asset_first":
                universe = mark_replay.frontier_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "asset_specific_clean_rsi_hf":
                universe = mark_replay.clean_universe(
                    sleeve,
                    audit,
                    config,
                    frames[symbol],
                    marks[symbol],
                    funding[symbol],
                )
            elif audit["source"] == "legacy_asset_specific_1h":
                asset = symbol.removesuffix("USDT")
                baseline_config = next(
                    cfg
                    for name, cfg in captured.items()
                    if name.startswith(asset) and cfg.style == audit["mechanism"]
                )
                universe = mark_replay.legacy_universe(
                    sleeve,
                    audit,
                    config,
                    contexts[asset]["engine"],
                    baseline_config,
                    featured[asset],
                    frames[symbol],
                    marks[symbol],
                    prefixes[asset],
                )
            else:
                raise RuntimeError(f"unknown frozen sleeve source: {audit['source']}")
            options[sleeve] = [
                {"option_id": "frozen", "config": config, "universe": universe}
            ]
        route = manifest["routes"][mode]
        routed_by_mode[mode] = account.route_scenarios(
            tuple(0 for _ in sleeves),
            sleeves,
            options,
            mode=mode,
            frames=frames,
            funding=funding,
            preemption_threshold=float(route.get("threshold", 0.75)),
            preemption_margin=float(route.get("margin", 0.05)),
            preemption_min_hold_hours=int(route.get("min_hold_hours", 1)),
        )
    return routed_by_mode, frames, funding


def historical_parity(manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = manifest or load_manifest()
    routed, _frames, _funding = reconstruct(payload, OOS_START)
    mismatches: list[str] = []
    for mode in MODES:
        scale = float(payload["routes"][mode]["account_scale"])
        actual = account.scale_result(routed[mode], scale)
        expected = payload["frozen_development_metrics"][mode]
        for scenario in account.SCENARIOS:
            for window in ("full", "current_3m", "all_six_active"):
                for field in (
                    "trades",
                    "wins",
                    "win_rate",
                    "total_return",
                    "max_dd",
                    "trades_per_day",
                ):
                    left = actual["scenarios"][scenario][window][field]
                    right = expected["scenarios"][scenario][window][field]
                    if not math.isclose(
                        float(left), float(right), rel_tol=0.0, abs_tol=1e-10
                    ):
                        mismatches.append(f"{mode}.{scenario}.{window}.{field}")
    if mismatches:
        raise RuntimeError("historical reveal parity failed: " + ", ".join(mismatches))
    return {"result": "PASS", "mismatches": mismatches}


def slices(trades: list[UnifiedTrade], scale: float) -> dict[str, Any]:
    return {
        "full": account.metric(trades, account.RESEARCH_START, scale),
        "future_3m_oos": account.metric(trades, OOS_START, scale),
        "1d": account.metric(trades, OOS_END - pd.Timedelta(days=1), scale),
        "7d": account.metric(trades, OOS_END - pd.Timedelta(days=7), scale),
        "1m": account.metric(trades, OOS_END - pd.DateOffset(months=1), scale),
        "3m": account.metric(trades, OOS_END - pd.DateOffset(months=3), scale),
        "6m": account.metric(trades, OOS_END - pd.DateOffset(months=6), scale),
        "1y": account.metric(trades, OOS_END - pd.DateOffset(years=1), scale),
    }


def final_gates(results: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mode in MODES:
        checks: dict[str, bool] = {}
        for scenario in account.SCENARIOS:
            for window in ("full", "future_3m_oos"):
                row = results[mode]["scenarios"][scenario][window]
                prefix = f"{scenario}_{window}"
                checks[f"{prefix}_win_ge_80pct"] = row["win_rate"] >= 0.80
                checks[f"{prefix}_dd_lt_20pct"] = row["max_dd"] > -0.20
                checks[f"{prefix}_return_positive"] = row["total_return"] > 0.0
        future = results[mode]["scenarios"]["base"]["future_3m_oos"]
        checks["future_oos_trades_ge_30"] = future["trades"] >= 30
        checks["future_oos_frequency_1_to_2"] = (
            1.0 <= future["trades_per_day"] <= 2.0
        )
        output[mode] = {"checks": checks, "pass": all(checks.values())}
    return output


def main() -> None:
    args = parse_args()
    manifest = load_manifest()
    verify.main()
    if args.historical_parity:
        print(json.dumps(historical_parity(manifest), indent=2))
        return
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
                    "future_market_data_read": False,
                },
                indent=2,
            )
        )
        return
    if not ready:
        raise RuntimeError(
            "future OOS reveal refused before the complete locked window: " + reason
        )

    routed, _frames, _funding = reconstruct(manifest, OOS_END)
    results: dict[str, Any] = {}
    trade_rows: list[dict[str, Any]] = []
    for mode in MODES:
        scale = float(manifest["routes"][mode]["account_scale"])
        results[mode] = {
            "route": manifest["routes"][mode],
            "scenarios": {
                scenario: slices(trades, scale)
                for scenario, trades in routed[mode].items()
            },
        }
        for trade in routed[mode]["base"]:
            trade_rows.append({"mode": mode, "scale": scale, **asdict(trade)})
    gates = final_gates(results)
    pd.DataFrame(trade_rows).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "one_shot_v6_mark_joint_future_oos_reveal",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "future_oos": [OOS_START.isoformat(), OOS_END.isoformat()],
        "historical_parity": historical_parity(manifest),
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
