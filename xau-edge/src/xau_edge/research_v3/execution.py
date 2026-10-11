"""Fill-side-correct trade simulation on stored M1 bid bars (V3 COMMON_PROTOCOL, cost model v2).

Prices are bid. A buy fills at ask = bid + spread x era multiplier of that minute; a sell fills at
bid. So a long pays the spread on entry and a short pays it on exit: one spread per round trip, on
the side that actually crosses it (no double spread). Short stops and targets trigger on the ask.
Both barriers inside one M1 bar: the stop first. A later bar opening beyond the stop fills at that
open; a later bar opening beyond the target fills at the target (no gap gift).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

POINT = 0.01
CONTRACT_OZ = 100.0
TICK_ERA_START = datetime(2021, 10, 1, tzinfo=UTC)
SWAP_LONG_POINTS = -69.25
"""MT5 symbol_info XAUUSD read 2026-10-11T06:16Z (swap_mode 1 = points; triple on Wednesday)."""
SWAP_SHORT_POINTS = -4.2
NEW_YORK = ZoneInfo("America/New_York")
ROLLOVER_NY = time(17, 0)
"""The broker rollover is 17:00 New York (the protocol's "21:00 UTC" is its summer value)."""


@dataclass(frozen=True)
class Scenario:
    name: str
    spread_mult: float
    slip_points: float


GROSS = Scenario("gross", 0.0, 0.0)


def scenarios_for_year(year: int) -> tuple[Scenario, Scenario]:
    """(base, pessimistic) bar-spread scenarios of cost model v2 for a decision year."""
    if year >= TICK_ERA_START.year:
        raise NotImplementedError(
            "2021 needs the 2021-10 tick-spread switch; not needed by Stage 1"
        )
    return Scenario("base", 1.6, 3.0), Scenario("pessimistic", 2.4, 6.0)


@dataclass(frozen=True)
class M1:
    t: NDArray[np.int64]
    o: NDArray[np.float64]
    h: NDArray[np.float64]
    low: NDArray[np.float64]
    spread: NDArray[np.float64]


@dataclass(frozen=True)
class Fill:
    entry_px: float
    exit_px: float
    exit_i: int
    reason: str
    """STOP_LOSS, TAKE_PROFIT or TIME_EXIT."""
    r: float
    """direction * (exit - entry) / unit - 2 * slippage / unit (swap added by the caller)."""


def simulate(  # noqa: PLR0917
    m1: M1,
    e: int,
    x: int,
    direction: int,
    unit: float,
    stop_dist: float,
    target_dist: float | None,
    sc: Scenario,
    *,
    x_exists: bool = True,
) -> Fill | None:
    """Enter at the open of M1 bar ``e``; time exit at the open of M1 bar ``x`` (exclusive scan).

    ``x_exists=False`` means the timeout hour has no M1 bar: a trade that reaches the timeout
    cannot be priced and returns None; a barrier exit before it is unaffected.
    """
    sp = m1.spread * POINT * sc.spread_mult
    entry = m1.o[e] + (sp[e] if direction > 0 else 0.0)
    stop = entry - direction * stop_dist
    target = None if target_dist is None else entry + direction * target_dist
    for j in range(e, x):
        adj = 0.0 if direction > 0 else sp[j]
        hi, lo, op = m1.h[j] + adj, m1.low[j] + adj, m1.o[j] + adj
        hit_s = lo <= stop if direction > 0 else hi >= stop
        if hit_s:
            gapped = j > e and (op <= stop if direction > 0 else op >= stop)
            return _fill(entry, op if gapped else stop, j, "STOP_LOSS", direction, unit, sc)
        if target is not None and (hi >= target if direction > 0 else lo <= target):
            return _fill(entry, target, j, "TAKE_PROFIT", direction, unit, sc)
    if not x_exists:
        return None
    exit_px = m1.o[x] + (0.0 if direction > 0 else sp[x])
    return _fill(entry, exit_px, x, "TIME_EXIT", direction, unit, sc)


def _fill(  # noqa: PLR0917
    entry: float, exit_px: float, i: int, reason: str, direction: int, unit: float, sc: Scenario
) -> Fill:
    r = direction * (exit_px - entry) / unit - 2 * sc.slip_points * POINT / unit
    return Fill(entry, exit_px, i, reason, r)


def rollovers(entry_us: int, exit_us: int, *, triple_wednesday: bool = False) -> int:
    """Swap nights: 17:00 New York instants on Monday..Friday with entry < instant <= exit."""
    a = datetime.fromtimestamp(entry_us / 1e6, tz=UTC)
    b = datetime.fromtimestamp(exit_us / 1e6, tz=UTC)
    d = a.astimezone(NEW_YORK).date()
    n = 0
    while True:
        instant = datetime.combine(d, ROLLOVER_NY, NEW_YORK).astimezone(UTC)
        if instant > b:
            return n
        if instant > a and d.weekday() < 5:
            n += 3 if (triple_wednesday and d.weekday() == 2) else 1
        d += timedelta(days=1)


def swap_r(direction: int, nights: int, unit: float) -> float:
    pts = SWAP_LONG_POINTS if direction > 0 else SWAP_SHORT_POINTS
    return pts * POINT * nights / unit
