"""Empirical cost distributions and deterministic Monte Carlo of EV (roadmap section 23).

Costs are expressed per trade in R (cost points divided by the trade's risk in points). A candidate
does not pass because it works at the MEDIAN cost: it is evaluated at base, stress and tail costs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

QUANTILES = (0.5, 0.9, 0.95, 0.99)


@dataclass(frozen=True)
class CostSummary:
    """Distribution of one cost component in one bucket."""

    bucket: str
    n: int
    median: float
    p90: float
    p95: float
    p99: float


def summarise(bucket: str, costs: NDArray[np.float64]) -> CostSummary | None:
    """Median and tail quantiles, or None when there are no observations (never invented)."""
    if len(costs) == 0 or not np.all(np.isfinite(costs)):
        return None
    q = np.quantile(costs, QUANTILES)
    return CostSummary(bucket, len(costs), float(q[0]), float(q[1]), float(q[2]), float(q[3]))


def by_bucket(costs: NDArray[np.float64], buckets: list[str]) -> dict[str, CostSummary]:
    """Summaries per bucket (session, volatility regime, news proximity ...)."""
    if len(costs) != len(buckets):
        msg = "costs and buckets must have the same length"
        raise ValueError(msg)
    out: dict[str, CostSummary] = {}
    for name in sorted(set(buckets)):
        mask = np.array([b == name for b in buckets])
        summary = summarise(name, costs[mask])
        if summary is not None:
            out[name] = summary
    return out


@dataclass(frozen=True)
class EvScenarios:
    """Mean net R under four cost assumptions and the Monte Carlo spread."""

    gross_mean_r: float
    base: float
    stress: float
    tail: float
    mc_p05: float
    mc_median: float
    mc_p95: float
    passes_tail: bool


def ev_scenarios(
    gross_r: NDArray[np.float64],
    observed_cost_r: NDArray[np.float64],
    *,
    seed: int,
    draws: int = 2000,
) -> EvScenarios:
    """EV at median (base), p95 (stress) and p99 (tail) per-trade cost, plus a bootstrap of costs.

    The Monte Carlo draws each trade's cost from the empirical distribution with replacement; it is
    deterministic given ``seed``. ``passes_tail`` is True only when the p99 scenario is positive.
    """
    if len(observed_cost_r) == 0 or len(gross_r) == 0:
        msg = "gross results and observed costs are both required"
        raise ValueError(msg)
    q = np.quantile(observed_cost_r, [0.5, 0.95, 0.99])
    gross = float(gross_r.mean())
    rng = np.random.default_rng(seed)
    sims = np.array(
        [
            float(gross_r.mean() - rng.choice(observed_cost_r, size=len(gross_r)).mean())
            for _ in range(draws)
        ]
    )
    return EvScenarios(
        gross_mean_r=gross,
        base=gross - float(q[0]),
        stress=gross - float(q[1]),
        tail=gross - float(q[2]),
        mc_p05=float(np.quantile(sims, 0.05)),
        mc_median=float(np.median(sims)),
        mc_p95=float(np.quantile(sims, 0.95)),
        passes_tail=gross - float(q[2]) > 0,
    )
