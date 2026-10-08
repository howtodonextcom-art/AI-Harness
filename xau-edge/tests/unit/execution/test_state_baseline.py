"""Account baseline, daily risk and approval records survive restarts (review finding: limits)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from xau_edge.execution.state import ExecutionState

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def test_account_baseline_persists_across_restarts_and_rolls_per_day(tmp_path: Path) -> None:
    path = tmp_path / "s.sqlite"
    first = ExecutionState(path).account_baseline("2026-03-04", 10_000.0)
    assert (first.initial_capital, first.day_start_balance, first.highest_eod_balance) == (
        10_000.0,
        10_000.0,
        10_000.0,
    )
    # a loss during the day; a restart must not move the reference points
    later = ExecutionState(path).account_baseline("2026-03-04", 9_000.0)
    assert (later.initial_capital, later.day_start_balance) == (10_000.0, 10_000.0)
    # next day: starts from the last balance seen, the high-water mark is kept
    nxt = ExecutionState(path).account_baseline("2026-03-05", 9_000.0)
    assert nxt.initial_capital == 10_000.0
    assert nxt.day_start_balance == 9_000.0
    assert nxt.highest_eod_balance == 10_000.0
    day3 = ExecutionState(path).account_baseline("2026-03-06", 12_000.0)
    assert day3.highest_eod_balance == 10_000.0
    day4 = ExecutionState(path).account_baseline("2026-03-07", 12_000.0)
    assert day4.highest_eod_balance == 12_000.0


def test_the_configured_initial_capital_wins_on_the_first_call(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    base = state.account_baseline("d", 9_494.0, initial_capital=100_000.0)
    assert base.initial_capital == 100_000.0
    assert state.account_baseline("d", 9_000.0, initial_capital=5.0).initial_capital == 100_000.0


def _accept(state: ExecutionState, tag: str, day: str, *, dry_run: bool, risk: float) -> None:
    state.record_accepted(
        signal_hash=tag,
        intent_id="i" + tag,
        decision_time=T,
        day=day,
        dry_run=dry_run,
        max_orders_per_day=9,
        risk_amount=risk,
    )


def test_risk_taken_counts_only_real_orders_of_that_day(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    _accept(state, "a", "d1", dry_run=False, risk=100.0)
    _accept(state, "b", "d1", dry_run=True, risk=500.0)
    _accept(state, "c", "d2", dry_run=False, risk=7.0)
    assert state.risk_taken("d1") == 100.0
    assert state.risk_taken("d2") == 7.0
    assert state.risk_taken("d3") == 0.0
    assert state.is_approved("ia")
    assert not state.is_approved("ib")  # a dry-run intent is never approved for sending
    assert not state.is_approved("zzz")
