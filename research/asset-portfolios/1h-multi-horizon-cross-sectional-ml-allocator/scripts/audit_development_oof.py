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
OOF_ROOT = ARTIFACT_DIR / "development_walk_forward"
AUDIT_PATH = ARTIFACT_DIR / "development_oof_audit_2026-07-18.json"
SUMMARY_PATH = ARTIFACT_DIR / "development_oof_predictive_summary_2026-07-18.csv"
DEVELOPMENT_END = pd.Timestamp("2026-04-01T00:00:00Z")
PURGE_HOURS = 48
EXPECTED_FOLDS = 7
HORIZONS = (4, 8, 12, 24, 48)
EXPECTED_CONFIGS = (
    ("long_return", "regression"),
    ("short_return", "regression"),
    ("long_mae", "quantile"),
    ("short_mae", "quantile"),
    ("long_event", "classification"),
    ("short_event", "classification"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_diagnostics() -> list[dict[str, Any]]:
    rows = []
    for path in sorted(OOF_ROOT.glob("*/diagnostics.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["diagnostic_path"] = str(path.relative_to(ROOT))
        rows.append(payload)
    return rows


def main() -> None:
    diagnostics = read_diagnostics()
    blockers: list[str] = []
    selected = [
        row
        for row in diagnostics
        if row.get("feature_set") == "compact"
        and int(row.get("seed", -1)) == 42
        and (row.get("task"), row.get("model_type")) in EXPECTED_CONFIGS
        and int(row.get("horizon_hours", -1)) in HORIZONS
        and row.get("train_window_days") is None
    ]
    expected_total = len(EXPECTED_CONFIGS) * len(HORIZONS) * EXPECTED_FOLDS
    if len(selected) != expected_total:
        blockers.append(f"expected_diagnostics={expected_total},actual={len(selected)}")
    identities = [str(row.get("identity")) for row in selected]
    if len(identities) != len(set(identities)):
        blockers.append("duplicate_model_identities")
    predictive_rows: list[dict[str, Any]] = []
    model_hash_failures = 0
    boundary_failures = 0
    isolation_failures = 0
    for row in selected:
        validation_start = pd.Timestamp(row["validation_start"])
        validation_end = pd.Timestamp(row["validation_end_exclusive"])
        train_end = pd.Timestamp(row["train_end_exclusive"])
        if validation_end > DEVELOPMENT_END:
            boundary_failures += 1
        if train_end > validation_start - pd.Timedelta(hours=PURGE_HOURS):
            boundary_failures += 1
        if (
            not row.get("development_only")
            or row.get("reused_holdout_outcomes_read")
            or row.get("prospective_oos_outcomes_read")
        ):
            isolation_failures += 1
        model_path = ROOT / row["model_path"]
        if not model_path.exists() or sha256(model_path) != row.get("model_sha256"):
            model_hash_failures += 1
        predictive = row.get("predictive", {})
        predictive_rows.append(
            {
                "task": row["task"],
                "model_type": row["model_type"],
                "feature_set": row["feature_set"],
                "horizon_hours": int(row["horizon_hours"]),
                "fold_id": row["fold_id"],
                "validation_rows": int(row["validation_rows"]),
                "best_iteration": row.get("best_iteration"),
                "global_spearman": predictive.get("spearman"),
                "mean_cross_sectional_rank_ic": predictive.get(
                    "mean_cross_sectional_rank_ic"
                ),
                "positive_cross_sectional_rank_ic_share": predictive.get(
                    "positive_cross_sectional_rank_ic_share"
                ),
            }
        )
    if model_hash_failures:
        blockers.append(f"model_hash_failures={model_hash_failures}")
    if boundary_failures:
        blockers.append(f"boundary_failures={boundary_failures}")
    if isolation_failures:
        blockers.append(f"isolation_failures={isolation_failures}")
    predictive_frame = pd.DataFrame(predictive_rows)
    if predictive_frame.empty:
        summary = pd.DataFrame()
    else:
        summary = (
            predictive_frame.groupby(
                ["task", "model_type", "feature_set", "horizon_hours"],
                as_index=False,
            )
            .agg(
                fold_count=("fold_id", "nunique"),
                validation_rows=("validation_rows", "sum"),
                mean_rank_ic=("mean_cross_sectional_rank_ic", "mean"),
                min_fold_rank_ic=("mean_cross_sectional_rank_ic", "min"),
                max_fold_rank_ic=("mean_cross_sectional_rank_ic", "max"),
                mean_positive_rank_ic_share=(
                    "positive_cross_sectional_rank_ic_share",
                    "mean",
                ),
                median_best_iteration=("best_iteration", "median"),
            )
            .sort_values(["task", "horizon_hours"])
        )
        incomplete = summary.loc[summary["fold_count"] != EXPECTED_FOLDS]
        if not incomplete.empty:
            blockers.append(f"incomplete_configurations={len(incomplete)}")
    summary.to_csv(SUMMARY_PATH, index=False)
    audit = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "development_only": True,
        "reused_holdout_outcomes_read": False,
        "prospective_oos_outcomes_read": False,
        "expected_diagnostics": expected_total,
        "actual_diagnostics": len(selected),
        "model_hash_failures": model_hash_failures,
        "boundary_failures": boundary_failures,
        "isolation_failures": isolation_failures,
        "configuration_summary_rows": len(summary),
        "predictive_summary_csv": str(SUMMARY_PATH.relative_to(ROOT)),
        "blockers": blockers,
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, ensure_ascii=False, default=str))
    if blockers:
        raise RuntimeError(f"development OOF audit blocked: {blockers}")


if __name__ == "__main__":
    main()
