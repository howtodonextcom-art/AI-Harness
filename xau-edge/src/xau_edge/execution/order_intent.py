"""Order intent: the broker-neutral, audit-ready description of one order a signal has earned.

An intent is only ever built from a ``Signal`` that already passed the bridge (risk engine, safety,
kill switch, idempotency). It holds no secrets, takes nothing from a client, and is deterministic:
the same signal and decision time always give the same ``intent_id``. It names no broker; a later
adapter translates it, and ``to_order`` maps it onto the existing paper/broker ``Order``.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from xau_edge.execution.interface import Order
from xau_edge.signals.schema import Direction, Signal

COMMENT_PREFIX: Final = "XAUEDGE:"
MAX_COMMENT_LENGTH: Final = 31
"""The MT5 terminal truncates order comments at 31 characters."""
_COMMENT_RE: Final = re.compile(r"^[A-Za-z0-9:_-]+$")


class IntentError(ValueError):
    """The signal cannot become an order intent."""


def make_intent_id(signal_hash: str, decision_time: datetime) -> str:
    """Deterministic id from the signal's input hash and the decision bar."""
    raw = f"{signal_hash}|{decision_time.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


class OrderIntent(BaseModel):
    """One order the system is allowed to place (or, in dry-run, would place)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str = Field(min_length=8)
    signal_hash: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    direction: Literal[-1, 1]
    lots: float = Field(gt=0, allow_inf_nan=False)
    risk_amount: float = Field(ge=0, allow_inf_nan=False)
    entry_reference: float = Field(gt=0, allow_inf_nan=False)
    stop_loss: float = Field(gt=0, allow_inf_nan=False)
    take_profit: float = Field(gt=0, allow_inf_nan=False)
    max_hold_until: datetime
    decision_time: datetime
    created_at: datetime
    magic: int = Field(ge=0)
    comment: str
    dry_run: bool = True
    metadata: Mapping[str, str | float | int | bool | None] = Field(default_factory=dict)

    @field_validator("decision_time", "created_at", "max_hold_until")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            msg = "timestamps must be timezone-aware"
            raise ValueError(msg)
        return value

    @field_validator("comment")
    @classmethod
    def _comment_is_safe(cls, value: str) -> str:
        if len(value) > MAX_COMMENT_LENGTH or not _COMMENT_RE.fullmatch(value):
            msg = f"comment must be 1-{MAX_COMMENT_LENGTH} characters of [A-Za-z0-9:_-]"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _levels_are_consistent(self) -> Self:
        if self.direction == 1 and not self.stop_loss < self.entry_reference < self.take_profit:
            msg = "a long needs stop_loss < entry < take_profit"
            raise ValueError(msg)
        if self.direction == -1 and not self.take_profit < self.entry_reference < self.stop_loss:
            msg = "a short needs take_profit < entry < stop_loss"
            raise ValueError(msg)
        if self.max_hold_until <= self.decision_time:
            msg = "max_hold_until must be after the decision time"
            raise ValueError(msg)
        return self

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy with ``update`` applied AND validated (pydantic's default skips validation)."""
        data = self.model_dump()
        data.update(update or {})
        return type(self)(**data)

    @classmethod
    def model_construct(cls, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        """Unvalidated construction would bypass the level checks, so it is refused."""
        msg = "OrderIntent objects must be built through validation"
        raise TypeError(msg)

    def to_order(self) -> Order:
        """The broker-neutral ``Order`` for this intent (no broker is contacted)."""
        return Order(
            order_id=self.intent_id,
            symbol=self.symbol,
            direction=self.direction,
            lots=self.lots,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            signal_hash=self.signal_hash,
            max_hold_until=self.max_hold_until,
        )


def build_intent(
    signal: Signal,
    *,
    lots: float,
    risk_amount: float,
    magic: int,
    created_at: datetime,
    max_hold_until: datetime,
    dry_run: bool,
    entry_reference: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    direction: Direction | None = None,
    unvalidated: bool = False,
    strategy_id: str | None = None,
) -> OrderIntent:
    """Build the intent for a BUY/SELL signal; WAIT or an incomplete one raises ``IntentError``.

    ``entry_reference`` is the price the order is expected to fill at (the ask for a BUY, the bid
    for a SELL); without it the middle of the signal's entry zone is used. ``stop_loss`` and
    ``take_profit`` default to the signal's own levels; the bridge passes them rounded to the
    symbol's digits.
    """
    side = direction or signal.direction
    if side is Direction.WAIT:
        msg = "a WAIT signal never becomes an order intent"
        raise IntentError(msg)
    if not signal.inputs_hash:
        msg = "the signal has no inputs_hash"
        raise IntentError(msg)
    if signal.entry_zone is None or signal.stop_loss is None or signal.take_profit_1 is None:
        msg = "the signal lacks an entry zone, stop loss or take profit"
        raise IntentError(msg)
    entry = entry_reference if entry_reference is not None else sum(signal.entry_zone) / 2
    sl = signal.stop_loss if stop_loss is None else stop_loss
    tp = signal.take_profit_1 if take_profit is None else take_profit
    if not all(math.isfinite(v) for v in (entry, sl, tp)):
        msg = "the signal has non-finite price levels"
        raise IntentError(msg)
    intent_id = make_intent_id(signal.inputs_hash, signal.timestamp)
    try:
        return OrderIntent(
            intent_id=intent_id,
            signal_hash=signal.inputs_hash,
            symbol=signal.symbol,
            direction=1 if side is Direction.BUY else -1,
            lots=lots,
            risk_amount=risk_amount,
            entry_reference=entry,
            stop_loss=sl,
            take_profit=tp,
            max_hold_until=max_hold_until,
            decision_time=signal.timestamp,
            created_at=created_at,
            magic=magic,
            comment=(
                f"{COMMENT_PREFIX}UNV:{intent_id[:10]}"
                if unvalidated
                else f"{COMMENT_PREFIX}{intent_id[:12]}"
            ),
            dry_run=dry_run,
            metadata={
                "timeframe": signal.timeframe,
                "regime": signal.market_regime,
                "risk_reward": signal.risk_reward,
                "expected_R": signal.expected_R,
                "evidence_status": (
                    "UNVALIDATED_OVERRIDE" if unvalidated else signal.evidence_status.value
                ),
                "strategy_id": strategy_id,
                "code_version": signal.code_version,
            },
        )
    except ValueError as exc:
        msg = f"the signal does not form a consistent order: {exc}"
        raise IntentError(msg) from exc
