"""Per-year broker-clock and data-quality forensics on TIMESTAMPS ONLY (roadmap P0).

These functions take a column of bar-open timestamps (UTC, as stored) and nothing else. They never
see a price, so they cannot create outcome evidence: the output is Class D (descriptive).

The test of a clock is the weekly session boundary. The market closes at 17:00 New York on Friday
and opens 17:00 New York on Sunday. If the stored UTC timestamps were produced with the wrong server
offset in some years, the New York minute of the last bar before each weekend gap is not constant,
and the daily-break hour in New York time shifts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

NEW_YORK = "America/New_York"
WEEKEND_GAP = timedelta(hours=24)
NY_ROLLOVER_MINUTE = 17 * 60
MIN_WEEKS = 30
MIN_MISMATCH_WEEKS = 2
_NY = ZoneInfo(NEW_YORK)
_ATHENS = ZoneInfo("Europe/Athens")
FRIDAY = 5
SUNDAY = 7
CERTIFY_FRACTION = 0.90


@dataclass(frozen=True)
class YearClock:
    """What one calendar year of timestamps says about the clock."""

    year: int
    bars: int
    weeks: int
    close_mode_minute: int | None
    close_fraction: float
    open_mode_minute: int | None
    open_fraction: float
    daily_break_hours_ny: tuple[int, ...]
    mismatch_weeks: int
    ny_anchored_mismatch_fraction: float | None
    certified: bool
    reason: str


def _ny_minutes(ts: pl.Series, bar_minutes: int, *, at_close: bool) -> list[int]:
    shifted = ts + timedelta(minutes=bar_minutes) if at_close else ts
    ny = shifted.dt.convert_time_zone(NEW_YORK)
    return (ny.dt.hour().cast(pl.Int32) * 60 + ny.dt.minute().cast(pl.Int32)).to_list()


def _modal(values: list[int]) -> tuple[int | None, float]:
    if not values:
        return None, 0.0
    counts: dict[int, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    mode, count = max(counts.items(), key=lambda kv: (kv[1], -kv[0]))
    return mode, count / len(values)


def weekend_gaps(ts: pl.Series) -> tuple[list[int], list[int]]:
    """Indices of the last bar before, and first bar after, each WEEKEND gap.

    A weekend gap is longer than 24 hours, starts on a New York Friday and ends on a New York
    Sunday; holiday gaps in mid-week or on other days are not weekends and are excluded.
    """
    ny_weekday = ts.dt.convert_time_zone(NEW_YORK).dt.weekday().to_list()
    gap = (ts.diff() > WEEKEND_GAP).fill_null(False).to_list()
    before, after = [], []
    for i, flag in enumerate(gap):
        if flag and ny_weekday[i - 1] == FRIDAY and ny_weekday[i] == SUNDAY:
            before.append(i - 1)
            after.append(i)
    return before, after


def year_clock(year: int, ts: pl.Series, bar_minutes: int = 60) -> YearClock:
    """Evaluate one year (``ts`` sorted, UTC, only that year's bars)."""
    n = ts.len()
    before, after = weekend_gaps(ts)
    if len(before) < MIN_WEEKS:
        return YearClock(
            year, n, len(before), None, 0.0, None, 0.0, (), 0, None, False, "too few weeks"
        )
    close_min = _ny_minutes(ts, bar_minutes, at_close=True)
    open_min = _ny_minutes(ts, bar_minutes, at_close=False)
    closes = [close_min[i] for i in before]
    opens = [open_min[i] for i in after]
    close_mode, close_frac = _modal(closes)
    open_mode, open_frac = _modal(opens)
    ny_hours = ts.dt.convert_time_zone(NEW_YORK)
    weekday = ny_hours.dt.weekday().cast(pl.Int32)
    hour = ny_hours.dt.hour().cast(pl.Int32)
    frame = pl.DataFrame({"h": hour, "w": weekday}).filter(pl.col("w") <= 4)
    by_hour = dict(frame.group_by("h").len().iter_rows())
    counts = [by_hour.get(h, 0) for h in range(24)]
    ordered = sorted(counts)
    median = ordered[len(ordered) // 2]
    quiet = tuple(h for h, c in enumerate(counts) if c < 0.5 * median)
    mismatch = _mismatch_weeks(ts, before)
    held = [i for i in mismatch if close_min[i] == close_mode]
    ny_fraction = len(held) / len(mismatch) if mismatch else None
    anchored = close_mode == NY_ROLLOVER_MINUTE
    if not anchored:
        verdict, reason = False, "weekly close not at 17:00 New York"
    elif ny_fraction is None or len(mismatch) < MIN_MISMATCH_WEEKS:
        verdict, reason = False, "no US/EU daylight-saving mismatch weeks to test the anchor"
    elif ny_fraction < CERTIFY_FRACTION:
        verdict = False
        reason = "weekly close moves with European daylight saving (not New York anchored)"
    else:
        verdict, reason = True, "weekly close held at 17:00 New York through the DST mismatch weeks"
    return YearClock(
        year,
        n,
        len(before),
        close_mode,
        close_frac,
        open_mode,
        open_frac,
        quiet,
        len(mismatch),
        ny_fraction,
        verdict,
        reason,
    )


def _mismatch_weeks(ts: pl.Series, before: list[int]) -> list[int]:
    """Gap indices (last bar before the weekend) in weeks where New York and Athens DST differ."""
    stamps = ts.to_list()
    diffs = []
    for i in before:
        t = stamps[i]
        ny = t.astimezone(_NY).utcoffset()
        eu = t.astimezone(_ATHENS).utcoffset()
        diffs.append(None if ny is None or eu is None else (eu - ny).total_seconds() / 3600)
    if not diffs:
        return []
    typical = max(set(diffs), key=diffs.count)
    return [i for i, d in zip(before, diffs, strict=True) if d != typical]


def clock_by_year(ts: pl.Series, bar_minutes: int = 60) -> list[YearClock]:
    """Run ``year_clock`` for every calendar year present."""
    ordered = ts.sort()
    years = ordered.dt.year()
    return [
        year_clock(int(y), ordered.filter(years == y), bar_minutes)
        for y in sorted(years.unique().to_list())
    ]


@dataclass(frozen=True)
class YearQuality:
    """Timestamp-only data quality for one year against the calendar."""

    year: int
    bars: int
    expected_open_slots: int
    bars_in_open_time: int
    bars_inside_closure: int
    missing_fraction: float
    gaps_over_limit: int


def year_quality(
    year: int,
    ts: pl.Series,
    closed: Callable[[pl.Series], pl.Series],
    *,
    bar_minutes: int = 60,
    max_gap_hours: int = 28,
) -> YearQuality:
    """Missing fraction against the calendar's open slots, plus bars sitting inside closures.

    ``closed`` maps a UTC datetime series to a boolean series (True = the market is closed), built
    from the broker profile by the caller. The slot grid is every ``bar_minutes`` of the year.
    """
    if ts.len() == 0:
        return YearQuality(year, 0, 0, 0, 0, 1.0, 0)
    start = datetime(year, 1, 1, tzinfo=UTC)
    end = datetime(year + 1, 1, 1, tzinfo=UTC) - timedelta(minutes=bar_minutes)
    grid = pl.datetime_range(start, end, interval=f"{bar_minutes}m", time_zone="UTC", eager=True)
    open_slots = int((~closed(grid)).sum())
    in_closure = int(closed(ts).sum())
    in_open = ts.len() - in_closure
    gaps = int((ts.diff() > timedelta(hours=max_gap_hours)).fill_null(False).sum())
    missing = 0.0 if open_slots == 0 else max(0.0, 1 - in_open / open_slots)
    return YearQuality(year, ts.len(), open_slots, in_open, in_closure, missing, gaps)


def certificate(rows: list[YearClock]) -> dict[str, object]:
    """The JSON the console reads: ``{"years": {"2022": {"certified": ..., "offset": ...}}}``."""
    years: dict[str, object] = {}
    for row in rows:
        years[str(row.year)] = {
            "certified": row.certified,
            "offset": "NY+7" if row.certified else None,
            "weeks": row.weeks,
            "close_minute_ny": row.close_mode_minute,
            "close_fraction": round(row.close_fraction, 4),
            "dst_mismatch_weeks": row.mismatch_weeks,
            "ny_anchored_fraction_in_mismatch_weeks": row.ny_anchored_mismatch_fraction,
            "open_minute_ny": row.open_mode_minute,
            "open_fraction": round(row.open_fraction, 4),
            "reason": row.reason,
        }
    return {
        "method": (
            "weekly close New York minute through US/EU DST mismatch weeks; "
            "bar-open timestamps only (no prices)"
        ),
        "years": years,
    }
