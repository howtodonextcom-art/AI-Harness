"""Holiday / early-close closure windows inferred from the broker's own absence of bars.

The weekly template (weekend + daily break) lives in ``MarketCalendar``. What it cannot know are
holidays and early closes. They are found here by looking for stretches where the template says
the market is OPEN but the broker produced no native bars, and are then split into:

* ``HOLIDAY`` / ``EARLY_CLOSE``: the stretch touches a recognised holiday date (US federal
  holidays, Good Friday, Christmas, New Year; rule based, never a fixed list of years). These
  become closure windows, so resampling stops reporting them as missing data;
* ``UNCLASSIFIED``: any other absence. It is NEVER turned into a closure (that would hide real
  data loss); it stays a data gap with state UNKNOWN until someone explains it.

A real missing bar on a holiday date cannot be told apart from the holiday itself with bars alone,
so the date rule is deliberately narrow: the absence must start at or after the holiday's own date
and end by the next regular reopening.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators.market_calendar import ClosureWindow, MarketCalendar

Reason = Literal["HOLIDAY", "EARLY_CLOSE", "UNCLASSIFIED"]


def easter(year: int) -> date:
    """Gregorian Easter Sunday (anonymous algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> list[date]:
    """The day itself plus the weekday on which a weekend holiday is observed."""
    if day.weekday() == 5:
        return [day, day - timedelta(days=1)]
    if day.weekday() == 6:
        return [day, day + timedelta(days=1)]
    return [day]


def holiday_dates(year: int) -> set[date]:
    """Dates around which a US-dollar gold CFD commonly trims or skips its session."""
    days: set[date] = set()
    for fixed in (date(year, 1, 1), date(year, 6, 19), date(year, 7, 4), date(year, 12, 25)):
        days.update(_observed(fixed))
    days.add(date(year, 12, 31))
    days.update(
        {
            _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
            _nth_weekday(year, 2, 0, 3),  # Presidents' Day
            easter(year) - timedelta(days=2),  # Good Friday
            _last_weekday(year, 5, 0),  # Memorial Day
            _nth_weekday(year, 9, 0, 1),  # Labor Day
            _nth_weekday(year, 11, 3, 4),  # Thanksgiving
            _nth_weekday(year, 11, 3, 4) + timedelta(days=1),  # day after Thanksgiving
            date(year, 12, 24),
            date(year, 12, 26),
        }
    )
    return days


@dataclass(frozen=True)
class Absence:
    """An open-session stretch with no native bars."""

    start: datetime
    end: datetime
    reason: Reason
    open_slots: int


def _regular_open_slots(
    calendar: MarketCalendar, start: datetime, end: datetime, step_minutes: int
) -> list[datetime]:
    slots = pl.datetime_range(start, end, interval=f"{step_minutes}m", closed="left", eager=True)
    if slots.len() == 0:
        return []
    frame = pl.DataFrame({"t": slots.dt.replace_time_zone("UTC")})
    open_mask = frame.select((~calendar.closed_span_expr(pl.col("t"), step_minutes)).alias("o"))[
        "o"
    ]
    return frame.filter(open_mask)["t"].to_list()


def find_absences(
    bars: pl.DataFrame,
    timeframe: Timeframe,
    calendar: MarketCalendar,
    *,
    ny: str = "America/New_York",
) -> list[Absence]:
    """Stretches the weekly template calls OPEN where the broker has no bars, classified."""
    ts = bars["timestamp"].sort()
    if ts.len() < 2:
        return []
    step = timeframe.minutes
    frame = pl.DataFrame({"prev": ts.shift(1), "next": ts}).drop_nulls()
    gaps = frame.filter(pl.col("next") - pl.col("prev") > pl.duration(minutes=step))
    zone = ZoneInfo(ny)
    out: list[Absence] = []
    for prev, nxt in gaps.iter_rows():
        start, end = prev + timedelta(minutes=step), nxt
        open_slots = _regular_open_slots(calendar, start, end, step)
        if not open_slots:
            continue  # fully explained by the weekly template
        first_open, last_open = open_slots[0], open_slots[-1] + timedelta(minutes=step)
        local_days = {
            first_open.astimezone(zone).date(),
            (last_open - timedelta(minutes=1)).astimezone(zone).date(),
        }
        holidays = holiday_dates(min(local_days).year) | holiday_dates(max(local_days).year)
        touched = local_days & holidays
        reason: Reason = "UNCLASSIFIED"
        if touched:
            local_first = first_open.astimezone(zone)
            starts_midday = (local_first.hour, local_first.minute) > (0, 0) and (
                local_first.date() in holidays
            )
            reason = (
                "EARLY_CLOSE" if starts_midday and len(open_slots) < 24 * 60 // step else "HOLIDAY"
            )
        out.append(Absence(first_open, last_open, reason, len(open_slots)))
    return out


def closures_from(absences: list[Absence]) -> tuple[ClosureWindow, ...]:
    """Only explained absences become closure windows."""
    return tuple(
        ClosureWindow(start=a.start.astimezone(UTC), end=a.end.astimezone(UTC), reason=a.reason)
        for a in absences
        if a.reason != "UNCLASSIFIED"
    )


def dump_closures(path: Path, windows: tuple[ClosureWindow, ...], header: str) -> None:
    rows: list[dict[str, Any]] = [
        {"start": w.start.isoformat(), "end": w.end.isoformat(), "reason": w.reason}
        for w in sorted(windows, key=lambda w: w.start)
    ]
    path.write_text(
        f"{header}\n" + yaml.safe_dump({"closures": rows}, sort_keys=False), encoding="utf-8"
    )


def load_closures(path: Path) -> tuple[ClosureWindow, ...]:
    """Closure windows from the exceptions file (none when it does not exist)."""
    if not path.exists():
        return ()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return tuple(ClosureWindow.model_validate(row) for row in raw.get("closures", []))
