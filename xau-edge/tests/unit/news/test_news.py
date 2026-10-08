"""News risk guard: configurable windows around high-impact events; fail-open is NOT allowed."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xau_edge.news.calendar import (
    CalendarUnavailableError,
    EventImpact,
    NewsEvent,
    StaticCalendar,
    load_calendar_csv,
    news_blocked,
)

T = datetime(2026, 3, 6, 13, 30, tzinfo=UTC)  # a Friday 08:30 New York
NFP = NewsEvent(time=T, category="NFP", impact=EventImpact.HIGH)
LOW = NewsEvent(time=T + timedelta(hours=3), category="Minor", impact=EventImpact.LOW)
WIDE = (T - timedelta(days=30), T + timedelta(days=30))


def test_blocked_inside_the_window_and_free_outside_with_inclusive_edges() -> None:
    cal = StaticCalendar([NFP], coverage=WIDE)
    assert news_blocked(cal, T, before_minutes=15, after_minutes=30)
    assert news_blocked(cal, T - timedelta(minutes=15), before_minutes=15, after_minutes=30)
    assert news_blocked(cal, T + timedelta(minutes=30), before_minutes=15, after_minutes=30)
    assert not news_blocked(cal, T - timedelta(minutes=16), before_minutes=15, after_minutes=30)
    assert not news_blocked(cal, T + timedelta(minutes=31), before_minutes=15, after_minutes=30)


@pytest.mark.parametrize("minutes", [5, 10, 15, 30, 60])
def test_the_brief_window_sizes_are_supported(minutes: int) -> None:
    cal = StaticCalendar([NFP], coverage=WIDE)
    inside = T + timedelta(minutes=minutes)
    outside = T + timedelta(minutes=minutes + 1)
    assert news_blocked(cal, inside, before_minutes=minutes, after_minutes=minutes)
    assert not news_blocked(cal, outside, before_minutes=minutes, after_minutes=minutes)


def test_only_events_at_or_above_the_minimum_impact_count() -> None:
    cal = StaticCalendar([LOW], coverage=WIDE)
    assert not news_blocked(cal, LOW.time, before_minutes=10, after_minutes=10)
    assert news_blocked(
        cal, LOW.time, before_minutes=10, after_minutes=10, min_impact=EventImpact.LOW
    )


def test_time_outside_calendar_coverage_is_an_error_not_a_free_pass() -> None:
    cal = StaticCalendar([NFP], coverage=(T - timedelta(days=1), T + timedelta(days=1)))
    with pytest.raises(CalendarUnavailableError):
        news_blocked(cal, T + timedelta(days=5), before_minutes=10, after_minutes=10)


def test_naive_times_are_rejected() -> None:
    cal = StaticCalendar([NFP], coverage=WIDE)
    naive = datetime(2026, 3, 6, 13, 30)  # noqa: DTZ001 - naive on purpose
    with pytest.raises(ValueError, match="timezone"):
        news_blocked(cal, naive, before_minutes=10, after_minutes=10)


def test_negative_windows_are_rejected() -> None:
    cal = StaticCalendar([], coverage=WIDE)
    with pytest.raises(ValueError, match="minutes"):
        news_blocked(cal, T, before_minutes=-1, after_minutes=5)


def test_csv_loader_reads_events_ordered_by_time(tmp_path: Path) -> None:
    path = tmp_path / "events.csv"
    path.write_text(
        "time_utc,category,impact\n"
        "2026-03-06T13:30:00Z,NFP,high\n"
        "2026-03-18T18:00:00Z,FOMC,high\n"
        "2026-03-10T09:00:00Z,Misc,low\n",
        encoding="utf-8",
    )
    cover = (datetime(2026, 3, 1, tzinfo=UTC), datetime(2026, 4, 1, tzinfo=UTC))
    events = load_calendar_csv(path, coverage=cover).events_between(*cover)
    assert [e.category for e in events] == ["NFP", "Misc", "FOMC"]
    assert events[0].impact is EventImpact.HIGH


def test_csv_loader_rejects_bad_rows(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("time_utc,category,impact\n2026-03-06T13:30:00,NFP,high\n", encoding="utf-8")
    with pytest.raises(ValueError, match="UTC"):
        load_calendar_csv(path, coverage=(T, T))
    path.write_text("time_utc,category,impact\n2026-03-06T13:30:00Z,NFP,huge\n", encoding="utf-8")
    with pytest.raises(ValueError, match="impact"):
        load_calendar_csv(path, coverage=(T, T))


def test_a_window_that_sticks_out_of_the_coverage_is_an_error() -> None:
    cal = StaticCalendar([], coverage=(T - timedelta(hours=1), T + timedelta(hours=1)))
    assert not news_blocked(cal, T, before_minutes=30, after_minutes=30)
    with pytest.raises(CalendarUnavailableError):
        news_blocked(cal, T, before_minutes=90, after_minutes=10)
    with pytest.raises(CalendarUnavailableError):
        news_blocked(cal, T, before_minutes=10, after_minutes=90)


def test_naive_coverage_is_rejected() -> None:
    naive = datetime(2026, 1, 1)  # noqa: DTZ001 - naive on purpose
    with pytest.raises(ValueError, match="timezone"):
        StaticCalendar([], coverage=(naive, T))
