"""Technical indicators as pure NumPy functions.

Conventions (verified against TA-Lib recorded output in ``tests/fixtures/talib_golden.json``):

* Inputs are 1-D float arrays of equal length, finite, oldest first. They are never modified.
* Every output has the input length. Warm-up positions are ``NaN``; the first valid position is
  documented per function. Input shorter than the warm-up gives all ``NaN``.
* Causal: the value at index ``i`` depends only on inputs ``0..i`` (tests append bars and require
  identical past output, so nothing repaints).
* Moving averages are seeded with a simple average; Wilder smoothing (RSI, ATR, ADX) follows
  Wilder's original recursion ``x[i] = (x[i-1] * (n - 1) + new) / n``.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import ArrayLike, NDArray

Floats = NDArray[np.float64]

_PERCENT = 100.0
_MAX_MAGNITUDE = 1e150


class AdxResult(NamedTuple):
    """ADX (first valid index ``2 * period - 1``) with +DI/-DI (first valid ``period``)."""

    adx: Floats
    plus_di: Floats
    minus_di: Floats


class MacdResult(NamedTuple):
    """MACD line (valid from ``slow - 1``); signal and histogram (from ``slow + signal - 2``)."""

    macd: Floats
    signal: Floats
    histogram: Floats


class StochasticResult(NamedTuple):
    """Slow stochastic %K and %D, both in [0, 100]."""

    k: Floats
    d: Floats


class BollingerResult(NamedTuple):
    """Bollinger bands around a simple moving average (population standard deviation)."""

    upper: Floats
    middle: Floats
    lower: Floats


def _series(values: ArrayLike, name: str = "values") -> Floats:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        msg = f"{name} must be 1-D, got shape {arr.shape}"
        raise ValueError(msg)
    if not np.isfinite(arr).all():
        msg = f"{name} must be finite (no NaN or infinity)"
        raise ValueError(msg)
    if arr.size and np.abs(arr).max() > _MAX_MAGNITUDE:
        msg = f"{name} magnitude above 1e150 is unsupported (squares would overflow)"
        raise ValueError(msg)
    return arr


def _hlc(high: ArrayLike, low: ArrayLike, close: ArrayLike) -> tuple[Floats, Floats, Floats]:
    h, lo, c = _series(high, "high"), _series(low, "low"), _series(close, "close")
    if not (h.shape == lo.shape == c.shape):
        msg = f"high, low and close must have the same length, got {h.size}, {lo.size}, {c.size}"
        raise ValueError(msg)
    if (h < lo).any():
        msg = "high must be >= low on every bar"
        raise ValueError(msg)
    return h, lo, c


def _period(period: int, name: str = "period", *, minimum: int = 1) -> int:
    if isinstance(period, bool) or not isinstance(period, (int, np.integer)):
        msg = f"{name} must be an integer, got {period!r}"
        raise ValueError(msg)
    if period < minimum:
        msg = f"{name} must be >= {minimum}, got {period}"
        raise ValueError(msg)
    return int(period)


def _empty(n: int) -> Floats:
    return np.full(n, np.nan)


def _sma_valid(arr: Floats, period: int) -> Floats:
    """SMA over an array whose entries are all valid (no NaN prefix handling)."""
    out = _empty(arr.size)
    if arr.size >= period:
        out[period - 1 :] = sliding_window_view(arr, period).mean(axis=1)
    return out


def _first_valid(arr: Floats) -> int:
    valid = np.flatnonzero(~np.isnan(arr))
    return int(valid[0]) if valid.size else arr.size


def _ema_valid(
    arr: Floats, period: int, seed_at: int | None = None, seed_len: int | None = None
) -> Floats:
    """EMA seeded with the mean of ``arr[seed_at - seed_len + 1 : seed_at + 1]``.

    ``arr`` must be valid from the seed window onward. Defaults seed on the first ``period``
    values of ``arr``.
    """
    n = arr.size
    length = period if seed_len is None else seed_len
    at = length - 1 if seed_at is None else seed_at
    out = _empty(n)
    if n <= at or at - length + 1 < 0:
        return out
    k = 2.0 / (period + 1)
    prev = float(arr[at - length + 1 : at + 1].mean())
    out[at] = prev
    for i in range(at + 1, n):
        prev = (arr[i] - prev) * k + prev
        out[i] = prev
    return out


def sma(values: ArrayLike, period: int) -> Floats:
    """Simple moving average. First valid index: ``period - 1``."""
    _period(period)
    return _sma_valid(_series(values), period)


def ema(values: ArrayLike, period: int) -> Floats:
    """Exponential moving average, seeded with the SMA of the first ``period`` values.

    Smoothing factor ``2 / (period + 1)``. First valid index: ``period - 1``.
    """
    _period(period)
    return _ema_valid(_series(values), period)


def rsi(close: ArrayLike, period: int = 14) -> Floats:
    """Wilder's RSI in [0, 100] (``period`` >= 2). First valid index: ``period``.

    With no price movement in the seed window (average gain and loss both zero) the value is 0,
    matching TA-Lib.
    """
    _period(period, minimum=2)
    c = _series(close, "close")
    n = c.size
    out = _empty(n)
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
        out[i] = _PERCENT * avg_gain / total if total > 0 else 0.0
    return out


def true_range(high: ArrayLike, low: ArrayLike, close: ArrayLike) -> Floats:
    """True range: max(high - low, |high - previous close|, |low - previous close|).

    Index 0 is ``NaN`` (there is no previous close).
    """
    h, lo, c = _hlc(high, low, close)
    out = _empty(h.size)
    if h.size > 1:
        prev = c[:-1]
        out[1:] = np.maximum.reduce([h[1:] - lo[1:], np.abs(h[1:] - prev), np.abs(lo[1:] - prev)])
    return out


def atr(high: ArrayLike, low: ArrayLike, close: ArrayLike, period: int = 14) -> Floats:
    """Wilder's Average True Range. First valid index: ``period``."""
    _period(period)
    tr = true_range(high, low, close)
    n = tr.size
    out = _empty(n)
    if n <= period:
        return out
    prev = float(tr[1 : period + 1].mean())
    out[period] = prev
    for i in range(period + 1, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def adx(high: ArrayLike, low: ArrayLike, close: ArrayLike, period: int = 14) -> AdxResult:
    """Wilder's Average Directional Index with +DI and -DI (TA-Lib compatible)."""
    _period(period, minimum=2)
    h, lo, c = _hlc(high, low, close)
    n = h.size
    adx_out, plus_out, minus_out = _empty(n), _empty(n), _empty(n)
    if n <= period:
        return AdxResult(adx_out, plus_out, minus_out)

    up = h[1:] - h[:-1]
    down = lo[:-1] - lo[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)  # index j <-> bar j + 1
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = true_range(h, lo, c)[1:]

    s_plus = float(plus_dm[: period - 1].sum())
    s_minus = float(minus_dm[: period - 1].sum())
    s_tr = float(tr[: period - 1].sum())
    dx = _empty(n)
    for i in range(period, n):
        j = i - 1
        s_plus = s_plus - s_plus / period + plus_dm[j]
        s_minus = s_minus - s_minus / period + minus_dm[j]
        s_tr = s_tr - s_tr / period + tr[j]
        if s_tr > 0:
            plus_out[i] = _PERCENT * s_plus / s_tr
            minus_out[i] = _PERCENT * s_minus / s_tr
        else:
            plus_out[i] = minus_out[i] = 0.0
        di_sum = plus_out[i] + minus_out[i]
        dx[i] = _PERCENT * abs(plus_out[i] - minus_out[i]) / di_sum if di_sum > 0 else 0.0

    first = 2 * period - 1
    if n > first:
        prev = float(dx[period : first + 1].mean())
        adx_out[first] = prev
        for i in range(first + 1, n):
            prev = (prev * (period - 1) + dx[i]) / period
            adx_out[i] = prev
    return AdxResult(adx_out, plus_out, minus_out)


def macd(close: ArrayLike, fast: int = 12, slow: int = 26, signal: int = 9) -> MacdResult:
    """Moving Average Convergence Divergence (TA-Lib compatible seeding).

    Both EMAs are seeded at index ``slow - 1``: the slow EMA with the mean of the first ``slow``
    values, the fast EMA with the mean of the ``fast`` values ending there. The signal line is an
    EMA of the MACD line seeded with its first ``signal`` values.
    """
    _period(fast, "fast period")
    _period(slow, "slow period")
    _period(signal, "signal period")
    if fast >= slow:
        msg = f"fast period must be < slow period, got {fast} >= {slow}"
        raise ValueError(msg)
    c = _series(close, "close")
    slow_ema = _ema_valid(c, slow)
    fast_ema = _ema_valid(c, fast, seed_at=slow - 1, seed_len=fast)
    line = fast_ema - slow_ema
    sig = _empty(c.size)
    start = slow - 1
    if c.size >= start + signal:
        sig[start:] = _ema_valid(line[start:], signal)
    return MacdResult(line, sig, line - sig)


def stochastic(  # noqa: PLR0917 - conventional oscillator signature
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    k_period: int = 14,
    k_smooth: int = 3,
    d_period: int = 3,
) -> StochasticResult:
    """Slow stochastic oscillator (SMA smoothing).

    Raw %K is ``100 * (close - lowest low) / (highest high - lowest low)`` over ``k_period`` bars
    (0 when the range is zero, as in TA-Lib); %K is its ``k_smooth`` SMA and %D the ``d_period``
    SMA of %K. First valid index: %K ``k_period + k_smooth - 2``, %D ``+ d_period - 1``.
    """
    _period(k_period, "k period")
    _period(k_smooth, "k smoothing period")
    _period(d_period, "d period")
    h, lo, c = _hlc(high, low, close)
    n = h.size
    raw = _empty(n)
    if n >= k_period:
        hh = sliding_window_view(h, k_period).max(axis=1)
        ll = sliding_window_view(lo, k_period).min(axis=1)
        span = hh - ll
        raw[k_period - 1 :] = np.where(
            span > 0, _PERCENT * (c[k_period - 1 :] - ll) / np.where(span > 0, span, 1.0), 0.0
        )
    k_line = _empty(n)
    d_line = _empty(n)
    start = k_period - 1
    if n >= start + k_smooth:
        k_line[start:] = _sma_valid(raw[start:], k_smooth)
        start_d = start + k_smooth - 1
        if n >= start_d + d_period:
            d_line[start_d:] = _sma_valid(k_line[start_d:], d_period)
    return StochasticResult(k_line, d_line)


def bollinger(close: ArrayLike, period: int = 20, num_std: float = 2.0) -> BollingerResult:
    """Bollinger bands: SMA +/- ``num_std`` population standard deviations."""
    _period(period)
    if num_std < 0:
        msg = f"num_std must be >= 0, got {num_std}"
        raise ValueError(msg)
    c = _series(close, "close")
    mid = _sma_valid(c, period)
    std = _empty(c.size)
    if c.size >= period:
        std[period - 1 :] = sliding_window_view(c, period).std(axis=1, ddof=0)
    return BollingerResult(mid + num_std * std, mid, mid - num_std * std)


def simple_returns(close: ArrayLike) -> Floats:
    """``close[i] / close[i - 1] - 1``. Index 0 is ``NaN``."""
    return rolling_returns(close, 1)


def log_returns(close: ArrayLike) -> Floats:
    """``ln(close[i] / close[i - 1])``. Index 0 is ``NaN``. Prices must be positive."""
    c = _series(close, "close")
    if (c <= 0).any():
        msg = "close must be positive to take log returns"
        raise ValueError(msg)
    out = _empty(c.size)
    if c.size > 1:
        out[1:] = np.diff(np.log(c))
    return out


def rolling_returns(close: ArrayLike, window: int) -> Floats:
    """Return over ``window`` bars: ``close[i] / close[i - window] - 1``."""
    _period(window, "window")
    c = _series(close, "close")
    out = _empty(c.size)
    if c.size > window:
        out[window:] = c[window:] / c[:-window] - 1.0
    return out


def rolling_volatility(close: ArrayLike, window: int) -> Floats:
    """Sample standard deviation (ddof=1) of the last ``window`` log returns.

    First valid index: ``window`` (the first log return exists at index 1).
    """
    _period(window, "window")
    lr = log_returns(close)
    out = _empty(lr.size)
    if lr.size > window >= 2:
        out[window:] = sliding_window_view(lr[1:], window).std(axis=1, ddof=1)
    return out
