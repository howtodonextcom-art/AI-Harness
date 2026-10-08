"""MT5 demo reader against a fake terminal: DEMO-only, query-only, honest about failures."""

from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from xau_edge.brokers.mt5_demo import reader as reader_module
from xau_edge.brokers.mt5_demo.reader import DemoAccountError, DemoReader, QueryOnlyMt5
from xau_edge.market_data.broker_clock import BrokerClock

NOW = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


class FakeMt5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    ACCOUNT_TRADE_MODE_REAL = 2
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1
    DEAL_ENTRY_OUT = 1

    def __init__(self, *, trade_mode: int = 0, positions: Any = (), info: Any = "default") -> None:
        self.calls: list[str] = []
        self._positions = positions
        self._info = (
            SimpleNamespace(login=123456, trade_mode=trade_mode, balance=100000.0, equity=100050.0)
            if info == "default"
            else info
        )

    def account_info(self) -> Any:
        self.calls.append("account_info")
        return self._info

    def positions_get(self, **kwargs: Any) -> Any:
        self.calls.append("positions_get")
        return self._positions

    def last_error(self) -> tuple[int, str]:
        return (1, "boom")

    def history_deals_get(self, start: Any, end: Any) -> Any:
        return ()

    def order_send(self, request: object) -> None:  # must never be reachable
        raise AssertionError("order_send was reached")


def _row(**over: Any) -> Any:
    base: dict[str, Any] = {
        "ticket": 42,
        "symbol": "XAUUSD",
        "type": 0,
        "volume": 0.5,
        "price_open": 2000.0,
        "sl": 1990.0,
        "tp": 2010.0,
        "magic": 7,
        "comment": "XAUEDGE:abc",
        "time": int(datetime(2026, 3, 4, 16, 0, tzinfo=UTC).timestamp()),  # server wall clock
    }
    base.update(over)
    return SimpleNamespace(**base)


def _reader(fake: FakeMt5) -> DemoReader:
    return DemoReader(fake, BrokerClock.parse("NY+7"))


def test_a_demo_account_is_read(tmp_path: object) -> None:
    account = _reader(FakeMt5()).account()
    assert account.is_demo
    assert account.balance == 100000.0
    assert account.account_id == "123456"


def test_a_real_account_is_refused() -> None:
    with pytest.raises(DemoAccountError, match="non-DEMO"):
        _reader(FakeMt5(trade_mode=2)).account()


def test_no_login_is_an_error() -> None:
    with pytest.raises(DemoAccountError, match="no account"):
        _reader(FakeMt5(info=None)).account()


def test_positions_are_converted_with_the_broker_clock() -> None:
    reader = _reader(FakeMt5(positions=(_row(), _row(ticket=43, type=1))))
    first, second = reader.positions()
    assert first.ticket == "42"
    assert first.direction == 1
    assert second.direction == -1
    assert first.magic == 7
    assert first.opened_at.tzinfo is not None
    # 16:00 on a server running at NY+7 (NY is UTC-5 in March before DST): 16:00 - 7h = 09:00 NY
    assert first.opened_at == datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def test_an_empty_book_is_empty_but_a_failed_query_is_an_error() -> None:
    assert _reader(FakeMt5(positions=())).positions() == ()
    with pytest.raises(DemoAccountError, match="positions_get failed"):
        _reader(FakeMt5(positions=None)).positions()


def test_non_finite_position_values_are_an_error() -> None:
    with pytest.raises(DemoAccountError, match="non-finite"):
        _reader(FakeMt5(positions=(_row(sl=float("nan")),))).positions()


def test_the_snapshot_combines_account_and_positions() -> None:
    snap = _reader(FakeMt5(positions=(_row(),))).snapshot(NOW)
    assert snap.account.is_demo
    assert len(snap.positions) == 1


def test_the_query_proxy_cannot_reach_order_functions() -> None:
    proxy = QueryOnlyMt5(FakeMt5())
    for name in ("order_send", "order_check", "positions_close", "login", "history_orders_get"):
        with pytest.raises(AttributeError):
            getattr(proxy, name)
    assert proxy.account_info() is not None


def test_the_demo_adapter_package_uses_only_query_attributes() -> None:
    forbidden = {"order_send", "order_check", "order_calc_margin", "positions_close"}
    root = Path(reader_module.__file__).parent
    used: set[str] = set()
    for path in [root / "reader.py"]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute):
                used.add(node.attr)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                used.add(node.value)
    assert not (used & forbidden), sorted(used & forbidden)


def test_closed_results_come_from_the_deal_history() -> None:
    fake = FakeMt5()
    deal_time = int(datetime(2026, 3, 4, 16, 0, tzinfo=UTC).timestamp())

    def deals(start: Any, end: Any) -> Any:
        keep = SimpleNamespace(
            ticket=1, position_id=42, entry=1, symbol="XAUUSD", profit=10.0, commission=-1.0,
            swap=-0.5, time=deal_time,
        )  # fmt: skip
        opening = SimpleNamespace(
            ticket=2, position_id=42, entry=0, symbol="XAUUSD", profit=0.0, commission=0.0,
            swap=0.0, time=deal_time,
        )  # fmt: skip
        other = SimpleNamespace(
            ticket=3, position_id=7, entry=1, symbol="EURUSD", profit=1.0, commission=0.0,
            swap=0.0, time=deal_time,
        )  # fmt: skip
        return (keep, opening, other)

    fake.history_deals_get = deals  # type: ignore[method-assign]
    results = _reader(fake).closed_results(NOW, timedelta(days=7))
    assert len(results) == 1
    assert results[0].ticket == "42"
    assert results[0].profit == 8.5
    assert results[0].closed_at == datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def test_a_failed_history_query_is_an_error() -> None:
    fake = FakeMt5()
    fake.history_deals_get = lambda start, end: None  # type: ignore[method-assign]
    with pytest.raises(DemoAccountError, match="history_deals_get failed"):
        _reader(fake).closed_results(NOW, timedelta(days=1))


def test_a_missing_trade_allowed_attribute_fails_closed() -> None:
    info = SimpleNamespace(login=1, trade_mode=0, balance=1.0, equity=1.0)
    assert _reader(FakeMt5(info=info)).account().trade_allowed is False
