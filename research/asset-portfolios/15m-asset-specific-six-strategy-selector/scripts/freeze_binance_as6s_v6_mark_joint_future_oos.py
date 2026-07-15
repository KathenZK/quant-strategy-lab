from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from as6s_engine import REUSED_END
import combine_binance_as6s_v6_mark_robust_account as robust_account
import freeze_binance_as6s_v5_joint_state_future_oos as v5_freeze
import replay_binance_as6s_v6_mark_price_account as mark_replay


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
SOURCE = ARTIFACTS / "binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json"
AUDIT = ARTIFACTS / "binance_as6s_v6_mark_clean_rsi_joint_candidate_audit_2026-07-15.json"
V5_MANIFEST = ARTIFACTS / "binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v6_mark_joint_future_oos_freeze_2026-07-15.json"
FUTURE_END = pd.Timestamp("2026-10-14T09:00:00Z")
MARK_COLUMNS = ["ts", "open", "high", "low", "close"]

V6_FILES = (
    Path(__file__),
    Path(__file__).with_name("verify_binance_as6s_v6_mark_joint_freeze.py"),
    Path(__file__).with_name("reveal_binance_as6s_v6_mark_joint_future_oos.py"),
    Path(__file__).with_name("replay_binance_as6s_v6_mark_price_account.py"),
    Path(__file__).with_name("combine_binance_as6s_v6_microtuned_account.py"),
    Path(__file__).with_name("combine_binance_as6s_v6_mark_microtuned_account.py"),
    Path(__file__).with_name("combine_binance_as6s_v6_mark_robust_account.py"),
    Path(__file__).with_name("research_binance_as6s_v6_mark_clean_rsi_account_surface.py"),
    Path(__file__).with_name("combine_binance_as6s_v6_mark_clean_rsi_joint_refine.py"),
    Path(__file__).with_name("audit_binance_as6s_v6_mark_micro_candidate.py"),
    Path(__file__).with_name("audit_binance_as6s_v6_mark_clean_rsi_joint_candidate.py"),
    Path(__file__).with_name("sync_binance_as6s_mark_price_15m.py"),
    SOURCE,
    ARTIFACTS / "binance_as6s_v6_mark_clean_rsi_joint_refine_trades_2026-07-15.csv",
    AUDIT,
    ARTIFACTS / "binance_as6s_v6_mark_clean_rsi_account_surface_2026-07-15.json",
    ARTIFACTS / "binance_as6s_mark_price_15m_quality_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v5_parameter_inventory_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v5_inert_parameter_equivalence_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v5_frontier_full_ablation_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v5_clean_rsi_full_ablation_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v5_legacy_exact_full_ablation_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v6_frontier_microtune_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v6_clean_rsi_microtune_2026-07-15.json",
    ARTIFACTS / "binance_as6s_v6_legacy_microtune_2026-07-15.json",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-clean-rsi-joint-refine-2026-07-15.md",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-clean-rsi-account-surface-2026-07-15.md",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-price-account-2026-07-15.md",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-engine-bridge-2026-07-15.md",
    FAMILY_DIR / "diagnostics/binance-as6s-v6-mark-price-trigger-audit-2026-07-15.md",
    FAMILY_DIR / "specs/binance-as6s-v6-mark-joint-future-oos-freeze-2026-07-15.md",
    ROOT / "tests/test_as6s_v6_mark_reveal_parity.py",
)


def files_to_freeze() -> tuple[Path, ...]:
    return tuple(sorted(set((*v5_freeze.files_to_freeze(), *V6_FILES))))


def mark_snapshot() -> dict[str, Any]:
    output: dict[str, Any] = {}
    for symbol in sorted(mark_replay.SLUGS):
        frame = mark_replay.load_mark(symbol)
        output[symbol] = {
            "rows": len(frame),
            "first_ts": frame["ts"].iloc[0].isoformat(),
            "last_ts": frame["ts"].iloc[-1].isoformat(),
            "logical_sha256": v5_freeze.v4_freeze.v3_freeze.logical_frame_digest(
                frame, MARK_COLUMNS
            ),
        }
    return output


