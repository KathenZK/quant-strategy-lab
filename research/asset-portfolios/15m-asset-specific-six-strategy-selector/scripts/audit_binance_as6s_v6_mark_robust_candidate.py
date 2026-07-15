from __future__ import annotations

import audit_binance_as6s_v6_mark_micro_candidate as audit


audit.SOURCE = (
    audit.FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_robust_account_2026-07-15.json"
)
audit.OUTPUT = (
    audit.FAMILY_DIR
    / "artifacts/binance_as6s_v6_mark_robust_candidate_audit_2026-07-15.json"
)
audit.REPORT = (
    audit.FAMILY_DIR
    / "diagnostics/binance-as6s-v6-mark-robust-candidate-audit-2026-07-15.md"
)


if __name__ == "__main__":
    audit.main()
