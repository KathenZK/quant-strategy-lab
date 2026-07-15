from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
V3_CONTRACT = ARTIFACTS / "binance_as6s_v3_execution_contract_2026-07-14.json"
V4_CANDIDATE = ARTIFACTS / "binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json"
V4_FREEZE = ARTIFACTS / "binance_as6s_v4_live_safe_future_oos_freeze_2026-07-14.json"
TIEBREAK_AUDIT = ARTIFACTS / "binance_as6s_v3_future_tiebreak_audit_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v4_live_safe_execution_contract_2026-07-14.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = load(V3_CONTRACT)
    candidate = load(V4_CANDIDATE)
    freeze = load(V4_FREEZE)
    audit = load(TIEBREAK_AUDIT)
    if audit["conclusion"]["historical_ledger_changed"]:
        raise RuntimeError("V4 contract cannot inherit V3 execution structure")
    if candidate["selected_sleeves"] != freeze["selected_sleeves"]:
        raise RuntimeError("V4 candidate and freeze sleeve boundaries differ")

    contract["contract_version"] = 2
    contract["observation_id"] = "AS6S-ASSET-FIRST-V4-LIVE-SAFE-2026-07-14"
    contract["status"] = freeze["status"]
    contract["promotion_boundary"] = {
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "future_oos": freeze["future_oos"],
    }
    contract["source_integrity"] = {
        "candidate_path": str(V4_CANDIDATE.relative_to(ROOT)),
        "candidate_sha256": sha256(V4_CANDIDATE),
        "freeze_path": str(V4_FREEZE.relative_to(ROOT)),
        "freeze_sha256": sha256(V4_FREEZE),
        "future_tiebreak_audit_path": str(TIEBREAK_AUDIT.relative_to(ROOT)),
        "future_tiebreak_audit_sha256": sha256(TIEBREAK_AUDIT),
    }
    contract["strength_contract"] = {
        "formula": (
            "0.75 * frozen_normalized_sleeve_quality + "
            "0.25 * clip(signal_raw_strength, 0, 1)"
        ),
        "candidate_order": [
            "strength_desc",
            "sleeve_id_asc",
            "symbol_asc",
            "side_desc",
        ],
        "forbidden_entry_fields": [
            "exit_ts",
            "exit_reason",
            "net_return_1x",
            "mae_return_1x",
        ],
        "recompute_while_held": False,
        "current_position_strength": "frozen at accepted entry candidate strength",
    }
    contract["live_safe_arbitration"] = freeze["arbitration"]
    contract["routes"] = {
        "nonpreemptive": {
            **freeze["routes"]["nonpreemptive"],
            "max_effective_allocation": 1.2,
            "position_policy": "never preempt; other signals are discarded",
        },
        "strong_breakout_preemptive": {
            **freeze["routes"]["strong_breakout_preemptive"],
            "max_effective_allocation": 0.99,
            "challenger_policy": (
                "different symbol, breakout family, strength >= threshold, "
                "strength >= current + margin, minimum hold satisfied"
            ),
            "replacement_timing": (
                "close current, confirm venue flat, then open challenger; "
                "never overlap venue positions"
            ),
        },
    }
    contract["diagnostic_metrics"] = {
        mode: candidate["comparisons"][mode]["scenarios"]
        for mode in ("nonpreemptive", "strong_breakout_preemptive")
    }
    blockers = contract["runner_compatibility"]["live_readiness_blockers"]
    contract["runner_compatibility"]["live_readiness_blockers"] = [
        "V4 future OOS is unavailable and the observation is not registered",
        *[item for item in blockers if not item.startswith("V3 future OOS")],
    ]
    contract["runner_compatibility"]["required_new_strategy_module"] = (
        "asset_specific_six_selector_v4_live_safe"
    )
    contract["parity_gates_before_any_promotion"] = [
        "candidate identity, route params, and live-safe arbitration match this contract",
        "no entry decision code path can read a forbidden post-entry field",
        *contract["parity_gates_before_any_promotion"][1:],
    ]

    OUTPUT.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
