"""Causal indicators as pure NumPy functions (rewritten; parity with V1 proven by golden tests).

Every output has the input length, warm-up positions are NaN, and the value at index ``i`` uses
inputs ``0..i`` only (nothing repaints). Wilder smoothing follows ``x[i] = (x[i-1]*(n-1) + new)/n``.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

Floats = NDArray[np.float64]
_PCT = 100.0


class AdxResult(NamedTuple):
    adx: Floats
    plus_di: Floats
    minus_di: Floats


def _nan(n: int) -> Floats:
    return np.full(n, np.nan)


def _series(values: object, name: str) -> Floats:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1 or not np.isfinite(arr).all():
        msg = f"{name} must be a finite 1-D array"
        raise ValueError(msg)
    return arr


def _hlc(high: object, low: object, close: object) -> tuple[Floats, Floats, Floats]:
    h, lo, c = _series(high, "high"), _series(low, "low"), _series(close, "close")
    if not (h.shape == lo.shape == c.shape) or (h < lo).any():
        msg = "high, low and close must have the same length and high >= low"
        raise ValueError(msg)
    return h, lo, c


def ema(values: object, period: int) -> Floats:
    """EMA seeded with the SMA of the first ``period`` values; first valid index ``period - 1``."""
    arr = _series(values, "values")
    out = _nan(arr.size)
    if arr.size < period:
        return out
    k = 2.0 / (period + 1)
    prev = float(arr[:period].mean())
    out[period - 1] = prev
    for i in range(period, arr.size):
        prev = (arr[i] - prev) * k + prev
        out[i] = prev
    return out


def rsi(close: object, period: int = 14) -> Floats:
    """Wilder RSI in [0, 100]; first valid index ``period``; 0 when there is no movement at all."""
    c = _series(close, "close")
    n = c.size
    out = _nan(n)
    if n <= period:
        return out
    delta = np.diff(c)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = float(gain[:period].mean())
    avg_loss = float(loss[:period].mean())
    for i in range(period, n):
        if i > period:
            avg_gain = (avg_gain * (period - 1) + gain[i - 1]) / period
            avg_loss = (avg_loss * (period - 1) + loss[i - 1]) / period
        total = avg_gain + avg_loss
        out[i] = _PCT * avg_gain / total if total > 0 else 0.0
    return out


def true_range(high: object, low: object, close: object) -> Floats:
    h, lo, c = _hlc(high, low, close)
    out = _nan(h.size)
    if h.size > 1:
        prev = c[:-1]
        out[1:] = np.maximum.reduce([h[1:] - lo[1:], np.abs(h[1:] - prev), np.abs(lo[1:] - prev)])
    return out


def atr(high: object, low: object, close: object, period: int = 14) -> Floats:
    """Wilder ATR; first valid index ``period``."""
    tr = true_range(high, low, close)
    n = tr.size
    out = _nan(n)
    if n <= period:
        return out
    prev = float(tr[1 : period + 1].mean())
    out[period] = prev
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def adx(high: object, low: object, close: object, period: int = 14) -> AdxResult:
    """Wilder ADX with +DI / -DI; ADX first valid index ``2 * period - 1``, DI from ``period``."""
    h, lo, c = _hlc(high, low, close)
    n = h.size
    adx_out, plus_out, minus_out = _nan(n), _nan(n), _nan(n)
    if n <= period:
        return AdxResult(adx_out, plus_out, minus_out)
    up = h[1:] - h[:-1]
    down = lo[:-1] - lo[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(h, lo, c)[1:]
    s_plus = float(plus_dm[: period - 1].sum())
    s_minus = float(minus_dm[: period - 1].sum())
    s_tr = float(tr[: period - 1].sum())
    dx = _nan(n)
    for i in range(period, n):
        j = i - 1
        s_plus = s_plus - s_plus / period + plus_dm[j]
        s_minus = s_minus - s_minus / period + minus_dm[j]
        s_tr = s_tr - s_tr / period + tr[j]
        if s_tr > 0:
            plus_out[i] = _PCT * s_plus / s_tr
            minus_out[i] = _PCT * s_minus / s_tr
        else:
            plus_out[i] = minus_out[i] = 0.0
        di_sum = plus_out[i] + minus_out[i]
        dx[i] = _PCT * abs(plus_out[i] - minus_out[i]) / di_sum if di_sum > 0 else 0.0
    first = 2 * period - 1
    if n > first:
        prev = float(dx[period : first + 1].mean())
        adx_out[first] = prev
        for i in range(first + 1, n):
            prev = (prev * (period - 1) + dx[i]) / period
            adx_out[i] = prev
    return AdxResult(adx_out, plus_out, minus_out)


def volume_zscore(volume: object, window: int = 20) -> Floats:
    """``(v - mean) / std`` over the last ``window`` bars (sample std); NaN if flat."""
    v = _series(volume, "volume")
    out = _nan(v.size)
    if v.size >= window:
        view = sliding_window_view(v, window)
        mean = view.mean(axis=1)
        std = view.std(axis=1, ddof=1)
        ok = std > 0
        z = np.full(mean.shape, np.nan)
        z[ok] = (v[window - 1 :][ok] - mean[ok]) / std[ok]
        out[window - 1 :] = z
    return out


def volume_percentile(volume: object, window: int = 100) -> Floats:
    """Mid-rank share of the last ``window`` bars below the current bar (ties count half)."""
    v = _series(volume, "volume")
    out = _nan(v.size)
    for i in range(window - 1, v.size):
        win = v[i - window + 1 : i + 1]
        out[i] = float((np.sum(win < v[i]) + 0.5 * np.sum(win == v[i])) / win.size)
    return out


def volume_ratio(volume: object, window: int = 20) -> Floats:
    """Current volume over the mean of the PREVIOUS ``window`` bars."""
    v = _series(volume, "volume")
    out = _nan(v.size)
    for i in range(window, v.size):
        base = float(np.mean(v[i - window : i]))
        out[i] = v[i] / base if base > 0 else np.nan
    return out


def volume_acceleration(zscore: object, lag: int = 3) -> Floats:
    """Change of the volume z-score over ``lag`` bars."""
    z = np.asarray(zscore, dtype=np.float64)
    out = _nan(z.size)
    if z.size > lag:
        out[lag:] = z[lag:] - z[:-lag]
    return out
