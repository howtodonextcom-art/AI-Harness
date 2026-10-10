"""What the news guard can honestly say right now: one canonical state plus the evidence.

States (what a trader reads):

* ``CLEAR``          the calendar covers the whole window around now, is fresh, and no high-impact
                     event is inside it.
* ``BLOCKED``        a high-impact event is inside ``[now - after, now + before]``.
* ``UNKNOWN``        a calendar exists but does not cover the window around now (yet).
* ``NOT_CONFIGURED`` no calendar path is configured at all.
* ``STALE``          the calendar is readable but its coverage is ending/ended or it has not been
                     refreshed for ``STALE_AFTER``: it can no longer prove "no event".
* ``ERROR``          the calendar file is missing, unreadable, malformed or lists a row that was
                     published after now (look-ahead: a bad file or a wrong clock).

Only CLEAR is ever a green light. ``strategy_state`` folds the states the baseline already knows
(CLEAR / BLOCKED / UNKNOWN): every non-CLEAR, non-BLOCKED state is UNKNOWN there, so the strategy is
unchanged by this module.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from xau_edge.news.calendar import EventImpact
from xau_edge.news.pit import CalendarDocument, CalendarRow, format_utc, parse_calendar_text

STALE_AFTER = timedelta(hours=48)
UPDATE_STATUS_FILE = "update_status.json"
BEFORE_MINUTES = 30
AFTER_MINUTES = 15
UPCOMING_HOURS = 24
UPCOMING_LIMIT = 6

STATES = ("CLEAR", "BLOCKED", "UNKNOWN", "NOT_CONFIGURED", "STALE", "ERROR")


def strategy_state(state: str) -> str:
    """The three-valued input the baseline understands."""
    return state if state in ("CLEAR", "BLOCKED") else "UNKNOWN"


def _event(row: CalendarRow, now: datetime) -> dict[str, Any]:
    return {
        "time": format_utc(row.event.time),
        "title": row.event.category,
        "currency": row.meta.currency if row.meta else "",
        "impact": row.event.impact.name.lower(),
        "minutes_to": round((row.event.time - now).total_seconds() / 60),
    }


def read_update_status(path: Path) -> dict[str, Any] | None:
    """The last updater run (``update_status.json`` next to the calendar), if readable."""
    try:
        data = json.loads((path.parent / UPDATE_STATUS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def empty_status(state: str, detail: str | None = None) -> dict[str, Any]:
    """A status with every key present and nothing known."""
    return _result(state, detail or "")


def _result(state: str, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "state": state,
        "detail": detail,
        "coverage": None,
        "last_updated_at": None,
        "source": None,
        "next_events": [],
        "blocked_by": None,
        "last_update": None,
        **extra,
    }


def news_status(
    now: datetime,
    calendar_path: Path | str | None,
    *,
    before_minutes: int = BEFORE_MINUTES,
    after_minutes: int = AFTER_MINUTES,
) -> dict[str, Any]:
    """The canonical news state at ``now`` with coverage, freshness and the next events."""
    now = now.astimezone(UTC)
    if not calendar_path:
        return _result("NOT_CONFIGURED", "no economic calendar is configured")
    path = Path(calendar_path)
    try:
        doc = parse_calendar_text(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _result("ERROR", "the calendar file does not exist: run scripts/news_update.py")
    except (OSError, ValueError) as exc:
        return _result("ERROR", f"the calendar file is unreadable ({type(exc).__name__})")
    update = read_update_status(path)
    base: dict[str, Any] = {
        "coverage": {"from": format_utc(doc.coverage[0]), "to": format_utc(doc.coverage[1])},
        "last_update": update,
    }
    future = [r for r in doc.rows if r.available_at > now]
    if future:
        return _result(
            "ERROR",
            f"{len(future)} row(s) were published after now: bad file or wrong clock",
            **base,
        )
    stamps = [
        t
        for r in doc.rows
        for t in ((r.meta.updated_at or r.meta.ingested_at) if r.meta else r.available_at,)
        if t is not None
    ]
    last = max(stamps) if stamps else None
    sources = sorted({r.meta.source for r in doc.rows if r.meta and r.meta.source})
    base |= {
        "last_updated_at": format_utc(last) if last else None,
        "source": ", ".join(sources) or None,
    }
    return _judge(doc, base, last, now, (before_minutes, after_minutes))


def _judge(
    doc: CalendarDocument,
    base: dict[str, Any],
    last: datetime | None,
    now: datetime,
    window: tuple[int, int],
) -> dict[str, Any]:
    """Coverage, freshness and the high-impact window, in that order."""
    before_minutes, after_minutes = window
    lo, hi = doc.coverage
    window_start = now - timedelta(minutes=after_minutes)
    window_end = now + timedelta(minutes=before_minutes)
    horizon = now + timedelta(hours=UPCOMING_HOURS)
    upcoming = sorted(
        (
            r
            for r in doc.rows
            if r.event.impact >= EventImpact.MEDIUM and now <= r.event.time <= horizon
        ),
        key=lambda r: r.event.time,
    )
    base["next_events"] = [_event(r, now) for r in upcoming[:UPCOMING_LIMIT]]
    if window_start < lo:
        return _result("UNKNOWN", "the calendar does not start before now", **base)
    if window_end > hi:
        ended = "has ended" if now >= hi else "ends inside the news window"
        return _result("STALE", f"the calendar coverage {ended}", **base)
    if last is None or now - last > STALE_AFTER:
        ago = "never" if last is None else f"{(now - last).total_seconds() / 3600:.0f} h ago"
        return _result("STALE", f"the calendar was last refreshed {ago}", **base)
    inside = [
        r
        for r in doc.rows
        if r.event.impact >= EventImpact.HIGH and window_start <= r.event.time <= window_end
    ]
    if inside:
        first = min(inside, key=lambda r: r.event.time)
        base["blocked_by"] = _event(first, now)
        return _result("BLOCKED", "a high-impact event is inside the news window", **base)
    return _result("CLEAR", "no high-impact event inside the news window", **base)
