"""Market-aware freshness: a timeframe is stale only when it MISSED bars the market was open for.

Raw age is the wrong test: the last H4 bar may legitimately have closed hours ago, and every
timeframe is "old" right after the daily break or over a weekend. The question is how many bars
should already have closed (within the calendar's open slots) but are not stored.

``ALLOWED_LATE`` is how many missed bars are tolerated per timeframe before it is called STALE:
M1 tolerates 3 (collector poll lag, a slow terminal), M5 2, everything slower 1.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

import polars as pl

from xau_edge.domain.market import Quote
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators.market_calendar import MarketCalendar

ALLOWED_LATE = {
    Timeframe.M1: 3,
    Timeframe.M5: 2,
    Timeframe.M15: 1,
    Timeframe.M30: 1,
    Timeframe.H1: 1,
    Timeframe.H4: 1,
}
CLOSE_GRACE = timedelta(seconds=45)
MAX_COUNT_WINDOW = timedelta(days=14)


def missed_closed_bars(
    last_open: datetime | None,
    tf: Timeframe,
    now: datetime,
    calendar: MarketCalendar,
    *,
    grace: timedelta = CLOSE_GRACE,
) -> int | None:
    """Open-market bar slots that should have closed by ``now - grace`` after ``last_open``.

    ``None`` when nothing is stored yet (unknown, not zero). Counting is capped at 14 days back.
    """
    if last_open is None:
        return None
    first_slot = max(last_open + tf.delta, now - MAX_COUNT_WINDOW)
    last_slot = now - grace - tf.delta  # a slot opening here has just closed
    if last_slot < first_slot:
        return 0
    slots = pl.datetime_range(first_slot, last_slot, interval=f"{tf.minutes}m", eager=True)
    if slots.len() == 0:
        return 0
    table = pl.DataFrame({"t": slots.dt.replace_time_zone("UTC")})
    closed = table.select(calendar.closed_span_expr(pl.col("t"), tf.minutes).alias("c"))["c"]
    return int((~closed).sum())


def bar_freshness(missed: int | None, tf: Timeframe) -> str:
    """FRESH, STALE or UNKNOWN (nothing stored)."""
    if missed is None:
        return "UNKNOWN"
    return "STALE" if missed > ALLOWED_LATE[tf] else "FRESH"


def consistency_warnings(
    quote: Quote | None, forming: Mapping[str, Mapping[str, Any]] | None
) -> list[str]:
    """Diagnostic (never fatal) checks between the live quote and the forming bars."""
    if quote is None or quote.timestamp is None or quote.mid is None or not forming:
        return []
    out: list[str] = []
    tolerance = max(5 * (quote.spread_price or 0.0), quote.mid * 0.0025)
    for name, bar in forming.items():
        opened = datetime.fromisoformat(str(bar["timestamp"]))
        if quote.timestamp < opened:
            out.append(f"{name}: quote is older than the forming bar's open")
        low, high = float(bar["low"]), float(bar["high"])
        if not low - tolerance <= quote.mid <= high + tolerance:
            out.append(
                f"{name}: quote {quote.mid:.2f} is outside the forming range {low:.2f}-{high:.2f}"
            )
    return out
