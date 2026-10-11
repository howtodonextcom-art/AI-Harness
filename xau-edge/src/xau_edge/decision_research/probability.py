"""The probability contract. A probability is either evidence-backed or it is ``None``.

Nothing in this package can produce a win probability: there is no function from a pattern, a shape,
an R:R or a "confidence" to a number. A ``TradeSuccessProbability`` can only be constructed from the
output of a separately authorised, out-of-sample, calibrated study, and it is refused unless it
carries a horizon, a sample size, a confidence interval and a calibration status that allows
publishing.

Three probabilities are kept apart and never substituted for each other:

* pattern completion: P(a developing pattern reaches confirmation);
* direction: P(price is higher/lower after a horizon);
* trade success: P(take profit before stop loss within the horizon | the proposed trade).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CalibrationStatus(StrEnum):
    UNVALIDATED = "UNVALIDATED"
    DEVELOPMENT = "DEVELOPMENT"  # fitted and checked on development data only: never published
    OOS_CALIBRATED = "OOS_CALIBRATED"
    FORWARD_CALIBRATED = "FORWARD_CALIBRATED"


PUBLISHABLE = {CalibrationStatus.OOS_CALIBRATED, CalibrationStatus.FORWARD_CALIBRATED}


class TradeSuccessProbability(BaseModel):
    """P(TP before SL within ``horizon_minutes`` | the proposed BUY or SELL)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    side: Literal["BUY", "SELL"]
    estimate: float = Field(ge=0.0, le=1.0)
    ci_low: float = Field(ge=0.0, le=1.0)
    ci_high: float = Field(ge=0.0, le=1.0)
    sample_n: int = Field(ge=1)
    horizon_minutes: int = Field(ge=1)  # no horizon, no probability
    calibration_status: CalibrationStatus
    evidence_ref: str = Field(min_length=3)  # the study that produced it

    @model_validator(mode="after")
    def _consistent(self) -> TradeSuccessProbability:
        if not self.ci_low <= self.estimate <= self.ci_high:
            raise ValueError("the estimate must lie inside its confidence interval")
        return self


class DecisionProbability(BaseModel):
    """What a decision may show. Unvalidated means every number is ``None``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    buy_success: TradeSuccessProbability | None = None
    sell_success: TradeSuccessProbability | None = None
    calibration_status: CalibrationStatus = CalibrationStatus.UNVALIDATED
    note: str = "no validated probability exists: nothing is shown"


def publication_problems(
    p: TradeSuccessProbability | None, *, min_sample: int, max_ci_width: float
) -> list[str]:
    """Why ``p`` may not be published (empty list = it may)."""
    if p is None:
        return ["PROBABILITY_UNAVAILABLE"]
    problems: list[str] = []
    if p.calibration_status not in PUBLISHABLE:
        problems.append(f"CALIBRATION_{p.calibration_status}")
    if p.sample_n < min_sample:
        problems.append("INSUFFICIENT_SAMPLE")
    if p.ci_high - p.ci_low > max_ci_width:
        problems.append("CONFIDENCE_INTERVAL_TOO_WIDE")
    return problems
