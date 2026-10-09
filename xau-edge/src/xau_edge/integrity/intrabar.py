"""Intrabar ambiguity (roadmap section 18).

On OHLC data a bar can touch both the take-profit and the stop-loss; the order inside the bar is
unknown. We always keep the conservative (pessimistic) outcome as the primary one and report the
optimistic bound next to it. If the conclusion depends on which bound is used, the candidate is
INTRABAR_SENSITIVE and needs lower-timeframe confirmation before any promotion.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

INTRABAR_SENSITIVE = "INTRABAR_SENSITIVE"
INTRABAR_ROBUST = "INTRABAR_ROBUST"
MAX_AMBIGUOUS_FRACTION = 0.10


@dataclass(frozen=True)
class IntrabarReport:
    """Bounds on the mean result and the verdict about their disagreement."""

    n: int
    ambiguous_count: int
    ambiguous_fraction: float
    pessimistic_mean_r: float
    optimistic_mean_r: float
    status: str
    recommendation: str


def classify_bar(
    *, high: float, low: float, take_profit: float, stop_loss: float, long: bool
) -> str:
    """TP, SL, AMBIGUOUS or NONE for one bar of a trade already open."""
    if long:
        tp, sl = high >= take_profit, low <= stop_loss
    else:
        tp, sl = low <= take_profit, high >= stop_loss
    if tp and sl:
        return "AMBIGUOUS"
    if tp:
        return "TP"
    if sl:
        return "SL"
    return "NONE"


def intrabar_report(
    pessimistic_r: NDArray[np.float64],
    optimistic_r: NDArray[np.float64],
    ambiguous: NDArray[np.bool_],
) -> IntrabarReport:
    """Compare the two bounds. The primary evidence stays the pessimistic one."""
    n = len(pessimistic_r)
    if n == 0 or not (n == len(optimistic_r) == len(ambiguous)):
        msg = "inputs must be non-empty and the same length"
        raise ValueError(msg)
    if np.any(optimistic_r < pessimistic_r - 1e-12):
        msg = "the optimistic outcome cannot be worse than the pessimistic one"
        raise ValueError(msg)
    pess, opt = float(pessimistic_r.mean()), float(optimistic_r.mean())
    count = int(ambiguous.sum())
    fraction = count / n
    sensitive = (pess > 0) != (opt > 0) or fraction > MAX_AMBIGUOUS_FRACTION
    return IntrabarReport(
        n=n,
        ambiguous_count=count,
        ambiguous_fraction=fraction,
        pessimistic_mean_r=pess,
        optimistic_mean_r=opt,
        status=INTRABAR_SENSITIVE if sensitive else INTRABAR_ROBUST,
        recommendation=(
            "confirm with lower-timeframe data before any promotion" if sensitive else ""
        ),
    )
