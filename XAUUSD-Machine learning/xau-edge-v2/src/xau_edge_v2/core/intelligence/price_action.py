"""Descriptive, causal price-action events (observation only; no authority to trade).

Every event is decided with bars up to and including its own bar ``i`` and becomes known when that
bar CLOSES (``known_at_us = frame.available_us[i]``). Nothing is repainted: appending bars never
changes an event already emitted (tested). Thresholds are a-priori constants, never fitted, and a
pattern is a DESCRIPTION of what the bar did, not a forecast of the next bar.

Definitions (r = high - low, body = |close - open|, ATR = Wilder ATR(14) at the bar):

* wick rejection: r >= 0.5 ATR and one wick >= 0.6 r and >= 2 body; the rejected side is the long
  wick (UPPER wick = buyers rejected, LOWER wick = sellers rejected);
* engulfing: opposite colours and the body covers the previous body, body >= 0.3 ATR;
* inside / outside bar against the previous bar's high and low;
* displacement: r >= 1.5 ATR and body >= 0.6 r (a decisive, one-sided bar);
* failed breakout (sweep): the bar trades beyond the highest high (lowest low) of the previous 10
  bars but CLOSES back inside it.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.core import indicators as ind
from xau_edge_v2.core.frames import Frame

WICK_MIN_RANGE_ATR = 0.5
WICK_MIN_SHARE = 0.6
WICK_MIN_BODY_MULT = 2.0
ENGULF_MIN_BODY_ATR = 0.3
DISPLACEMENT_RANGE_ATR = 1.5
DISPLACEMENT_BODY_SHARE = 0.6
SWEEP_LOOKBACK = 10

KINDS = (
    "UPPER_WICK_REJECTION",
    "LOWER_WICK_REJECTION",
    "BULL_ENGULFING",
    "BEAR_ENGULFING",
    "INSIDE_BAR",
    "OUTSIDE_BAR",
    "BULL_DISPLACEMENT",
    "BEAR_DISPLACEMENT",
    "FAILED_BREAKOUT_UP",
    "FAILED_BREAKOUT_DOWN",
)

DESCRIPTION: dict[str, str] = {
    "UPPER_WICK_REJECTION": "bấc trên dài: giá cao bị từ chối",
    "LOWER_WICK_REJECTION": "bấc dưới dài: giá thấp bị từ chối",
    "BULL_ENGULFING": "nến tăng nhấn chìm thân nến giảm trước",
    "BEAR_ENGULFING": "nến giảm nhấn chìm thân nến tăng trước",
    "INSIDE_BAR": "nến nằm trong biên nến trước (nén)",
    "OUTSIDE_BAR": "nến vượt cả hai đầu nến trước (mở rộng)",
    "BULL_DISPLACEMENT": "nến tăng mạnh một chiều",
    "BEAR_DISPLACEMENT": "nến giảm mạnh một chiều",
    "FAILED_BREAKOUT_UP": "quét đỉnh rồi đóng lại bên dưới (phá vỡ thất bại)",
    "FAILED_BREAKOUT_DOWN": "quét đáy rồi đóng lại bên trên (phá vỡ thất bại)",
}


@dataclass(frozen=True)
class PriceActionEvent:
    kind: str
    index: int
    bar_open_us: int
    known_at_us: int
    """When the event became knowable: the close of its own bar (never earlier)."""
    level: float | None
    """The reference level: swept extreme, wick tip, or the previous bar's boundary."""
    invalidation: float | None
    """Price beyond which the description no longer holds (the event bar's own extreme)."""
    strength: float
    """Size of the event in ATR (range for wicks and displacement, body for engulfing)."""


def _atr(frame: Frame) -> NDArray[np.float64]:
    return ind.atr(frame.high, frame.low, frame.close, 14)


def detect_bar(frame: Frame, atr: NDArray[np.float64], i: int) -> list[PriceActionEvent]:  # noqa: PLR0912 - one rule per kind
    """Events of bar ``i`` using bars ``<= i`` only."""
    o, h, lo, c = frame.open[i], frame.high[i], frame.low[i], frame.close[i]
    a = float(atr[i]) if i < atr.size else float("nan")
    if not np.isfinite(a) or a <= 0:
        return []
    rng = float(h - lo)
    body = float(abs(c - o))
    upper = float(h - max(o, c))
    lower = float(min(o, c) - lo)
    t_open, t_known = int(frame.open_us[i]), int(frame.available_us[i])
    out: list[PriceActionEvent] = []

    def add(kind: str, level: float | None, invalidation: float | None, strength: float) -> None:
        out.append(PriceActionEvent(kind, i, t_open, t_known, level, invalidation, strength))

    if rng >= WICK_MIN_RANGE_ATR * a:
        if upper >= WICK_MIN_SHARE * rng and upper >= WICK_MIN_BODY_MULT * body:
            add("UPPER_WICK_REJECTION", float(h), float(h), rng / a)
        if lower >= WICK_MIN_SHARE * rng and lower >= WICK_MIN_BODY_MULT * body:
            add("LOWER_WICK_REJECTION", float(lo), float(lo), rng / a)
    if rng >= DISPLACEMENT_RANGE_ATR * a and body >= DISPLACEMENT_BODY_SHARE * rng:
        add("BULL_DISPLACEMENT" if c > o else "BEAR_DISPLACEMENT", float(c), float(o), rng / a)
    if i >= 1:
        po, ph, pl, pc = frame.open[i - 1], frame.high[i - 1], frame.low[i - 1], frame.close[i - 1]
        p_hi, p_lo = max(po, pc), min(po, pc)
        if p_hi > p_lo and body >= ENGULF_MIN_BODY_ATR * a:
            if c > o and pc < po and c >= p_hi and o <= p_lo:
                add("BULL_ENGULFING", float(p_hi), float(lo), body / a)
            elif c < o and pc > po and c <= p_lo and o >= p_hi:
                add("BEAR_ENGULFING", float(p_lo), float(h), body / a)
        if h <= ph and lo >= pl:
            add("INSIDE_BAR", float(ph), None, rng / a)
        elif h > ph and lo < pl:
            add("OUTSIDE_BAR", None, None, rng / a)
    if i >= SWEEP_LOOKBACK:
        prior_hi = float(frame.high[i - SWEEP_LOOKBACK : i].max())
        prior_lo = float(frame.low[i - SWEEP_LOOKBACK : i].min())
        if h > prior_hi and c < prior_hi:
            add("FAILED_BREAKOUT_UP", prior_hi, float(h), (h - prior_hi) / a)
        if lo < prior_lo and c > prior_lo:
            add("FAILED_BREAKOUT_DOWN", prior_lo, float(lo), (prior_lo - lo) / a)
    return out


def detect(frame: Frame, *, last: int | None = None) -> list[PriceActionEvent]:
    """Events for the last ``last`` bars (all bars when None), oldest first."""
    atr = _atr(frame)
    start = 0 if last is None else max(0, frame.height - last)
    events: list[PriceActionEvent] = []
    for i in range(start, frame.height):
        events.extend(detect_bar(frame, atr, i))
    return events
