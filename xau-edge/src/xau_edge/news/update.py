"""Daily calendar update: fetch, validate, merge point-in-time, write atomically, check coverage.

Fail-closed: a failed or invalid fetch never touches the existing file, and a source that would
shrink the coverage or loses events is refused. Sending alerts is the notifier's job
(``xau_edge.ops.notifier``); this module only returns ``Alert`` objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from xau_edge.execution.status import Alert
from xau_edge.news.pit import (
    CalendarDocument,
    CalendarRow,
    parse_calendar_text,
    render_calendar,
    write_text_atomic,
)
from xau_edge.news.providers import CalendarProvider
from xau_edge.news.status import UPDATE_STATUS_FILE

MIN_COVERAGE_DAYS = 7
NEWS_COVERAGE_CODE = "NEWS_COVERAGE_ENDING"


class CalendarUpdateError(RuntimeError):
    """Raised when an update is refused; the existing file is left untouched."""


@dataclass(frozen=True)
class UpdateResult:
    """What an update wrote."""

    path: Path
    coverage: tuple[datetime, datetime]
    events: int
    added: int
    changed: bool


def merge_documents(
    old: CalendarDocument | None, new: CalendarDocument, *, now: datetime | None = None
) -> CalendarDocument:
    """Union by event identity; the EARLIEST ``available_at`` wins (it is when we first knew).

    A row seen again keeps its first ``ingested_at`` and takes the newest ``updated_at``. With
    ``now`` the fresh document is authoritative for its own window: a FUTURE row of the same source
    that it no longer lists (cancelled or rescheduled) is dropped. Past rows are never dropped.
    """
    fresh_keys = {r.key for r in new.rows}
    by_key: dict[tuple[datetime, str, int], CalendarRow] = {}
    for row in [*(old.rows if old else ()), *new.rows]:
        kept = by_key.get(row.key)
        if kept is None:
            by_key[row.key] = row
            continue
        first, last = (row, kept) if row.available_at < kept.available_at else (kept, row)
        meta = last.meta
        if meta is not None and first.meta is not None:
            meta = replace(meta, ingested_at=first.meta.ingested_at or meta.ingested_at)
        by_key[row.key] = CalendarRow(first.event, first.available_at, meta)
    start, end = new.coverage
    if old is not None:
        if old.coverage[0] <= end and start <= old.coverage[1]:  # overlapping or touching
            start, end = min(start, old.coverage[0]), max(end, old.coverage[1])
        else:
            msg = "the new coverage does not overlap the existing one; refusing to create a gap"
            raise CalendarUpdateError(msg)

    def cancelled(row: CalendarRow) -> bool:
        return (
            now is not None
            and row.key not in fresh_keys
            and row.event.time > now
            and new.coverage[0] <= row.event.time <= new.coverage[1]
            and row.meta is not None
            and bool(row.meta.source)
            and any(r.meta is not None and r.meta.source == row.meta.source for r in new.rows)
        )

    rows = tuple(r for r in by_key.values() if start <= r.event.time <= end and not cancelled(r))
    return CalendarDocument((start, end), rows)


def update_calendar(
    provider: CalendarProvider,
    out_path: Path | str,
    *,
    now: datetime | None = None,
    allow_empty: bool = False,
) -> UpdateResult:
    """Fetch from ``provider`` and merge into ``out_path`` atomically."""
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    target = Path(out_path)
    try:
        text = provider.fetch_text()
        fetched = parse_calendar_text(text, default_available_at=stamp)
    except (ValueError, OSError) as exc:
        msg = f"source rejected: {exc}"
        raise CalendarUpdateError(msg) from exc
    if not fetched.rows and not allow_empty:
        msg = "the source has no events; an empty calendar is more likely a broken feed"
        raise CalendarUpdateError(msg)
    old: CalendarDocument | None = None
    if target.exists():
        try:
            old = parse_calendar_text(
                target.read_text(encoding="utf-8"), default_available_at=stamp
            )
        except ValueError as exc:
            msg = f"the existing {target} is unreadable ({exc}); fix or move it first"
            raise CalendarUpdateError(msg) from exc
        if fetched.coverage[1] < old.coverage[1]:
            msg = "the source ends before the existing calendar; refusing to shrink the coverage"
            raise CalendarUpdateError(msg)
    merged = merge_documents(old, fetched, now=stamp)
    new_text = render_calendar(merged.coverage, merged.rows)
    changed = old is None or new_text != render_calendar(old.coverage, old.rows)
    if changed:
        write_text_atomic(target, new_text)
    added = len(merged.rows) - (len(old.rows) if old else 0)
    return UpdateResult(target, merged.coverage, len(merged.rows), added, changed)


def record_update(
    calendar_path: Path | str,
    *,
    now: datetime,
    ok: bool,
    source: str | None,
    result: UpdateResult | None = None,
    error: str | None = None,
) -> None:
    """Leave the outcome of this run next to the calendar so the API can show a failed update."""
    path = Path(calendar_path)
    previous: dict[str, object] = {}
    try:
        loaded = json.loads((path.parent / UPDATE_STATUS_FILE).read_text(encoding="utf-8"))
        previous = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        previous = {}
    stamp = now.astimezone(UTC).isoformat()
    record: dict[str, object] = {
        "last_attempt_at": stamp,
        "ok": ok,
        "source": source or previous.get("source"),
        "error": error,
        "last_success_at": stamp if ok else previous.get("last_success_at"),
        "events": result.events if result else previous.get("events"),
        "added": result.added if result else 0,
    }
    write_text_atomic(path.parent / UPDATE_STATUS_FILE, json.dumps(record, indent=1) + "\n")


def coverage_alert(
    coverage_end: datetime | None,
    now: datetime,
    *,
    min_days: float = MIN_COVERAGE_DAYS,
) -> Alert | None:
    """An alert when less than ``min_days`` of coverage remain (critical once it has expired)."""
    if coverage_end is None:
        return Alert(NEWS_COVERAGE_CODE, "critical", "no news calendar loaded; signals stay WAIT")
    remaining = coverage_end - now
    if remaining <= timedelta(0):
        return Alert(
            NEWS_COVERAGE_CODE,
            "critical",
            f"news calendar coverage ended {-remaining.total_seconds() / 86400:.1f} days ago",
        )
    if remaining < timedelta(days=min_days):
        return Alert(
            NEWS_COVERAGE_CODE,
            "warning",
            f"news calendar coverage ends in {remaining.total_seconds() / 86400:.1f} days "
            f"(minimum {min_days:g})",
        )
    return None


def calendar_file_alert(
    path: Path | str, now: datetime, *, min_days: float = MIN_COVERAGE_DAYS
) -> Alert | None:
    """``coverage_alert`` for a file on disk; a missing or unreadable file is critical."""
    try:
        doc = parse_calendar_text(Path(path).read_text(encoding="utf-8"), default_available_at=now)
    except (OSError, ValueError) as exc:
        return Alert(NEWS_COVERAGE_CODE, "critical", f"news calendar unreadable: {exc}")
    return coverage_alert(doc.coverage[1], now, min_days=min_days)
