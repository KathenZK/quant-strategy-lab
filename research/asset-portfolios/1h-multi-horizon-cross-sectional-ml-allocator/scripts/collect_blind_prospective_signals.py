from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from frozen_r4_inference import (  # noqa: E402
    outcome_columns,
    score_controlled_baselines,
    score_r4_panel,
    sha256,
)


OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
REVEAL_NOT_BEFORE = pd.Timestamp("2026-10-20T21:05:00Z")
GRACE = pd.Timedelta(minutes=25)
FREEZE_DIR = FAMILY_DIR / "artifacts/freeze"
MASTER_FREEZE = FREEZE_DIR / "bin-1h-mhcsml-v1-freeze-r4.json"
MODEL_MANIFEST = FREEZE_DIR / "bin-1h-mhcsml-v1-model-freeze-r4.json"
BASELINE_MANIFEST = FREEZE_DIR / "bin-1h-mhcsml-v1-baseline-freeze-r4.json"
PANEL_MANIFEST = FAMILY_DIR / (
    "artifacts/prospective_oos/working/current_feature_panel_manifest.json"
)
BLIND_DIR = FAMILY_DIR / "artifacts/prospective_oos/blind"
CHAIN_DIR = BLIND_DIR / "chain"
SNAPSHOT_DIR = BLIND_DIR / "snapshots"
ZERO_HASH = "0" * 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Append on-time R4 signal snapshots only; never read labels, prices "
            "after entry, or performance."
        )
    )
    parser.add_argument(
        "--now",
        help="UTC override allowed only with --validate-only for deterministic tests.",
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def atomic_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def timestamp_id(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y%m%dT%H%M%SZ")


def chain_paths() -> list[Path]:
    return sorted(CHAIN_DIR.glob("*.json"))


def verify_chain(master_sha: str) -> tuple[set[pd.Timestamp], str]:
    seen: set[pd.Timestamp] = set()
    previous = ZERO_HASH
    for path in chain_paths():
        node = json.loads(path.read_text(encoding="utf-8"))
        if node["previous_node_sha256"] != previous:
            raise RuntimeError(f"blind chain link mismatch: {path}")
        if node["master_freeze_sha256"] != master_sha:
            raise RuntimeError(f"blind node uses a different master freeze: {path}")
        ts = pd.Timestamp(node["decision_ts"])
        if ts in seen:
            raise RuntimeError(f"duplicate blind decision timestamp: {ts}")
        seen.add(ts)
        previous = sha256(path)
    return seen, previous


def append_node(payload: dict[str, Any], previous_sha: str) -> str:
    decision_ts = pd.Timestamp(payload["decision_ts"])
    path = CHAIN_DIR / f"{timestamp_id(decision_ts)}.json"
    if path.exists():
        raise RuntimeError(f"blind node already exists: {path}")
    node = {**payload, "previous_node_sha256": previous_sha}
    atomic_json(node, path)
    return sha256(path)


def scheduled_through(now: pd.Timestamp) -> list[pd.Timestamp]:
    latest_closed_k0 = now.floor("h") - pd.Timedelta(hours=1)
    if latest_closed_k0 < OOS_START:
        return []
    latest = latest_closed_k0 - pd.Timedelta(hours=latest_closed_k0.hour % 4)
    latest = min(latest, OOS_END - pd.Timedelta(hours=4))
    if latest < OOS_START:
        return []
    return list(pd.date_range(OOS_START, latest, freq="4h"))


def load_current_panel(decision_ts: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest = json.loads(PANEL_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("blockers"):
        raise RuntimeError("current feature-only panel manifest is not PASS")
    if manifest.get("prospective_oos_outcomes_read"):
        raise RuntimeError("current panel manifest reports protected outcome access")
    panel_path = ROOT / manifest["panel_path"]
    if sha256(panel_path) != manifest["panel_sha256"]:
        raise RuntimeError("current feature-only panel SHA mismatch")
    panel = pd.read_parquet(panel_path)
    panel["ts"] = pd.to_datetime(panel["ts"], utc=True)
    forbidden = outcome_columns(panel.columns)
    if forbidden:
        raise RuntimeError(f"current panel contains outcome columns: {forbidden}")
    panel = panel.loc[panel["ts"].eq(decision_ts)].copy()
    if panel.empty:
        raise RuntimeError(f"current panel does not contain decision ts {decision_ts}")
    return panel, manifest


def write_signal_snapshot(
    decision_ts: pd.Timestamp,
    scores: pd.DataFrame,
    decisions: pd.DataFrame,
    legs: pd.DataFrame,
    baseline_decisions: pd.DataFrame,
    baseline_legs: pd.DataFrame,
) -> dict[str, Any]:
    target = SNAPSHOT_DIR / timestamp_id(decision_ts)
    if target.exists():
        raise RuntimeError(f"blind signal snapshot already exists: {target}")
    temporary = target.with_name(target.name + ".tmp")
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    outputs: dict[str, Any] = {}
    for name, frame in (
        ("scores", scores),
        ("decision", decisions),
        ("selected_legs", legs),
        ("baseline_decisions", baseline_decisions),
        ("baseline_selected_legs", baseline_legs),
    ):
        path = temporary / f"{name}.parquet"
        frame.to_parquet(path, index=False, compression="zstd")
        outputs[name] = {
            "path": str((target / path.name).relative_to(ROOT)),
            "sha256": sha256(path),
            "rows": len(frame),
            "columns": list(frame.columns),
        }
    os.replace(temporary, target)
    return outputs


def main() -> None:
    args = parse_args()
    if args.now and not args.validate_only:
        raise RuntimeError("--now is forbidden outside --validate-only")
    now = pd.Timestamp(args.now) if args.now else pd.Timestamp.now("UTC")
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    else:
        now = now.tz_convert("UTC")
    master = json.loads(MASTER_FREEZE.read_text(encoding="utf-8"))
    if master.get("status") != "PASS":
        raise RuntimeError("R4 master freeze is not PASS")
    master_sha = sha256(MASTER_FREEZE)
    if master["prospective_oos"]["single_reveal_not_before"] != REVEAL_NOT_BEFORE.isoformat():
        raise RuntimeError("master freeze reveal boundary mismatch")
    seen, previous_sha = verify_chain(master_sha)
    schedule = scheduled_through(now)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "role": "blind collector validation only",
                    "now": now.isoformat(),
                    "scheduled_through": schedule[-1].isoformat() if schedule else None,
                    "existing_nodes": len(seen),
                    "prospective_oos_outcomes_read": False,
                },
                indent=2,
            )
        )
        return
    if now < OOS_START:
        raise RuntimeError("prospective OOS signal window has not started")
    if now >= REVEAL_NOT_BEFORE:
        raise RuntimeError("blind collection has ended; use the one-time reveal guard")
    appended = 0
    for decision_ts in schedule:
        if decision_ts in seen:
            continue
        entry_time = decision_ts + pd.Timedelta(hours=1)
        deadline = entry_time + GRACE
        base_node = {
            "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
            "version": "BIN-1H-MHCSML-V1",
            "freeze_revision": "r4",
            "generated_at": now.isoformat(),
            "decision_ts": decision_ts.isoformat(),
            "entry_time": entry_time.isoformat(),
            "collection_deadline": deadline.isoformat(),
            "master_freeze_sha256": master_sha,
            "model_manifest_sha256": sha256(MODEL_MANIFEST),
            "prospective_oos_outcomes_read": False,
        }
        if now > deadline:
            previous_sha = append_node(
                {
                    **base_node,
                    "status": "MISSED",
                    "reason": "signal was not frozen before the on-time collection deadline",
                    "performance_fields_present": False,
                },
                previous_sha,
            )
            seen.add(decision_ts)
            appended += 1
            continue
        panel, panel_manifest = load_current_panel(decision_ts)
        scores, decisions, legs, metadata = score_r4_panel(
            panel, root=ROOT, model_manifest_path=MODEL_MANIFEST
        )
        baseline_decisions, baseline_legs, baseline_metadata = (
            score_controlled_baselines(
                panel,
                scores,
                root=ROOT,
                baseline_manifest_path=BASELINE_MANIFEST,
            )
        )
        if len(decisions) != 1 or pd.Timestamp(decisions.iloc[0]["ts"]) != decision_ts:
            raise RuntimeError("frozen scorer did not emit exactly one expected decision")
        outputs = write_signal_snapshot(
            decision_ts,
            scores,
            decisions,
            legs,
            baseline_decisions,
            baseline_legs,
        )
        previous_sha = append_node(
            {
                **base_node,
                "status": "FROZEN_ON_TIME",
                "panel_manifest_sha256": sha256(PANEL_MANIFEST),
                "source_data_manifest_sha256": panel_manifest[
                    "source_data_manifest_sha256"
                ],
                "active": bool(decisions.iloc[0]["active"]),
                "selected_legs": len(legs),
                "baseline_selected_legs": {
                    name: int(count)
                    for name, count in baseline_legs["baseline"].value_counts().items()
                },
                "sleeve_exposure": metadata["sleeve_exposure"],
                "baseline_manifest_sha256": baseline_metadata[
                    "baseline_manifest_sha256"
                ],
                "outputs": outputs,
                "performance_fields_present": False,
            },
            previous_sha,
        )
        seen.add(decision_ts)
        appended += 1
    print(
        json.dumps(
            {
                "status": "PASS",
                "role": "blind prospective signal collection",
                "generated_at": now.isoformat(),
                "nodes_appended": appended,
                "total_chain_nodes": len(seen),
                "last_node_sha256": previous_sha,
                "scheduled_through": schedule[-1].isoformat() if schedule else None,
                "prospective_oos_outcomes_read": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
