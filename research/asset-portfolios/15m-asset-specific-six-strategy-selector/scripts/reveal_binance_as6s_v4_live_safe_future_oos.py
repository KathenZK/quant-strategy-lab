from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import SYMBOLS, funding_arrays, load_funding, load_symbol_frame
from as6s_live_safe_router import nonpreemptive, preemptive
import reveal_binance_as6s_v3_future_oos as components
import verify_binance_as6s_v4_live_safe_freeze as verify


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
MANIFEST = (
    FAMILY_DIR / "artifacts/binance_as6s_v4_live_safe_future_oos_freeze_2026-07-14.json"
)
OUTPUT = (
    FAMILY_DIR / "artifacts/binance_as6s_v4_live_safe_future_oos_reveal_2026-10-14.json"
)
TRADES_OUTPUT = (
    FAMILY_DIR
    / "artifacts/binance_as6s_v4_live_safe_future_oos_reveal_trades_2026-10-14.csv"
)
OOS_START = pd.Timestamp("2026-07-14T09:00:00Z")
OOS_END = pd.Timestamp("2026-10-14T09:00:00Z")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="One-shot reveal for frozen AS6S V4 live-safe future OOS."
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
    if not payload["arbitration"]["entry_time_fields_only"]:
        raise RuntimeError("V4 manifest does not enforce live-safe arbitration")
    if "exit_ts" not in payload["arbitration"]["forbidden_fields"]:
        raise RuntimeError("V4 manifest does not forbid exit_ts arbitration")
    return payload


def future_ready() -> tuple[bool, str]:
    now = pd.Timestamp.now(tz="UTC")
    if now < OOS_END:
        return False, f"wall clock {now.isoformat()} is before {OOS_END.isoformat()}"
    return True, "wall-clock gate passed; data completeness is checked during load"


def route_results(
    manifest: dict[str, Any],
    universe: dict[str, dict[str, list[components.UnifiedTrade]]],
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
                    "arbitration": manifest["arbitration"],
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
    universe = components.build_universe(manifest, frames, funding)
    results, trades = route_results(manifest, universe, frames, funding)
    gates = components.final_gates(results)
    pd.DataFrame(trades).to_csv(TRADES_OUTPUT, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "one_shot_v4_live_safe_future_oos_reveal",
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "future_oos": [OOS_START.isoformat(), OOS_END.isoformat()],
        "arbitration": manifest["arbitration"],
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
