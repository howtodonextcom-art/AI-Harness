from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from tests.conftest import MONDAY, make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators import (
    IssueCode,
    MarketCalendar,
    Severity,
    ValidationConfig,
    validate_bars,
)

pytestmark = pytest.mark.unit

TF = Timeframe.M15


def codes(report: object) -> set[IssueCode]:
    return {i.code for i in report.issues}  # type: ignore[attr-defined]


def test_clean_series_passes_with_no_issues(bars: pl.DataFrame) -> None:
    report = validate_bars(bars, TF)
    assert report.passed
    assert report.issues == ()
    assert report.rows == bars.height


def test_empty_frame_is_an_error() -> None:
    report = validate_bars(make_bars(0), TF)
    assert not report.passed
    assert IssueCode.EMPTY in codes(report)


def test_missing_columns_short_circuits() -> None:
    report = validate_bars(pl.DataFrame({"timestamp": [MONDAY]}), TF)
    assert not report.passed
    assert codes(report) == {IssueCode.MISSING_COLUMNS}


def test_duplicate_timestamps_detected(bars: pl.DataFrame) -> None:
    dup = pl.concat([bars, bars.slice(10, 1)])
    report = validate_bars(dup, TF)
    issue = next(i for i in report.issues if i.code is IssueCode.DUPLICATE_TIMESTAMPS)
    assert issue.count == 1
    assert issue.severity is Severity.ERROR
    assert issue.sample == (bars["timestamp"][10],)
    # A pure duplicate (appended in order after its twin) must not also be "out of order".
    adjacent = pl.concat([bars.slice(0, 11), bars.slice(10, 1), bars.slice(11)])
    assert IssueCode.OUT_OF_ORDER not in codes(validate_bars(adjacent, TF))


def test_sunday_open_boundary_is_exact() -> None:
    sunday_2145 = datetime(2025, 2, 9, 21, 45, tzinfo=UTC)
    closed = validate_bars(make_bars(1, start=sunday_2145), TF)
    assert IssueCode.WEEKEND_BARS in codes(closed)
    sunday_2200 = datetime(2025, 2, 9, 22, 0, tzinfo=UTC)
    opened = validate_bars(make_bars(1, start=sunday_2200), TF)
    assert IssueCode.WEEKEND_BARS not in codes(opened)


@pytest.mark.parametrize(
    ("start", "weekend_bar_expected", "label"),
    [
        # Friday: market closes 17:00 New York = 21:00 UTC in US summer, 22:00 UTC in winter.
        (datetime(2025, 7, 4, 21, 15, tzinfo=UTC), True, "summer Friday 21:15 UTC is closed"),
        (datetime(2025, 7, 4, 20, 45, tzinfo=UTC), False, "summer Friday 20:45 UTC is open"),
        (datetime(2025, 1, 10, 21, 15, tzinfo=UTC), False, "winter Friday 21:15 UTC is open"),
        (datetime(2025, 1, 10, 22, 0, tzinfo=UTC), True, "winter Friday 22:00 UTC is closed"),
        # Sunday: reopens 17:00 New York = 21:00 UTC in summer, 22:00 UTC in winter.
        (datetime(2025, 7, 6, 20, 45, tzinfo=UTC), True, "summer Sunday 20:45 UTC is closed"),
        (datetime(2025, 7, 6, 21, 0, tzinfo=UTC), False, "summer Sunday 21:00 UTC is open"),
        (datetime(2025, 1, 12, 21, 45, tzinfo=UTC), True, "winter Sunday 21:45 UTC is closed"),
        (datetime(2025, 1, 12, 22, 0, tzinfo=UTC), False, "winter Sunday 22:00 UTC is open"),
    ],
)
def test_default_calendar_follows_new_york_daylight_saving(
    start: datetime, weekend_bar_expected: bool, label: str
) -> None:
    report = validate_bars(make_bars(1, start=start), TF)
    flagged = IssueCode.WEEKEND_BARS in codes(report)
    assert flagged is weekend_bar_expected, label


def test_calendar_rejects_unknown_timezone() -> None:
    with pytest.raises(ValueError, match="unknown IANA time zone"):
        MarketCalendar(timezone="Mars/Olympus")


