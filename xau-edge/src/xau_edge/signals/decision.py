"""The decision layer: forecast -> checks -> BUY / SELL / WAIT (briefs sections 2, 21, 56).

WAIT is the default and the only output unless every check passes AND the evidence gate is open.
All thresholds are in ``DecisionPolicy`` (configuration), none are buried in the logic.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.signals.expected_value import cost_in_r
from xau_edge.signals.explain import explain
from xau_edge.signals.schema import Direction, EvidenceStatus, NoTradeReason, Signal
from xau_edge.structure.regime import Regime

_PROB_TOLERANCE = 1e-6


class SignalInputs(BaseModel):
    """Everything the decision may look at (and nothing else)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symbol: str = "XAUUSD"
    timestamp: datetime
    timeframe: str = "M15"
    price: float
    atr: float
    spread_points: float
    regime: str | None = None
    htf_bias: dict[str, int] = Field(default_factory=dict)
    prob_up: float | None = None
    prob_down: float | None = None
    prob_neutral: float | None = None
    probability_source: str = "none"
    n_matches: int = 0
    similarity_quality: float | None = None
    analogue_expected_r_long: float | None = None
    analogue_expected_r_short: float | None = None
    analogue_mean_return: float | None = None
    nearest_resistance: float | None = None
    nearest_support: float | None = None
    news_blocked: bool | None = None
    data_valid: bool = True
    evidence_status: EvidenceStatus = EvidenceStatus.NONE

    def digest(self) -> str:
        """Stable hash of the inputs so a signal can be reproduced and audited."""
        canonical = json.dumps(self.model_dump(mode="json"), sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class DecisionPolicy(BaseModel):
    """Thresholds of the checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    edge_threshold: float = Field(default=0.15, ge=0)
    min_probability: float = Field(default=0.40, ge=0, le=1)
    min_ev_r: float = 0.0
    min_risk_reward: float = Field(default=1.5, gt=0)
    stop_atr: float = Field(default=1.5, gt=0)
    tp1_atr: float = Field(default=3.0, gt=0)
    tp2_atr: float = Field(default=4.5, gt=0)
    entry_buffer_atr: float = Field(default=0.1, ge=0)
    blocked_regimes: tuple[str, ...] = ("SHOCK",)
    max_spread_points: float = Field(default=120.0, gt=0)
    min_matches: int = Field(default=15, ge=1)
    max_similarity_ratio: float = Field(default=0.8, gt=0)
    slippage_points: float = Field(default=3.0, ge=0)
    min_clearance_atr: float = Field(default=1.0, ge=0)
    expiry_bars: int = Field(default=4, ge=1)
    bar_minutes: int = Field(default=15, ge=1)
    require_htf_alignment: bool = True


def _finite(*values: float | None) -> bool:
    return all(v is not None and math.isfinite(v) for v in values)


_TIMEFRAMES_REQUIRED = ("H4", "H1")
_KNOWN_REGIMES = frozenset(r.value for r in Regime)


def _optional_finite(*values: float | None) -> bool:
    """True if every value that is present is finite (None means 'not provided')."""
    return all(v is None or math.isfinite(v) for v in values)


def _valid(inp: SignalInputs) -> bool:  # noqa: PLR0911 - one early exit per invalid input
    if not inp.data_valid or not _finite(inp.price, inp.atr, inp.spread_points):
        return False
    if inp.atr <= 0 or inp.price <= 0 or inp.spread_points < 0 or inp.n_matches < 0:
        return False
    if not _optional_finite(
        inp.similarity_quality,
        inp.analogue_expected_r_long,
        inp.analogue_expected_r_short,
        inp.analogue_mean_return,
        inp.nearest_resistance,
        inp.nearest_support,
    ):
        return False
    if any(tf not in inp.htf_bias for tf in _TIMEFRAMES_REQUIRED) or any(
        v not in (-1, 0, 1) for v in inp.htf_bias.values()
    ):
        return False
    if inp.nearest_resistance is not None and inp.nearest_resistance < inp.price:
        return False
    if inp.nearest_support is not None and inp.nearest_support > inp.price:
        return False
    probs = (inp.prob_up, inp.prob_down, inp.prob_neutral)
    if not _finite(*probs):
        return False
    total = sum(p for p in probs if p is not None)
    return abs(total - 1.0) <= _PROB_TOLERANCE and all(p is not None and p >= 0 for p in probs)


def _probabilities(inp: SignalInputs) -> tuple[float, float, float]:
    """(up, down, neutral) once ``_valid`` has confirmed they exist."""
    if inp.prob_up is None or inp.prob_down is None or inp.prob_neutral is None:
        msg = "probabilities are missing"
        raise ValueError(msg)
    return inp.prob_up, inp.prob_down, inp.prob_neutral


def decide(  # noqa: PLR0912, PLR0915 - one independent check per refusal reason
    inp: SignalInputs, policy: DecisionPolicy | None = None, *, code_version: str = ""
) -> Signal:
    """Apply every check; return BUY/SELL only if none refused and the evidence gate is open."""
    pol = policy or DecisionPolicy()
    reasons: list[NoTradeReason] = []
    if inp.evidence_status is not EvidenceStatus.VALIDATED:
        reasons.append(NoTradeReason.NO_VALIDATED_EDGE)

    valid = _valid(inp)
    if not valid:
        reasons.append(NoTradeReason.DATA_INVALID)

    candidate: Direction | None = None
    probs: tuple[float, float, float] | None = None
    if valid:
        up, down, neutral = _probabilities(inp)
        probs = (down, neutral, up)
        edge = round(up - down, 12)
        if edge >= pol.edge_threshold and round(up, 12) >= pol.min_probability:
            candidate = Direction.BUY
        elif edge <= -pol.edge_threshold and round(down, 12) >= pol.min_probability:
            candidate = Direction.SELL
        else:
            reasons.append(NoTradeReason.EDGE_INSUFFICIENT)

    entry_zone = stop = tp1 = tp2 = rr = expected_r = None
    if valid and candidate is not None:
        sign = 1 if candidate is Direction.BUY else -1
        stop_dist = pol.stop_atr * inp.atr
        buffer = pol.entry_buffer_atr * inp.atr
        entry_zone = (inp.price - buffer, inp.price + buffer)
        stop = inp.price - sign * stop_dist
        tp1 = inp.price + sign * pol.tp1_atr * inp.atr
        tp2 = inp.price + sign * pol.tp2_atr * inp.atr
        rr = pol.tp1_atr / pol.stop_atr
        if rr < pol.min_risk_reward:
            reasons.append(NoTradeReason.RISK_REWARD_POOR)
        gross = inp.analogue_expected_r_long if sign > 0 else inp.analogue_expected_r_short
        if gross is None:
            reasons.append(NoTradeReason.MODEL_UNCERTAIN)
        else:
            cost = cost_in_r(inp.spread_points, pol.slippage_points, stop_dist)
            expected_r = gross - cost
            if not expected_r > pol.min_ev_r:
                reasons.append(NoTradeReason.EV_NOT_POSITIVE)
        if pol.require_htf_alignment and any(
            inp.htf_bias.get(tf, 0) * sign < 0 for tf in ("H4", "H1")
        ):
            reasons.append(NoTradeReason.HTF_BIAS_CONFLICT)
        clearance = pol.min_clearance_atr * inp.atr
        above = None if inp.nearest_resistance is None else inp.nearest_resistance - inp.price
        below = None if inp.nearest_support is None else inp.price - inp.nearest_support
        opposing = above if sign > 0 else below
        if opposing is not None and 0 <= opposing < clearance:
            reasons.append(NoTradeReason.ENTRY_QUALITY_POOR)

    if inp.regime not in _KNOWN_REGIMES or inp.regime in pol.blocked_regimes:
        reasons.append(NoTradeReason.REGIME_UNSUPPORTED)
    if inp.news_blocked is None:
        reasons.append(NoTradeReason.NEWS_UNKNOWN)
    elif inp.news_blocked:
        reasons.append(NoTradeReason.NEWS_RISK)
    if valid and inp.spread_points > pol.max_spread_points:
        reasons.append(NoTradeReason.SPREAD_EXCESSIVE)
    if (
        inp.n_matches < pol.min_matches
        or inp.similarity_quality is None
        or inp.similarity_quality > pol.max_similarity_ratio
    ):
        reasons.append(NoTradeReason.MODEL_UNCERTAIN)

    unique = tuple(dict.fromkeys(reasons))
    final = candidate if (not unique and candidate is not None) else Direction.WAIT
    expiry = inp.timestamp + timedelta(minutes=pol.bar_minutes * pol.expiry_bars)
    htf = ", ".join(f"{tf}:{inp.htf_bias.get(tf, 0):+d}" for tf in ("H4", "H1", "M15", "M5"))
    return Signal(
        symbol=inp.symbol,
        timestamp=inp.timestamp,
        timeframe=inp.timeframe,
        direction=final,
        candidate_direction=candidate,
        prob_up=inp.prob_up if valid else None,
        prob_down=inp.prob_down if valid else None,
        prob_neutral=inp.prob_neutral if valid else None,
        probability_source=inp.probability_source,
        expected_return=inp.analogue_mean_return,
        expected_R=expected_r,
        market_regime=inp.regime,
        higher_timeframe_bias=htf,
        entry_zone=entry_zone,
        stop_loss=stop,
        take_profit_1=tp1,
        take_profit_2=tp2,
        risk_reward=rr,
        signal_expiry=expiry,
        explanation=explain(
            candidate=candidate,
            final=final,
            reasons=unique,
            htf_bias=inp.htf_bias,
            regime=inp.regime,
            probs=probs,
            n_matches=inp.n_matches,
            expected_r=expected_r,
            atr=inp.atr if _finite(inp.atr) else None,
            source=inp.probability_source,
        ),
        historical_matches_count=inp.n_matches,
        similarity_quality=inp.similarity_quality,
        evidence_status=inp.evidence_status,
        reasons=unique,
        inputs_hash=inp.digest(),
        code_version=code_version,
    )
