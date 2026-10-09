"""Holiday rules, absence classification, closure windows and drop reasons."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from xau_edge.domain.market import MarketStatus
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.calendars import classify_incomplete, ftmo_calendar, ftmo_profile
from xau_edge.market_data.resampling import resample_bars
from xau_edge.market_data.session import market_status
from xau_edge.market_data.session_exceptions import (
    closures_from,
    dump_closures,
    easter,
    find_absences,
    holiday_dates,
    load_closures,
)
from xau_edge.market_data.validators.market_calendar import ClosureWindow

TEMPLATE = ftmo_profile().validation.calendar


def minute_bars(
    start: datetime, end: datetime, *, skip: tuple[datetime, datetime] | None = None
) -> pl.DataFrame:
    """M1 bars on every slot the weekly template calls open (optionally with a hole)."""
    slots = pl.datetime_range(
        start, end, interval="1m", closed="left", eager=True
    ).dt.replace_time_zone("UTC")
    frame = pl.DataFrame({"timestamp": slots})
    frame = frame.filter(~TEMPLATE.closed_expr(pl.col("timestamp")))
    if skip:
        frame = frame.filter(~((pl.col("timestamp") >= skip[0]) & (pl.col("timestamp") < skip[1])))
    return frame.with_columns(
        open=pl.lit(2000.0), high=pl.lit(2001.0), low=pl.lit(1999.0), close=pl.lit(2000.5),
        tick_volume=pl.lit(10, dtype=pl.Int64), spread=pl.lit(30, dtype=pl.Int64),
        real_volume=pl.lit(0, dtype=pl.Int64),
    )  # fmt: skip


def test_easter_and_holiday_rules() -> None:
    assert easter(2026) == date(2026, 4, 5)
    days = holiday_dates(2026)
    assert date(2026, 4, 3) in days  # Good Friday
    assert date(2026, 7, 3) in days  # Independence Day observed (the 4th is a Saturday)
    assert date(2026, 9, 7) in days  # Labor Day
    assert date(2026, 11, 26) in days  # Thanksgiving
    assert date(2026, 3, 11) not in days


def test_weekly_template_has_no_absence_without_holes() -> None:
    bars = minute_bars(datetime(2026, 3, 9, tzinfo=UTC), datetime(2026, 3, 14, tzinfo=UTC))
    assert find_absences(bars, Timeframe.M1, TEMPLATE) == []


def test_holiday_early_close_becomes_closure_and_unexplained_gap_does_not() -> None:
    # Labor Day 2026-09-07: the broker stops trading at 14:30 NY (18:30 UTC) until 18:05 NY.
    holiday = (datetime(2026, 9, 7, 18, 30, tzinfo=UTC), datetime(2026, 9, 7, 22, 5, tzinfo=UTC))
    gap = (datetime(2026, 9, 9, 10, 0, tzinfo=UTC), datetime(2026, 9, 9, 11, 30, tzinfo=UTC))
    bars = minute_bars(
        datetime(2026, 9, 6, tzinfo=UTC), datetime(2026, 9, 12, tzinfo=UTC), skip=holiday
    )
    bars = bars.filter(~((pl.col("timestamp") >= gap[0]) & (pl.col("timestamp") < gap[1])))
    absences = find_absences(bars, Timeframe.M1, TEMPLATE)
    reasons = sorted(a.reason for a in absences)
    assert reasons == ["EARLY_CLOSE", "UNCLASSIFIED"]
    windows = closures_from(absences)
    assert len(windows) == 1 and windows[0].reason == "EARLY_CLOSE"


def test_closure_window_makes_resampling_complete_and_gap_is_still_dropped() -> None:
    holiday = (datetime(2026, 9, 7, 18, 30, tzinfo=UTC), datetime(2026, 9, 7, 22, 5, tzinfo=UTC))
    gap = (datetime(2026, 9, 9, 10, 0, tzinfo=UTC), datetime(2026, 9, 9, 11, 30, tzinfo=UTC))
    bars = minute_bars(
        datetime(2026, 9, 6, tzinfo=UTC), datetime(2026, 9, 12, tzinfo=UTC), skip=holiday
    )
    bars = bars.filter(~((pl.col("timestamp") >= gap[0]) & (pl.col("timestamp") < gap[1])))
    clock = ftmo_profile().clock
    plain = resample_bars(bars, Timeframe.M1, Timeframe.H1, clock=clock, calendar=TEMPLATE)
    calendar = TEMPLATE.model_copy(
        update={"closures": closures_from(find_absences(bars, Timeframe.M1, TEMPLATE))}
    )
    modelled = resample_bars(bars, Timeframe.M1, Timeframe.H1, clock=clock, calendar=calendar)
    assert len(modelled.incomplete) == len(plain.incomplete) - 1
    reasons = classify_incomplete(modelled.incomplete, Timeframe.H1, bars, calendar)
    assert len(reasons["DATA_GAP"]) == 1  # the unexplained hole is reported, never filled


def test_market_status_inside_holiday_window_is_closed_not_rollover() -> None:
    window = ClosureWindow(
        start=datetime(2026, 9, 7, 18, 30, tzinfo=UTC),
        end=datetime(2026, 9, 7, 22, 5, tzinfo=UTC),
        reason="EARLY_CLOSE",
    )
    calendar = TEMPLATE.model_copy(update={"closures": (window,)})
    assert market_status(datetime(2026, 9, 7, 20, 0, tzinfo=UTC), calendar) == MarketStatus.CLOSED
    assert market_status(datetime(2026, 9, 8, 15, 0, tzinfo=UTC), calendar) == MarketStatus.OPEN
    assert market_status(datetime(2026, 9, 8, 21, 0, tzinfo=UTC), calendar) == MarketStatus.ROLLOVER


def test_closure_file_round_trip_and_validation(tmp_path: Path) -> None:
    window = ClosureWindow(
        start=datetime(2026, 7, 3, 17, tzinfo=UTC),
        end=datetime(2026, 7, 5, 22, 5, tzinfo=UTC),
        reason="HOLIDAY",
    )
    path = tmp_path / "x.yaml"
    dump_closures(path, (window,), "# test")
    assert load_closures(path) == (window,)
    assert load_closures(tmp_path / "missing.yaml") == ()
    with pytest.raises(ValueError, match="timezone-aware"):
        ClosureWindow(start=datetime(2026, 1, 1), end=datetime(2026, 1, 2), reason="HOLIDAY")  # noqa: DTZ001
    assert timedelta(0) == timedelta(0)


def test_shipped_calendar_loads_with_recent_closures() -> None:
    calendar = ftmo_calendar()
    assert any(w.reason == "EARLY_CLOSE" and w.start.year == 2026 for w in calendar.closures)


def test_short_thin_market_gaps_and_multi_week_gaps_are_never_closures() -> None:
    from datetime import timedelta  # noqa: PLC0415

    bars = minute_bars(datetime(2026, 3, 9, tzinfo=UTC), datetime(2026, 3, 13, tzinfo=UTC))
    thin = (datetime(2026, 3, 10, 9, 0, tzinfo=UTC), datetime(2026, 3, 10, 9, 40, tzinfo=UTC))
    cut = bars.filter(~((pl.col("timestamp") >= thin[0]) & (pl.col("timestamp") < thin[1])))
    assert (
        find_absences(cut, Timeframe.M1, TEMPLATE) == []
    )  # 40 minutes: not even reported as a closure
    # a two-week hole on a day touching a holiday date is data loss, never a "holiday"
    start = datetime(2026, 11, 20, tzinfo=UTC)
    long_hole = minute_bars(start, start + timedelta(days=2))
    later = minute_bars(start + timedelta(days=16), start + timedelta(days=17))
    absences = find_absences(pl.concat([long_hole, later]), Timeframe.M1, TEMPLATE)
    assert absences
    assert {a.reason for a in absences} == {"UNCLASSIFIED"}
