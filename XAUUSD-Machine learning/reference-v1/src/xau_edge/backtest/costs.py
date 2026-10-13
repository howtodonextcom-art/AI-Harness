"""Transaction-cost assumptions for the backtest.

Spread is not a parameter here: it is read bar by bar from the data (M5 spread, in points) because
a derived higher-timeframe spread is not the broker's (docs/reports/mt5-verification.md). What is
assumed is listed explicitly so reports can state it.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

_NEW_YORK = ZoneInfo("America/New_York")
_SATURDAY = 5


class CostModel(BaseModel):
    """Per-fill and per-night costs. Swap points follow MT5 mode 1: points per lot per night."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    point: float = Field(default=0.01, gt=0)
    contract_size: float = Field(default=100.0, gt=0)
    slippage_points: float = Field(default=3.0, ge=0)
    """Adverse slippage per market or stop fill (assumption, not measured)."""
    commission_per_lot_per_side: float = Field(default=0.0, ge=0)
    """USD per lot per side. 0 for FTMO gold CFDs is UNVERIFIED; set from the account type."""
    swap_long_points: float = -76.05
    swap_short_points: float = -4.2
    """Read from the FTMO demo terminal on 2026-10-08; they change, so re-read before use."""
    rollover_hour_new_york: int = Field(default=17, ge=0, le=23)

    @property
    def value_per_point_per_lot(self) -> float:
        """USD per point per lot (XAUUSD: 0.01 x 100 oz = 1.0)."""
        return self.point * self.contract_size

    def rollover_nights(self, entry: datetime, exit_: datetime) -> int:
        """Number of daily rollovers (17:00 New York) between entry and exit."""
        shift = self.rollover_hour_new_york
        a = entry.astimezone(_NEW_YORK)
        b = exit_.astimezone(_NEW_YORK)
        key_a = (a.replace(tzinfo=None) - timedelta(hours=shift)).date()
        key_b = (b.replace(tzinfo=None) - timedelta(hours=shift)).date()
        flips = (key_a + timedelta(days=d) for d in range(1, max((key_b - key_a).days, 0) + 1))
        return sum(1 for day in flips if day.weekday() < _SATURDAY)  # no rollover on Sat/Sun

    def swap_cost(self, direction: int, lots: float, nights: int) -> float:
        """Swap in USD (negative = cost). Triple Wednesday swap is not modelled."""
        points = self.swap_long_points if direction > 0 else self.swap_short_points
        return points * nights * lots * self.value_per_point_per_lot
