#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/research-governance/machine/active-strategy-manifest.yaml"


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate(manifest_path: Path, runner_root: Path | None) -> list[str]:
    data = json.loads(manifest_path.read_text())
    errors: list[str] = []
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be 1.0")
    entries = data.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be an array"]

    seen: set[str] = set()
    now = dt.datetime.now(dt.timezone.utc)
    for entry in entries:
        instance_id = entry.get("instance_id", "")
        if not instance_id or instance_id in seen:
            errors.append(f"duplicate or empty instance_id: {instance_id!r}")
        seen.add(instance_id)
        if entry.get("strategy_id") != entry.get("ledger_identity"):
            errors.append(f"{instance_id}: strategy_id != ledger_identity")
        mode = entry.get("mode")
        approval = entry.get("approval_level")
        if entry.get("enabled_allowed"):
            allowed = approval in ({"dry_run"} if mode == "dry_run" else {"tiny_live_pilot", "live"})
            if not allowed:
                errors.append(f"{instance_id}: enabled_allowed conflicts with approval_level")
        if mode == "live" and approval == "tiny_live_pilot":
            expires = entry.get("approval_expires_at")
            if not expires:
                errors.append(f"{instance_id}: tiny live pilot needs approval_expires_at")
            elif parse_time(expires) <= now:
                errors.append(f"{instance_id}: tiny live pilot approval expired")
            if not entry.get("funding_boundary"):
                errors.append(f"{instance_id}: tiny live pilot needs funding_boundary")
        lab_spec = ROOT / entry.get("lab_live_spec", "")
        if not lab_spec.is_file():
            errors.append(f"{instance_id}: missing lab spec {lab_spec}")
        decision_path = entry.get("decision_log_ref", "").split("#", 1)[0]
        if not (ROOT / decision_path).is_file():
            errors.append(f"{instance_id}: missing decision log {decision_path}")
        parity = entry.get("parity_gate", {})
        if (
            entry.get("enabled_allowed")
            and parity.get("required")
            and parity.get("status") != "PASS"
        ):
            until = parity.get("grandfather_until")
            if not until or parse_time(until) <= now:
                errors.append(f"{instance_id}: parity is not PASS and grandfather is absent/expired")
        if runner_root:
            runner_spec = runner_root / entry.get("runner_spec", "")
            if not runner_spec.is_file():
                errors.append(f"{instance_id}: missing runner spec {runner_spec}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runner-root", type=Path)
    args = parser.parse_args()
    errors = validate(args.manifest, args.runner_root)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"validated {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
