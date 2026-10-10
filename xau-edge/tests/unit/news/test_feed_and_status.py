"""The Forex Factory weekly provider, provenance columns, and the canonical news states."""

from __future__ import annotations

import io
import json
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from xau_edge.news.forexfactory import ForexFactoryProvider, convert, week_bounds
from xau_edge.news.pit import parse_calendar_text
from xau_edge.news.providers import CalendarProviderError, provider_from_source
from xau_edge.news.status import STATES, news_status, strategy_state
from xau_edge.news.update import record_update, update_calendar

pytestmark = pytest.mark.unit


def row(title: str, country: str, date: str, impact: str) -> dict[str, str]:
    return {"title": title, "country": country, "date": date, "impact": impact}


FEED = [
    row("FOMC Meeting Minutes", "USD", "2026-10-07T14:00:00-04:00", "High"),
    row("CPI m/m", "USD", "2026-10-08T08:30:00-04:00", "High"),
    row("Unemployment Claims", "USD", "2026-10-08T08:30:00-04:00", "Medium"),
    row("German Factory Orders", "EUR", "2026-10-08T02:00:00-04:00", "High"),
    row("OPEC-JMMC Meetings", "All", "2026-10-04T05:15:00-04:00", "Medium"),
    row("Bank Holiday", "USD", "2026-10-05T00:00:00-04:00", "Holiday"),
]
FETCH = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)


def opener(feeds: dict[str, object]) -> Callable[[str, float], bytes]:
    def read(url: str, timeout: float) -> bytes:
        for week, payload in feeds.items():
            if url.endswith(f"ff_calendar_{week}.json"):
                if isinstance(payload, Exception):
                    raise payload
                return json.dumps(payload).encode()
        raise AssertionError(url)

    return read


def http_error(code: int, retry: str | None = None) -> urllib.error.HTTPError:
    headers = Message()
    if retry:
        headers["Retry-After"] = retry
    return urllib.error.HTTPError("u", code, "x", headers, io.BytesIO(b""))


def provider(this_week: object, next_week: object | None = None) -> ForexFactoryProvider:
    return ForexFactoryProvider(
        opener=opener({"thisweek": this_week, "nextweek": next_week or http_error(404)})
    )


def test_the_feed_becomes_a_usd_only_point_in_time_document() -> None:
    text, kept = convert(FEED, ("USD", "All"))
    doc = parse_calendar_text(text, default_available_at=FETCH)
    assert kept == 4  # the EUR event and the holiday are out of scope
    titles = {r.event.category for r in doc.rows}
    assert titles == {
        "FOMC Meeting Minutes",
        "CPI m/m",
        "Unemployment Claims",
        "OPEC-JMMC Meetings",
    }
    cpi = next(r for r in doc.rows if r.event.category == "CPI m/m")
    assert cpi.event.time == datetime(2026, 10, 8, 12, 30, tzinfo=UTC)  # 08:30 New York in EDT
    assert cpi.meta is not None and cpi.meta.currency == "USD"
    assert cpi.meta.source == "forexfactory-weekly" and cpi.meta.ingested_at == FETCH


def test_the_declared_coverage_is_the_feed_week_in_new_york_time() -> None:
    start, end = week_bounds(datetime(2026, 10, 8, 12, 30, tzinfo=UTC))
    assert start == datetime(2026, 10, 4, 4, 0, tzinfo=UTC)  # Sunday 00:00 EDT
    assert end - start == timedelta(days=7)
    winter = week_bounds(datetime(2026, 11, 3, 12, 0, tzinfo=UTC))  # the week DST ends
    assert winter[1] - winter[0] == timedelta(days=7, hours=1)


def test_a_missing_next_week_is_fine_but_a_failed_this_week_is_not() -> None:
    assert parse_calendar_text(provider(FEED).fetch_text(), default_available_at=FETCH).rows
    limited = ForexFactoryProvider(opener=opener({"thisweek": http_error(429, "120")}))
    with pytest.raises(CalendarProviderError, match=r"HTTP 429, retry after 120s"):
        limited.fetch_text()
    junk = ForexFactoryProvider(opener=lambda _u, _t: b"<html>nope</html>")
    with pytest.raises(CalendarProviderError, match="not JSON"):
        junk.fetch_text()


def test_forexfactory_is_a_named_source() -> None:
    assert isinstance(provider_from_source("forexfactory"), ForexFactoryProvider)


def test_two_weeks_join_into_one_contiguous_coverage() -> None:
    nxt = [row("Next CPI", "USD", "2026-10-15T08:30:00-04:00", "High")]
    doc = parse_calendar_text(provider(FEED, nxt).fetch_text(), default_available_at=FETCH)
    assert doc.coverage[1] - doc.coverage[0] == timedelta(days=14)
    assert "Next CPI" in {r.event.category for r in doc.rows}


