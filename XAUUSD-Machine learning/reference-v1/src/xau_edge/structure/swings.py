"""Deterministic, non-repainting market structure (rules documented in ADR-0012).

Definitions, all computed bar by bar from data up to and including that bar:

* **Swing high** at bar ``i``: ``high[i]`` is strictly greater than the ``left`` bars before it and
  greater than or equal to the ``right`` bars after it. It is *confirmed* (and only then visible)
  at bar ``i + right``; nothing is ever reported earlier, so labels never repaint.
* **Swing low**: the mirror image.
* **HH / LH**: a new confirmed swing high above / below the previous one; **HL / LL** likewise for
  lows. Equal prices give label 0.
* **Trend**: +1 when the latest high is HH and the latest low is HL, -1 when LH and LL, else 0.
* **Break**: the *close* crosses the latest confirmed swing level that has not been broken yet.
  Each swing level can be broken once.
* **BOS** (break of structure): a break in the direction of the prior trend, or any break while the
  prior trend is 0. **CHoCH** (change of character): a break against the prior trend (an upside
  break while the trend was -1, a downside break while it was +1).
* **Support / resistance**: among the last ``sr_lookback`` swings, the highest unbroken swing low
  below the close and the lowest unbroken swing high above it.
"""

from __future__ import annotations

from typing import NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.features.indicators import as_hlc

Floats = NDArray[np.float64]
Ints = NDArray[np.int8]


class StructureConfig(BaseModel):
    """Pivot window and support/resistance memory."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    left: int = Field(default=3, ge=1)
    right: int = Field(default=3, ge=1)
    sr_lookback: int = Field(default=10, ge=1)


class StructureResult(NamedTuple):
    """Per-bar structure state (each array has the input length)."""

    last_swing_high: Floats
    last_swing_low: Floats
    new_swing_high: Ints
    new_swing_low: Ints
    high_label: Ints
    low_label: Ints
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


def analyse_structure(  # noqa: PLR0912, PLR0915 - single-pass state machine
    high: ArrayLike, low: ArrayLike, close: ArrayLike, config: StructureConfig | None = None
) -> StructureResult:
    """Compute swings, labels, trend, BOS/CHoCH and support/resistance for a bar series."""
    cfg = config or StructureConfig()
    h, lo, c = as_hlc(high, low, close)
    n = h.size
    last_high = np.full(n, np.nan)
    last_low = np.full(n, np.nan)
    support = np.full(n, np.nan)
    resistance = np.full(n, np.nan)
    new_high = np.zeros(n, dtype=np.int8)
    new_low = np.zeros(n, dtype=np.int8)
    high_label = np.zeros(n, dtype=np.int8)
    low_label = np.zeros(n, dtype=np.int8)
    trend_out = np.zeros(n, dtype=np.int8)
    bos = np.zeros(n, dtype=np.int8)
    choch = np.zeros(n, dtype=np.int8)

    highs: list[_Swing] = []
    lows: list[_Swing] = []
    h_lab = l_lab = trend = 0

    for j in range(n):
        close_j = c[j]
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

        for swing in highs[-cfg.sr_lookback :]:
            swing.broken = swing.broken or close_j > swing.price
        for swing in lows[-cfg.sr_lookback :]:
            swing.broken = swing.broken or close_j < swing.price

        i = j - cfg.right
        if i - cfg.left >= 0:
            if h[i] > h[i - cfg.left : i].max() and h[i] >= h[i + 1 : j + 1].max():
                h_lab = _sign(h[i] - highs[-1].price) if highs else 0
                highs.append(_Swing(float(h[i])))
                new_high[j] = 1
            if lo[i] < lo[i - cfg.left : i].min() and lo[i] <= lo[i + 1 : j + 1].min():
                l_lab = _sign(lo[i] - lows[-1].price) if lows else 0
                lows.append(_Swing(float(lo[i])))
                new_low[j] = 1
            if new_high[j] or new_low[j]:
                trend = (
                    1 if (h_lab == 1 and l_lab == 1) else -1 if (h_lab == -1 and l_lab == -1) else 0
                )

        if highs:
            last_high[j] = highs[-1].price
        if lows:
            last_low[j] = lows[-1].price
        high_label[j], low_label[j], trend_out[j] = h_lab, l_lab, trend

        below = [s.price for s in lows[-cfg.sr_lookback :] if not s.broken and s.price < close_j]
        above = [s.price for s in highs[-cfg.sr_lookback :] if not s.broken and s.price > close_j]
        if below:
            support[j] = max(below)
        if above:
            resistance[j] = min(above)

    return StructureResult(
        last_high,
        last_low,
        new_high,
        new_low,
        high_label,
        low_label,
        trend_out,
        bos,
        choch,
        support,
        resistance,
    )
