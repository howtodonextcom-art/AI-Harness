"""Tick-volume features (causal: each value uses only the current and earlier bars)."""

from __future__ import annotations

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike

from xau_edge.features.indicators import Floats, as_series, check_period


def _volume(values: ArrayLike) -> Floats:
    arr = as_series(values, "volume")
    if (arr < 0).any():
        msg = "volume must not be negative"
        raise ValueError(msg)
    return arr


def volume_zscore(volume: ArrayLike, window: int = 20) -> Floats:
    """``(v - mean) / std`` over the last ``window`` bars including the current one.

    Sample standard deviation (ddof=1); ``NaN`` while the window is incomplete and when the window
    is constant. First valid index: ``window - 1``.
    """
    check_period(window, "window", minimum=2)
    v = _volume(volume)
    out = np.full(v.size, np.nan)
    if v.size >= window:
        view = sliding_window_view(v, window)
        mean = view.mean(axis=1)
        std = view.std(axis=1, ddof=1)
        ok = std > 0
        z = np.full(mean.shape, np.nan)
        z[ok] = (v[window - 1 :][ok] - mean[ok]) / std[ok]
        out[window - 1 :] = z
    return out


def volume_change(volume: ArrayLike) -> Floats:
    """``v[i] / v[i-1] - 1``; ``NaN`` at index 0 and where the previous volume is zero."""
    v = _volume(volume)
    out = np.full(v.size, np.nan)
    if v.size > 1:
        prev = v[:-1]
        ok = prev > 0
        change = np.full(prev.shape, np.nan)
        change[ok] = v[1:][ok] / prev[ok] - 1.0
        out[1:] = change
    return out
