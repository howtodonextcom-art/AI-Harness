"""Paper broker: bid/ask fills, protective levels, costs, floating equity, journal."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from xau_edge.backtest.costs import CostModel
from xau_edge.execution.interface import ExecutionBroker, Order
from xau_edge.execution.paper import MarketBar, PaperExecutionBroker

T0 = datetime(2026, 3, 2, 10, 0, tzinfo=UTC)
COSTS = CostModel(slippage_points=3.0, swap_long_points=0.0, swap_short_points=0.0)


def _broker(costs: CostModel = COSTS, journal: Path | None = None) -> PaperExecutionBroker:
    b = PaperExecutionBroker(100_000.0, costs=costs, journal_path=journal)
    b.set_quote(T0, bid=100.0, spread_points=20.0)
    return b


def _order(direction: int = 1, **over: object) -> Order:
    base: dict[str, object] = {
        "order_id": "o1",
        "symbol": "XAUUSD",
        "direction": direction,
        "lots": 1.66,
        "stop_loss": 97.23 if direction > 0 else 102.97,
        "take_profit": 106.23 if direction > 0 else 93.97,
        "signal_hash": "abc",
    }
    base.update(over)
    return Order(**base)


def _bar(minutes: int, **over: float) -> MarketBar:
    base = {"open": 100.0, "high": 100.1, "low": 99.9, "close": 100.0, "spread_points": 20.0}
    base.update(over)
    return MarketBar(time=T0 + timedelta(minutes=minutes), **base)


def test_the_paper_broker_satisfies_the_broker_interface() -> None:
    broker: ExecutionBroker = _broker()
    assert broker.get_account().balance == 100_000.0
    assert broker.get_positions() == []


def test_long_fills_at_the_ask_plus_slippage_and_short_at_the_bid_minus_slippage() -> None:
    b = _broker()
    long = b.submit_order(_order(1))
    assert long.entry_price == pytest.approx(100.23)
    short = b.submit_order(_order(-1, order_id="o2"))
    assert short.entry_price == pytest.approx(99.97)
    assert len(b.get_positions()) == 2


def test_target_and_stop_hits_close_with_the_same_fill_rules_as_the_backtest() -> None:
    b = _broker()
    b.submit_order(_order(1))
    closed = b.update_market(_bar(5, high=106.5))
    assert len(closed) == 1
    t = closed[0]
    assert t.reason == "TARGET"
    assert t.exit_price == pytest.approx(106.23)
    assert t.net_pnl == pytest.approx(6.0 * 1.66 * 100)
    assert b.get_account().balance == pytest.approx(100_000 + 996.0)
    assert b.get_positions() == []

    b2 = _broker()
    b2.submit_order(_order(1))
    t2 = b2.update_market(_bar(5, low=96.9))[0]
    assert t2.reason == "STOP"
    assert t2.exit_price == pytest.approx(97.23 - 0.03)


def test_a_bar_touching_both_levels_resolves_to_the_stop_and_gaps_fill_at_the_open() -> None:
    b = _broker()
    b.submit_order(_order(1))
    assert b.update_market(_bar(5, high=110.0, low=90.0))[0].reason == "STOP"
    g = _broker()
    g.submit_order(_order(1))
    gap = g.update_market(_bar(5, open=95.0, high=95.2, low=94.8, close=95.0))[0]
    assert gap.reason == "STOP"
    assert gap.exit_price == pytest.approx(95.0)


def test_short_levels_use_ask_prices() -> None:
    near = _broker()
    near.submit_order(_order(-1))
    assert near.update_market(_bar(5, high=102.7)) == []  # ask high 102.9 < stop 102.97
    hit = _broker()
    hit.submit_order(_order(-1))
    t = hit.update_market(_bar(5, high=102.8))[0]
    assert t.reason == "STOP"
    assert t.exit_price == pytest.approx(102.97 + 0.03)


def test_equity_marks_floating_pnl_against_the_exit_side_of_the_quote() -> None:
    b = _broker()
    b.submit_order(_order(1))
    b.set_quote(T0 + timedelta(minutes=5), bid=101.0, spread_points=20.0)
    assert b.get_account().equity == pytest.approx(100_000 + (101.0 - 100.23) * 1.66 * 100)
    s = _broker()
    s.submit_order(_order(-1))
    s.set_quote(T0 + timedelta(minutes=5), bid=99.0, spread_points=20.0)
    assert s.get_account().equity == pytest.approx(100_000 + (99.97 - 99.20) * 1.66 * 100)


def test_manual_close_uses_the_exit_side_with_slippage() -> None:
    b = _broker()
    p = b.submit_order(_order(1))
    b.set_quote(T0 + timedelta(minutes=5), bid=101.0, spread_points=20.0)
    t = b.close_position(p.position_id, "manual")
    assert t.exit_price == pytest.approx(101.0 - 0.03)
    assert t.reason == "manual"
    assert b.get_positions() == []


def test_time_exit_at_max_hold() -> None:
    b = _broker()
    b.submit_order(_order(1, max_hold_until=T0 + timedelta(minutes=10)))
    assert b.update_market(_bar(5)) == []
    t = b.update_market(_bar(10, close=100.5))[0]
    assert t.reason == "TIME"
    assert t.exit_price == pytest.approx(100.5 - 0.03)


def test_commission_and_swap_are_charged() -> None:
    costs = CostModel(
        slippage_points=3.0,
        commission_per_lot_per_side=3.5,
        swap_long_points=-76.05,
        swap_short_points=-4.2,
    )
    start = datetime(2026, 3, 2, 21, 50, tzinfo=UTC)  # holds across 17:00 New York (22:00 UTC)
    b = PaperExecutionBroker(100_000.0, costs=costs)
    b.set_quote(start, bid=100.0, spread_points=20.0)
    b.submit_order(_order(1))
    b.set_quote(start + timedelta(minutes=30), bid=100.0, spread_points=20.0)
    t = b.close_position("p1", "manual")
    assert t.commission == pytest.approx(2 * 3.5 * 1.66)
    assert t.swap == pytest.approx(-76.05 * 1.66)
    assert t.net_pnl == pytest.approx(t.gross_pnl - t.commission + t.swap)


def test_modify_position_changes_levels_on_the_right_side_only() -> None:
    b = _broker()
    p = b.submit_order(_order(1))
    moved = b.modify_position(p.position_id, stop_loss=99.0)
    assert moved.stop_loss == 99.0
    assert moved.take_profit == p.take_profit
    with pytest.raises(ValueError, match="stop"):
        b.modify_position(p.position_id, stop_loss=101.0)  # above the bid for a long
    with pytest.raises(ValueError, match="take"):
        b.modify_position(p.position_id, take_profit=99.5)
    with pytest.raises(KeyError):
        b.modify_position("nope", stop_loss=99.0)


def test_invalid_orders_are_rejected() -> None:
    b = _broker()
    with pytest.raises(ValueError, match="stop"):
        b.submit_order(_order(1, stop_loss=101.0))
    with pytest.raises(ValueError, match="take"):
        b.submit_order(_order(1, take_profit=100.0))
    with pytest.raises(ValueError, match="symbol"):
        b.submit_order(_order(1, symbol="EURUSD"))
    b.submit_order(_order(1))
    with pytest.raises(ValueError, match="duplicate"):
        b.submit_order(_order(1))
    empty = PaperExecutionBroker(1000.0, costs=COSTS)
    with pytest.raises(RuntimeError, match="quote"):
        empty.submit_order(_order(1))


def test_cancel_has_nothing_to_cancel_for_immediate_fills() -> None:
    assert _broker().cancel_order("o1") is False


def test_unknown_position_close_is_an_error() -> None:
    with pytest.raises(KeyError):
        _broker().close_position("nope", "manual")


def test_every_event_is_journalled_with_the_signal_hash(tmp_path: Path) -> None:
    path = tmp_path / "paper.jsonl"
    b = _broker(journal=path)
    b.submit_order(_order(1))
    b.update_market(_bar(5, high=106.5))
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [e["event"] for e in events] == ["order.filled", "position.closed"]
    assert all(e["signal_hash"] == "abc" for e in events)
    assert events[1]["reason"] == "TARGET"
    json.dumps(events, allow_nan=False)


def test_journal_records_carry_the_mode(tmp_path: Path) -> None:
    path = tmp_path / "j.jsonl"
    b = PaperExecutionBroker(100_000.0, costs=COSTS, journal_path=path, mode="replay")
    b.set_quote(T0, bid=100.0, spread_points=20.0)
    b.submit_order(_order(1))
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["mode"] == "replay"
    assert PaperExecutionBroker(1.0, costs=COSTS).mode == "forward"


def test_a_short_stop_must_clear_the_ask_not_just_the_bid() -> None:
    b = _broker()
    p = b.submit_order(_order(-1))
    with pytest.raises(ValueError, match="stop"):
        b.modify_position(
            p.position_id, stop_loss=100.1
        )  # above the bid 100.0, below the ask 100.2
    assert b.modify_position(p.position_id, stop_loss=100.5).stop_loss == 100.5


def test_non_finite_order_values_are_rejected() -> None:
    for field in ("lots", "stop_loss", "take_profit"):
        with pytest.raises(ValidationError):
            _order(1, **{field: float("inf")})


def test_short_target_needs_the_ask_to_reach_it() -> None:
    near = _broker()
    near.submit_order(_order(-1))
    assert near.update_market(_bar(5, low=93.8)) == []  # bid 93.8 but ask 94.0 > target 93.97
    hit = _broker()
    hit.submit_order(_order(-1))
    assert hit.update_market(_bar(5, low=93.7))[0].reason == "TARGET"  # ask 93.9 <= 93.97
