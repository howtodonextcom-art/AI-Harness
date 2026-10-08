"""Read-only view of the MT5 DEMO account: account facts and open positions (ADR-0019).

This package is the only place that may talk to the terminal about positions. The reader reaches
the terminal through an allowlist proxy that exposes ONLY query calls; nothing that can change the
account is reachable through it. It refuses to answer unless the logged-in account is a DEMO
account, and never returns or logs the password.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any, Protocol

import polars as pl

from xau_edge.execution.reconcile import BrokerAccount, BrokerPosition, BrokerSnapshot
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

_QUERY_NAMES = frozenset(
    {
        "initialize",
        "shutdown",
        "last_error",
        "account_info",
        "terminal_info",
        "symbol_info",
        "symbol_info_tick",
        "symbol_select",
        "positions_get",
        "orders_get",
        "ACCOUNT_TRADE_MODE_DEMO",
        "POSITION_TYPE_BUY",
        "POSITION_TYPE_SELL",
    }
)


class DemoAccountError(RuntimeError):
    """The terminal is not logged in to a DEMO account, or the read failed."""


class QueryMt5(Protocol):
    """The query subset of the MetaTrader5 module."""

    def account_info(self) -> Any: ...

    def positions_get(self, **kwargs: Any) -> Any: ...


class QueryOnlyMt5:
    """Allowlist proxy: query calls and constants only (not a sandbox, an accident guard)."""

    def __init__(self, client: Any) -> None:
        self._inner = client

    def __getattr__(self, name: str) -> Any:
        if name in _QUERY_NAMES:
            return getattr(self._inner, name)
        msg = f"{name!r} is not available on the query-only MT5 client"
        raise AttributeError(msg)


class DemoReader:
    """Builds a ``BrokerSnapshot`` from a terminal after checking that it is a DEMO account."""

    def __init__(self, client: Any, clock: BrokerClock, symbol: str = "XAUUSD") -> None:
        self._client = QueryOnlyMt5(client)
        self._clock = clock
        self.symbol = symbol

    def account(self) -> BrokerAccount:
        """The account facts; raises ``DemoAccountError`` unless the account is DEMO."""
        info = self._client.account_info()
        if info is None:
            msg = f"no account is logged in: {self._client.last_error()}"
            raise DemoAccountError(msg)
        if info.trade_mode != self._client.ACCOUNT_TRADE_MODE_DEMO:
            msg = "refusing to read from a non-DEMO account"
            raise DemoAccountError(msg)
        return BrokerAccount(
            account_id=str(info.login),
            is_demo=True,
            balance=float(info.balance),
            equity=float(info.equity),
            trade_allowed=bool(getattr(info, "trade_allowed", True)),
        )

    def _utc(self, epoch_seconds: int) -> datetime:
        naive = datetime.fromtimestamp(epoch_seconds, UTC).replace(tzinfo=None)
        converted = self._clock.server_to_utc(pl.Series([naive], dtype=pl.Datetime("us")))
        value = converted[0]
        if not isinstance(value, datetime):
            msg = "cannot convert the position time to UTC"
            raise DemoAccountError(msg)
        return value

    def positions(self) -> tuple[BrokerPosition, ...]:
        """Open positions on the symbol; ``None`` from the terminal is an error, not 'empty'."""
        rows = self._client.positions_get(symbol=self.symbol)
        if rows is None:
            msg = f"positions_get failed: {self._client.last_error()}"
            raise DemoAccountError(msg)
        buy = self._client.POSITION_TYPE_BUY
        out: list[BrokerPosition] = []
        for r in rows:
            values = (r.volume, r.price_open, r.sl, r.tp)
            if not all(math.isfinite(float(v)) for v in values):
                msg = f"position {r.ticket} has non-finite values"
                raise DemoAccountError(msg)
            out.append(
                BrokerPosition(
                    ticket=str(r.ticket),
                    symbol=str(r.symbol),
                    direction=1 if r.type == buy else -1,
                    lots=float(r.volume),
                    entry_price=float(r.price_open),
                    stop_loss=float(r.sl),
                    take_profit=float(r.tp),
                    magic=int(r.magic),
                    comment=str(r.comment),
                    opened_at=self._utc(int(r.time)),
                )
            )
        return tuple(out)

    def snapshot(self, now: datetime) -> BrokerSnapshot:
        """Account plus positions in one object; any failure raises."""
        snap = BrokerSnapshot(now, self.account(), self.positions())
        log_event(_LOG, "mt5.snapshot", positions=len(snap.positions))
        return snap
