"""Backward, chunked, resumable history backfill with an honest completeness state.

Phase A takes the newest bars with one position-based call (``copy_rates_from_pos``). Phase B walks
BACKWARD from the oldest stored bar with date-based calls (``copy_rates_from``), chunk by chunk,
until nothing older comes back. Every chunk is validated before it is stored, hashed into the event
log (provenance), and appended idempotently, so an interrupted run resumes from the ledger and a
repeat run adds nothing. Loops are bounded: a repeated boundary, an empty answer, a terminal
failure or ``max_chunks`` all end the walk.

Completeness is a STATE, not an assumption:

* ``COMPLETE_AVAILABLE_HISTORY``: the ledger reaches what was asked for (or all the server has);
* ``TERMINAL_LIMITED``: the terminal's "Max bars in chart" cap is the reason nothing older came back
  (fixable by the owner);
* ``BROKER_LIMITED``: the cap is not binding and the terminal/server returned nothing older, i.e.
  the broker simply has no earlier history;
* ``INCOMPLETE``: the walk stopped early (error or chunk budget): run it again;
* ``UNKNOWN``: nothing stored.

Native history is never fabricated: a shallow M1 is not extended from H1, ticks are not inferred.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger
from xau_edge.market_data.mt5.feed import MAX_BARS_PER_CALL, Mt5Feed

CAP_BINDING_FRACTION = 0.98
DEFAULT_CHUNK = 50_000
DEFAULT_MAX_CHUNKS = 400
UNLIMITED_MAX_BARS = 10_000_000

COMPLETE = "COMPLETE_AVAILABLE_HISTORY"
TERMINAL_LIMITED = "TERMINAL_LIMITED"
BROKER_LIMITED = "BROKER_LIMITED"
INCOMPLETE = "INCOMPLETE"
UNKNOWN = "UNKNOWN"


@dataclass
class TimeframeBackfill:
    """The auditable outcome for one timeframe."""

    timeframe: str
    requested_oldest: str
    broker_returned_oldest: str | None
    local_oldest: str | None
    local_latest: str | None
    rows: int
    state: str
    reason: str
    chunks: int = 0
    new_rows: int = 0
    duplicates: int = 0
    changed: int = 0
    terminal_max_bars: int | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        """True when the ledger holds everything the broker can serve right now."""
        return self.state in (COMPLETE, BROKER_LIMITED)

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "complete": self.complete}


def validate_chunk(frame: pl.DataFrame) -> list[str]:
    """Problems that must stop a chunk from being stored (empty list = clean)."""
    if frame.height == 0:
        return []
    problems: list[str] = []
    ts = frame["timestamp"]
    if ts.n_unique() != frame.height:
        problems.append("duplicate timestamps in chunk")
    if not ts.is_sorted():
        problems.append("chunk not sorted")
    bad = frame.filter(
        (pl.col("high") < pl.max_horizontal("open", "close"))
        | (pl.col("low") > pl.min_horizontal("open", "close"))
        | (pl.col("low") <= 0)
        | (pl.col("tick_volume") < 0)
    ).height
    if bad:
        problems.append(f"{bad} bars violate OHLC sanity")
    return problems


def chunk_digest(frame: pl.DataFrame) -> str:
    """SHA-256 over the chunk's canonical values (provenance for the event log)."""
    payload = frame.select("timestamp", "open", "high", "low", "close", "tick_volume").write_csv()
    return hashlib.sha256(payload.encode()).hexdigest()


def _cap_binding(rows: int, max_bars: int | None) -> bool:
    return bool(
        max_bars and max_bars < UNLIMITED_MAX_BARS and rows >= CAP_BINDING_FRACTION * (max_bars - 1)
    )


