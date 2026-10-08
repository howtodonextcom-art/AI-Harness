"""Read-only view of the MT5 DEMO account: account facts and open positions (ADR-0019).

This package is the only place that may talk to the terminal about positions. The reader reaches
the terminal through an allowlist proxy that exposes ONLY query calls; nothing that can change the
account is reachable through it. It refuses to answer unless the logged-in account is a DEMO
account, and never returns or logs the password.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import polars as pl

from xau_edge.execution.reconcile import (
    BrokerAccount,
    BrokerPosition,
    BrokerSnapshot,
    ClosedResult,
)
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
        "history_deals_get",
        "DEAL_ENTRY_OUT",
        "DEAL_ENTRY_IN",
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


@dataclass(frozen=True)
class EntryDeal:
    """A deal that opened a position."""

    position_id: str
    magic: int
    comment: str
    volume: float
    opened_at: datetime


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
            trade_allowed=bool(getattr(info, "trade_allowed", False)),  # fail closed
        )

    def utc_from_epoch(self, epoch_seconds: int) -> datetime:
        """Server-clock epoch seconds from the terminal -> a true UTC datetime."""
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
                    opened_at=self.utc_from_epoch(int(r.time)),
                )
            )
        return tuple(out)

    def closed_results(self, now: datetime, lookback: timedelta) -> tuple[ClosedResult, ...]:
        """Positions closed in the window, from the deal history (net of commission and swap)."""
        start = self._clock.label_as_utc(now - lookback)
        end = self._clock.label_as_utc(now + timedelta(hours=1))
        deals = self._client.history_deals_get(start, end)
        if deals is None:
            msg = f"history_deals_get failed: {self._client.last_error()}"
            raise DemoAccountError(msg)
        out_entry = self._client.DEAL_ENTRY_OUT
        results: list[ClosedResult] = []
        for deal in deals:
            if deal.entry != out_entry or str(deal.symbol) != self.symbol:
                continue
            net = float(deal.profit) + float(deal.commission) + float(deal.swap)
            if not math.isfinite(net):
                msg = f"deal {deal.ticket} has non-finite values"
                raise DemoAccountError(msg)
            results.append(
                ClosedResult(
                    ticket=str(deal.position_id),
                    closed_at=self.utc_from_epoch(int(deal.time)),
                    profit=net,
                )
            )
        return tuple(results)

    def entry_deals(self, now: datetime, lookback: timedelta) -> tuple[EntryDeal, ...]:
        """Deals that opened a position in the window (used to resolve an unknown order)."""
        start = self._clock.label_as_utc(now - lookback)
        end = self._clock.label_as_utc(now + timedelta(hours=1))
        deals = self._client.history_deals_get(start, end)
        if deals is None:
            msg = f"history_deals_get failed: {self._client.last_error()}"
            raise DemoAccountError(msg)
        entry_in = self._client.DEAL_ENTRY_IN
        return tuple(
            EntryDeal(
                position_id=str(d.position_id),
                magic=int(d.magic),
                comment=str(d.comment),
                volume=float(d.volume),
                opened_at=self.utc_from_epoch(int(d.time)),
            )
            for d in deals
            if d.entry == entry_in and str(d.symbol) == self.symbol
        )

    def snapshot(self, now: datetime, lookback: timedelta = timedelta(days=14)) -> BrokerSnapshot:
        """Account, positions and recent closes in one object; any failure raises."""
        snap = BrokerSnapshot(
            now, self.account(), self.positions(), self.closed_results(now, lookback)
        )
        log_event(_LOG, "mt5.snapshot", positions=len(snap.positions))
        return snap
