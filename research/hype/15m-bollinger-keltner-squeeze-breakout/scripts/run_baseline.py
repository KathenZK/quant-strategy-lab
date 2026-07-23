from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/15m-bollinger-keltner-squeeze-breakout"
ENGINE_PATH = ROOT / "research/_shared-kernels/bollinger-keltner-squeeze-breakout/v1/engine.py"
ENGINE_SHA256 = "1640f7a451b0768c1c8395ea10b135b7e30d0a61e3b6006e7178cac415da841e"
FAMILY_NAME = "HYPE-15M-Bollinger-Keltner-Squeeze-Breakout"
FAMILY_ALIAS = "HYPE-15M-BKSB"
TIMEFRAME = "15m"


def load_engine() -> object:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(f"shared kernel SHA mismatch: expected {ENGINE_SHA256}, got {digest}")
    spec = importlib.util.spec_from_file_location("bollinger_keltner_squeeze_breakout_v1", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    engine = load_engine()
    run_date = datetime.now(UTC).date().isoformat()
    artifact_stem = f"hype-15m-bksb-baseline-{run_date}"
    payload, paths = engine.run_suite(
        ROOT,
        family_dir=FAMILY_DIR,
        family_name=FAMILY_NAME,
        family_alias=FAMILY_ALIAS,
        timeframe=TIMEFRAME,
        run_date=run_date,
    )
    payload["kernel"] = {"path": str(ENGINE_PATH.relative_to(ROOT)), "sha256": ENGINE_SHA256}
    engine.write_outputs(
        family_dir=FAMILY_DIR,
        artifact_stem=artifact_stem,
        payload=payload,
        paths=paths,
    )
    print(json.dumps({"family": FAMILY_NAME, "signals": payload["signal_counts"], "metrics": payload["results"]["primary_k1"]["metrics"], "gate": payload["viability_gate"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
