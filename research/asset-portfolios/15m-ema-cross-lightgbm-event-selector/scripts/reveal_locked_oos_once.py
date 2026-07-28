"""One-shot locked-OOS reveal for BIN-15M-EMAX-LGBM (2026-01-01 .. 2026-06-30 UTC).

Requires EMAX_OOS_REVEAL=1 and an existing freeze manifest. Verifies the frozen
model and code hashes, extracts OOS events (with two months of pre-context for
cluster features), scores them with the frozen models, runs the frozen
portfolio rules, and evaluates the pre-registered hard gates. Refuses to run if
a reveal report already exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import joblib
import pandas as pd

import emax_common as ec
import backtest_portfolio as bp
from train_event_models import feature_columns, score_events


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=ec.ARTIFACT_DIR / "model_v1")
    parser.add_argument(
        "--output", type=Path, default=ec.ARTIFACT_DIR / "model_v1" / "locked_oos_reveal.json"
    )
    args = parser.parse_args()

    if os.environ.get("EMAX_OOS_REVEAL") != "1":
        raise RuntimeError("reveal requires EMAX_OOS_REVEAL=1")
    if args.output.exists():
        raise RuntimeError(f"reveal already happened, refusing to rerun: {args.output}")
    freeze_path = args.model_dir / "freeze_manifest.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))

    scripts_dir = Path(__file__).resolve().parent
    for name, expected in freeze["code_sha256"].items():
        actual = sha256(scripts_dir / name)
        if actual != expected:
            raise RuntimeError(f"code hash mismatch for {name}: {actual} != {expected}")
    for name, expected in freeze["models"].items():
        actual = sha256(args.model_dir / f"final_{name}.joblib")
        if actual != expected:
            raise RuntimeError(f"model hash mismatch for {name}")

    events_path = ec.ARTIFACT_DIR / "events_oos_reveal.parquet"
    dataset_path = ec.ARTIFACT_DIR / "event_dataset_oos_reveal.parquet"
    env = os.environ | {"EMAX_OOS_REVEAL": "1"}
    subprocess.run(
        [
            sys.executable, str(scripts_dir / "extract_cross_events.py"),
            "--include-locked-oos", "--min-entry-ts", "2025-11-01",
            "--output", str(events_path),
        ],
        check=True,
        env=env,
    )
    subprocess.run(
        [
            sys.executable, str(scripts_dir / "build_event_dataset.py"),
            "--events", str(events_path), "--output", str(dataset_path),
        ],
        check=True,
        env=env,
    )

    dataset = pd.read_parquet(dataset_path)
    dataset["entry_ts"] = pd.to_datetime(dataset["entry_ts"], utc=True)
    oos = dataset.loc[
        (dataset["entry_ts"] >= ec.LOCKED_OOS_START)
        & (dataset["entry_ts"] < ec.LOCKED_OOS_END)
    ].copy()

    bracket = freeze["bracket"]
    k_tp, k_sl = ec.BRACKETS[bracket]
    net_column = f"{bracket}_net_atr"
    exit_column = f"{bracket}_exit_ts"
    oos[exit_column] = pd.to_datetime(oos[exit_column], utc=True)
    features = feature_columns()

    training = json.loads(
        (args.model_dir / "training_report.json").read_text(encoding="utf-8")
    )
    parts = []
    for side, name in ((1, "long"), (-1, "short")):
        model = joblib.load(args.model_dir / f"final_{name}.joblib")
        timeout_mean = training["final_models"][name]["timeout_mean_atr"]
        side_rows = oos.loc[oos["side"] == side].copy()
        scored = score_events(model, side_rows, features, k_tp, k_sl, timeout_mean)
        parts.append(pd.concat([side_rows, scored], axis=1))
    scored_oos = pd.concat(parts, ignore_index=True)
    pool = scored_oos.loc[scored_oos["in_trading_pool"]].copy()

    tau = freeze["tau"]
    result = bp.simulate(pool, tau=tau, net_column=net_column, exit_column=exit_column)
    stress = bp.simulate(
        pool, tau=tau, net_column=net_column, exit_column=exit_column, stress=1.5
    )
    baseline_a = bp.simulate(pool, tau=None, net_column=net_column, exit_column=exit_column)

    gates = freeze["hard_gates"]
    checks = {
        "min_trades": result.get("trades", 0) >= gates["min_trades"],
        "net_return_positive": result.get("total_return", 0.0) > 0.0,
        "profit_factor": result.get("profit_factor", 0.0) >= gates["min_profit_factor"],
        "max_drawdown": result.get("max_drawdown", 1.0) <= gates["max_drawdown_limit"],
        "stress_positive": stress.get("total_return", 0.0) > 0.0,
        "beats_baseline_a": result.get("total_return", 0.0)
        > baseline_a.get("total_return", 0.0),
    }
    verdict = "PASS" if all(checks.values()) else "HARD-GATE-FAILED"

    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "freeze_manifest_sha256": sha256(freeze_path),
        "window": [str(ec.LOCKED_OOS_START), str(ec.LOCKED_OOS_END)],
        "reused_holdout_note": freeze["locked_oos"]["reused_holdout_note"],
        "oos_events": int(len(scored_oos)),
        "oos_trading_pool_events": int(len(pool)),
        "tau": tau,
        "portfolio_result": result,
        "portfolio_result_stress_1p5x": stress,
        "baseline_a_result": baseline_a,
        "gate_checks": checks,
        "verdict": verdict,
    }
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    print(json.dumps({"gate_checks": checks, "verdict": verdict}, indent=2))
    print(f"reveal -> {args.output}")


if __name__ == "__main__":
    main()
