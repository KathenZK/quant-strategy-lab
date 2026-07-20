from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
MASTER_FREEZE = FAMILY_DIR / (
    "artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json"
)
CHAIN_DIR = FAMILY_DIR / "artifacts/prospective_oos/blind/chain"
EXPECTED_MASTER_SHA256 = (
    "64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11"
)
OOS_START = pd.Timestamp("2026-07-19T00:00:00Z")
OOS_END = pd.Timestamp("2026-10-19T00:00:00Z")
ZERO_HASH = "0" * 64
ALLOWED_STATUS = {"FROZEN_ON_TIME", "MISSED"}
EXPECTED_OUTPUTS = {
    "scores",
    "decision",
    "selected_legs",
    "baseline_decisions",
    "baseline_selected_legs",
}
FORBIDDEN_COLUMN_TOKENS = (
    "label_",
    "trade_return",
    "portfolio_return",
    "stress_trade_return",
    "pnl",
    "profit",
    "drawdown",
    "win_rate",
    "sharpe",
    "entry_open",
    "exit_open",
    "funding_sum",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the prospective signal-only chain without reading outcomes."
    )
    parser.add_argument("--now", help="UTC audit time; defaults to current UTC.")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_utc(value: str | pd.Timestamp) -> pd.Timestamp:
    result = pd.Timestamp(value)
    return result.tz_localize("UTC") if result.tzinfo is None else result.tz_convert("UTC")


def expected_schedule(now: pd.Timestamp) -> list[pd.Timestamp]:
    latest_closed_k0 = now.floor("h") - pd.Timedelta(hours=1)
    if latest_closed_k0 < OOS_START:
        return []
    latest = latest_closed_k0 - pd.Timedelta(hours=latest_closed_k0.hour % 4)
    latest = min(latest, OOS_END - pd.Timedelta(hours=4))
    if latest < OOS_START:
        return []
    return list(pd.date_range(OOS_START, latest, freq="4h"))


def forbidden_columns(columns: list[str]) -> list[str]:
    return sorted(
        column
        for column in columns
        if any(token in column.lower() for token in FORBIDDEN_COLUMN_TOKENS)
    )


def verified_output(
    spec: dict[str, Any],
    *,
    root: Path,
    expected_relative: Path,
    blockers: list[str],
) -> None:
    relative = Path(str(spec.get("path", "")))
    if relative != expected_relative:
        blockers.append(f"snapshot_path_mismatch:{relative}")
        return
    try:
        path = (root / relative).resolve(strict=True)
    except FileNotFoundError:
        blockers.append(f"snapshot_missing:{relative}")
        return
    allowed_root = (
        root
        / "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
        "artifacts/prospective_oos/blind/snapshots"
    ).resolve()
    if path != allowed_root and allowed_root not in path.parents:
        blockers.append(f"snapshot_path_outside_blind_root:{relative}")
        return
    expected_sha = str(spec.get("sha256", ""))
    if sha256(path) != expected_sha:
        blockers.append(f"snapshot_sha_mismatch:{relative}")
        return
    declared_columns = [str(column) for column in spec.get("columns", [])]
    parquet = pq.ParquetFile(path)
    actual_columns = list(parquet.schema_arrow.names)
    if actual_columns != declared_columns:
        blockers.append(f"snapshot_schema_manifest_mismatch:{relative}")
    declared_rows = spec.get("rows")
    if not isinstance(declared_rows, int) or parquet.metadata.num_rows != declared_rows:
        blockers.append(f"snapshot_row_count_mismatch:{relative}")
    bad = forbidden_columns(actual_columns)
    if bad:
        blockers.append(f"snapshot_outcome_columns:{relative}:{','.join(bad)}")


