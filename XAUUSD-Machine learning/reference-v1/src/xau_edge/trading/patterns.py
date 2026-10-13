"""Objective candle and price patterns (trading core section 9).

Every detector is causal and non-repainting: the value at bar ``i`` uses bars ``0..i`` only, so it
never changes when later bars arrive (tested with truncation and future-garbage tests). Results
are int8 arrays: +1 bullish, -1 bearish, 0 none (``inside_bar``, ``outside_bar``,
``range_expansion`` and ``compression`` are 0/1 flags). Only unambiguous definitions are encoded;
subjective chart-pattern names are not.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

Ints = NDArray[np.int8]


def _arrays(
    o: ArrayLike, h: ArrayLike, low: ArrayLike, c: ArrayLike
) -> tuple[NDArray[np.float64], ...]:
    arrays = tuple(np.asarray(x, dtype=np.float64) for x in (o, h, low, c))
    if len({a.shape for a in arrays}) != 1 or arrays[0].ndim != 1:
        msg = "open, high, low and close must be 1-D arrays of the same length"
        raise ValueError(msg)
    return arrays


def strong_body(
    o: ArrayLike, h: ArrayLike, low: ArrayLike, c: ArrayLike, *, min_body_to_range: float = 0.6
) -> Ints:
    """+1 / -1 when the body fills at least ``min_body_to_range`` of the range (up / down)."""
    op, hi, lo, cl = _arrays(o, h, low, c)
    rng = hi - lo
    body = cl - op
    big = (rng > 0) & (np.abs(body) >= min_body_to_range * np.where(rng > 0, rng, 1.0))
    return np.where(big, np.sign(body), 0).astype(np.int8)


def pin_bar(
    o: ArrayLike, h: ArrayLike, low: ArrayLike, c: ArrayLike, *, wick_to_body: float = 2.0
) -> Ints:
    """Rejection candle: a wick of at least ``wick_to_body`` x body and half the range.

    +1 for a long LOWER wick (rejection of lower prices), -1 for a long UPPER wick.
    """
    op, hi, lo, cl = _arrays(o, h, low, c)
    rng = hi - lo
    body = np.abs(cl - op)
    upper = hi - np.maximum(op, cl)
    lower = np.minimum(op, cl) - lo
    half = 0.5 * rng
    bull = (rng > 0) & (lower >= half) & (lower >= wick_to_body * body) & (lower > upper)
    bear = (rng > 0) & (upper >= half) & (upper >= wick_to_body * body) & (upper > lower)
    return np.where(bull, 1, np.where(bear, -1, 0)).astype(np.int8)


def engulfing(o: ArrayLike, h: ArrayLike, low: ArrayLike, c: ArrayLike) -> Ints:
    """+1 when a bullish body fully engulfs the previous bearish body (and -1 for the mirror)."""
    op, _hi, _lo, cl = _arrays(o, h, low, c)
    out = np.zeros(op.size, dtype=np.int8)
    if op.size < 2:
        return out
    po, pc = op[:-1], cl[:-1]
    bull = (pc < po) & (cl[1:] > op[1:]) & (cl[1:] >= po) & (op[1:] <= pc)
    bear = (pc > po) & (cl[1:] < op[1:]) & (cl[1:] <= po) & (op[1:] >= pc)
    out[1:] = np.where(bull, 1, np.where(bear, -1, 0))
    return out


def inside_bar(h: ArrayLike, low: ArrayLike) -> Ints:
    """1 when the bar's range lies within the previous bar's range."""
    hi, lo = np.asarray(h, dtype=np.float64), np.asarray(low, dtype=np.float64)
    out = np.zeros(hi.size, dtype=np.int8)
    if hi.size > 1:
        out[1:] = ((hi[1:] <= hi[:-1]) & (lo[1:] >= lo[:-1])).astype(np.int8)
    return out


def outside_bar(h: ArrayLike, low: ArrayLike) -> Ints:
    """1 when the bar's range exceeds the previous bar's range on both sides."""
    hi, lo = np.asarray(h, dtype=np.float64), np.asarray(low, dtype=np.float64)
    out = np.zeros(hi.size, dtype=np.int8)
    if hi.size > 1:
        out[1:] = ((hi[1:] > hi[:-1]) & (lo[1:] < lo[:-1])).astype(np.int8)
    return out


def range_expansion(h: ArrayLike, low: ArrayLike, atr: ArrayLike, *, k: float = 1.5) -> Ints:
    """1 when the bar's range is at least ``k`` x the ATR (ATR must be known)."""
    rng = np.asarray(h, dtype=np.float64) - np.asarray(low, dtype=np.float64)
    a = np.asarray(atr, dtype=np.float64)
    return (np.isfinite(a) & (a > 0) & (rng >= k * np.where(a > 0, a, 1.0))).astype(np.int8)


def compression(
    h: ArrayLike, low: ArrayLike, atr: ArrayLike, *, bars: int = 3, ratio: float = 0.6
) -> Ints:
    """1 when the mean range of the last ``bars`` bars is at most ``ratio`` x the ATR."""
    rng = np.asarray(h, dtype=np.float64) - np.asarray(low, dtype=np.float64)
    a = np.asarray(atr, dtype=np.float64)
    out = np.zeros(rng.size, dtype=np.int8)
    for i in range(bars - 1, rng.size):
        if (
            np.isfinite(a[i])
            and a[i] > 0
            and float(np.mean(rng[i - bars + 1 : i + 1])) <= ratio * a[i]
        ):
            out[i] = 1
    return out


def breakout(h: ArrayLike, low: ArrayLike, c: ArrayLike, *, lookback: int = 10) -> Ints:
    """+1 when the close is above the highest high of the previous ``lookback`` bars (-1 mirror)."""
    hi, lo, cl = (np.asarray(x, dtype=np.float64) for x in (h, low, c))
    out = np.zeros(cl.size, dtype=np.int8)
    for i in range(lookback, cl.size):
        if cl[i] > hi[i - lookback : i].max():
            out[i] = 1
        elif cl[i] < lo[i - lookback : i].min():
            out[i] = -1
    return out


def failed_breakout(h: ArrayLike, low: ArrayLike, c: ArrayLike, *, lookback: int = 10) -> Ints:
    """-1 when a bar poked above the prior range high but CLOSED back inside it (+1 mirror).

    Both the poke and the close back inside are on the SAME bar, so the label is known at its
    close. +1 means a failed break DOWN (bullish), -1 a failed break UP (bearish).
    """
    hi, lo, cl = (np.asarray(x, dtype=np.float64) for x in (h, low, c))
    out = np.zeros(cl.size, dtype=np.int8)
    for i in range(lookback, cl.size):
        top, bottom = hi[i - lookback : i].max(), lo[i - lookback : i].min()
        if hi[i] > top and cl[i] <= top:
            out[i] = -1
        elif lo[i] < bottom and cl[i] >= bottom:
            out[i] = 1
    return out


def detect_patterns(
    o: ArrayLike, h: ArrayLike, low: ArrayLike, c: ArrayLike, atr: ArrayLike
) -> dict[str, Ints]:
    """Every detector for one timeframe."""
    return {
        "strong_body": strong_body(o, h, low, c),
        "pin_bar": pin_bar(o, h, low, c),
        "engulfing": engulfing(o, h, low, c),
        "inside_bar": inside_bar(h, low),
        "outside_bar": outside_bar(h, low),
        "range_expansion": range_expansion(h, low, atr),
        "compression": compression(h, low, atr),
        "breakout": breakout(h, low, c),
        "failed_breakout": failed_breakout(h, low, c),
    }
