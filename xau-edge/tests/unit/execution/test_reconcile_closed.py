"""A position the broker closed (stop or target) is a normal event, not a mismatch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.unit.execution.test_reconcile import _account, _pos, _record
from xau_edge.execution.reconcile import (
    BrokerSnapshot,
    ClosedResult,
    Reconciler,
    trailing_losses,
)
from xau_edge.execution.state import ExecutionState

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _snap(*closed: ClosedResult) -> BrokerSnapshot:
    return BrokerSnapshot(T, _account(), (), closed)


def test_a_ticket_closed_by_the_broker_is_marked_closed_without_a_mismatch(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    state.register_position(_record())
    rec = Reconciler(state, magic=7, trip_on_mismatch=True)
    result = rec.check(_snap(ClosedResult("100", T, 25.0)))
    assert result.clean
    assert state.open_positions() == []
    assert state.kill_switch_state()[0] is False
    assert rec.check(_snap()).clean  # and it stays clean afterwards


def test_a_vanished_ticket_without_a_close_record_is_still_a_mismatch(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    state.register_position(_record())
    rec = Reconciler(state, magic=7, trip_on_mismatch=True)
    assert rec.check(_snap(ClosedResult("999", T, 1.0))).codes == ("BOT_TICKET_MISSING",)
    assert state.kill_switch_state()[0] is True


def test_a_still_open_position_is_not_closed_by_an_unrelated_close(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    state.register_position(_record())
    rec = Reconciler(state, magic=7)
    snap = BrokerSnapshot(T, _account(), (_pos(),), (ClosedResult("5", T, 1.0),))
    assert rec.check(snap).clean
    assert len(state.open_positions()) == 1


def test_trailing_losses_counts_only_recent_bot_losses() -> None:
    def res(ticket: str, minutes: int, profit: float) -> ClosedResult:
        return ClosedResult(ticket, T + timedelta(minutes=minutes), profit)

    results = (
        res("1", 0, -5.0),
        res("2", 10, 3.0),
        res("3", 20, -1.0),
        res("4", 30, -2.0),
        res("manual", 40, -9.0),
    )
    assert trailing_losses(results, {"1", "2", "3", "4"}) == 2
    assert trailing_losses(results, {"1", "2"}) == 0
    assert trailing_losses((), {"1"}) == 0
    assert trailing_losses((res("1", 0, -1.0),), {"1"}) == 1
