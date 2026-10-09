from __future__ import annotations

import json
from pathlib import Path

import pytest

from xau_edge.research.lifecycle import LifecycleError, LifecycleStore

SEED = {"A": "FUNDED", "B": "FUNDED"}


def test_a_key_reused_for_another_strategy_is_a_conflict_not_a_silent_success(
    tmp_path: Path,
) -> None:
    store = LifecycleStore(tmp_path / "l.jsonl", SEED)
    store.demote("A", "DISABLED", "kill A", "web", key="key-12345678")
    with pytest.raises(LifecycleError, match="IDEMPOTENCY_CONFLICT"):
        store.demote("B", "DISABLED", "kill B", "web", key="key-12345678")
    assert store.states() == {"A": "DISABLED", "B": "FUNDED"}
    with pytest.raises(LifecycleError, match="invalid strategy id"):
        store.demote("../x", "DISABLED", "r", "web", key="key-12345678")
    assert store.demote("A", "DISABLED", "kill A", "web", key="key-12345678").strategy_id == "A"


def test_a_torn_last_line_does_not_block_an_emergency_demote(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    store = LifecycleStore(path, SEED)
    store.demote("A", "WATCH", "first", "web")
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"strategy_id": "B", "from_st')  # crash mid-write, no newline
    assert store.states()["A"] == "WATCH"
    store.demote("B", "DISABLED", "emergency", "web")
    assert store.states() == {"A": "WATCH", "B": "DISABLED"}
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert any(
        json.loads(ln).get("strategy_id") == "B" and json.loads(ln).get("to_state")
        for ln in lines[-1:]
    )


def test_a_corrupt_middle_line_still_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    store = LifecycleStore(path, SEED)
    store.demote("A", "WATCH", "first", "web")
    path.write_text("garbage\n" + path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(LifecycleError):
        store.states()


def test_a_complete_last_event_that_only_lost_its_newline_is_kept(tmp_path: Path) -> None:
    path = tmp_path / "l.jsonl"
    store = LifecycleStore(path, SEED)
    store.demote("A", "WATCH", "first", "web")
    path.write_text(path.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8")
    store.demote("B", "DISABLED", "second", "web")
    assert store.states() == {"A": "WATCH", "B": "DISABLED"}
