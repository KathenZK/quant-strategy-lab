from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from as6s_engine import REUSED_END, SYMBOLS, load_funding, load_symbol_frame
from audit_binance_as6s_v4_joint_state import (
    clean_rsi_raw_universe,
    frontier_raw_universe,
    legacy_raw_universe,
)
from audit_legacy_asset_specific_1h_sleeves import aggregate_h1


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
V5_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a local-only V5 Rust signal parity fixture."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/as6s_v5_runner_signal_parity.json"),
    )
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
            "volume": float(row.volume),
        }
        for row in frame.itertuples()
    ]


def sample_indices(size: int, count: int) -> list[int]:
    if size <= count:
        return list(range(size))
    if count <= 1:
        return [size - 1]
    return sorted({round(index * (size - 1) / (count - 1)) for index in range(count)})


def main() -> None:
    args = parse_args()
    v5 = json.loads(V5_PATH.read_text(encoding="utf-8"))
    selected = tuple(v5["selected_sleeves"])
    sleeve_audit = v5["sleeve_audit"]
    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
    universe = {
        **legacy_raw_universe(selected, sleeve_audit),
        **frontier_raw_universe(selected, sleeve_audit, frames, funding),
        **clean_rsi_raw_universe(selected, sleeve_audit, frames, funding),
    }
    checks: list[dict[str, object]] = []
    for sleeve in selected:
        rows = universe[sleeve]["base"]
        if not rows:
            raise RuntimeError(f"selected sleeve has no base candidates: {sleeve}")
        for index in sample_indices(len(rows), args.checks_per_sleeve):
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
        }
        for sleeve in selected
        for trade in universe[sleeve]["base"]
    ]
    selected_frame = pd.read_csv(ROOT / v5["trades_csv"])
    selected_frame = selected_frame.loc[
        (selected_frame["mode"] == "nonpreemptive")
        & (selected_frame["scenario"] == "base")
    ]
    expected_selected = [
        {
            "sleeve_id": row.sleeve,
            "symbol": row.symbol,
            "side": int(row.side),
            "entry_ts": pd.Timestamp(row.entry_ts).isoformat(),
            "exit_ts": pd.Timestamp(row.exit_ts).isoformat(),
        }
        for row in selected_frame.itertuples()
    ]

    payload = {
        "source": "AS6S-ASSET-FIRST-V5-JOINT-STATE-2026-07-14",
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
                "funding": [
                    {"ts": row.ts.isoformat(), "rate": float(row.funding_rate)}
                    for row in funding[symbol].itertuples()
                ],
            }
            for symbol in SYMBOLS
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "checks": len(checks),
                "sleeves": len(selected),
                "bytes": args.output.stat().st_size,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
