"""Execution journal and the kill switch command line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from xau_edge.execution.cli import run
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.runner import JournalError
from xau_edge.execution.state import ExecutionState
from xau_edge.risk.kill_switch import RESET_PHRASE


def test_events_are_appended_and_read_back(tmp_path: Path) -> None:
    journal = ExecutionJournal(tmp_path / "j.jsonl")
    journal.record("order.requested", intent_id="i1", lots=0.5)
    journal.record("order.answered", intent_id="i1", retcode=10009)
    rows = journal.read()
    assert [r["event"] for r in rows] == ["order.requested", "order.answered"]
    assert rows[1]["retcode"] == 10009


def test_secret_like_fields_are_redacted(tmp_path: Path) -> None:
    journal = ExecutionJournal(tmp_path / "j.jsonl")
    journal.record("x", password="hunter2", nested={"api_token": "t", "ok": 1})
    text = (tmp_path / "j.jsonl").read_text(encoding="utf-8")
    assert "hunter2" not in text
    assert json.loads(text)["nested"]["ok"] == 1


def test_an_unwritable_journal_raises(tmp_path: Path) -> None:
    (tmp_path / "j.jsonl").mkdir()
    with pytest.raises(JournalError):
        ExecutionJournal(tmp_path / "j.jsonl").record("x")


def test_a_malformed_journal_line_raises_on_read(tmp_path: Path) -> None:
    path = tmp_path / "j.jsonl"
    path.write_text("garbage\n", encoding="utf-8")
    with pytest.raises(JournalError):
        ExecutionJournal(path).read()


def _cli(tmp_path: Path, *argv: str) -> int:
    return run(argv, state_path=tmp_path / "s.sqlite", journal_path=tmp_path / "j.jsonl")


def test_trip_status_and_reset_through_the_cli(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _cli(tmp_path, "status") == 0
    assert "clear" in capsys.readouterr().out
    assert _cli(tmp_path, "trip", "--reason", "manual stop") == 0
    assert ExecutionState(tmp_path / "s.sqlite").kill_switch_state() == (True, "manual stop")
    capsys.readouterr()
    assert _cli(tmp_path, "status") == 0
    assert "TRIPPED" in capsys.readouterr().out
    assert _cli(tmp_path, "reset", "--confirm", "yes") == 2
    assert ExecutionState(tmp_path / "s.sqlite").kill_switch_state()[0] is True
    assert _cli(tmp_path, "reset", "--confirm", RESET_PHRASE) == 0
    assert ExecutionState(tmp_path / "s.sqlite").kill_switch_state()[0] is False
    events = [r["event"] for r in ExecutionJournal(tmp_path / "j.jsonl").read()]
    assert events == ["kill_switch.trip", "kill_switch.reset"]


def test_a_trip_still_latches_when_the_journal_is_broken(tmp_path: Path) -> None:
    (
        tmp_path / "j.jsonl"
    ).mkdir()  # the journal path is a directory: ExecutionJournal() ok, writes fail
    code = _cli(tmp_path, "trip", "--reason", "r")
    assert code == 0
    assert ExecutionState(tmp_path / "s.sqlite").kill_switch_state() == (True, "r")


def test_a_corrupt_state_file_gives_exit_code_3(tmp_path: Path) -> None:
    (tmp_path / "s.sqlite").write_bytes(b"junk" * 100)
    assert _cli(tmp_path, "status") == 3
