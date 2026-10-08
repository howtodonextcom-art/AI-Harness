"""The signal contract (brief section 21).

A signal is WAIT unless every check passed AND the evidence gate is open. The schema itself
enforces this, so no code path can construct a BUY or SELL that carries a refusal reason or lacks
validated evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Direction(StrEnum):
    """Final decision."""

    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class EvidenceStatus(StrEnum):
    """Whether any strategy has passed the pre-registered validation on all periods."""

    NONE = "NONE"
    VALIDATED = "VALIDATED"


class NoTradeReason(StrEnum):
    """Machine-readable reasons for WAIT."""

    NO_VALIDATED_EDGE = "NO_VALIDATED_EDGE"
    EDGE_INSUFFICIENT = "EDGE_INSUFFICIENT"
    EV_NOT_POSITIVE = "EV_NOT_POSITIVE"
    RISK_REWARD_POOR = "RISK_REWARD_POOR"
    REGIME_UNSUPPORTED = "REGIME_UNSUPPORTED"
    NEWS_RISK = "NEWS_RISK"
    NEWS_UNKNOWN = "NEWS_UNKNOWN"
    SPREAD_EXCESSIVE = "SPREAD_EXCESSIVE"
    DATA_INVALID = "DATA_INVALID"
    MODEL_UNCERTAIN = "MODEL_UNCERTAIN"
    HTF_BIAS_CONFLICT = "HTF_BIAS_CONFLICT"
    ENTRY_QUALITY_POOR = "ENTRY_QUALITY_POOR"


class Signal(BaseModel):
    """Decision plus everything needed to understand and reproduce it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str
    timestamp: datetime
    timeframe: str
    direction: Direction
    candidate_direction: Direction | None = None
    """What the analysis leans towards, shown even when the final decision is WAIT."""
    prob_up: float | None = Field(default=None, ge=0, le=1)
    prob_down: float | None = Field(default=None, ge=0, le=1)
    prob_neutral: float | None = Field(default=None, ge=0, le=1)
    probability_source: str = "none"
    expected_return: float | None = None
    expected_R: float | None = None  # noqa: N815 - name fixed by the brief's schema
    market_regime: str | None = None
    higher_timeframe_bias: str | None = None
    entry_zone: tuple[float, float] | None = None
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    risk_reward: float | None = None
    signal_expiry: datetime | None = None
    explanation: tuple[str, ...] = ()
    historical_matches_count: int = 0
    similarity_quality: float | None = None
    evidence_status: EvidenceStatus = EvidenceStatus.NONE
    reasons: tuple[NoTradeReason, ...] = ()
    inputs_hash: str = ""
    code_version: str = ""

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy with ``update`` applied AND validated (pydantic's default skips validation)."""
        data = self.model_dump()
        data.update(update or {})
        return type(self)(**data)

    @classmethod
    def model_construct(cls, *args: Any, **kwargs: Any) -> Self:  # type: ignore[override]
        """Unvalidated construction would bypass the BUY/SELL invariant, so it is refused."""
        msg = "Signal objects must be built through validation (use decide() or Signal(...))"
        raise TypeError(msg)

    @model_validator(mode="after")
    def _trade_requires_clean_checks(self) -> Self:
        if self.direction is not Direction.WAIT:
            if self.reasons:
                msg = "a BUY/SELL signal cannot carry no-trade reasons"
                raise ValueError(msg)
            if self.evidence_status is not EvidenceStatus.VALIDATED:
                msg = "a BUY/SELL signal requires validated evidence"
                raise ValueError(msg)
            if self.stop_loss is None or self.take_profit_1 is None or self.entry_zone is None:
                msg = "a BUY/SELL signal needs an entry zone, stop loss and take profit"
                raise ValueError(msg)
        elif not self.reasons:
            msg = "a WAIT signal must state at least one reason"
            raise ValueError(msg)
        return self
