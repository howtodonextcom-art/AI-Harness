"""MT5 demo executor against a fake terminal: every gate, exactly-once, unknown states, closing."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.execution.test_bridge import _account, _bridge, _buy
from xau_edge.brokers.mt5_demo import executor as executor_module
from xau_edge.brokers.mt5_demo.executor import (
    SMOKE_COMMENT,
    ExecutorConfig,
    Mt5DemoExecutor,
    SubmitResult,
    TradeMt5,
    build_smoke_intent,
)
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.order_intent import OrderIntent
from xau_edge.execution.reconcile import Reconciler
from xau_edge.execution.state import ExecutionState
from xau_edge.market_data.broker_clock import BrokerClock

T = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)
MAGIC = 7
LOGIN = "555"


class FakeTerminal:
    """A scripted terminal: records calls, can fill, reject, stay silent or raise."""

    ACCOUNT_TRADE_MODE_DEMO = 0
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2
    SYMBOL_TRADE_MODE_FULL = 4
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008
    DEAL_ENTRY_OUT = 1
    DEAL_ENTRY_IN = 0

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.checked: list[dict[str, Any]] = []
        self.positions: list[SimpleNamespace] = []
        self.trade_mode = 0
        self.trade_allowed = True
        self.send_behaviour = "done"  # done | reject | none | raise
        self.fill_on_done = True
        self.check_retcode = 0
        self.symbol_trade_mode = 4
        self.volume = (0.01, 100.0, 0.01)
        self.ask = 2000.2
        self.bid = 2000.0
        self.close_removes = True
        self.balance = 100000.0
        self.equity = 100000.0
        self.stops_level = 0
        self.freeze_level = 0
        self.tick_time = int((T + timedelta(hours=2)).timestamp())  # server clock is UTC+2
        self.deals: list[SimpleNamespace] = []
        self._next = 1000

    # queries
    def account_info(self) -> Any:
        return SimpleNamespace(
            login=int(LOGIN),
            trade_mode=self.trade_mode,
            balance=self.balance,
            equity=self.equity,
            trade_allowed=self.trade_allowed,
        )

    def last_error(self) -> tuple[int, str]:
        return (1, "x")

    def positions_get(self, **kwargs: Any) -> Any:
        return tuple(self.positions)

    def history_deals_get(self, start: Any, end: Any) -> Any:
        return tuple(self.deals)

    def symbol_info(self, symbol: str) -> Any:
        low, high, step = self.volume
        return SimpleNamespace(
            trade_mode=self.symbol_trade_mode,
            volume_min=low,
            volume_max=high,
            volume_step=step,
            point=0.01,
            digits=2,
            trade_stops_level=self.stops_level,
            trade_freeze_level=self.freeze_level,
            filling_mode=2,
        )

    def symbol_info_tick(self, symbol: str) -> Any:
        return SimpleNamespace(ask=self.ask, bid=self.bid, time=self.tick_time)

    # trading
    def order_check(self, request: dict[str, Any]) -> Any:
        self.checked.append(request)
        return SimpleNamespace(retcode=self.check_retcode)

    def order_send(self, request: dict[str, Any]) -> Any:
        self.sent.append(request)
        if self.send_behaviour == "raise":
            raise ConnectionError("terminal gone")
        if self.send_behaviour == "none":
            return None
        if self.send_behaviour == "reject":
            return SimpleNamespace(retcode=10006, order=0)
        if "position" in request:
            if self.close_removes:
                self.positions = [p for p in self.positions if p.ticket != request["position"]]
                self.deals.append(
                    SimpleNamespace(
                        ticket=900 + len(self.deals),
                        position_id=request["position"],
                        entry=1,
                        symbol="XAUUSD",
                        profit=-5.0,
                        commission=0.0,
                        swap=0.0,
                        time=int(T.timestamp()),
                    )
                )
            return SimpleNamespace(retcode=10009, order=request["position"])
        self._next += 1
        if self.fill_on_done:
            self.positions.append(
                SimpleNamespace(
                    ticket=self._next,
                    symbol=request["symbol"],
                    type=request["type"],
                    volume=request["volume"],
                    price_open=request["price"],
                    sl=request["sl"],
                    tp=request["tp"],
                    magic=request["magic"],
                    comment=request["comment"],
                    time=int(T.timestamp()),
                )
            )
        return SimpleNamespace(retcode=10009, order=self._next)


def _intent(**over: Any) -> OrderIntent:
    base: dict[str, Any] = {
        "intent_id": "a" * 32,
        "signal_hash": "h" * 16,
        "symbol": "XAUUSD",
        "direction": 1,
        "lots": 0.5,
        "risk_amount": 300.0,
        "entry_reference": 2000.2,
        "stop_loss": 1990.0,
        "take_profit": 2015.0,
        "max_hold_until": T + timedelta(hours=5),
        "decision_time": T,
        "created_at": T,
        "magic": MAGIC,
        "comment": "XAUEDGE:" + "a" * 12,
        "dry_run": False,
    }
    base.update(over)
    return OrderIntent(**base)


def _config(**over: Any) -> ExecutorConfig:
    base: dict[str, Any] = {
        "enabled": True,
        "dry_run": False,
        "allowed_accounts": (LOGIN,),
        "symbols": ("XAUUSD",),
        "magic": MAGIC,
        "max_lots": 1.0,
    }
    base.update(over)
    return ExecutorConfig(**base)


def _make(
    tmp_path: Path, term: FakeTerminal | None = None, **cfg: Any
) -> tuple[Mt5DemoExecutor, FakeTerminal]:
    term = term or FakeTerminal()
    state = ExecutionState(tmp_path / "s.sqlite")
    reader = DemoReader(term, BrokerClock.parse("NY+7"))
    reconciler = Reconciler(state, magic=MAGIC, allowed_accounts=(LOGIN,), trip_on_mismatch=True)
    journal = ExecutionJournal(tmp_path / "j.jsonl")
    sleeps: list[float] = []
    executor = Mt5DemoExecutor(
        term, reader, state, journal, reconciler, _config(**cfg), sleep=sleeps.append
    )
    executor.sleeps = sleeps  # type: ignore[attr-defined]
    return executor, term


def _go(ex: Mt5DemoExecutor, intent: OrderIntent, now: datetime) -> SubmitResult:
    """Approve the intent the way the bridge would, then submit it."""
    if not ex.state.is_approved(intent.intent_id):
        ex.state.record_accepted(
            signal_hash=intent.signal_hash,
            intent_id=intent.intent_id,
            decision_time=intent.decision_time,
            day="d",
            dry_run=False,
            max_orders_per_day=99,
        )
    return ex.submit(intent, now)


def test_a_valid_intent_is_sent_once_with_every_protective_field(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert len(term.sent) == 1
    req = term.sent[0]
    assert req["sl"] == 1990.0
    assert req["tp"] == 2015.0
    assert req["magic"] == MAGIC
    assert req["comment"].startswith("XAUEDGE:")
    assert req["type"] == term.ORDER_TYPE_BUY
    assert req["price"] == 2000.2  # the ask for a buy
    assert len(term.checked) == 1
    assert term.checked[0] == req
    assert ex.state.open_positions()[0].ticket == result.ticket
    assert ex.state.unresolved_submissions() == []
    events = [e["event"] for e in ex.journal.read()]
    assert events == ["order.requested", "order.answered", "position.opened"]


@pytest.mark.parametrize(
    ("cfg", "reason"),
    [
        ({"enabled": False}, "DEMO_TRADING_DISABLED"),
        ({"dry_run": True}, "DRY_RUN"),
        ({"allowed_accounts": ()}, "NO_ACCOUNT_WHITELIST"),
        ({"magic": None}, "MAGIC_NOT_CONFIGURED"),
        ({"allowed_accounts": ("999",)}, "ACCOUNT_NOT_WHITELISTED"),
        ({"symbols": ("EURUSD",)}, "SYMBOL_NOT_WHITELISTED"),
        ({"max_lots": 0.1}, "LOTS_ABOVE_MAXIMUM"),
    ],
)
def test_configuration_and_intent_gates_refuse_before_anything_is_sent(
    tmp_path: Path, cfg: dict[str, Any], reason: str
) -> None:
    ex, term = _make(tmp_path, **cfg)
    result = _go(ex, _intent(), T)
    assert result.status == "REFUSED"
    assert reason in result.reasons
    assert term.sent == []
    assert term.checked == []


def test_a_dry_run_intent_and_a_foreign_magic_are_refused(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    assert "INTENT_IS_DRY_RUN" in _go(ex, _intent(dry_run=True), T).reasons
    assert "MAGIC_MISMATCH" in _go(ex, _intent(magic=8), T).reasons
    assert term.sent == []


def test_a_tripped_kill_switch_blocks_opening(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    ex.state.trip_kill_switch("stop")
    assert "KILL_SWITCH" in _go(ex, _intent(), T).reasons
    assert term.sent == []


def test_a_non_demo_account_is_refused(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.trade_mode = 2
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "REFUSED"
    assert term.sent == []


def test_disallowed_terminal_trading_is_refused(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.trade_allowed = False
    ex, term = _make(tmp_path, term)
    assert "TRADING_NOT_ALLOWED" in _go(ex, _intent(), T).reasons
    assert term.sent == []


def test_a_dirty_reconciliation_refuses_and_trips_the_kill_switch(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.positions.append(
        SimpleNamespace(
            ticket=1, symbol="XAUUSD", type=0, volume=0.1, price_open=2000.0, sl=0.0, tp=0.0,
            magic=0, comment="manual", time=int(T.timestamp()),
        )
    )  # fmt: skip
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert "RECONCILE_MANUAL_POSITION_SAME_SYMBOL" in result.reasons
    assert term.sent == []
    assert ex.state.kill_switch_state()[0] is True


@pytest.mark.parametrize(
    ("attr", "value", "reason"),
    [
        ("symbol_trade_mode", 0, "SYMBOL_NOT_TRADABLE"),
        ("volume", (1.0, 100.0, 1.0), "VOLUME_OUT_OF_RANGE"),
        ("volume", (0.01, 100.0, 0.2), "VOLUME_NOT_ON_STEP"),
        ("ask", 2100.0, "ENTRY_PRICE_MOVED"),
    ],
)
def test_market_gates_refuse_before_sending(
    tmp_path: Path, attr: str, value: Any, reason: str
) -> None:
    term = FakeTerminal()
    setattr(term, attr, value)
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.reasons == (reason,)
    assert term.sent == []
    assert ex.state.unresolved_submissions() == []  # refused before the submission row


def test_a_failed_order_check_is_a_rejection_and_nothing_is_sent(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.check_retcode = 10019
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "REJECTED"
    assert term.sent == []
    assert ex.state.open_positions() == []


def test_the_same_intent_is_never_sent_twice_even_after_its_position_is_closed(
    tmp_path: Path,
) -> None:
    ex, term = _make(tmp_path)
    first = _go(ex, _intent(), T)
    assert first.status == "FILLED"
    assert first.ticket is not None
    assert _go(ex, _intent(), T).reasons == ("BOT_POSITION_ALREADY_OPEN",)
    assert ex.close_position(first.ticket, "test").status == "FILLED"
    again = _go(ex, _intent(), T)
    assert again.status == "REFUSED"
    assert again.reasons == ("DUPLICATE_SUBMISSION",)
    assert len(term.sent) == 2  # the order and its close, nothing more


def test_a_rejected_order_is_not_retried_automatically(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.send_behaviour = "reject"
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "REJECTED"
    assert result.retcode == 10006
    assert ex.state.open_positions() == []
    term.send_behaviour = "done"
    assert _go(ex, _intent(), T).reasons == ("DUPLICATE_SUBMISSION",)
    assert len(term.sent) == 1


@pytest.mark.parametrize("behaviour", ["none", "raise"])
def test_no_answer_and_the_position_missing_means_unknown_and_the_kill_switch_trips(
    tmp_path: Path, behaviour: str
) -> None:
    term = FakeTerminal()
    term.send_behaviour = behaviour
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True
    assert "UNKNOWN_ORDER_STATE" in ex.state.kill_switch_state()[1]
    assert len(term.sent) == 1  # never retried
    assert ex.state.unresolved_submissions() == [_intent().intent_id]
    assert _go(ex, _intent(), T).status == "REFUSED"
    assert len(term.sent) == 1


def test_no_answer_but_the_position_exists_is_resolved_without_tripping(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.send_behaviour = "raise"
    original = term.order_send

    def send_then_fail(request: dict[str, Any]) -> Any:
        term.send_behaviour = "done"
        original(request)  # the order really went through
        term.send_behaviour = "raise"
        raise ConnectionError("answer lost")

    term.order_send = send_then_fail  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert ex.state.kill_switch_state()[0] is False
    assert len(ex.state.open_positions()) == 1


def test_done_but_the_position_cannot_be_found_is_unknown(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.fill_on_done = False
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True


def test_closing_a_bot_position_works_even_when_the_kill_switch_is_tripped(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    ticket = _go(ex, _intent(), T).ticket
    assert ticket is not None
    ex.state.trip_kill_switch("stop")
    result = ex.close_position(ticket, "manual")
    assert result.status == "FILLED"
    close = term.sent[-1]
    assert close["position"] == int(ticket)
    assert close["type"] == term.ORDER_TYPE_SELL
    assert ex.state.open_positions() == []
    assert [e["event"] for e in ex.journal.read()][-2:] == ["position.closing", "position.closed"]


def test_only_bot_positions_can_be_closed(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.positions.append(
        SimpleNamespace(
            ticket=77, symbol="XAUUSD", type=0, volume=0.1, price_open=2000.0, sl=0.0, tp=0.0,
            magic=0, comment="manual", time=int(T.timestamp()),
        )
    )  # fmt: skip
    ex, term = _make(tmp_path, term)
    assert ex.close_position("77", "x").reasons == ("NOT_A_BOT_POSITION",)
    assert term.sent == []


def test_a_close_that_leaves_the_position_open_is_unknown_and_trips(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    ticket = _go(ex, _intent(), T).ticket
    assert ticket is not None
    term.close_removes = False
    assert ex.close_position(ticket, "x").status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True


def test_expired_positions_are_closed_and_fresh_ones_are_kept(tmp_path: Path) -> None:
    ex, _ = _make(tmp_path)
    _go(ex, _intent(), T)
    assert ex.close_expired(T + timedelta(hours=1)) == []
    results = ex.close_expired(T + timedelta(hours=6))
    assert [r.status for r in results] == ["FILLED"]
    assert ex.state.open_positions() == []


def test_smoke_is_off_by_default(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    smoke = _intent(comment=SMOKE_COMMENT, lots=0.01)
    assert ex.submit_smoke(smoke, T).reasons == ("SMOKE_DISABLED",)
    assert term.sent == []


def test_smoke_orders_must_be_labelled_and_minimum_lot(tmp_path: Path) -> None:
    ex, term = _make(tmp_path, smoke=True)
    assert ex.submit_smoke(_intent(), T).reasons == ("NOT_A_SMOKE_INTENT",)
    assert "SMOKE_LOT_TOO_LARGE" in ex.submit_smoke(_intent(comment=SMOKE_COMMENT), T).reasons
    assert term.sent == []
    assert ex.submit_smoke(_intent(comment=SMOKE_COMMENT, lots=0.01), T).status == "FILLED"
    assert term.sent[0]["comment"] == SMOKE_COMMENT


def test_order_send_has_exactly_one_call_site_inside_the_guarded_function() -> None:
    root = Path(executor_module.__file__).parent
    sites: list[tuple[str, str]] = []
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef):
                for node in ast.walk(fn):
                    if isinstance(node, ast.Attribute) and node.attr == "order_send":
                        sites.append((path.name, fn.name))
    assert sites == [("executor.py", "_guarded_send")]


def test_the_proxy_exposes_no_other_trading_or_account_changing_call() -> None:
    proxy = TradeMt5(FakeTerminal())
    for name in ("positions_close", "login", "history_deals_get", "order_calc_profit", "shutdown"):
        with pytest.raises(AttributeError):
            getattr(proxy, name)


def _position(ticket: int, magic: int) -> SimpleNamespace:
    return SimpleNamespace(
        ticket=ticket, symbol="XAUUSD", type=0, volume=0.5, price_open=2000.2, sl=1990.0,
        tp=2015.0, magic=magic, comment="XAUEDGE:x", time=int(T.timestamp()),
    )  # fmt: skip


def test_a_position_with_the_bot_magic_but_unknown_to_the_state_is_not_closed(
    tmp_path: Path,
) -> None:
    term = FakeTerminal()
    term.positions.append(_position(88, MAGIC))
    ex, term = _make(tmp_path, term)
    assert ex.close_position("88", "x").reasons == ("NOT_A_BOT_POSITION",)
    assert term.sent == []


def test_a_state_position_whose_broker_magic_differs_is_not_closed(tmp_path: Path) -> None:
    term = FakeTerminal()
    ex, term = _make(tmp_path, term)
    ticket = _go(ex, _intent(), T).ticket
    assert ticket is not None
    for p in term.positions:
        p.magic = 999  # someone else's position now carries this ticket
    sent_before = len(term.sent)
    assert ex.close_position(ticket, "x").reasons == ("NOT_A_BOT_POSITION",)
    assert len(term.sent) == sent_before


def test_the_smoke_intent_is_labelled_minimum_lot_and_has_protective_levels() -> None:
    intent = build_smoke_intent(2000.0, T, magic=MAGIC)
    assert intent.comment == SMOKE_COMMENT
    assert intent.lots == 0.01
    assert intent.stop_loss < 2000.0 < intent.take_profit
    assert intent.dry_run is False
    assert intent.signal_hash.startswith("SMOKE-")


def test_an_intent_the_bridge_never_approved_is_refused(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    result = ex.submit(_intent(), T)
    assert "NOT_APPROVED_BY_BRIDGE" in result.reasons
    assert term.sent == []


def test_a_dry_run_approval_does_not_count(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    ex.state.record_accepted(
        signal_hash="h" * 16, intent_id="a" * 32, decision_time=T, day="d", dry_run=True,
        max_orders_per_day=9,
    )  # fmt: skip
    assert "NOT_APPROVED_BY_BRIDGE" in ex.submit(_intent(), T).reasons
    assert term.sent == []


def test_stale_and_expired_intents_are_refused(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    assert "INTENT_STALE" in _go(ex, _intent(), T + timedelta(hours=1)).reasons
    assert (
        "INTENT_EXPIRED"
        in _go(
            ex, _intent(intent_id="b" * 32, signal_hash="z" * 16), T + timedelta(hours=6)
        ).reasons
    )
    assert term.sent == []


def test_a_stale_tick_is_refused(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.tick_time = int((T - timedelta(minutes=10)).timestamp()) + 7200
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).reasons == ("TICK_STALE",)
    assert term.sent == []


def test_the_price_limit_uses_the_symbols_own_point(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.ask = 2000.2 + 0.25  # 25 points of 0.01 away: within 30 points
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "FILLED"


def test_only_one_bot_position_may_be_open(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    assert _go(ex, _intent(), T).status == "FILLED"
    second = _go(ex, _intent(intent_id="c" * 32, signal_hash="g" * 16), T)
    assert "BOT_POSITION_ALREADY_OPEN" in second.reasons
    assert len(term.sent) == 1


def test_the_kill_switch_tripped_after_the_gates_still_stops_the_send(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    original = ex.state.begin_submission

    def begin_then_trip(intent_id: str, signal_hash: str) -> None:
        original(intent_id, signal_hash)
        ex.state.trip_kill_switch("tripped in the window")

    ex.state.begin_submission = begin_then_trip  # type: ignore[method-assign]
    result = _go(ex, _intent(), T)
    assert result.status == "REFUSED"
    assert "KILL_SWITCH" in result.reasons
    assert term.sent == []
    assert ex.state.unresolved_submissions() == []


def test_a_partial_fill_is_registered_with_the_real_volume(tmp_path: Path) -> None:
    term = FakeTerminal()
    original = term.order_send

    def partial(request: dict[str, Any]) -> Any:
        result = original(request)
        term.positions[-1].volume = 0.2
        result.retcode = 10010
        return result

    term.order_send = partial  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert ex.state.open_positions()[0].lots == 0.2


@pytest.mark.parametrize("retcode", [10012, 10031])
def test_an_ambiguous_retcode_is_resolved_by_lookup_not_assumed_rejected(
    tmp_path: Path, retcode: int
) -> None:
    term = FakeTerminal()
    original = term.order_send

    def ambiguous(request: dict[str, Any]) -> Any:
        result = original(request)  # the order really executed
        result.retcode = retcode
        return result

    term.order_send = ambiguous  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert len(ex.state.open_positions()) == 1


def test_an_ambiguous_retcode_with_no_position_is_unknown(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.fill_on_done = False
    original = term.order_send

    def ambiguous(request: dict[str, Any]) -> Any:
        result = original(request)
        result.retcode = 10012
        return result

    term.order_send = ambiguous  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True


def test_a_malformed_answer_after_sending_cannot_escape_unresolved(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.order_send = lambda request: SimpleNamespace(retcode="garbage")  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True


def test_a_broker_that_strips_the_stop_is_closed_at_once_and_stops_the_bot(
    tmp_path: Path,
) -> None:
    term = FakeTerminal()
    original = term.order_send

    def strip_stop(request: dict[str, Any]) -> Any:
        result = original(request)
        if "position" not in request:
            term.positions[-1].sl = 0.0
        return result

    term.order_send = strip_stop  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.reasons == ("PROTECTION_MISMATCH",)
    assert term.positions == []  # closed straight away
    assert ex.state.open_positions() == []
    assert ex.state.kill_switch_state()[0] is True
    assert "PROTECTION_MISMATCH" in ex.state.kill_switch_state()[1]


def test_a_duplicate_is_journalled_as_refused(tmp_path: Path) -> None:
    ex, _ = _make(tmp_path)
    first = _go(ex, _intent(), T)
    assert first.ticket is not None
    ex.close_position(first.ticket, "test")
    _go(ex, _intent(), T)
    events = [(e["event"], e.get("reasons")) for e in ex.journal.read()]
    assert ("order.refused", ["DUPLICATE_SUBMISSION"]) in events


def test_levels_not_on_the_symbols_tick_are_refused(tmp_path: Path) -> None:
    ex, term = _make(tmp_path)
    result = _go(ex, _intent(stop_loss=1990.123), T)
    assert result.reasons == ("LEVELS_NOT_ON_TICK",)
    assert term.sent == []


def test_stops_closer_than_the_brokers_stop_level_are_refused(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.stops_level = 2000  # 20.00 in price units for a 0.01 point
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)  # stop is only 10.2 away
    assert result.reasons == ("STOPS_TOO_CLOSE",)
    assert term.sent == []


def test_a_position_inside_the_freeze_level_is_not_closed_but_not_treated_as_unknown(
    tmp_path: Path,
) -> None:
    ex, term = _make(tmp_path)
    ticket = _go(ex, _intent(), T).ticket
    assert ticket is not None
    term.freeze_level = 100000  # everything is frozen
    result = ex.close_position(ticket, "x")
    assert result.status == "REFUSED"
    assert result.reasons == ("POSITION_FROZEN",)
    assert ex.state.kill_switch_state()[0] is False
    assert len(term.sent) == 1  # only the opening order


def test_a_buy_from_a_signal_fills_with_the_real_31_point_spread(tmp_path: Path) -> None:
    """Regression for blocker c2: entry was a bid compared with an ask and always moved."""
    bridge = _bridge(tmp_path / "b")
    signal = _buy()
    result = bridge.process(signal, T, account=_account(), spread_points=31.0)
    assert result.intent is not None
    term = FakeTerminal()
    term.bid = 2000.0
    term.ask = 2000.31
    ex, term = _make(tmp_path, term)
    ex.state.record_accepted(
        signal_hash=result.intent.signal_hash,
        intent_id=result.intent.intent_id,
        decision_time=T,
        day="d",
        dry_run=False,
        max_orders_per_day=9,
    )
    intent = result.intent.model_copy(update={"dry_run": False})
    assert ex.submit(intent, T).status == "FILLED"
    assert term.sent[0]["price"] == 2000.31


def test_an_unknown_order_is_polled_before_the_kill_switch_trips(tmp_path: Path) -> None:
    """T2.4: the answer was lost, the position shows up a moment later."""
    term = FakeTerminal()
    term.send_behaviour = "none"
    ex, term = _make(tmp_path, term)
    original_positions = term.positions_get
    late = _position(4242, MAGIC)
    late.comment = "XAUEDGE:" + "a" * 12

    def late_positions(**kwargs: Any) -> Any:
        if len(ex.sleeps) >= 2 and late not in term.positions:  # type: ignore[attr-defined]
            term.positions.append(late)
        return original_positions(**kwargs)

    term.positions_get = late_positions  # type: ignore[method-assign]
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert ex.state.kill_switch_state()[0] is False
    assert len(ex.sleeps) == 2  # type: ignore[attr-defined]
    assert len(term.sent) == 1  # never retried


def test_an_order_that_filled_and_closed_at_once_is_found_in_the_deal_history(
    tmp_path: Path,
) -> None:
    term = FakeTerminal()
    term.send_behaviour = "none"
    term.deals.append(
        SimpleNamespace(
            ticket=1, position_id=777, entry=0, symbol="XAUUSD", magic=MAGIC,
            comment="XAUEDGE:" + "a" * 12, volume=0.5, profit=0.0, commission=0.0, swap=0.0,
            time=int((T + timedelta(hours=2)).timestamp()),
        )
    )  # fmt: skip
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "FILLED"
    assert result.reasons == ("ALREADY_CLOSED",)
    assert ex.state.open_positions() == []
    assert ex.state.kill_switch_state()[0] is False


def test_an_unknown_order_that_never_appears_polls_then_trips(tmp_path: Path) -> None:
    term = FakeTerminal()
    term.send_behaviour = "none"
    ex, term = _make(tmp_path, term)
    result = _go(ex, _intent(), T)
    assert result.status == "UNKNOWN"
    assert ex.state.kill_switch_state()[0] is True
    assert len(ex.sleeps) == 5  # type: ignore[attr-defined]  # 15 s resolution / 3 s poll
    assert len(term.sent) == 1


def test_a_partial_fill_is_never_topped_up(tmp_path: Path) -> None:
    """T2.6: the real volume is recorded and no second order is sent."""
    term = FakeTerminal()
    original = term.order_send

    def partial(request: dict[str, Any]) -> Any:
        result = original(request)
        term.positions[-1].volume = 0.2
        result.retcode = 10010
        return result

    term.order_send = partial  # type: ignore[method-assign]
    ex, term = _make(tmp_path, term)
    assert _go(ex, _intent(), T).status == "FILLED"
    assert len(term.sent) == 1
    assert ex.reconciler.check(ex.reader.snapshot(T)).clean  # reconciles with the real volume
