"""Header context computed on the server: broker-day statistics and candle countdowns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.calendars import ftmo_calendar
from xau_edge.market_data.session import market_status
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.market_context import bar_closes, day_stats, market_context, next_open


def m5_frame(start: datetime, closes: list[float], *, spread: float = 1.0) -> pl.DataFrame:
    stamps = [start + timedelta(minutes=5 * i) for i in range(len(closes))]
    opens = [closes[0], *closes[:-1]]
    return pl.DataFrame(
        {
            "timestamp": pl.Series(stamps, dtype=pl.Datetime("us", "UTC")),
            "open": opens,
            "high": [max(o, c) + spread for o, c in zip(opens, closes, strict=True)],
            "low": [min(o, c) - spread for o, c in zip(opens, closes, strict=True)],
            "close": closes,
            "available_at": pl.Series(
                [s + timedelta(minutes=5) for s in stamps], dtype=pl.Datetime("us", "UTC")
            ),
        }
    )


# 2026-03-03 is a Tuesday; the server (NY+7) wall clock is UTC+2 in winter, so the broker day
# starts at 22:00 UTC of the previous evening.
DAY_START = datetime(2026, 3, 2, 22, 0, tzinfo=UTC)


def test_day_stats_use_the_broker_day_and_the_previous_close() -> None:
    prev = m5_frame(
        DAY_START - timedelta(hours=2), [2000.0] * 24
    )  # the day before (server date 03-02)
    today = m5_frame(DAY_START, [2010.0, 2012.0, 2008.0, 2015.0])
    frame = pl.concat([prev, today])
    now = DAY_START + timedelta(minutes=21)
    stats = day_stats(frame, SERVER_CLOCK, now, price=2016.0)
    assert stats is not None
    assert stats["is_current_day"] is True
    assert stats["open"] == 2010.0
    assert stats["prev_close"] == 2000.0
    assert stats["high"] == 2016.0  # the live price extends the extreme
    assert stats["low"] == min(today["low"].to_list())
    assert stats["change"] == 16.0
    assert stats["change_basis"] == "PREV_CLOSE"
    assert 0.0 <= stats["range_position"] <= 1.0


def test_closed_market_reports_the_last_traded_day_not_an_empty_one() -> None:
    frame = m5_frame(DAY_START, [2010.0, 2012.0, 2008.0, 2015.0])
    saturday = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    stats = day_stats(frame, SERVER_CLOCK, saturday, price=None)
    assert stats is not None
    assert stats["is_current_day"] is False
    assert stats["change_basis"] == "DAY_OPEN"
    assert stats["last"] == 2015.0


def test_no_bars_means_no_stats_instead_of_zeros() -> None:
    assert day_stats(None, SERVER_CLOCK, DAY_START, 2000.0) is None
    assert day_stats(m5_frame(DAY_START, [2000.0]).head(0), SERVER_CLOCK, DAY_START, 2000.0) is None


def test_countdown_comes_from_the_closed_bar_grid_and_stops_when_the_market_is_closed() -> None:
    frame = m5_frame(DAY_START, [2000.0] * 4)  # last bar closes at DAY_START + 20 min
    now = DAY_START + timedelta(minutes=22)
    closes = bar_closes({Timeframe.M5: frame}, now, market_open=True)
    assert closes["M5"] == (DAY_START + timedelta(minutes=25)).isoformat()
    assert bar_closes({Timeframe.M5: frame}, now, market_open=False)["M5"] is None
    late = DAY_START + timedelta(hours=3)  # the grid is behind: never a fake countdown
    assert bar_closes({Timeframe.M5: frame}, late, market_open=True)["M5"] is None


def test_market_context_has_a_session_label_in_vietnamese() -> None:
    frame = m5_frame(DAY_START, [2000.0] * 4)
    ctx = market_context(
        {Timeframe.M5: frame},
        SERVER_CLOCK,
        DAY_START + timedelta(minutes=22),
        price=2001.0,
        session="LONDON_NY_OVERLAP",
        market_open=True,
    )
    assert ctx["session"]["label"] == "Âu-Mỹ chồng phiên"
    assert ctx["daily"]["day"]
    assert ctx["server_time"].startswith("2026-03-02T22:22")


def test_next_open_is_the_first_open_minute_after_a_weekend() -> None:
    calendar = ftmo_calendar()
    saturday = datetime(2026, 3, 7, 12, 0, tzinfo=UTC)
    reopens = next_open(saturday, calendar)
    assert reopens is not None
    assert reopens > saturday
    assert market_status(reopens, calendar).value == "OPEN"
    assert market_status(reopens - timedelta(minutes=1), calendar).value != "OPEN"
    assert reopens - saturday < timedelta(days=2)


def test_the_context_names_the_reopening_only_while_closed() -> None:
    calendar = ftmo_calendar()
    frame = m5_frame(DAY_START, [2000.0] * 4)
    closed = market_context(
        {Timeframe.M5: frame}, SERVER_CLOCK, datetime(2026, 3, 7, 12, 0, tzinfo=UTC),
        price=None, session="OFF_HOURS", market_open=False, calendar=calendar,
    )  # fmt: skip
    assert closed["next_open"] is not None
    open_ = market_context(
        {Timeframe.M5: frame}, SERVER_CLOCK, DAY_START + timedelta(minutes=22),
        price=2000.0, session="ASIA", market_open=True, calendar=calendar,
    )  # fmt: skip
    assert open_["next_open"] is None
