"""Execution abstraction (brief section 31): trading logic never talks to a broker directly.

Only ``PaperExecutionBroker`` implements this interface. A live broker is deliberately NOT part
of this project (ADR-0018); if one is ever added it must pass the same interface, the safety
checks of ``execution.safety`` and a separate owner decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Order(BaseModel):
    """A market order with protective levels, traceable to the signal that produced it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_id: str
    symbol: str
    direction: Literal[-1, 1]
    lots: float = Field(gt=0, allow_inf_nan=False)
    stop_loss: float = Field(gt=0, allow_inf_nan=False)
    take_profit: float = Field(gt=0, allow_inf_nan=False)
    signal_hash: str
    max_hold_until: datetime | None = None


class Position(BaseModel):
    """An open position."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str
    order_id: str
    symbol: str
    direction: Literal[-1, 1]
    lots: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    signal_hash: str
    max_hold_until: datetime | None = None


class AccountInfo(BaseModel):
    """Account snapshot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_capital: float
    balance: float
    equity: float
    open_positions: int
    open_lots: float


class ClosedTrade(BaseModel):
    """A closed paper trade with its cost breakdown."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    position_id: str
    direction: Literal[-1, 1]
    lots: float
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    reason: str
    gross_pnl: float
    commission: float
    swap: float
    net_pnl: float
    risk_amount: float
    signal_hash: str


class ExecutionBroker(Protocol):
    """What the trading layer may ask of any broker (paper today)."""

    def get_account(self) -> AccountInfo:
        """Current balance, equity and exposure."""
        ...

    def get_positions(self) -> list[Position]:
        """Open positions."""
        ...

    def submit_order(self, order: Order) -> Position:
        """Fill a market order immediately and return the resulting position."""
        ...

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order; ``False`` when there is nothing to cancel."""
        ...

    def close_position(self, position_id: str, reason: str) -> ClosedTrade:
        """Close a position at the current quote."""
        ...

    def modify_position(
        self,
        position_id: str,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Position:
        """Change the protective levels of an open position."""
        ...
