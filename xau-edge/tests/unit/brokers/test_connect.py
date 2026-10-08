"""Trading connection: needs its own password, refuses non-demo, never leaks the password."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import SecretStr

from tests.unit.brokers.test_executor import FakeTerminal
from xau_edge.brokers.mt5_demo.connect import (
    Mt5TradeSettings,
    TradeConnectError,
    connect_for_trading,
)
from xau_edge.brokers.mt5_demo.reader import DemoReader
from xau_edge.market_data.broker_clock import BrokerClock


class Terminal(FakeTerminal):
    def __init__(self, *, init_ok: bool = True) -> None:
        super().__init__()
        self.init_ok = init_ok
        self.init_kwargs: dict[str, Any] = {}
        self.shut = False

    def initialize(self, **kwargs: Any) -> bool:
        self.init_kwargs = kwargs
        return self.init_ok

    def shutdown(self) -> None:
        self.shut = True


def _settings(**over: Any) -> Mt5TradeSettings:
    base: dict[str, Any] = {"login": 1, "trade_password": SecretStr("pw"), "server": "S"}
    base.update(over)
    return Mt5TradeSettings(_env_file=None, **base)


def _reader(term: Terminal) -> DemoReader:
    return DemoReader(term, BrokerClock.parse("NY+7"))


def test_connects_with_the_trading_password_to_a_demo_account() -> None:
    term = Terminal()
    connect_for_trading(term, _reader(term), "C:/mt5/terminal64.exe", _settings())
    assert term.init_kwargs["password"] == "pw"
    assert term.init_kwargs["login"] == 1
    assert not term.shut


@pytest.mark.parametrize("missing", ["login", "trade_password", "server"])
def test_every_credential_is_required(missing: str) -> None:
    term = Terminal()
    with pytest.raises(TradeConnectError, match="must all be set"):
        connect_for_trading(term, _reader(term), "x", _settings(**{missing: None}))
    assert term.init_kwargs == {}


def test_a_failed_initialize_is_an_error() -> None:
    term = Terminal(init_ok=False)
    with pytest.raises(TradeConnectError, match="failed"):
        connect_for_trading(term, _reader(term), "x", _settings())


def test_a_non_demo_account_is_disconnected_again() -> None:
    term = Terminal()
    term.trade_mode = 2
    with pytest.raises(TradeConnectError, match="non-DEMO"):
        connect_for_trading(term, _reader(term), "x", _settings())
    assert term.shut


def test_an_account_that_cannot_trade_is_disconnected_again() -> None:
    term = Terminal()
    term.trade_allowed = False
    with pytest.raises(TradeConnectError, match="does not allow trading"):
        connect_for_trading(term, _reader(term), "x", _settings())
    assert term.shut


def test_the_password_is_not_in_the_settings_repr() -> None:
    assert "pw" not in repr(_settings())
