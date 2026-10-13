"""Market-structure events with explicit knowledge times.

A swing high at bar ``i`` needs ``right`` further bars before it exists: it is KNOWN at the close of
bar ``i + right`` (``known_at_us``), never at bar ``i``. The pivot rule is the one in
``core.structure`` (strictly higher than the ``left`` bars before, at least as high as the
``right`` bars after), and a test pins the two to the same swing. A PROVISIONAL swing is the
candidate inside the last ``right`` bars: it is shown as unconfirmed and may still disappear.

BOS / CHoCH come from ``analyse_structure`` (a CLOSE beyond the latest unbroken swing; BOS follows
the prior trend, CHoCH opposes it). The broken level is the swing in force before that bar.
A FAILED_BREAK is a BOS/CHoCH whose broken level is lost again by a close within 3 bars.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from xau_edge_v2.core import structure as st
from xau_edge_v2.core.frames import Frame

FAIL_WINDOW = 3


@dataclass(frozen=True)
class Swing:
    kind: str
    """HIGH or LOW."""
    index: int
    price: float
    bar_open_us: int
    known_at_us: int
    """Close of bar ``index + right`` for a confirmed swing; the last bar's close if provisional."""
    confirmed: bool


@dataclass(frozen=True)
class StructureEvent:
    kind: str
    """BOS_UP, BOS_DOWN, CHOCH_UP, CHOCH_DOWN or FAILED_BREAK_UP / FAILED_BREAK_DOWN."""
    index: int
    bar_open_us: int
    known_at_us: int
    level: float | None


def swings(frame: Frame, *, left: int = st.SWING_LEFT, right: int = st.SWING_RIGHT) -> list[Swing]:
    """Confirmed swings (oldest first) followed by at most one provisional high and low."""
    h, lo = frame.high, frame.low
    n = frame.height
    out: list[Swing] = []
    for i in range(left, n - right):
        if h[i] > h[i - left : i].max() and h[i] >= h[i + 1 : i + right + 1].max():
            out.append(
                Swing(
                    "HIGH",
                    i,
                    float(h[i]),
                    int(frame.open_us[i]),
                    int(frame.available_us[i + right]),
                    True,
                )
            )
        if lo[i] < lo[i - left : i].min() and lo[i] <= lo[i + 1 : i + right + 1].min():
            out.append(
                Swing(
                    "LOW",
                    i,
                    float(lo[i]),
                    int(frame.open_us[i]),
                    int(frame.available_us[i + right]),
                    True,
                )
            )
    for i in range(max(left, n - right), n):
        after_hi = h[i + 1 :].max() if i + 1 < n else -np.inf
        after_lo = lo[i + 1 :].min() if i + 1 < n else np.inf
        if h[i] > h[i - left : i].max() and h[i] >= after_hi:
            out.append(
                Swing(
                    "HIGH",
                    i,
                    float(h[i]),
                    int(frame.open_us[i]),
                    int(frame.available_us[-1]),
                    False,
                )
            )
        if lo[i] < lo[i - left : i].min() and lo[i] <= after_lo:
            out.append(
                Swing(
                    "LOW",
                    i,
                    float(lo[i]),
                    int(frame.open_us[i]),
                    int(frame.available_us[-1]),
                    False,
                )
            )
    return out


def last_swing(items: list[Swing], kind: str, *, confirmed_only: bool = True) -> Swing | None:
    for s in reversed(items):
        if s.kind == kind and (s.confirmed or not confirmed_only):
            return s
    return None


def structure_events(frame: Frame) -> list[StructureEvent]:
    """BOS / CHoCH / failed breaks over the whole frame, oldest first."""
    res = st.analyse_structure(frame.high, frame.low, frame.close)
    n = frame.height
    out: list[StructureEvent] = []
    for j in range(n):
        for arr, name in ((res.bos, "BOS"), (res.choch, "CHOCH")):
            v = int(arr[j])
            if v == 0:
                continue
            ref = res.last_swing_high if v > 0 else res.last_swing_low
            level = float(ref[j - 1]) if j >= 1 and np.isfinite(ref[j - 1]) else None
            side = "UP" if v > 0 else "DOWN"
            out.append(
                StructureEvent(
                    f"{name}_{side}", j, int(frame.open_us[j]), int(frame.available_us[j]), level
                )
            )
            if level is None:
                continue
            for k in range(j + 1, min(n, j + 1 + FAIL_WINDOW)):
                lost = frame.close[k] < level if v > 0 else frame.close[k] > level
                if lost:
                    out.append(
                        StructureEvent(
                            f"FAILED_BREAK_{side}",
                            k,
                            int(frame.open_us[k]),
                            int(frame.available_us[k]),
                            level,
                        )
                    )
                    break
    return out
