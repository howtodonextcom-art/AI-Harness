"""Closed-bar discipline and deterministic multi-timeframe frames (trading core sections 44, 45).

A bar is usable only once it has CLOSED: ``available_at = open + timeframe length``. At 10:37 the
H1 bar 10:00-11:00 is still forming, so the decision uses the last closed H1 bar (09:00-10:00).
``closed_as_of`` is the single place that enforces this; everything downstream goes through it.

Coarser timeframes can be derived deterministically from M1 (``derive_from_m1``, the existing
broker-clock aware resampler that drops incomplete buckets), and ``compare_with_broker`` measures
how well that derivation reproduces the broker's own bars so the aggregation rule is verified,
never assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import numpy as np
import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.resampling import resample_bars
from xau_edge.market_data.validators.market_calendar import MarketCalendar

ORDER = (Timeframe.M1, Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4)
DERIVED = (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1, Timeframe.H4)
REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close", "tick_volume", "spread")


class FrameError(ValueError):
    """The bars are unusable (missing columns, unsorted, naive time stamps)."""


def with_available_at(df: pl.DataFrame, timeframe: Timeframe) -> pl.DataFrame:
    """Add ``available_at`` (the bar's close time) and validate the frame's basic shape."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        msg = f"missing column(s): {', '.join(missing)}"
        raise FrameError(msg)
    dtype = df.schema["timestamp"]
    if not isinstance(dtype, pl.Datetime) or dtype.time_zone != "UTC":
        msg = "timestamp must be a UTC datetime"
        raise FrameError(msg)
    if df.height > 1 and not bool(
        (df["timestamp"].diff().drop_nulls().dt.total_microseconds() > 0).all()
    ):
        msg = "timestamps must be strictly increasing"
        raise FrameError(msg)
    return df.with_columns(
        (pl.col("timestamp") + pl.duration(minutes=timeframe.minutes)).alias("available_at")
    )


def closed_as_of(df: pl.DataFrame, at: datetime) -> pl.DataFrame:
    """Only the bars that had closed at ``at`` (``available_at <= at``)."""
    if "available_at" not in df.columns:
        msg = "frame has no available_at column; call with_available_at first"
        raise FrameError(msg)
    return df.filter(pl.col("available_at") <= at)


def forming_bar_open(timeframe: Timeframe, at: datetime) -> datetime:
    """Open time of the bar of ``timeframe`` that is still forming at ``at`` (UTC grid)."""
    epoch_minutes = int(at.timestamp() // 60)
    start = epoch_minutes - epoch_minutes % timeframe.minutes
    return datetime.fromtimestamp(start * 60, tz=at.tzinfo)


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _micros(at: datetime) -> int:
    """Microseconds since the epoch (exact integer arithmetic, no float rounding)."""
    delta = at.astimezone(UTC) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


@dataclass(frozen=True)
class MultiTfBars:
    """Frames per timeframe, each with ``available_at``; absent timeframes are simply missing.

    ``as_of`` is called hundreds of times per decision (the setup lifecycle replays the recent M5
    closes), so each frame's ``available_at`` is indexed once as an int64 array and the closed
    prefix is a zero-copy slice found with a binary search. The result is identical to
    ``closed_as_of`` (the frames are strictly increasing); a frame that is not sorted falls back
    to the filter.
    """

    frames: dict[Timeframe, pl.DataFrame]
    _index: dict[Timeframe, np.ndarray | None] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def _positions(self, timeframe: Timeframe) -> np.ndarray | None:
        if timeframe not in self._index:
            frame = self.frames[timeframe]
            if "available_at" not in frame.columns:
                self._index[timeframe] = None
            else:
                arr = frame["available_at"].dt.epoch("us").to_numpy()
                self._index[timeframe] = arr if bool(np.all(np.diff(arr) > 0)) else None
        return self._index[timeframe]

    def closed(self, timeframe: Timeframe, at: datetime) -> pl.DataFrame:
        """``closed_as_of`` for one of this object's frames, via the index."""
        frame = self.frames[timeframe]
        positions = self._positions(timeframe)
        if positions is None:
            return closed_as_of(frame, at)
        return frame.head(int(np.searchsorted(positions, _micros(at), side="right")))

    def as_of(self, timeframe: Timeframe, at: datetime) -> pl.DataFrame | None:
        """Closed bars of one timeframe at ``at`` (None when that timeframe is not available)."""
        if timeframe not in self.frames:
            return None
        return self.closed(timeframe, at)

    def available(self) -> tuple[Timeframe, ...]:
        return tuple(tf for tf in ORDER if tf in self.frames)

    def truncated(self, at: datetime) -> MultiTfBars:
        """The same bars with everything not yet closed at ``at`` removed (live-style view)."""
        return MultiTfBars({tf: self.closed(tf, at) for tf in self.frames})


def from_frames(frames: dict[Timeframe, pl.DataFrame]) -> MultiTfBars:
    """Wrap raw frames (as stored or fetched) into ``MultiTfBars``."""
    return MultiTfBars({tf: with_available_at(df, tf) for tf, df in frames.items()})


def derive_from_m1(
    m1: pl.DataFrame, *, clock: BrokerClock, calendar: MarketCalendar
) -> dict[Timeframe, pl.DataFrame]:
    """M5, M15, M30, H1 and H4 from M1 with the broker-aligned resampler (complete buckets only)."""
    out: dict[Timeframe, pl.DataFrame] = {Timeframe.M1: m1}
    for target in DERIVED:
        result = resample_bars(m1, Timeframe.M1, target, clock=clock, calendar=calendar)
        out[target] = result.frame
    return out


@dataclass(frozen=True)
class ResampleComparison:
    """How well a derived frame reproduces the broker's own bars over their common bars."""

    timeframe: Timeframe
    common_bars: int
    ohlc_mismatches: int
    volume_mismatches: int
    spread_mismatches: int
    max_abs_price_diff: float

    @property
    def exact(self) -> bool:
        return self.common_bars > 0 and self.ohlc_mismatches == 0


def compare_with_broker(
    derived: pl.DataFrame, broker: pl.DataFrame, timeframe: Timeframe, *, tol: float = 1e-9
) -> ResampleComparison:
    """Join on the bar open time and count disagreements (prices, tick volume, spread)."""
    joined = derived.join(broker, on="timestamp", how="inner", suffix="_b")
    if joined.height == 0:
        return ResampleComparison(timeframe, 0, 0, 0, 0, 0.0)
    price_cols = ("open", "high", "low", "close")
    diffs = [(pl.col(c) - pl.col(f"{c}_b")).abs() for c in price_cols]
    worst = pl.max_horizontal(*diffs)
    frame = joined.with_columns(worst.alias("_w"))
    return ResampleComparison(
        timeframe=timeframe,
        common_bars=joined.height,
        ohlc_mismatches=int((frame["_w"] > tol).sum()),
        volume_mismatches=int((joined["tick_volume"] != joined["tick_volume_b"]).sum()),
        spread_mismatches=int((joined["spread"] != joined["spread_b"]).sum()),
        max_abs_price_diff=float(frame["_w"].to_numpy().max()),
    )
