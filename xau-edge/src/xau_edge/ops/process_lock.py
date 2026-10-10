"""Single-writer ownership of a directory (the paper desk's ``data/trade``).

A thread lock protects one process only. The desk persists money-like state (a simulated account,
an open position, a journal), so exactly ONE process may write it. Ownership is an operating-system
lock on a file, held for the life of the process:

* it is released by the OS when the owner exits OR crashes (no stale lock can survive a dead owner,
  and no clock or PID-reuse guess is involved);
* two processes racing to start are arbitrated by the OS, not by a check-then-create;
* the owner writes ``{pid, started_at, role, code_version}`` into the file so a refused process
  can say WHO holds it; metadata left by a dead owner is reported as a recovered stale owner.

The lock byte lives far from the metadata (Windows byte-range locks are mandatory, so a refused
process must still be able to read the metadata).
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

LOCK_OFFSET = 1 << 20
"""Byte offset of the locked region, well past the metadata."""
META_LIMIT = 4096


class WriterLockError(RuntimeError):
    """Another process owns the directory."""

    def __init__(self, path: Path, owner: dict[str, Any] | None) -> None:
        self.path = path
        self.owner = owner
        who = "an unknown process" if not owner else f"pid {owner.get('pid')} ({owner.get('role')})"
        super().__init__(f"{path} is owned by {who}; only one process may write it")


@dataclass(frozen=True)
class Acquired:
    """The lock is ours; ``stale_owner`` is the dead previous owner (its metadata), if any."""

    stale_owner: dict[str, Any] | None


def _lock_region(handle: int | Any, *, release: bool = False) -> None:
    if sys.platform == "win32":
        import msvcrt  # noqa: PLC0415 - Windows only

        os.lseek(handle, LOCK_OFFSET, os.SEEK_SET)
        msvcrt.locking(handle, msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined,unused-ignore]
    else:
        import fcntl  # noqa: PLC0415 - POSIX only

        mode = fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB  # type: ignore[attr-defined,unused-ignore]
        fcntl.flock(handle, mode)  # type: ignore[attr-defined,unused-ignore]


class WriterLock:
    """Exclusive, crash-safe ownership of ``path`` (a small lock file)."""

    def __init__(
        self, path: Path | str, *, role: str = "trade-engine", code_version: str = ""
    ) -> None:
        self.path = Path(path)
        self.role = role
        self.code_version = code_version
        self._fd: int | None = None

    # ---- inspection ------------------------------------------------------------------------

    def owner(self) -> dict[str, Any] | None:
        """The metadata the last owner wrote (it may belong to a dead process)."""
        try:
            raw = self.path.read_bytes()[:META_LIMIT].split(b"\0", 1)[0]
            value = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    @property
    def held(self) -> bool:
        return self._fd is not None

    # ---- ownership -------------------------------------------------------------------------

    def acquire(self) -> Acquired:
        """Take ownership or raise ``WriterLockError`` (never blocks)."""
        if self._fd is not None:
            return Acquired(None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0))
        try:
            _lock_region(fd)
        except OSError as exc:
            os.close(fd)
            raise WriterLockError(self.path, self.owner()) from exc
        # the lock was free, so whoever wrote the metadata is gone: report it as a stale owner
        previous = self.owner()
        stale = previous if previous and previous.get("pid") != os.getpid() else None
        meta = {
            "pid": os.getpid(),
            "role": self.role,
            "host": socket.gethostname(),
            "started_at": datetime.now(UTC).isoformat(),
            "code_version": self.code_version,
        }
        os.lseek(fd, 0, os.SEEK_SET)
        payload = json.dumps(meta).encode("utf-8")
        os.write(fd, payload + b"\0" * max(0, META_LIMIT - len(payload)))
        self._fd = fd
        return Acquired(stale)

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        with contextlib.suppress(OSError):  # the OS drops it when the descriptor closes anyway
            _lock_region(fd, release=True)
        os.close(fd)

    def __enter__(self) -> WriterLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()
