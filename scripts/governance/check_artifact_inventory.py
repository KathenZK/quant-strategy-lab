#!/usr/bin/env python3
"""Report artifact budget and retention warnings without failing by default."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INVENTORY = (
    ROOT / "research" / "_artifact-inventory" / "artifact-inventory.json"
)
MAX_FILE_DETAIL_WARNINGS = 20
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "node_modules",
}


def current_artifact_totals(root: Path) -> tuple[int, int]:
    file_count = 0
    total_bytes = 0
    for current, directory_names, file_names in os.walk(root, followlinks=False):
        directory_names[:] = [
            name
            for name in directory_names
            if name not in SKIP_DIR_NAMES
            and not (Path(current) / name).is_symlink()
        ]
        if "artifacts" not in Path(current).relative_to(root).parts:
            continue
        for name in file_names:
            path = Path(current) / name
            if path.is_symlink():
                continue
            file_count += 1
            total_bytes += path.stat().st_size
    return file_count, total_bytes


def evaluate_inventory(
    inventory: dict[str, object],
    max_file_details: int = MAX_FILE_DETAIL_WARNINGS,
) -> list[str]:
    warnings: list[str] = []
    files = inventory.get("files", [])
    families = inventory.get("families", [])
    if not isinstance(files, list) or not isinstance(families, list):
        return ["清单格式错误：files 和 families 必须是数组"]

    for family in families:
        if not isinstance(family, dict):
            warnings.append("清单格式错误：families 含非对象条目")
            continue
        if family.get("budget_tier") != "A-normal":
            warnings.append(
                f"家族预算 {family.get('budget_tier')}: "
                f"{family.get('family_path')} ({family.get('total_bytes')} bytes)"
            )

    class_counts: dict[str, int] = {}
    class_bytes: dict[str, int] = {}
    over_budget_files: list[dict[str, object]] = []
    for row in files:
        if not isinstance(row, dict):
            warnings.append("清单格式错误：files 含非对象条目")
            continue
        size_bytes = int(row.get("size_bytes", 0))
        budget_tier = row.get("budget_tier", "A-normal")
        retention_class = str(
            row.get("retention_class", "retained-unclassified")
        )
        class_counts[retention_class] = class_counts.get(retention_class, 0) + 1
        class_bytes[retention_class] = (
            class_bytes.get(retention_class, 0) + size_bytes
        )
        if budget_tier != "A-normal":
            over_budget_files.append(row)

    over_budget_files.sort(
        key=lambda row: int(row.get("size_bytes", 0)), reverse=True
    )
    for row in over_budget_files[:max_file_details]:
        warnings.append(
            f"文件预算 {row.get('budget_tier')}: {row.get('path')} "
            f"({row.get('size_bytes')} bytes)"
        )
    omitted_count = len(over_budget_files) - max_file_details
    if omitted_count > 0:
        warnings.append(
            f"文件预算明细已截断：另有 {omitted_count} 个 B/C/D 级文件，见 JSON 清单"
        )

    for retention_class in ("regenerable-large", "scratch", "local-dataset"):
        count = class_counts.get(retention_class, 0)
        if count:
            warnings.append(
                f"保留复核 {retention_class}: {count} files, "
                f"{class_bytes[retention_class]} bytes"
            )
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Warn about artifact budget and retention-policy findings."
    )
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return exit code 1 when warnings exist; default always exits 0.",
    )
    args = parser.parse_args()
    if not args.inventory.is_file():
        if args.inventory.resolve() != DEFAULT_INVENTORY.resolve():
            print(f"ERROR: artifact inventory does not exist: {args.inventory}")
            return 1
        current_files, current_bytes = current_artifact_totals(ROOT)
        print(
            "Live artifact scan: "
            f"{current_files} files/{current_bytes} bytes. "
            "No persistent inventory snapshot is configured."
        )
        return 0
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    if args.inventory.resolve() == DEFAULT_INVENTORY.resolve():
        current_files, current_bytes = current_artifact_totals(ROOT)
        summary = inventory.get("summary", {})
        recorded_files = int(summary.get("file_count", 0))
        recorded_bytes = int(summary.get("total_bytes", 0))
        if (current_files, current_bytes) != (recorded_files, recorded_bytes):
            print(
                "WARNING: artifact inventory is stale; "
                f"recorded={recorded_files} files/{recorded_bytes} bytes, "
                f"current={current_files} files/{current_bytes} bytes. "
                "Regenerate the inventory before using its budget findings."
            )
            return 1 if args.strict else 0
    warnings = evaluate_inventory(inventory)
    if warnings:
        print("\n".join(f"WARNING: {warning}" for warning in warnings))
        print(
            f"{len(warnings)} warning(s); advisory only"
            + (" (strict mode enabled)" if args.strict else "")
        )
        return 1 if args.strict else 0
    print("artifact inventory check passed without warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
