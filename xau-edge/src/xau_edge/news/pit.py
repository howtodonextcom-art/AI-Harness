"""Point-in-time (PIT) calendar file: events carry ``available_at`` to prevent leakage.

File format (UTF-8)::

    # coverage: 2026-10-01T00:00:00Z..2026-12-31T23:59:59Z
    time_utc,category,impact,available_at
    2026-11-06T13:30:00Z,NFP,high,2026-10-20T08:00:00Z

``available_at`` is when WE could first have known about the event (publication or fetch time of
the schedule). A decision taken at time ``t`` may only use rows with ``available_at <= t``. The
file stays readable by the older ``load_calendar_file`` (it ignores the extra column).
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from xau_edge.news.calendar import (
    COVERAGE_PREFIX,
    EventImpact,
    NewsEvent,
    StaticCalendar,
)

HEADER = ("time_utc", "category", "impact", "available_at")
META_HEADER = (*HEADER, "currency", "source", "published_at", "ingested_at", "updated_at")
FutureRows = Literal["raise", "drop"]


class CalendarLeakageError(ValueError):
    """Raised when a row is only available after the decision time (look-ahead)."""


@dataclass(frozen=True)
class RowMeta:
    """Where a row came from and when we last saw it (all optional, all point-in-time).

    ``published_at``: when the SOURCE published the row (empty when the source does not say).
    ``ingested_at``: when we first stored it. ``updated_at``: the last fetch that confirmed it.
    """

    currency: str = ""
    source: str = ""
    published_at: datetime | None = None
    ingested_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class CalendarRow:
    """One event plus the time it became known."""

    event: NewsEvent
    available_at: datetime
    meta: RowMeta | None = None

    @property
    def key(self) -> tuple[datetime, str, int]:
        """Identity of the event (the same event re-published keeps its earliest availability)."""
        return (self.event.time, self.event.category, int(self.event.impact))


@dataclass(frozen=True)
class CalendarDocument:
    """A parsed PIT file."""

    coverage: tuple[datetime, datetime]
    rows: tuple[CalendarRow, ...]


def parse_utc(raw: str, label: str) -> datetime:
    """Parse ``YYYY-MM-DDTHH:MM:SSZ``; anything not explicitly UTC is refused."""
    text = raw.strip()
    if not text.endswith("Z"):
        msg = f"{label} must be UTC and end in Z, got {raw!r}"
        raise ValueError(msg)
    try:
        return datetime.fromisoformat(text[:-1]).replace(tzinfo=UTC)
    except ValueError:
        msg = f"{label} is not an ISO timestamp: {raw!r}"
        raise ValueError(msg) from None


def format_utc(value: datetime) -> str:
    """Inverse of ``parse_utc`` (second precision)."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_coverage_line(first: str) -> tuple[datetime, datetime]:
    """Parse ``# coverage: <start>Z..<end>Z``."""
    if not first.startswith(COVERAGE_PREFIX):
        msg = f"the first line must be '{COVERAGE_PREFIX} <start>Z..<end>Z'"
        raise ValueError(msg)
    parts = first[len(COVERAGE_PREFIX) :].strip().split("..")
    if len(parts) != 2:
        msg = "the coverage line must look like '# coverage: <start>Z..<end>Z' (ISO, UTC)"
        raise ValueError(msg)
    start, end = parse_utc(parts[0], "coverage start"), parse_utc(parts[1], "coverage end")
    if start >= end:
        msg = "the coverage start must be before its end"
        raise ValueError(msg)
    return start, end


