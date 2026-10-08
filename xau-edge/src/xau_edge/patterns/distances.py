"""Similarity measures behind one interface (brief section 14).

Every method has the signature ``f(query, candidates) -> distances`` where ``query`` has shape
``(window, features)`` and ``candidates`` ``(n, window, features)``; the result has shape ``(n,)``,
is non-negative, and is ``0`` for an identical window. Smaller means more similar. Inputs must be
finite (callers mask incomplete windows first).

Methods: ``euclidean``, ``cosine``, ``pearson`` (1 - correlation), ``dtw`` (multivariate dynamic
time warping, optional Sakoe-Chiba band) and ``znorm_path`` (per-channel z-normalised Euclidean,
the distance the Matrix Profile family is built on). ``mass_distance_profile`` computes the same
z-normalised distance for a 1-D query against every window of a series with FFTs, and
``matrix_profile`` is a reference self-join for small series.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

Floats = NDArray[np.float64]
DistanceFn = Callable[[Floats, Floats], Floats]


def _check(query: Floats, candidates: Floats) -> None:
    if query.ndim != 2 or candidates.ndim != 3 or candidates.shape[1:] != query.shape:
        msg = (
            f"shape mismatch: query {query.shape} needs candidates (n, {query.shape[0]}, "
            f"{query.shape[-1]}), got {candidates.shape}"
        )
        raise ValueError(msg)
    if not (np.isfinite(query).all() and np.isfinite(candidates).all()):
        msg = "inputs must be finite"
        raise ValueError(msg)


def euclidean_distance(query: Floats, candidates: Floats) -> Floats:
    """Euclidean distance between the flattened windows."""
    _check(query, candidates)
    diff = candidates - query
    return np.sqrt((diff * diff).sum(axis=(1, 2)))


def cosine_distance(query: Floats, candidates: Floats) -> Floats:
    """``1 - cosine similarity`` of the flattened windows; 1 when either vector is zero."""
    _check(query, candidates)
    q = query.ravel()
    c = candidates.reshape(candidates.shape[0], -1)
    denom = np.linalg.norm(c, axis=1) * np.linalg.norm(q)
    dot = c @ q
    cos = np.divide(dot, denom, out=np.zeros_like(dot), where=denom > 0)
    return np.clip(1.0 - cos, 0.0, 2.0)


def pearson_distance(query: Floats, candidates: Floats) -> Floats:
    """``1 - Pearson correlation`` of the flattened windows; 1 when either is constant."""
    _check(query, candidates)
    q = query.ravel() - query.mean()
    c = candidates.reshape(candidates.shape[0], -1)
    c = c - c.mean(axis=1, keepdims=True)
    denom = np.linalg.norm(c, axis=1) * np.linalg.norm(q)
    scale = np.linalg.norm(c, axis=1).max(initial=0.0) * np.linalg.norm(q)
    corr = np.divide(
        c @ q, denom, out=np.zeros(c.shape[0]), where=denom > 1e-12 * max(scale, 1e-300)
    )
    return np.clip(1.0 - corr, 0.0, 2.0)


def dtw_distance(query: Floats, candidates: Floats, *, radius: int | None = None) -> Floats:
    """Multivariate DTW (squared Euclidean cost per time pair, square root of the total).

    ``radius`` is the Sakoe-Chiba band half-width in bars (``None`` = unconstrained, ``0`` = the
    diagonal, which equals the Euclidean distance).
    """
    _check(query, candidates)
    if radius is not None and radius < 0:
        msg = f"radius must be >= 0, got {radius}"
        raise ValueError(msg)
    n, w, _ = candidates.shape
    cost = ((query[None, :, None, :] - candidates[:, None, :, :]) ** 2).sum(axis=3)  # (n, i, j)
    acc = np.full((n, w + 1, w + 1), np.inf)
    acc[:, 0, 0] = 0.0
    for i in range(1, w + 1):
        lo = 1 if radius is None else max(1, i - radius)
        hi = w if radius is None else min(w, i + radius)
        for j in range(lo, hi + 1):
            best = np.minimum(np.minimum(acc[:, i - 1, j], acc[:, i, j - 1]), acc[:, i - 1, j - 1])
            acc[:, i, j] = cost[:, i - 1, j - 1] + best
    return np.sqrt(acc[:, w, w])


def _znorm(windows: Floats) -> Floats:
    mean = windows.mean(axis=-2, keepdims=True)
    std = windows.std(axis=-2, keepdims=True)
    return np.divide(windows - mean, std, out=np.zeros_like(windows), where=std > 1e-12)


def znorm_path_distance(query: Floats, candidates: Floats) -> Floats:
    """Euclidean distance after z-normalising every channel of every window over time."""
    _check(query, candidates)
    zq = _znorm(query)
    zc = _znorm(candidates)
    diff = zc - zq
    return np.sqrt((diff * diff).sum(axis=(1, 2)))


def _rolling_mean_std(series: Floats, m: int) -> tuple[Floats, Floats]:
    view = sliding_window_view(series, m)
    return view.mean(axis=1), view.std(axis=1)


def mass_distance_profile(query: Floats, series: Floats) -> Floats:
    """Z-normalised Euclidean distance of ``query`` to every window of ``series`` (MASS, via FFT).

    A constant window is z-normalised to zeros, so its distance to a non-constant query is
    ``sqrt(len(query))`` and two constant windows are at distance 0.
    """
    m = query.size
    n = series.size
    if m < 2 or n < m:
        msg = f"need 2 <= len(query) <= len(series), got {m} and {n}"
        raise ValueError(msg)
    offset = float(series.mean())  # centring keeps the FFT dot products accurate at any price level
    series = series - offset
    query = query - offset
    size = 1 << int(np.ceil(np.log2(n + m)))
    dot = np.fft.irfft(np.fft.rfft(series, size) * np.fft.rfft(query[::-1], size), size)[m - 1 : n]
    mu_t, sd_t = _rolling_mean_std(series, m)
    mu_q, sd_q = float(query.mean()), float(query.std())
    out = np.empty(n - m + 1)
    if sd_q <= 1e-12:
        out[:] = np.where(sd_t <= 1e-12, 0.0, np.sqrt(m))
        return out
    live = sd_t > 1e-12
    corr = (dot[live] - m * mu_q * mu_t[live]) / (m * sd_q * sd_t[live])
    out[live] = np.sqrt(np.maximum(2.0 * m * (1.0 - corr), 0.0))
    out[~live] = np.sqrt(m)
    return out


def matrix_profile(
    series: Floats, m: int, exclusion: int | None = None
) -> tuple[Floats, NDArray[np.intp]]:
    """Reference matrix profile (self-join): nearest non-trivial neighbour of every window.

    ``exclusion`` is the half-width of the zone around each window that is ignored (default ``m``)
    so a window is never matched with its own overlap. Cost is O(n^2 log n): for small series,
    tests and motif exploration, not for production-size histories.
    """
    zone = m if exclusion is None else exclusion
    count = series.size - m + 1
    profile = np.full(count, np.inf)
    index = np.full(count, -1, dtype=np.intp)
    for i in range(count):
        d = mass_distance_profile(series[i : i + m], series)
        lo, hi = max(0, i - zone + 1), min(count, i + zone)
        d[lo:hi] = np.inf
        j = int(np.argmin(d))
        if np.isfinite(d[j]):
            profile[i], index[i] = d[j], j
    return profile, index


METHODS: Final[dict[str, DistanceFn]] = {
    "pearson": pearson_distance,
    "euclidean": euclidean_distance,
    "cosine": cosine_distance,
    "dtw": dtw_distance,
    "znorm_path": znorm_path_distance,
}
