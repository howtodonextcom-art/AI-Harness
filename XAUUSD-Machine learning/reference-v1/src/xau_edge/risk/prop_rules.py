"""Prop-firm rule profiles loaded from ``configs/prop`` (never hard-coded in trading logic)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class PropProfile(BaseModel):
    """The loss-limit rules of one challenge type, with provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    source: str
    verified_on: date
    daily_loss_limit_pct: float = Field(gt=0, lt=100)
    max_loss_limit_pct: float = Field(gt=0, lt=100)
    max_loss_kind: Literal["static", "trailing_end_of_day_balance"]
    minimum_trading_days: int | None = None
    best_day_share_pct: float | None = None
    internal_buffer_pct_of_limit: float = Field(default=40.0, ge=0, lt=100)
    ea_restrictions: str = "unverified"
    trading_restrictions: str = "unverified"
    execution_rules: str = "unverified"

    def daily_loss_amount(self, initial_capital: float) -> float:
        """Size of the daily loss allowance in account currency."""
        return initial_capital * self.daily_loss_limit_pct / 100.0

    def daily_loss_floor(self, initial_capital: float, *, day_start_balance: float) -> float:
        """Equity below which today's loss limit is breached (balance at day start minus limit)."""
        return day_start_balance - self.daily_loss_amount(initial_capital)

    def max_loss_floor(self, initial_capital: float, *, highest_eod_balance: float) -> float:
        """Equity below which the maximum loss is breached."""
        amount = initial_capital * self.max_loss_limit_pct / 100.0
        static = initial_capital - amount
        if self.max_loss_kind == "static":
            return static
        return max(static, highest_eod_balance - amount)


def load_prop_profile(path: Path | str) -> PropProfile:
    """Read a profile YAML (see ``configs/prop``)."""
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    best_day = raw.get("best_day_rule") or {}
    return PropProfile(
        name=raw["name"],
        source=raw["source"],
        verified_on=raw["verified_on"],
        daily_loss_limit_pct=raw["daily_loss"]["limit_pct"],
        max_loss_limit_pct=raw["max_loss"]["limit_pct"],
        max_loss_kind=raw["max_loss"]["kind"],
        minimum_trading_days=raw.get("minimum_trading_days"),
        best_day_share_pct=best_day.get("max_share_of_positive_days_profit_pct"),
        internal_buffer_pct_of_limit=raw.get("internal_buffer_pct_of_limit", 40.0),
        ea_restrictions=str(raw.get("ea_restrictions", "unverified")),
        trading_restrictions=str(raw.get("trading_restrictions", "unverified")),
        execution_rules=str(raw.get("execution_rules", "unverified")),
    )