def test_an_update_keeps_first_seen_and_drops_a_cancelled_future_event(tmp_path: Path) -> None:
    out = tmp_path / "calendar.csv"
    update_calendar(provider(FEED), out, now=FETCH)
    later = FETCH + timedelta(days=1)
    update_calendar(provider([e for e in FEED if e["title"] != "CPI m/m"]), out, now=later)
    doc = parse_calendar_text(out.read_text(encoding="utf-8"))
    assert "CPI m/m" not in {r.event.category for r in doc.rows}  # future and no longer listed
    minutes = next(r for r in doc.rows if r.event.category == "FOMC Meeting Minutes")
    assert minutes.available_at == FETCH  # first seen, not re-stamped
    assert minutes.meta is not None
    assert minutes.meta.ingested_at == FETCH and minutes.meta.updated_at == later
    # a row already in the past is history and stays even when the feed forgets it
    update_calendar(provider([FEED[4]]), out, now=datetime(2026, 10, 9, 6, 0, tzinfo=UTC))
    kept = {r.event.category for r in parse_calendar_text(out.read_text(encoding="utf-8")).rows}
    assert "FOMC Meeting Minutes" in kept


def calendar(tmp_path: Path, fetched: datetime = FETCH) -> Path:
    out = tmp_path / "news" / "calendar.csv"
    update_calendar(provider(FEED), out, now=fetched)
    return out


def test_every_state_is_reachable_and_only_clear_is_green(tmp_path: Path) -> None:
    out = calendar(tmp_path)
    clear_at = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
    assert news_status(clear_at, out)["state"] == "CLEAR"
    # CPI at 12:30 UTC: blocked from 30 minutes before to 15 minutes after
    morning = datetime(2026, 10, 8, 6, 0, tzinfo=UTC)
    fresh = calendar(tmp_path / "fresh", morning)  # refreshed the same morning
    blocked = news_status(datetime(2026, 10, 8, 12, 5, tzinfo=UTC), fresh)
    assert blocked["state"] == "BLOCKED" and blocked["blocked_by"]["title"] == "CPI m/m"
    assert news_status(datetime(2026, 10, 8, 12, 46, tzinfo=UTC), fresh)["state"] == "CLEAR"
    assert news_status(clear_at, None)["state"] == "NOT_CONFIGURED"
    assert news_status(clear_at, tmp_path / "missing.csv")["state"] == "ERROR"
    bad = tmp_path / "bad.csv"
    bad.write_text("not a calendar", encoding="utf-8")
    assert news_status(clear_at, bad)["state"] == "ERROR"
    early_file = calendar(tmp_path / "early", datetime(2026, 10, 3, 12, 0, tzinfo=UTC))
    just_after_open = datetime(2026, 10, 4, 4, 5, tzinfo=UTC)  # the window starts before coverage
    assert news_status(just_after_open, early_file)["state"] == "UNKNOWN"
    ended = news_status(datetime(2026, 10, 12, 12, 0, tzinfo=UTC), out)
    assert ended["state"] == "STALE" and "ended" in ended["detail"]
    old = news_status(FETCH + timedelta(days=3), out)  # fetched 3 days ago, week still open
    assert old["state"] == "STALE" and "refreshed" in old["detail"]
    early = news_status(FETCH - timedelta(hours=1), out)  # a row published after "now"
    assert early["state"] == "ERROR" and "published after now" in early["detail"]
    assert set(STATES) == {"CLEAR", "BLOCKED", "UNKNOWN", "NOT_CONFIGURED", "STALE", "ERROR"}


def test_the_baseline_only_sees_clear_blocked_or_unknown() -> None:
    assert [strategy_state(s) for s in STATES] == [
        "CLEAR",
        "BLOCKED",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
    ]


def test_the_next_events_are_listed_with_minutes_to_go(tmp_path: Path) -> None:
    status: dict[str, Any] = news_status(
        datetime(2026, 10, 8, 6, 30, tzinfo=UTC), calendar(tmp_path)
    )
    first = status["next_events"][0]
    assert first["title"] == "CPI m/m" and first["minutes_to"] == 360 and first["currency"] == "USD"
    assert status["source"] == "forexfactory-weekly" and status["last_updated_at"]


def test_a_failed_update_is_recorded_without_losing_the_last_success(tmp_path: Path) -> None:
    out = calendar(tmp_path)
    record_update(out, now=FETCH, ok=True, source="forexfactory")
    failed_at = FETCH + timedelta(hours=1)
    record_update(out, now=failed_at, ok=False, source="forexfactory", error="HTTP 429")
    last = news_status(FETCH + timedelta(hours=2), out)["last_update"]
    assert last["ok"] is False and last["error"] == "HTTP 429"
    assert last["last_success_at"] == FETCH.isoformat()
