from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
V4_CONTRACT = ARTIFACTS / "binance_as6s_v4_live_safe_execution_contract_2026-07-14.json"
V5_CANDIDATE = ARTIFACTS / "binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
V5_FREEZE = ARTIFACTS / "binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
JOINT_AUDIT = ARTIFACTS / "binance_as6s_v4_joint_state_audit_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v5_joint_state_execution_contract_2026-07-14.json"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract = load(V4_CONTRACT)
    candidate = load(V5_CANDIDATE)
    freeze = load(V5_FREEZE)
    audit = load(JOINT_AUDIT)
    if not audit["conclusion"]["historical_ledger_changed"]:
        raise RuntimeError("V5 contract requires the material joint-state correction")
    if candidate["selected_sleeves"] != freeze["selected_sleeves"]:
        raise RuntimeError("V5 candidate and freeze sleeve boundaries differ")

    contract["contract_version"] = 3
    contract["observation_id"] = "AS6S-ASSET-FIRST-V5-JOINT-STATE-2026-07-14"
    contract["status"] = freeze["status"]
    contract["promotion_boundary"] = {
        "registered": False,
        "promoted": False,
        "live_ready": False,
        "future_oos": freeze["future_oos"],
    }
    contract["source_integrity"] = {
        "candidate_path": str(V5_CANDIDATE.relative_to(ROOT)),
        "candidate_sha256": sha256(V5_CANDIDATE),
        "freeze_path": str(V5_FREEZE.relative_to(ROOT)),
        "freeze_sha256": sha256(V5_FREEZE),
        "joint_state_audit_path": str(JOINT_AUDIT.relative_to(ROOT)),
        "joint_state_audit_sha256": sha256(JOINT_AUDIT),
    }
    contract["state_contract"] = freeze["state_contract"]
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
    contract["runner_compatibility"]["required_new_strategy_module"] = (
        "asset_specific_six_selector_v5_joint_state"
    )
    contract["runner_compatibility"]["live_readiness_blockers"] = [
        "V5 future OOS is unavailable and the observation is not registered",
        "quant-runner dry-run replay parity is not yet proven",
        "mark-price protection and strong-breakout close-then-open replacement require dry-run evidence",
    ]
    contract["parity_gates_before_any_promotion"] = [
        "candidate identity, route params, arbitration, and joint state contract match this contract",
        "blocked candidates are discarded without mutating sleeve position or cooldown state",
        "only accepted entries and their real exits may mutate account/sleeve state",
        "no entry decision code path can read a forbidden post-entry field",
        "offline replay and quant-runner emit identical accepted entries, exits, side, sleeve, and route state transitions",
        "dry-run proves venue-flat confirmation before any preemptive replacement entry",
    ]

    OUTPUT.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