def selected_sleeve_configs(
    source: dict[str, Any], v5_manifest: dict[str, Any]
) -> dict[str, Any]:
    reference = source["results"]["nonpreemptive"]["selection"]
    other = source["results"]["strong_breakout_preemptive"]["selection"]
    if set(reference) != set(other):
        raise RuntimeError("V6 routes do not share one sleeve set")
    output: dict[str, Any] = {}
    for sleeve, selection in reference.items():
        if selection["option"] == "dropped":
            raise RuntimeError(f"V6 cannot freeze dropped sleeve: {sleeve}")
        base = dict(v5_manifest["sleeve_configs"][sleeve])
        output[sleeve] = {
            **base,
            "config": selection["config"],
            "selected_option_by_route": {
                "nonpreemptive": selection["option"],
                "strong_breakout_preemptive": other[sleeve]["option"],
            },
            "config_by_route": {
                "nonpreemptive": selection["config"],
                "strong_breakout_preemptive": other[sleeve]["config"],
            },
        }
    return output


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    v5_manifest = json.loads(V5_MANIFEST.read_text(encoding="utf-8"))
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        result = source["results"][mode]["result"]
        if not result["hard_pass"] or not robust_account.robust_pass(result):
            raise RuntimeError(f"cannot freeze non-buffered V6 route: {mode}")
        audited = audit["results"][mode]
        if audited["source_parity"]["result"] != "PASS":
            raise RuntimeError(f"V6 audit parity failed: {mode}")
        if audited["dispensable_sleeves"]:
            raise RuntimeError(f"V6 still has dispensable sleeves: {mode}")

    sleeves = tuple(source["results"]["nonpreemptive"]["selection"])
    sleeve_configs = selected_sleeve_configs(source, v5_manifest)
    frozen_files = files_to_freeze()
    missing = [str(path) for path in frozen_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"freeze inputs missing: {missing}")
    routes = {
        "nonpreemptive": {
            "account_scale": source["results"]["nonpreemptive"]["result"]["scale"],
            "max_effective_leverage": source["results"]["nonpreemptive"]["result"][
                "effective_max_leverage"
            ],
            "preemption": False,
        },
        "strong_breakout_preemptive": {
            "account_scale": source["results"]["strong_breakout_preemptive"][
                "result"
            ]["scale"],
            "max_effective_leverage": source["results"][
                "strong_breakout_preemptive"
            ]["result"]["effective_max_leverage"],
            "preemption": True,
            "threshold": 0.75,
            "margin": 0.05,
            "min_hold_hours": 1,
        },
    }
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": "Binance-15M-Asset-Specific-Six-Strategy-Selector",
        "version": "BIN-15M-AS6S-V6",
        "role": "dual-route mark-price joint-state registered observation",
        "status": "registered_not_promoted_not_live_ready",
        "selection_end_exclusive": REUSED_END.isoformat(),
        "future_oos": {
            "start_inclusive": REUSED_END.isoformat(),
            "end_exclusive": FUTURE_END.isoformat(),
            "reveal_policy": (
                "one-shot only after the complete window is available; the check-only "
                "path must not read future-window market data"
            ),
        },
        "execution_contract": {
            "signal_and_entry_source": "Binance USD-M trade OHLC; closed bars only",
            "entry_timing": "signal close plus K+1 open; K+2 is delayed stress",
            "protective_trigger_source": "Binance 15m mark-price OHLC",
            "protective_fill": (
                "gap at same 15m trade open; otherwise mark trigger mapped by the "
                "same-bar trade-open/mark-open basis and clipped to trade high/low; "
                "adverse slippage then applied"
            ),
            "same_bar_collision": "stop-first",
            "trailing_update": "closed strategy bar only; active from next bar",
            "fees_per_fill": 0.001,
            "base_slippage_per_fill": 0.0004,
            "stress_slippage_per_fill": 0.0008,
            "funding": "historical Binance funding accrued over actual holding interval",
        },
        "arbitration": {
            "account_position_owner": "global joint account only",
            "blocked_signal_policy": "discard; never queue and never mutate sleeve state",
            "entry_time_fields_only": True,
            "forbidden_fields": ["exit_ts", "exit_reason", "net_return_1x", "mae_return_1x"],
            "same_timestamp_tie_break": (
                "entry timestamp, descending entry-time strength, sleeve id"
            ),
        },
        "selected_sleeves": sleeves,
        "sleeve_configs": sleeve_configs,
        "routes": routes,
        "frozen_development_metrics": {
            mode: source["results"][mode]["result"]
            for mode in ("nonpreemptive", "strong_breakout_preemptive")
        },
        "final_account_audit": {
            mode: {
                "dispensable_sleeves": audit["results"][mode][
                    "dispensable_sleeves"
                ],
                "scale_summary": audit["results"][mode]["scale_summary"],
                "router_summary": audit["results"][mode]["router_summary"],
                "option_substitution_summary": audit["results"][mode][
                    "option_substitution_summary"
                ],
            }
            for mode in ("nonpreemptive", "strong_breakout_preemptive")
        },
        "frozen_files": {
            str(path.relative_to(ROOT)): v5_freeze.v4_freeze.v3_freeze.sha256_file(path)
            for path in frozen_files
        },
        "trade_and_funding_snapshot_through_selection_end": (
            v5_freeze.v4_freeze.v3_freeze.data_snapshot()
        ),
        "mark_price_snapshot_through_selection_end": mark_snapshot(),
        "prohibited_before_reveal": (
            "parameter tuning, sleeve replacement, threshold/exposure/scale/route/state/"
            "execution changes, history rewrites, and partial future-window inspection"
        ),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT.relative_to(ROOT)),
                "version": payload["version"],
                "selected_sleeves": len(sleeves),
                "files_frozen": len(frozen_files),
                "symbols_snapshotted": len(
                    payload["trade_and_funding_snapshot_through_selection_end"]
                ),
                "mark_symbols_snapshotted": len(
                    payload["mark_price_snapshot_through_selection_end"]
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
