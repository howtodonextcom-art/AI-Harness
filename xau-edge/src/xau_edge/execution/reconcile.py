"""Reconciliation: compare what the broker holds with what the bot believes (ADR-0019).

The broker is the source of truth for what exists; the persistent state is the source of truth for
what the bot did. Any difference means the bot cannot trust its own picture, so nothing new may be
submitted. With ``trip_on_mismatch`` the persistent kill switch is tripped as well (the executor
uses it; the read-only dry-run reports instead). The module is broker-neutral: an adapter turns
its terminal's data into a ``BrokerSnapshot``.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from xau_edge.execution.state import BotPositionRecord, ExecutionState, StateError
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class BrokerAccount:
    """Account facts needed for reconciliation (identifiers are compared, never logged)."""

    account_id: str
    is_demo: bool
    balance: float
    equity: float
    trade_allowed: bool = True


@dataclass(frozen=True)
class BrokerPosition:
    """An open position as the broker reports it."""

    ticket: str
    symbol: str
    direction: Literal[-1, 1]
    lots: float
    entry_price: float
    stop_loss: float
    take_profit: float
    magic: int
    comment: str
    opened_at: datetime


@dataclass(frozen=True)
class ClosedResult:
    """A position the broker has closed (by stop, target or request) and its net result."""

    ticket: str
    closed_at: datetime
    profit: float


def trailing_losses(closed: tuple[ClosedResult, ...], bot_tickets: set[str]) -> int:
    """How many of the bot's most recent closed trades in a row lost money."""
    mine = sorted((c for c in closed if c.ticket in bot_tickets), key=lambda c: c.closed_at)
    count = 0
    for result in reversed(mine):
        if result.profit >= 0:
            break
        count += 1
    return count


@dataclass(frozen=True)
class BrokerSnapshot:
    """One consistent read of the broker."""

    taken_at: datetime
    account: BrokerAccount
    positions: tuple[BrokerPosition, ...]
    closed: tuple[ClosedResult, ...] = ()


@dataclass(frozen=True)
class Mismatch:
    """One difference found by reconciliation."""

    code: str
    detail: str


@dataclass(frozen=True)
class ReconcileResult:
    """Outcome: clean only when no difference was found."""

    clean: bool
    mismatches: tuple[Mismatch, ...]

    @property
    def codes(self) -> tuple[str, ...]:
        """Distinct mismatch codes, in the order found."""
        return tuple(dict.fromkeys(m.code for m in self.mismatches))


def _finite_positive(*values: float) -> bool:
    return all(math.isfinite(v) and v > 0 for v in values)


class Reconciler:
    """Checks a broker snapshot against the persistent state."""

    def __init__(
        self,
        state: ExecutionState,
        *,
        magic: int | None,
        symbols: tuple[str, ...] = ("XAUUSD",),
        allowed_accounts: tuple[str, ...] = (),
        trip_on_mismatch: bool = False,
        price_tolerance: float = 0.005,
        lot_tolerance: float = 1e-9,
    ) -> None:
        self.state = state
        self.magic = magic
        self.symbols = symbols
        self.allowed_accounts = allowed_accounts
        self.trip_on_mismatch = trip_on_mismatch
        self.price_tolerance = price_tolerance
        self.lot_tolerance = lot_tolerance

    def check(self, snapshot: BrokerSnapshot) -> ReconcileResult:
        """Compare; a state error is itself a mismatch (``STATE_UNAVAILABLE``)."""
        found: list[Mismatch] = []
        self._check_account(snapshot.account, found)
        try:
            records = {r.ticket: r for r in self.state.open_positions()}
        except StateError as exc:
            found.append(Mismatch("STATE_UNAVAILABLE", str(exc)))
            records = {}
        else:
            self._check_positions(snapshot, records, found)
            try:
                pending = self.state.unresolved_submissions()
            except StateError as exc:
                found.append(Mismatch("STATE_UNAVAILABLE", str(exc)))
                pending = []
            found.extend(
                Mismatch("UNRESOLVED_SUBMISSION", f"intent {i[:12]} has no final outcome")
                for i in pending
            )
        result = ReconcileResult(not found, tuple(found))
        if not result.clean:
            log_event(_LOG, "reconcile.mismatch", logging.ERROR, codes=list(result.codes))
            if self.trip_on_mismatch:
                self._trip(result)
        return result

    def _trip(self, result: ReconcileResult) -> None:
        try:
            self.state.trip_kill_switch("RECONCILIATION: " + ",".join(result.codes))
        except StateError as exc:
            log_event(_LOG, "reconcile.trip_failed", logging.CRITICAL, error=str(exc))

    def _check_account(self, account: BrokerAccount, found: list[Mismatch]) -> None:
        if not account.is_demo:
            found.append(
                Mismatch("ACCOUNT_NOT_DEMO", "the connected account is not a DEMO account")
            )
        if not _finite_positive(account.balance, account.equity):
            found.append(Mismatch("ACCOUNT_EQUITY_INVALID", "balance or equity is not usable"))
        if self.allowed_accounts and account.account_id not in self.allowed_accounts:
            found.append(Mismatch("ACCOUNT_NOT_WHITELISTED", "the account is not in the whitelist"))

    def _check_positions(
        self,
        snapshot: BrokerSnapshot,
        records: dict[str, BotPositionRecord],
        found: list[Mismatch],
    ) -> None:
        seen: set[str] = set()
        for pos in snapshot.positions:
            if pos.symbol not in self.symbols:
                continue
            seen.add(pos.ticket)
            record = records.get(pos.ticket)
            if self.magic is not None and pos.magic == self.magic:
                if record is None:
                    found.append(
                        Mismatch("UNKNOWN_BOT_POSITION", f"ticket {pos.ticket} has the bot magic")
                    )
                else:
                    self._compare(pos, record, found)
            else:
                found.append(
                    Mismatch(
                        "MANUAL_POSITION_SAME_SYMBOL",
                        f"ticket {pos.ticket} on {pos.symbol} was not opened by the bot",
                    )
                )
        closed_tickets = {c.ticket for c in snapshot.closed}
        for ticket in records:
            if ticket in seen:
                continue
            if ticket in closed_tickets:  # the broker closed it (stop, target): a normal event
                try:
                    self.state.mark_position_closed(ticket)
                except StateError as exc:
                    found.append(Mismatch("STATE_UNAVAILABLE", str(exc)))
            else:
                found.append(Mismatch("BOT_TICKET_MISSING", f"ticket {ticket} is not open"))

    def _compare(
        self, pos: BrokerPosition, record: BotPositionRecord, found: list[Mismatch]
    ) -> None:
        if pos.direction != record.direction:
            found.append(Mismatch("DIRECTION_MISMATCH", f"ticket {pos.ticket}"))
        if abs(pos.lots - record.lots) > self.lot_tolerance:
            found.append(Mismatch("LOT_MISMATCH", f"ticket {pos.ticket}"))
        if abs(pos.stop_loss - record.stop_loss) > self.price_tolerance:
            found.append(Mismatch("SL_MISMATCH", f"ticket {pos.ticket}"))
        if abs(pos.take_profit - record.take_profit) > self.price_tolerance:
            found.append(Mismatch("TP_MISMATCH", f"ticket {pos.ticket}"))
