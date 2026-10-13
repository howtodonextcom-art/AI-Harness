"""Volatility phase and compression-box breakout, causal and descriptive.

* ATR ratio = ATR(14) now / median of the previous 100 ATR values (current excluded);
* COMPRESSION: the mean range of the last 6 bars <= 0.7 ATR and ATR ratio <= 0.85;
* EXPANSION: the last bar's range >= 1.5 ATR or ATR ratio >= 1.3; otherwise NORMAL;
* compression box: high / low of the 12 bars BEFORE the last bar, valid when that box is tight
  (height <= 3 ATR and mean range <= 0.8 ATR). A close beyond it is a BOX_BREAKOUT_UP / DOWN,
  a close that returns inside within 3 bars is a BOX_BREAKOUT_FAILED (reported by the scenario).

Constants are a-priori, not fitted. Nothing here looks at a bar after the one being described.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core.frames import Frame

BASELINE_BARS = 100
RECENT_BARS = 6
COMPRESSION_RANGE_ATR = 0.7
COMPRESSION_ATR_RATIO = 0.85
EXPANSION_RANGE_ATR = 1.5
EXPANSION_ATR_RATIO = 1.3
BOX_BARS = 12
BOX_MAX_HEIGHT_ATR = 3.0
BOX_MAX_MEAN_RANGE_ATR = 0.8
MIN_BARS = 40


@dataclass(frozen=True)
class VolatilityView:
    phase: str
    """COMPRESSION, NORMAL, EXPANSION or UNKNOWN."""
    atr: float | None
    atr_ratio: float | None
    recent_range_atr: float | None
    box_high: float | None
    box_low: float | None
    box_valid: bool
    box_breakout: int
    """+1 / -1 when the LAST bar closed beyond a valid box, else 0."""
    box_known_at_us: int | None


UNKNOWN_VIEW = VolatilityView("UNKNOWN", None, None, None, None, None, False, 0, None)


def analyse(frame: Frame) -> VolatilityView:
    n = frame.height
    if n < MIN_BARS:
        return UNKNOWN_VIEW
    atr = ind.atr(frame.high, frame.low, frame.close, 14)
    a = float(atr[-1])
    valid = atr[:-1][np.isfinite(atr[:-1])][-BASELINE_BARS:]
    if not np.isfinite(a) or a <= 0 or valid.size < 20:
        return UNKNOWN_VIEW
    ratio = a / float(np.median(valid))
    rng = frame.high - frame.low
    recent = float(rng[-RECENT_BARS:].mean()) / a
    last_range = float(rng[-1]) / a
    if last_range >= EXPANSION_RANGE_ATR or ratio >= EXPANSION_ATR_RATIO:
        phase = "EXPANSION"
    elif recent <= COMPRESSION_RANGE_ATR and ratio <= COMPRESSION_ATR_RATIO:
        phase = "COMPRESSION"
    else:
        phase = "NORMAL"
    box_hi = float(frame.high[-1 - BOX_BARS : -1].max())
    box_lo = float(frame.low[-1 - BOX_BARS : -1].min())
    box_mean = float(rng[-1 - BOX_BARS : -1].mean()) / a
    box_valid = (box_hi - box_lo) <= BOX_MAX_HEIGHT_ATR * a and box_mean <= BOX_MAX_MEAN_RANGE_ATR
    close = float(frame.close[-1])
    breakout = 0
    if box_valid:
        breakout = 1 if close > box_hi else -1 if close < box_lo else 0
    return VolatilityView(
        phase,
        a,
        ratio,
        recent,
        box_hi,
        box_lo,
        box_valid,
        breakout,
        int(frame.available_us[-1]),
    )
