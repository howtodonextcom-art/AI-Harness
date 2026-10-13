"""Closed-bar discipline on plain NumPy arrays (no polars in the core).

A bar is usable only once it has CLOSED: ``available_at = open + timeframe length``.
``MultiFrames.as_of`` is the single place that enforces it: at 10:37 the H1 bar 10:00-11:00 is
still forming, so a decision uses the last closed H1 bar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
from numpy.typing import NDArray

from xau_edge_v2.domain.contract import Timeframe

ORDER: tuple[Timeframe, ...] = (
    Timeframe.M1,
    Timeframe.M5,
    Timeframe.M15,
    Timeframe.M30,
    Timeframe.H1,
    Timeframe.H4,
)
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_US = 1_000_000


def to_micros(at: datetime) -> int:
    """Microseconds since the epoch (exact integer arithmetic)."""
    delta = at.astimezone(UTC) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * _US + delta.microseconds


def from_micros(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=int(value))


@dataclass(frozen=True)
class Frame:
    """One timeframe's closed bars, strictly increasing in time (arrays of equal length)."""

    timeframe: Timeframe
    open_us: NDArray[np.int64]
    open: NDArray[np.float64]
    high: NDArray[np.float64]
    low: NDArray[np.float64]
    close: NDArray[np.float64]
    tick_volume: NDArray[np.float64]
    spread: NDArray[np.float64]
    real_volume: NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        n = self.open_us.size
        arrays = (self.open, self.high, self.low, self.close, self.tick_volume, self.spread)
        if any(a.size != n for a in arrays):
            msg = "frame arrays must have the same length"
            raise ValueError(msg)
        if n > 1 and not bool(np.all(np.diff(self.open_us) > 0)):
            msg = "frame timestamps must be strictly increasing"
            raise ValueError(msg)

    @property
    def height(self) -> int:
        return int(self.open_us.size)

    @property
    def available_us(self) -> NDArray[np.int64]:
        return self.open_us + np.int64(self.timeframe.seconds * _US)

    def head(self, rows: int) -> Frame:
        s = slice(0, rows)
        return Frame(
            self.timeframe,
            self.open_us[s],
            self.open[s],
            self.high[s],
            self.low[s],
            self.close[s],
            self.tick_volume[s],
            self.spread[s],
            None if self.real_volume is None else self.real_volume[s],
        )

    def tail(self, rows: int) -> Frame:
        s = slice(max(0, self.height - rows), None)
        return Frame(
            self.timeframe,
            self.open_us[s],
            self.open[s],
            self.high[s],
            self.low[s],
            self.close[s],
            self.tick_volume[s],
            self.spread[s],
            None if self.real_volume is None else self.real_volume[s],
        )


@dataclass(frozen=True)
class MultiFrames:
    """Frames per timeframe; an absent timeframe is simply missing (never invented)."""

    frames: dict[Timeframe, Frame]
    _avail: dict[Timeframe, NDArray[np.int64]] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def as_of(self, timeframe: Timeframe, at: datetime) -> Frame | None:
        """Bars of ``timeframe`` that had closed at ``at`` (``available_at <= at``)."""
        frame = self.frames.get(timeframe)
        if frame is None:
            return None
        if timeframe not in self._avail:
            self._avail[timeframe] = frame.available_us
        rows = int(np.searchsorted(self._avail[timeframe], to_micros(at), side="right"))
        return frame.head(rows)

    def available(self) -> tuple[Timeframe, ...]:
        return tuple(tf for tf in ORDER if tf in self.frames)
