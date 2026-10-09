from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from xau_edge.forensics.clock import (
    certificate,
    clock_by_year,
    weekend_gaps,
    year_clock,
    year_quality,
)

NY = ZoneInfo("America/New_York")


def week_bars(monday_utc: datetime, shift_hours: int = 0) -> list[datetime]:
    """Hourly bars Sun 18:00 NY to Fri 16:00 NY, shifted by ``shift_hours`` (a clock error)."""
    ny_monday = monday_utc.replace(hour=12).astimezone(NY).replace(hour=0, minute=0)
    start = (ny_monday - timedelta(days=1)).replace(hour=18)
    out = []
    cur = start
    while cur < ny_monday + timedelta(days=4, hours=17):
        if cur.hour != 17:  # the daily break hour
            out.append(cur.astimezone(UTC) + timedelta(hours=shift_hours))
        cur += timedelta(hours=1)
    return out


ATHENS = ZoneInfo("Europe/Athens")


def eu_anchored_series(year: int, weeks: int) -> pl.Series:
    """Weeks whose session boundary is pinned to Athens midnight (a European-DST server clock)."""
    monday = datetime(year, 1, 1, tzinfo=UTC)
    monday += timedelta(days=(7 - monday.weekday()) % 7)
    stamps: list[datetime] = []
    for w in range(weeks):
        day = (monday + timedelta(weeks=w)).replace(hour=12).astimezone(ATHENS)
        day = day.replace(hour=0, minute=0)
        cur = day + timedelta(hours=1)  # Monday 01:00 Athens = Sunday 18:00 New York
        end = day + timedelta(days=5)  # Saturday 00:00 Athens
        while cur < end:
            stamps.append(cur.astimezone(UTC))
            cur += timedelta(hours=1)
    return pl.Series("timestamp", stamps, dtype=pl.Datetime("us", "UTC")).sort()


def series(year: int, weeks: int, shift: int = 0, shift_from_week: int = 10**6) -> pl.Series:
    monday = datetime(year, 1, 1, tzinfo=UTC)
    monday += timedelta(days=(7 - monday.weekday()) % 7)
    stamps: list[datetime] = []
    for w in range(weeks):
        s = shift if w >= shift_from_week else 0
        stamps.extend(week_bars(monday + timedelta(weeks=w), s))
    return pl.Series("timestamp", stamps, dtype=pl.Datetime("us", "UTC")).sort()


def test_a_correct_clock_year_is_certified() -> None:
    row = year_clock(2023, series(2023, 45))
    assert row.certified
    assert row.close_mode_minute == 17 * 60
    assert row.close_fraction > 0.9
    assert 17 in row.daily_break_hours_ny


def test_a_wrong_offset_year_is_not_certified_and_says_why() -> None:
    row = year_clock(2014, series(2014, 45, shift=1, shift_from_week=0))
    assert not row.certified
    assert row.close_mode_minute != 17 * 60
    assert "17:00" in row.reason


def test_an_offset_change_in_the_middle_of_a_year_is_not_certified() -> None:
    row = year_clock(2020, series(2020, 48, shift=1, shift_from_week=20))
    assert not row.certified


def test_too_few_weeks_cannot_be_certified() -> None:
    row = year_clock(2021, series(2021, 5))
    assert not row.certified
    assert row.reason == "too few weeks"


def test_clock_by_year_splits_years_and_the_certificate_has_the_console_shape() -> None:
    both = pl.concat([series(2022, 45), series(2024, 45, shift=2, shift_from_week=0)]).sort()
    rows = {r.year: r for r in clock_by_year(both)}
    assert rows[2022].certified
    assert not rows[2024].certified
    cert = certificate(list(rows.values()))
    years = cert["years"]
    assert isinstance(years, dict)
    assert years["2022"]["certified"] is True
    assert years["2024"]["certified"] is False
    assert years["2024"]["offset"] is None


def test_weekend_gaps_find_the_boundaries() -> None:
    ts = series(2023, 3)
    before, after = weekend_gaps(ts)
    assert len(before) == len(after) == 2


def test_year_quality_counts_bars_inside_closures_and_gaps() -> None:
    ts = series(2023, 10)

    def closed(s: pl.Series) -> pl.Series:
        ny = s.dt.convert_time_zone("America/New_York")
        return (ny.dt.hour() == 17) | (ny.dt.weekday() == 6)

    q = year_quality(2023, ts, closed)
    assert q.bars == ts.len()
    assert q.bars_inside_closure == 0
    assert 0.5 < q.missing_fraction < 1.0  # only 10 of 52 weeks present
    assert year_quality(2023, ts.head(0), closed).missing_fraction == 1.0


def test_a_european_dst_clock_is_detected_by_the_mismatch_weeks() -> None:
    row = year_clock(2016, eu_anchored_series(2016, 48))
    assert row.mismatch_weeks >= 2
    assert row.ny_anchored_mismatch_fraction is not None
    assert row.ny_anchored_mismatch_fraction < 0.5
    assert not row.certified
    assert "European" in row.reason


def test_a_new_york_anchored_year_holds_through_the_mismatch_weeks() -> None:
    row = year_clock(2023, series(2023, 48))
    assert row.mismatch_weeks >= 2
    assert row.ny_anchored_mismatch_fraction == 1.0
    assert row.certified
