"""Non-repainting market structure, regime labels and the two candle patterns the chain uses.

* swing high at bar ``i``: ``high[i]`` > the ``left`` bars before and >= the ``right`` bars after;
  it is only visible (confirmed) at bar ``i + right``, so a label never changes afterwards;
* trend +1 when the latest high is higher and the latest low is higher, -1 for the mirror;
* a break is a CLOSE beyond the latest unbroken swing; BOS follows the prior trend, CHoCH opposes;
* regime per bar (first match wins): SHOCK, HIGH_VOLATILITY, TREND_UP/DOWN (ADX >= 25),
  LOW_VOLATILITY, RANGE. Thresholds are a-priori constants, never fitted.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

Floats = NDArray[np.float64]
Ints = NDArray[np.int8]

SWING_LEFT = 3
SWING_RIGHT = 3
SR_LOOKBACK = 10

ADX_TREND = 25.0
HIGH_VOL_RATIO = 1.5
LOW_VOL_RATIO = 0.67
SHOCK_RANGE_ATR = 3.0
_CHUNK = 4096


class StructureResult(NamedTuple):
    last_swing_high: Floats
    last_swing_low: Floats
    trend: Ints
    bos: Ints
    choch: Ints
    support: Floats
    resistance: Floats


class _Swing:
    __slots__ = ("broken", "price")

    def __init__(self, price: float) -> None:
        self.price = price
        self.broken = False


def _sign(delta: float) -> int:
    return int(delta > 0) - int(delta < 0)


def analyse_structure(  # noqa: PLR0912 - single-pass state machine
    high: Floats,
    low: Floats,
    close: Floats,
    *,
    left: int = SWING_LEFT,
    right: int = SWING_RIGHT,
    sr_lookback: int = SR_LOOKBACK,
) -> StructureResult:
    n = high.size
    last_high, last_low = np.full(n, np.nan), np.full(n, np.nan)
    support, resistance = np.full(n, np.nan), np.full(n, np.nan)
    trend_out = np.zeros(n, dtype=np.int8)
    bos, choch = np.zeros(n, dtype=np.int8), np.zeros(n, dtype=np.int8)
    highs: list[_Swing] = []
    lows: list[_Swing] = []
    h_lab = l_lab = trend = 0
    for j in range(n):
        close_j = close[j]
        prior_trend = trend
        event = 0
        if highs and not highs[-1].broken and close_j > highs[-1].price:
            highs[-1].broken = True
            event = 1
        elif lows and not lows[-1].broken and close_j < lows[-1].price:
            lows[-1].broken = True
            event = -1
        if event == 1:
            (choch if prior_trend < 0 else bos)[j] = 1
        elif event == -1:
            (choch if prior_trend > 0 else bos)[j] = -1
        for swing in highs[-sr_lookback:]:
            swing.broken = swing.broken or close_j > swing.price
        for swing in lows[-sr_lookback:]:
            swing.broken = swing.broken or close_j < swing.price
        i = j - right
        if i - left >= 0:
            new_swing = False
            if high[i] > high[i - left : i].max() and high[i] >= high[i + 1 : j + 1].max():
                h_lab = _sign(high[i] - highs[-1].price) if highs else 0
                highs.append(_Swing(float(high[i])))
                new_swing = True
            if low[i] < low[i - left : i].min() and low[i] <= low[i + 1 : j + 1].min():
                l_lab = _sign(low[i] - lows[-1].price) if lows else 0
                lows.append(_Swing(float(low[i])))
                new_swing = True
            if new_swing:
                trend = (
                    1 if (h_lab == 1 and l_lab == 1) else -1 if (h_lab == -1 and l_lab == -1) else 0
                )
        if highs:
            last_high[j] = highs[-1].price
        if lows:
            last_low[j] = lows[-1].price
        trend_out[j] = trend
        below = [s.price for s in lows[-sr_lookback:] if not s.broken and s.price < close_j]
        above = [s.price for s in highs[-sr_lookback:] if not s.broken and s.price > close_j]
        if below:
            support[j] = max(below)
        if above:
            resistance[j] = min(above)
    return StructureResult(last_high, last_low, trend_out, bos, choch, support, resistance)


def _past_median(values: Floats, window: int, min_history: int) -> Floats:
    """Median of the ``window`` values before each index (current excluded), NaN-aware."""
    n = values.size
    out = np.full(n, np.nan)
    padded = np.concatenate([np.full(window, np.nan), values])
    view = sliding_window_view(padded, window)[:n]
    for start in range(0, n, _CHUNK):
        block = view[start : start + _CHUNK]
        counts = (~np.isnan(block)).sum(axis=1)
        # rows without any value would warn ("All-NaN slice") and are NaN anyway (min_history >= 2);
        # feed them zeros instead of silencing warnings, which is not thread safe
        med = np.nanmedian(np.where((counts == 0)[:, None], 0.0, block), axis=1)
        med[counts < min_history] = np.nan
        out[start : start + _CHUNK] = med
    return out


def classify_regime(
    *,
    adx: Floats,
    plus_di: Floats,
    minus_di: Floats,
    atr: Floats,
    high: Floats,
    low: Floats,
    vol_window: int,
    min_history: int,
) -> NDArray[np.object_]:
    """One regime label (or ``None`` while unknown) per bar."""
    n = adx.size
    baseline = _past_median(atr, vol_window, min_history)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(baseline > 0, atr / baseline, np.nan)
    prev_atr = np.concatenate([[np.nan], atr[:-1]])
    bar_range = high - low
    out = np.full(n, None, dtype=object)
    known = ~np.isnan(adx) & ~np.isnan(plus_di) & ~np.isnan(minus_di) & ~np.isnan(ratio)
    known &= (prev_atr > 0) & ~np.isnan(bar_range)
    shock = known & (bar_range >= SHOCK_RANGE_ATR * prev_atr)
    high_vol = known & (ratio >= HIGH_VOL_RATIO)
    trending = known & (adx >= ADX_TREND)
    low_vol = known & (ratio <= LOW_VOL_RATIO)
    out[known] = "RANGE"
    out[low_vol] = "LOW_VOLATILITY"
    out[trending & (plus_di > minus_di)] = "TREND_UP"
    out[trending & (minus_di > plus_di)] = "TREND_DOWN"
    out[high_vol] = "HIGH_VOLATILITY"
    out[shock] = "SHOCK"
    return out


def strong_body(
    o: Floats, h: Floats, low: Floats, c: Floats, min_body_to_range: float = 0.6
) -> Ints:
    """+1 / -1 when the body fills at least 60% of the range (up / down)."""
    rng = h - low
    body = c - o
    big = (rng > 0) & (np.abs(body) >= min_body_to_range * np.where(rng > 0, rng, 1.0))
    return np.where(big, np.sign(body), 0).astype(np.int8)


def range_expansion(h: Floats, low: Floats, atr: Floats, k: float = 1.5) -> Ints:
    """1 when the bar's range is at least ``k`` x the ATR (ATR must be known)."""
    rng = h - low
    return (np.isfinite(atr) & (atr > 0) & (rng >= k * np.where(atr > 0, atr, 1.0))).astype(np.int8)
