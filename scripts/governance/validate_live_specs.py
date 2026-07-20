#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

try:
    from .schema_utils import load_json, schema_errors
except ImportError:  # Direct script execution.
    from schema_utils import load_json, schema_errors


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "docs/research-governance/machine/active-strategy-manifest.json"
DEFAULT_SCHEMA = (
    ROOT / "docs/research-governance/schemas/lab-live-spec-frontmatter.schema.json"
)
APPROVAL_RANK = {"none": 0, "dry_run": 1, "tiny_live_pilot": 2, "live": 3}


def read_frontmatter(path: Path) -> tuple[dict[str, Any], str | None]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "missing YAML front matter"
    try:
        end = lines.index("---", 1)
    except ValueError:
        return {}, "unterminated YAML front matter"
    data = yaml.safe_load("\n".join(lines[1:end]))
    if not isinstance(data, dict):
        return {}, "front matter must be a mapping"
    return data, None


def implementation_pairs(frontmatter: dict[str, Any]) -> set[tuple[str, str]]:
    if "implementations" in frontmatter:
        return {
            (item.get("strategy_id", ""), item.get("runner_kind", ""))
            for item in frontmatter.get("implementations", [])
            if isinstance(item, dict)
        }
    return {(frontmatter.get("strategy_id", ""), frontmatter.get("runner_kind", ""))}


def validate(
    manifest_path: Path = DEFAULT_MANIFEST,
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    manifest = load_json(manifest_path)
    by_spec: dict[Path, list[dict[str, Any]]] = {}
    for entry in manifest.get("entries", []):
        path = ROOT / entry.get("lab_live_spec", "")
        by_spec.setdefault(path, []).append(entry)

    errors: list[str] = []
    active_pairs: dict[tuple[str, str], Path] = {}
    for path, entries in sorted(by_spec.items(), key=lambda item: str(item[0])):
        if not path.is_file():
            errors.append(f"{path}: referenced live spec does not exist")
            continue
        frontmatter, parse_error = read_frontmatter(path)
        if parse_error:
            errors.append(f"{path}: {parse_error}")
            continue
        errors.extend(f"{path}: schema: {error}" for error in schema_errors(frontmatter, schema_path))
        pairs = implementation_pairs(frontmatter)
        if len(pairs) != len(frontmatter.get("implementations", pairs)):
            errors.append(f"{path}: duplicate strategy_id/runner_kind implementation mapping")
        instance_ids = set(frontmatter.get("manifest_instance_ids", []))
        for entry in entries:
            instance_id = entry.get("instance_id")
            pair = (entry.get("strategy_id"), entry.get("runner_kind"))
            if pair not in pairs:
                errors.append(f"{path}: missing manifest mapping {pair} for {instance_id}")
            if instance_id not in instance_ids:
                errors.append(f"{path}: manifest_instance_ids missing {instance_id}")
            if frontmatter.get("family_id") != entry.get("family_id"):
                errors.append(f"{path}: family_id does not match {instance_id}")
            if frontmatter.get("main_status") != entry.get("main_status"):
                errors.append(f"{path}: main_status does not match {instance_id}")
            if entry.get("enabled_allowed") and frontmatter.get("spec_status") != "active":
                errors.append(f"{path}: enabled instance {instance_id} requires active spec")
            maximum = APPROVAL_RANK.get(frontmatter.get("approval_level_max"), -1)
            requested = APPROVAL_RANK.get(entry.get("approval_level"), -1)
            if requested > maximum:
                errors.append(f"{path}: {instance_id} exceeds approval_level_max")
        if frontmatter.get("spec_status") == "active":
            for pair in pairs:
                previous = active_pairs.get(pair)
                if previous and previous != path:
                    errors.append(f"{path}: active mapping {pair} duplicates {previous}")
                active_pairs[pair] = path
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    errors = validate(args.manifest, args.schema)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("validated manifest-referenced Lab live specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
