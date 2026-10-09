"""Backward backfill: broker floor, terminal cap, resume, repeated boundary, corrupt chunk."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from tests.unit.market_data.test_collector_ledger import DTYPE, NOW, FakeClient, make_feed
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.history_backfill import (
    BROKER_LIMITED,
    COMPLETE,
    INCOMPLETE,
    TERMINAL_LIMITED,
    UNKNOWN,
    backfill_timeframe,
    coverage_gaps,
    validate_chunk,
)
from xau_edge.market_data.ledger import BarLedger

TF = Timeframe.M5
STEP = timedelta(minutes=5)
FLOOR = datetime(2026, 1, 1, tzinfo=UTC)


class DepthClient(FakeClient):
    """A terminal holding M5 bars from ``floor`` (broker limit) with an optional bar-count cap."""

    def __init__(
        self,
        floor: datetime = FLOOR,
        cap: int | None = None,
        *,
        same_bars: bool = False,
        pos_limit: int | None = None,
    ) -> None:
        super().__init__()
        self.floor = floor
        self.cap = cap
        self.same_bars = same_bars
        self.pos_limit = pos_limit
        self.corrupt_before: datetime | None = None

    def _last_open(self) -> datetime:
        slots = int((self.now - self.floor) / STEP)
        return self.floor + STEP * slots

    def _rates(self, start: datetime, end: datetime) -> Any:
        rows = []
        t = start
        while t <= end:
            slot = int(t.timestamp() // 300)
            base = 2000.0 + (slot % 400) * 0.1
            low = base - 1
            if self.corrupt_before is not None and t < self.corrupt_before:
                low = base + 5  # low above the close: an invalid bar
            rows.append(
                (int(t.timestamp()), base, base + 1, low, base + 0.5, 50 + slot % 20, 20, 0)
            )
            t += STEP
        return np.array(rows, dtype=DTYPE)

    def copy_rates_from_pos(self, symbol: str, tf: int, pos: int, count: int) -> Any:
        last = self._last_open()
        count = min(count, self.cap) if self.cap else count
        count = min(count, self.pos_limit) if self.pos_limit else count
        start = max(self.floor, last - STEP * (count - 1))
        return self._rates(start, last)

    def copy_rates_from(self, symbol: str, tf: int, date_to: datetime, count: int) -> Any:
        if self.same_bars:
            return self._rates(self.floor, self.floor + STEP * 9)
        if self.cap:
            depth_floor = self._last_open() - STEP * (self.cap - 1)
            if date_to.replace(tzinfo=None) < depth_floor.replace(tzinfo=None):
                return None  # "Terminal: Call failed"
        end = min(date_to, self._last_open())
        start = max(self.floor, end - STEP * (count - 1))
        if end < self.floor:
            return np.array([], dtype=DTYPE)
        return self._rates(start, end)


def run(
    tmp_path: Path,
    client: DepthClient,
    *,
    since: datetime,
    max_bars: int | None,
    chunk: int = 500,
    max_chunks: int = 50,
) -> Any:
    feed = make_feed(client)
    return backfill_timeframe(
        feed,
        BarLedger(tmp_path),
        symbol="XAUUSD",
        broker_symbol="XAUUSD",
        timeframe=TF,
        requested_oldest=since,
        max_bars=max_bars,
        now=client.now,
        chunk=chunk,
        max_chunks=max_chunks,
    )


def test_broker_floor_is_found_and_classified_broker_limited(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, pos_limit=1000)
    result = run(
        tmp_path, client, since=datetime(2003, 1, 1, tzinfo=UTC), max_bars=100_000_000, chunk=1000
    )
    assert result.state == BROKER_LIMITED
    assert result.complete
    assert result.local_oldest == FLOOR.isoformat()
    expected = int((client._last_open() - FLOOR) / STEP)
    assert result.rows == expected  # every closed bar up to the forming one
    assert result.chunks > 2  # it really walked backward in pieces
    assert "no earlier bars" in result.reason


def test_terminal_cap_is_classified_terminal_limited_and_not_complete(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, cap=3000)
    result = run(tmp_path, client, since=datetime(2003, 1, 1, tzinfo=UTC), max_bars=3001)
    assert result.state == TERMINAL_LIMITED
    assert not result.complete
    assert 2900 <= result.rows <= 3001
    assert "Max bars in chart" in result.reason


def test_reaching_the_requested_start_is_complete(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR)
    result = run(tmp_path, client, since=FLOOR + timedelta(days=3), max_bars=100_000_000)
    assert result.state == COMPLETE


def test_interrupted_run_resumes_and_a_third_run_adds_nothing(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, pos_limit=500)
    since = datetime(2003, 1, 1, tzinfo=UTC)
    first = run(tmp_path, client, since=since, max_bars=100_000_000, chunk=500, max_chunks=3)
    assert first.state == INCOMPLETE
    second = run(tmp_path, client, since=since, max_bars=100_000_000, chunk=500, max_chunks=200)
    assert second.state == BROKER_LIMITED
    assert second.rows > first.rows
    third = run(tmp_path, client, since=since, max_bars=100_000_000, chunk=500, max_chunks=200)
    assert third.new_rows == 0
    assert third.rows == second.rows


def test_repeated_boundary_cannot_loop_forever(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, same_bars=True)
    result = run(tmp_path, client, since=datetime(2003, 1, 1, tzinfo=UTC), max_bars=100_000_000)
    assert result.state in {BROKER_LIMITED, UNKNOWN, INCOMPLETE}
    assert result.chunks <= 3  # newest + at most one more answer, then it stops


def test_invalid_chunk_is_not_stored_and_run_is_incomplete(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, pos_limit=500)
    client.corrupt_before = FLOOR + timedelta(days=40)
    result = run(
        tmp_path, client, since=datetime(2003, 1, 1, tzinfo=UTC), max_bars=100_000_000, chunk=200
    )
    assert result.state == INCOMPLETE
    assert "invalid" in result.reason
    stored = BarLedger(tmp_path).load("XAUUSD", TF)
    assert stored.height > 0
    assert validate_chunk(stored) == []  # nothing corrupt reached the ledger


def test_chunk_events_carry_provenance_hashes(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR, pos_limit=1000)
    run(tmp_path, client, since=datetime(2003, 1, 1, tzinfo=UTC), max_bars=100_000_000, chunk=1000)
    events = [e for e in BarLedger(tmp_path).events("XAUUSD") if e["kind"] == "BACKFILL_CHUNK"]
    assert events
    assert all(len(e["sha256"]) == 64 for e in events)
    assert {e["phase"] for e in events} >= {"newest", "backward"}


def test_coverage_gaps_reports_largest_holes(tmp_path: Path) -> None:
    client = DepthClient(floor=FLOOR)
    run(tmp_path, client, since=FLOOR, max_bars=None)
    frame = BarLedger(tmp_path).load("XAUUSD", TF)
    assert coverage_gaps(frame, TF) == []
    holed = frame.filter(
        (frame["timestamp"] < FLOOR + timedelta(days=1))
        | (frame["timestamp"] > FLOOR + timedelta(days=2))
    )
    gaps = coverage_gaps(holed, TF)
    assert len(gaps) == 1
    assert 23 <= gaps[0]["hours"] <= 25
    assert NOW.year == 2026
