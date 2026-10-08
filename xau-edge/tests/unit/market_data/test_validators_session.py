"""Validator behaviour on a broker-like session (daily break, holidays, partial bars).

These cases came from validating real FTMO demo data: a calendar that only looked at bar-open
times produced hundreds of false WEEKEND_BARS warnings on H1/H4, and early-close holidays were
counted as data loss.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import polars as pl
import pytest

from tests.conftest import make_bars
from tests.synthetic import FTMO_CALENDAR, drop_ny_window, ftmo_like_m5
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators import (
    IssueCode,
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
