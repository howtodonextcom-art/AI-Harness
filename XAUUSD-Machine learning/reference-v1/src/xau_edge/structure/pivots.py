"""Confirmed swing pivots shared by the pattern detectors.

A pivot at bar ``i`` is only known ``right`` bars later (``confirmed_at = i + right``); every
detector must act on ``confirmed_at``, never on ``bar``. This module is the single place where that
rule is applied, so a detector cannot accidentally use a pivot before it exists.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

from numpy.typing import ArrayLike

from xau_edge.features.indicators import as_hlc
from xau_edge.structure.swings import StructureConfig, analyse_structure


class Pivot(NamedTuple):
    bar: int  # the bar where the extreme formed
    price: float
    kind: Literal["H", "L"]
    confirmed_at: int  # the first bar at which the pivot is knowable (bar + right)


def confirmed_pivots(
    high: ArrayLike, low: ArrayLike, close: ArrayLike, *, left: int, right: int
) -> list[Pivot]:
    """All swing pivots ordered by when they become known (then by bar)."""
    h, lo, c = as_hlc(high, low, close)
    res = analyse_structure(h, lo, c, StructureConfig(left=left, right=right))
    found: list[Pivot] = []
    for j in range(h.size):
        if res.new_swing_high[j]:
            found.append(Pivot(j - right, float(res.last_swing_high[j]), "H", j))
        if res.new_swing_low[j]:
            found.append(Pivot(j - right, float(res.last_swing_low[j]), "L", j))
    found.sort(key=lambda p: (p.confirmed_at, p.bar))
    return found


def alternate(history: list[Pivot], new: Pivot) -> Pivot | None:
    """Keep H and L strictly alternating; of two same-kind neighbours keep the more extreme.

    Returns the pivot that was replaced (superseded) so a caller can retire anything built on it,
    or ``None`` when ``new`` was appended or ignored.
    """
    if history and history[-1].kind == new.kind:
        last = history[-1]
        better = new.price > last.price if new.kind == "H" else new.price < last.price
        if better:
            history[-1] = new
            return last
        return None
    history.append(new)
    return None
