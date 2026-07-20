from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAMILY = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
OOS = FAMILY / "artifacts/v1_oos_2026q2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_revocation_manifest_binds_original_and_corrected_evidence() -> None:
    revocation = json.loads((OOS / "REVOCATION.json").read_text(encoding="utf-8"))
    assert revocation["status"].startswith("REVOKED_FORMULA_INVALID")
    assert revocation["invalid_claims"]["oos_total_return"] > 2.0
    assert revocation["corrected_fixed_selection_oos"]["total_return"] < 0.0
    assert "oos_gate_audit.json" in revocation["revoked_artifact_patterns"]
    assert "models/*" in revocation["revoked_artifact_patterns"]

    evidence = revocation["evidence_sha256"]
    paths = {
        "original_oos_gate_audit": OOS / "oos_gate_audit.json",
        "original_oos_result": OOS / "oos_result.json",
        "original_execution_stress": OOS / "oos_execution_stress_audit.json",
        "original_recent_slice": OOS / "v1_recent_slice_audit.json",
        "correction_audit": OOS / "linear_return_correction/correction_audit.json",
        "correction_script": FAMILY / "scripts/audit_v1_short_return_correction.py",
        "linear_return_implementation": ROOT
        / "src/strategy_lab/data/linear_contract_returns.py",
        "linear_return_tests": ROOT / "tests/test_linear_contract_returns.py",
    }
    assert set(evidence) == set(paths)
    for name, path in paths.items():
        assert sha256(path) == evidence[name]


def test_repository_routes_expose_formula_invalidation() -> None:
    research_index = (ROOT / "research/README.md").read_text(encoding="utf-8")
    portfolio_index = (ROOT / "research/asset-portfolios/README.md").read_text(
        encoding="utf-8"
    )
    family_readme = (FAMILY / "README.md").read_text(encoding="utf-8")
    assert "formula-invalidated / HARD-GATE-FAILED" in research_index
    assert "旧绩效因空头公式错误全部撤销" in portfolio_index
    assert "V1 OOS artifact 撤销清单" in family_readme
