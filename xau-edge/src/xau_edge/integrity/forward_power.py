"""Forward-evidence readiness without a hard-coded trade count (roadmap section 22).

``100`` trades survives only as a labelled legacy reference. The real requirement is candidate
specific: the effective sample size needed to detect the target effect at the target power, plus a
minimum calendar exposure and regime coverage. Raw N alone never concludes anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

LEGACY_MIN_TRADES = 100
INCONCLUSIVE = "INCONCLUSIVE"
CONSISTENT = "CONSISTENT"
INCONSISTENT = "INCONSISTENT"
_NORMAL = NormalDist()


@dataclass(frozen=True)
class ForwardReadiness:
    """Everything the console shows about whether the forward sample can conclude."""

    raw_n: int
    effective_n: float
    required_effective_n: int
    calendar_days: float
    minimum_calendar_days: float
    regimes_seen: int
    regimes_required: int
    power_estimate: float
    legacy_reference_trades: int
    conclusion: str
    reasons: tuple[str, ...]


def required_effective_n(target_effect: float, sd: float, power: float, alpha: float) -> int:
    """Effective N to detect ``target_effect`` (one-sided) at ``power`` and ``alpha``."""
    if target_effect <= 0 or sd <= 0 or not 0 < power < 1 or not 0 < alpha < 1:
        msg = "invalid forward power inputs"
        raise ValueError(msg)
    z = _NORMAL.inv_cdf(1 - alpha) + _NORMAL.inv_cdf(power)
    return math.ceil((z * sd / target_effect) ** 2)


def power_at(effective_n: float, target_effect: float, sd: float, alpha: float) -> float:
    """Power to detect ``target_effect`` with ``effective_n`` observations."""
    if effective_n <= 0 or sd <= 0:
        return 0.0
    return _NORMAL.cdf(target_effect / (sd / math.sqrt(effective_n)) - _NORMAL.inv_cdf(1 - alpha))


def readiness(
    *,
    raw_n: int,
    effective_n: float,
    calendar_days: float,
    regimes_seen: int,
    observed_mean: float,
    observed_sd: float,
    expected_lower_bound: float,
    target_effect: float,
    expected_sd: float,
    power: float = 0.8,
    alpha: float = 0.05,
    minimum_calendar_days: float = 90.0,
    regimes_required: int = 2,
) -> ForwardReadiness:
    """INCONCLUSIVE until every requirement is met; then CONSISTENT or INCONSISTENT with Stage 2."""
    need = required_effective_n(target_effect, expected_sd, power, alpha)
    reasons: list[str] = []
    if effective_n < need:
        reasons.append(f"effective N {effective_n:.0f} below the required {need}")
    if calendar_days < minimum_calendar_days:
        reasons.append(
            f"{calendar_days:.0f} calendar days below the required {minimum_calendar_days:.0f}"
        )
    if regimes_seen < regimes_required:
        reasons.append(f"{regimes_seen} regimes seen, {regimes_required} required")
    estimate = power_at(effective_n, target_effect, expected_sd, alpha)
    if reasons:
        conclusion = INCONCLUSIVE
    else:
        se = observed_sd / math.sqrt(effective_n)
        upper = observed_mean + 1.959964 * se
        conclusion = INCONSISTENT if upper < expected_lower_bound else CONSISTENT
        if conclusion == INCONSISTENT:
            reasons.append("observed upper bound is below the Stage 2 lower bound")
    return ForwardReadiness(
        raw_n=raw_n,
        effective_n=effective_n,
        required_effective_n=need,
        calendar_days=calendar_days,
        minimum_calendar_days=minimum_calendar_days,
        regimes_seen=regimes_seen,
        regimes_required=regimes_required,
        power_estimate=estimate,
        legacy_reference_trades=LEGACY_MIN_TRADES,
        conclusion=conclusion,
        reasons=tuple(reasons),
    )
