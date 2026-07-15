from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

import freeze_binance_as6s_v3_future_oos as v3_freeze


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
ARTIFACTS = FAMILY_DIR / "artifacts"
SOURCE = ARTIFACTS / "binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json"
OUTPUT = ARTIFACTS / "binance_as6s_v4_live_safe_future_oos_freeze_2026-07-14.json"
FUTURE_END = pd.Timestamp("2026-10-14T09:00:00Z")

V4_FILES = (
    Path(__file__),
    SOURCE,
    ARTIFACTS / "binance_as6s_asset_first_v4_live_safe_candidate_trades_2026-07-14.csv",
    ARTIFACTS / "binance_as6s_v3_future_tiebreak_audit_2026-07-14.json",
    Path(__file__).with_name("as6s_live_safe_router.py"),
    Path(__file__).with_name("audit_binance_as6s_v3_future_tiebreak.py"),
    Path(__file__).with_name("build_binance_as6s_v4_live_safe_execution_contract.py"),
    Path(__file__).with_name("research_binance_as6s_asset_first_v4_live_safe.py"),
    Path(__file__).with_name("reveal_binance_as6s_v4_live_safe_future_oos.py"),
    Path(__file__).with_name("verify_binance_as6s_v4_live_safe_freeze.py"),
    FAMILY_DIR / "diagnostics/binance-as6s-v4-live-safe-observation-2026-07-14.md",
    ROOT / "tests/test_as6s_live_safe_router.py",
)


def files_to_freeze() -> tuple[Path, ...]:
    return tuple(sorted(set((*v3_freeze.files_to_freeze(), *V4_FILES))))


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    for mode in ("nonpreemptive", "strong_breakout_preemptive"):
        gate = source["diagnostic_gates"][mode]
        if not gate["current_diagnostic_pass"]:
            raise RuntimeError(f"cannot freeze failing V4 route: {mode}")
        if gate["final_future_oos_pass"] is not None:
            raise RuntimeError(f"future OOS already populated unexpectedly: {mode}")
    arbitration = source["arbitration"]
    if not arbitration["entry_time_fields_only"]:
        raise RuntimeError("V4 arbitration is not live-safe")
    forbidden = set(arbitration["forbidden_fields"])
    required_forbidden = {"exit_ts", "exit_reason", "net_return_1x", "mae_return_1x"}
    if not required_forbidden.issubset(forbidden):
        raise RuntimeError("V4 arbitration does not forbid every post-entry field")
    if source["derivation"]["post_selection_data_read_for_derivation"]:
        raise RuntimeError("V4 derivation unexpectedly read post-selection data")

    frozen_files = files_to_freeze()
    missing = [str(path) for path in frozen_files if not path.exists()]
    if missing:
        raise FileNotFoundError(f"freeze inputs missing: {missing}")
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": source["family"],
        "candidate": "BIN-15M-AS6S-V4-live-safe-observation",
        "status": "frozen_observation_not_registered_not_promoted_not_live_ready",
        "selection_end_exclusive": v3_freeze.v3.REUSED_END.isoformat(),
        "derivation": source["derivation"],
        "future_oos": {
            "start_inclusive": v3_freeze.v3.REUSED_END.isoformat(),
            "end_exclusive": FUTURE_END.isoformat(),
            "reveal_policy": (
                "one-shot only after the complete window is available; no parameter, sleeve, "
                "route, exposure, score, arbitration, or execution change before reveal"
            ),
        },
        "arbitration": arbitration,
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
            str(path.relative_to(ROOT)): v3_freeze.sha256_file(path)
            for path in frozen_files
        },
        "data_snapshot_through_selection_end": v3_freeze.data_snapshot(),
        "prohibited_before_reveal": (
            "parameter tuning, sleeve replacement, threshold changes, exposure changes, "
            "account-scale changes, route changes, arbitration changes, data-history rewrites, "
            "and partial future-window inspection"
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
