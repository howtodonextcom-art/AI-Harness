"""Placebo engine (roadmap section 13): deterministic reference distributions.

A placebo is DIAGNOSTIC. It reports where the real statistic falls in a distribution produced by a
procedure that should carry no edge; it is never an extra pass criterion unless a pre-registered
protocol says so.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class PlaceboResult:
    """Real statistic against its placebo distribution."""

    real: float
    n_placebo: int
    median: float
    p95: float
    p99: float
    empirical_percentile: float
    seed: int


def run_placebo(
    real: float,
    placebo_stat: Callable[[np.random.Generator], float],
    *,
    n: int = 1000,
    seed: int,
) -> PlaceboResult:
    """Draw ``n`` placebo statistics with a seeded generator (same seed, same result)."""
    if n < 50:
        msg = "at least 50 placebo draws are needed"
        raise ValueError(msg)
    rng = np.random.default_rng(seed)
    draws = np.array([placebo_stat(rng) for _ in range(n)], dtype=np.float64)
    if not np.all(np.isfinite(draws)):
        msg = "a placebo draw was not finite"
        raise ValueError(msg)
    return PlaceboResult(
        real=real,
        n_placebo=n,
        median=float(np.median(draws)),
        p95=float(np.quantile(draws, 0.95)),
        p99=float(np.quantile(draws, 0.99)),
        empirical_percentile=float(np.mean(draws <= real)),
        seed=seed,
    )


def shift_placebo(
    outcomes: NDArray[np.float64], directions: NDArray[np.float64], shift: int
) -> float:
    """Mean outcome when each event's direction is applied to the outcome ``shift`` events away."""
    if shift == 0 or abs(shift) >= len(outcomes):
        msg = "shift must be non-zero and smaller than the sample"
        raise ValueError(msg)
    rolled = np.roll(outcomes, shift)
    valid = slice(shift, None) if shift > 0 else slice(None, shift)
    return float(np.mean((directions * rolled)[valid]))


def flip_placebo(directions_times_outcome: NDArray[np.float64]) -> float:
    """Mean outcome with every direction flipped (the mirror of the real result)."""
    return float(-np.mean(directions_times_outcome))


def random_pool_placebo(
    pool: NDArray[np.float64], size: int
) -> Callable[[np.random.Generator], float]:
    """Placebo that draws ``size`` outcomes from a matched pool (same session/regime/vol bucket)."""
    if size < 1 or len(pool) < size:
        msg = "the matched pool is smaller than the sample"
        raise ValueError(msg)

    def draw(rng: np.random.Generator) -> float:
        return float(np.mean(rng.choice(pool, size=size, replace=False)))

    return draw


def block_permutation_placebo(
    outcomes: NDArray[np.float64], directions: NDArray[np.float64], block: int
) -> Callable[[np.random.Generator], float]:
    """Placebo that permutes outcomes within blocks of ``block`` consecutive events."""
    if block < 2 or len(outcomes) < block:
        msg = "block must be >= 2 and not larger than the sample"
        raise ValueError(msg)

    def draw(rng: np.random.Generator) -> float:
        permuted = outcomes.copy()
        for start in range(0, len(outcomes), block):
            chunk = permuted[start : start + block]
            permuted[start : start + block] = rng.permutation(chunk)
        return float(np.mean(directions * permuted))

    return draw
