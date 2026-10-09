"""Dependence-aware statistics (roadmap section 14): effective N and block-bootstrap sensitivity.

Trades that overlap in time or cluster inside one day are not independent, so raw N overstates the
evidence. Everything here is deterministic given the seed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

DEFAULT_BLOCK_DAYS = (1, 2, 5)
DEPENDENCE_SENSITIVE = "DEPENDENCE_SENSITIVE"
DEPENDENCE_STABLE = "DEPENDENCE_STABLE"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DependenceReport:
    """Counts that expose how much independent information a sample really holds."""

    raw_n: int
    unique_days: int
    unique_weeks: int
    overlap_ratio: float
    icc: float
    lag1_autocorr: float
    effective_n: float


def _floats(values: NDArray[np.float64] | list[float]) -> NDArray[np.float64]:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or not np.all(np.isfinite(arr)):
        msg = "values must be a finite 1-D sequence"
        raise ValueError(msg)
    return arr


def overlap_ratio(entry: NDArray[np.int64], exit_: NDArray[np.int64]) -> float:
    """Share of trades whose holding window overlaps another trade's window (times as integers)."""
    if len(entry) != len(exit_):
        msg = "entry and exit must have the same length"
        raise ValueError(msg)
    n = len(entry)
    if n < 2:
        return 0.0
    order = np.argsort(entry, kind="stable")
    start, end = entry[order], exit_[order]
    if np.any(end < start):
        msg = "a trade exits before it enters"
        raise ValueError(msg)
    overlapped = np.zeros(n, dtype=bool)
    furthest = end[0]
    furthest_idx = 0
    for i in range(1, n):
        if start[i] < furthest:
            overlapped[i] = True
            overlapped[furthest_idx] = True
        if end[i] > furthest:
            furthest, furthest_idx = end[i], i
    return float(overlapped.mean())


def _icc(values: NDArray[np.float64], groups: NDArray[np.int64]) -> float:
    """One-way ANOVA intraclass correlation, clipped to [0, 1]; 0 when it cannot be estimated."""
    labels, inverse, counts = np.unique(groups, return_inverse=True, return_counts=True)
    k, n = len(labels), len(values)
    if k < 2 or n <= k:
        return 0.0
    grand = values.mean()
    sums = np.bincount(inverse, weights=values)
    means = sums / counts
    ssb = float(np.sum(counts * (means - grand) ** 2))
    ssw = float(np.sum((values - means[inverse]) ** 2))
    msb, msw = ssb / (k - 1), ssw / (n - k)
    m0 = (n - float(np.sum(counts**2)) / n) / (k - 1)
    denom = msb + (m0 - 1) * msw
    if denom <= 0 or m0 <= 0:
        return 0.0
    return float(min(1.0, max(0.0, (msb - msw) / denom)))


def _lag1(values: NDArray[np.float64]) -> float:
    if len(values) < 3:
        return 0.0
    centred = values - values.mean()
    denom = float(np.dot(centred, centred))
    if denom == 0:
        return 0.0
    return float(np.dot(centred[:-1], centred[1:]) / denom)


def effective_n(values: NDArray[np.float64], day_ids: NDArray[np.int64]) -> float:
    """Raw N over the larger of the cluster and serial design effects (never above raw N)."""
    values = _floats(values)
    if len(values) != len(day_ids):
        msg = "values and day_ids must have the same length"
        raise ValueError(msg)
    n = len(values)
    if n == 0:
        return 0.0
    m_bar = n / len(np.unique(day_ids))
    deff_cluster = 1.0 + (m_bar - 1.0) * _icc(values, day_ids)
    rho = max(0.0, _lag1(values))
    deff_serial = (1.0 + rho) / (1.0 - rho) if rho < 0.99 else float(n)
    return n / max(1.0, deff_cluster, deff_serial)


