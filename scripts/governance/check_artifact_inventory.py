#!/usr/bin/env python3
"""Evaluate the live artifact inventory in memory against repository budgets."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Protocol, cast


class _InventoryBuilder(Protocol):
    def __call__(
        self, root: Path, generated_at: str | None = None
    ) -> dict[str, object]: ...


def _load_inventory_builder() -> _InventoryBuilder:
    module_path = Path(__file__).with_name("inventory_artifacts.py")
    spec = importlib.util.spec_from_file_location("artifact_inventory_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load artifact inventory module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(_InventoryBuilder, module.build_inventory)


build_inventory = _load_inventory_builder()


ROOT = Path(__file__).resolve().parents[2]
MAX_FILE_DETAILS = 20
WARNING_TIER = "B-review"
FAILURE_TIERS = {"C-externalize", "D-prohibited-new-git"}
RETENTION_WARNING_CLASSES = (
    "regenerable-large",
    "scratch",
    "local-dataset",
)


def evaluate_inventory(
    inventory: dict[str, object],
    max_file_details: int = MAX_FILE_DETAILS,
) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    failures: list[str] = []
    files = inventory.get("files", [])
    families = inventory.get("families", [])
    if not isinstance(files, list) or not isinstance(families, list):
        return [], ["清单格式错误：files 和 families 必须是数组"]

    for family in families:
        if not isinstance(family, dict):
            failures.append("清单格式错误：families 含非对象条目")
            continue
        budget_tier = str(family.get("budget_tier", "A-normal"))
        message = (
            f"家族预算 {budget_tier}: {family.get('family_path')} "
            f"({family.get('total_bytes')} bytes)"
        )
        if budget_tier == WARNING_TIER:
            warnings.append(message)
        elif budget_tier in FAILURE_TIERS:
            failures.append(message)
        elif budget_tier != "A-normal":
            failures.append(f"未知预算级别：{message}")

    class_counts: dict[str, int] = {}
    class_bytes: dict[str, int] = {}
    review_files: list[dict[str, object]] = []
    rejected_files: list[dict[str, object]] = []
    for row in files:
        if not isinstance(row, dict):
            failures.append("清单格式错误：files 含非对象条目")
            continue
        size_bytes = int(row.get("size_bytes", 0))
        budget_tier = str(row.get("budget_tier", "A-normal"))
        retention_class = str(
            row.get("retention_class", "retained-unclassified")
        )
        class_counts[retention_class] = class_counts.get(retention_class, 0) + 1
        class_bytes[retention_class] = (
            class_bytes.get(retention_class, 0) + size_bytes
        )
        if budget_tier == WARNING_TIER:
            review_files.append(row)
        elif budget_tier in FAILURE_TIERS:
            rejected_files.append(row)
        elif budget_tier != "A-normal":
            failures.append(
                f"未知文件预算级别 {budget_tier}: {row.get('path')}"
            )

    for rows, findings in (
        (review_files, warnings),
        (rejected_files, failures),
    ):
        rows.sort(key=lambda row: int(row.get("size_bytes", 0)), reverse=True)
        for row in rows[:max_file_details]:
            findings.append(
                f"文件预算 {row.get('budget_tier')}: {row.get('path')} "
                f"({row.get('size_bytes')} bytes)"
            )
        omitted_count = len(rows) - max_file_details
        if omitted_count > 0:
            findings.append(
                f"文件预算明细已截断：另有 {omitted_count} 个同级发现；"
                "运行 inventory_artifacts.py 导出完整人工清单"
            )

    for retention_class in RETENTION_WARNING_CLASSES:
        count = class_counts.get(retention_class, 0)
        if count:
            warnings.append(
                f"保留复核 {retention_class}: {count} files, "
                f"{class_bytes[retention_class]} bytes"
            )
    return warnings, failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate the current artifact tree without a persisted snapshot."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--max-file-details",
        type=int,
        default=MAX_FILE_DETAILS,
        help="Maximum B-tier and C/D-tier file details printed per severity.",
    )
    args = parser.parse_args()
    if args.max_file_details < 0:
        parser.error("--max-file-details must be non-negative")

    inventory = build_inventory(args.root)
    summary = inventory["summary"]
    assert isinstance(summary, dict)
    print(
        "Live artifact inventory: "
        f"{summary['file_count']} files/{summary['total_bytes']} bytes across "
        f"{summary['family_count']} families; no snapshot written."
    )
    warnings, failures = evaluate_inventory(
        inventory, max_file_details=args.max_file_details
    )
    if warnings:
        print("\n".join(f"WARNING: {warning}" for warning in warnings))
    if failures:
        print("\n".join(f"ERROR: {failure}" for failure in failures))
        print(
            f"Artifact budget check failed with {len(failures)} blocking "
            "finding(s). Run inventory_artifacts.py for manual JSON/Markdown "
            "inventory output."
        )
        return 1
    if warnings:
        print(f"Artifact budget check passed with {len(warnings)} warning(s).")
    else:
        print("Artifact budget check passed without findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
