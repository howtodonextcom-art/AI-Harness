"""Restoring the paper book from a backup: verified first, reversible, never half-done."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.unit.test_reliability import NOW, position_row
from xau_edge_v2.paper.restore import RestoreError, restore, verify
from xau_edge_v2.paper.store import PaperStore


def book(path: Path, setups: int) -> PaperStore:
    store = PaperStore(path)
    for i in range(setups):
        assert store.insert_position(position_row(f"s{i}"), {"i": i})
    return store


def test_restore_replaces_the_book_keeps_the_old_one_and_matches_the_backup(tmp_path: Path) -> None:
    good = book(tmp_path / "good.sqlite3", 2)
    backup = good.backup_to(tmp_path / "backups" / "paper-1.sqlite3")
    good.close()
    live = book(tmp_path / "paper.sqlite3", 5)  # the damaged or later book: 5 positions
    live.close()
    kept, counts = restore(backup, tmp_path / "paper.sqlite3", NOW)
    assert counts["positions"] == 2 and counts["journal"] == 2
    assert kept is not None and kept.name == "paper-before-restore-20260303-100020.sqlite3"
    assert verify(kept)["positions"] == 5  # the undo exists
    restored = PaperStore(tmp_path / "paper.sqlite3")
    assert restored.integrity() == [] and len(restored.positions()) == 2
    restored.close()


def test_stale_wal_files_cannot_leak_into_the_restored_data(tmp_path: Path) -> None:
    src = book(tmp_path / "a.sqlite3", 1)
    backup = src.backup_to(tmp_path / "paper-1.sqlite3")
    src.close()
    target = tmp_path / "paper.sqlite3"
    target.write_bytes(backup.read_bytes())
    (tmp_path / "paper.sqlite3-wal").write_bytes(b"garbage that must not be replayed")
    (tmp_path / "paper.sqlite3-shm").write_bytes(b"x" * 32768)
    restore(backup, target, NOW)
    assert not (tmp_path / "paper.sqlite3-wal").exists()
    assert not (tmp_path / "paper.sqlite3-shm").exists()


def test_a_missing_or_corrupt_backup_is_refused_and_nothing_changes(tmp_path: Path) -> None:
    live = book(tmp_path / "paper.sqlite3", 3)
    live.close()
    before = (tmp_path / "paper.sqlite3").read_bytes()
    with pytest.raises(RestoreError, match="no such backup"):
        restore(tmp_path / "nope.sqlite3", tmp_path / "paper.sqlite3", NOW)
    junk = tmp_path / "junk.sqlite3"
    junk.write_bytes(b"this is not a database at all" * 100)
    with pytest.raises(RestoreError):
        restore(junk, tmp_path / "paper.sqlite3", NOW)
    assert (tmp_path / "paper.sqlite3").read_bytes() == before
    assert not list(tmp_path.glob("paper-before-restore-*"))


def test_restore_works_when_there_is_no_current_database(tmp_path: Path) -> None:
    src = book(tmp_path / "a.sqlite3", 1)
    backup = src.backup_to(tmp_path / "b" / "paper-1.sqlite3")
    src.close()
    kept, counts = restore(backup, tmp_path / "fresh" / "paper.sqlite3", NOW)
    assert kept is None and counts["positions"] == 1
