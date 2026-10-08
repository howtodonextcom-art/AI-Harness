"""Persistent execution state: survives restarts, and any storage problem fails closed."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xau_edge.execution.state import (
    STATE_UNREADABLE,
    BotPositionRecord,
    DailyLimitError,
    DuplicateSignalError,
    DuplicateSubmissionError,
    ExecutionState,
    PersistentKillSwitch,
    StateError,
)
from xau_edge.risk.kill_switch import RESET_PHRASE

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _record(
    state: ExecutionState, sig: str = "h1", *, dry_run: bool = False, limit: int = 5
) -> None:
    state.record_accepted(
        signal_hash=sig,
        intent_id="i-" + sig,
        decision_time=T,
        day="2026-03-04",
        dry_run=dry_run,
        max_orders_per_day=limit,
    )


def test_a_new_state_starts_safe(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    assert state.kill_switch_state() == (False, "")
    assert not state.is_seen("h1")
    assert state.last_decision_bar() is None
    assert state.daily_order_count("2026-03-04") == 0
    assert state.open_positions() == []


def test_the_kill_switch_survives_a_restart_and_keeps_the_first_reason(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    ExecutionState(path).trip_kill_switch("first")
    again = ExecutionState(path)
    again.trip_kill_switch("second")
    assert again.kill_switch_state() == (True, "first")


def test_the_kill_switch_never_resets_by_itself_and_needs_the_phrase(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    state = ExecutionState(path)
    state.trip_kill_switch("breach")
    for _ in range(3):
        state = ExecutionState(path)  # restarts do not reset
    assert state.kill_switch_state()[0] is True
    with pytest.raises(ValueError, match="confirm"):
        state.reset_kill_switch(confirm="yes")
    assert state.kill_switch_state()[0] is True
    state.reset_kill_switch(confirm=RESET_PHRASE)
    assert ExecutionState(path).kill_switch_state() == (False, "")


def test_a_seen_signal_and_the_decision_bar_persist_across_restart(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    _record(ExecutionState(path))
    again = ExecutionState(path)
    assert again.is_seen("h1")
    assert again.last_decision_bar() == T
    with pytest.raises(DuplicateSignalError):
        _record(again)


def test_the_daily_counter_persists_and_the_limit_is_enforced_atomically(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    _record(ExecutionState(path), "a", limit=2)
    _record(ExecutionState(path), "b", limit=2)
    state = ExecutionState(path)
    assert state.daily_order_count("2026-03-04") == 2
    with pytest.raises(DailyLimitError):
        _record(state, "c", limit=2)
    assert not state.is_seen("c")  # nothing was written by the refused call
    assert state.daily_order_count("2026-03-04") == 2


def test_dry_run_is_remembered_but_does_not_use_the_daily_budget(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    _record(state, "a", dry_run=True, limit=1)
    assert state.is_seen("a")
    assert state.daily_order_count("2026-03-04") == 0
    _record(state, "b", dry_run=False, limit=1)


def _record_position(intent: str = "i1", ticket: str = "100") -> BotPositionRecord:
    return BotPositionRecord(intent, ticket, "XAUUSD", 1, 0.5, 1990.0, 2010.0, T, T)


def test_bot_positions_persist_and_can_be_closed(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    ExecutionState(path).register_position(_record_position())
    state = ExecutionState(path)
    assert state.open_positions() == [_record_position()]
    state.mark_position_closed("100")
    assert ExecutionState(path).open_positions() == []


def test_registering_twice_or_closing_an_unknown_ticket_is_an_error(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    state.register_position(_record_position())
    with pytest.raises(StateError, match="already"):
        state.register_position(_record_position(ticket="101"))
    with pytest.raises(StateError, match="no open"):
        state.mark_position_closed("999")
    state.mark_position_closed("100")
    with pytest.raises(StateError, match="no open"):
        state.mark_position_closed("100")


def test_a_file_that_is_not_a_database_is_refused_not_recreated(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    path.write_bytes(b"this is not a sqlite database" * 50)
    with pytest.raises(StateError):
        ExecutionState(path)
    assert path.read_bytes().startswith(b"this is not")  # left untouched


def test_an_empty_or_wrong_schema_file_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.sqlite"
    empty.write_bytes(b"")
    with pytest.raises(StateError, match="schema"):
        ExecutionState(empty)
    other = tmp_path / "other.sqlite"
    conn = sqlite3.connect(other)
    conn.execute("CREATE TABLE unrelated (x INTEGER)")
    conn.commit()
    conn.close()
    with pytest.raises(StateError, match="schema"):
        ExecutionState(other)


def test_a_wrong_schema_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    ExecutionState(path)
    conn = sqlite3.connect(path)
    conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(StateError, match="version"):
        ExecutionState(path)


def test_an_unusable_path_raises(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")
    with pytest.raises(StateError):
        ExecutionState(blocker / "sub" / "s.sqlite")


def test_a_directory_in_place_of_the_file_raises(tmp_path: Path) -> None:
    folder = tmp_path / "s.sqlite"
    folder.mkdir()
    with pytest.raises(StateError):
        ExecutionState(folder)


def test_a_write_failure_is_raised_not_swallowed(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    state = ExecutionState(path)
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE seen_signals")
    conn.commit()
    conn.close()
    with pytest.raises(StateError):
        _record(state)


def test_a_corrupted_stored_decision_bar_raises(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    state = ExecutionState(path)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO meta (key, value) VALUES ('last_decision_bar', 'garbage')")
    conn.commit()
    conn.close()
    with pytest.raises(StateError):
        state.last_decision_bar()


def test_the_persistent_kill_switch_matches_the_risk_engine_interface(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    switch = PersistentKillSwitch(ExecutionState(path))
    assert not switch.tripped
    assert switch.reason == ""
    switch.trip("breach")
    restarted = PersistentKillSwitch(ExecutionState(path))
    assert restarted.tripped
    assert restarted.reason == "breach"
    with pytest.raises(ValueError, match="confirm"):
        restarted.reset(confirm="no")
    assert restarted.tripped
    restarted.reset(confirm=RESET_PHRASE)
    assert not PersistentKillSwitch(ExecutionState(path)).tripped


def test_an_unreadable_state_makes_the_persistent_kill_switch_report_tripped(
    tmp_path: Path,
) -> None:
    path = tmp_path / "s.sqlite"
    switch = PersistentKillSwitch(ExecutionState(path))
    conn = sqlite3.connect(path)
    conn.execute("DROP TABLE kill_switch")
    conn.commit()
    conn.close()
    assert switch.tripped is True
    assert switch.reason == STATE_UNREADABLE


def test_a_submission_can_begin_once_and_unresolved_ones_are_listed(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    state = ExecutionState(path)
    state.begin_submission("i1", "h1")
    with pytest.raises(DuplicateSubmissionError):
        ExecutionState(path).begin_submission("i1", "h1")  # even from a new process
    assert state.unresolved_submissions() == ["i1"]
    state.finish_submission("i1", "UNKNOWN")
    assert state.unresolved_submissions() == ["i1"]
    state.finish_submission("i1", "FILLED", retcode=10009, ticket="5")
    assert state.unresolved_submissions() == []
    with pytest.raises(DuplicateSubmissionError):
        state.begin_submission("i1", "h1")  # a finished intent is never sent again
    with pytest.raises(StateError, match="no submission"):
        state.finish_submission("zzz", "FILLED")
