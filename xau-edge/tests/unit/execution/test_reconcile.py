"""Reconciliation: every difference between broker and state is found and fails closed."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from xau_edge.execution.reconcile import (
    BrokerAccount,
    BrokerPosition,
    BrokerSnapshot,
    Reconciler,
)
from xau_edge.execution.state import BotPositionRecord, ExecutionState

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)
MAGIC = 7


def _account(**over: Any) -> BrokerAccount:
    base: dict[str, Any] = {
        "account_id": "A1",
        "is_demo": True,
        "balance": 100_000.0,
        "equity": 100_000.0,
    }
    base.update(over)
    return BrokerAccount(**base)


def _pos(**over: Any) -> BrokerPosition:
    base: dict[str, Any] = {
        "ticket": "100",
        "symbol": "XAUUSD",
        "direction": 1,
        "lots": 0.5,
        "entry_price": 2000.0,
        "stop_loss": 1990.0,
        "take_profit": 2010.0,
        "magic": MAGIC,
        "comment": "XAUEDGE:abc",
        "opened_at": T,
    }
    base.update(over)
    return BrokerPosition(**base)


def _snap(*positions: BrokerPosition, account: BrokerAccount | None = None) -> BrokerSnapshot:
    return BrokerSnapshot(T, account or _account(), tuple(positions))


def _record() -> BotPositionRecord:
    return BotPositionRecord("i1", "100", "XAUUSD", 1, 0.5, 1990.0, 2010.0, T, T)


def _rec(tmp_path: Path, *, with_position: bool = True, **kwargs: Any) -> Reconciler:
    state = ExecutionState(tmp_path / "s.sqlite")
    if with_position:
        state.register_position(_record())
    return Reconciler(state, magic=MAGIC, **kwargs)


def test_an_empty_book_on_both_sides_is_clean(tmp_path: Path) -> None:
    result = _rec(tmp_path, with_position=False).check(_snap())
    assert result.clean
    assert result.codes == ()


def test_a_matching_position_is_clean(tmp_path: Path) -> None:
    assert _rec(tmp_path).check(_snap(_pos())).clean


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"lots": 0.6}, "LOT_MISMATCH"),
        ({"stop_loss": 1985.0}, "SL_MISMATCH"),
        ({"take_profit": 2020.0}, "TP_MISMATCH"),
        ({"direction": -1}, "DIRECTION_MISMATCH"),
    ],
)
def test_changed_position_fields_are_mismatches(
    tmp_path: Path, override: dict[str, Any], code: str
) -> None:
    result = _rec(tmp_path).check(_snap(_pos(**override)))
    assert not result.clean
    assert code in result.codes


def test_a_bot_ticket_that_vanished_is_a_mismatch(tmp_path: Path) -> None:
    assert _rec(tmp_path).check(_snap()).codes == ("BOT_TICKET_MISSING",)


def test_an_unknown_position_with_the_bot_magic_is_a_mismatch(tmp_path: Path) -> None:
    result = _rec(tmp_path, with_position=False).check(_snap(_pos(ticket="555")))
    assert result.codes == ("UNKNOWN_BOT_POSITION",)


def test_a_manual_position_on_the_same_symbol_is_a_mismatch(tmp_path: Path) -> None:
    result = _rec(tmp_path, with_position=False).check(_snap(_pos(ticket="9", magic=0)))
    assert result.codes == ("MANUAL_POSITION_SAME_SYMBOL",)


def test_positions_on_other_symbols_are_ignored(tmp_path: Path) -> None:
    other = _pos(ticket="9", magic=0, symbol="EURUSD")
    assert _rec(tmp_path, with_position=False).check(_snap(other)).clean


def test_account_problems_are_mismatches(tmp_path: Path) -> None:
    rec = _rec(tmp_path, with_position=False, allowed_accounts=("A1",))
    assert "ACCOUNT_NOT_DEMO" in rec.check(_snap(account=_account(is_demo=False))).codes
    assert "ACCOUNT_EQUITY_INVALID" in rec.check(_snap(account=_account(equity=0.0))).codes
    nan_balance = _account(balance=float("nan"))
    assert "ACCOUNT_EQUITY_INVALID" in rec.check(_snap(account=nan_balance)).codes
    assert "ACCOUNT_NOT_WHITELISTED" in rec.check(_snap(account=_account(account_id="B"))).codes
    assert rec.check(_snap()).clean


def test_a_mismatch_can_trip_the_persistent_kill_switch(tmp_path: Path) -> None:
    rec = _rec(tmp_path, trip_on_mismatch=True)
    rec.check(_snap())
    tripped, reason = rec.state.kill_switch_state()
    assert tripped
    assert "BOT_TICKET_MISSING" in reason


def test_observe_only_mode_does_not_trip(tmp_path: Path) -> None:
    rec = _rec(tmp_path)
    assert not rec.check(_snap()).clean
    assert rec.state.kill_switch_state()[0] is False


def test_a_state_failure_is_a_mismatch(tmp_path: Path) -> None:
    rec = _rec(tmp_path, with_position=False)
    conn = sqlite3.connect(rec.state.path)
    conn.execute("DROP TABLE bot_positions")
    conn.commit()
    conn.close()
    assert "STATE_UNAVAILABLE" in rec.check(_snap()).codes


def test_a_closed_position_is_no_longer_expected(tmp_path: Path) -> None:
    rec = _rec(tmp_path)
    rec.state.mark_position_closed("100")
    assert rec.check(_snap()).clean
