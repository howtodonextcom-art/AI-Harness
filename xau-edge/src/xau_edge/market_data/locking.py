"""Cross-process advisory lock for ledger writes (create-exclusive lock file, stale-safe).

The collector and a backfill may run at the same time and touch the same partition; a write is a
read-merge-replace, so two writers could lose each other's rows without this. The lock is held only
for the short merge, and a lock file older than ``stale_seconds`` (a crashed writer) is removed.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class LockTimeoutError(RuntimeError):
    """The lock could not be acquired in time."""


@contextmanager
def file_lock(
    path: Path, *, timeout: float = 120.0, stale_seconds: float = 300.0, poll: float = 0.05
) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except (FileExistsError, PermissionError):  # Windows: a file mid-delete denies access
            try:
                if time.time() - path.stat().st_mtime > stale_seconds:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                time.sleep(poll)
                continue
            if time.monotonic() > deadline:
                msg = f"could not acquire {path.name} within {timeout:.0f}s"
                raise LockTimeoutError(msg) from None
            time.sleep(poll)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)
