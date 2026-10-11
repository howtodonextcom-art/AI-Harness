"""Statistics and the Stage 1 gate exactly as frozen in V3 COMMON_PROTOCOL.md (2026-10-11).

Bootstrap: circular blocks of 5 consecutive trading days, 10,000 resamples, seed 20261011, one-sided
H0 mean net R (base) <= 0, p = share of resampled means <= 0. Placebo: the same entries with a
random direction, 1,000 draws, seed 20261011. Gate: n >= minimum, p < alpha, mean base >= +0.10R,
mean pessimistic > 0, and no artefact (positive in >= 5 of 8 Dev years, still positive without the
best 1% of trades, placebo percentile >= 95).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

SEED = 20261011
BLOCK_DAYS = 5
RESAMPLES = 10_000
PLACEBO_DRAWS = 1_000
FLOOR_R = 0.10
YEARS_POSITIVE_MIN = 5
PLACEBO_PCT_MIN = 95.0


def block_bootstrap_means(
    values: NDArray[np.float64],
    days: NDArray[np.int64],
    *,
    resamples: int = RESAMPLES,
    seed: int = SEED,
    chunk: int = 500,
    calendar: NDArray[np.int64] | None = None,
) -> NDArray[np.float64]:
    """Means of resampled event sets built from circular blocks of consecutive trading days.

    ``calendar`` (sorted day keys) is the universe of trading days; days without events weigh 0, so
    a block is 5 calendar trading days, not 5 days that happen to have events.
    """
    uniq = np.unique(days) if calendar is None else np.asarray(calendar, dtype=np.int64)
    inverse = np.searchsorted(uniq, days)
    if (inverse >= uniq.size).any() or not np.array_equal(uniq[inverse], days):
        raise ValueError("an event day is missing from the trading calendar")
    n_days = uniq.size
    sums = np.bincount(inverse, weights=values, minlength=n_days)
    counts = np.bincount(inverse, minlength=n_days).astype(np.float64)
    n_blocks = math.ceil(n_days / BLOCK_DAYS)
    offsets = np.arange(BLOCK_DAYS)
    rng = np.random.default_rng(seed)
    out = np.empty(resamples)
    for start in range(0, resamples, chunk):
        size = min(chunk, resamples - start)
        starts = rng.integers(0, n_days, size=(size, n_blocks))
        idx = ((starts[:, :, None] + offsets) % n_days).reshape(size, -1)[:, :n_days]
        c = counts[idx].sum(axis=1)
        if (c == 0).any():
            raise ValueError("a resample drew only days without events; the sample is too sparse")
        out[start : start + size] = sums[idx].sum(axis=1) / c
    return out


def weekday_calendar(first: int, last: int) -> NDArray[np.int64]:
    """Monday..Friday day keys (days since the epoch, day 0 a Thursday) in [first, last]."""
    k = np.arange(first, last + 1, dtype=np.int64)
    return k[(k + 3) % 7 < 5]


def max_drawdown(r: NDArray[np.float64]) -> float:
    eq = np.cumsum(r)
    return float(np.max(np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:] - eq, initial=0.0))


def describe(r: NDArray[np.float64]) -> dict[str, Any]:
    wins, losses = r[r > 0], r[r <= 0]
    pf = float(wins.sum() / -losses.sum()) if losses.sum() < 0 else None
    return {
        "n": int(r.size),
        "mean_r": float(r.mean()),
        "median_r": float(np.median(r)),
        "win_rate": float((r > 0).mean()),
        "avg_win_r": float(wins.mean()) if wins.size else None,
        "avg_loss_r": float(losses.mean()) if losses.size else None,
        "profit_factor": pf,
        "max_drawdown_r": max_drawdown(r),
        "sum_r": float(r.sum()),
    }


def placebo_percentile(
    long_r: NDArray[np.float64],
    short_r: NDArray[np.float64],
    real_mean: float,
    *,
    draws: int = PLACEBO_DRAWS,
    seed: int = SEED,
) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    side = rng.integers(0, 2, size=(draws, long_r.size)).astype(bool)
    means = np.where(side, long_r, short_r).mean(axis=1)
    return {
        "draws": draws,
        "median": float(np.median(means)),
        "p95": float(np.percentile(means, 95)),
        "percentile_of_real": float((means < real_mean).mean() * 100),
    }


def stage1_gate(
    *,
    n: int,
    n_min: int,
    p: float,
    alpha: float,
    mean_base: float,
    mean_pess: float,
    years_positive: int,
    mean_without_top1pct: float,
    placebo_pct: float,
) -> dict[str, Any]:
    checks = {
        "n_at_least_minimum": n >= n_min,
        "p_below_alpha": p < alpha,
        "mean_base_at_least_floor": mean_base >= FLOOR_R,
        "mean_pessimistic_positive": mean_pess > 0,
        "artefact_years_positive": years_positive >= YEARS_POSITIVE_MIN,
        "artefact_without_top1pct_positive": mean_without_top1pct > 0,
        "artefact_placebo_percentile": placebo_pct >= PLACEBO_PCT_MIN,
    }
    return {"checks": checks, "verdict": "PASS" if all(checks.values()) else "FAIL"}


def mean_without_top(r: NDArray[np.float64], share: float = 0.01) -> float:
    k = max(1, math.ceil(r.size * share))
    return float(np.sort(r)[:-k].mean())
