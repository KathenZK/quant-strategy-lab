from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/audit_blind_chain_health.py"
)
SPEC = importlib.util.spec_from_file_location("audit_blind_chain_health", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_master(path: Path) -> None:
    path.write_text("frozen", encoding="utf-8")


def write_missed_node(
    chain: Path,
    *,
    decision_ts: pd.Timestamp,
    generated_at: pd.Timestamp,
    previous: str,
    master_sha256: str | None = None,
) -> Path:
    payload = {
        "decision_ts": decision_ts.isoformat(),
        "generated_at": generated_at.isoformat(),
        "collection_deadline": (
            decision_ts + pd.Timedelta(hours=1, minutes=25)
        ).isoformat(),
        "status": "MISSED",
        "master_freeze_sha256": master_sha256 or audit.EXPECTED_MASTER_SHA256,
        "previous_node_sha256": previous,
        "prospective_oos_outcomes_read": False,
        "performance_fields_present": False,
    }
    path = chain / f"{decision_ts.strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_expected_schedule_uses_only_closed_k0() -> None:
    before = pd.Timestamp("2026-07-19T00:59:00Z")
    after = pd.Timestamp("2026-07-19T01:01:00Z")
    assert audit.expected_schedule(before) == []
    assert audit.expected_schedule(after) == [
        pd.Timestamp("2026-07-19T00:00:00Z")
    ]


def test_complete_missed_chain_passes_without_outputs(tmp_path: Path) -> None:
    chain = tmp_path / "chain"
    chain.mkdir()
    master = tmp_path / "master.json"
    write_master(master)
    first = write_missed_node(
        chain,
        decision_ts=pd.Timestamp("2026-07-19T00:00:00Z"),
        generated_at=pd.Timestamp("2026-07-19T01:26:00Z"),
        previous="0" * 64,
        master_sha256=digest(master),
    )
    original = audit.EXPECTED_MASTER_SHA256
    audit.EXPECTED_MASTER_SHA256 = digest(master)
    try:
        payload = audit.audit_chain(
            now=pd.Timestamp("2026-07-19T01:30:00Z"),
            root=tmp_path,
            master_path=master,
            chain_dir=chain,
            verify_outputs=False,
        )
    finally:
        audit.EXPECTED_MASTER_SHA256 = original
    assert digest(first) == payload["chain_tail_sha256"]
    assert payload["status"] == "PASS"
    assert payload["missed_nodes"] == 1
    assert payload["prospective_oos_outcomes_read"] is False


def test_missing_due_node_blocks(tmp_path: Path) -> None:
    master = tmp_path / "master.json"
    write_master(master)
    chain = tmp_path / "chain"
    chain.mkdir()
    original = audit.EXPECTED_MASTER_SHA256
    audit.EXPECTED_MASTER_SHA256 = digest(master)
    try:
        payload = audit.audit_chain(
            now=pd.Timestamp("2026-07-19T01:30:00Z"),
            root=tmp_path,
            master_path=master,
            chain_dir=chain,
            verify_outputs=False,
        )
    finally:
        audit.EXPECTED_MASTER_SHA256 = original
    assert payload["status"] == "BLOCKED"
    assert payload["missing_due_nodes"] == 1
    assert "missing_due_chain_nodes:1" in payload["blockers"]


def test_missed_before_deadline_is_rejected(tmp_path: Path) -> None:
    master = tmp_path / "master.json"
    write_master(master)
    chain = tmp_path / "chain"
    chain.mkdir()
    write_missed_node(
        chain,
        decision_ts=pd.Timestamp("2026-07-19T00:00:00Z"),
        generated_at=pd.Timestamp("2026-07-19T01:20:00Z"),
        previous="0" * 64,
        master_sha256=digest(master),
    )
    original = audit.EXPECTED_MASTER_SHA256
    audit.EXPECTED_MASTER_SHA256 = digest(master)
    try:
        payload = audit.audit_chain(
            now=pd.Timestamp("2026-07-19T01:30:00Z"),
            root=tmp_path,
            master_path=master,
            chain_dir=chain,
            verify_outputs=False,
        )
    finally:
        audit.EXPECTED_MASTER_SHA256 = original
    assert payload["status"] == "BLOCKED"
    assert any(value.startswith("on_time_node_marked_missed") for value in payload["blockers"])
