"""History fetch planning and the research-only daily dataset (no D1 timeframe is added)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.history import daily_from_h1, fetch_back
from xau_edge.market_data.broker_clock import BrokerClock

CLOCK = BrokerClock.parse("NY+7")


def test_timeframe_enum_has_no_daily_member() -> None:
    assert {t.value for t in Timeframe} == {"M1", "M5", "M15", "M30", "H1", "H4"}


def test_fetch_back_walks_backwards_and_stops_after_empty_run() -> None:
    have_from = datetime(2024, 3, 1, tzinfo=UTC)
    calls: list[tuple[datetime, datetime]] = []

    def fake(start: datetime, end: datetime) -> pl.DataFrame:
        calls.append((start, end))
        if end <= have_from:
            return make_bars(0, Timeframe.H1)
        return make_bars(2, Timeframe.H1, start=max(start, have_from))

    out = fetch_back(fake, end=datetime(2024, 6, 1, tzinfo=UTC), empty_run_stop=3)
    assert out["timestamp"].is_sorted()
    assert out["timestamp"].is_unique().all()
    assert calls[0][1] == datetime(2024, 6, 1, tzinfo=UTC)
    # 3 months with data (Mar, Apr, May) then 3 empty months, then stop
    assert len(calls) == 6
    assert out.height == 6


def test_fetch_back_returns_empty_when_nothing_exists() -> None:
    out = fetch_back(
        lambda s, e: make_bars(0, Timeframe.H1),
        end=datetime(2024, 6, 1, tzinfo=UTC),
        empty_run_stop=2,
    )
    assert out.height == 0


def _h1_days() -> pl.DataFrame:
    # server day = NY day shifted +7h => it starts at 17:00 New York; Jan = EST (UTC-5) => 22:00 UTC
    start = datetime(2025, 1, 6, 22, 0, tzinfo=UTC)
    return make_bars(48, Timeframe.H1, start=start)


def test_daily_from_h1_groups_by_server_day_and_aggregates() -> None:
    h1 = _h1_days()
    daily = daily_from_h1(h1, CLOCK, min_bars=1)
    assert daily.height == 2
    first = daily.row(0, named=True)
    day1 = h1.head(24)
    assert first["timestamp"] == day1["timestamp"][0]
    assert first["open"] == day1["open"][0]
    assert first["close"] == day1["close"][-1]
    assert first["high"] == day1["high"].max()
    assert first["low"] == day1["low"].min()
    assert first["n_bars"] == 24


def test_daily_from_h1_drops_thin_days() -> None:
    h1 = _h1_days().head(30)
    daily = daily_from_h1(h1, CLOCK, min_bars=20)
    assert daily.height == 1
    assert daily["timestamp"][0] + timedelta(hours=24) <= h1["timestamp"][-1] + timedelta(hours=1)
