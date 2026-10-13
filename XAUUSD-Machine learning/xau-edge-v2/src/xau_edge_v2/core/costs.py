"""Cost model: what a round trip costs, with an honest status for every component.

Nothing here is silently zero. Each component carries where it came from:

* ``spread``  MEASURED when the live quote exists (or from stored ticks), else UNKNOWN;
* ``slippage`` ASSUMED (3 points per market fill, the V1 research assumption, not measured);
* ``commission`` ASSUMED 0 USD/lot/side (V1: "0 for FTMO gold CFDs is UNVERIFIED"; set from the
  account type before any claim about net results);
* ``swap`` per night, read from the FTMO demo terminal on 2026-10-08 (they change: re-read before
  use); NOT included in the round-trip estimate, reported next to it for a position held overnight.

The overall status is the weakest component: MEASURED only if every included component is measured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.core.risk import SymbolSpec

CostStatus = Literal["MEASURED", "ASSUMED", "UNKNOWN"]
SLIPPAGE_POINTS = 3.0
COMMISSION_PER_LOT_PER_SIDE = 0.0
SWAP_LONG_POINTS = -76.05
SWAP_SHORT_POINTS = -4.2
SWAP_NOTE = (
    "swap read from the FTMO demo terminal on 2026-10-08 "
    "(long -76.05, short -4.2 points/lot/night); re-read before relying on it"
)


@dataclass(frozen=True)
class CostEstimate:
    total_usd: float | None
    spread_usd: float | None
    slippage_usd: float
    commission_usd: float
    status: CostStatus
    swap_note: str


def estimate_round_trip(lots: float, spread_price: float | None, spec: SymbolSpec) -> CostEstimate:
    """Spread + two fills of slippage + commission for ``lots``; UNKNOWN without a spread."""
    slippage = 2 * lots * spec.loss_per_lot(SLIPPAGE_POINTS * spec.point)
    commission = 2 * lots * COMMISSION_PER_LOT_PER_SIDE
    if spread_price is None:
        return CostEstimate(None, None, slippage, commission, "UNKNOWN", SWAP_NOTE)
    spread = lots * spec.loss_per_lot(spread_price)
    total = spread + slippage + commission
    return CostEstimate(total, spread, slippage, commission, "ASSUMED", SWAP_NOTE)


def swap_per_night_usd(direction: int, lots: float, spec: SymbolSpec) -> float:
    """Swap in USD for one night (negative = cost); triple-Wednesday swap is not modelled."""
    points = SWAP_LONG_POINTS if direction > 0 else SWAP_SHORT_POINTS
    return points * lots * spec.point * spec.contract_size


@dataclass(frozen=True)
class SpreadStats:
    ticks: int
    median_points: float
    p90_points: float
    p99_points: float
    max_points: float


def spread_stats_from_ticks(
    bid: NDArray[np.float64], ask: NDArray[np.float64], point: float
) -> SpreadStats | None:
    """Measured spread distribution (in points) from stored ticks, ignoring crossed quotes."""
    spread = (ask - bid) / point
    spread = spread[np.isfinite(spread) & (spread >= 0)]
    if spread.size == 0:
        return None
    q = np.quantile(spread, [0.5, 0.9, 0.99])
    return SpreadStats(int(spread.size), float(q[0]), float(q[1]), float(q[2]), float(spread.max()))
