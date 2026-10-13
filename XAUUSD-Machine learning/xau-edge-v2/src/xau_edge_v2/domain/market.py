"""Pure market-time rules: broker clock, session calendar, market status (no I/O, no polars).

Rewritten from the behaviour of V1 (never imported from it). Parity with V1 is proven by
``scripts/parity/`` on tens of thousands of instants, including every DST boundary.

* The broker server clock is "New York wall clock + N hours" (FTMO demo: NY+7), so the 17:00 New
  York rollover is server midnight. It follows US DST, so it is NOT one IANA zone.
* The session calendar is a weekly template in New York time (closes Friday 16:50, reopens Sunday
  18:05), a daily break of the same hours, and explicit holiday / early-close windows.
"""

from __future__ import annotations

import bisect
import re
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator

NEW_YORK = "America/New_York"
_NY_TOKEN = re.compile(r"^NY([+-]\d{1,2})$", re.IGNORECASE)
_MAX_NY_OFFSET_HOURS = 14
_SATURDAY, _FRIDAY, _SUNDAY = 6, 5, 7


class MarketStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"  # weekend, holiday or early-close window
    ROLLOVER = "ROLLOVER"  # the daily break
    UNKNOWN = "UNKNOWN"


class BrokerClockError(ValueError):
    """Unparseable or invalid broker clock, or a server time that cannot be mapped to UTC."""


class BrokerClock(BaseModel):
    """Maps a naive broker wall-clock time to and from true UTC (exactly one kind per clock)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    iana: str | None = None
    ny_offset_hours: int | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> BrokerClock:
        if (self.iana is None) == (self.ny_offset_hours is None):
            msg = "set exactly one of iana / ny_offset_hours"
            raise ValueError(msg)
        if self.ny_offset_hours is not None and abs(self.ny_offset_hours) > _MAX_NY_OFFSET_HOURS:
            msg = f"NY offset {self.ny_offset_hours}h out of range"
            raise ValueError(msg)
        if self.iana is not None:
            try:
                ZoneInfo(self.iana)
            except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
                msg = f"unknown IANA zone {self.iana!r}"
                raise ValueError(msg) from exc
        return self

    @classmethod
    def parse(cls, token: str) -> BrokerClock:
        """``"NY+7"`` / ``"NY-2"`` or an IANA name such as ``"Europe/Athens"``."""
        text = token.strip()
        match = _NY_TOKEN.match(text)
        if not text or (text.upper().startswith("NY") and not match):
            msg = f"invalid broker clock {token!r}: expected 'NY+<hours>' or an IANA zone"
            raise BrokerClockError(msg)
        try:
            return cls(ny_offset_hours=int(match.group(1))) if match else cls(iana=text)
        except ValueError as exc:
            raise BrokerClockError(f"invalid broker clock {token!r}: {exc}") from exc

    @property
    def token(self) -> str:
        return self.iana if self.iana is not None else f"NY{self.ny_offset_hours:+d}"

    def to_server_wall(self, utc: datetime) -> datetime:
        """A UTC instant -> naive server wall clock."""
        _require_aware(utc)
        if self.iana is not None:
            return utc.astimezone(ZoneInfo(self.iana)).replace(tzinfo=None)
        ny = utc.astimezone(ZoneInfo(NEW_YORK)).replace(tzinfo=None)
        return ny + timedelta(hours=self.ny_offset_hours or 0)

    def server_to_utc(self, naive: datetime, *, strict: bool = True) -> datetime | None:
        """Naive server wall clock -> aware UTC.

        Ambiguous or non-existent local times (DST fold/gap) raise when ``strict``, else ``None``.
        """
        if naive.tzinfo is not None:
            msg = "server time must be naive"
            raise BrokerClockError(msg)
        if self.iana is not None:
            zone, local = ZoneInfo(self.iana), naive
        else:
            zone, local = ZoneInfo(NEW_YORK), naive - timedelta(hours=self.ny_offset_hours or 0)
        first = local.replace(tzinfo=zone, fold=0)
        second = local.replace(tzinfo=zone, fold=1)
        gap = first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local
        ambiguous = first.utcoffset() != second.utcoffset()
        if gap or ambiguous:
            if strict:
                kind = "non-existent" if gap else "ambiguous"
                msg = f"{kind} server time {naive.isoformat()} for clock {self.token}"
                raise BrokerClockError(msg)
            return None
        return first.astimezone(UTC)


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None:
        msg = "expected a timezone-aware datetime"
        raise ValueError(msg)


class ClosureWindow(BaseModel):
    """Holiday or early close in true UTC, ``[start, end)``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: datetime
    end: datetime
    reason: Literal["HOLIDAY", "EARLY_CLOSE"]

    @model_validator(mode="after")
    def _ordered(self) -> ClosureWindow:
        if self.start.tzinfo is None or self.end.tzinfo is None or self.end <= self.start:
            msg = "closure windows need aware, increasing start/end"
            raise ValueError(msg)
        return self


