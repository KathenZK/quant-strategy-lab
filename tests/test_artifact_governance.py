from __future__ import annotations

import importlib.util
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
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


inventory_artifacts = _load_script_module("inventory_artifacts")
check_artifact_inventory = _load_script_module("check_artifact_inventory")


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


def test_checker_builds_live_inventory_without_writing_snapshot(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    artifact = tmp_path / "research" / "demo" / "artifacts" / "result.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"123")
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_artifact_inventory.py", "--root", str(tmp_path)],
    )

    assert check_artifact_inventory.main() == 0
    output = capsys.readouterr().out
    assert "Live artifact inventory: 1 files/3 bytes" in output
    assert "no snapshot written" in output
    assert not (tmp_path / "research" / "_artifact-inventory").exists()


def test_checker_warns_for_b_review_and_passes(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    artifact = tmp_path / "research" / "demo" / "artifacts" / "matrix.csv"
    _write_sparse(artifact, inventory_artifacts.FILE_REVIEW_BYTES + 1)
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_artifact_inventory.py", "--root", str(tmp_path)],
    )

    assert check_artifact_inventory.main() == 0
    output = capsys.readouterr().out
    assert "WARNING: 文件预算 B-review" in output
    assert "passed with" in output


def test_checker_fails_for_c_and_d_files(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    artifact_dir = tmp_path / "research" / "demo" / "artifacts"
    _write_sparse(
        artifact_dir / "externalize.csv",
        inventory_artifacts.FILE_EXTERNALIZE_BYTES + 1,
    )
    _write_sparse(
        artifact_dir / "prohibited.csv",
        inventory_artifacts.FILE_GIT_PROHIBITED_BYTES + 1,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_artifact_inventory.py",
            "--root",
            str(tmp_path),
        ],
    )

    assert check_artifact_inventory.main() == 1
    output = capsys.readouterr().out
    assert "ERROR: 文件预算 C-externalize" in output
    assert "ERROR: 文件预算 D-prohibited-new-git" in output
