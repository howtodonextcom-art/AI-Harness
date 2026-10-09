"""Calibration of the binding robustness gates by planted-strategy simulation (roadmap section 16).

The thresholds are those of roadmap section 21, fixed BEFORE use. Simulation estimates, for each
gate, how often a strategy with no edge passes (false positive) and how often a strategy with a
real edge passes (power). A gate is only classified, never silently changed: a proposed threshold
revision needs a versioned document and applies to future registered experiments only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

SD = 1.3
EFFECTS = (0.0, 0.05, 0.10, 0.20)
SUPPORTED = "SUPPORTED"
CONSERVATIVE = "CONSERVATIVE"
OVER_STRICT = "OVER-STRICT"
UNDER_STRICT = "UNDER-STRICT"
UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class GateRates:
    """Pass rate of one gate at each planted effect (key "0.00R" is the false-positive rate)."""

    gate: str
    pass_rate: dict[str, float]
    classification: str
    reason: str


def temporal_gate(year_means: NDArray[np.float64], year_profit: NDArray[np.float64]) -> bool:
    """Positive in >= 70% of years and no year above 40% of total profit."""
    if len(year_means) == 0:
        return False
    if float(np.mean(year_means > 0)) < 0.70:
        return False
    total = float(year_profit.sum())
    return total > 0 and float(year_profit.max()) / total <= 0.40


def parameter_gate(chosen_mean: float, neighbour_means: NDArray[np.float64]) -> bool:
    """Every neighbour above zero and at least half of the chosen (best) variant."""
    if chosen_mean <= 0 or len(neighbour_means) == 0:
        return False
    return bool(np.all(neighbour_means > 0) and np.all(neighbour_means >= 0.5 * chosen_mean))


def broker_gate(mean_a: float, mean_b: float) -> bool:
    """Same sign and at least half of broker A's mean net R."""
    return mean_a > 0 and mean_b > 0 and mean_b >= 0.5 * mean_a


def _simulate(
    gate: str, effect: float, rng: np.random.Generator, years: int, per_year: int
) -> bool:
    if gate == "temporal":
        data = effect + SD * rng.standard_normal((years, per_year))
        return temporal_gate(data.mean(axis=1), data.sum(axis=1))
    # selection: the chosen variant is the best of 6 correlated grid points (a lucky pick)
    common = rng.standard_normal(years * per_year)
    grid = np.array(
        [
            effect
            + SD * (math.sqrt(0.8) * common + math.sqrt(0.2) * rng.standard_normal(common.size))
            for _ in range(6)
        ]
    )
    means = grid.mean(axis=1)
    best = int(np.argmax(means))
    if gate == "parameter":
        others = np.delete(means, best)
        near = others[:2]  # the two grid neighbours of the chosen point
        return parameter_gate(float(means[best]), near)
    # broker: same events, broker B sees the same signal with its own costs/noise
    chosen = grid[best]
    on_b = 0.7 * (chosen - effect) + math.sqrt(1 - 0.49) * SD * rng.standard_normal(chosen.size)
    return broker_gate(float(chosen.mean()), float(effect + on_b.mean()))


def classify(
    false_positive: float, power: float, *, informative_effect: float = 0.10
) -> tuple[str, str]:
    """Rule fixed here, before any result is looked at."""
    if false_positive > 0.20:
        return UNDER_STRICT, f"passes {false_positive:.0%} of no-edge strategies"
    if power < 0.40:
        return OVER_STRICT, f"passes only {power:.0%} of real {informative_effect:.2f}R edges"
    if false_positive <= 0.10 and power >= 0.70:
        return SUPPORTED, f"false positives {false_positive:.0%}, power {power:.0%}"
    return CONSERVATIVE, f"false positives {false_positive:.0%}, power {power:.0%}"


def calibrate(
    *, sims: int = 400, seed: int = 1, years: int = 8, per_year: int = 150
) -> list[GateRates]:
    """Estimate pass rates for the temporal, parameter-stability and broker gates."""
    out = []
    for gate in ("temporal", "parameter", "broker"):
        rng = np.random.default_rng(seed)
        rates = {
            f"{e:.2f}R": sum(_simulate(gate, e, rng, years, per_year) for _ in range(sims)) / sims
            for e in EFFECTS
        }
        label, why = classify(rates["0.00R"], rates["0.10R"])
        out.append(GateRates(gate, rates, label, why))
    return out
