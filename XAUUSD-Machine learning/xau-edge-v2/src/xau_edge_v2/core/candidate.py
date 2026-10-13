"""Candidate V2 (``xau_mtf_cv2``): a thin layer around the control's ``decide()``.

The control (``core/decision.py``, baseline v1.1.0) is untouched and pinned. The candidate CALLS it:
the chain labels, the stop, the targets, the net R:R and the sizing are the control's code. With every
flag off ``candidate_step`` returns exactly what ``decide`` returns (parity test). The differences are
the four CORE changes and their guards, frozen in ``docs/research/cand_v2_spec.json``:

* C1  lifecycle memory: a setup stays ARMED for ``memory_bars`` closed M5 bars after its conditions
      stop being true, unless invalidated; a trigger inside the window is judged with the armed
      setup labels (every other input is the current bar's);
* C2  cost-per-risk gate instead of the spread percentile / spread-to-ATR gate (+ spike guard);
* C3a the LOW volatility percentile gate is dropped;
* C3b the HIGH volatility percentile gate and the H4 HIGH_VOLATILITY block are replaced by a SHOCK
      guard;
* C7  (exploratory, never in the frozen candidate) opposing structure from H1 / previous day levels.

Pure and deterministic. PAPER only: nothing here can reach a broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from xau_edge_v2.core.costs import SLIPPAGE_POINTS
from xau_edge_v2.core.decision import (
    BLOCKING_H4,
    Decision,
    DecisionConfig,
    DecisionContext,
    decide,
)
from xau_edge_v2.core.market_state import POINT, MarketState
from xau_edge_v2.core.risk import compute_stop

CAND_ID = "xau_mtf_cv2"
CAND_VERSION = "2.0.0-cand.1"
MEMORY_BARS = 6
COST_R_CAP = 0.15
SPIKE_PERCENTILE = 0.99
COST_CODE = "COST_TOO_HIGH"
SPIKE_CODE = "SPREAD_SPIKE"
SHOCK_CODE = "SHOCK_GUARD"
RESTORE_CODE = "RESTORE_PENDING"


@dataclass(frozen=True)
class CandidateConfig:
    c1: bool = False
    c2: bool = False
    c3a: bool = False
    c3b: bool = False
    c7: bool = False
    memory_bars: int = MEMORY_BARS
    cost_r_cap: float = COST_R_CAP
    spike_percentile: float = SPIKE_PERCENTILE
    base: DecisionConfig = field(default_factory=DecisionConfig)


VARIANTS: dict[str, tuple[str, ...]] = {
    "CTRL": (),
    "A_C1": ("C1",),
    "A_C2": ("C2",),
    "A_C3a": ("C3a",),
    "A_C3b": ("C3b",),
    "B_C1C2": ("C1", "C2"),
    "B_C2C3a": ("C2", "C3a"),
    "CORE": ("C1", "C2", "C3a", "C3b"),
    "LOO_noC1": ("C2", "C3a", "C3b"),
    "LOO_noC2": ("C1", "C3a", "C3b"),
    "LOO_noC3a": ("C1", "C2", "C3b"),
    "LOO_noC3b": ("C1", "C2", "C3a"),
    "X_C7": ("C7",),
    "X_CORE_C7": ("C1", "C2", "C3a", "C3b", "C7"),
}
CORE_TIER = frozenset(v for v in VARIANTS if not v.startswith("X_"))


def config_for(variant: str) -> CandidateConfig:
    flags = {c.lower() for c in VARIANTS[variant]}
    return CandidateConfig(
        c1="c1" in flags, c2="c2" in flags, c3a="c3a" in flags, c3b="c3b" in flags, c7="c7" in flags
    )


@dataclass(frozen=True)
class Observation:
    """Inputs the market state does not carry (computed once per closed M5 bar by the caller)."""

    shock: bool = False
    """SHOCK per the spec: M15 (last 2 bars) / H1 (last bar) range >= 3 ATR, H4 regime SHOCK, M1 ABNORMAL."""
    h1_resistance: float | None = None
    h1_support: float | None = None
    m5_close: float | None = None


@dataclass(frozen=True)
class Memory:
    """Lifecycle memory of one setup (C1). ``side`` None means IDLE."""

    side: str | None = None
    arm_bar: int = -1
    last_armed_bar: int = -1
    planned_stop: float | None = None
    cold: bool = False
    """True after a restart that could NOT restore the checkpoint: the arm bar of a setup that is already
    armed is unknown, so C1 decisions are WAIT until the setup has been off for ``memory_bars + 1`` bars."""
    quiet: int = 0
    """Consecutive bars without the armed condition while ``cold``."""

    @staticmethod
    def cold_start() -> Memory:
        return Memory(cold=True)


@dataclass(frozen=True)
class StepInfo:
    lifecycle: str
    """IDLE / BIASED / ARMED / MEMORY / INVALIDATED / EXPIRED."""
    armed_now: bool
    substituted: bool
    guard: str | None = None
    cost_r: float | None = None
    invalidated_by: str | None = None


def side_of(state: MarketState) -> str | None:
    return {"BULLISH": "BUY", "BEARISH": "SELL"}.get(state.h1_trend)


def _labels(side: str) -> tuple[str, str, str]:
    """(with-trend M15 label, against label, matching pullback label)."""
    if side == "BUY":
        return "UP", "DOWN", "PULLBACK_IN_UPTREND"
    return "DOWN", "UP", "PULLBACK_IN_DOWNTREND"


def armed_now(state: MarketState) -> bool:
    """The control's setup condition at this closed bar (H1 side, no H4 veto, M15 with trend + pullback)."""
    side = side_of(state)
    if side is None or state.h4_regime == BLOCKING_H4[side]:
        return False
    with_trend, _, pullback = _labels(side)
    return state.m15_structure == with_trend and state.m15_pullback == pullback


