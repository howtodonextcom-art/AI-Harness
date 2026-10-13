"""Block bootstrap for dependent observations (resample whole days, not single trades)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from numpy.typing import ArrayLike, NDArray

Statistic = Callable[[NDArray[np.float64]], float]


def block_bootstrap_ci(
    values: ArrayLike,
    blocks: ArrayLike,
    *,
    alpha: float = 0.05,
    n_resamples: int = 2000,
    seed: int = 7,
    statistic: Statistic = np.mean,
) -> tuple[float, float]:
    """Percentile interval of ``statistic`` when whole blocks are resampled with replacement.

    ``blocks`` labels each observation's block (for example its calendar day); observations in one
    block always move together, which keeps within-block dependence in the interval.
    """
    v = np.asarray(values, dtype=np.float64)
    b = np.asarray(blocks)
    if v.size == 0:
        msg = "cannot bootstrap an empty sample"
        raise ValueError(msg)
    if v.shape != b.shape or v.ndim != 1:
        msg = f"values and blocks must be 1-D with the same length, got {v.shape} and {b.shape}"
        raise ValueError(msg)
    if not np.isfinite(v).all():
        msg = "values must be finite"
        raise ValueError(msg)
    if not 0 < alpha < 1:
        msg = f"alpha must be within (0, 1), got {alpha}"
        raise ValueError(msg)
    _, inverse = np.unique(b, return_inverse=True)
    groups = [v[inverse == i] for i in range(int(inverse.max()) + 1)]
    rng = np.random.default_rng(seed)
    n_blocks = len(groups)
    stats = np.empty(n_resamples)
    for r in range(n_resamples):
        picks = rng.integers(0, n_blocks, n_blocks)
        stats[r] = statistic(np.concatenate([groups[i] for i in picks]))
    lo, hi = np.percentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
