"""Canonical market-data schema: bars, ticks, quotes, volume type, session state, feed health.

Every consumer (research, backtest, signal engine, paper, demo, API, dashboard) reads this one
vocabulary. Missing data stays explicit (``None``), tick volume is never presented as real volume,
and a bar always says whether it is CLOSED: research, backtest and signals default to closed bars
only, and only the dashboard may show a forming bar (clearly marked).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

import polars as pl
from pydantic import BaseModel, ConfigDict, Field

from xau_edge.domain.timeframe import Timeframe

REAL_VOLUME_POLICY = (
    "UNVERIFIED_LEGACY_REAL_VOLUME: real_volume is non-zero only in an imported H1/H4 era "
    "(2012-03-28..2018-02-09) with unproven meaning; it is never displayed or used. "
    "tick_volume is the only volume."
)


class VolumeType(StrEnum):
    """What a feed's volume fields mean (decided from the data, never assumed)."""

    TICK_VOLUME = "TICK_VOLUME"
    REAL_VOLUME = "REAL_VOLUME"
    BOTH = "BOTH"
    UNKNOWN = "UNKNOWN"


class MarketStatus(StrEnum):
    """Whether the market is expected to quote now (a closed market is not a data failure)."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    ROLLOVER = "ROLLOVER"
    MAINTENANCE = "MAINTENANCE"
    UNKNOWN = "UNKNOWN"


class FeedHealth(StrEnum):
    """Overall trust in the feed."""

    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    DISCONNECTED = "DISCONNECTED"
    UNKNOWN = "UNKNOWN"


CANONICAL_BAR_COLUMNS = (
    "canonical_symbol",
    "broker_symbol",
    "timeframe",
    "timestamp_open",
    "timestamp_close",
    "available_at",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "real_volume",
    "spread_points",
    "is_closed",
    "volume_type",
    "source",
    "broker_server",
    "dataset_id",
)


TICK_COLUMNS = ("timestamp_msc", "timestamp", "bid", "ask", "last", "volume", "flags")


def empty_ticks() -> pl.DataFrame:
    """A tick frame with the canonical schema and no rows."""
    return pl.DataFrame(
        schema={
            "timestamp_msc": pl.Int64,
            "timestamp": pl.Datetime("ms", "UTC"),
            "bid": pl.Float64,
            "ask": pl.Float64,
            "last": pl.Float64,
            "volume": pl.Int64,
            "flags": pl.Int64,
        }
    )


def conform_ticks(frame: pl.DataFrame) -> pl.DataFrame:
    """Cast a tick frame to the canonical schema (millisecond UTC timestamp, fixed dtypes)."""
    if frame.height == 0:
        return empty_ticks()
    return frame.select(TICK_COLUMNS).cast(empty_ticks().schema)


class Tick(BaseModel):
    """One tick; only the fields the feed really provided are populated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    broker_symbol: str
    timestamp: datetime
    timestamp_msc: int
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    volume_real: float | None = None
    flags: int | None = None
    spread: float | None = None
    source: str = "mt5"


class Quote(BaseModel):
    """The latest quote with its age: a stale quote is never shown as current."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical_symbol: str
    broker_symbol: str
    bid: float | None
    ask: float | None
    mid: float | None
    last: float | None
    spread_price: float | None
    spread_points: float | None
    timestamp: datetime | None
    age_seconds: float | None
    stale: bool
    market_status: MarketStatus
    source: str = "mt5"
    note: str = Field(default="")


def canonicalise(
    bars: pl.DataFrame,
    timeframe: Timeframe,
    *,
    canonical_symbol: str,
    broker_symbol: str,
    source: str,
    broker_server: str | None,
    dataset_id: str | None,
    now: datetime,
    volume_type: VolumeType,
) -> pl.DataFrame:
    """Canonical frame from the stored/fetched bar frame (``timestamp`` = UTC open time).

    ``is_closed`` is decided against ``now``: a bar is closed once ``now >= open + length``.
    """
    length = pl.duration(minutes=timeframe.minutes)
    real = pl.col("real_volume") if "real_volume" in bars.columns else pl.lit(None, pl.Int64)
    return bars.select(
        pl.lit(canonical_symbol).alias("canonical_symbol"),
        pl.lit(broker_symbol).alias("broker_symbol"),
        pl.lit(timeframe.value).alias("timeframe"),
        pl.col("timestamp").alias("timestamp_open"),
        (pl.col("timestamp") + length).alias("timestamp_close"),
        (pl.col("timestamp") + length).alias("available_at"),
        "open",
        "high",
        "low",
        "close",
        "tick_volume",
        real.alias("real_volume"),
        pl.col("spread").alias("spread_points"),
        ((pl.col("timestamp") + length) <= now).alias("is_closed"),
        pl.lit(volume_type.value).alias("volume_type"),
        pl.lit(source).alias("source"),
        pl.lit(broker_server, dtype=pl.String).alias("broker_server"),
        pl.lit(dataset_id, dtype=pl.String).alias("dataset_id"),
    )


def volume_type_of(tick_volume: object, real_volume: object | None) -> VolumeType:
    """What volume fields a frame carries: TICK_VOLUME, BOTH (a non-zero real volume exists) or
    UNKNOWN. BOTH describes AVAILABILITY only: the meaning of ``real_volume`` is not verified and
    the dashboard still labels the bars' volume as tick volume."""
    import numpy as np  # noqa: PLC0415 - keep the domain module light

    ticks = np.asarray(tick_volume, dtype=np.float64)
    if ticks.size == 0 or not np.isfinite(ticks).all() or (ticks <= 0).all():
        return VolumeType.UNKNOWN
    if real_volume is None:
        return VolumeType.TICK_VOLUME
    real = np.asarray(real_volume, dtype=np.float64)
    real = real[np.isfinite(real)]
    return (
        VolumeType.BOTH if real.size and float(np.abs(real).sum()) > 0 else VolumeType.TICK_VOLUME
    )


def closed_only(canonical: pl.DataFrame) -> pl.DataFrame:
    """The default view for every scientific consumer: forming bars removed."""
    return canonical.filter(pl.col("is_closed"))


def feed_age_limit(timeframe: Timeframe) -> timedelta:
    """How old the last closed bar of ``timeframe`` may be (during open hours) before STALE."""
    return timedelta(minutes=max(3 * timeframe.minutes, 5))
