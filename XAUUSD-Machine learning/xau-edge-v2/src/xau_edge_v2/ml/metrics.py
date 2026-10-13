"""Forecast metrics (no trading PnL is ever used to select a model).

* ``mse``: mean squared error of the log range (the primary metric);
* ``qlike``: QLIKE on the range LEVEL, ``r/f - ln(r/f) - 1`` with ``r = exp(y)``, ``f = exp(pred)``;
* ``coverage``: share of rows whose label falls inside the interval;
* ``r2_vs``: skill against a reference MSE, ``1 - MSE / MSE_ref``;
* ``block_ci``: monthly block bootstrap of the paired squared-error difference
  ``MSE(base) - MSE(model)`` (positive: the model is better), seed fixed.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

Floats = NDArray[np.float64]
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 7


def mse(pred: Floats, y: Floats, mask: NDArray[np.bool_]) -> float:
    return float(np.mean((pred[mask] - y[mask]) ** 2))


def qlike(pred: Floats, y: Floats, mask: NDArray[np.bool_]) -> float:
    ratio = np.exp(y[mask] - pred[mask])
    return float(np.mean(ratio - np.log(ratio) - 1.0))


def coverage(lower: Floats, upper: Floats, y: Floats, mask: NDArray[np.bool_]) -> float:
    inside = (y[mask] >= lower[mask]) & (y[mask] <= upper[mask])
    return float(np.mean(inside))


def skill(mse_model: float, mse_reference: float) -> float:
    """Relative MSE improvement over the reference (0.10 = 10% lower MSE)."""
    return 1.0 - mse_model / mse_reference


def month_keys(open_s: NDArray[np.int64]) -> NDArray[np.int64]:
    months = open_s.astype("datetime64[s]").astype("datetime64[M]")
    return months.astype(np.int64)


def block_ci(
    pred_model: Floats,
    pred_base: Floats,
    y: Floats,
    mask: NDArray[np.bool_],
    months: NDArray[np.int64],
    levels: tuple[float, ...] = (0.95,),
    one_sided: tuple[float, ...] = (0.975,),
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float | list[float]]:
    """Mean paired difference with bootstrap bounds.

    ``levels`` are TWO-sided intervals (``ci95`` = the 2.5th and 97.5th percentiles). ``one_sided``
    are lower bounds for the claim "the model improves on the baseline" (``lower97.5_one_sided`` =
    the 2.5th percentile): with a family alpha of 0.05 and K = 2 comparisons, the Bonferroni level
    per comparison is alpha/K = 0.025, i.e. a 97.5% ONE-sided lower bound (ADR-V2-007).
    """
    idx = np.flatnonzero(mask)
    diff = (pred_base[idx] - y[idx]) ** 2 - (pred_model[idx] - y[idx]) ** 2
    keys = months[idx]
    unique = np.unique(keys)
    groups = [diff[keys == u] for u in unique]
    rng = np.random.default_rng(seed)
    sums = np.array([g.sum() for g in groups])
    counts = np.array([g.size for g in groups], dtype=np.float64)
    means = np.empty(draws)
    for d in range(draws):
        pick = rng.integers(0, len(groups), size=len(groups))
        means[d] = sums[pick].sum() / counts[pick].sum()
    out: dict[str, float | list[float]] = {"mean": float(diff.mean()), "months": float(len(unique))}
    for level in levels:
        tail = (1 - level) / 2 * 100
        lo, hi = np.percentile(means, [tail, 100 - tail])
        out[f"ci{level * 100:g}"] = [float(lo), float(hi)]
    for level in one_sided:
        out[f"lower{level * 100:g}_one_sided"] = float(np.percentile(means, (1 - level) * 100))
    return out
