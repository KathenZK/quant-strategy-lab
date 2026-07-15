from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import REUSED_END, STARTS
from audit_legacy_asset_specific_1h_sleeves import aggregate_h1
import combine_binance_as6s_v6_mark_microtuned_account as mark_micro
import replay_binance_as6s_v6_mark_price_account as mark_replay


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
FINAL = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json"
FINAL_TRADES = FAMILY_DIR / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv"
MODES = ("nonpreemptive", "strong_breakout_preemptive")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export frozen V6 NP and strong-breakout runner parity fixtures."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp"))
    parser.add_argument("--checks-per-sleeve", type=int, default=3)
    return parser.parse_args()


def candle_rows(frame: pd.DataFrame) -> list[dict[str, object]]:
    return [
        {
            "ts": row.ts.isoformat(),
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(getattr(row, "volume", 0.0)),
        }
        for row in frame.itertuples()
    ]


def sample_indices(size: int, count: int) -> list[int]:
    if size <= count:
        return list(range(size))
    if count <= 1:
        return [size - 1]
    return sorted({round(index * (size - 1) / (count - 1)) for index in range(count)})


def route_universe(
    mode: str,
    final: dict[str, Any],
    manifest: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, list[Any]]]:
    selection = final["results"][mode]["selection"]
    marks = {symbol: mark_replay.load_mark(symbol) for symbol in STARTS}
    output: dict[str, dict[str, list[Any]]] = {}
    for sleeve in sleeves:
        selected = selection[sleeve]
        if selected["option"] == "dropped":
            raise RuntimeError(f"V6 freeze unexpectedly dropped {sleeve}")
        audit = manifest["sleeve_configs"][sleeve]
        if audit["source"] == "asset_specific_clean_rsi_hf":
            symbol = audit["symbol"]
            output[sleeve] = mark_replay.clean_universe(
                sleeve,
                audit,
                selected["config"],
                frames[symbol],
                marks[symbol],
                funding[symbol],
            )
            continue
        option = next(
            row for row in options[sleeve] if row["option_id"] == selected["option"]
        )
        if json.dumps(option["config"], sort_keys=True, default=str) != json.dumps(
            selected["config"], sort_keys=True, default=str
        ):
            raise RuntimeError(f"selected option/config mismatch for {mode} {sleeve}")
        output[sleeve] = option["universe"]
    return output


def fixture_payload(
    mode: str,
    final: dict[str, Any],
    manifest: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    funding: dict[str, pd.DataFrame],
    sleeves: tuple[str, ...],
    options: dict[str, list[dict[str, Any]]],
    checks_per_sleeve: int,
    selected_frame: pd.DataFrame,
) -> dict[str, Any]:
    universe = route_universe(mode, final, manifest, frames, funding, sleeves, options)
    checks: list[dict[str, object]] = []
    for sleeve in sleeves:
        rows = universe[sleeve]["base"]
        if not rows:
            raise RuntimeError(f"selected sleeve has no base candidates: {mode} {sleeve}")
        for index in sample_indices(len(rows), checks_per_sleeve):
            trade = rows[index]
            checks.append(
                {
                    "sleeve_id": sleeve,
                    "decision_open_ts": trade.entry_ts.isoformat(),
                    "side": int(trade.side),
                    "entry_price": float(trade.entry_price),
                    "exit_ts": trade.exit_ts.isoformat(),
                    "exit_reason": trade.exit_reason,
                    "raw_strength": float(trade.raw_strength),
                    "strength": float(trade.strength),
                }
            )
    all_candidates = [
        {
            "sleeve_id": trade.sleeve,
            "symbol": trade.symbol,
            "side": int(trade.side),
            "entry_ts": trade.entry_ts.isoformat(),
            "exit_ts": trade.exit_ts.isoformat(),
            "strength": float(trade.strength),
            "cooldown_hours": int(trade.cooldown_hours),
            "exit_reason": trade.exit_reason,
        }
        for sleeve in sleeves
        for trade in universe[sleeve]["base"]
    ]
    expected = selected_frame.loc[selected_frame["mode"] == mode]
    expected_selected = [
        {
            "sleeve_id": row.sleeve,
            "symbol": row.symbol,
            "side": int(row.side),
            "entry_ts": pd.Timestamp(row.entry_ts).isoformat(),
            "exit_ts": pd.Timestamp(row.exit_ts).isoformat(),
            "exit_reason": row.exit_reason,
        }
        for row in expected.itertuples()
    ]
    marks = {symbol: mark_replay.load_mark(symbol) for symbol in STARTS}
    return {
        "source": "BIN-15M-AS6S-V6-MARK-JOINT-FREEZE-2026-07-15",
        "route": mode,
        "end_exclusive": REUSED_END.isoformat(),
        "checks": checks,
        "all_candidates": all_candidates,
        "expected_selected": expected_selected,
        "assets": {
            symbol: {
                "m15": candle_rows(
                    frames[symbol][["ts", "open", "high", "low", "close", "volume"]]
                ),
                "h1": candle_rows(aggregate_h1(symbol)),
                "mark_m15": candle_rows(
                    marks[symbol][["ts", "open", "high", "low", "close"]]
                ),
                "funding": [
                    {"ts": row.ts.isoformat(), "rate": float(row.funding_rate)}
                    for row in funding[symbol].itertuples()
                ],
            }
            for symbol in STARTS
        },
    }


def main() -> None:
    args = parse_args()
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    _source, manifest, frames, funding, sleeves, options = (
        mark_micro.prepare_mark_account_inputs()
    )
    selected_frame = pd.read_csv(FINAL_TRADES)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, Any] = {}
    for mode in MODES:
        payload = fixture_payload(
            mode,
            final,
            manifest,
            frames,
            funding,
            sleeves,
            options,
            args.checks_per_sleeve,
            selected_frame,
        )
        suffix = "np" if mode == "nonpreemptive" else "preemptive"
        path = args.output_dir / f"as6s_v6_mark_{suffix}_runner_parity.json"
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        path.write_bytes(encoded)
        outputs[mode] = {
            "path": str(path),
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
            "checks": len(payload["checks"]),
            "candidates": len(payload["all_candidates"]),
            "selected": len(payload["expected_selected"]),
        }
    print(json.dumps(outputs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
