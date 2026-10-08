"""Probability scoring (Brier, log loss, reliability) and one-vs-rest calibration.

A model that says 0.70 must be right about 70% of the time; these functions measure that and
repair it using data that was NOT used to fit the model (the caller keeps the split chronological).
No "confidence percentage" is ever shown without having passed through this module's scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

Floats = NDArray[np.float64]
Method = Literal["sigmoid", "isotonic"]
N_CLASSES = 3  # 0 = DOWN, 1 = NEUTRAL, 2 = UP
_EPS = 1e-15
_FLOOR = 1e-6


def _check(p: Floats, y: NDArray[np.int_]) -> None:
    if p.ndim != 2 or p.shape[1] != N_CLASSES:
        msg = f"probabilities must have shape (n, {N_CLASSES}), got {p.shape}"
        raise ValueError(msg)
    if p.shape[0] != y.shape[0]:
        msg = f"probabilities and labels need the same rows, got {p.shape[0]} and {y.shape[0]}"
        raise ValueError(msg)
    if not np.isfinite(p).all():
        msg = "probabilities must be finite"
        raise ValueError(msg)


def multiclass_brier(p: Floats, y: NDArray[np.int_]) -> float:
    """Mean over rows of the squared distance to the one-hot label (0 best, 2 worst)."""
    _check(p, y)
    onehot = np.eye(N_CLASSES)[y]
    return float(((p - onehot) ** 2).sum(axis=1).mean())


def log_loss(p: Floats, y: NDArray[np.int_]) -> float:
    """Mean negative log probability of the true class (probabilities clipped at 1e-15)."""
    _check(p, y)
    chosen = np.clip(p[np.arange(y.shape[0]), y], _EPS, 1.0)
    return float(-np.log(chosen).mean())


@dataclass(frozen=True)
class ReliabilityBin:
    """One bin of a reliability curve."""

    mean_predicted: float
    observed_rate: float
    count: int


def reliability_curve(p: Floats, hit: Floats, bins: int = 10) -> list[ReliabilityBin]:
    """Observed frequency versus mean predicted probability in equal-width bins (non-empty only)."""
    idx = np.minimum((np.asarray(p) * bins).astype(int), bins - 1)
    out: list[ReliabilityBin] = []
    for b in range(bins):
        mask = idx == b
        if mask.any():
            out.append(
                ReliabilityBin(
                    float(p[mask].mean()), float(np.asarray(hit)[mask].mean()), int(mask.sum())
                )
            )
    return out


def expected_calibration_error(p: Floats, hit: Floats, bins: int = 10) -> float:
    """Count-weighted mean gap between predicted probability and observed frequency."""
    curve = reliability_curve(p, hit, bins)
    total = sum(b.count for b in curve)
    return float(sum(b.count * abs(b.observed_rate - b.mean_predicted) for b in curve) / total)


def base_rate_probabilities(y_train: NDArray[np.int_], rows: int) -> Floats:
    """The no-skill forecast: training class frequencies repeated for ``rows`` rows."""
    counts = np.bincount(y_train, minlength=N_CLASSES).astype(float)
    return np.tile(counts / counts.sum(), (rows, 1))


class OvRCalibrator:
    """One calibrator per class (Platt/sigmoid or isotonic), outputs renormalised to sum to 1."""

    def __init__(self, method: str) -> None:
        if method not in ("sigmoid", "isotonic"):
            msg = f"unknown calibration method {method!r}; use 'sigmoid' or 'isotonic'"
            raise ValueError(msg)
        self.method: Method = method  # type: ignore[assignment]
        self._fitted: list[object] | None = None

    def fit(self, p: Floats, y: NDArray[np.int_]) -> OvRCalibrator:
        """Fit on held-out probabilities ``p`` and labels ``y``."""
        _check(p, y)
        models: list[object] = []
        for k in range(N_CLASSES):
            target = (y == k).astype(int)
            if target.min() == target.max():  # class absent (or always present): constant
                models.append((target.sum() + 0.5) / (target.size + 1.0))
                continue
            score = p[:, k]
            if self.method == "sigmoid":
                clipped = np.clip(score, _EPS, 1 - _EPS)
                x = np.log(clipped / (1 - clipped)).reshape(-1, 1)
                models.append(LogisticRegression(C=1e6, max_iter=1000).fit(x, target))
            else:
                iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
                models.append(iso.fit(score, target))
        self._fitted = models
        return self

    def transform(self, p: Floats) -> Floats:
        """Calibrated probabilities with a small floor, rows summing to one."""
        if self._fitted is None:
            msg = "call fit before transform"
            raise RuntimeError(msg)
        if p.ndim != 2 or p.shape[1] != N_CLASSES:
            msg = f"probabilities must have shape (n, {N_CLASSES}), got {p.shape}"
            raise ValueError(msg)
        cols: list[Floats] = []
        for k, model in enumerate(self._fitted):
            score = p[:, k]
            if isinstance(model, float):
                cols.append(np.full(score.shape, model))
            elif isinstance(model, LogisticRegression):
                clipped = np.clip(score, _EPS, 1 - _EPS)
                x = np.log(clipped / (1 - clipped)).reshape(-1, 1)
                cols.append(model.predict_proba(x)[:, 1])
            else:
                cols.append(np.asarray(model.predict(score), dtype=float))  # type: ignore[attr-defined,arg-type]
        out = np.maximum(np.column_stack(cols), _FLOOR)
        return out / out.sum(axis=1, keepdims=True)
