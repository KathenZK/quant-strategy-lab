from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import train_frozen_final_models as final_models  # noqa: E402


ROOT = final_models.ROOT
FAMILY_DIR = final_models.FAMILY_DIR
ARTIFACT_DIR = final_models.ARTIFACT_DIR
FREEZE_DIR = ARTIFACT_DIR / "freeze"
R4_LOCK = FREEZE_DIR / "bin-1h-mhcsml-v1-prefit-lock-r4.json"
R4_MODELS = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r4.json"
OUTPUT_DIR = FREEZE_DIR / "comparison_baselines"
RIDGE_MODEL = OUTPUT_DIR / "short_return_ridge_compact_48h.joblib"
MANIFEST_PATH = FREEZE_DIR / "bin-1h-mhcsml-v1-baseline-freeze-r4.json"
MANIFEST_SHA = MANIFEST_PATH.with_suffix(".sha256")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    now = pd.Timestamp.now("UTC")
    if now >= PROSPECTIVE_START:
        raise RuntimeError("comparison baselines must be frozen before OOS starts")
    lock = json.loads(R4_LOCK.read_text(encoding="utf-8"))
    models = json.loads(R4_MODELS.read_text(encoding="utf-8"))
    if lock.get("status") != "PASS" or models.get("status") != "PASS":
        raise RuntimeError("R4 lock/model freeze is not PASS")
    if lock["candidate_config"] != models["candidate_config"]:
        raise RuntimeError("R4 config mismatch")
    feature_spec = models["feature_lists"]["compact"]
    features = json.loads((ROOT / feature_spec["path"]).read_text(encoding="utf-8"))
    files = final_models.panel_files()
    labels = [
        "label_short_net_48h",
        "label_short_mae_48h",
        "label_short_squeeze_10pct_48h",
    ]
    frame = final_models.load_training_frame(files, features, labels)
    x = frame[features].astype("float32").replace([np.inf, -np.inf], np.nan)
    y = frame["label_short_net_48h"].to_numpy(dtype="float64")
    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", Ridge(alpha=10.0, solver="lsqr")),
        ]
    )
    model.fit(x, y)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, RIDGE_MODEL)
    controlled = {
        "horizon_hours": 48,
        "decision_frequency_hours": 4,
        "side_mode": "short_only",
        "confirmation_weight": lock["candidate_config"]["confirmation_weight"],
        "mae_penalty": lock["candidate_config"]["mae_penalty"],
        "event_penalty": lock["candidate_config"]["event_penalty"],
        "utility_calibration": "within_time_robust_zscore",
        "utility_z_threshold": lock["candidate_config"]["utility_z_threshold"],
        "max_positions": lock["candidate_config"]["max_positions"],
        "gross_exposure": lock["candidate_config"]["gross_exposure"],
        "allocation_within_sleeve": "equal_weight",
    }
    payload = {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "freeze_revision": "r4",
        "generated_at": now.isoformat(),
        "status": "PASS",
        "role": "prospective OOS controlled comparison baselines",
        "comparison_contract": (
            "Replace only the R4 short-return score; retain frozen confirmation, "
            "MAE, squeeze-risk, calibration, cadence, threshold and exposure."
        ),
        "controlled_allocator": controlled,
        "baselines": {
            "ridge_compact": {
                "score": "Ridge(alpha=10) prediction of short_net_48h",
                "model_path": str(RIDGE_MODEL.relative_to(ROOT)),
                "model_sha256": sha256(RIDGE_MODEL),
                "feature_list_path": feature_spec["path"],
                "feature_list_sha256": feature_spec["sha256"],
                "training_rows": len(frame),
                "training_end_exclusive": final_models.TRAIN_END.isoformat(),
                "utility_z_threshold": 0.82,
                "prefreeze_unlabeled_selected_legs": 97,
            },
            "rule_carry_momentum": {
                "score": (
                    "-(0.50*cs_rank_ret_24 + 0.30*cs_rank_ret_168 + "
                    "0.20*cs_rank_ema_spread_24_96 - "
                    "0.20*cs_rank_funding_rate)"
                ),
                "side": "short",
                "fit_required": False,
                "utility_z_threshold": 1.16,
                "prefreeze_unlabeled_selected_legs": 92,
            },
        },
        "density_calibration": {
            "target": "match R4's 95 prefreeze unlabeled selected legs",
            "outcomes_read": False,
            "selection_role": "comparison activity normalization only",
        },
        "r4_model_manifest": str(R4_MODELS.relative_to(ROOT)),
        "r4_model_manifest_sha256": sha256(R4_MODELS),
        "prospective_oos_outcomes_read": False,
        "blockers": [],
    }
    MANIFEST_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    digest = sha256(MANIFEST_PATH)
    MANIFEST_SHA.write_text(f"{digest}  {MANIFEST_PATH.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "training_rows": len(frame),
                "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
                "sha256": digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
