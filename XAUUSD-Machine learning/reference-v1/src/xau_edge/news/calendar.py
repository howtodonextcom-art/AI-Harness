"""Economic calendar interface and the news guard.

No data source is bundled: reliable calendar data (CPI, NFP, FOMC, central-bank speeches) must be
supplied, for example as a CSV of ``time_utc,category,impact``. The guard refuses to answer for
times the calendar does not cover (``CalendarUnavailableError``) instead of silently reporting
"no news", which would be a fail-open risk check.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from pathlib import Path
from typing import Protocol


class EventImpact(IntEnum):
    """Impact levels, ordered."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class CalendarUnavailableError(RuntimeError):
    """Raised when asked about a time the calendar has no coverage for."""


@dataclass(frozen=True)
class NewsEvent:
    """One scheduled event."""

    time: datetime
    category: str
    impact: EventImpact


class EconomicCalendar(Protocol):
    """Anything that can list events in a time range and say what it covers."""

    coverage: tuple[datetime, datetime]

    def events_between(self, start: datetime, end: datetime) -> list[NewsEvent]:
        """Events with ``start <= time <= end``, ordered by time."""
        ...


class StaticCalendar:
    """In-memory calendar over a fixed list of events and a declared coverage range."""

    def __init__(self, events: Iterable[NewsEvent], *, coverage: tuple[datetime, datetime]) -> None:
        if coverage[0].tzinfo is None or coverage[1].tzinfo is None:
            msg = "coverage bounds must carry a timezone (UTC)"
            raise ValueError(msg)
        self._events = sorted(events, key=lambda e: e.time)
        self.coverage = coverage

    def events_between(self, start: datetime, end: datetime) -> list[NewsEvent]:
        """Events with ``start <= time <= end``, ordered by time."""
        return [e for e in self._events if start <= e.time <= end]


def load_calendar_csv(path: Path | str, *, coverage: tuple[datetime, datetime]) -> StaticCalendar:
    """Read ``time_utc,category,impact`` rows (``time_utc`` ends in ``Z``)."""
    events: list[NewsEvent] = []
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            raw = row["time_utc"].strip()
            if not raw.endswith("Z"):
                msg = f"time_utc must be UTC and end in Z, got {raw!r}"
                raise ValueError(msg)
            try:
                impact = EventImpact[row["impact"].strip().upper()]
            except KeyError:
                msg = f"unknown impact {row['impact']!r}; use low, medium or high"
                raise ValueError(msg) from None
            when = datetime.fromisoformat(raw[:-1]).replace(tzinfo=UTC)
            events.append(NewsEvent(when, row["category"].strip(), impact))
    return StaticCalendar(events, coverage=coverage)


def news_blocked(
    calendar: EconomicCalendar,
    at: datetime,
    *,
    before_minutes: int,
    after_minutes: int,
    min_impact: EventImpact = EventImpact.HIGH,
) -> bool:
    """True if ``at`` lies within the window around any event of at least ``min_impact``.

    The window is ``[event - before_minutes, event + after_minutes]``, inclusive.
    """
    if at.tzinfo is None:
        msg = "at must carry a timezone (UTC)"
        raise ValueError(msg)
    if before_minutes < 0 or after_minutes < 0:
        msg = "before_minutes and after_minutes must be >= 0"
        raise ValueError(msg)
    lo, hi = calendar.coverage
    window_start = at - timedelta(minutes=after_minutes)
    window_end = at + timedelta(minutes=before_minutes)
    if not (lo <= window_start and window_end <= hi):
        msg = (
            f"the window around {at.isoformat()} is not inside the calendar coverage "
            f"{lo.isoformat()}..{hi.isoformat()}"
        )
        raise CalendarUnavailableError(msg)
    return any(e.impact >= min_impact for e in calendar.events_between(window_start, window_end))


COVERAGE_PREFIX = "# coverage:"


def load_calendar_file(path: Path | str) -> StaticCalendar:
    """Load a calendar CSV whose FIRST line declares what it covers.

    The first line must read ``# coverage: 2026-01-01T00:00:00Z..2026-12-31T23:59:59Z``. A file
    without it is refused: a calendar that does not say which period it covers cannot be trusted
    to mean "no event" for a time it never saw (that would be a fail-open risk check).
    """
    text = Path(path).read_text(encoding="utf-8")
    first, _, rest = text.partition(chr(10))
    if not first.startswith(COVERAGE_PREFIX):
        msg = f"the first line must be '{COVERAGE_PREFIX} <start>Z..<end>Z'"
        raise ValueError(msg)
    try:
        raw_start, raw_end = first[len(COVERAGE_PREFIX) :].strip().split("..")
        if not (raw_start.endswith("Z") and raw_end.endswith("Z")):
            raise ValueError
        coverage = (
            datetime.fromisoformat(raw_start[:-1]).replace(tzinfo=UTC),
            datetime.fromisoformat(raw_end[:-1]).replace(tzinfo=UTC),
        )
    except ValueError:
        msg = "the coverage line must look like '# coverage: <start>Z..<end>Z' (ISO, UTC)"
        raise ValueError(msg) from None
    if coverage[0] >= coverage[1]:
        msg = "the coverage start must be before its end"
        raise ValueError(msg)
    tmp = Path(path).with_suffix(".body.tmp")
    try:
        tmp.write_text(rest, encoding="utf-8")
        return load_calendar_csv(tmp, coverage=coverage)
    finally:
        tmp.unlink(missing_ok=True)
