"""Dry-run cycle: one journalled decision per closed bar; stale data refused; intents only."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.api.test_api import frames  # noqa: F401 - fixture import
from tests.unit.execution.test_bridge import PROP, _account
from tests.unit.signals.test_decision import _inputs
from xau_edge.execution.bridge import SignalBridge
from xau_edge.execution.runner import (
    CycleJournal,
    DryRunCycle,
    JournalError,
    LockHeldError,
    acquire_lock,
    next_close,
    write_heartbeat,
)
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.state import ExecutionState, PersistentKillSwitch
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.signals.decision import decide
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import EvidenceStatus, Signal


def _decision_time(frames: MarketFrames) -> datetime:  # noqa: F811
    last = frames.m15["timestamp"].max()
    assert isinstance(last, datetime)
    return last + timedelta(minutes=15)


def _cycle(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
    *,
    evidence: EvidenceStatus = EvidenceStatus.VALIDATED,
) -> DryRunCycle:
    state = ExecutionState(tmp_path / "s.sqlite")
    risk = RiskEngine(RiskLimits(), PROP, kill_switch=PersistentKillSwitch(state))
    bridge = SignalBridge(state, risk, ExecutionSafety(), magic=7)
    price = float(frames.m5["close"][-1])

    def signal_fn(at: datetime) -> Signal:
        return decide(_inputs(timestamp=at, price=price, evidence_status=evidence))

    return DryRunCycle(bridge, signal_fn, CycleJournal(tmp_path / "journal.jsonl"))


def _lines(tmp_path: Path) -> list[dict[str, object]]:
    text = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines()]


def test_a_fresh_bar_with_open_evidence_gives_a_dry_run_intent_and_one_journal_line(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    at = _decision_time(frames)
    report = _cycle(tmp_path, frames).run(frames, at + timedelta(minutes=1), _account())
    assert report.accepted
    assert report.dry_run is True
    assert report.direction == "BUY"
    assert report.intent_id is not None
    rows = _lines(tmp_path)
    assert len(rows) == 1
    assert rows[0]["decision_time"] == at.isoformat()
    assert "password" not in json.dumps(rows[0]).lower()


def test_closed_evidence_means_wait_with_reasons_in_the_journal(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    at = _decision_time(frames)
    cycle = _cycle(tmp_path, frames, evidence=EvidenceStatus.NONE)
    report = cycle.run(frames, at + timedelta(minutes=1), _account())
    assert not report.accepted
    assert report.direction == "WAIT"
    assert "NO_VALIDATED_EDGE" in report.reasons
    assert report.intent_id is None


def test_stale_data_is_refused_and_journalled_without_a_signal(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    at = _decision_time(frames)
    report = _cycle(tmp_path, frames).run(frames, at + timedelta(hours=3), _account())
    assert report.reasons == ("DATA_STALE",)
    assert not report.accepted
    assert report.signal_hash == ""
    assert _lines(tmp_path)[0]["reasons"] == ["DATA_STALE"]


def test_data_from_the_future_is_refused(tmp_path: Path, frames: MarketFrames) -> None:  # noqa: F811
    at = _decision_time(frames)
    report = _cycle(tmp_path, frames).run(frames, at - timedelta(minutes=5), _account())
    assert report.reasons == ("DATA_IN_FUTURE",)


def test_the_same_bar_is_not_decided_twice_even_after_a_restart(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    at = _decision_time(frames)
    now = at + timedelta(minutes=1)
    _cycle(tmp_path, frames).run(frames, now, _account())
    again = _cycle(tmp_path, frames).run(frames, now, _account())  # a fresh process
    assert again.reasons == ("BAR_ALREADY_PROCESSED",)
    assert len(_lines(tmp_path)) == 1


def test_a_tripped_kill_switch_refuses_and_is_journalled(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    at = _decision_time(frames)
    cycle = _cycle(tmp_path, frames)
    cycle.bridge.state.trip_kill_switch("test")
    report = cycle.run(frames, at + timedelta(minutes=1), _account())
    assert report.reasons == ("KILL_SWITCH",)
    assert _lines(tmp_path)[0]["reasons"] == ["KILL_SWITCH"]


def test_empty_data_is_skipped(tmp_path: Path, frames: MarketFrames) -> None:  # noqa: F811
    empty = MarketFrames(frames.m5.head(0), frames.m15.head(0), frames.h1, frames.h4)
    report = _cycle(tmp_path, frames).run(empty, _decision_time(frames), _account())
    assert report.reasons == ("DATA_EMPTY",)


def test_an_unwritable_journal_stops_the_cycle(
    tmp_path: Path,
    frames: MarketFrames,  # noqa: F811
) -> None:
    cycle = _cycle(tmp_path, frames)
    folder = tmp_path / "journal.jsonl"
    folder.mkdir()  # a directory where the file should be
    at = _decision_time(frames)
    with pytest.raises(JournalError):
        cycle.run(frames, at + timedelta(minutes=1), _account())


def test_a_corrupt_journal_is_refused(tmp_path: Path, frames: MarketFrames) -> None:  # noqa: F811
    (tmp_path / "journal.jsonl").write_text("not json\n", encoding="utf-8")
    with pytest.raises(JournalError):
        _cycle(tmp_path, frames).run(frames, _decision_time(frames), _account())


def test_the_runner_package_has_no_broker_call() -> None:
    text = (Path(__file__).parents[3] / "src" / "xau_edge" / "execution" / "runner.py").read_text()
    for forbidden in ("submit_order", "MetaTrader5", "order_send"):
        assert forbidden not in text


def test_next_close_is_the_next_quarter_hour_boundary() -> None:
    base = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)
    assert next_close(base) == base + timedelta(minutes=15)
    assert next_close(base + timedelta(minutes=14, seconds=59)) == base + timedelta(minutes=15)
    assert next_close(base + timedelta(minutes=15)) == base + timedelta(minutes=30)
    assert next_close(base + timedelta(minutes=50)) == base + timedelta(hours=1)


def test_a_second_instance_is_refused_until_the_lock_is_removed(tmp_path: Path) -> None:
    lock = tmp_path / "x" / "bot.lock"
    acquire_lock(lock)
    with pytest.raises(LockHeldError):
        acquire_lock(lock)
    lock.unlink()
    acquire_lock(lock)


def test_the_heartbeat_records_time_and_status(tmp_path: Path) -> None:
    path = tmp_path / "hb.json"
    now = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)
    write_heartbeat(path, now, "OK")
    assert json.loads(path.read_text(encoding="utf-8")) == {"at": now.isoformat(), "status": "OK"}
