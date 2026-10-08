from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators import IssueCode, Severity
from xau_edge.market_data.validators.coverage import check_coverage

pytestmark = pytest.mark.unit

START = datetime(2025, 3, 3, 0, 0, tzinfo=UTC)  # a Monday
BARS = make_bars(96, timeframe=Timeframe.M15, start=START)  # exactly one day
END = START + timedelta(days=1)


def test_full_coverage_has_no_issue() -> None:
    assert check_coverage(BARS, START, END) is None


def test_small_edge_gaps_within_tolerance_are_ignored() -> None:
    assert check_coverage(BARS, START - timedelta(days=2), END + timedelta(days=2)) is None


def test_history_that_starts_late_is_an_error() -> None:
    issue = check_coverage(BARS, START - timedelta(days=10), END)
    assert issue is not None
    assert issue.code is IssueCode.INCOMPLETE_COVERAGE
    assert issue.severity is Severity.ERROR
    assert "starts" in issue.message
    assert issue.sample == (BARS["timestamp"][0],)


def test_history_that_ends_early_is_an_error() -> None:
    issue = check_coverage(BARS, START, END + timedelta(days=10))
    assert issue is not None
    assert "ends" in issue.message
    assert issue.sample == (BARS["timestamp"][-1],)


def test_both_edges_are_reported_in_one_issue() -> None:
    issue = check_coverage(BARS, START - timedelta(days=6), END + timedelta(days=6))
    assert issue is not None
    assert "starts" in issue.message
    assert "ends" in issue.message


def test_tolerance_boundary_is_inclusive() -> None:
    tolerance = timedelta(days=3)
    assert check_coverage(BARS, START - tolerance, END, tolerance=tolerance) is None
    assert check_coverage(BARS, START - tolerance - timedelta(seconds=1), END, tolerance=tolerance)
    assert (
        check_coverage(BARS, START, BARS["timestamp"][-1] + tolerance, tolerance=tolerance) is None
    )
    assert check_coverage(
        BARS, START, BARS["timestamp"][-1] + tolerance + timedelta(seconds=1), tolerance=tolerance
    )


def test_tolerance_is_configurable() -> None:
    assert check_coverage(BARS, START - timedelta(days=6), END, tolerance=timedelta(days=7)) is None
    assert check_coverage(BARS, START - timedelta(days=2), END, tolerance=timedelta(hours=1))


def test_empty_frame_is_an_error() -> None:
    issue = check_coverage(make_bars(0), START, END)
    assert issue is not None
    assert issue.code is IssueCode.INCOMPLETE_COVERAGE
