from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

import freeze_binance_as6s_v4_live_safe_future_oos as v4_freeze


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
SOURCE = ARTIFACTS / "binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
AUDIT = ARTIFACTS / "binance_as6s_v4_joint_state_audit_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v5_joint_state_future_oos_freeze_2026-07-14.json"
FUTURE_END = pd.Timestamp("2026-10-14T09:00:00Z")

V5_FILES = (
    Path(__file__),
    SOURCE,
    ARTIFACTS / "binance_as6s_asset_first_v5_joint_state_candidate_trades_2026-07-14.csv",
    AUDIT,
    ARTIFACTS / "binance_as6s_v4_joint_state_audit_trades_2026-07-14.csv",
    Path(__file__).with_name("audit_binance_as6s_v4_joint_state.py"),
    Path(__file__).with_name("research_binance_as6s_asset_first_v5_joint_state.py"),
    Path(__file__).with_name("build_binance_as6s_v5_joint_state_execution_contract.py"),
    Path(__file__).with_name("reveal_binance_as6s_v5_joint_state_future_oos.py"),
    Path(__file__).with_name("verify_binance_as6s_v5_joint_state_freeze.py"),
    FAMILY_DIR / "diagnostics/binance-as6s-v5-joint-state-observation-2026-07-14.md",
    ROOT / "tests/test_as6s_joint_state_router.py",
    ROOT / "tests/test_as6s_v5_reveal_parity.py",
)


def files_to_freeze() -> tuple[Path, ...]:
    return tuple(sorted(set((*v4_freeze.files_to_freeze(), *V5_FILES))))


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if not audit["conclusion"]["historical_ledger_changed"]:
        raise RuntimeError("V5 freeze requires the material joint-state audit")
    if source["derivation"]["post_selection_data_read_for_derivation"]:
        raise RuntimeError("V5 derivation unexpectedly read post-selection data")
    if source["state_contract"]["account_position_owner"] != "global joint account only":
        raise RuntimeError("V5 state ownership is not live-executable")
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        gate = source["diagnostic_gates"][mode]
        if not gate["current_diagnostic_pass"]:
            raise RuntimeError(f"cannot freeze failing V5 route: {mode}")
        if gate["final_future_oos_pass"] is not None:
            raise RuntimeError(f"future OOS already populated unexpectedly: {mode}")

    frozen_files = files_to_freeze()
    missing = [str(path) for path in frozen_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"freeze inputs missing: {missing}")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": source["family"],
        "candidate": "BIN-15M-AS6S-V5-joint-state-observation",
        "status": "frozen_observation_not_registered_not_promoted_not_live_ready",
        "selection_end_exclusive": v4_freeze.v3_freeze.v3.REUSED_END.isoformat(),
        "derivation": source["derivation"],
        "future_oos": {
            "start_inclusive": v4_freeze.v3_freeze.v3.REUSED_END.isoformat(),
            "end_exclusive": FUTURE_END.isoformat(),
            "reveal_policy": (
                "one-shot only after the complete window is available; no parameter, "
                "sleeve, route, exposure, score, arbitration, state, or execution "
                "change before reveal"
            ),
        },
        "arbitration": source["arbitration"],
        "state_contract": source["state_contract"],
        "selected_sleeves": source["selected_sleeves"],
        "routes": {
            mode: source["comparisons"][mode]["frozen_params"]
            for mode in ("nonpreemptive", "strong_breakout_preemptive")
        },
        "sleeve_configs": {
            sleeve: source["sleeve_audit"][sleeve]
            for sleeve in source["selected_sleeves"]
        },
        "current_diagnostic_gates": source["diagnostic_gates"],
        "frozen_files": {
            str(path.relative_to(ROOT)): v4_freeze.v3_freeze.sha256_file(path)
            for path in frozen_files
        },
        "data_snapshot_through_selection_end": v4_freeze.v3_freeze.data_snapshot(),
        "prohibited_before_reveal": (
            "parameter tuning, sleeve replacement, threshold changes, exposure changes, "
            "account-scale changes, route changes, arbitration changes, state-contract "
            "changes, data-history rewrites, and partial future-window inspection"
        ),
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "selected_sleeves": len(payload["selected_sleeves"]),
                "files_frozen": len(payload["frozen_files"]),
                "symbols_snapshotted": len(payload["data_snapshot_through_selection_end"]),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
