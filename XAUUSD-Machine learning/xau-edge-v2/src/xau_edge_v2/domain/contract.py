"""The data contract (pure, no I/O): every type that crosses the API boundary.

Rules baked in (V2 ledger R-05, A-03, C-02, P-09):

* the mode is ``PAPER`` and nothing else (no live/demo value can even be expressed);
* an evidence label is mandatory on every decision surface (no hidden evidence level);
* bars of one response are strictly increasing in time (no duplicate timestamps, so a prepend or
  merge on the client can never create a duplicate);
* readiness is a deterministic lifecycle (0..6), not a probability.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from itertools import pairwise
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xau_edge_v2.domain.market import MarketStatus

SCHEMA_VERSION = "2.0.0-g10"
SYMBOL = "XAUUSD"


class Frozen(BaseModel):
    """Base for contract types: immutable, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Timeframe(StrEnum):
    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"

    @property
    def seconds(self) -> int:
        return {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400}[self.value]


class ActionCode(StrEnum):
    WAIT = "WAIT"
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"
    UNAVAILABLE = "UNAVAILABLE"


class Readiness(StrEnum):
    """Deterministic lifecycle, lowest to highest (spec section 9). NOT probabilities."""

    NEUTRAL = "NEUTRAL"
    BIAS = "BIAS"
    WATCH = "WATCH"
    SETUP_ARMED = "SETUP_ARMED"
    TRIGGER = "TRIGGER"
    PLAN_VALID = "PLAN_VALID"
    READY = "READY"


READINESS_ORDER: tuple[Readiness, ...] = tuple(Readiness)


def readiness_level(value: Readiness) -> int:
    """0 (NEUTRAL) .. 6 (READY)."""
    return READINESS_ORDER.index(value)


class EvidenceLabel(StrEnum):
    UNVALIDATED = "UNVALIDATED"
    RESEARCH = "RESEARCH"
    SHADOW = "SHADOW"
    OOS_VALIDATED = "OOS_VALIDATED"
    FORWARD_VALIDATED = "FORWARD_VALIDATED"


class ModelStatus(StrEnum):
    NOT_DEPLOYED = "NOT_DEPLOYED"
    RESEARCH = "RESEARCH"
    VALIDATED_OFFLINE = "VALIDATED_OFFLINE"
    SHADOW = "SHADOW"
    PAPER_ELIGIBLE = "PAPER_ELIGIBLE"
    PAPER_ACTIVE = "PAPER_ACTIVE"
    RETIRED = "RETIRED"


class ModelInfo(Frozen):
    status: ModelStatus
    task: str | None = None
    version: str | None = None
    note: str = ""


class TradePlan(Frozen):
    """Entry/SL/TP of a valid plan (served from G4 on; not produced by the G2 skeleton)."""

    side: Literal["BUY", "SELL"]
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float | None = None
    net_rr: float


class RiskInfo(Frozen):
    """Risk of a plan, cost known or explicitly unknown (never silently zero)."""

    risk_pct: float
    lots: float | None
    risk_amount: float | None
    cost_usd: float | None
    cost_status: Literal["MEASURED", "ASSUMED", "UNKNOWN"]
    swap_note: str | None = None


class DataInfo(Frozen):
    data_version: str
    data_timestamp: datetime | None = None
    stale: bool = True


class MtfRow(Frozen):
    """One timeframe's role and verdict in the chain (H4 regime ... M1 execution)."""

    timeframe: Timeframe
    role: str
    verdict: str
    detail: str = ""


M1State = Literal[
    "TOO_EARLY", "WATCH", "FORMING", "CONFIRMED", "EXECUTION_WINDOW", "TOO_LATE", "INVALIDATED"
]
M1Quality = Literal["GOOD", "CAUTION", "BAD"]
Recommendation = Literal["BUY_CANDIDATE", "SELL_CANDIDATE", "WAIT", "HOLD", "EXIT_WATCH"]


class M1Execution(Frozen):
    """Is this a good MOMENT to act on an idea the higher timeframes already support? Timing only:
    ``direction`` is copied from H1 and M1 can never change it."""

    applicable: bool
    reason: str
    direction: Literal["BUY", "SELL"] | None = None
    state: M1State | None = None
    quality: M1Quality | None = None
    reasons: tuple[str, ...] = ()
    features: dict[str, float | bool | str | None] = {}
    planned_entry: float | None = None
    planned_stop: float | None = None
    planned_target: float | None = None
    net_rr_now: float | None = None
    price_now: float | None = None


