from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1h-multi-horizon-ema-forecast"
ENGINE_PATH = (
    ROOT
    / "research/_shared-kernels/multi-horizon-ema-forecast/v1/engine.py"
)
ENGINE_SHA256 = "63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4"
FAMILY_NAME = "HYPE-1H-Multi-Horizon-EMA-Forecast"
FAMILY_ALIAS = "HYPE-1H-MHEF"
TIMEFRAME = "1h"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Run {FAMILY_NAME} baseline research.")
    parser.add_argument(
        "--run-date",
        default=datetime.now(UTC).date().isoformat(),
        help="Date embedded in report and artifact filenames.",
    )
    return parser.parse_args()


def load_engine() -> object:
    digest = hashlib.sha256(ENGINE_PATH.read_bytes()).hexdigest()
    if digest != ENGINE_SHA256:
        raise RuntimeError(
            f"shared kernel SHA mismatch: expected {ENGINE_SHA256}, got {digest}"
        )
    spec = importlib.util.spec_from_file_location("multi_horizon_ema_forecast_v1", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import shared kernel: {ENGINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    args = parse_args()
    engine = load_engine()
    artifact_stem = f"hype-1h-mhef-baseline-{args.run_date}"
    payload, paths = engine.run_suite(ROOT, timeframe=TIMEFRAME)
    payload["family_name"] = FAMILY_NAME
    payload["family_alias"] = FAMILY_ALIAS
    payload["run_date"] = args.run_date
    payload["kernel"] = {
        "path": str(ENGINE_PATH.relative_to(ROOT)),
        "sha256": ENGINE_SHA256,
    }
    payload["artifacts"] = {
        "summary": f"artifacts/{artifact_stem}-summary.json",
        "forecasts": f"artifacts/{artifact_stem}-forecasts.csv",
        "paths": f"artifacts/{artifact_stem}-paths.csv",
    }
    engine.write_suite_outputs(
        family_dir=FAMILY_DIR,
        artifact_stem=artifact_stem,
        payload=payload,
        paths=paths,
    )
    report_path = (
        FAMILY_DIR
        / "notes"
        / f"hype-1h-mhef-baseline-backtest-{args.run_date}.md"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        engine.render_markdown_report(
            payload=payload,
            family_name=FAMILY_NAME,
            family_alias=FAMILY_ALIAS,
            artifact_stem=artifact_stem,
            kernel_sha256=ENGINE_SHA256,
            run_date=args.run_date,
        ),
        encoding="utf-8",
    )
    headline = {
        result["name"]: result["metrics"]
        for result in payload["results"]
        if result["name"]
        in {"ensemble_buffer_0.00", "ensemble_buffer_0.10", "perpetual_buy_hold_1x"}
    }
    print(json.dumps(headline, ensure_ascii=False, indent=2))
    print(f"report -> {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
