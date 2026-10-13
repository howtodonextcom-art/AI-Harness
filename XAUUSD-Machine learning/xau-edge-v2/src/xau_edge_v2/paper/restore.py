"""Restore the paper book from a backup (the service must be stopped first).

The backup is verified BEFORE anything is touched; the current database is kept next to it
(``paper-before-restore-<utc>.sqlite3``) so a restore can itself be undone; the stale WAL/SHM
sidecars of the old file are removed so SQLite cannot replay them into the restored data.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

TABLES = ("positions", "journal", "decision_log", "human_decisions", "account")


class RestoreError(RuntimeError):
    """The restore was refused; nothing was changed."""


def verify(path: Path) -> dict[str, int]:
    """Row counts of a sound backup; raises ``RestoreError`` when it is not sound."""
    if not path.is_file():
        msg = f"no such backup: {path}"
        raise RestoreError(msg)
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True)
        try:
            verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
            present = {
                r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            counts = {
                t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
                for t in TABLES
                if t in present  # an older backup may predate a table
            }
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        msg = f"the backup is not a usable database: {exc}"
        raise RestoreError(msg) from exc
    if verdict != "ok":
        msg = f"the backup failed integrity_check: {verdict}"
        raise RestoreError(msg)
    return counts


def restore(
    backup: Path, target: Path, now: datetime | None = None
) -> tuple[Path | None, dict[str, int]]:
    """Replace ``target`` with ``backup``; returns (the kept copy of the old file, restored counts)."""
    counts = verify(backup)
    moment = now or datetime.now(UTC)
    kept: Path | None = None
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        kept = target.with_name(f"paper-before-restore-{moment:%Y%m%d-%H%M%S}.sqlite3")
        shutil.copyfile(target, kept)
    for suffix in ("-wal", "-shm"):
        Path(str(target) + suffix).unlink(missing_ok=True)
    tmp = target.with_suffix(".restoring")
    shutil.copyfile(backup, tmp)
    tmp.replace(target)
    after = verify(target)
    if after != counts:
        msg = "the restored file does not match the backup"
        raise RestoreError(msg)
    return kept, after
