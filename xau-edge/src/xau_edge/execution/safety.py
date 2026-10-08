"""Execution safety controls (brief section 32) enforced before any order reaches a broker.

Live trading is disabled by default and cannot be enabled by configuration in this project
(``Settings`` rejects it). These checks apply to the paper broker today and are the minimum any
future executor must also pass: environment confirmation, account and symbol whitelists, maximum lot
size, maximum orders per day, dry-run mode.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.config import Settings


class ExecutionSafety(BaseModel):
    """Limits and switches; the defaults are the strict ones."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str = "paper"
    allowed_environments: tuple[str, ...] = ("paper",)
    allowed_accounts: tuple[str, ...] = ("paper",)
    allowed_symbols: tuple[str, ...] = ("XAUUSD",)
    max_lots: float = Field(default=10.0, gt=0)
    max_orders_per_day: int = Field(default=10, ge=1)
    dry_run: bool = False
    account: str = "paper"

    def violations(self, *, symbol: str, lots: float, orders_today: int) -> list[str]:
        """Reasons the order must not go out (empty when it may)."""
        out: list[str] = []
        if self.environment not in self.allowed_environments:
            out.append("ENVIRONMENT_NOT_CONFIRMED")
        if self.account not in self.allowed_accounts:
            out.append("ACCOUNT_NOT_WHITELISTED")
        if symbol not in self.allowed_symbols:
            out.append("SYMBOL_NOT_WHITELISTED")
        if lots > self.max_lots:
            out.append("LOTS_ABOVE_MAXIMUM")
        if orders_today >= self.max_orders_per_day:
            out.append("ORDER_COUNT_EXCEEDED")
        return out


def assert_live_trading_disabled(settings: Settings | None = None) -> None:
    """Raise unless the process is configured with live trading off (the only supported state)."""
    current = settings or Settings()
    if current.enable_live_trading:
        msg = "live trading must remain disabled"
        raise RuntimeError(msg)


def day_key(moment_date: date) -> str:
    """Key used to count orders per calendar day."""
    return moment_date.isoformat()
