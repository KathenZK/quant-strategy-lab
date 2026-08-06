from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


GOVERNANCE_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "governance"


def _load_script_module(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, GOVERNANCE_SCRIPTS / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_artifact_inventory = _load_script_module("check_artifact_inventory")
inventory_artifacts = _load_script_module("inventory_artifacts")


def _write_sparse(path: Path, size_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.seek(size_bytes - 1)
        handle.write(b"\0")


def test_inventory_uses_metadata_and_external_markdown_references(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "research" / "demo" / "family" / "artifacts"
    artifact_dir.mkdir(parents=True)
    evidence = artifact_dir / "evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    # Invalid UTF-8 proves artifact Markdown content is not scanned for references.
    (artifact_dir / "README.md").write_bytes(b"\xff\xfe")
    large = artifact_dir / "training-matrix.csv"
    _write_sparse(large, inventory_artifacts.FILE_REVIEW_BYTES + 1)
    scratch = artifact_dir / "scratch" / "trial.json"
    scratch.parent.mkdir()
    scratch.write_text("{}\n", encoding="utf-8")

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "report.md").write_text(
        "[evidence](../research/demo/family/artifacts/evidence.json)\n",
        encoding="utf-8",
    )

    inventory = inventory_artifacts.build_inventory(
        tmp_path, generated_at="2026-07-20T00:00:00+00:00"
    )

    assert inventory["summary"] == {
        "artifact_root_count": 1,
        "family_count": 1,
        "file_count": 4,
        "total_bytes": inventory_artifacts.FILE_REVIEW_BYTES + 9,
        "referenced_file_count": 1,
        "reference_coverage_pct": 25.0,
    }
    family = inventory["families"][0]
    assert family["family_path"] == "research/demo/family"
    assert family["max_file"]["path"].endswith("training-matrix.csv")
    assert family["reference_coverage_pct"] == 25.0

    rows = {row["path"]: row for row in inventory["files"]}
    assert rows["research/demo/family/artifacts/evidence.json"]["referenced_by"] == [
        "docs/report.md"
    ]
    assert (
        rows["research/demo/family/artifacts/evidence.json"]["retention_class"]
        == "normative-evidence"
    )
    assert (
        rows["research/demo/family/artifacts/training-matrix.csv"][
            "retention_class"
        ]
        == "regenerable-large"
    )
    assert (
        rows["research/demo/family/artifacts/scratch/trial.json"][
            "retention_class"
        ]
        == "scratch"
    )


def test_markdown_summary_omits_full_file_listing(tmp_path: Path) -> None:
    artifact = tmp_path / "research" / "demo" / "artifacts" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}\n", encoding="utf-8")
    inventory = inventory_artifacts.build_inventory(
        tmp_path, generated_at="2026-07-20T00:00:00+00:00"
    )

    markdown = inventory_artifacts.render_markdown(
        inventory, "artifact-inventory.json"
    )

    assert "逐文件机器明细" in markdown
    assert "## 家族/主题汇总" in markdown
    assert "## 逐文件" not in markdown


def test_current_artifact_totals_reads_live_filesystem(tmp_path: Path) -> None:
    first = tmp_path / "research" / "demo" / "artifacts" / "first.json"
    second = tmp_path / "archive" / "demo" / "artifacts" / "second.csv"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_bytes(b"123")
    second.write_bytes(b"4567")

    assert check_artifact_inventory.current_artifact_totals(tmp_path) == (2, 7)


def test_checker_uses_live_scan_when_snapshot_is_absent(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    artifact = tmp_path / "research" / "demo" / "artifacts" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"123")
    missing = tmp_path / "missing-inventory.json"
    monkeypatch.setattr(check_artifact_inventory, "ROOT", tmp_path)
    monkeypatch.setattr(check_artifact_inventory, "DEFAULT_INVENTORY", missing)
    monkeypatch.setattr(sys, "argv", ["check_artifact_inventory.py"])

    assert check_artifact_inventory.main() == 0
    assert "Live artifact scan: 1 files/3 bytes" in capsys.readouterr().out


def test_checker_is_advisory_unless_strict(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(
            {
                "families": [
                    {
                        "family_path": "research/demo",
                        "total_bytes": 600 * 1024 * 1024,
                        "budget_tier": "C-externalize",
                    }
                ],
                "files": [
                    {
                        "path": "research/demo/artifacts/matrix.csv",
                        "size_bytes": 60 * 1024 * 1024,
                        "budget_tier": "C-externalize",
                        "retention_class": "regenerable-large",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys, "argv", ["check_artifact_inventory.py", "--inventory", str(inventory_path)]
    )
    assert check_artifact_inventory.main() == 0
    assert "advisory only" in capsys.readouterr().out

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_artifact_inventory.py",
            "--inventory",
            str(inventory_path),
            "--strict",
        ],
    )
    assert check_artifact_inventory.main() == 1
    assert "strict mode enabled" in capsys.readouterr().out
