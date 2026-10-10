"""Market context for the trader's header: day statistics and candle countdowns (server side).

Everything here is derived from canonical closed bars (and the live quote for the open extreme), on
the broker day (server wall-clock date, the same day definition as PDH/PDL). The browser never
guesses a day boundary, a high/low or a bar close: it only displays what this module returns.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock

SESSION_LABELS = {
    "ASIA": "Phiên Á (Tokyo)",
    "LONDON": "Phiên Âu (London)",
    "NEW_YORK": "Phiên Mỹ (New York)",
    "LONDON_NY_OVERLAP": "Âu-Mỹ chồng phiên",
    "OFF_HOURS": "Ngoài phiên chính",
}


def day_stats(
    m5: pl.DataFrame | None,
    clock: BrokerClock | None,
    now: datetime,
    price: float | None,
) -> dict[str, Any] | None:
    """Open/high/low/range and change of the current (or last traded) broker day.

    ``change`` is measured from the previous broker day's last close when it is known, otherwise
    from the day's open (``change_basis`` says which). While the market is closed the figures are
    those of the last traded day and ``is_current_day`` is False.
    """
    if m5 is None or m5.height == 0 or clock is None:
        return None
    frame = m5.filter(pl.col("available_at") <= now) if "available_at" in m5.columns else m5
    if frame.height == 0:
        return None
    wall = clock.utc_to_server(frame["timestamp"])
    frame = frame.with_columns(wall.dt.date().alias("_day"))
    last_day = frame["_day"][-1]
    today = clock.to_server_wall(now).date()
    day = frame.filter(pl.col("_day") == last_day)
    before = frame.filter(pl.col("_day") < last_day)
    current = last_day == today
    high = float(day["high"].max())  # type: ignore[arg-type]
    low = float(day["low"].min())  # type: ignore[arg-type]
    last = float(day["close"][-1])
    if price is not None and current:
        high, low, last = max(high, price), min(low, price), price
    day_open = float(day["open"][0])
    prev_close = float(before["close"][-1]) if before.height else None
    base = prev_close if prev_close is not None else day_open
    change = last - base
    return {
        "day": last_day.isoformat(),
        "is_current_day": current,
        "open": day_open,
        "high": high,
        "low": low,
        "range": high - low,
        "prev_close": prev_close,
        "last": last,
        "change": change,
        "change_pct": None if base == 0 else change / base * 100.0,
        "change_basis": "PREV_CLOSE" if prev_close is not None else "DAY_OPEN",
        "range_position": None if high == low else (last - low) / (high - low),
    }


def bar_closes(
    frames: dict[Timeframe, pl.DataFrame], now: datetime, *, market_open: bool
) -> dict[str, str | None]:
    """When the bar forming now closes, per timeframe, from the broker-aligned closed-bar grid.

    The next close is the last closed bar's close plus one bar length; it is withheld (``None``)
    when the market is closed or the grid is behind (a gap), because a countdown to a bar that
    will not form would mislead.
    """
    out: dict[str, str | None] = {}
    for tf, frame in frames.items():
        value: str | None = None
        if market_open and frame.height and "available_at" in frame.columns:
            last_close = frame["available_at"][-1]
            nxt = last_close + timedelta(minutes=tf.minutes)
            if isinstance(nxt, datetime) and last_close <= now < nxt + timedelta(seconds=1):
                value = nxt.isoformat()
        out[tf.value] = value
    return out


def market_context(
    frames: dict[Timeframe, pl.DataFrame],
    clock: BrokerClock | None,
    now: datetime,
    *,
    price: float | None,
    session: str,
    market_open: bool,
) -> dict[str, Any]:
    return {
        "server_time": now.isoformat(),
        "session": {"code": session, "label": SESSION_LABELS.get(session, session)},
        "daily": day_stats(frames.get(Timeframe.M5), clock, now, price),
        "bar_close": bar_closes(frames, now, market_open=market_open),
    }