def _against(state: MarketState, side: str) -> bool:
    _, against, _ = _labels(side)
    reversal = "REVERSAL_DOWN" if side == "BUY" else "REVERSAL_UP"
    return state.m15_structure in (against, reversal)


def _planned_stop(state: MarketState, side: str) -> float | None:
    direction = 1 if side == "BUY" else -1
    atr, price = state.atr_m15, state.price
    if atr is None or atr <= 0 or price is None:
        return None
    swing = state.snapshots.get("M5")
    level = None
    if swing is not None:
        level = swing.last_swing_low if direction > 0 else swing.last_swing_high
    stop = compute_stop(direction, price, level, atr)
    return None if stop is None else stop.price


def _invalidation(  # noqa: PLR0911 - one return per invalidation reason
    state: MarketState, mem: Memory, obs: Observation
) -> str | None:
    """Why the remembered setup is no longer valid at this bar (None: still valid)."""
    assert mem.side is not None
    if side_of(state) != mem.side:
        return "H1_BIAS"
    if state.h4_regime == BLOCKING_H4[mem.side]:
        return "H4_VETO"
    if _against(state, mem.side):
        return "M15_AGAINST"
    if obs.shock:
        return "SHOCK"
    if state.data_quality in ("STALE", "UNKNOWN") or not state.market_open:
        return "DATA"
    close = obs.m5_close
    if close is not None and mem.planned_stop is not None:
        beyond = close <= mem.planned_stop if mem.side == "BUY" else close >= mem.planned_stop
        if beyond:
            return "STOP_LEVEL"
    return None


def advance_memory(  # noqa: PLR0911 - one return per lifecycle state
    mem: Memory, state: MarketState, obs: Observation, bar: int, cfg: CandidateConfig
) -> tuple[Memory, str, str | None]:
    """The lifecycle after this closed M5 bar: (memory, lifecycle label, invalidated_by)."""
    side = side_of(state)
    if mem.cold:
        # the state of an already armed setup is unknown: wait until any memory would have expired anyway
        quiet = 0 if armed_now(state) else mem.quiet + 1
        if quiet > cfg.memory_bars:
            return Memory(), "IDLE", None
        return Memory(cold=True, quiet=quiet), "RESTORE_PENDING", None
    invalid: str | None = None
    if mem.side is not None:
        invalid = _invalidation(state, mem, obs)
        if invalid is not None:
            mem = Memory()
    now = armed_now(state)
    if now and side is not None:
        if mem.side != side:
            mem = Memory(side, bar, bar, _planned_stop(state, side))
        else:
            mem = replace(mem, last_armed_bar=bar)
        return mem, "ARMED", invalid
    if mem.side is not None:
        if bar - mem.last_armed_bar > cfg.memory_bars:
            return Memory(), "EXPIRED", None
        return mem, "MEMORY", None
    if invalid is not None:
        return mem, "INVALIDATED", invalid
    return mem, "BIASED" if side is not None else "IDLE", None


