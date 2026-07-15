from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import research_binance_as6s_asset_first_v3 as v3
from as6s_engine import funding_arrays, funding_return, load_funding, load_symbol_frame
from combine_hybrid_asset_specific_account import UnifiedTrade, nonpreemptive


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
SOURCE = FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
OUTPUT = FAMILY_DIR / "artifacts/binance_as6s_v3_funding_boundary_2026-07-14.json"


def alternate_funding_return(
    side: int,
    entry_ts: pd.Timestamp,
    exit_ts: pd.Timestamp,
    times: np.ndarray,
    prefix: np.ndarray,
) -> float:
    # Alternate event ordering: an entry stamped exactly at funding time occurs
    # after that settlement, while an exit stamped there occurs after settlement.
    left = int(np.searchsorted(times, int(entry_ts.value), side="right"))
    right = int(np.searchsorted(times, int(exit_ts.value), side="right"))
    return float(-side * (prefix[right] - prefix[left]))


def adjust_trade(
    trade: UnifiedTrade,
    funding: dict[str, tuple[np.ndarray, np.ndarray]],
    mode: str,
) -> UnifiedTrade:
    times, prefix = funding[trade.symbol]
    standard = funding_return(
        trade.side, trade.entry_ts, trade.exit_ts, times, prefix
    )
    alternate = alternate_funding_return(
        trade.side, trade.entry_ts, trade.exit_ts, times, prefix
    )
    if mode == "alternate":
        chosen = alternate
    elif mode == "per_trade_worst":
        chosen = min(standard, alternate)
    else:
        chosen = standard
    adjusted = float(trade.net_return_1x + chosen - standard)
    return replace(
        trade,
        net_return_1x=adjusted,
        mae_return_1x=min(trade.mae_return_1x, adjusted),
    )


def metric(
    trades: list[UnifiedTrade], start: pd.Timestamp, end: pd.Timestamp, scale: float
) -> dict[str, Any]:
    return v3.metric_with_frequency(trades, start, end, scale)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    selected = tuple(source["selected_sleeves"])
    scale = float(
        source["comparisons"]["nonpreemptive"]["frozen_params"]["account_scale"]
    )
    frames = {
        symbol: load_symbol_frame(symbol, end=v3.REUSED_END)
        for symbol in v3.SYMBOLS
    }
    funding_frames = {
        symbol: load_funding(symbol, end=v3.REUSED_END) for symbol in v3.SYMBOLS
    }
    old, old_audit = v3.legacy_universe()
    frontier, frontier_audit = v3.frontier_universe(frames, funding_frames)
    clean, clean_audit = v3.clean_rsi_universe(frames, funding_frames)
    raw_universe = {**old, **frontier, **clean}
    audit = {**old_audit, **frontier_audit, **clean_audit}
    universe = v3.normalize_strengths(raw_universe, audit)
    funding = {
        symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()
    }

    results: dict[str, Any] = {}
    for scenario in v3.SCENARIOS:
        results[scenario] = {}
        raw_items = [
            trade for sleeve in selected for trade in universe[sleeve][scenario]
        ]
        for boundary_mode in ("standard", "alternate", "per_trade_worst"):
            items = [
                adjust_trade(trade, funding, boundary_mode) for trade in raw_items
            ]
            trades = nonpreemptive(
                items, start=v3.RESEARCH_START, end=v3.REUSED_END
            )
            results[scenario][boundary_mode] = {
                "full": metric(
                    trades, v3.RESEARCH_START, v3.REUSED_END, scale
                ),
                "all_six_active": metric(
                    trades, v3.ALL_SIX_ACTIVE_START, v3.REUSED_END, scale
                ),
                "current_3m": metric(
                    trades, v3.CURRENT_3M_START, v3.REUSED_END, scale
                ),
            }

    checks = {
        f"{scenario}_{boundary_mode}_{window}": (
            metric_["total_return"] > 0.0
            and metric_["win_rate"] >= 0.80
            and metric_["max_dd"] > -0.20
        )
        for scenario, boundary_rows in results.items()
        for boundary_mode, windows in boundary_rows.items()
        for window, metric_ in windows.items()
        if window in {"full", "current_3m"}
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "stage": "funding_boundary_robustness_audit",
        "source": str(SOURCE.relative_to(ROOT)),
        "route": "nonpreemptive",
        "account_scale": scale,
        "standard_convention": "entry timestamp inclusive, exit timestamp exclusive",
        "alternate_convention": "entry timestamp exclusive, exit timestamp inclusive",
        "worst_convention": "minimum funding return per trade across both conventions",
        "results": results,
        "checks": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise RuntimeError(f"funding boundary audit failed: {failed}")
    print(json.dumps({"output": str(OUTPUT), "result": "PASS"}, indent=2))


if __name__ == "__main__":
    main()
