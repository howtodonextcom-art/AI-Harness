"""Copies of the daily backup on other places, verified before they count.

A mirror copy is accepted only when (1) it was written under a temporary name and renamed, (2) its
bytes are identical to the source backup (sha256), and (3) SQLite opens it and reports it sound.
Old copies are rotated per mirror. A failing mirror is recorded (never raised): the engine keeps
running and ``/health`` says which mirror is behind. A mirror on another PARTITION of the same disk
guards against deletion and corruption but not against the disk dying; only ``offdevice`` mirrors
(another device or a synced cloud folder) count as an off-device copy.
"""

from __future__ import annotations

import contextlib
import hashlib
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class MirrorState:
    path: Path
    offdevice: bool
    last_ok: datetime | None = None
    last_attempt: datetime | None = None
    last_error: str | None = None
    last_file: str | None = None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_verified(source: Path, folder: Path, keep: int) -> Path:
    """Copy ``source`` into ``folder`` (atomic rename), verify it, rotate. Raises on any failure."""
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / source.name
    partial = folder / (source.name + ".partial")
    try:
        shutil.copyfile(source, partial)
        if sha256(partial) != sha256(source):
            msg = "copy differs from the source backup (sha256)"
            raise OSError(msg)
        partial.replace(final)
    finally:
        partial.unlink(missing_ok=True)
    conn = sqlite3.connect(
        f"file:{final.as_posix()}?mode=ro&immutable=1", uri=True
    )  # no -wal/-shm files
    try:
        verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    if verdict != "ok":
        final.unlink(missing_ok=True)
        msg = f"copy failed SQLite integrity_check: {verdict}"
        raise OSError(msg)
    for old in sorted(folder.glob("paper-*.sqlite3"))[:-keep]:
        with contextlib.suppress(OSError):  # a locked old copy must not fail a good new copy
            old.unlink(missing_ok=True)
    return final


def sync_mirror(state: MirrorState, source: Path, keep: int, now: datetime | None = None) -> bool:
    """Bring one mirror up to date with ``source`` (the newest local backup). Never raises."""
    moment = now or datetime.now(UTC)
    state.last_attempt = moment
    try:
        final = copy_verified(source, state.path, keep)
    except Exception as exc:
        state.last_error = f"{type(exc).__name__}: {exc}"
        return False
    state.last_ok, state.last_error, state.last_file = moment, None, final.name
    return True