def _veto(d: Decision, code: str) -> Decision:
    """The same decision turned into WAIT by a candidate guard (the control's chain had passed)."""
    return replace(
        d,
        action="WAIT",
        readiness_level=min(d.readiness_level, 5),
        refusals=(code,),
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        take_profit_2=None,
        net_rr=None,
        gross_rr=None,
        required_win_rate=None,
        stop_model=None,
        capped_by_structure=False,
        lots=None,
        risk_amount=None,
        expiry=None,
        entry_quality="",
        setup_id="",
        invalidation=None,
        cost=None,
    )


def quote_spread_points(ctx: DecisionContext, state: MarketState) -> float | None:
    """The spread of the EXECUTABLE quote when the context has one (spec: execution_timing), else the state's."""
    if ctx.bid is not None and ctx.ask is not None and ctx.ask >= ctx.bid:
        return (ctx.ask - ctx.bid) / POINT
    return state.spread


def cost_r(d: Decision, spread_points: float | None) -> float | None:
    """(spread + 2 x slippage) / |entry quote - stop|, all in price units; None when it cannot be known."""
    if spread_points is None or d.entry_price is None or d.stop_loss is None:
        return None
    risk = abs(d.entry_price - d.stop_loss)
    if risk <= 0:
        return None
    return (spread_points * POINT + 2 * SLIPPAGE_POINTS * POINT) / risk


def _decision_config(cfg: CandidateConfig) -> DecisionConfig:
    base = cfg.base
    return replace(
        base,
        block_low_volatility=base.block_low_volatility and not cfg.c3a,
        block_high_volatility=base.block_high_volatility and not cfg.c3b,
        blocked_regimes=("SHOCK",) if cfg.c3b else base.blocked_regimes,
    )


def _opposing_from_higher_timeframes(state: MarketState, obs: Observation) -> MarketState:
    """C7: distance to the nearest H1 swing / previous-day extreme instead of the nearest M15 swing."""
    price = state.price
    if price is None:
        return state
    above = [x for x in (obs.h1_resistance, state.pdh) if x is not None and x > price]
    below = [x for x in (obs.h1_support, state.pdl) if x is not None and x < price]
    return replace(
        state,
        distance_to_resistance=min(above) - price if above else None,
        distance_to_support=price - max(below) if below else None,
    )


def candidate_step(
    mem: Memory,
    state: MarketState,
    ctx: DecisionContext,
    cfg: CandidateConfig,
    obs: Observation,
    bar: int,
) -> tuple[Decision, Memory, StepInfo]:
    """The candidate's decision at one closed M5 bar, and the lifecycle memory to carry forward."""
    new_mem, lifecycle, invalid = advance_memory(mem, state, obs, bar, cfg)
    now = armed_now(state)
    work = state
    substituted = False
    if cfg.c1 and new_mem.side is not None and not now and side_of(state) == new_mem.side:
        with_trend, _, pullback = _labels(new_mem.side)
        work = replace(work, m15_structure=with_trend, m15_pullback=pullback)
        substituted = True
    if cfg.c7:
        work = _opposing_from_higher_timeframes(work, obs)
    if cfg.c2 and state.execution_quality in ("GOOD", "POOR"):
        spike = (
            state.spread_percentile is not None and state.spread_percentile >= cfg.spike_percentile
        )
        work = replace(work, execution_quality="POOR" if spike else "GOOD")
    d = decide(work, ctx, _decision_config(cfg))
    guard: str | None = None
    ratio: float | None = None
    if d.action != "WAIT":
        if cfg.c3b and obs.shock:
            guard = SHOCK_CODE
        elif cfg.c2:
            ratio = cost_r(d, quote_spread_points(ctx, state))
            if ratio is None or ratio > cfg.cost_r_cap:
                guard = COST_CODE
        if guard is not None:
            d = _veto(d, guard)
    if cfg.c1 and new_mem.cold and d.action != "WAIT":
        guard = RESTORE_CODE  # the checkpoint could not be restored: never act on a state that may differ from a continuous run
        d = _veto(d, guard)
    # the decision must carry the RAW state (what the market said), never the labels C1 substituted
    d = replace(d, state=state)
    if substituted:
        d = replace(
            d,
            reasons=(
                *d.reasons,
                f"C1: setup remembered (armed {bar - new_mem.arm_bar} bars ago, last armed "
                f"{bar - new_mem.last_armed_bar} bars ago); M15 labels substituted, raw M15 "
                f"{state.m15_structure}/{state.m15_pullback}",
            ),
        )
    if not cfg.c1:
        new_mem = Memory()  # no memory is carried when C1 is off (the control's same-bar rule)
    return d, new_mem, StepInfo(lifecycle, now, substituted, guard, ratio, invalid)