def parse_calendar_text(
    text: str, *, default_available_at: datetime | None = None
) -> CalendarDocument:
    """Parse a calendar document.

    Rows without an ``available_at`` value are refused unless ``default_available_at`` is given
    (the update job passes the fetch time: honest, because that is when we first saw the row).
    """
    first, _, rest = text.lstrip("﻿").partition("\n")
    coverage = parse_coverage_line(first.strip())
    reader = csv.DictReader(io.StringIO(rest))
    fields = set(reader.fieldnames or [])
    missing = {"time_utc", "category", "impact"} - fields
    if missing:
        msg = f"missing column(s): {', '.join(sorted(missing))}"
        raise ValueError(msg)
    if "available_at" not in fields and default_available_at is None:
        msg = "the calendar has no available_at column; cannot prove it is free of look-ahead"
        raise ValueError(msg)
    rows: list[CalendarRow] = []
    for line in reader:
        try:
            impact = EventImpact[line["impact"].strip().upper()]
        except KeyError:
            msg = f"unknown impact {line['impact']!r}; use low, medium or high"
            raise ValueError(msg) from None
        when = parse_utc(line["time_utc"], "time_utc")
        raw_avail = (line.get("available_at") or "").strip()
        if raw_avail:
            available = parse_utc(raw_avail, "available_at")
        elif default_available_at is not None:
            available = default_available_at
        else:
            msg = f"row {line['time_utc']!r} has an empty available_at"
            raise ValueError(msg)
        meta = _read_meta(line)
        if meta is not None and default_available_at is not None:
            meta = replace(
                meta,
                ingested_at=meta.ingested_at or default_available_at,
                updated_at=meta.updated_at or default_available_at,
            )
        rows.append(CalendarRow(NewsEvent(when, line["category"].strip(), impact), available, meta))
    return CalendarDocument(coverage, tuple(rows))


def _optional_utc(raw: str | None, label: str) -> datetime | None:
    text = (raw or "").strip()
    return parse_utc(text, label) if text else None


def _read_meta(line: dict[str, str]) -> RowMeta | None:
    """The optional provenance columns of a row (None for a legacy four-column file)."""
    if not any(name in line for name in META_HEADER[4:]):
        return None
    return RowMeta(
        currency=(line.get("currency") or "").strip(),
        source=(line.get("source") or "").strip(),
        published_at=_optional_utc(line.get("published_at"), "published_at"),
        ingested_at=_optional_utc(line.get("ingested_at"), "ingested_at"),
        updated_at=_optional_utc(line.get("updated_at"), "updated_at"),
    )


def load_calendar_asof(
    path: Path | str,
    decision_time: datetime,
    *,
    future_rows: FutureRows = "raise",
) -> StaticCalendar:
    """Load a PIT calendar as it was known at ``decision_time``.

    A row with ``available_at > decision_time`` is look-ahead. ``future_rows="raise"`` (live
    default) refuses the whole file with ``CalendarLeakageError``: for a live bot it means a bad
    file or a wrong clock. ``"drop"`` hides those rows, which is what a backtest replaying the past
    needs.
    """
    if decision_time.tzinfo is None:
        msg = "decision_time must carry a timezone (UTC)"
        raise ValueError(msg)
    doc = parse_calendar_text(Path(path).read_text(encoding="utf-8"))
    visible: list[NewsEvent] = []
    for row in doc.rows:
        if row.available_at > decision_time:
            if future_rows == "raise":
                msg = (
                    f"event {format_utc(row.event.time)} {row.event.category!r} became available "
                    f"at {format_utc(row.available_at)}, after the decision time "
                    f"{format_utc(decision_time)}"
                )
                raise CalendarLeakageError(msg)
            continue
        visible.append(row.event)
    return StaticCalendar(visible, coverage=doc.coverage)


def render_calendar(coverage: tuple[datetime, datetime], rows: Iterable[CalendarRow]) -> str:
    """Canonical text: coverage line, header, rows sorted by time then category.

    The provenance columns are written only when at least one row carries them, so a legacy file
    stays byte-identical.
    """
    ordered = sorted(rows, key=lambda r: (r.event.time, r.event.category))
    with_meta = any(r.meta is not None for r in ordered)
    out = io.StringIO()
    out.write(f"{COVERAGE_PREFIX} {format_utc(coverage[0])}..{format_utc(coverage[1])}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(META_HEADER if with_meta else HEADER)
    for row in ordered:
        cells = [
            format_utc(row.event.time),
            row.event.category,
            row.event.impact.name.lower(),
            format_utc(row.available_at),
        ]
        if with_meta:
            meta = row.meta or RowMeta()
            cells += [
                meta.currency,
                meta.source,
                *(format_utc(t) if t else "" for t in (meta.published_at, meta.ingested_at)),
                format_utc(meta.updated_at) if meta.updated_at else "",
            ]
        writer.writerow(cells)
    return out.getvalue()


def write_text_atomic(path: Path | str, text: str) -> None:
    """Write via a temp file in the same folder, fsync, then ``os.replace`` (all or nothing)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(target)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
