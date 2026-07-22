from __future__ import annotations

from http.client import IncompleteRead
import hashlib
import importlib.util
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / (
    "research/asset-portfolios/1h-multi-horizon-cross-sectional-ml-allocator/"
    "scripts/run_prospective_feature_sync.py"
)


def load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("mhcsml_sync_runner", RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load prospective sync runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_retries_incomplete_read_without_changing_arguments() -> None:
    runner = load_runner()
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    delays: list[float] = []

    def request(*args: Any, **kwargs: Any) -> dict[str, bool]:
        calls.append((args, kwargs))
        if len(calls) < 3:
            raise IncompleteRead(b"partial", 10)
        return {"ok": True}

    wrapped = runner.with_incomplete_read_retry(
        request,
        attempts=4,
        sleep=delays.append,
    )

    assert wrapped("/fapi/v1/klines", symbol="BEAMXUSDT") == {"ok": True}
    assert calls == [
        (("/fapi/v1/klines",), {"symbol": "BEAMXUSDT"}),
        (("/fapi/v1/klines",), {"symbol": "BEAMXUSDT"}),
        (("/fapi/v1/klines",), {"symbol": "BEAMXUSDT"}),
    ]
    assert delays == [0.5, 1.0]


def test_reraises_after_retry_budget() -> None:
    runner = load_runner()
    calls = 0

    def request() -> None:
        nonlocal calls
        calls += 1
        raise IncompleteRead(b"partial", 1)

    wrapped = runner.with_incomplete_read_retry(
        request,
        attempts=3,
        sleep=lambda _: None,
    )

    with pytest.raises(IncompleteRead):
        wrapped()
    assert calls == 3


def test_does_not_retry_unrelated_errors() -> None:
    runner = load_runner()
    calls = 0

    def request() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("original fail-closed error")

    wrapped = runner.with_incomplete_read_retry(
        request,
        attempts=3,
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="original fail-closed error"):
        wrapped()
    assert calls == 1


def test_frozen_input_hash_guard_accepts_exact_bytes(tmp_path: Path) -> None:
    runner = load_runner()
    path = tmp_path / "frozen-input"
    payload = b"exact frozen bytes"
    path.write_bytes(payload)

    runner.require_sha256(path, hashlib.sha256(payload).hexdigest())


def test_frozen_input_hash_guard_fails_closed(tmp_path: Path) -> None:
    runner = load_runner()
    path = tmp_path / "frozen-input"
    path.write_bytes(b"changed")

    with pytest.raises(RuntimeError, match="frozen input SHA256 mismatch"):
        runner.require_sha256(path, "0" * 64)
