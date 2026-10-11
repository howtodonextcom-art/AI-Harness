"""Payoff geometry: net reward-to-risk, break-even probability and expected value in R.

R:R describes payoff geometry. It is NOT a probability: a 1:1 payoff does not mean 50%, a 2:1 payoff
does not mean 66%. What R:R fixes is the win probability that is *required* to break even;
whether the real probability exceeds it is a separate, evidence-based question this module
never answers.

Convention (same as ``trading/levels.py``): costs are in price units, paid on every trade, and enter
the payoff as ``net_rr = (reward - costs) / (risk + costs)``.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from math import isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CostModel(BaseModel):
    """All-in cost of one round trip in price units (spread, slippage, commission, swap)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    spread: float = Field(ge=0.0, allow_inf_nan=False)
    slippage: float = Field(ge=0.0, allow_inf_nan=False)
    commission: float = Field(ge=0.0, allow_inf_nan=False)
    swap: float = Field(ge=0.0, allow_inf_nan=False)
    source: str = Field(min_length=1)
    verified: bool

    @property
    def total(self) -> float:
        return self.spread + self.slippage + self.commission + self.swap


class NetPayoff(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    gross_risk: float
    gross_reward: float
    gross_rr: float
    net_risk: float
    net_reward: float
    net_rr: float
    break_even_probability: float  # gross, before costs
    net_break_even_probability: float  # the one that matters: with costs


def break_even_probability(rr: float) -> float:
    """Win probability at which a payoff of ``rr`` : 1 breaks even (1:1 -> 50%, 2:1 -> 33.3%)."""
    if rr <= 0:
        raise ValueError("a payoff needs a positive reward-to-risk")
    return 1.0 / (1.0 + rr)


def net_payoff(
    side: Literal["BUY", "SELL"], entry: float, stop: float, target: float, costs: CostModel
) -> NetPayoff | None:
    """The payoff after costs, or ``None`` when the levels are on the wrong side of the entry."""
    if not all(isfinite(value) for value in (entry, stop, target)):
        return None
    sign = 1.0 if side == "BUY" else -1.0
    risk = sign * (entry - stop)
    reward = sign * (target - entry)
    if risk <= 0 or reward <= 0:
        return None
    gross_rr = reward / risk
    net_risk = risk + costs.total
    net_reward = reward - costs.total
    net_rr = max(0.0, net_reward / net_risk)
    return NetPayoff(
        gross_risk=risk,
        gross_reward=reward,
        gross_rr=gross_rr,
        net_risk=net_risk,
        net_reward=net_reward,
        net_rr=net_rr,
        break_even_probability=break_even_probability(gross_rr),
        net_break_even_probability=break_even_probability(net_rr) if net_rr > 0 else 1.0,
    )


def round_levels_to_tick(
    side: Literal["BUY", "SELL"], entry: float, stop: float, target: float, tick_size: float
) -> tuple[float, float, float]:
    """Round all levels adversely to a broker tick before any authorization calculation."""
    if not all(isfinite(value) for value in (entry, stop, target, tick_size)) or tick_size <= 0:
        raise ValueError("tick_size must be positive")
    tick = Decimal(str(tick_size))
    rounding = {
        "entry": ROUND_CEILING if side == "BUY" else ROUND_FLOOR,
        "stop": ROUND_FLOOR if side == "BUY" else ROUND_CEILING,
        "target": ROUND_FLOOR if side == "BUY" else ROUND_CEILING,
    }

    def quantize(value: float, mode: str) -> float:
        units = (Decimal(str(value)) / tick).to_integral_value(rounding=mode)
        return float(units * tick)

    return (
        quantize(entry, rounding["entry"]),
        quantize(stop, rounding["stop"]),
        quantize(target, rounding["target"]),
    )


def required_probability(
    net_rr: float, *, calibration_margin: float, uncertainty_margin: float
) -> float:
    """Break-even plus a preregistered margin for calibration error and sampling uncertainty."""
    if calibration_margin < 0 or uncertainty_margin < 0:
        raise ValueError("margins cannot be negative")
    return min(1.0, break_even_probability(net_rr) + calibration_margin + uncertainty_margin)


def expected_value_r(p_win: float, net_rr: float) -> float:
    """Expected value per trade in units of risk, costs already inside ``net_rr``:
    ``p * net_rr - (1 - p) * 1``. ``p_win`` must be a validated, calibrated probability."""
    if not 0.0 <= p_win <= 1.0:
        raise ValueError("a probability lies in [0, 1]")
    return p_win * net_rr - (1.0 - p_win)
