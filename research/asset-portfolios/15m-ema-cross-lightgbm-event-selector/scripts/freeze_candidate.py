"""Phase 5 freeze for BIN-15M-EMAX-LGBM: pin every artifact before the OOS reveal.

Writes a freeze manifest with SHA256 of models, dataset, code, the chosen
bracket/threshold/portfolio rules, and the pre-registered hard gates. The
locked OOS may be revealed exactly once, only after this manifest exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

import emax_common as ec


HARD_GATES = {
    "min_trades": 60,
    "net_return_positive": True,
    "min_profit_factor": 1.2,
    "max_drawdown_limit": 0.15,
    "stress_1p5x_positive": True,
    "must_beat_baseline_a": True,
}

CODE_FILES = [
    "emax_common.py",
    "emax_features.py",
    "extract_cross_events.py",
    "build_event_dataset.py",
    "train_event_models.py",
    "backtest_portfolio.py",
    "reveal_locked_oos_once.py",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ec.ARTIFACT_DIR / "model_v1")
    parser.add_argument(
        "--output", type=Path, default=ec.ARTIFACT_DIR / "model_v1" / "freeze_manifest.json"
    )
    args = parser.parse_args()

    if args.output.exists():
        raise RuntimeError(f"freeze manifest already exists, refusing to overwrite: {args.output}")

    portfolio = json.loads(
        (args.model_dir / "portfolio_report.json").read_text(encoding="utf-8")
    )
    if portfolio.get("decision") != "P4_GATE_PASS":
        raise RuntimeError(f"P4 gate not passed: {portfolio.get('decision')}")
    baseline = json.loads(
        (ec.ARTIFACT_DIR / "baseline_a_report.json").read_text(encoding="utf-8")
    )

    scripts_dir = Path(__file__).resolve().parent
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "family": "Binance-15M-EMA-Cross-LightGBM-Event-Selector",
        "contract": "specs/bin-15m-emax-lgbm-research-contract-2026-07-23.md",
        "bracket": baseline["bracket_selection"]["chosen"],
        "tau": portfolio["chosen"]["tau"],
        "portfolio_rules": portfolio["rules"],
        "locked_oos": {
            "start": str(ec.LOCKED_OOS_START),
            "end": str(ec.LOCKED_OOS_END),
            "reused_holdout_note": "2026Q2 was previously revealed by BIN-1H-CSLGBM",
        },
        "hard_gates": HARD_GATES,
        "models": {
            name: sha256(args.model_dir / f"final_{name}.joblib")
            for name in ["long", "short"]
        },
        "dataset_sha256": sha256(ec.ARTIFACT_DIR / "event_dataset_dev.parquet"),
        "events_sha256": sha256(ec.ARTIFACT_DIR / "events_dev.parquet"),
        "code_sha256": {name: sha256(scripts_dir / name) for name in CODE_FILES},
        "training_report_sha256": sha256(args.model_dir / "training_report.json"),
    }
    args.output.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({k: manifest[k] for k in ["bracket", "tau", "hard_gates"]}, indent=2))
    print(f"freeze -> {args.output}")


if __name__ == "__main__":
    main()