def dependence_report(
    values: NDArray[np.float64],
    day_ids: NDArray[np.int64],
    entry: NDArray[np.int64] | None = None,
    exit_: NDArray[np.int64] | None = None,
) -> DependenceReport:
    """All dependence indicators for one trade/event sample (day ids are integer day numbers)."""
    values = _floats(values)
    weeks = np.unique(np.asarray(day_ids) // 7)
    overlap = overlap_ratio(entry, exit_) if entry is not None and exit_ is not None else 0.0
    return DependenceReport(
        raw_n=len(values),
        unique_days=len(np.unique(day_ids)),
        unique_weeks=len(weeks),
        overlap_ratio=overlap,
        icc=_icc(values, np.asarray(day_ids)) if len(values) else 0.0,
        lag1_autocorr=_lag1(values),
        effective_n=effective_n(values, np.asarray(day_ids)),
    )


def block_bootstrap_ci(
    values: NDArray[np.float64],
    day_ids: NDArray[np.int64],
    block_days: int,
    *,
    seed: int,
    draws: int = 2000,
    level: float = 0.95,
) -> tuple[float, float]:
    """Two-sided CI of the mean, resampling blocks of ``block_days`` consecutive calendar days."""
    values = _floats(values)
    if block_days < 1 or draws < 100 or not 0 < level < 1:
        msg = "invalid bootstrap settings"
        raise ValueError(msg)
    if len(values) == 0 or len(values) != len(day_ids):
        msg = "values and day_ids must be non-empty and the same length"
        raise ValueError(msg)
    days = np.unique(day_ids)
    first = int(days.min())
    block_of_day = (np.asarray(day_ids) - first) // block_days
    blocks = np.unique(block_of_day)
    sums = np.array([values[block_of_day == b].sum() for b in blocks])
    counts = np.array([float((block_of_day == b).sum()) for b in blocks])
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(blocks), size=(draws, len(blocks)))
    means = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    tail = (1 - level) / 2
    lo, hi = np.quantile(means, [tail, 1 - tail])
    return float(lo), float(hi)


def stationary_indices(rng: np.random.Generator, n: int, p: float) -> NDArray[np.int64]:
    """One Politis-Romano resample: restart at a random point with probability ``p``."""
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    restart = rng.random(n) < p
    fresh = rng.integers(0, n, size=n)
    for i in range(1, n):
        idx[i] = fresh[i] if restart[i] else (idx[i - 1] + 1) % n
    return idx


def stationary_bootstrap_ci(
    values: NDArray[np.float64],
    *,
    mean_block: float,
    seed: int,
    draws: int = 2000,
    level: float = 0.95,
) -> tuple[float, float]:
    """Politis-Romano stationary bootstrap CI of the mean over the time-ordered sequence."""
    values = _floats(values)
    n = len(values)
    if n < 2 or mean_block < 1 or draws < 100:
        msg = "invalid stationary bootstrap settings"
        raise ValueError(msg)
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    means = np.empty(draws)
    for d in range(draws):
        idx = stationary_indices(rng, n, p)
        means[d] = values[idx].mean()
    tail = (1 - level) / 2
    lo, hi = np.quantile(means, [tail, 1 - tail])
    return float(lo), float(hi)


@dataclass(frozen=True)
class SensitivityReport:
    """Does the verdict ("CI lower bound above zero") survive reasonable dependence assumptions?"""

    status: str
    by_block: dict[str, tuple[float, float]]
    verdicts: dict[str, bool]


def dependence_sensitivity(
    values: NDArray[np.float64],
    day_ids: NDArray[np.int64],
    *,
    seed: int,
    block_days: tuple[int, ...] = DEFAULT_BLOCK_DAYS,
    include_stationary: bool = True,
) -> SensitivityReport:
    """Run 1/2/5-day blocks and a stationary bootstrap; disagree on the verdict => SENSITIVE."""
    values = _floats(values)
    if len(values) < 10:
        return SensitivityReport(UNKNOWN, {}, {})
    by_block: dict[str, tuple[float, float]] = {}
    for b in block_days:
        by_block[f"{b}d"] = block_bootstrap_ci(values, day_ids, b, seed=seed)
    if include_stationary:
        n_days = max(1, len(np.unique(day_ids)))
        mean_block = max(1.0, len(values) / n_days * 2)
        by_block["stationary"] = stationary_bootstrap_ci(values, mean_block=mean_block, seed=seed)
    verdicts = {name: lo > 0 for name, (lo, _hi) in by_block.items()}
    status = DEPENDENCE_STABLE if len(set(verdicts.values())) == 1 else DEPENDENCE_SENSITIVE
    return SensitivityReport(status, by_block, verdicts)


def finite_or_none(value: float) -> float | None:
    """JSON-safe number."""
    return value if math.isfinite(value) else None