class SystemAdvice(Frozen):
    """The SYSTEM layer: an advisory recommendation, never a command. The human decides."""

    recommendation: Recommendation
    reasons: tuple[str, ...]
    primary_blocker: str | None = None
    blocker_text: str | None = None
    secondary: tuple[str, ...] = ()
    secondary_text: tuple[str, ...] = ()
    bias: Literal["BUY", "SELL", "NEUTRAL"]
    setup_state: Literal["NONE", "WATCHING", "ARMED"]
    trigger_state: Literal["NONE", "WAITING", "CONFIRMED"]
    strategy_action: str
    """What the deterministic strategy itself said (BUY/SELL/WAIT): shown, never overwritten."""
    strategy_version: str | None = None
    m1: M1Execution


class HumanChoice(StrEnum):
    ACCEPT = "ACCEPT"
    WAIT = "WAIT"
    REJECT = "REJECT"


class HumanRecord(Frozen):
    """One decision of the HUMAN, with the system state it answered. Append-only: never edited."""

    id: str
    timestamp: datetime
    decision_id: str
    """The system decision this answers."""
    setup_id: str
    system_action: str
    system_recommendation: Recommendation
    system_bias: str
    setup_state: str
    trigger_state: str
    m1_execution_state: str | None
    m1_quality: str | None
    entry: float | None
    sl: float | None
    tp: float | None
    rr: float | None
    risk_pct: float | None
    risk_amount: float | None
    price: float | None
    expiry: datetime | None
    human_choice: HumanChoice
    human_reason: str
    paper_mode: Literal["PAPER"] = "PAPER"
    strategy_version: str
    evidence_label: str


class HumanRequest(Frozen):
    """What the page may send: which candidate (setup_id) and the choice. Never a price or a size."""

    choice: HumanChoice
    setup_id: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="", max_length=500)


class HumanDecisionsResponse(Frozen):
    decisions: tuple[HumanRecord, ...]


class HumanActionResult(Frozen):
    ok: bool
    message: str
    record: HumanRecord | None = None


class StateSnapshot(Frozen):
    """The one decision surface the page renders (WAIT/BUY/SELL/HOLD/EXIT/UNAVAILABLE)."""

    schema_version: str = SCHEMA_VERSION
    symbol: str = SYMBOL
    mode: Literal["PAPER"] = "PAPER"
    generated_at: datetime
    action: ActionCode
    readiness: Readiness
    readiness_level: int = Field(ge=0, le=6)
    bias: Literal["BUY", "SELL", "NEUTRAL"]
    headline: str
    reason_codes: tuple[str, ...]
    blocker: str | None = None
    next_condition: str | None = None
    evidence: EvidenceLabel
    model: ModelInfo
    plan: TradePlan | None = None
    risk: RiskInfo | None = None
    data: DataInfo
    decision_id: str | None = None
    strategy_version: str | None = None
    chain: tuple[str, ...] = ()
    """The reasons the chain produced, one line per link (H4, H1, M15, M5, M1, spread, volume)."""
    warnings: tuple[str, ...] = ()
    expires_at: datetime | None = None
    mtf: tuple[MtfRow, ...] = ()
    setup_id: str | None = None
    """Identity of the current candidate (stable while the same M5 trigger bar holds); the human's
    answer must name it, so a plan that changed is never answered by mistake."""
    system: SystemAdvice | None = None
    human: HumanRecord | None = None
    """The human's latest choice on the CURRENT candidate (None when none, or no candidate)."""

    @model_validator(mode="after")
    def _consistent(self) -> StateSnapshot:
        if self.readiness_level != readiness_level(self.readiness):
            msg = "readiness_level must equal the index of readiness"
            raise ValueError(msg)
        if self.action in (ActionCode.BUY, ActionCode.SELL) and self.plan is None:
            msg = "a BUY/SELL decision must carry a plan"
            raise ValueError(msg)
        if self.action is ActionCode.UNAVAILABLE and self.plan is not None:
            msg = "an UNAVAILABLE decision cannot carry a plan"
            raise ValueError(msg)
        return self


class Bar(Frozen):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: float
    spread: float | None = None
    is_closed: bool = True

    @model_validator(mode="after")
    def _ohlc(self) -> Bar:
        if not (self.low <= min(self.open, self.close) and self.high >= max(self.open, self.close)):
            msg = "OHLC violates low <= open/close <= high"
            raise ValueError(msg)
        return self


class BarsResponse(Frozen):
    """History window (served from G3/G5). ``bars`` are strictly increasing in time."""

    symbol: str = SYMBOL
    timeframe: Timeframe
    bars: tuple[Bar, ...]
    oldest_available: datetime | None
    newest_available: datetime | None
    has_more_before: bool
    has_more_after: bool
    data_version: str

    @model_validator(mode="after")
    def _ordered(self) -> BarsResponse:
        times = [b.time for b in self.bars]
        if any(b <= a for a, b in pairwise(times)):
            msg = "bars must be strictly increasing in time (no duplicates)"
            raise ValueError(msg)
        return self


