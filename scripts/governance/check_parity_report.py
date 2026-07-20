#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

try:
    from .schema_utils import load_json, schema_errors
except ImportError:  # Direct script execution.
    from schema_utils import load_json, schema_errors

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/research-governance/machine/active-strategy-manifest.json"
DEFAULT_SCHEMA = ROOT / "docs/research-governance/schemas/parity-report.schema.json"


def _discover_from_manifest(
    manifest_path: Path,
) -> tuple[dict[Path, list[dict]], list[str]]:
    manifest = load_json(manifest_path)
    discovered: dict[Path, list[dict]] = {}
    errors: list[str] = []
    for entry in manifest.get("entries", []):
        parity = entry.get("parity_gate", {})
        status = parity.get("status")
        field = "last_pass_artifact" if status == "PASS" else "pending_artifact"
        artifact = parity.get(field)
        if parity.get("required") and status in {"PASS", "PENDING"} and not artifact:
            errors.append(f"{entry.get('instance_id')}: {status} requires {field}")
            continue
        if artifact:
            path = ROOT / artifact
            discovered.setdefault(path, []).append(entry)
    return discovered, errors


def _validate_report(
    path: Path,
    schema_path: Path,
    references: list[dict],
) -> list[str]:
    if path.suffix.lower() != ".json":
        return [f"{path}: parity evidence must be a standardized JSON artifact"]
    if not path.is_file():
        return [f"{path}: parity artifact does not exist"]
    report = load_json(path)
    errors = [f"{path}: schema: {error}" for error in schema_errors(report, schema_path)]
    trade_path = report.get("trade_path", {})
    if report.get("conclusion") == "PASS":
        if trade_path.get("reference_trades") != trade_path.get("runtime_trades"):
            errors.append(f"{path}: PASS report trade counts differ")
    for entry in references:
        instance_id = entry.get("instance_id")
        if report.get("strategy_id") != entry.get("strategy_id"):
            errors.append(f"{path}: strategy_id does not match {instance_id}")
        if report.get("runner_kind") != entry.get("runner_kind"):
            errors.append(f"{path}: runner_kind does not match {instance_id}")
        expected = entry.get("parity_gate", {}).get("status")
        if expected == "PASS" and report.get("conclusion") != "PASS":
            errors.append(f"{path}: manifest PASS points to non-PASS artifact")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reports", nargs="*", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    discovered, errors = _discover_from_manifest(args.manifest)
    for path in args.reports:
        resolved = path if path.is_absolute() else ROOT / path
        discovered.setdefault(resolved, [])
    for path, references in sorted(discovered.items(), key=lambda item: str(item[0])):
        errors.extend(_validate_report(path, args.schema, references))
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"validated {len(discovered)} parity reports discovered from manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
