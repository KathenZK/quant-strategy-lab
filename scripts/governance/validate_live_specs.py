#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

try:
    from .schema_utils import schema_errors
except ImportError:  # Direct script execution.
    from schema_utils import schema_errors


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = (
    ROOT / "docs/research-governance/schemas/lab-live-spec-frontmatter.schema.json"
)


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
    schema_path: Path = DEFAULT_SCHEMA,
) -> list[str]:
    errors: list[str] = []
    active_pairs: dict[tuple[str, str], Path] = {}
    declared_specs = 0
    paths = sorted((ROOT / "research").glob("**/live-specs/**/*.md"))
    for path in paths:
        frontmatter, parse_error = read_frontmatter(path)
        if parse_error:
            continue
        if frontmatter.get("spec_role") != "lab_handoff":
            continue
        if frontmatter.get("spec_status") == "superseded":
            continue
        declared_specs += 1
        errors.extend(f"{path}: schema: {error}" for error in schema_errors(frontmatter, schema_path))
        pairs = implementation_pairs(frontmatter)
        if len(pairs) != len(frontmatter.get("implementations", pairs)):
            errors.append(f"{path}: duplicate strategy_id/runner_kind implementation mapping")
        if frontmatter.get("spec_status") == "active":
            for pair in pairs:
                previous = active_pairs.get(pair)
                if previous and previous != path:
                    errors.append(f"{path}: active mapping {pair} duplicates {previous}")
                active_pairs[pair] = path
    if declared_specs == 0:
        errors.append("no Lab handoff specs declared with spec_role=lab_handoff")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    errors = validate(args.schema)
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print("validated declared Lab handoff specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
