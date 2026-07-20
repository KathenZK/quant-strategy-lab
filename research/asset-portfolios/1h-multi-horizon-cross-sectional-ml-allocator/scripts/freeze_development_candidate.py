from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
FREEZE_DIR = ARTIFACT_DIR / "freeze"
SEED_AUDIT = ARTIFACT_DIR / "h48_candidate_seed_stability_r4_2026-07-18.json"
SUPERSEDED_LOCK = FREEZE_DIR / "bin-1h-mhcsml-v1-prefit-lock-r3.json"
PREFIT_LOCK = FREEZE_DIR / "bin-1h-mhcsml-v1-prefit-lock-r4.json"
PREFIT_SHA = PREFIT_LOCK.with_suffix(".sha256")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")
PROSPECTIVE_END = pd.Timestamp("2026-10-19T00:00:00Z")
PROSPECTIVE_REVEAL = pd.Timestamp("2026-10-20T21:05:00Z")

EVIDENCE_PATHS = (
    FAMILY_DIR / "specs/binance-1h-mhcsml-research-contract-2026-07-18.md",
    ARTIFACT_DIR / "data_quality_manifest_2026-07-18.json",
    ARTIFACT_DIR / "multihorizon_factor_dataset/factor_dataset_manifest.json",
    ARTIFACT_DIR / "factor_panel_audit_2026-07-18.json",
    ARTIFACT_DIR / "development_model_matrix_manifest.json",
    ARTIFACT_DIR / "development_oof_audit_2026-07-18.json",
    SEED_AUDIT,
    ROOT / "src/strategy_lab/data/linear_contract_returns.py",
    ROOT / "src/strategy_lab/data/factors/multi_asset_tail_1h.py",
    FAMILY_DIR / "scripts/build_multihorizon_factor_panel.py",
    FAMILY_DIR / "scripts/prepare_development_model_matrix.py",
    FAMILY_DIR / "scripts/train_development_walk_forward.py",
    FAMILY_DIR / "scripts/search_development_allocator.py",
    FAMILY_DIR / "scripts/search_h48_confirmation_allocator.py",
    FAMILY_DIR / "scripts/audit_h48_candidate_seed_stability.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_candidate(audit: dict[str, Any]) -> None:
    if audit.get("blockers"):
        raise RuntimeError(f"seed-stability audit has blockers: {audit['blockers']}")
    if audit.get("prospective_oos_outcomes_read"):
        raise RuntimeError("seed audit reports prospective OOS outcome access")
    if audit.get("reused_holdout_outcomes_read"):
        raise RuntimeError("candidate selection accessed reused-holdout outcomes")
    metrics = audit["ensemble"]
    checks = {
        "positive_return": metrics["total_return"] > 0.0,
        "max_drawdown_lte_20pct": metrics["max_drawdown"] >= -0.20,
        "historical_win_rate_gte_52pct": metrics["win_rate"] >= 0.52,
        "sharpe_gte_1_5": metrics["sharpe"] >= 1.50,
        "profit_factor_gte_1_30": metrics["profit_factor"] >= 1.30,
        "majority_folds_positive": metrics["positive_fold_count"] >= 4,
        "stress_positive": metrics["stress_total_return"] > 0.0,
        "stress_drawdown_lte_25pct": metrics["stress_max_drawdown"] >= -0.25,
        "symbol_concentration_lte_25pct": (
            metrics["symbol_positive_profit_concentration"] <= 0.25
        ),
        "month_concentration_lte_35pct": (
            metrics["month_positive_profit_concentration"] <= 0.35
        ),
        "projected_three_month_legs_gte_300": (
            metrics["trade_count"] / 13.0 >= 300
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError(f"candidate freeze gates failed: {failed}")


def main() -> None:
    now = pd.Timestamp.now("UTC")
    if now >= PROSPECTIVE_START:
        raise RuntimeError(
            "prefit candidate lock must be created before prospective OOS starts"
        )
    audit = json.loads(SEED_AUDIT.read_text(encoding="utf-8"))
    assert_candidate(audit)
    missing = [path for path in EVIDENCE_PATHS if not path.exists()]
    if missing:
        raise RuntimeError(f"freeze evidence missing: {missing}")
    evidence = {
        str(path.relative_to(ROOT)): sha256(path) for path in EVIDENCE_PATHS
    }
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "generated_at": now.isoformat(),
        "freeze_stage": "prefit_candidate_parameter_lock",
        "freeze_revision": "r4",
        "status": "PASS",
        "candidate_role": "registered_candidate_pending_prospective_oos",
        "promotion_status": "not promoted",
        "live_ready": False,
        "selection_data_end_exclusive": "2026-04-01T00:00:00+00:00",
        "reused_holdout": {
            "start": "2026-04-01T00:00:00+00:00",
            "end_exclusive": "2026-07-01T00:00:00+00:00",
            "outcomes_read_for_selection": False,
            "permitted_next_role": "final model fitting only after this lock",
        },
        "freeze_gap": {
            "start": "2026-07-01T00:00:00+00:00",
            "end_exclusive": PROSPECTIVE_START.isoformat(),
            "outcomes_read": False,
            "role": "unlabeled data quality and inference warmup only",
        },
        "prospective_oos": {
            "start": PROSPECTIVE_START.isoformat(),
            "end_exclusive": PROSPECTIVE_END.isoformat(),
            "single_reveal_not_before": PROSPECTIVE_REVEAL.isoformat(),
            "last_scheduled_decision_ts": "2026-10-18T20:00:00+00:00",
            "last_planned_exit_ts": "2026-10-20T21:00:00+00:00",
            "outcomes_read": False,
        },
        "candidate_config": audit["candidate_config"],
        "ensemble_seeds": audit["seeds"],
        "development_oof_metrics": audit["ensemble"],
        "seed_stability_gates": audit["gates"],
        "known_non_gate_observation": {
            "annualized_return_below_internal_50pct_search_heuristic": (
                audit["ensemble"]["annualized_return"] < 0.50
            ),
            "positive_month_share": audit["ensemble"]["positive_month_share"],
            "development_win_rate": audit["ensemble"]["win_rate"],
            "development_win_rate_below_final_55pct_target": (
                audit["ensemble"]["win_rate"] < 0.55
            ),
            "projected_three_month_decisions": (
                audit["ensemble"]["decision_count"] / 13.0
            ),
            "projected_three_month_legs": (
                audit["ensemble"]["trade_count"] / 13.0
            ),
            "note": (
                "The final prospective contract does not use the internal 50% "
                "historical annualized-return heuristic as a final pass claim. "
                "The 55% win-rate threshold remains a prospective OOS hard gate."
            ),
        },
        "supersedes": {
            "path": str(SUPERSEDED_LOCK.relative_to(ROOT)),
            "sha256": sha256(SUPERSEDED_LOCK),
            "reason": (
                "R3 utility_z>=2.0 projected only about 234 legs from the unlabeled "
                "prefreeze score distribution, below the 300-leg contract. R4 uses "
                "the already searched utility_z>=1.75 grid point, which passed all "
                "development multi-seed gates and projected about 495 unlabeled legs."
            ),
        },
        "immutable_after_lock": [
            "feature lists",
            "label semantics",
            "four model tasks and four ensemble seeds",
            "48h holding horizon",
            "4h decision cadence",
            "short-only side",
            "confirmation and risk utility thresholds",
            "within-time robust z-score calibration of raw utility",
            "up to five selected symbols per active decision",
            "37.5% gross exposure",
            "cost and funding accounting",
            "prospective OOS window and gates",
        ],
        "evidence_sha256": evidence,
    }
    FREEZE_DIR.mkdir(parents=True, exist_ok=True)
    PREFIT_LOCK.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    digest = sha256(PREFIT_LOCK)
    PREFIT_SHA.write_text(f"{digest}  {PREFIT_LOCK.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "lock": str(PREFIT_LOCK.relative_to(ROOT)),
                "sha256": digest,
                "prospective_start": PROSPECTIVE_START.isoformat(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
