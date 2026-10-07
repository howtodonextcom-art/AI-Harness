"""Instrument metadata."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Instrument(BaseModel):
    """Static description of a tradable instrument.

    Values are broker-dependent (digits, contract size). The defaults for XAUUSD below are
    common but ASSUMPTIONS: they must be confirmed against the broker's symbol specification
    before any cost or position-size calculation relies on them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = Field(min_length=1)
    digits: int = Field(ge=0, le=8)
    point: float = Field(gt=0)
    contract_size: float = Field(gt=0)
    quote_currency: str = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def _point_matches_digits(self) -> Instrument:
        if not math.isclose(self.point, 10.0**-self.digits, rel_tol=1e-9):
            msg = f"point {self.point} is inconsistent with digits {self.digits}"
            raise ValueError(msg)
        return self


XAUUSD = Instrument(
    symbol="XAUUSD", digits=2, point=0.01, contract_size=100.0, quote_currency="USD"
)
