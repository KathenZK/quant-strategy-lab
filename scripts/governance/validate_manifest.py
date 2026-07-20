#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

try:
    from .schema_utils import load_json, schema_errors
except ImportError:  # Direct script execution.
    from schema_utils import load_json, schema_errors

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/research-governance/machine/active-strategy-manifest.json"
DEFAULT_SCHEMA = ROOT / "docs/research-governance/schemas/active-strategy-manifest.schema.json"
GRANDFATHER_REGISTRY = (
    ROOT / "docs/research-governance/machine/external-runner-grandfathers.json"
)
GRANDFATHER_SCHEMA = (
    ROOT / "docs/research-governance/schemas/external-runner-grandfathers.schema.json"
)


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate(
    manifest_path: Path,
    runner_root: Path | None,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    data = load_json(manifest_path)
    errors = [
        f"schema: {error}" for error in schema_errors(data, schema_path)
    ]
    entries = data.get("entries")
    if not isinstance(entries, list):
        return errors

    seen: set[str] = set()
    status_by_strategy: dict[str, set[str]] = {}
    now = dt.datetime.now(dt.timezone.utc)
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        instance_id = entry.get("instance_id", "")
        if not instance_id or instance_id in seen:
            errors.append(f"duplicate or empty instance_id: {instance_id!r}")
        seen.add(instance_id)
        if entry.get("strategy_id") != entry.get("ledger_identity"):
            errors.append(f"{instance_id}: strategy_id != ledger_identity")
        status_by_strategy.setdefault(entry.get("strategy_id", ""), set()).add(
            entry.get("main_status", "")
        )
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
            else:
                try:
                    if parse_time(expires) <= now:
                        errors.append(f"{instance_id}: tiny live pilot approval expired")
                except (TypeError, ValueError):
                    pass
            if not entry.get("funding_boundary"):
                errors.append(f"{instance_id}: tiny live pilot needs funding_boundary")
        lab_spec_value = entry.get("lab_live_spec", "")
        lab_spec = ROOT / lab_spec_value
        if not lab_spec.is_file():
            errors.append(f"{instance_id}: missing lab spec {lab_spec}")
        decision_path = entry.get("decision_log_ref", "").split("#", 1)[0]
        if not (ROOT / decision_path).is_file():
            errors.append(f"{instance_id}: missing decision log {decision_path}")
        parity = entry.get("parity_gate", {})
        for field in ("last_pass_artifact", "pending_artifact", "narrative_report"):
            evidence = parity.get(field)
            if evidence and not (ROOT / evidence).is_file():
                errors.append(f"{instance_id}: missing {field} {evidence}")
        if (
            entry.get("enabled_allowed")
            and parity.get("required")
            and parity.get("status") != "PASS"
        ):
            until = parity.get("grandfather_until")
            try:
                valid_until = bool(until) and parse_time(until) > now
            except (TypeError, ValueError):
                valid_until = False
            if not valid_until:
                errors.append(f"{instance_id}: parity is not PASS and grandfather is absent/expired")
        if runner_root:
            runner_spec = runner_root / entry.get("runner_spec", "")
            if not runner_spec.is_file():
                errors.append(f"{instance_id}: missing runner spec {runner_spec}")
    for strategy_id, statuses in sorted(status_by_strategy.items()):
        if len(statuses) != 1:
            errors.append(
                f"{strategy_id}: one version has multiple main_status values {sorted(statuses)}"
            )
    grandfather_data = load_json(GRANDFATHER_REGISTRY)
    errors.extend(
        f"external grandfather schema: {error}"
        for error in schema_errors(grandfather_data, GRANDFATHER_SCHEMA)
    )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--runner-root", type=Path)
    args = parser.parse_args()
    errors = validate(args.manifest, args.runner_root, args.schema)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"validated {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
