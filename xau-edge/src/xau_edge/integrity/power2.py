"""Power engine V2 (roadmap section 15): effective N, planted-edge simulation.

The V1 formula (``research.power``) is the i.i.d. lower bound. V2 reports it for BOTH raw and
effective N, and adds a simulator so the gate's real behaviour (false positives, false negatives)
is measured instead of assumed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from numpy.typing import NDArray

from xau_edge.research.power import BASE_ALPHA, DEFAULT_POWER, DEFAULT_SD

_NORMAL = NormalDist()
SCENARIOS = ("independent", "clustered", "overlapping")


@dataclass(frozen=True)
class PowerReport:
    """Power numbers for one hypothesis or candidate."""

    raw_n: int
    effective_n: float | None
    k: int
    alpha: float
    power_target: float
    sd: float
    mde_raw: float
    mde_effective: float | None
    required_effective_n_for_target: dict[str, int]
    adequately_powered: bool | None


def _mde(k: int, n: float, sd: float, power: float, alpha: float) -> float:
    if k < 1 or n <= 0 or sd <= 0 or not 0 < power < 1 or not 0 < alpha < 1:
        msg = "invalid power inputs"
        raise ValueError(msg)
    z = _NORMAL.inv_cdf(1 - alpha / k) + _NORMAL.inv_cdf(power)
    return z * sd / math.sqrt(n)


def power_report(
    *,
    raw_n: int,
    effective_n: float | None,
    k: int,
    sd: float = DEFAULT_SD,
    power: float = DEFAULT_POWER,
    alpha: float = BASE_ALPHA,
    targets: tuple[float, ...] = (0.05, 0.10, 0.20),
    cap: float = 0.20,
) -> PowerReport:
    """MDE for raw and effective N. "Adequately powered" needs effective N, never raw N alone."""
    mde_raw = _mde(k, raw_n, sd, power, alpha)
    mde_eff = _mde(k, effective_n, sd, power, alpha) if effective_n and effective_n > 0 else None
    z = _NORMAL.inv_cdf(1 - alpha / k) + _NORMAL.inv_cdf(power)
    needed = {f"{t:.2f}R": math.ceil((z * sd / t) ** 2) for t in targets}
    return PowerReport(
        raw_n=raw_n,
        effective_n=effective_n,
        k=k,
        alpha=alpha,
        power_target=power,
        sd=sd,
        mde_raw=mde_raw,
        mde_effective=mde_eff,
        required_effective_n_for_target=needed,
        adequately_powered=None if mde_eff is None else mde_eff <= cap,
    )


def simulate_sample(
    rng: np.random.Generator,
    *,
    effect: float,
    scenario: str,
    days: int = 250,
    per_day: int = 3,
    sd: float = DEFAULT_SD,
    rho: float = 0.3,
    hold: int = 4,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Planted-edge trade sample: values (mean ``effect``, sd ``sd``) and their day ids."""
    if scenario not in SCENARIOS:
        msg = f"unknown scenario {scenario!r}"
        raise ValueError(msg)
    n = days * per_day
    day_ids = np.repeat(np.arange(days, dtype=np.int64), per_day)
    noise = rng.standard_normal(n)
    if scenario == "independent":
        values = noise
    elif scenario == "clustered":
        shared = np.repeat(rng.standard_normal(days), per_day)
        values = math.sqrt(rho) * shared + math.sqrt(1 - rho) * noise
    else:  # overlapping outcomes: each result shares `hold` consecutive increments
        steps = rng.standard_normal(n + hold - 1)
        kernel = np.ones(hold) / math.sqrt(hold)
        values = np.convolve(steps, kernel, mode="valid")
    return effect + sd * values, day_ids


def cluster_t_stat(values: NDArray[np.float64], day_ids: NDArray[np.int64]) -> float:
    """t statistic of the mean using day-cluster robust standard errors."""
    labels, inverse = np.unique(day_ids, return_inverse=True)
    g = len(labels)
    if g < 2:
        return 0.0
    mean = values.mean()
    sums = np.bincount(inverse, weights=values - mean)
    se = math.sqrt(float(np.sum(sums**2)) * g / (g - 1)) / len(values)
    return 0.0 if se == 0 else float(mean / se)


def rejection_rate(
    *,
    effect: float,
    scenario: str,
    k: int,
    sims: int = 400,
    seed: int = 1,
    days: int = 250,
    per_day: int = 3,
    clustered_test: bool = True,
) -> float:
    """Fraction of simulated samples where the one-sided Bonferroni test at alpha/K rejects."""
    rng = np.random.default_rng(seed)
    crit = _NORMAL.inv_cdf(1 - BASE_ALPHA / k)
    hits = 0
    for _ in range(sims):
        values, day_ids = simulate_sample(
            rng, effect=effect, scenario=scenario, days=days, per_day=per_day
        )
        if clustered_test:
            t = cluster_t_stat(values, day_ids)
        else:
            sd = float(values.std(ddof=1))
            t = float(values.mean() / (sd / math.sqrt(len(values)))) if sd > 0 else 0.0
        hits += t > crit
    return hits / sims


def planted_edge_table(
    *,
    k: int = 21,
    effects: tuple[float, ...] = (0.0, 0.05, 0.10, 0.20),
    sims: int = 400,
    seed: int = 1,
) -> dict[str, dict[str, float]]:
    """Rejection rate per effect and scenario: row 0.00R is the false-positive rate."""
    return {
        f"{e:.2f}R": {
            s: rejection_rate(effect=e, scenario=s, k=k, sims=sims, seed=seed) for s in SCENARIOS
        }
        for e in effects
    }
