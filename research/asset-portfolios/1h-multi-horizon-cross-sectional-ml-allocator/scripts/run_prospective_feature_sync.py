from __future__ import annotations

from collections.abc import Callable
import hashlib
from http.client import IncompleteRead
from pathlib import Path
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
FAMILY_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sync_binance_usdm_prospective_features as frozen_sync  # noqa: E402


INCOMPLETE_READ_ATTEMPTS = 12
INITIAL_BACKOFF_SECONDS = 0.5
MAX_BACKOFF_SECONDS = 10.0
MASTER_FREEZE_PATH = (
    FAMILY_DIR / "artifacts/freeze/bin-1h-mhcsml-v1-freeze-r4.json"
)
MASTER_FREEZE_SHA256 = (
    "64ee12688980673aa2cd348a961553c89d246d1f338eba0192ddcbfdd095fe11"
)
FROZEN_SYNC_PATH = SCRIPT_DIR / "sync_binance_usdm_prospective_features.py"
FROZEN_SYNC_SHA256 = (
    "9ae92d6bffb634ac8976567a7bf7a2bce72518160e2468f233cc892e94ace62a"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(
            f"frozen input SHA256 mismatch for {path}: expected {expected}, got {actual}"
        )


def verify_frozen_inputs() -> None:
    require_sha256(MASTER_FREEZE_PATH, MASTER_FREEZE_SHA256)
    require_sha256(FROZEN_SYNC_PATH, FROZEN_SYNC_SHA256)


def with_incomplete_read_retry(
    request_json: Callable[..., Any],
    *,
    attempts: int = INCOMPLETE_READ_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> Callable[..., Any]:
    """Retry only truncated HTTP responses around the frozen request function."""
    if attempts < 1:
        raise ValueError("attempts must be positive")

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        for attempt in range(attempts):
            try:
                return request_json(*args, **kwargs)
            except IncompleteRead:
                if attempt + 1 >= attempts:
                    raise
                delay = min(
                    MAX_BACKOFF_SECONDS,
                    INITIAL_BACKOFF_SECONDS * (2**attempt),
                )
                print(
                    "prospective feature request was truncated; "
                    f"retrying {attempt + 2}/{attempts} after {delay:.1f}s",
                    file=sys.stderr,
                    flush=True,
                )
                sleep(delay)
        raise AssertionError("unreachable")

    return wrapped


def main() -> None:
    verify_frozen_inputs()
    frozen_sync.base.request_json = with_incomplete_read_retry(
        frozen_sync.base.request_json
    )
    frozen_sync.main()


if __name__ == "__main__":
    main()
