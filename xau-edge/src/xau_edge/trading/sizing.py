"""Risk-based position size from the BROKER's symbol specification (trading core section 20).

Never a hard-coded XAU lot value: the loss per lot at the stop comes from ``tick_size`` and
``tick_value`` (``symbol_info``). The volume is rounded DOWN to the volume step, the real risk is
recomputed after rounding, and the trade is refused when even the minimum volume exceeds the risk
cap or when the stop is closer than the broker's minimum stop distance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class SymbolSpec(BaseModel):
    """Contract specification of one symbol (all values come from the broker)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = "XAUUSD"
    point: float = Field(default=0.01, gt=0)
    tick_size: float = Field(default=0.01, gt=0)
    tick_value: float = Field(default=1.0, gt=0)
    """Account-currency profit of ONE tick for ONE lot."""
    contract_size: float = Field(default=100.0, gt=0)
    volume_min: float = Field(default=0.01, gt=0)
    volume_max: float = Field(default=100.0, gt=0)
    volume_step: float = Field(default=0.01, gt=0)
    stops_level_points: int = Field(default=0, ge=0)
    freeze_level_points: int = Field(default=0, ge=0)
    digits: int = Field(default=2, ge=0)

    def loss_per_lot(self, distance: float) -> float:
        """Account-currency loss of one lot when price moves ``distance`` against the position."""
        return distance / self.tick_size * self.tick_value

    def min_stop_distance(self) -> float:
        return self.stops_level_points * self.point


@dataclass(frozen=True)
class SizeResult:
    """The allowed volume and the risk it really carries."""

    lots: float
    risk_amount: float
    risk_pct_actual: float
    reasons: tuple[str, ...]

    @property
    def allowed(self) -> bool:
        return self.lots > 0 and not self.reasons


def size_for_risk(  # noqa: PLR0911 - one early exit per refusal
    equity: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    spec: SymbolSpec,
    *,
    max_risk_pct: float | None = None,
) -> SizeResult:
    """Largest volume (rounded down) whose stop loss costs at most ``risk_pct`` of equity."""
    if not (math.isfinite(equity) and equity > 0):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_EQUITY",))
    if not (math.isfinite(risk_pct) and 0 < risk_pct <= 2.0):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_RISK_PCT",))
    distance = abs(entry - stop_loss)
    if not (math.isfinite(distance) and distance > 0):
        return SizeResult(0.0, 0.0, 0.0, ("INVALID_STOP",))
    if distance < spec.min_stop_distance():
        return SizeResult(0.0, 0.0, 0.0, ("STOP_TOO_CLOSE_FOR_BROKER",))
    loss_lot = spec.loss_per_lot(distance)
    budget = equity * risk_pct / 100.0
    steps = math.floor(budget / loss_lot / spec.volume_step + 1e-9)
    lots = min(steps * spec.volume_step, spec.volume_max)
    if lots < spec.volume_min - 1e-12:
        return SizeResult(0.0, 0.0, 0.0, ("MIN_LOT_EXCEEDS_RISK",))
    lots = round(lots, 8)
    risk_amount = lots * loss_lot
    actual_pct = risk_amount / equity * 100.0
    cap = max_risk_pct if max_risk_pct is not None else risk_pct
    if actual_pct > cap + 1e-9:
        return SizeResult(0.0, 0.0, actual_pct, ("RISK_ABOVE_CAP_AFTER_ROUNDING",))
    return SizeResult(lots, risk_amount, actual_pct, ())
