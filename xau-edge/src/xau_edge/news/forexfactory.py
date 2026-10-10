"""Forex Factory weekly calendar feed (the community JSON the site publishes) as a provider.

Chosen by the rubric in ``docs/reports/NEWS_SOURCE_DECISION.md``: it is the only candidate that is
free, needs no key, carries an explicit UTC offset on every event and a High/Medium/Low impact. Its
limits are part of the design and are NOT hidden:

* it is an unofficial feed (no SLA, no published terms for automated use): it is a decision AID, the
  trader still owns the news check;
* it publishes the CURRENT week only (next week appears late in the current one), so the declared
  coverage is that week and the state turns STALE once it ends, never CLEAR;
* it has no publish/update timestamps: ``available_at`` is therefore OUR first fetch of the row.

Output is a point-in-time document in the ``news/pit.py`` format, scoped to ``currencies`` (gold is
quoted in USD: USD and the global "All" events by default).
"""

from __future__ import annotations

import json
import urllib.error
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from xau_edge.news.calendar import COVERAGE_PREFIX
from xau_edge.news.pit import HEADER, format_utc
from xau_edge.news.providers import (
    MAX_BYTES,
    CalendarProviderError,
    _urlopen_read,
)

SOURCE_NAME = "forexfactory-weekly"
BASE_URL = "https://nfs.faireconomy.media/ff_calendar_{week}.json"
WEEKS = ("thisweek", "nextweek")
DEFAULT_CURRENCIES = ("USD", "All")
IMPACTS = {"high": "high", "medium": "medium", "low": "low"}  # "Holiday" has no market impact
_NY = ZoneInfo("America/New_York")
_COLUMNS = (*HEADER, "currency", "source")


def week_bounds(moment: datetime) -> tuple[datetime, datetime]:
    """The feed's week: Sunday 00:00 to the next Sunday 00:00, New York time, as UTC."""
    local = moment.astimezone(_NY)
    sunday = (local - timedelta(days=(local.weekday() + 1) % 7)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    nxt = (sunday + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
    return sunday.astimezone(UTC), nxt.astimezone(UTC)


def _csv_cell(value: str) -> str:
    return '"' + value.replace('"', '""') + '"' if any(c in value for c in ',"\n') else value


def convert(events: list[dict[str, Any]], currencies: tuple[str, ...]) -> tuple[str, int]:
    """One week of feed events to PIT text and the number of rows kept."""
    if not events:
        msg = "the feed returned no events"
        raise CalendarProviderError(msg)
    rows: list[tuple[datetime, str, str, str]] = []
    first: datetime | None = None
    for event in events:
        try:
            when = datetime.fromisoformat(str(event["date"])).astimezone(UTC)
            title, currency = str(event["title"]).strip(), str(event["country"]).strip()
            impact = IMPACTS.get(str(event["impact"]).strip().lower())
        except (KeyError, ValueError) as exc:
            msg = f"unexpected feed row ({type(exc).__name__})"
            raise CalendarProviderError(msg) from None
        first = when if first is None or when < first else first
        if impact is not None and currency in currencies and title:
            rows.append((when, title, impact, currency))
    assert first is not None  # noqa: S101 - events is not empty
    start, end = week_bounds(first)
    lines = [f"{COVERAGE_PREFIX} {format_utc(start)}..{format_utc(end)}", ",".join(_COLUMNS)]
    for when, title, impact, currency in sorted(rows):
        lines.append(
            ",".join([format_utc(when), _csv_cell(title), impact, "", currency, SOURCE_NAME])
        )
    return "\n".join(lines) + "\n", len(rows)


def merge_weeks(texts: list[str]) -> str:
    """Several weekly documents into one (contiguous weeks: coverage is first start..last end)."""
    if len(texts) == 1:
        return texts[0]
    starts, ends, body = [], [], []
    for text in texts:
        head, _, rest = text.partition("\n")
        a, b = head[len(COVERAGE_PREFIX) :].strip().split("..")
        starts.append(a)
        ends.append(b)
        body.extend(rest.splitlines()[1:])
    header = ",".join(_COLUMNS)
    return f"{COVERAGE_PREFIX} {min(starts)}..{max(ends)}\n{header}\n" + "\n".join(body) + "\n"


class ForexFactoryProvider:
    """``CalendarProvider`` over the weekly JSON feed; a missing next week is tolerated."""

    def __init__(
        self,
        *,
        currencies: tuple[str, ...] = DEFAULT_CURRENCIES,
        timeout: float = 20.0,
        opener: Callable[[str, float], bytes] = _urlopen_read,
    ) -> None:
        self.currencies = currencies
        self._timeout = timeout
        self._opener = opener

    def _week(self, week: str) -> list[dict[str, Any]] | None:
        try:
            data = self._opener(BASE_URL.format(week=week), self._timeout)
        except urllib.error.HTTPError as exc:
            exc.close()  # release the response body now, not at garbage collection
            if exc.code == 404 and week != WEEKS[0]:
                return None  # next week is not published yet
            wait = exc.headers.get("Retry-After") if exc.headers else None
            msg = f"download failed (HTTP {exc.code}{f', retry after {wait}s' if wait else ''})"
            raise CalendarProviderError(msg) from None
        except Exception as exc:
            msg = f"download failed ({type(exc).__name__})"
            raise CalendarProviderError(msg) from None
        if len(data) > MAX_BYTES:
            msg = f"download larger than {MAX_BYTES} bytes"
            raise CalendarProviderError(msg)
        try:
            parsed = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            msg = "the feed is not JSON"
            raise CalendarProviderError(msg) from None
        if not isinstance(parsed, list):
            msg = "the feed is not a list of events"
            raise CalendarProviderError(msg)
        return [e for e in parsed if isinstance(e, dict)]

    def fetch_text(self) -> str:
        """This week (required) plus next week (when published), as one PIT document."""
        texts: list[str] = []
        for week in WEEKS:
            events = self._week(week)
            if events is not None:
                texts.append(convert(events, self.currencies)[0])
        return merge_weeks(texts)
