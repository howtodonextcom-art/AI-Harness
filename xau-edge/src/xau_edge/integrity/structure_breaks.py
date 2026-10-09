"""Structural-break and era diagnostics (roadmap section 24).

Purpose: find out whether an apparent edge belongs to ONE historical era. Nothing here tunes a
strategy around a detected break; it only labels the evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

ERA_DEPENDENT = "ERA_DEPENDENT"
ERA_STABLE = "ERA_STABLE"
UNKNOWN = "UNKNOWN"
MIN_ERA_TRADES = 30


@dataclass(frozen=True)
class Era:
    """Result inside one era."""

    label: str
    n: int
    mean: float
    ci_low: float
    ci_high: float
    profit_share: float


@dataclass(frozen=True)
class EraReport:
    """Effect by era and the verdict."""

    status: str
    eras: tuple[Era, ...]
    reason: str


def _mean_ci(values: NDArray[np.float64]) -> tuple[float, float, float]:
    n = len(values)
    mean = float(values.mean())
    se = float(values.std(ddof=1) / math.sqrt(n)) if n > 1 else float("inf")
    return mean, mean - 1.959964 * se, mean + 1.959964 * se


def era_report(
    values: NDArray[np.float64], era_of: list[str], *, order: list[str] | None = None
) -> EraReport:
    """Effect per era. ERA_DEPENDENT when it is positive in fewer than half of the eras, when its
    sign flips with a significant negative era, or when one era carries over 60% of the profit.
    """
    if len(values) != len(era_of) or len(values) == 0:
        return EraReport(UNKNOWN, (), "no data or length mismatch")
    labels = order or sorted(set(era_of))
    total = float(values.sum())
    eras: list[Era] = []
    for label in labels:
        mask = np.array([e == label for e in era_of])
        part = values[mask]
        if len(part) < MIN_ERA_TRADES:
            continue
        mean, lo, hi = _mean_ci(part)
        eras.append(
            Era(label, len(part), mean, lo, hi, 0.0 if total == 0 else float(part.sum()) / total)
        )
    if len(eras) < 2:
        return EraReport(UNKNOWN, tuple(eras), "fewer than two eras with enough trades")
    positive = sum(e.mean > 0 for e in eras)
    significant_negative = any(e.ci_high < 0 for e in eras)
    concentrated = total > 0 and any(e.profit_share > 0.60 for e in eras)
    if positive < len(eras) / 2 or significant_negative or concentrated:
        why = (
            "positive in fewer than half of the eras"
            if positive < len(eras) / 2
            else "an era is significantly negative"
            if significant_negative
            else "one era carries over 60% of the profit"
        )
        return EraReport(ERA_DEPENDENT, tuple(eras), why)
    return EraReport(ERA_STABLE, tuple(eras), "positive in most eras with no dominant era")


def best_mean_shift(
    values: NDArray[np.float64], *, min_segment: int = 30
) -> tuple[int, float] | None:
    """Most likely single mean-shift position and its t-like statistic, or None if too short."""
    n = len(values)
    if n < 2 * min_segment:
        return None
    csum = np.cumsum(values)
    total = csum[-1]
    best_k, best_stat = -1, 0.0
    sd = float(values.std(ddof=1)) or 1.0
    for k in range(min_segment, n - min_segment):
        left = csum[k - 1] / k
        right = (total - csum[k - 1]) / (n - k)
        stat = abs(left - right) / (sd * math.sqrt(1 / k + 1 / (n - k)))
        if stat > best_stat:
            best_k, best_stat = k, stat
    return (best_k, best_stat) if best_k >= 0 else None


def cusum_break(
    values: NDArray[np.float64], *, seed: int, draws: int = 500, min_segment: int = 30
) -> dict[str, float | int | None]:
    """Mean-shift scan with a permutation p-value (diagnostic only; no tuning follows from it)."""
    found = best_mean_shift(values, min_segment=min_segment)
    if found is None:
        return {"position": None, "statistic": None, "p_value": None}
    position, stat = found
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(draws):
        shuffled = rng.permutation(values)
        again = best_mean_shift(shuffled, min_segment=min_segment)
        exceed += again is not None and again[1] >= stat
    return {"position": position, "statistic": stat, "p_value": (exceed + 1) / (draws + 1)}