class CalendarConfig(BaseModel):
    """Weekly template (minutes-of-day in ``timezone``) + daily break + closures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timezone: str = NEW_YORK
    weekend_close_minute: int = Field(ge=0, lt=24 * 60)
    weekend_open_minute: int = Field(ge=0, lt=24 * 60)
    daily_break_start_minute: int | None = Field(default=None, ge=0, lt=24 * 60)
    daily_break_end_minute: int | None = Field(default=None, ge=0, lt=24 * 60)
    closures: tuple[ClosureWindow, ...] = ()

    @model_validator(mode="after")
    def _break_complete(self) -> CalendarConfig:
        if (self.daily_break_start_minute is None) != (self.daily_break_end_minute is None):
            msg = "a daily break needs both a start and an end minute"
            raise ValueError(msg)
        return self


def _micros(value: datetime) -> int:
    delta = value.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


class MarketCalendar:
    """Is the market closed at an instant, and why. O(log n) in the number of closures."""

    def __init__(self, config: CalendarConfig) -> None:
        self.config = config
        self._zone = ZoneInfo(config.timezone)
        merged: list[list[int]] = []
        for start, end in sorted((_micros(w.start), _micros(w.end)) for w in config.closures):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        self._starts = [m[0] for m in merged]
        self._ends = [m[1] for m in merged]

    def _in_closure(self, ts: datetime) -> bool:
        t = _micros(ts)
        i = bisect.bisect_right(self._starts, t) - 1
        return i >= 0 and t < self._ends[i]

    def _weekend(self, weekday: int, minute: int) -> bool:
        c = self.config
        return (
            weekday == _SATURDAY
            or (weekday == _FRIDAY and minute >= c.weekend_close_minute)
            or (weekday == _SUNDAY and minute < c.weekend_open_minute)
        )

    def _break(self, minute: int) -> bool:
        c = self.config
        start, end = c.daily_break_start_minute, c.daily_break_end_minute
        if start is None or end is None:
            return False
        return (start <= minute < end) if start < end else (minute >= start or minute < end)

    def is_closed(self, ts: datetime) -> bool:
        _require_aware(ts)
        local = ts.astimezone(self._zone)
        minute = local.hour * 60 + local.minute
        return (
            self._weekend(local.isoweekday(), minute) or self._break(minute) or self._in_closure(ts)
        )

    def status(self, now: datetime) -> MarketStatus:
        if now.tzinfo is None:
            return MarketStatus.UNKNOWN
        if not self.is_closed(now):
            return MarketStatus.OPEN
        if self._in_closure(now):
            return MarketStatus.CLOSED
        local = now.astimezone(self._zone)
        weekend = self._weekend(local.isoweekday(), local.hour * 60 + local.minute)
        return MarketStatus.CLOSED if weekend else MarketStatus.ROLLOVER

    def next_open(self, now: datetime, *, horizon_days: int = 10) -> datetime | None:
        """First open minute at or after ``now`` (``None`` beyond ``horizon_days``)."""
        cursor = now.astimezone(UTC).replace(second=0, microsecond=0)
        if cursor < now:
            cursor += timedelta(minutes=1)
        for _ in range(horizon_days * 24 * 60):
            if not self.is_closed(cursor):
                return cursor
            cursor += timedelta(minutes=1)
        return None

    def open_seconds_between(self, start: datetime, end: datetime) -> float:
        """Seconds of OPEN market in ``[start, end)`` (minute resolution): calendar-aware age."""
        if end <= start:
            return 0.0
        cursor = start.astimezone(UTC).replace(second=0, microsecond=0)
        total = 0.0
        while cursor < end:
            nxt = cursor + timedelta(minutes=1)
            if not self.is_closed(cursor):
                lo, hi = max(cursor, start), min(nxt, end)
                total += max(0.0, (hi - lo).total_seconds())
            cursor = nxt
        return total
