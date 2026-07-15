from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SCRIPTS = FAMILY / "scripts"
sys.path.insert(0, str(SCRIPTS))

from as6s_engine import BASE_SLIPPAGE, REUSED_END, SYMBOLS, funding_arrays, load_funding, load_symbol_frame  # noqa: E402
from as6s_live_safe_router import nonpreemptive, preemptive  # noqa: E402
import research_binance_as6s_asset_first_v3 as v3  # noqa: E402
import reveal_binance_as6s_v5_joint_state_future_oos as reveal  # noqa: E402


CANDIDATE = (
    FAMILY / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
)
TRADES = (
    FAMILY
    / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_trades_2026-07-14.csv"
)


def signature(rows: list[object] | pd.DataFrame) -> list[tuple[object, ...]]:
    iterator = rows.itertuples() if isinstance(rows, pd.DataFrame) else iter(rows)
    return [
        (
            row.sleeve,
            pd.Timestamp(row.entry_ts).isoformat(),
            pd.Timestamp(row.exit_ts).isoformat(),
            int(row.side),
            row.exit_reason,
        )
        for row in iterator
    ]


def test_v5_one_shot_reveal_reconstructs_frozen_historical_ledger() -> None:
    candidate = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    manifest = {
        "selected_sleeves": candidate["selected_sleeves"],
        "sleeve_configs": {
            sleeve: candidate["sleeve_audit"][sleeve]
            for sleeve in candidate["selected_sleeves"]
        },
        "routes": {
            mode: candidate["comparisons"][mode]["frozen_params"]
            for mode in ("nonpreemptive", "strong_breakout_preemptive")
        },
    }
    reveal.OOS_END = REUSED_END
    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding_frames = {
        symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS
    }
    universe = reveal.build_universe(manifest, frames, funding_frames)
    funding = {
        symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()
    }
    frozen = pd.read_csv(TRADES)
    frozen["entry_ts"] = pd.to_datetime(frozen["entry_ts"], utc=True)
    frozen["exit_ts"] = pd.to_datetime(frozen["exit_ts"], utc=True)

    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        params = manifest["routes"][mode]
        items = [
            trade
            for sleeve in manifest["selected_sleeves"]
            for trade in universe[sleeve]["base"]
        ]
        if mode == "nonpreemptive":
            actual = nonpreemptive(items, start=v3.RESEARCH_START, end=REUSED_END)
        else:
            actual = preemptive(
                items,
                start=v3.RESEARCH_START,
                end=REUSED_END,
                threshold=params["threshold"],
                margin=params["margin"],
                min_hold_hours=params["min_hold_hours"],
                bars=frames,
                funding=funding,
                slippage=BASE_SLIPPAGE,
            )
        expected = frozen.loc[frozen["mode"] == mode]
        assert signature(actual) == signature(expected)
