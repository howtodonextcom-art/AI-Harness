"""Synthetic data generators for tests (no market information; code-path exercise only)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from xau_edge.domain.bars import BAR_SCHEMA
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.validators import MarketCalendar

NY = ZoneInfo("America/New_York")

# The session measured on the FTMO demo server (see configs/brokers/ftmo_demo.yaml).
FTMO_CALENDAR = MarketCalendar(
    weekend_close_minute=16 * 60 + 50,
    weekend_open_minute=18 * 60 + 5,
    daily_break_start_minute=16 * 60 + 50,
    daily_break_end_minute=18 * 60 + 5,
)


def drop_ny_window(df: pl.DataFrame, day: date, start_minute: int, end_minute: int) -> pl.DataFrame:
    """Remove bars opening on New York ``day`` with start <= minute-of-day < end (UTC frame)."""
    ny = pl.col("timestamp").dt.convert_time_zone("America/New_York")
    minute = ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32)
    in_window = (ny.dt.date() == day) & (minute >= start_minute) & (minute < end_minute)
    return df.filter(~in_window)


def ftmo_like_m5(weeks_from: datetime, weeks: int) -> pl.DataFrame:
    """M5 bars following the observed broker session, in UTC.

    Session in New York time: open Sunday 18:05, daily break 16:50-18:05 Mon-Thu, close Friday
    16:50 (last bar 16:45). ``weeks_from`` must be a Monday 00:00 UTC.
    """
    rows = []
    price = 2000.0
    step = timedelta(minutes=5)
    sunday = weeks_from.date() - timedelta(days=1)
    cursor = datetime(sunday.year, sunday.month, sunday.day, 18, 5, tzinfo=NY)
    end = cursor + timedelta(weeks=weeks)
    while cursor < end:
        local = cursor
        minute = local.hour * 60 + local.minute
        weekday = local.weekday()  # Mon=0..Sun=6
        closed = (
            weekday == 5
            or (weekday == 4 and minute >= 16 * 60 + 50)
            or (weekday == 6 and minute < 18 * 60 + 5)
            or (16 * 60 + 50 <= minute < 18 * 60 + 5)
        )
        if not closed:
            rows.append(
                {
                    "timestamp": cursor.astimezone(UTC),
                    "open": price,
                    "high": price + 0.3,
                    "low": price - 0.3,
                    "close": price + 0.1,
                    "tick_volume": 100,
                    "spread": 30,
                    "real_volume": None,
                }
            )
            price += 0.1
        cursor = (cursor.astimezone(UTC) + step).astimezone(NY)
    return pl.DataFrame(rows, schema=BAR_SCHEMA)


def to_server_labels(utc_bars: pl.DataFrame, clock: BrokerClock) -> pl.DataFrame:
    """Return the frame with ``timestamp`` replaced by naive broker wall-clock labels."""
    return utc_bars.with_columns(clock.utc_to_server(pl.col("timestamp")).alias("timestamp"))
