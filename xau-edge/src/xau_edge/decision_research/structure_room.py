# ruff: noqa: E501 - these modules carry their selection/audit record as prose
"""Structure room: does opposing confirmed structure leave the reward distance (plus one tick) free?

Audited properties (each has a test): only pivots already confirmed at the actionable bar are known (a
pivot confirmed later is the future); of several barriers the NEAREST one in the target's direction
decides, duplicates at one price change nothing; the target must stop at least one tick short of the
barrier; BUY and SELL are exact mirrors; no known barrier is UNKNOWN room, which is never free room.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from xau_edge.structure.pivots import Pivot


def nearest_barrier_gap(
    side: Literal["BUY", "SELL"], entry: float, pivots: Sequence[Pivot], actionable_at: int
) -> float | None:
    """Distance from ``entry`` to the nearest opposing confirmed pivot, or ``None`` if none is known.

    A BUY looks up at confirmed swing highs above the entry; a SELL looks down at swing lows below it.
    """
    known = [p for p in pivots if p.confirmed_at <= actionable_at]
    if side == "BUY":
        above = [p.price - entry for p in known if p.kind == "H" and p.price > entry]
        return min(above) if above else None
    below = [entry - p.price for p in known if p.kind == "L" and p.price < entry]
    return min(below) if below else None


def room_ok(gap: float | None, reward: float, tick: float) -> bool | None:
    """``True`` when the floored free distance covers the reward plus one tick; ``None`` if unknown."""
    if gap is None:
        return None
    return int(gap / tick) * tick >= reward + tick