def backfill_timeframe(  # noqa: PLR0912, PLR0915
    feed: Mt5Feed,
    ledger: BarLedger,
    *,
    symbol: str,
    broker_symbol: str,
    timeframe: Timeframe,
    requested_oldest: datetime,
    max_bars: int | None,
    now: datetime | None = None,
    chunk: int = DEFAULT_CHUNK,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> TimeframeBackfill:
    """Fill ``symbol``/``timeframe`` backward as far as the terminal allows; classify the result."""
    stamp = now or datetime.now(UTC)
    result = TimeframeBackfill(
        timeframe=timeframe.value,
        requested_oldest=requested_oldest.isoformat(),
        broker_returned_oldest=None,
        local_oldest=None,
        local_latest=None,
        rows=0,
        state=UNKNOWN,
        reason="",
        terminal_max_bars=max_bars,
    )
    interrupted = False
    older_empty = False
    walk_failed = False

    def store(frame: pl.DataFrame, reason: str) -> None:
        added = ledger.append_closed(symbol, timeframe, frame, now=stamp, reason=reason)
        result.new_rows += added.new
        result.duplicates += added.duplicates
        result.changed += added.changed

    # Phase A: the newest bars (position based, bounded by the per-call cap).
    count = MAX_BARS_PER_CALL if not max_bars else min(MAX_BARS_PER_CALL, max_bars - 1)
    newest = None
    while count >= 100 and newest is None:
        try:
            newest = feed.latest_bars(broker_symbol, timeframe, count)
        except RuntimeError:
            count //= 2
    if newest is None:
        result.state, result.reason = INCOMPLETE, "the terminal refused every request size"
        return result
    problems = validate_chunk(newest)
    if problems:
        result.state, result.reason = INCOMPLETE, "newest chunk invalid: " + "; ".join(problems)
        return result
    store(newest, "backfill-newest")
    result.chunks += 1
    ledger.log_event(symbol, "BACKFILL_CHUNK", {
        "timeframe": timeframe.value, "phase": "newest", "rows": newest.height,
        "sha256": chunk_digest(newest),
        "first": newest["timestamp"].min(), "last": newest["timestamp"].max(),
    }, now=stamp)  # fmt: skip

    # Phase B: walk backward from the oldest stored bar.
    cursor = ledger.earliest(symbol, timeframe)
    while cursor is not None and cursor > requested_oldest and result.chunks < max_chunks:
        try:
            older = feed.bars_before(broker_symbol, timeframe, cursor, chunk)
        except RuntimeError as exc:
            walk_failed = True
            result.notes.append(f"older request failed: {exc}"[:200])
            break
        if older.height == 0:
            older_empty = True
            break
        first = older["timestamp"].min()
        if not isinstance(first, datetime) or first >= cursor:
            older_empty = True  # repeated boundary: the same bars again means nothing older exists
            result.notes.append("repeated boundary: no progress")
            break
        problems = validate_chunk(older)
        if problems:
            result.state, result.reason = INCOMPLETE, "chunk invalid: " + "; ".join(problems)
            interrupted = True
            break
        store(older, "backfill-backward")
        result.chunks += 1
        ledger.log_event(symbol, "BACKFILL_CHUNK", {
            "timeframe": timeframe.value, "phase": "backward", "rows": older.height,
            "sha256": chunk_digest(older), "first": first, "last": older["timestamp"].max(),
        }, now=stamp)  # fmt: skip
        cursor = first
    else:
        interrupted = (
            cursor is not None and cursor > requested_oldest and result.chunks >= max_chunks
        )

    earliest = ledger.earliest(symbol, timeframe)
    latest = ledger.latest(symbol, timeframe)
    rows = ledger.load(symbol, timeframe).height
    result.local_oldest = None if earliest is None else earliest.isoformat()
    result.local_latest = None if latest is None else latest.isoformat()
    result.rows = rows
    result.broker_returned_oldest = result.local_oldest
    if result.state == INCOMPLETE:
        return result
    if earliest is None:
        result.state, result.reason = UNKNOWN, "nothing stored"
    elif interrupted:
        result.state, result.reason = INCOMPLETE, f"stopped after {max_chunks} chunks: run again"
    elif earliest <= requested_oldest:
        result.state, result.reason = COMPLETE, "the ledger reaches the requested start"
    elif _cap_binding(rows, max_bars) or (
        walk_failed and max_bars and max_bars < UNLIMITED_MAX_BARS
    ):
        result.state = TERMINAL_LIMITED
        result.reason = (
            f"the terminal's 'Max bars in chart' ({max_bars}) caps the history it can serve; "
            "raise it, restart the terminal and rerun"
        )
    elif older_empty or walk_failed:
        result.state = BROKER_LIMITED
        result.reason = (
            "the cap is not binding and nothing older is served: the broker has no earlier bars"
        )
    else:
        result.state, result.reason = UNKNOWN, "walk ended without a conclusive answer"
    return result


def coverage_gaps(
    frame: pl.DataFrame, timeframe: Timeframe, limit: int = 5
) -> list[dict[str, Any]]:
    """The largest holes between consecutive stored bars (before any calendar judgement)."""
    if frame.height < 2:
        return []
    step = timedelta(minutes=timeframe.minutes)
    gaps = (
        frame.select("timestamp", pl.col("timestamp").diff().alias("gap"))
        .filter(pl.col("gap") > step * 2)
        .sort("gap", descending=True)
        .head(limit)
    )
    out = []
    for row in gaps.iter_rows(named=True):
        out.append(
            {
                "after": (row["timestamp"] - row["gap"]).isoformat(),
                "before": row["timestamp"].isoformat(),
                "hours": round(row["gap"].total_seconds() / 3600, 1),
            }
        )
    return out
