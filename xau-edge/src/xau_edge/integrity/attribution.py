"""Edge attribution (roadmap section 12): which part of the apparent expectancy is what.

Inputs are per-event results in R for BOTH sides, so every counterfactual uses the same events and
the same cost model. The decomposition is descriptive: it does not claim causality beyond what the
paired differences show.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from xau_edge.integrity.power2 import cluster_t_stat

_Z95 = 1.959964


@dataclass(frozen=True)
class Counterfactual:
    """One comparison against the original strategy."""

    name: str
    mean_r: float
    incremental_r: float
    ci_low: float
    ci_high: float
    effect_size: float


def _paired(
    name: str, observed: NDArray[np.float64], other: NDArray[np.float64], days: NDArray[np.int64]
) -> Counterfactual:
    diff = observed - other
    n = len(diff)
    mean = float(diff.mean())
    t = cluster_t_stat(diff, days)
    se = abs(mean / t) if t != 0 else float(diff.std(ddof=1) / math.sqrt(n)) if n > 1 else 0.0
    sd = float(diff.std(ddof=1)) if n > 1 else 0.0
    return Counterfactual(
        name=name,
        mean_r=float(other.mean()),
        incremental_r=mean,
        ci_low=mean - _Z95 * se,
        ci_high=mean + _Z95 * se,
        effect_size=0.0 if sd == 0 else mean / sd,
    )


@dataclass(frozen=True)
class Attribution:
    """Counterfactuals A-G and the descriptive decomposition."""

    observed_mean_r: float
    n: int
    counterfactuals: tuple[Counterfactual, ...]
    timing_edge: float | None
    direction_edge: float
    selection_edge: float | None
    exit_edge: float | None
    drift_exposure: float
    note: str


def attribute(
    *,
    long_r: NDArray[np.float64],
    short_r: NDArray[np.float64],
    direction: NDArray[np.float64],
    day_ids: NDArray[np.int64],
    matched_pool_mean_r: float | None = None,
    all_candidate_mean_r: float | None = None,
    alt_exit_r: NDArray[np.float64] | None = None,
) -> Attribution:
    """Attribute the observed expectancy.

    ``long_r`` / ``short_r``: result of taking each event long / short with the real exit rule.
    ``direction``: +1 or -1 chosen by the strategy. ``matched_pool_mean_r``: mean result of
    matched random timestamps (same session, regime, volatility bucket). ``all_candidate_mean_r``:
    mean over every candidate event before the strategy's filter. ``alt_exit_r``: result of the
    same entries and directions with an alternative exit.
    """
    n = len(direction)
    if not (len(long_r) == len(short_r) == n == len(day_ids)) or n < 2:
        msg = "inputs must have the same length >= 2"
        raise ValueError(msg)
    if not np.all(np.isin(direction, (-1.0, 1.0))):
        msg = "direction must be +1 or -1"
        raise ValueError(msg)
    observed = np.where(direction > 0, long_r, short_r)
    random_dir = (long_r + short_r) / 2  # expectation of a fair coin per event
    cfs = [
        _paired("B random direction (expected)", observed, random_dir, day_ids),
        _paired("C always long", observed, long_r, day_ids),
        _paired("D always short", observed, short_r, day_ids),
        _paired(
            "E opposite direction", observed, np.where(direction > 0, short_r, long_r), day_ids
        ),
    ]
    if alt_exit_r is not None:
        if len(alt_exit_r) != n:
            msg = "alt_exit_r must match the sample"
            raise ValueError(msg)
        cfs.append(_paired("G alternative exit", observed, alt_exit_r, day_ids))
    f_mean = None
    if matched_pool_mean_r is not None:
        f_mean = float(random_dir.mean()) - matched_pool_mean_r
    obs_mean = float(observed.mean())
    return Attribution(
        observed_mean_r=obs_mean,
        n=n,
        counterfactuals=tuple(cfs),
        timing_edge=f_mean,
        direction_edge=obs_mean - float(random_dir.mean()),
        selection_edge=(
            None
            if all_candidate_mean_r is None
            else float(random_dir.mean()) - all_candidate_mean_r
        ),
        exit_edge=None if alt_exit_r is None else obs_mean - float(alt_exit_r.mean()),
        drift_exposure=float(long_r.mean() - short_r.mean()) / 2,
        note="descriptive decomposition from paired differences; not a causal claim",
    )
