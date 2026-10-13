"""Temporal features and trading-session labels from bar-open timestamps (ADR-0011).

Sessions follow local exchange hours so daylight saving is handled by the time-zone database:

* ASIA: 09:00-18:00 Asia/Tokyo
* LONDON: 08:00-17:00 Europe/London
* NEW_YORK: 08:00-17:00 America/New_York

Both European and US hours active gives ``LONDON_NY_OVERLAP``; neither (nor Asia) gives
``OFF_HOURS``. Where Asia and London overlap the label is ``LONDON``. The label uses the bar OPEN
time, so a bar belongs to the session in which it starts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import polars as pl


class TradingSession(StrEnum):
    """Session labels."""

    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    OFF_HOURS = "OFF_HOURS"


_HOURS: Final = {
    "tokyo": ("Asia/Tokyo", 9 * 60, 18 * 60),
    "london": ("Europe/London", 8 * 60, 17 * 60),
    "new_york": ("America/New_York", 8 * 60, 17 * 60),
}


def _active(ts: pl.Series, zone: str, start: int, end: int) -> pl.Series:
    local = ts.dt.convert_time_zone(zone)
    minutes = local.dt.hour().cast(pl.Int32) * 60 + local.dt.minute().cast(pl.Int32)
    return (minutes >= start) & (minutes < end)


def session_features(timestamps: pl.Series) -> pl.DataFrame:
    """Return ``hour`` (UTC), ``day_of_week`` (Monday = 1) and ``trading_session``."""
    dtype = timestamps.dtype
    if not isinstance(dtype, pl.Datetime) or dtype.time_zone != "UTC":
        msg = f"timestamps must be Datetime in UTC, got {dtype}"
        raise ValueError(msg)
    if timestamps.null_count() > 0:
        msg = "timestamps must not contain null values"
        raise ValueError(msg)
    frame = pl.DataFrame(
        {
            "hour": timestamps.dt.hour().cast(pl.Int8),
            "day_of_week": timestamps.dt.weekday().cast(pl.Int8),
            "asia": _active(timestamps, *_HOURS["tokyo"]),
            "london": _active(timestamps, *_HOURS["london"]),
            "new_york": _active(timestamps, *_HOURS["new_york"]),
        }
    )
    label = (
        pl.when(pl.col("london") & pl.col("new_york"))
        .then(pl.lit(TradingSession.LONDON_NY_OVERLAP.value))
        .when(pl.col("london"))
        .then(pl.lit(TradingSession.LONDON.value))
        .when(pl.col("new_york"))
        .then(pl.lit(TradingSession.NEW_YORK.value))
        .when(pl.col("asia"))
        .then(pl.lit(TradingSession.ASIA.value))
        .otherwise(pl.lit(TradingSession.OFF_HOURS.value))
    )
    return frame.select("hour", "day_of_week", label.alias("trading_session"))
