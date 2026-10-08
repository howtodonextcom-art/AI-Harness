"""Validator behaviour on a broker-like session (daily break, holidays, partial bars).

These cases came from validating real FTMO demo data: a calendar that only looked at bar-open
times produced hundreds of false WEEKEND_BARS warnings on H1/H4, and early-close holidays were
counted as data loss.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from tests.synthetic import FTMO_CALENDAR, drop_ny_window, ftmo_like_m5
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.market_data.validators import (
    IssueCode,
    MarketCalendar,
    Severity,
    ValidationConfig,
    ValidationReport,
    validate_bars,
)

pytestmark = pytest.mark.unit

CFG = ValidationConfig(calendar=FTMO_CALENDAR)
M5 = Timeframe.M5
MONDAY = datetime(2026, 6, 15, tzinfo=UTC)
WEEK = ftmo_like_m5(MONDAY, weeks=1)
DAY = date(2026, 6, 16)  # a Tuesday inside WEEK


def issue(report: ValidationReport, code: IssueCode):  # type: ignore[no-untyped-def]
    return next((i for i in report.issues if i.code is code), None)


def test_clean_broker_like_week_has_no_issues() -> None:
    report = validate_bars(WEEK, M5, config=CFG)
    assert report.issues == ()


def test_higher_timeframe_bar_starting_inside_the_break_is_not_a_weekend_bar() -> None:
    # H1 bar opening at server 01:00 (NY 18:00, inside the break) holds data from 01:05.
    start = datetime(2026, 6, 30, 22, 0, tzinfo=UTC)  # server 01:00 on 2026-07-01
    report = validate_bars(
        make_bars(1, timeframe=Timeframe.H1, start=start), Timeframe.H1, config=CFG
    )
    assert issue(report, IssueCode.WEEKEND_BARS) is None


def test_bar_entirely_inside_the_break_is_still_flagged() -> None:
    start = datetime(2026, 6, 30, 21, 0, tzinfo=UTC)  # NY 17:00 on a Tuesday
    report = validate_bars(make_bars(1, timeframe=M5, start=start), M5, config=CFG)
    assert issue(report, IssueCode.WEEKEND_BARS) is not None


def test_early_close_is_a_scheduled_closure_warning_not_missing_bars() -> None:
    early = drop_ny_window(WEEK, DAY, 14 * 60 + 25, 16 * 60 + 50)  # 29 five-minute slots
    report = validate_bars(early, M5, config=CFG)
    closure = issue(report, IssueCode.UNSCHEDULED_CLOSURES)
    assert closure is not None
    assert closure.severity is Severity.WARNING
    assert closure.count == 29
    assert issue(report, IssueCode.MISSING_BARS) is None
    assert report.passed


def test_mid_session_data_loss_is_missing_bars() -> None:
    lossy = drop_ny_window(WEEK, DAY, 10 * 60, 10 * 60 + 50)  # 10 slots mid-morning
    report = validate_bars(lossy, M5, config=CFG)
    missing = issue(report, IssueCode.MISSING_BARS)
    assert missing is not None
    assert missing.count == 10
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES) is None


def test_short_gap_just_before_the_break_is_missing_bars_not_a_closure() -> None:
    lossy = drop_ny_window(WEEK, DAY, 16 * 60 + 35, 16 * 60 + 50)  # 3 slots, below 30 minutes
    report = validate_bars(lossy, M5, config=CFG)
    missing = issue(report, IssueCode.MISSING_BARS)
    assert missing is not None
    assert missing.count == 3
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES) is None


def test_closure_threshold_is_configurable() -> None:
    lossy = drop_ny_window(WEEK, DAY, 16 * 60 + 35, 16 * 60 + 50)
    cfg = ValidationConfig(calendar=FTMO_CALENDAR, min_closure_minutes=10)
    report = validate_bars(lossy, M5, config=cfg)
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES) is not None
    assert issue(report, IssueCode.MISSING_BARS) is None


def test_outage_longer_than_a_trading_day_ending_at_a_reopening_is_data_loss() -> None:
    """ECC review F-01: a ~31h outage ending at a reopening must not pass as a holiday."""
    ny = pl.col("timestamp").dt.convert_time_zone("America/New_York").dt.replace_time_zone(None)
    start, end = datetime(2026, 6, 16, 9, 0), datetime(2026, 6, 17, 17, 0)  # noqa: DTZ001
    outage = ftmo_like_m5(MONDAY, weeks=2).filter(~((ny >= start) & (ny < end)))
    report = validate_bars(outage, M5, config=ValidationConfig(calendar=FTMO_CALENDAR))
    missing = issue(report, IssueCode.MISSING_BARS)
    assert missing is not None
    assert missing.severity is Severity.ERROR  # >1% of the data is gone
    assert not report.passed
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES) is None


def test_closure_cap_boundary_is_inclusive() -> None:
    # NY 12:50-16:50 on DAY: 48 slots = 240 open minutes, ending at the 16:50 break.
    gap = drop_ny_window(WEEK, DAY, 12 * 60 + 50, 16 * 60 + 50)
    at_cap = ValidationConfig(calendar=FTMO_CALENDAR, max_closure_minutes=240)
    assert issue(validate_bars(gap, M5, config=at_cap), IssueCode.UNSCHEDULED_CLOSURES)
    below = ValidationConfig(calendar=FTMO_CALENDAR, max_closure_minutes=235)
    report = validate_bars(gap, M5, config=below)
    assert issue(report, IssueCode.MISSING_BARS)
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES) is None


def test_closure_cap_must_not_be_below_the_minimum() -> None:
    with pytest.raises(ValueError, match="max_closure_minutes"):
        ValidationConfig(min_closure_minutes=60, max_closure_minutes=30)


def test_default_closure_cap_is_one_trading_day() -> None:
    assert ValidationConfig().max_closure_minutes == 24 * 60


def test_half_configured_daily_break_is_rejected() -> None:
    with pytest.raises(ValueError, match="daily break"):
        MarketCalendar(daily_break_start_minute=60)
    with pytest.raises(ValueError, match="daily break"):
        MarketCalendar(daily_break_end_minute=60)
    MarketCalendar()  # neither is fine


@pytest.mark.parametrize(
    ("utc", "closed"),
    [
        # Literal instants from the live FTMO measurement (NOT derived from the calendar rules):
        # last bar of the week opens Fri 16:45 New York, first bar of the week Sun 18:05.
        (datetime(2026, 3, 13, 20, 45, tzinfo=UTC), False),  # Fri 16:45 EDT: last bar
        (datetime(2026, 3, 13, 20, 50, tzinfo=UTC), True),  # Fri 16:50 EDT: closed
        (datetime(2026, 3, 15, 22, 0, tzinfo=UTC), True),  # Sun 18:00 EDT: still closed
        (datetime(2026, 3, 15, 22, 5, tzinfo=UTC), False),  # Sun 18:05 EDT: first bar
        (datetime(2025, 12, 5, 21, 45, tzinfo=UTC), False),  # Fri 16:45 EST: last bar (winter)
        (datetime(2025, 12, 5, 21, 50, tzinfo=UTC), True),  # Fri 16:50 EST
        (datetime(2026, 1, 7, 22, 0, tzinfo=UTC), True),  # Wed 17:00 EST: daily break
        (datetime(2026, 1, 7, 23, 5, tzinfo=UTC), False),  # Wed 18:05 EST: reopened
    ],
)
def test_ftmo_profile_session_matches_measured_instants(utc: datetime, closed: bool) -> None:
    profile = BrokerProfile.from_yaml(
        Path(__file__).resolve().parents[3] / "configs" / "brokers" / "ftmo_demo.yaml"
    )
    report = validate_bars(make_bars(1, timeframe=M5, start=utc), M5, config=profile.validation)
    assert (issue(report, IssueCode.WEEKEND_BARS) is not None) is closed


def test_closure_threshold_boundary_is_inclusive() -> None:
    lossy = drop_ny_window(WEEK, DAY, 16 * 60 + 35, 16 * 60 + 50)  # 3 slots = exactly 15 minutes
    exact = ValidationConfig(calendar=FTMO_CALENDAR, min_closure_minutes=15)
    assert issue(validate_bars(lossy, M5, config=exact), IssueCode.UNSCHEDULED_CLOSURES)
    just_above = ValidationConfig(calendar=FTMO_CALENDAR, min_closure_minutes=16)
    assert issue(validate_bars(lossy, M5, config=just_above), IssueCode.MISSING_BARS)


def test_missing_fraction_excludes_closures_but_not_data_loss() -> None:
    both = drop_ny_window(
        drop_ny_window(WEEK, DAY, 14 * 60 + 25, 16 * 60 + 50), DAY, 10 * 60, 10 * 60 + 50
    )
    tight = ValidationConfig(calendar=FTMO_CALENDAR, max_missing_fraction=0.0001)
    report = validate_bars(both, M5, config=tight)
    assert issue(report, IssueCode.MISSING_BARS).severity is Severity.ERROR
    assert issue(report, IssueCode.UNSCHEDULED_CLOSURES).severity is Severity.WARNING
    assert not report.passed


def test_unscheduled_closure_sample_points_at_the_first_missing_slot() -> None:
    early = drop_ny_window(WEEK, DAY, 14 * 60 + 25, 16 * 60 + 50)
    closure = issue(validate_bars(early, M5, config=CFG), IssueCode.UNSCHEDULED_CLOSURES)
    assert closure is not None
    expected_first = (
        pl.Series([datetime(2026, 6, 16, 14, 25)])  # noqa: DTZ001
        .dt.replace_time_zone("America/New_York")
        .dt.convert_time_zone("UTC")[0]
    )
    assert closure.sample[0] == expected_first
