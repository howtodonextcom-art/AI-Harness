"""Incremental refresh: fetches only what is missing, never stores a forming bar."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from tests.conftest import MONDAY, make_bars
from xau_edge.domain.bars import BarRequest
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.refresh import OVERLAP_BARS, refresh_market_data
from xau_edge.market_data.store import RawStore


class FakeSource:
    """Serves synthetic bars and remembers the requests."""

    name = "fake"

    def __init__(self) -> None:
        self.requests: list[BarRequest] = []

    def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
        self.requests.append(request)
        n = int((request.end_utc - request.start_utc) / request.timeframe.delta) + 2
        start = request.start_utc.replace(second=0, microsecond=0)
        frame = make_bars(n, request.timeframe, start)
        # like a real terminal, also return the still-forming bar
        return frame.filter(pl.col("timestamp") < request.end_utc + request.timeframe.delta)


def test_the_first_refresh_uses_the_lookback_and_stores_only_closed_bars(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    now = MONDAY + timedelta(hours=6, minutes=7)
    out = refresh_market_data(
        FakeSource(),
        store,
        "XAUUSD",
        now,
        source_name="fake",
        timeframes=(Timeframe.M15,),
        initial_lookback=timedelta(hours=3),
    )
    assert out[0].fetched_rows > 0
    newest = out[0].newest
    assert newest is not None
    assert newest + Timeframe.M15.delta <= now  # the forming bar is not stored


def test_a_second_refresh_starts_just_before_the_newest_stored_bar(tmp_path: Path) -> None:
    store = RawStore(tmp_path)
    source = FakeSource()
    now = MONDAY + timedelta(hours=6, minutes=7)
    first = refresh_market_data(
        source, store, "XAUUSD", now, source_name="fake", timeframes=(Timeframe.M15,),
        initial_lookback=timedelta(hours=3),
    )  # fmt: skip
    later = now + timedelta(minutes=30)
    refresh_market_data(
        source, store, "XAUUSD", later, source_name="fake", timeframes=(Timeframe.M15,)
    )
    newest = first[0].newest
    assert newest is not None
    assert source.requests[-1].start_utc == newest - Timeframe.M15.delta * OVERLAP_BARS


def test_nothing_new_leaves_the_store_unchanged(tmp_path: Path) -> None:
    class Empty:
        name = "empty"

        def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
            return make_bars(0, request.timeframe)

    store = RawStore(tmp_path)
    out = refresh_market_data(
        Empty(), store, "XAUUSD", datetime(2026, 3, 4, tzinfo=UTC), source_name="empty",
        timeframes=(Timeframe.M5,),
    )  # fmt: skip
    assert out[0].fetched_rows == 0
    assert out[0].newest is None
    assert store.datasets("XAUUSD", Timeframe.M5) == []
