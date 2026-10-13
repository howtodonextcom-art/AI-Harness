"""Contract of the market-intelligence endpoint.

Four layers are kept apart on purpose:

* OBSERVATION: what the closed bars show (regime, structure, volatility, price action);
* SCENARIOS: conditional situations to watch, each with what confirms and what invalidates it;
* AUTHORIZATION: what the validated strategy (the V1 baseline) says and why, with the market's
  own blocker kept apart from the safety gates and from the account governor;
* HUMAN: not here (it stays in ``/api/v2/state`` and ``/api/v2/human/*``).

``authority`` is always ``NONE``: nothing in this document can open, size or close anything.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from xau_edge_v2.domain.contract import Frozen, Timeframe

SCHEMA = "intel-1"

Direction = Literal["UP", "DOWN", "NONE"]
ScenarioStatus = Literal["WATCH", "CONTEXT", "INACTIVE", "BLOCKED"]
StepStatus = Literal["PASS", "FAIL", "NOT_REACHED", "NOT_APPLICABLE"]
GateCategory = Literal["DATA", "COST", "VOLATILITY", "NEWS", "GOVERNOR", "STRATEGY"]


class LevelView(Frozen):
    role: str
    """SWING_HIGH, SWING_LOW, PROVISIONAL_HIGH, SUPPORT, RESISTANCE, BOX_HIGH, PDH, ..."""
    label: str
    price: float
    timeframe: Timeframe | None = None
    confirmed: bool = True
    known_at: datetime | None = None
    distance_atr: float | None = None
    """Distance from the last close in M15 ATR (signed: positive above price)."""


class EventView(Frozen):
    scope: Literal["PRICE_ACTION", "STRUCTURE", "VOLATILITY"]
    timeframe: Timeframe
    kind: str
    text: str
    bar_open: datetime
    known_at: datetime
    """Never earlier than the close of the bar the event describes (no repainting)."""
    level: float | None = None
    invalidation: float | None = None
    strength: float | None = None
    age_bars: int = 0


class TimeframeView(Frozen):
    timeframe: Timeframe
    role: str
    available: bool
    stale: bool = False
    last_closed: datetime | None = None
    regime: str | None = None
    trend: Direction = "NONE"
    volatility_phase: str = "UNKNOWN"
    atr: float | None = None
    atr_ratio: float | None = None
    last_swing_high: LevelView | None = None
    last_swing_low: LevelView | None = None
    provisional_high: LevelView | None = None
    provisional_low: LevelView | None = None


class ScenarioView(Frozen):
    key: str
    title: str
    direction: Direction
    status: ScenarioStatus
    why: tuple[str, ...]
    confirm: str
    invalidate: str
    levels: tuple[LevelView, ...] = ()


class FunnelStep(Frozen):
    key: str
    label: str
    status: StepStatus
    observed: str
    required: str


class GateView(Frozen):
    code: str
    text: str
    category: GateCategory


class Authorization(Frozen):
    """The strategy's word, split into the market's reason, the safety gates and the governor."""

    strategy_id: str
    strategy_version: str
    evidence: Literal["UNVALIDATED"] = "UNVALIDATED"
    candidate_active: Literal[False] = False
    """Candidate V2 is research only: it never decides in this build."""
    action: str
    chain_verdict: str
    """``CHAIN_OK`` or the first link of the chain that refuses, IGNORING gates and governor."""
    chain_blocker: GateView | None
    next_condition: str | None
    gates: tuple[GateView, ...]
    """Safety / cost / data gates that hold the strategy back right now."""
    system_hold: tuple[GateView, ...]
    """Account governor refusals (cooldown, daily limit, risk limit): not a market statement."""
    funnel: tuple[FunnelStep, ...]
    explanation: str


class ChangeView(Frozen):
    at: datetime
    kind: str
    text: str


class MarketIntelligence(Frozen):
    schema_version: str = SCHEMA
    generated_at: datetime
    authority: Literal["NONE"] = "NONE"
    descriptive_only: Literal[True] = True
    evidence: Literal["UNVALIDATED"] = "UNVALIDATED"
    last_closed_m5: datetime | None
    quote_age_s: float | None
    data_state: str
    market_open: bool
    price: float | None
    summary: str
    timeframes: tuple[TimeframeView, ...]
    levels: tuple[LevelView, ...]
    events: tuple[EventView, ...]
    scenarios: tuple[ScenarioView, ...]
    authorization: Authorization
    changes: tuple[ChangeView, ...] = Field(default=())
