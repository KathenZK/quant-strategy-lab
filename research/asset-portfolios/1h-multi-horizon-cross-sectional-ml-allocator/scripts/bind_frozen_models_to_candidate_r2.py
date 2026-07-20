from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
FREEZE_DIR = FAMILY_DIR / "artifacts/freeze"
LOCK_R2 = FREEZE_DIR / "bin-1h-mhcsml-v1-prefit-lock-r4.json"
SOURCE_MODEL_FREEZE = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r3.json"
OUTPUT = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r4.json"
OUTPUT_SHA = OUTPUT.with_suffix(".sha256")
PROSPECTIVE_START = pd.Timestamp("2026-07-19T00:00:00Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if pd.Timestamp.now("UTC") >= PROSPECTIVE_START:
        raise RuntimeError("model binding revision must precede prospective OOS")
    lock = json.loads(LOCK_R2.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_MODEL_FREEZE.read_text(encoding="utf-8"))
    if lock.get("status") != "PASS" or source.get("status") != "PASS":
        raise RuntimeError("candidate lock or source model freeze is not PASS")
    for model in source["models"]:
        path = ROOT / model["model_path"]
        if sha256(path) != model["model_sha256"]:
            raise RuntimeError(f"frozen model SHA mismatch: {path}")
    payload = {
        **source,
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "freeze_revision": "r4",
        "candidate_prefit_lock": str(LOCK_R2.relative_to(ROOT)),
        "candidate_prefit_lock_sha256": sha256(LOCK_R2),
        "candidate_config": lock["candidate_config"],
        "model_binaries_reused_without_retraining": True,
        "model_binary_reuse_reason": (
            "R4 changes only the already-searched calibrated utility threshold; "
            "the four frozen model tasks, feature lists, seeds, training data and "
            "model binaries are unchanged."
        ),
        "superseded_model_freeze": {
            "path": str(SOURCE_MODEL_FREEZE.relative_to(ROOT)),
            "sha256": sha256(SOURCE_MODEL_FREEZE),
            "reason": "bound to the leg-density-infeasible R3 threshold",
        },
        "prospective_oos_outcomes_read": False,
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
                "models_verified": len(source["models"]),
                "manifest": str(OUTPUT.relative_to(ROOT)),
                "sha256": digest,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