def test_missing_fraction_exactly_at_threshold_is_only_a_warning() -> None:
    full = make_bars(40)
    gappy = pl.concat([full.slice(0, 10), full.slice(14)])  # 4 missing of 40 expected = 0.1
    report = validate_bars(gappy, TF, config=ValidationConfig(max_missing_fraction=0.1))
    issue = next(i for i in report.issues if i.code is IssueCode.MISSING_BARS)
    assert issue.severity is Severity.WARNING


def test_out_of_order_timestamps_detected(bars: pl.DataFrame) -> None:
    shuffled = pl.concat([bars.slice(5, 1), bars.slice(0, 5), bars.slice(6)])
    report = validate_bars(shuffled, TF)
    assert IssueCode.OUT_OF_ORDER in codes(report)
    # Order problems must not be hidden by sorting inside the validator.
    assert not report.passed


def test_missing_bars_counted_inside_open_market() -> None:
    full = make_bars(40)
    gappy = pl.concat([full.slice(0, 10), full.slice(14)])  # drop 4 consecutive bars
    report = validate_bars(gappy, TF, config=ValidationConfig(max_missing_fraction=0.5))
    issue = next(i for i in report.issues if i.code is IssueCode.MISSING_BARS)
    assert issue.count == 4
    assert issue.severity is Severity.WARNING


def test_missing_bars_escalate_to_error_above_threshold() -> None:
    full = make_bars(40)
    gappy = pl.concat([full.slice(0, 10), full.slice(30)])
    report = validate_bars(gappy, TF, config=ValidationConfig(max_missing_fraction=0.01))
    issue = next(i for i in report.issues if i.code is IssueCode.MISSING_BARS)
    assert issue.severity is Severity.ERROR
    assert not report.passed


def test_weekend_gap_itself_is_never_reported_as_missing() -> None:
    friday = datetime(2025, 2, 7, 20, 0, tzinfo=UTC)
    sunday = datetime(2025, 2, 9, 22, 0, tzinfo=UTC)
    fri = make_bars(4, start=friday)  # 20:00..20:45 -> last bar 20:45 Fri
    sun = make_bars(4, start=sunday)
    report = validate_bars(pl.concat([fri, sun]), TF)
    # Friday 21:00..21:45 slots are still open (close at 22:00): the week ended early. That is
    # an early close ending at a scheduled reopening, i.e. a closure warning, not data loss.
    assert IssueCode.MISSING_BARS not in codes(report)
    closure = next(i for i in report.issues if i.code is IssueCode.UNSCHEDULED_CLOSURES)
    assert closure.count == 4  # 21:00, 21:15, 21:30, 21:45 only
    assert closure.severity is Severity.WARNING


def test_weekend_bars_flagged_as_warning() -> None:
    saturday = datetime(2025, 3, 8, 12, 0, tzinfo=UTC)
    report = validate_bars(make_bars(3, start=saturday), TF)
    issue = next(i for i in report.issues if i.code is IssueCode.WEEKEND_BARS)
    assert issue.count == 3
    assert issue.severity is Severity.WARNING


def test_custom_calendar_changes_weekend_window() -> None:
    friday_2130 = datetime(2025, 3, 7, 21, 30, tzinfo=UTC)
    early_close = ValidationConfig(
        calendar=MarketCalendar(timezone="UTC", weekend_close_minute=21 * 60)
    )
    report = validate_bars(make_bars(2, start=friday_2130), TF, config=early_close)
    assert IssueCode.WEEKEND_BARS in codes(report)
    default = validate_bars(make_bars(2, start=friday_2130), TF)
    assert IssueCode.WEEKEND_BARS not in codes(default)


@pytest.mark.parametrize(
    ("column", "value"),
    [("high", 1990.0), ("low", 2100.0)],
)
def test_invalid_ohlc_detected(bars: pl.DataFrame, column: str, value: float) -> None:
    broken = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 7).then(value).otherwise(pl.col(column)).alias(column)
    )
    report = validate_bars(broken, TF)
    issue = next(i for i in report.issues if i.code is IssueCode.INVALID_OHLC)
    assert issue.count == 1
    assert issue.sample == (bars["timestamp"][7],)


def test_non_positive_price_detected(bars: pl.DataFrame) -> None:
    broken = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 3).then(0.0).otherwise(pl.col("low")).alias("low")
    )
    assert IssueCode.NON_POSITIVE_PRICE in codes(validate_bars(broken, TF))