def audit_chain(
    *,
    now: pd.Timestamp,
    root: Path = ROOT,
    master_path: Path = MASTER_FREEZE,
    chain_dir: Path = CHAIN_DIR,
    verify_outputs: bool = True,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not master_path.exists():
        blockers.append("master_freeze_missing")
        master_sha = None
    else:
        master_sha = sha256(master_path)
        if master_sha != EXPECTED_MASTER_SHA256:
            blockers.append("master_freeze_sha_mismatch")

    expected = expected_schedule(now)
    paths = sorted(chain_dir.glob("*.json")) if chain_dir.exists() else []
    if len(paths) > len(expected):
        blockers.append("future_or_extra_chain_nodes")

    previous = ZERO_HASH
    frozen_count = 0
    missed_count = 0
    observed_times: list[pd.Timestamp] = []
    for index, path in enumerate(paths):
        try:
            node = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            blockers.append(f"invalid_chain_json:{path.name}")
            continue
        if node.get("previous_node_sha256") != previous:
            blockers.append(f"chain_link_mismatch:{path.name}")
        if node.get("master_freeze_sha256") != EXPECTED_MASTER_SHA256:
            blockers.append(f"node_master_sha_mismatch:{path.name}")
        try:
            decision_ts = as_utc(node["decision_ts"])
            generated_at = as_utc(node["generated_at"])
            deadline = as_utc(node["collection_deadline"])
        except (KeyError, TypeError, ValueError):
            blockers.append(f"node_time_contract_invalid:{path.name}")
            previous = sha256(path)
            continue
        observed_times.append(decision_ts)
        if index >= len(expected) or decision_ts != expected[index]:
            blockers.append(f"decision_sequence_mismatch:{path.name}")
        if path.stem != decision_ts.strftime("%Y%m%dT%H%M%SZ"):
            blockers.append(f"decision_filename_mismatch:{path.name}")
        if deadline != decision_ts + pd.Timedelta(hours=1, minutes=25):
            blockers.append(f"deadline_mismatch:{path.name}")
        status = str(node.get("status"))
        if status not in ALLOWED_STATUS:
            blockers.append(f"invalid_node_status:{path.name}")
        elif status == "FROZEN_ON_TIME":
            frozen_count += 1
            if generated_at > deadline:
                blockers.append(f"late_node_marked_frozen:{path.name}")
            outputs = node.get("outputs")
            if not isinstance(outputs, dict) or set(outputs) != EXPECTED_OUTPUTS:
                blockers.append(f"snapshot_set_mismatch:{path.name}")
            elif verify_outputs:
                for name in sorted(EXPECTED_OUTPUTS):
                    spec = outputs.get(name)
                    if not isinstance(spec, dict):
                        blockers.append(f"snapshot_spec_invalid:{path.name}:{name}")
                    else:
                        expected_relative = Path(
                            "research/asset-portfolios/"
                            "1h-multi-horizon-cross-sectional-ml-allocator/"
                            "artifacts/prospective_oos/blind/snapshots"
                        ) / decision_ts.strftime("%Y%m%dT%H%M%SZ") / f"{name}.parquet"
                        verified_output(
                            spec,
                            root=root,
                            expected_relative=expected_relative,
                            blockers=blockers,
                        )
        elif status == "MISSED":
            missed_count += 1
            if generated_at <= deadline:
                blockers.append(f"on_time_node_marked_missed:{path.name}")
            if node.get("performance_fields_present") is not False:
                blockers.append(f"missed_node_performance_flag_invalid:{path.name}")
        if node.get("prospective_oos_outcomes_read") is not False:
            blockers.append(f"node_reports_outcome_access:{path.name}")
        previous = sha256(path)

    missing = expected[len(paths) :] if len(paths) < len(expected) else []
    if missing:
        blockers.append(f"missing_due_chain_nodes:{len(missing)}")
    if len(set(observed_times)) != len(observed_times):
        blockers.append("duplicate_decision_timestamps")

    return {
        "family": "Binance-1H-Multi-Horizon-Cross-Sectional-ML-Allocator",
        "version": "BIN-1H-MHCSML-V1",
        "freeze_revision": "r4",
        "audited_at": now.isoformat(),
        "status": "PASS" if not blockers else "BLOCKED",
        "master_freeze_sha256": master_sha,
        "expected_through": expected[-1].isoformat() if expected else None,
        "expected_nodes": len(expected),
        "actual_nodes": len(paths),
        "frozen_on_time_nodes": frozen_count,
        "missed_nodes": missed_count,
        "missing_due_nodes": len(missing),
        "chain_tail_sha256": previous,
        "prospective_oos_outcomes_read": False,
        "blockers": blockers,
    }


def main() -> None:
    args = parse_args()
    now = as_utc(args.now) if args.now else pd.Timestamp.now("UTC")
    result = audit_chain(now=now)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
