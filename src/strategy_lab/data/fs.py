from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
import os
import tempfile

try:
    import fcntl
except ImportError:  # pragma: no cover - fcntl is unavailable on Windows.
    fcntl = None


@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(f".{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    try:
        if lock_path.exists() and lock_path.stat().st_size == 0:
            lock_path.unlink()
    except OSError:
        pass


def atomic_write_path(path: Path, writer: Callable[[Path], None]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            writer(temp_path)
            os.replace(temp_path, path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
    return path


def atomic_write_text(path: Path, contents: str, *, encoding: str = "utf-8") -> Path:
    return atomic_write_path(path, lambda temp_path: temp_path.write_text(contents, encoding=encoding))


def append_text_locked(path: Path, contents: str, *, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(path):
        with path.open("a", encoding=encoding) as handle:
            handle.write(contents)
    return path
