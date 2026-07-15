from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from as6s_engine import BASE_SLIPPAGE, REUSED_END, SYMBOLS, funding_arrays, load_funding, load_symbol_frame
from as6s_live_safe_router import nonpreemptive, preemptive
import research_binance_as6s_asset_first_v3 as v3


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
V3_PATH = FAMILY_DIR / "artifacts/binance_as6s_asset_first_v3_candidate_2026-07-14.json"
TIEBREAK_AUDIT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_v3_future_tiebreak_audit_2026-07-14.json"
)
OUTPUT_PATH = (
    FAMILY_DIR / "artifacts/binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json"
)
TRADES_OUTPUT_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v4_live_safe_candidate_trades_2026-07-14.csv"
)


def diagnostic_gates(comparisons: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for mode, comparison in comparisons.items():
        base = comparison["scenarios"]["base"]
        stress = comparison["scenarios"]["stress_8bps"]
        delayed = comparison["scenarios"]["k_plus_2"]
        checks = {
            "full_win_rate_ge_80pct": base["full"]["win_rate"] >= 0.80,
            "current_3m_win_rate_ge_80pct": base["3m"]["win_rate"] >= 0.80,
            "full_max_dd_lt_20pct": base["full"]["max_dd"] > -0.20,
            "current_3m_max_dd_lt_20pct": base["3m"]["max_dd"] > -0.20,
            "stress_full_positive_dd_lt_20pct": (
                stress["full"]["total_return"] > 0.0
                and stress["full"]["max_dd"] > -0.20
            ),
            "k_plus_2_full_positive_dd_lt_20pct": (
                delayed["full"]["total_return"] > 0.0
                and delayed["full"]["max_dd"] > -0.20
            ),
            "frequency_target_0_75_to_2_25_per_day": (
                0.75 <= base["all_six_active"]["trades_per_day"] <= 2.25
            ),
        }
        output[mode] = {
            "checks": checks,
            "current_diagnostic_pass": all(checks.values()),
            "final_future_oos_pass": None,
            "final_future_oos_reason": (
                "future [2026-07-14T09:00Z, 2026-10-14T09:00Z) data unavailable"
            ),
        }
    return output


def main() -> None:
    old = json.loads(V3_PATH.read_text(encoding="utf-8"))
    tiebreak_audit = json.loads(TIEBREAK_AUDIT_PATH.read_text(encoding="utf-8"))
    if tiebreak_audit["conclusion"]["historical_ledger_changed"]:
        raise RuntimeError("V4 requires a fresh selection search because V3 ledger changed")

    frames = {symbol: load_symbol_frame(symbol, end=REUSED_END) for symbol in SYMBOLS}
    funding_frames = {symbol: load_funding(symbol, end=REUSED_END) for symbol in SYMBOLS}
    legacy, legacy_audit = v3.legacy_universe()
    frontier, frontier_audit = v3.frontier_universe(frames, funding_frames)
    clean, clean_audit = v3.clean_rsi_universe(frames, funding_frames)
    raw_universe = {**legacy, **frontier, **clean}
    sleeve_audit = {**legacy_audit, **frontier_audit, **clean_audit}
    universe = v3.normalize_strengths(raw_universe, sleeve_audit)

    selected = tuple(old["selected_sleeves"])
    if any(sleeve not in universe for sleeve in selected):
        raise RuntimeError("V4 selected sleeve is missing from reconstructed universe")

    funding = {symbol: funding_arrays(frame) for symbol, frame in funding_frames.items()}
    comparisons: dict[str, Any] = {}
    output_trades: list[dict[str, Any]] = []
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        frozen_params = old["comparisons"][mode]["frozen_params"]
        comparisons[mode] = {"scenarios": {}, "frozen_params": frozen_params}
        for scenario in v3.SCENARIOS:
            items = [trade for sleeve in selected for trade in universe[sleeve][scenario]]
            if mode == "nonpreemptive":
                trades = nonpreemptive(items, start=v3.RESEARCH_START, end=REUSED_END)
            else:
                trades = preemptive(
                    items,
                    start=v3.RESEARCH_START,
                    end=REUSED_END,
                    threshold=frozen_params["threshold"],
                    margin=frozen_params["margin"],
                    min_hold_hours=frozen_params["min_hold_hours"],
                    bars=frames,
                    funding=funding,
                    slippage=0.0008 if scenario == "stress_8bps" else BASE_SLIPPAGE,
                )
            comparisons[mode]["scenarios"][scenario] = v3.all_slices(
                trades, frozen_params["account_scale"]
            )
            old_full = old["comparisons"][mode]["scenarios"][scenario]["full"]
            new_full = comparisons[mode]["scenarios"][scenario]["full"]
            if old_full["trades"] != new_full["trades"] or abs(
                old_full["total_return"] - new_full["total_return"]
            ) > 1e-10:
                raise RuntimeError(f"{mode} {scenario} changed after safe tie-break")
            if scenario == "base":
                output_trades.extend(
                    {
                        "mode": mode,
                        "scenario": scenario,
                        "account_scale": frozen_params["account_scale"],
                        **asdict(trade),
                    }
                    for trade in trades
                )

    import pandas as pd

    pd.DataFrame(output_trades).to_csv(TRADES_OUTPUT_PATH, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": old["family"],
        "stage": "asset_first_v4_live_safe_observation_not_registered_not_live_ready",
        "derivation": {
            "source_observation": "V3 asset-first candidate",
            "selection_and_parameters_changed": False,
            "execution_rule_changed": True,
            "change": (
                "removed exit_ts from every entry-time ordering and tie-break; use "
                "strength desc, sleeve_id asc, symbol asc, side desc"
            ),
            "historical_trade_ledger_changed": False,
            "post_selection_data_read_for_derivation": False,
            "audit_artifact": str(TIEBREAK_AUDIT_PATH.relative_to(ROOT)),
        },
        "future_final_oos": old["future_final_oos"],
        "candidate_sleeves": list(universe),
        "selected_sleeves": list(selected),
        "sleeve_audit": sleeve_audit,
        "arbitration": {
            "entry_time_fields_only": True,
            "candidate_order": [
                "strength_desc",
                "sleeve_id_asc",
                "symbol_asc",
                "side_desc",
            ],
            "forbidden_fields": [
                "exit_ts",
                "exit_reason",
                "net_return_1x",
                "mae_return_1x",
            ],
        },
        "comparisons": comparisons,
        "diagnostic_gates": diagnostic_gates(comparisons),
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
                "selected_sleeves": len(selected),
                "diagnostic_gates": payload["diagnostic_gates"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