def test_negative_volume_detected(bars: pl.DataFrame) -> None:
    broken = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 2)
        .then(-5)
        .otherwise(pl.col("tick_volume"))
        .alias("tick_volume")
    )
    assert IssueCode.NEGATIVE_VOLUME in codes(validate_bars(broken, TF))


def test_negative_real_volume_detected(bars: pl.DataFrame) -> None:
    broken = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 2)
        .then(-5)
        .otherwise(pl.col("real_volume"))
        .alias("real_volume")
    )
    assert IssueCode.NEGATIVE_VOLUME in codes(validate_bars(broken, TF))


def test_negative_spread_is_error_and_wide_spread_is_warning(bars: pl.DataFrame) -> None:
    neg = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 1).then(-1).otherwise(pl.col("spread")).alias("spread")
    )
    r1 = validate_bars(neg, TF)
    assert next(i for i in r1.issues if i.code is IssueCode.INVALID_SPREAD).severity is (
        Severity.ERROR
    )
    wide = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 1).then(99999).otherwise(pl.col("spread")).alias("spread")
    )
    r2 = validate_bars(wide, TF, config=ValidationConfig(max_spread_points=500))
    assert next(i for i in r2.issues if i.code is IssueCode.INVALID_SPREAD).severity is (
        Severity.WARNING
    )
    assert r2.passed


def test_naive_timestamps_flagged(bars: pl.DataFrame) -> None:
    naive = bars.with_columns(pl.col("timestamp").dt.replace_time_zone(None))
    assert IssueCode.NON_UTC_TIMESTAMPS in codes(validate_bars(naive, TF))


def test_non_utc_timezone_flagged(bars: pl.DataFrame) -> None:
    athens = bars.with_columns(pl.col("timestamp").dt.convert_time_zone("Europe/Athens"))
    assert IssueCode.NON_UTC_TIMESTAMPS in codes(validate_bars(athens, TF))


def test_null_and_non_finite_values_detected(bars: pl.DataFrame) -> None:
    with_null = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 4).then(None).otherwise(pl.col("close")).alias("close")
    )
    assert IssueCode.NULL_VALUES in codes(validate_bars(with_null, TF))
    with_nan = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 4)
        .then(float("nan"))
        .otherwise(pl.col("close"))
        .alias("close")
    )
    assert IssueCode.NON_FINITE_VALUES in codes(validate_bars(with_nan, TF))
    with_inf = bars.with_columns(
        pl.when(pl.int_range(pl.len()) == 4)
        .then(float("inf"))
        .otherwise(pl.col("high"))
        .alias("high")
    )
    assert IssueCode.NON_FINITE_VALUES in codes(validate_bars(with_inf, TF))


@pytest.mark.parametrize(
    ("tf", "offset"),
    [
        (Timeframe.M5, timedelta(minutes=2)),
        (Timeframe.M15, timedelta(minutes=5)),
        (Timeframe.H1, timedelta(minutes=30)),
        (Timeframe.H4, timedelta(seconds=30)),
    ],
)
def test_misaligned_timestamps_detected(tf: Timeframe, offset: timedelta) -> None:
    shifted = make_bars(10, timeframe=tf).with_columns(pl.col("timestamp") + offset)
    assert IssueCode.MISALIGNED_TIMESTAMPS in codes(validate_bars(shifted, tf))


def test_h4_allows_broker_hour_offset() -> None:
    # Broker H4 bars start at server midnight, i.e. not a multiple of 4h in UTC.
    start = datetime(2025, 3, 3, 2, 0, tzinfo=UTC)
    report = validate_bars(make_bars(6, timeframe=Timeframe.H4, start=start), Timeframe.H4)
    assert IssueCode.MISALIGNED_TIMESTAMPS not in codes(report)


def test_report_summary_lists_each_issue(bars: pl.DataFrame) -> None:
    dup = pl.concat([bars, bars.slice(0, 2)])
    text = validate_bars(dup, TF).summary()
    assert "DUPLICATE_TIMESTAMPS" in text
    assert "FAILED" in text


def test_validator_does_not_mutate_input(bars: pl.DataFrame) -> None:
    before = bars.clone()
    validate_bars(bars, TF)
    assert bars.equals(before)
