"""Statistics of the candidate evaluation (spec: ``cand_v2_spec.json`` -> statistics).

* the primary endpoint is the mean realised net R per executed trade;
* its uncertainty is a one-sided 97.5% bound from a calendar-month block bootstrap (B = 10000, seed 7);
* below ``N_MIN`` trades or ``MONTHS_MIN`` months with trades every outcome inference is INCONCLUSIVE;
* ``REFUTED_HARM`` needs the UPPER bound below 0; ``SUPPORTED`` needs the LOWER bound above 0 AND
  N >= N_req(0.20R); everything else is ``INCONCLUSIVE``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import numpy as np

N_MIN = 30
MONTHS_MIN = 12
SD_R = 1.5
DEFF = 1.5
ALPHA = 0.025
POWER = 0.8
DELTA_SUPPORT = 0.20
BOOTSTRAP = 10_000
SEED = 7
MAX_DRAWDOWN_R = 20.0
WORST_MONTH_R = -8.0

Status = Literal["SUPPORTED", "REFUTED_HARM", "INCONCLUSIVE"]


def n_required(delta: float, *, sd: float = SD_R, deff: float = DEFF) -> int:
    z = NormalDist().inv_cdf
    return math.ceil(deff * ((z(1 - ALPHA) + z(POWER)) * sd / delta) ** 2)


@dataclass(frozen=True)
class Bound:
    mean: float
    lower: float
    upper: float
    n: int
    months: int


def block_bootstrap(values: Sequence[float], months: Sequence[str], *, b: int = BOOTSTRAP) -> Bound:
    """Mean and one-sided 97.5% bounds, resampling whole calendar months with replacement."""
    x = np.asarray(values, dtype=float)
    if x.size == 0:
        return Bound(math.nan, math.nan, math.nan, 0, 0)
    labels = sorted(set(months))
    idx = {m: np.flatnonzero(np.asarray(months) == m) for m in labels}
    sums = np.array([x[idx[m]].sum() for m in labels])
    counts = np.array([len(idx[m]) for m in labels], dtype=float)
    rng = np.random.default_rng(SEED)
    pick = rng.integers(0, len(labels), size=(b, len(labels)))
    boot = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return Bound(
        float(x.mean()),
        float(np.quantile(boot, ALPHA)),
        float(np.quantile(boot, 1 - ALPHA)),
        int(x.size),
        len(labels),
    )


def classify(bound: Bound) -> tuple[Status, str]:
    """Status of H: E is not harmful / is positive, with the reason in words."""
    if bound.n < N_MIN or bound.months < MONTHS_MIN:
        return (
            "INCONCLUSIVE",
            f"N={bound.n}, months={bound.months} below N_min={N_MIN}/{MONTHS_MIN}",
        )
    if bound.upper < 0:
        return "REFUTED_HARM", f"upper 97.5% bound {bound.upper:.3f}R < 0"
    if bound.lower > 0 and bound.n >= n_required(DELTA_SUPPORT):
        return (
            "SUPPORTED",
            f"lower 97.5% bound {bound.lower:.3f}R > 0 with N >= {n_required(DELTA_SUPPORT)}",
        )
    return (
        "INCONCLUSIVE",
        f"bounds [{bound.lower:.3f}, {bound.upper:.3f}]R, N={bound.n} (N_req(0.20R)={n_required(DELTA_SUPPORT)})",
    )


def drawdown_r(r_in_time_order: Sequence[float]) -> float:
    """Largest peak-to-trough fall of the cumulative R (a positive number)."""
    if len(r_in_time_order) == 0:
        return 0.0
    curve = np.cumsum(np.asarray(r_in_time_order, dtype=float))
    peak = np.maximum.accumulate(np.concatenate([[0.0], curve]))[1:]
    return float(np.max(peak - curve).clip(min=0.0))


def worst_month_r(r_values: Sequence[float], months: Sequence[str]) -> float:
    if len(r_values) == 0:
        return 0.0
    totals: dict[str, float] = {}
    for r, m in zip(r_values, months, strict=True):
        totals[m] = totals.get(m, 0.0) + r
    return min(totals.values())


def safety_caps_hold(
    r_in_time_order: Sequence[float], months: Sequence[str]
) -> tuple[bool, float, float]:
    mdd = drawdown_r(r_in_time_order)
    worst = worst_month_r(r_in_time_order, months)
    return (mdd <= MAX_DRAWDOWN_R and worst >= WORST_MONTH_R), mdd, worst
