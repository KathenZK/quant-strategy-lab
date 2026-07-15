from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from audit_binance_as6s_v4_joint_state import (
    OUTPUT_PATH as AUDIT_PATH,
    TRADES_OUTPUT_PATH as AUDIT_TRADES_PATH,
)
from research_binance_as6s_asset_first_v4_live_safe import diagnostic_gates


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/15m-asset-specific-six-strategy-selector"
V4_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v4_live_safe_candidate_2026-07-14.json"
)
OUTPUT_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_2026-07-14.json"
)
TRADES_OUTPUT_PATH = (
    FAMILY_DIR
    / "artifacts/binance_as6s_asset_first_v5_joint_state_candidate_trades_2026-07-14.csv"
)


def main() -> None:
    v4 = json.loads(V4_PATH.read_text(encoding="utf-8"))
    audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if not audit["conclusion"]["historical_ledger_changed"]:
        raise RuntimeError("V5 requires a material V4 joint-state correction")
    if audit["post_selection_data_read"]:
        raise RuntimeError("V5 derivation must not inspect post-selection data")

    comparisons = {
        mode: {
            "frozen_params": row["frozen_params"],
            "scenarios": {
                scenario: values["joint_state"]
                for scenario, values in row["scenarios"].items()
            },
        }
        for mode, row in audit["comparisons"].items()
    }
    trades = pd.read_csv(AUDIT_TRADES_PATH)
    trades.to_csv(TRADES_OUTPUT_PATH, index=False)
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "family": v4["family"],
        "stage": "asset_first_v5_joint_state_observation_not_registered_not_live_ready",
        "derivation": {
            "source_observation": "V4 live-safe arbitration candidate",
            "selection_and_parameters_changed": False,
            "strength_and_exposure_changed": False,
            "execution_rule_changed": True,
            "change": (
                "frontier15m and cleanrsi15m no longer create virtual sleeve "
                "occupancy; only an account-accepted order may create position "
                "or cooldown state"
            ),
            "historical_trade_ledger_changed": True,
            "post_selection_data_read_for_derivation": False,
            "audit_artifact": str(AUDIT_PATH.relative_to(ROOT)),
        },
        "future_final_oos": v4["future_final_oos"],
        "candidate_sleeves": v4["candidate_sleeves"],
        "selected_sleeves": v4["selected_sleeves"],
        "sleeve_audit": v4["sleeve_audit"],
        "arbitration": v4["arbitration"],
        "state_contract": {
            "account_position_owner": "global joint account only",
            "blocked_signal_policy": "discard; never queue and never mutate sleeve state",
            "accepted_signal_policy": (
                "create the sole account position; release on its own exit event"
            ),
            "sleeve_cooldown_policy": (
                "start only after an accepted trade exits; zero when the frozen "
                "sleeve has no explicit cooldown"
            ),
            "same_timestamp_reentry": False,
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
                "trades_output": str(TRADES_OUTPUT_PATH),
                "diagnostic_gates": payload["diagnostic_gates"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
