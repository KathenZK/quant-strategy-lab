from __future__ import annotations

import audit_binance_as6s_v6_mark_micro_candidate as audit
import combine_binance_as6s_v6_mark_clean_rsi_joint_refine as joint_refine


audit.SOURCE = (
    audit.FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_refine_2026-07-15.json"
)
audit.OUTPUT = (
    audit.FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_clean_rsi_joint_candidate_audit_2026-07-15.json"
)
audit.REPORT = (
    audit.FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md"
)
audit.PREPARE_INPUTS = joint_refine.prepare_refine_inputs


if __name__ == "__main__":
    audit.main()
