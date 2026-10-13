"""Sample size for the one-sided mean test of R-multiples (analytic, then verified by simulation).

    n = DEFF * ((z_alpha + z_beta) * sd / delta) ** 2

for H0: E <= 0 against E = delta, one-sided alpha, power 1 - beta, clustering design effect DEFF.
The Gate A report used (z_alpha * sd / delta) ** 2 with no power term: that is the sample size at
which the test has about 50% power, not 80%.

    uv run python scripts/research/power.py [--mc]
"""

from __future__ import annotations

import math
import sys
from statistics import NormalDist

import numpy as np

SD = 1.5
DEFF = 1.5
ALPHA = 0.025
POWER = 0.8


def n_required(
    delta: float, *, sd: float = SD, deff: float = DEFF, alpha: float = ALPHA, power: float = POWER
) -> int:
    z = NormalDist().inv_cdf
    return math.ceil(deff * ((z(1 - alpha) + z(power)) * sd / delta) ** 2)


def n_gate_a_report(delta: float, *, sd: float = SD, alpha: float = ALPHA) -> int:
    """The superseded figure (no power term, no design effect)."""
    return math.ceil((NormalDist().inv_cdf(1 - alpha) * sd / delta) ** 2)


def simulated_power(
    n: int, delta: float, *, clustered: bool, trials: int = 3000, seed: int = 7
) -> float:
    """Share of simulated studies whose one-sided 97.5% lower bound is above 0.

    ``clustered=False``: independent trades, R = +2 with probability p else -1 (mean ``delta``).
    ``clustered=True``: trades in clusters of 3 (a month's regime) with intra-cluster correlation
    0.25, which is DEFF = 1 + (3 - 1) * 0.25 = 1.5; the bound uses the cluster means.
    """
    rng = np.random.default_rng(seed)
    z = NormalDist().inv_cdf(1 - ALPHA)
    hits = 0
    for _ in range(trials):
        if clustered:
            k = n // 3
            u = rng.normal(size=(k, 1))
            e = rng.normal(size=(k, 3))
            r = delta + SD * (math.sqrt(0.25) * u + math.sqrt(0.75) * e)
            means = r.mean(axis=1)
            lower = means.mean() - z * means.std(ddof=1) / math.sqrt(k)
        else:
            p = (delta + 1.0) / 3.0
            r = np.where(rng.random(n) < p, 2.0, -1.0)
            lower = r.mean() - z * r.std(ddof=1) / math.sqrt(n)
        hits += lower > 0
    return hits / trials


def main() -> None:
    print(f"sd={SD} DEFF={DEFF} alpha={ALPHA} power={POWER}")
    for delta in (0.30, 0.20, 0.15, 0.10):
        line = f"delta {delta:.2f}R: n_required={n_required(delta)}  (superseded gate-A figure {n_gate_a_report(delta)})"
        if "--mc" in sys.argv:
            ind = n_required(delta, deff=1.0)
            line += f"  MC power: independent n={ind}: {simulated_power(ind, delta, clustered=False):.2f}"
            line += f", clustered n={n_required(delta)}: {simulated_power(n_required(delta), delta, clustered=True):.2f}"
        print(line)


if __name__ == "__main__":
    main()
