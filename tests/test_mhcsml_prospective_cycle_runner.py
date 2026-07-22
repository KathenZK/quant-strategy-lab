from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/run_blind_prospective_cycle.py"
)


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("mhcsml_cycle_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load prospective cycle runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed(returncode: int, payload: dict[str, Any] | None = None) -> Any:
    stdout = json.dumps(payload) if payload is not None else ""
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def test_skips_work_when_chain_is_already_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = load_runner()
    calls: list[tuple[list[str], bool]] = []

    def fake_run(command: list[str], *, capture: bool = False) -> Any:
        calls.append((command, capture))
        return completed(0, {"status": "PASS", "blockers": []})

    monkeypatch.setattr(runner, "run_command", fake_run)

    assert runner.run_cycle(sync_workers=12, panel_workers=8) == "CHAIN_ALREADY_PASS"
    assert len(calls) == 1
    assert calls[0][0][-1].endswith("audit_blind_chain_health.py")


def test_runs_only_for_missing_due_nodes(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = load_runner()
    calls: list[list[str]] = []
    audit_count = 0

    def fake_run(command: list[str], *, capture: bool = False) -> Any:
        nonlocal audit_count
        calls.append(command)
        if command[-1].endswith("audit_blind_chain_health.py"):
            audit_count += 1
            if audit_count == 1:
                return completed(
                    1,
                    {"status": "BLOCKED", "blockers": ["missing_due_chain_nodes:1"]},
                )
            return completed(0, {"status": "PASS", "blockers": []})
        return completed(0)

    monkeypatch.setattr(runner, "run_command", fake_run)

    assert runner.run_cycle(sync_workers=7, panel_workers=3) == "CYCLE_PASS"
    assert [Path(command[1]).name for command in calls] == [
        "audit_blind_chain_health.py",
        "run_prospective_feature_sync.py",
        "build_blind_prospective_panel.py",
        "collect_blind_prospective_signals.py",
        "audit_blind_chain_health.py",
    ]
    assert calls[1][-2:] == ["--workers", "7"]
    assert calls[2][-2:] == ["--workers", "3"]


def test_refuses_any_other_chain_blocker(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = load_runner()

    monkeypatch.setattr(
        runner,
        "run_command",
        lambda command, capture=False: completed(
            1,
            {"status": "BLOCKED", "blockers": ["master_freeze_sha_mismatch"]},
        ),
    )

    with pytest.raises(RuntimeError, match="non-recoverable chain blockers"):
        runner.run_cycle(sync_workers=12, panel_workers=8)


def test_stops_after_failed_pipeline_step(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = load_runner()
    calls = 0

    def fake_run(command: list[str], *, capture: bool = False) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            return completed(
                1,
                {"status": "BLOCKED", "blockers": ["missing_due_chain_nodes:1"]},
            )
        return completed(2)

    monkeypatch.setattr(runner, "run_command", fake_run)

    with pytest.raises(RuntimeError, match="feature sync"):
        runner.run_cycle(sync_workers=12, panel_workers=8)
    assert calls == 2


@pytest.mark.parametrize(
    ("blockers", "expected"),
    [
        (["missing_due_chain_nodes"], True),
        (["missing_due_chain_nodes:1"], True),
        (["missing_due_chain_nodes:17"], True),
        (["missing_due_chain_nodes:1", "master_freeze_sha_mismatch"], False),
        (["missing_due_chain_nodes_extra:1"], False),
        ([], False),
        ("missing_due_chain_nodes:1", False),
    ],
)
def test_missing_due_blocker_matching(blockers: Any, expected: bool) -> None:
    runner = load_runner()

    assert runner.has_only_missing_due_nodes_blocker({"blockers": blockers}) is expected
