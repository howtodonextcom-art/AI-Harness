from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from xau_edge_v2.data.broker_profile import default_calendar, load_profile
from xau_edge_v2.domain.market import (
    BrokerClock,
    BrokerClockError,
    CalendarConfig,
    ClosureWindow,
    MarketCalendar,
    MarketStatus,
)

NY = ZoneInfo("America/New_York")
CAL = MarketCalendar(
    CalendarConfig(
        weekend_close_minute=1010,
        weekend_open_minute=1085,
        daily_break_start_minute=1010,
        daily_break_end_minute=1085,
    )
)


def ny(y: int, m: int, d: int, hh: int, mm: int) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=NY).astimezone(UTC)


# ---- broker clock -----------------------------------------------------------------------------


def test_clock_parse_and_token() -> None:
    assert BrokerClock.parse("NY+7").token == "NY+7"
    assert BrokerClock.parse("ny-2").token == "NY-2"
    assert BrokerClock.parse("Europe/Athens").token == "Europe/Athens"
    for bad in ("", "NY", "NY+99", "Mars/Olympus", "NYX"):
        with pytest.raises(BrokerClockError):
            BrokerClock.parse(bad)


def test_server_wall_follows_us_dst_not_one_iana_zone() -> None:
    clock = BrokerClock.parse("NY+7")
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)  # NY 07:00 -> server 14:00
    summer = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)  # NY 08:00 -> server 15:00
    assert clock.to_server_wall(winter) == datetime(2026, 1, 15, 14, 0)
    assert clock.to_server_wall(summer) == datetime(2026, 7, 15, 15, 0)
    # the 17:00 NY rollover is server midnight all year
    assert clock.to_server_wall(ny(2026, 1, 14, 17, 0)).hour == 0
    assert clock.to_server_wall(ny(2026, 7, 14, 17, 0)).hour == 0


def test_server_to_utc_roundtrip() -> None:
    clock = BrokerClock.parse("NY+7")
    for utc in (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), datetime(2026, 7, 15, 12, 0, tzinfo=UTC)):
        assert clock.server_to_utc(clock.to_server_wall(utc)) == utc


def test_dst_gap_and_fold_are_refused_or_null() -> None:
    clock = BrokerClock.parse("NY+7")
    gap = datetime(2026, 3, 8, 9, 30)  # NY 02:30 does not exist on the spring-forward day
    fold = datetime(2026, 11, 1, 8, 30)  # NY 01:30 happens twice on the fall-back day
    for naive in (gap, fold):
        with pytest.raises(BrokerClockError):
            clock.server_to_utc(naive)
        assert clock.server_to_utc(naive, strict=False) is None


def test_clock_rejects_naive_utc_and_aware_server() -> None:
    clock = BrokerClock.parse("NY+7")
    with pytest.raises(ValueError, match="aware"):
        clock.to_server_wall(datetime(2026, 1, 1))
    with pytest.raises(BrokerClockError):
        clock.server_to_utc(datetime(2026, 1, 1, tzinfo=UTC))


# ---- calendar ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        (ny(2026, 10, 14, 12, 0), MarketStatus.OPEN),  # Wednesday noon
        (ny(2026, 10, 14, 16, 49), MarketStatus.OPEN),
        (ny(2026, 10, 14, 16, 50), MarketStatus.ROLLOVER),  # daily break starts
        (ny(2026, 10, 14, 18, 4), MarketStatus.ROLLOVER),
        (ny(2026, 10, 14, 18, 5), MarketStatus.OPEN),  # reopens
        (ny(2026, 10, 16, 16, 49), MarketStatus.OPEN),  # Friday just before the weekend close
        (ny(2026, 10, 16, 16, 50), MarketStatus.CLOSED),  # weekend begins (not the daily break)
        (ny(2026, 10, 17, 12, 0), MarketStatus.CLOSED),  # Saturday
        (ny(2026, 10, 18, 18, 4), MarketStatus.CLOSED),  # Sunday before the open
        (ny(2026, 10, 18, 18, 5), MarketStatus.OPEN),  # Sunday open
    ],
)
def test_status_weekly_template(moment: datetime, expected: MarketStatus) -> None:
    assert CAL.status(moment) is expected


def test_status_of_naive_time_is_unknown() -> None:
    assert CAL.status(datetime(2026, 10, 14, 12, 0)) is MarketStatus.UNKNOWN


def test_closure_windows_close_the_market_and_merge() -> None:
    a = ClosureWindow(start=ny(2026, 12, 25, 6, 0), end=ny(2026, 12, 25, 12, 0), reason="HOLIDAY")
    b = ClosureWindow(start=ny(2026, 12, 25, 11, 0), end=ny(2026, 12, 25, 14, 0), reason="HOLIDAY")
    cal = MarketCalendar(
        CalendarConfig(weekend_close_minute=1010, weekend_open_minute=1085, closures=(a, b))
    )
    assert cal.status(ny(2026, 12, 25, 5, 59)) is MarketStatus.OPEN
    assert cal.status(ny(2026, 12, 25, 6, 0)) is MarketStatus.CLOSED
    assert cal.status(ny(2026, 12, 25, 13, 59)) is MarketStatus.CLOSED  # merged window
    assert cal.status(ny(2026, 12, 25, 14, 0)) is MarketStatus.OPEN


def test_next_open_from_the_weekend_is_sunday_1805_ny() -> None:
    nxt = CAL.next_open(ny(2026, 10, 17, 9, 0))
    assert nxt is not None and nxt == ny(2026, 10, 18, 18, 5)
    now = ny(2026, 10, 14, 12, 0)
    assert CAL.next_open(now) == now  # already open


def test_open_seconds_skip_weekend_and_break() -> None:
    # Fri 16:40 -> Sun 18:15 NY: 10 open minutes before the close + 10 after the reopen
    start, end = ny(2026, 10, 16, 16, 40), ny(2026, 10, 18, 18, 15)
    assert CAL.open_seconds_between(start, end) == 1200.0
    assert CAL.open_seconds_between(end, start) == 0.0


def test_one_hour_week_around_dst_change_keeps_ny_anchored_hours() -> None:
    # US spring-forward 2026-03-08: the Sunday open is still 18:05 NY (UTC offset moved by an hour)
    before = ny(2026, 3, 1, 18, 5)
    after = ny(2026, 3, 15, 18, 5)
    assert before.hour != after.hour  # 23:05 UTC then 22:05 UTC
    assert CAL.status(before) is MarketStatus.OPEN and CAL.status(after) is MarketStatus.OPEN
    assert CAL.status(before - timedelta(minutes=1)) is MarketStatus.CLOSED


@given(st.datetimes(min_value=datetime(2004, 6, 1), max_value=datetime(2026, 12, 31)))
def test_status_open_iff_not_closed(naive: datetime) -> None:
    moment = naive.replace(tzinfo=UTC)
    cal = default_calendar()
    assert (cal.status(moment) is MarketStatus.OPEN) == (not cal.is_closed(moment))


def test_profile_is_the_ftmo_demo_one() -> None:
    profile = load_profile()
    assert profile.clock.token == "NY+7"
    assert (
        profile.calendar.weekend_close_minute == 1010
        and profile.calendar.weekend_open_minute == 1085
    )
    assert len(profile.calendar.closures) == 1307
    assert profile.instrument.symbol == "XAUUSD" and profile.instrument.contract_size == 100.0
