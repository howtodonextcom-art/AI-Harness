"""FTMO guards: rollover, market close, request budget, auto-flatten, trading days."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.unit.execution.test_bridge import PROP, _account, _bridge, _buy, _offer
from xau_edge.brokers.mt5_demo.executor import TRADE_SERVER_REQUESTS
from xau_edge.execution.guards import (
    DAILY_REQUEST_BUDGET,
    MIDNIGHT_ROLLOVER_RISK,
    NEAR_MARKET_CLOSE,
    CountingMt5,
    EntryGuard,
    RequestBudgetExceededError,
    evaluate_flatten,
    midnight_rollover_risk,
    near_market_close,
    next_prague_midnight,
)
from xau_edge.execution.state import ExecutionState
from xau_edge.market_data.profiles import BrokerProfile

PROFILE = BrokerProfile.from_yaml(
    Path(__file__).parents[3] / "configs" / "brokers" / "ftmo_demo.yaml"
)
CAL = PROFILE.validation.calendar
T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)  # a Wednesday afternoon
BUDGETED = TRADE_SERVER_REQUESTS


def test_next_prague_midnight_follows_daylight_saving() -> None:
    winter = next_prague_midnight(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
    assert winter == datetime(2026, 1, 15, 23, 0, tzinfo=UTC)  # CET = UTC+1
    summer = next_prague_midnight(datetime(2026, 7, 15, 12, 0, tzinfo=UTC))
    assert summer == datetime(2026, 7, 15, 22, 0, tzinfo=UTC)  # CEST = UTC+2


def test_rollover_risk_needs_both_the_window_and_a_hold_across_midnight() -> None:
    midnight = datetime(2026, 1, 15, 23, 0, tzinfo=UTC)
    near = midnight - timedelta(minutes=60)
    assert midnight_rollover_risk(near, near + timedelta(hours=5))
    assert not midnight_rollover_risk(near, near + timedelta(minutes=30))  # closes before
    far = midnight - timedelta(hours=6)
    assert not midnight_rollover_risk(far, far + timedelta(hours=8))  # outside the window
    edge = midnight - timedelta(minutes=120)
    assert midnight_rollover_risk(edge, edge + timedelta(hours=3))  # window is inclusive


def test_market_close_margin_covers_the_daily_break_and_the_weekend() -> None:
    # daily break starts 16:50 New York; on 2026-03-04 New York is UTC-5 -> 21:50 UTC
    assert near_market_close(datetime(2026, 3, 4, 21, 30, tzinfo=UTC), CAL, margin_minutes=30)
    assert not near_market_close(datetime(2026, 3, 4, 20, 0, tzinfo=UTC), CAL, margin_minutes=30)
    assert near_market_close(
        datetime(2026, 3, 4, 22, 0, tzinfo=UTC), CAL, margin_minutes=30
    )  # in it
    friday_late = datetime(2026, 3, 6, 21, 40, tzinfo=UTC)
    assert near_market_close(friday_late, CAL, margin_minutes=30)
    saturday = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    assert near_market_close(saturday, CAL, margin_minutes=30)


def test_the_entry_guard_returns_every_reason() -> None:
    guard = EntryGuard(CAL)
    assert guard(T, T + timedelta(hours=5)) == []
    late = datetime(
        2026, 3, 4, 21, 45, tzinfo=UTC
    )  # 15 min before the break, 75 min before midnight
    reasons = guard(late, late + timedelta(hours=5))
    assert NEAR_MARKET_CLOSE in reasons
    assert MIDNIGHT_ROLLOVER_RISK in reasons


def test_the_bridge_refuses_through_the_entry_guard_and_records_nothing(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    bridge.entry_guard = EntryGuard(CAL)
    signal = _buy()
    result = _offer(bridge, signal, now=signal.timestamp)  # 14:00 UTC, mid-session
    assert result.accepted
    other = tmp_path / "o"
    other.mkdir()
    blocked_bridge = _bridge(other)
    blocked_bridge.entry_guard = lambda now, hold: [NEAR_MARKET_CLOSE]
    blocked = _offer(blocked_bridge, _buy())
    assert blocked.reasons == (NEAR_MARKET_CLOSE,)
    assert not blocked_bridge.state.is_seen(_buy().inputs_hash)


def test_auto_flatten_triggers_within_one_percent_of_either_floor() -> None:
    far = evaluate_flatten(_account(), PROP)
    assert not far.flatten
    # daily floor = 100,000 - 5,000 = 95,000; equity 95,900 is 0.9% of initial above it
    near_daily = evaluate_flatten(_account(equity=95_900.0, balance=100_000.0), PROP)
    assert near_daily.flatten
    assert near_daily.reason == "AUTO_FLATTEN_DAILY_LOSS"
    assert near_daily.daily_distance_pct == pytest.approx(0.9)
    just_outside = evaluate_flatten(_account(equity=96_100.0), PROP)
    assert not just_outside.flatten
    # max-loss floor 90,000; day start at 91,000 keeps the daily floor far below
    near_max = evaluate_flatten(
        _account(equity=90_900.0, balance=91_000.0, day_start_balance=91_000.0), PROP
    )
    assert near_max.flatten
    assert near_max.reason == "AUTO_FLATTEN_MAX_LOSS"
    on_floor = evaluate_flatten(_account(equity=95_000.0), PROP)
    assert on_floor.flatten


class _Terminal:
    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self) -> None:
        self.calls = 0
        self.reads = 0

    def order_check(self, request: object = None) -> SimpleNamespace:
        self.calls += 1
        return SimpleNamespace(retcode=0)

    def account_info(self) -> SimpleNamespace:
        self.reads += 1
        return SimpleNamespace(login=1)

    def last_error(self) -> tuple[int, str]:
        return (0, "ok")


def test_the_request_counter_persists_and_stops_at_the_budget(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    term = _Terminal()
    client = CountingMt5(term, state, budgeted=BUDGETED, budget=3, clock=lambda: T)
    for _ in range(3):
        client.order_check()
    client.last_error()  # not counted
    assert client.ACCOUNT_TRADE_MODE_DEMO == 0  # constants pass through
    assert client.used_today() == 3
    with pytest.raises(RequestBudgetExceededError):
        client.order_check()
    assert term.calls == 3  # the refused call never reached the terminal
    again = CountingMt5(
        term, ExecutionState(tmp_path / "s.sqlite"), budgeted=BUDGETED, budget=3, clock=lambda: T
    )
    with pytest.raises(RequestBudgetExceededError):
        again.order_check()  # a restart does not reset the count


def test_reads_are_counted_but_never_stopped_by_the_trade_budget(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    term = _Terminal()
    client = CountingMt5(term, state, budgeted=BUDGETED, budget=1, clock=lambda: T)
    client.order_check()
    for _ in range(5):
        client.account_info()  # monitoring keeps working once the trade budget is spent
    assert client.used_today() == 1
    assert client.calls_today() == 5
    assert term.reads == 5


def test_the_counter_starts_over_on_the_next_prague_day(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    term = _Terminal()
    now = {"t": T}
    client = CountingMt5(term, state, budgeted=BUDGETED, budget=1, clock=lambda: now["t"])
    client.order_check()
    with pytest.raises(RequestBudgetExceededError):
        client.order_check()
    now["t"] = T + timedelta(days=1)
    client.order_check()
    assert term.calls == 2


def test_the_default_budget_is_a_hard_900_requests_a_day(tmp_path: Path) -> None:
    assert DAILY_REQUEST_BUDGET == 900
    assert DAILY_REQUEST_BUDGET < 1000
    state = ExecutionState(tmp_path / "s.sqlite")
    term = _Terminal()
    client = CountingMt5(term, state, budgeted=BUDGETED, clock=lambda: T)
    assert client.budget == 900
    state.bump_requests("2026-03-04", 899)
    client.order_check()  # the 900th request is allowed
    assert client.used_today() == 900
    with pytest.raises(RequestBudgetExceededError):
        client.order_check()  # the 901st is not
    assert term.calls == 1


def test_trading_days_are_recorded_once_per_day(tmp_path: Path) -> None:
    state = ExecutionState(tmp_path / "s.sqlite")
    assert state.trading_days() == []
    state.record_trading_day("2026-03-04")
    state.record_trading_day("2026-03-04")
    state.record_trading_day("2026-03-02")
    assert ExecutionState(tmp_path / "s.sqlite").trading_days() == ["2026-03-02", "2026-03-04"]
