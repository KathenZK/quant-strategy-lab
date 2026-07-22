from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Iterator


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator"
)
SCRIPT_DIR = FAMILY_DIR / "scripts"
LOCK_PATH = FAMILY_DIR / "artifacts/prospective_oos/working/cycle.lock"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one locked, outcome-blind prospective OOS signal cycle."
    )
    parser.add_argument("--sync-workers", type=int, default=12)
    parser.add_argument("--panel-workers", type=int, default=8)
    parser.add_argument("--lock-wait-seconds", type=float, default=0.0)
    parser.add_argument("--lock-poll-seconds", type=float, default=5.0)
    return parser.parse_args()


@contextmanager
def exclusive_cycle_lock(
    path: Path,
    *,
    wait_seconds: float,
    poll_seconds: float,
) -> Iterator[None]:
    if wait_seconds < 0:
        raise ValueError("wait_seconds must be non-negative")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be positive")
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    with path.open("a+", encoding="utf-8") as handle:
        while True:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"prospective cycle lock is busy: {path}")
                time.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def run_command(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command,
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=capture,
    )


def audit_chain() -> tuple[subprocess.CompletedProcess[str], dict[str, Any]]:
    result = run_command(
        [sys.executable, str(SCRIPT_DIR / "audit_blind_chain_health.py")],
        capture=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("blind-chain audit did not emit valid JSON") from exc
    return result, payload


def require_success(result: subprocess.CompletedProcess[str], *, step: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"prospective cycle step failed: {step}")


def has_only_missing_due_nodes_blocker(payload: dict[str, Any]) -> bool:
    blockers = payload.get("blockers")
    return (
        isinstance(blockers, list)
        and len(blockers) == 1
        and isinstance(blockers[0], str)
        and (
            blockers[0] == "missing_due_chain_nodes"
            or blockers[0].startswith("missing_due_chain_nodes:")
        )
    )


def run_cycle(*, sync_workers: int, panel_workers: int) -> str:
    initial_result, initial = audit_chain()
    if initial_result.returncode == 0 and initial.get("status") == "PASS":
        return "CHAIN_ALREADY_PASS"
    if not has_only_missing_due_nodes_blocker(initial):
        raise RuntimeError(
            "prospective cycle refused non-recoverable chain blockers: "
            f"{initial.get('blockers')}"
        )

    require_success(
        run_command(
            [
                sys.executable,
                str(SCRIPT_DIR / "run_prospective_feature_sync.py"),
                "--workers",
                str(sync_workers),
            ]
        ),
        step="feature sync",
    )
    require_success(
        run_command(
            [
                sys.executable,
                str(SCRIPT_DIR / "build_blind_prospective_panel.py"),
                "--workers",
                str(panel_workers),
            ]
        ),
        step="feature-only panel",
    )
    require_success(
        run_command(
            [sys.executable, str(SCRIPT_DIR / "collect_blind_prospective_signals.py")]
        ),
        step="blind collector",
    )
    final_result, final = audit_chain()
    require_success(final_result, step="post-cycle chain audit")
    if final.get("status") != "PASS":
        raise RuntimeError(f"post-cycle chain audit not PASS: {final.get('status')}")
    return "CYCLE_PASS"


def main() -> None:
    args = parse_args()
    with exclusive_cycle_lock(
        LOCK_PATH,
        wait_seconds=args.lock_wait_seconds,
        poll_seconds=args.lock_poll_seconds,
    ):
        status = run_cycle(
            sync_workers=args.sync_workers,
            panel_workers=args.panel_workers,
        )
    print(status, flush=True)


if __name__ == "__main__":
    main()
