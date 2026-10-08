"""Aggregate outcomes of a set of analogues (or of all history, the base rate).

Probabilities carry Wilson intervals; the forward-move distribution is reported with percentiles,
not only a mean, and expected R is given for both sides (gross, before costs).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from xau_edge.outcomes.engine import OutcomeTable

PERCENTILES = (5, 25, 50, 75, 95)
_Z95 = 1.959963984540054


def wilson_interval(k: int, n: int, z: float = _Z95) -> tuple[float, float]:
    """Wilson score interval for a proportion ``k / n``."""
    if n < 1:
        msg = f"n must be >= 1, got {n}"
        raise ValueError(msg)
    if not 0 <= k <= n:
        msg = f"k must be within 0..n, got k={k}, n={n}"
        raise ValueError(msg)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True)
class OutcomeSummary:
    """Statistics of the outcomes of ``n`` anchors at one horizon."""

    n: int
    p_up: float
    p_down: float
    p_neutral: float
    p_up_ci: tuple[float, float]
    p_down_ci: tuple[float, float]
    mean_forward_atr: float
    median_forward_atr: float
    mean_return: float
    percentiles: dict[int, float]
    mean_max_up_atr: float
    mean_max_down_atr: float
    expected_r_long: float
    expected_r_short: float


def summarise(
    table: OutcomeTable, horizon_col: int, rows: NDArray[np.intp] | None = None
) -> OutcomeSummary | None:
    """Summarise complete outcomes at ``horizon_col`` for ``rows`` (all rows when ``None``)."""
    idx = np.arange(table.complete.shape[0]) if rows is None else np.asarray(rows, dtype=np.intp)
    keep = idx[table.complete[idx, horizon_col]]
    n = int(keep.size)
    if n == 0:
        return None
    direction = table.direction[keep, horizon_col]
    fwd = table.forward_atr[keep, horizon_col]
    up = int((direction == 1).sum())
    down = int((direction == -1).sum())
    return OutcomeSummary(
        n=n,
        p_up=up / n,
        p_down=down / n,
        p_neutral=(n - up - down) / n,
        p_up_ci=wilson_interval(up, n),
        p_down_ci=wilson_interval(down, n),
        mean_forward_atr=float(fwd.mean()),
        median_forward_atr=float(np.median(fwd)),
        mean_return=float(table.forward_return[keep, horizon_col].mean()),
        percentiles={p: float(np.percentile(fwd, p)) for p in PERCENTILES},
        mean_max_up_atr=float(table.max_up_atr[keep, horizon_col].mean()),
        mean_max_down_atr=float(table.max_down_atr[keep, horizon_col].mean()),
        expected_r_long=float(table.long_r[keep, horizon_col].mean()),
        expected_r_short=float(table.short_r[keep, horizon_col].mean()),
    )