class Tick(Frozen):
    time_msc: int
    time: datetime
    bid: float
    ask: float


class TicksResponse(Frozen):
    """Ticks in ``[from, to)`` ordered by millisecond time (read-only; for the cost model)."""

    symbol: str = SYMBOL
    ticks: tuple[Tick, ...]
    count: int
    limit: int
    has_more: bool
    first_day: str | None
    last_day: str | None


class FormingBar(Frozen):
    """The still-open bar of one timeframe (``bar.is_closed`` is False)."""

    timeframe: Timeframe
    bar: Bar


class FormingResponse(Frozen):
    bars: tuple[FormingBar, ...]
    updated_at: datetime | None


class PaperPositionView(Frozen):
    """One PAPER position (open or closed). Nothing here ever reached a broker."""

    id: str
    setup_id: str
    decision_id: str
    side: Literal["BUY", "SELL"]
    lots: float
    entry: float
    """Fill price: the executable quote plus assumed adverse slippage."""
    quote_entry: float
    stop_loss: float
    take_profit: float
    take_profit_2: float | None = None
    net_rr: float
    risk_amount: float
    risk_pct: float
    source: Literal["AUTO", "MANUAL"]
    session: str
    opened_at: datetime
    status: Literal["OPEN", "CLOSED"]
    closed_at: datetime | None = None
    exit_price: float | None = None
    exit_reason: Literal["STOP_LOSS", "TAKE_PROFIT", "MANUAL", "FLATTEN"] | None = None
    ambiguous: bool = False
    """The closing bar reached both levels; the stop was assumed first."""
    pnl_usd: float | None = None
    swap_usd: float | None = None
    net_pnl_usd: float | None = None
    r_multiple: float | None = None
    floating_pnl_usd: float | None = None
    mae_points: float = 0.0
    mfe_points: float = 0.0


class PaperPositionsResponse(Frozen):
    positions: tuple[PaperPositionView, ...]


class GovernorStatus(Frozen):
    open_positions: int
    trades_today: int
    trades_last_hour: int
    loss_streak: int
    daily_loss_pct: float
    daily_loss_stop_pct: float
    cooldown_until: datetime | None = None
    refusals: tuple[str, ...] = ()
    """Why a NEW paper trade would be refused right now (empty: allowed)."""


class PaperSummary(Frozen):
    mode: Literal["PAPER"] = "PAPER"
    auto_paper: bool
    start_equity: float
    realized_pnl_usd: float
    floating_pnl_usd: float
    equity: float
    day_start_equity: float
    day_pnl_usd: float
    open_count: int
    closed_count: int
    wins: int
    losses: int
    total_r: float
    governor: GovernorStatus
    assumptions: tuple[str, ...]
    """What the paper numbers assume (fills, slippage, swap, commission, equity)."""


class ForwardGap(Frozen):
    """A run of closed M5 bars during which the engine logged nothing (it was down or stuck)."""

    start: datetime
    end: datetime
    bars: int


class ForwardFunnel(Frozen):
    """How far the decision chain got at each closed M5 bar (descriptive, no claim)."""

    by_action: dict[str, int]
    by_readiness: dict[str, int]
    first_refusal: dict[str, int]
    signals: int
    """Closed M5 bars whose decision was BUY or SELL."""
    distinct_setups: int


class ForwardTrades(Frozen):
    strategy_version: str
    closed: int
    wins: int
    losses: int
    total_r: float
    mean_r: float | None
    win_rate: float | None
    win_rate_ci95: tuple[float, float] | None
    """Wilson 95% interval; wide at small n (and says so)."""


class ForwardProgress(Frozen):
    closed_trades: int
    min_closed_trades: int
    observed_days: float
    min_days: int
    coverage: float | None
    min_coverage: float
    trades_per_day: float | None
    eta_days_to_min_trades: float | None
    claim_allowed: bool
    """True only when every minimum of the protocol is met AND an owner-approved hypothesis exists."""
    reason: str


class ForwardSummary(Frozen):
    mode: Literal["PAPER"] = "PAPER"
    evidence: Literal["FORWARD_ACCUMULATING", "NO_OBSERVATIONS"]
    protocol: str
    started: datetime | None
    last: datetime | None
    logged_bars: int
    expected_bars: int
    funnel: ForwardFunnel | None
    gaps: tuple[ForwardGap, ...]
    trades: tuple[ForwardTrades, ...]
    progress: ForwardProgress
    buy_and_hold_pct: float | None
    paper_return_pct: float | None
    notes: tuple[str, ...]


