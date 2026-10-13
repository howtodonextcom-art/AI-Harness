"""Candle geometry: body, wicks, ATR-normalised sizes. Row-local, so causal by construction."""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike

from xau_edge.features.indicators import Floats, as_hlc, as_series


class CandleGeometry(NamedTuple):
    """Per-bar candle measurements (price units unless named ``*_to_*``)."""

    body_size: Floats
    upper_wick: Floats
    lower_wick: Floats
    body_to_range: Floats
    body_to_atr: Floats
    upper_wick_to_atr: Floats
    lower_wick_to_atr: Floats
    range_to_atr: Floats


def _ratio(numerator: Floats, denominator: Floats) -> Floats:
    """``numerator / denominator``; ``NaN`` where the denominator is not a positive number."""
    out = np.full(numerator.shape, np.nan)
    ok = np.isfinite(denominator) & (denominator > 0)
    out[ok] = numerator[ok] / denominator[ok]
    return out


def candle_geometry(
    open_: ArrayLike, high: ArrayLike, low: ArrayLike, close: ArrayLike, atr: ArrayLike
) -> CandleGeometry:
    """Measure each candle.

    ``body_size`` is ``|close - open|``; wicks are measured from the body edge to the extreme.
    Ratios are ``NaN`` when the range is zero or the ATR is unavailable (``NaN``) or zero. ``atr``
    may contain ``NaN`` for the warm-up bars.
    """
    o = as_series(open_, "open")
    h, lo, c = as_hlc(high, low, close)
    a = np.asarray(atr, dtype=np.float64)
    if a.ndim != 1:
        msg = f"atr must be 1-D, got shape {a.shape}"
        raise ValueError(msg)
    if not (o.shape == h.shape == a.shape):
        msg = f"open, high, low, close and atr must have the same length, got {o.size}, {a.size}"
        raise ValueError(msg)
    top = np.maximum(o, c)
    bottom = np.minimum(o, c)
    body = np.abs(c - o)
    upper = h - top
    lower = bottom - lo
    rng = h - lo
    if (upper < 0).any() or (lower < 0).any():
        msg = "open and close must lie within [low, high]"
        raise ValueError(msg)
    return CandleGeometry(
        body_size=body,
        upper_wick=upper,
        lower_wick=lower,
        body_to_range=_ratio(body, rng),
        body_to_atr=_ratio(body, a),
        upper_wick_to_atr=_ratio(upper, a),
        lower_wick_to_atr=_ratio(lower, a),
        range_to_atr=_ratio(rng, a),
    )
