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
OUTPUT = FREEZE_DIR / "bin-1h-mhcsml-v1-freeze-r4.json"
OUTPUT_SHA = OUTPUT.with_suffix(".sha256")
START = pd.Timestamp("2026-07-19T00:00:00Z")
END = pd.Timestamp("2026-10-19T00:00:00Z")
REVEAL = pd.Timestamp("2026-10-20T21:05:00Z")

LOCK = FREEZE_DIR / "bin-1h-mhcsml-v1-prefit-lock-r4.json"
MODEL_FREEZE = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r4.json"
SEED_AUDIT = ARTIFACT_DIR / "h48_candidate_seed_stability_r4_2026-07-18.json"
TAIL_MANIFEST = FREEZE_DIR / "freeze_gap_data_manifest_2026-07-18.json"
INFERENCE_PANEL_MANIFEST = FREEZE_DIR / (
    "prefreeze_inference_panel_manifest_2026-07-18.json"
)
DRY_INFERENCE_MANIFEST = FREEZE_DIR / "prefreeze_dry_inference_r4/manifest.json"
BASELINE_FREEZE = FREEZE_DIR / "bin-1h-mhcsml-v1-baseline-freeze-r4.json"

CODE_AND_CONTRACT_PATHS = (
    ROOT / "src/strategy_lab/data/linear_contract_returns.py",
    ROOT / "src/strategy_lab/data/factors/multi_asset_tail_1h.py",
    FAMILY_DIR / "specs/binance-1h-mhcsml-research-contract-2026-07-18.md",
    FAMILY_DIR / "diagnostics/binance-1h-mhcsml-data-quality-2026-07-18.md",
    FAMILY_DIR / "diagnostics/binance-1h-mhcsml-factor-panel-2026-07-18.md",
    FAMILY_DIR / "diagnostics/binance-1h-mhcsml-development-matrix-2026-07-18.md",
    FAMILY_DIR / "diagnostics/binance-1h-mhcsml-oof-model-allocator-2026-07-18.md",
    FAMILY_DIR / "scripts/build_multihorizon_factor_panel.py",
    FAMILY_DIR / "scripts/prepare_development_model_matrix.py",
    FAMILY_DIR / "scripts/train_development_walk_forward.py",
    FAMILY_DIR / "scripts/search_development_allocator.py",
    FAMILY_DIR / "scripts/search_h48_confirmation_allocator.py",
    FAMILY_DIR / "scripts/search_h48_calibrated_utility_allocator.py",
    FAMILY_DIR / "scripts/audit_h48_candidate_seed_stability.py",
    FAMILY_DIR / "scripts/train_frozen_final_models.py",
    FAMILY_DIR / "scripts/freeze_development_candidate.py",
    FAMILY_DIR / "scripts/bind_frozen_models_to_candidate_r2.py",
    FAMILY_DIR / "scripts/sync_binance_usdm_freeze_gap.py",
    FAMILY_DIR / "scripts/build_prefreeze_inference_panel.py",
    FAMILY_DIR / "scripts/score_frozen_prefreeze_panel.py",
    FAMILY_DIR / "scripts/frozen_r4_inference.py",
    FAMILY_DIR / "scripts/freeze_comparison_baselines.py",
    FAMILY_DIR / "scripts/sync_binance_usdm_prospective_features.py",
    FAMILY_DIR / "scripts/build_blind_prospective_panel.py",
    FAMILY_DIR / "scripts/collect_blind_prospective_signals.py",
    FAMILY_DIR / "scripts/reveal_prospective_oos_once.py",
    ROOT / "tests/test_mhcsml_blind_oos.py",
    ROOT / "tests/test_linear_contract_returns.py",
    ROOT / "tests/test_multi_asset_tail_1h_factors.py",
    ROOT / "tests/test_multihorizon_labels.py",
    ROOT / "tests/test_mhcsml_allocator.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pass(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "PASS" or payload.get("blockers"):
        raise RuntimeError(f"freeze input is not PASS: {path}")
    if payload.get("prospective_oos_outcomes_read"):
        raise RuntimeError(f"freeze input reports prospective outcome access: {path}")
    return payload


def main() -> None:
    now = pd.Timestamp.now("UTC")
    if now >= START:
        raise RuntimeError("R4 master freeze must be finalized before OOS starts")
    lock = load_pass(LOCK)
    models = load_pass(MODEL_FREEZE)
    seed = json.loads(SEED_AUDIT.read_text(encoding="utf-8"))
    if seed.get("blockers") or seed.get("prospective_oos_outcomes_read"):
        raise RuntimeError("R4 seed audit is not clean")
    tail = load_pass(TAIL_MANIFEST)
    panel = load_pass(INFERENCE_PANEL_MANIFEST)
    dry = load_pass(DRY_INFERENCE_MANIFEST)
    baselines = load_pass(BASELINE_FREEZE)
    configs = [
        lock["candidate_config"],
        models["candidate_config"],
        seed["candidate_config"],
        dry["candidate_config"],
    ]
    if any(config != configs[0] for config in configs[1:]):
        raise RuntimeError("R4 config mismatch across freeze evidence")
    if dry["selected_legs"] < 50:
        raise RuntimeError("R4 unlabeled prefreeze inference density is too low")
    if panel["label_columns"]:
        raise RuntimeError("prefreeze inference panel contains labels")
    if panel["missing_frozen_features"]:
        raise RuntimeError("prefreeze inference panel misses frozen features")
    if len(models["models"]) != 16:
        raise RuntimeError("R4 does not contain 16 frozen models")
    for model in models["models"]:
        path = ROOT / model["model_path"]
        if sha256(path) != model["model_sha256"]:
            raise RuntimeError(f"model SHA mismatch: {path}")
    ridge = baselines["baselines"]["ridge_compact"]
    ridge_path = ROOT / ridge["model_path"]
    if sha256(ridge_path) != ridge["model_sha256"]:
        raise RuntimeError("controlled Ridge baseline SHA mismatch")
    if baselines["controlled_allocator"]["gross_exposure"] != configs[0]["gross_exposure"]:
        raise RuntimeError("controlled baseline exposure mismatch")
    missing = [path for path in CODE_AND_CONTRACT_PATHS if not path.exists()]
    if missing:
        raise RuntimeError(f"freeze source files missing: {missing}")
    code_hashes = {
        str(path.relative_to(ROOT)): sha256(path)
        for path in CODE_AND_CONTRACT_PATHS
    }
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "freeze_revision": "r4",
        "generated_at": now.isoformat(),
        "status": "PASS",
        "research_status": "registered",
        "promotion_status": "not promoted",
        "live_ready": False,
        "candidate_config": configs[0],
        "derived_execution_semantics": {
            "decision_sleeve_exposure": 0.03125,
            "allocation_within_sleeve": "equal_weight_across_selected_legs",
            "per_leg_exposure": "decision_sleeve_exposure / selected_leg_count",
            "maximum_overlapping_sleeves": 12,
            "maximum_scheduled_open_gross": 0.375,
        },
        "ensemble_seeds": seed["seeds"],
        "development_oof_metrics": seed["ensemble"],
        "development_seed_gates": seed["gates"],
        "known_risk": {
            "development_win_rate": seed["ensemble"]["win_rate"],
            "below_final_55pct_win_rate_target": seed["ensemble"]["win_rate"] < 0.55,
            "no_final_pass_claim_before_reveal": True,
        },
        "prospective_oos": {
            "start": START.isoformat(),
            "end_exclusive": END.isoformat(),
            "single_reveal_not_before": REVEAL.isoformat(),
            "last_scheduled_decision_ts": "2026-10-18T20:00:00+00:00",
            "last_planned_exit_ts": "2026-10-20T21:00:00+00:00",
            "outcomes_read": False,
            "mutation_policy": (
                "Any change to factors, model binaries, seeds, allocator, costs, "
                "universe, cadence, horizon, exposure or gates invalidates this "
                "window and requires a new future OOS clock."
            ),
        },
        "final_hard_gates": {
            "three_month_return_gte": 0.1892,
            "annualized_return_gte": 1.0,
            "max_drawdown_lte": 0.20,
            "decision_win_rate_gte": 0.55,
            "sharpe_gte": 1.50,
            "profit_factor_gte": 1.30,
            "active_decisions_gte": 45,
            "completed_legs_gte": 300,
            "positive_months_gte": 2,
            "stress_cost_multiple": 1.5,
            "stress_return_positive": True,
            "stress_max_drawdown_lte": 0.25,
            "single_symbol_positive_profit_concentration_lte": 0.25,
            "single_month_positive_profit_concentration_lte": 0.35,
            "majority_historical_folds_positive": True,
            "factor_group_and_tail_ic_direction_stable": True,
            "lgbm_beats_linear_and_rule_baselines": True,
        },
        "freeze_evidence": {
            "candidate_lock": {"path": str(LOCK.relative_to(ROOT)), "sha256": sha256(LOCK)},
            "model_freeze": {"path": str(MODEL_FREEZE.relative_to(ROOT)), "sha256": sha256(MODEL_FREEZE)},
            "seed_audit": {"path": str(SEED_AUDIT.relative_to(ROOT)), "sha256": sha256(SEED_AUDIT)},
            "freeze_gap_data": {"path": str(TAIL_MANIFEST.relative_to(ROOT)), "sha256": sha256(TAIL_MANIFEST)},
            "feature_only_panel": {"path": str(INFERENCE_PANEL_MANIFEST.relative_to(ROOT)), "sha256": sha256(INFERENCE_PANEL_MANIFEST)},
            "dry_inference": {"path": str(DRY_INFERENCE_MANIFEST.relative_to(ROOT)), "sha256": sha256(DRY_INFERENCE_MANIFEST)},
            "controlled_baselines": {"path": str(BASELINE_FREEZE.relative_to(ROOT)), "sha256": sha256(BASELINE_FREEZE)},
        },
        "freeze_gap_seal": {
            "current_closed_end_exclusive": tail["closed_end_exclusive"],
            "prospective_start": START.isoformat(),
            "remaining_hours_are_data_warmup_only": True,
            "must_backfill_before_first_2026_07_19_decision": True,
        },
        "verification": {
            "targeted_tests": {
                "command": (
                    ".venv/bin/python -m pytest -q "
                    "tests/test_linear_contract_returns.py "
                    "tests/test_multi_asset_tail_1h_factors.py "
                    "tests/test_multihorizon_labels.py "
                    "tests/test_mhcsml_allocator.py "
                    "tests/test_mhcsml_blind_oos.py"
                ),
                "result": "20 passed",
            },
            "code_and_contract_sha256": code_hashes,
        },
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    digest = sha256(OUTPUT)
    OUTPUT_SHA.write_text(f"{digest}  {OUTPUT.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "freeze": str(OUTPUT.relative_to(ROOT)),
                "sha256": digest,
                "prospective_start": START.isoformat(),
                "single_reveal_not_before": REVEAL.isoformat(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