class JournalEventView(Frozen):
    seq: int
    ts: datetime
    kind: str
    position_id: str | None = None
    detail: dict[str, str | float | int | bool | None]


class JournalResponse(Frozen):
    events: tuple[JournalEventView, ...]


class PaperActionResult(Frozen):
    ok: bool
    message: str
    position: PaperPositionView | None = None


class ErrorBody(Frozen):
    """Every API error has this shape (never an HTML page, never a bare 503)."""

    error_code: str
    message: str


class ModelCriterion(Frozen):
    id: str
    label: str
    value: str
    passed: bool | None
    """True/False once evaluated; None when the evidence does not exist yet (e.g. Test-H)."""


class ModelStage(Frozen):
    name: str
    n: int
    skill_vs_atr14: float
    """Relative MSE improvement of the default model over the one-feature ATR14 baseline."""
    ci95: tuple[float, float]
    lower_adjusted: float
    """K-adjusted ONE-sided 97.5% lower bound (Bonferroni alpha/K) of the paired MSE difference."""
    coverage_80: float
    criteria: tuple[ModelCriterion, ...]


class ModelDetail(Frozen):
    """The ML V0 volatility/range model: status, evidence and locks (never a forecast)."""

    available: bool
    model_id: str | None = None
    version: str | None = None
    status: ModelStatus
    authority: Literal["NONE"] = "NONE"
    role: str | None = None
    task: str = "future_log_range"
    label_version: str | None = None
    spec_version: str | None = None
    spec_hash: str | None = None
    k_family: str | None = None
    k: int | None = None
    candidates: tuple[str, ...] = ()
    stages: tuple[ModelStage, ...] = ()
    lightgbm_promoted: bool = False
    test_h: Literal["LOCKED", "RUN"] = "LOCKED"
    holdout: Literal["LOCKED", "RUN"] = "LOCKED"
    display: str = ""
    notes: tuple[str, ...] = ()


class HealthCheck(Frozen):
    id: str
    label: str
    state: Literal["OK", "WARN", "FAIL", "NOT_DEPLOYED"]
    detail: str


FreshnessState = Literal["FRESH", "STALE", "MARKET_CLOSED", "UNKNOWN"]


class TimeframeFreshness(Frozen):
    timeframe: Timeframe
    latest_bar_open: datetime | None
    age_seconds: float | None
    """Wall-clock seconds since the last stored bar CLOSED."""
    open_age_seconds: float | None = None
    """The same age counting only minutes when the market was open (calendar-aware)."""
    state: FreshnessState = "UNKNOWN"
    files: int


class StoreStatus(Frozen):
    root: str
    reachable: bool
    read_only: Literal[True] = True
    market_status: MarketStatus
    timeframes: tuple[TimeframeFreshness, ...]
    calendar_aware: Literal[True] = True
    disk_free_gb: float | None


class QuoteResponse(Frozen):
    """Latest quote from the collector's live file (read-only)."""

    available: bool
    state: Literal["FRESH", "STALE", "MARKET_CLOSED", "UNAVAILABLE"]
    market_status: MarketStatus
    reason: str
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    spread_points: float | None = None
    spread_price: float | None = None
    timestamp: datetime | None = None
    age_seconds: float | None = None
    collector_age_seconds: float | None = None


class SymbolInfo(Frozen):
    """Broker contract specification (measured by the collector, never hard-coded)."""

    symbol: str = SYMBOL
    source: Literal["BROKER_LIVE"]
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level_points: int
    freeze_level_points: int


class HealthResponse(Frozen):
    status: Literal["OK", "DEGRADED", "DOWN"]
    version: str
    schema_version: str = SCHEMA_VERSION
    mode: Literal["PAPER"] = "PAPER"
    generated_at: datetime
    uptime_s: float
    checks: tuple[HealthCheck, ...]
    store: StoreStatus


class WsEvent(Frozen):
    """Server push. ``seq`` increases by one per event so a client detects a gap and refetches."""

    type: Literal["hello", "heartbeat", "live", "state", "paper", "human"]
    seq: int = Field(ge=0)
    ts: datetime
    schema_version: str = SCHEMA_VERSION
    data_version: str
    quote: QuoteResponse | None = None
    """``live``: the newest quote."""
    forming: tuple[FormingBar, ...] = ()
    """``live``: the still-open bar of every timeframe."""
    decision_id: str | None = None
    """``state``: the decision changed; the client refetches ``/api/v2/state``."""
    # ``paper``: a position opened or closed; the client refetches ``/api/v2/paper/*``.
