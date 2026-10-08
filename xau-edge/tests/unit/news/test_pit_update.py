"""Point-in-time calendar loader, providers, atomic update job and coverage alert."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xau_edge.news.calendar import (
    CalendarUnavailableError,
    load_calendar_file,
    news_blocked,
)
from xau_edge.news.pit import (
    CalendarLeakageError,
    load_calendar_asof,
    parse_calendar_text,
)
from xau_edge.news.providers import (
    CalendarProviderError,
    HttpsCsvProvider,
    LocalFileProvider,
    provider_from_source,
)
from xau_edge.news.update import (
    CalendarUpdateError,
    calendar_file_alert,
    coverage_alert,
    update_calendar,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
DOC = (
    "# coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z\n"
    "time_utc,category,impact,available_at\n"
    "2026-11-06T13:30:00Z,NFP,high,2026-10-01T08:00:00Z\n"
    "2026-10-20T12:30:00Z,CPI,high,2026-10-09T08:00:00Z\n"
)


def write(tmp_path: Path, text: str = DOC, name: str = "cal.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_future_available_at_is_refused_by_default(tmp_path: Path) -> None:
    path = write(tmp_path)
    with pytest.raises(CalendarLeakageError, match="CPI"):
        load_calendar_asof(path, NOW)
    cal = load_calendar_asof(path, NOW + timedelta(days=2))
    assert len(cal.events_between(NOW, NOW + timedelta(days=60))) == 2


def test_drop_mode_hides_rows_not_yet_known(tmp_path: Path) -> None:
    cal = load_calendar_asof(write(tmp_path), NOW, future_rows="drop")
    events = cal.events_between(NOW, NOW + timedelta(days=60))
    assert [e.category for e in events] == ["NFP"]


def test_naive_decision_time_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timezone"):
        load_calendar_asof(write(tmp_path), datetime(2026, 10, 8, 12, 0))  # noqa: DTZ001


def test_missing_available_at_column_is_refused(tmp_path: Path) -> None:
    text = "# coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z\ntime_utc,category,impact\n"
    with pytest.raises(ValueError, match="available_at"):
        load_calendar_asof(write(tmp_path, text), NOW)


@pytest.mark.parametrize(
    "row",
    [
        "2026-11-06T13:30:00,NFP,high,2026-10-01T08:00:00Z",  # time not UTC
        "2026-11-06T13:30:00Z,NFP,high,2026-10-01T08:00:00",  # available_at not UTC
        "2026-11-06T13:30:00Z,NFP,huge,2026-10-01T08:00:00Z",  # impact
        "2026-11-06T13:30:00Z,NFP,high,",  # empty available_at
    ],
)
def test_bad_rows_are_refused(row: str) -> None:
    head = "# coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z\n"
    with pytest.raises(ValueError, match=r"UTC|impact|available_at"):
        parse_calendar_text(head + "time_utc,category,impact,available_at\n" + row + "\n")


def test_old_loader_still_reads_pit_files_and_no_coverage_means_unknown(tmp_path: Path) -> None:
    path = write(tmp_path)
    cal = load_calendar_file(path)
    assert news_blocked(
        cal, datetime(2026, 11, 6, 13, 30, tzinfo=UTC), before_minutes=5, after_minutes=5
    )
    with pytest.raises(CalendarUnavailableError):
        news_blocked(cal, datetime(2027, 3, 1, tzinfo=UTC), before_minutes=5, after_minutes=5)


def test_local_provider_and_source_dispatch(tmp_path: Path) -> None:
    path = write(tmp_path)
    assert LocalFileProvider(path).fetch_text() == DOC
    with pytest.raises(CalendarProviderError):
        LocalFileProvider(tmp_path / "nope.csv").fetch_text()
    assert isinstance(provider_from_source(str(path)), LocalFileProvider)
    assert isinstance(provider_from_source("https://example.invalid/cal.csv"), HttpsCsvProvider)


def test_https_provider_requires_https_and_hides_url_in_errors() -> None:
    with pytest.raises(CalendarProviderError):
        HttpsCsvProvider("http://example.invalid/x.csv")

    def boom(url: str, timeout: float) -> bytes:
        raise OSError(url)

    with pytest.raises(CalendarProviderError) as err:
        HttpsCsvProvider("https://example.invalid/x.csv?key=SECRET", opener=boom).fetch_text()
    assert "SECRET" not in str(err.value)
    ok = HttpsCsvProvider("https://example.invalid/x.csv", opener=lambda u, t: DOC.encode())
    assert ok.fetch_text() == DOC


def test_update_writes_atomically_and_is_idempotent(tmp_path: Path) -> None:
    src = write(tmp_path, name="src.csv")
    out = tmp_path / "out" / "calendar.csv"
    first = update_calendar(LocalFileProvider(src), out, now=NOW)
    assert first.changed
    assert first.events == 2
    assert out.read_text(encoding="utf-8").startswith("# coverage: 2026-10-01T00:00:00Z..")
    assert not list(out.parent.glob("*.tmp"))
    second = update_calendar(LocalFileProvider(src), out, now=NOW + timedelta(days=1))
    assert not second.changed


def test_update_keeps_earliest_available_at_and_extends_coverage(tmp_path: Path) -> None:
    out = tmp_path / "calendar.csv"
    update_calendar(LocalFileProvider(write(tmp_path, name="a.csv")), out, now=NOW)
    later = (
        "# coverage: 2026-10-15T00:00:00Z..2027-03-31T23:59:59Z\n"
        "time_utc,category,impact\n"
        "2026-11-06T13:30:00Z,NFP,high\n"
        "2027-01-08T13:30:00Z,NFP,high\n"
    )
    result = update_calendar(
        LocalFileProvider(write(tmp_path, later, "b.csv")), out, now=NOW + timedelta(days=30)
    )
    assert result.coverage == (
        datetime(2026, 10, 1, tzinfo=UTC),
        datetime(2027, 3, 31, 23, 59, 59, tzinfo=UTC),
    )
    doc = parse_calendar_text(out.read_text(encoding="utf-8"))
    nfp = next(r for r in doc.rows if r.event.time.month == 11)
    assert nfp.available_at == datetime(2026, 10, 1, 8, 0, tzinfo=UTC)  # earliest wins
    assert len(doc.rows) == 3


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("garbage", "source rejected"),
        (
            "# coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z\ntime_utc,category,impact\n",
            "no events",
        ),
        (
            "# coverage: 2026-10-01T00:00:00Z..2026-11-30T23:59:59Z\ntime_utc,category,impact\n"
            "2026-11-06T13:30:00Z,NFP,high\n",
            "shrink",
        ),
        (
            "# coverage: 2028-01-01T00:00:00Z..2028-02-01T00:00:00Z\ntime_utc,category,impact\n"
            "2028-01-06T13:30:00Z,NFP,high\n",
            "gap",
        ),
    ],
)
def test_bad_updates_are_refused_and_leave_the_file_alone(
    tmp_path: Path, text: str, match: str
) -> None:
    out = tmp_path / "calendar.csv"
    update_calendar(LocalFileProvider(write(tmp_path, name="a.csv")), out, now=NOW)
    before = out.read_text(encoding="utf-8")
    with pytest.raises(CalendarUpdateError, match=match):
        update_calendar(LocalFileProvider(write(tmp_path, text, "b.csv")), out, now=NOW)
    assert out.read_text(encoding="utf-8") == before


def test_failed_fetch_leaves_no_file(tmp_path: Path) -> None:
    out = tmp_path / "calendar.csv"
    with pytest.raises(CalendarProviderError):
        update_calendar(LocalFileProvider(tmp_path / "missing.csv"), out, now=NOW)
    assert not out.exists()


def test_coverage_alert_thresholds() -> None:
    assert coverage_alert(NOW + timedelta(days=30), NOW) is None
    assert coverage_alert(NOW + timedelta(days=7), NOW) is None
    warn = coverage_alert(NOW + timedelta(days=6, hours=23), NOW)
    assert warn is not None
    assert (warn.code, warn.severity) == ("NEWS_COVERAGE_ENDING", "warning")
    expired = coverage_alert(NOW - timedelta(days=1), NOW)
    assert expired is not None
    assert expired.severity == "critical"
    none = coverage_alert(None, NOW)
    assert none is not None
    assert none.severity == "critical"


def test_file_alert_for_missing_and_ending_calendar(tmp_path: Path) -> None:
    missing = calendar_file_alert(tmp_path / "x.csv", NOW)
    assert missing is not None
    assert missing.severity == "critical"
    path = write(tmp_path)
    assert calendar_file_alert(path, NOW) is None
    ending = calendar_file_alert(path, datetime(2026, 12, 28, tzinfo=UTC))
    assert ending is not None
    assert ending.severity == "warning"
