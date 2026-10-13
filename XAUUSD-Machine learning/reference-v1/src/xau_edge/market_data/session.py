"""Market session state: OPEN, CLOSED (weekend), ROLLOVER (daily break), MAINTENANCE, UNKNOWN.

A closed market does not tick, and that is not a data failure. The state is derived from the
broker profile's calendar (same model the validators use); a holiday the calendar does not know is
not guessed: with no ticks during an "OPEN" window the caller reports STALE, never silently fine.
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from xau_edge.domain.market import MarketStatus
from xau_edge.market_data.validators.market_calendar import MarketCalendar


def market_status(now: datetime, calendar: MarketCalendar) -> MarketStatus:
    """The expected state of the market at ``now`` (a timezone-aware instant)."""
    if now.tzinfo is None:
        return MarketStatus.UNKNOWN
    ts = pl.Series("t", [now]).dt.convert_time_zone("UTC")
    frame = pl.DataFrame({"t": ts})
    closed = bool(frame.select(calendar.closed_expr(pl.col("t")).alias("c"))["c"][0])
    if not closed:
        return MarketStatus.OPEN
    if any(w.start <= now < w.end for w in calendar.closures):
        return MarketStatus.CLOSED  # a holiday or early-close window, not the daily break
    local = frame.select(pl.col("t").dt.convert_time_zone(calendar.timezone).alias("l"))["l"][0]
    weekday = local.isoweekday()  # Monday=1 ... Sunday=7
    minute = local.hour * 60 + local.minute
    weekend = (
        weekday == 6
        or (weekday == 5 and minute >= calendar.weekend_close_minute)
        or (weekday == 7 and minute < calendar.weekend_open_minute)
    )
    return MarketStatus.CLOSED if weekend else MarketStatus.ROLLOVER
