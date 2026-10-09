"""Typed signal of the trading core (sections 28 to 30).

``TradingSignal`` is the explainable BUY/SELL/WAIT answer with its levels and reasons. The
baseline is OPERATIONAL, never a validated edge: ``evidence_status`` is ``UNVALIDATED_BASELINE``
and a BUY/SELL cannot be built without entry, stop loss, take profit and a positive risk. WAIT must
state at least one refusal reason. There is no confidence percentage: none is calibrated.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TradeDecision(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


class EvidenceLabel(StrEnum):
    UNVALIDATED_BASELINE = "UNVALIDATED_BASELINE"
    VALIDATED = "VALIDATED"


class EntryType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class Refusal(StrEnum):
    """Why the answer is WAIT (section 30)."""

    NO_DIRECTION = "NO_DIRECTION"
    TIMEFRAME_CONFLICT = "TIMEFRAME_CONFLICT"
    NO_SETUP = "NO_SETUP"
    NO_TRIGGER = "NO_TRIGGER"
    SPREAD_TOO_WIDE = "SPREAD_TOO_WIDE"
    VOLUME_TOO_LOW = "VOLUME_TOO_LOW"
    VOLATILITY_TOO_HIGH = "VOLATILITY_TOO_HIGH"
    VOLATILITY_TOO_LOW = "VOLATILITY_TOO_LOW"
    TOO_CLOSE_TO_RESISTANCE = "TOO_CLOSE_TO_RESISTANCE"
    TOO_CLOSE_TO_SUPPORT = "TOO_CLOSE_TO_SUPPORT"
    RR_TOO_LOW = "RR_TOO_LOW"
    INVALID_STOP_DISTANCE = "INVALID_STOP_DISTANCE"
    RISK_LIMIT = "RISK_LIMIT"
    DAILY_LIMIT = "DAILY_LIMIT"
    COOLDOWN = "COOLDOWN"
    NEWS_UNKNOWN = "NEWS_UNKNOWN"
    NEWS_WINDOW = "NEWS_WINDOW"
    STALE_DATA = "STALE_DATA"
    MARKET_CLOSED = "MARKET_CLOSED"
    BROKER_DISCONNECTED = "BROKER_DISCONNECTED"
    UNKNOWN_STATE = "UNKNOWN_STATE"


class TradingSignal(BaseModel):
    """BUY / SELL / WAIT with the whole chain of reasons and every level."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str
    timestamp: datetime
    symbol: str
    decision: TradeDecision
    strategy_id: str
    strategy_version: str
    evidence_status: EvidenceLabel = EvidenceLabel.UNVALIDATED_BASELINE
    active_timeframe: str = "M5"
    market_regime: str
    h4_bias: str
    h1_bias: str
    m30_state: str
    m15_setup: str
    m5_trigger: str
    m1_execution_state: str
    entry_type: EntryType | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_2: float | None = None
    risk_reward: float | None = None
    required_win_rate: float | None = None
    stop_model: str | None = None
    risk_pct: float | None = None
    position_size: float | None = None
    spread: float | None = None
    atr: float | None = None
    volume_state: str
    volume_type: str
    signal_expiry: datetime | None = None
    reasons: tuple[str, ...] = ()
    refusal_reasons: tuple[Refusal, ...] = ()
    code_version: str = ""
    inputs_hash: str = ""
    metadata: dict[str, float | str | None] = Field(default_factory=dict)
    setup_id: str = ""
    """Stable while the same M5 trigger bar holds: the identity used for alerts and paper orders."""
    news_state: str = "UNKNOWN"
    spread_state: str = "UNKNOWN"
    volatility_regime: str = "UNKNOWN"
    entry_quality: str = ""
    risk_amount: float | None = None
    invalidation: str | None = None
    warnings: tuple[str, ...] = ()
    bid: float | None = None
    ask: float | None = None
    generated_at: datetime | None = None
    data_age_seconds: float | None = None

    @property
    def decision_id(self) -> str:
        """Alias of ``signal_id`` (the id of this exact computation)."""
        return self.signal_id

    @property
    def expires_at(self) -> datetime | None:
        return self.signal_expiry

    @property
    def tick_volume_state(self) -> str:
        """The volume state is always TICK volume on this feed (``volume_type`` says so)."""
        return self.volume_state

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.decision is TradeDecision.WAIT:
            if not self.refusal_reasons:
                msg = "a WAIT must state at least one refusal reason"
                raise ValueError(msg)
            return self
        if self.refusal_reasons:
            msg = "a BUY/SELL cannot carry refusal reasons"
            raise ValueError(msg)
        needed = (self.entry_price, self.stop_loss, self.take_profit, self.risk_reward)
        if self.entry_type is None or any(v is None for v in needed):
            msg = "a BUY/SELL needs entry type, entry, stop loss, take profit and risk/reward"
            raise ValueError(msg)
        assert self.entry_price is not None  # noqa: S101 - narrowed by the check above
        assert self.stop_loss is not None  # noqa: S101
        assert self.take_profit is not None  # noqa: S101
        buy = self.decision is TradeDecision.BUY
        if buy and not self.stop_loss < self.entry_price < self.take_profit:
            msg = "BUY needs stop loss < entry < take profit"
            raise ValueError(msg)
        if not buy and not self.take_profit < self.entry_price < self.stop_loss:
            msg = "SELL needs take profit < entry < stop loss"
            raise ValueError(msg)
        if self.signal_expiry is None:
            msg = "a BUY/SELL needs an expiry"
            raise ValueError(msg)
        if self.evidence_status is EvidenceLabel.VALIDATED:
            msg = "the operational baseline can never be labelled VALIDATED"
            raise ValueError(msg)
        return self


TradingDecision = TradingSignal
"""The canonical decision object (the name used by the product documents)."""


def make_signal_id(parts: dict[str, object]) -> str:
    """Stable id from the decision inputs (the same closed bars give the same id)."""
    canonical = json.dumps(parts, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:20]
