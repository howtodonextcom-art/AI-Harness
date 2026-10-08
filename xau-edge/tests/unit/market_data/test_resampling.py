from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from tests.conftest import make_bars
from tests.synthetic import ftmo_like_m5
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.broker_clock import BrokerClock
from xau_edge.market_data.resampling import resample_bars
from xau_edge.market_data.validators import MarketCalendar

pytestmark = pytest.mark.unit

CLOCK = BrokerClock.parse("NY+7")
FTMO_CAL = MarketCalendar(
    weekend_close_minute=16 * 60 + 50,
    weekend_open_minute=18 * 60 + 5,
    daily_break_start_minute=16 * 60 + 50,
    daily_break_end_minute=18 * 60 + 5,
)
# Wed 2026-07-01 server 04:00 == 01:00 UTC (US summer: server = UTC+3).
SUMMER = datetime(2026, 7, 1, 1, 0, tzinfo=UTC)


def m5(n: int, start: datetime = SUMMER) -> pl.DataFrame:
    return make_bars(n, timeframe=Timeframe.M5, start=start)


def test_m5_to_m15_aggregates_ohlc_and_volumes() -> None:
    src = m5(6)
    out = resample_bars(src, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert out.frame.height == 2
    first = out.frame.row(0, named=True)
    assert first["timestamp"] == SUMMER
    assert first["open"] == src["open"][0]
    assert first["close"] == src["close"][2]
    assert first["high"] == src["high"][:3].max()
    assert first["low"] == src["low"][:3].min()
    assert first["tick_volume"] == int(src["tick_volume"][:3].sum())
    assert first["real_volume"] is None
    assert out.incomplete == ()


def test_real_volume_is_summed_when_present() -> None:
    src = m5(3).with_columns(pl.lit(7, dtype=pl.Int64).alias("real_volume"))
    out = resample_bars(src, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert out.frame["real_volume"][0] == 21


@pytest.mark.parametrize(
    ("policy", "expected"),
    [("first", 10), ("last", 30), ("max", 30), ("mean", 20)],
)
def test_spread_policy(policy: str, expected: int) -> None:
    src = m5(3).with_columns(pl.Series("spread", [10, 20, 30], dtype=pl.Int64))
    out = resample_bars(
        src,
        Timeframe.M5,
        Timeframe.M15,
        clock=CLOCK,
        calendar=FTMO_CAL,
        spread_policy=policy,  # type: ignore[arg-type]
    )
    assert out.frame["spread"][0] == expected


def test_h4_buckets_are_anchored_to_server_midnight_not_utc() -> None:
    # Summer: server 04:00-08:00 is 01:00-05:00 UTC. 48 M5 bars fill exactly one H4 bucket.
    out = resample_bars(m5(48), Timeframe.M5, Timeframe.H4, clock=CLOCK, calendar=FTMO_CAL)
    assert out.frame["timestamp"].to_list() == [SUMMER]
    # Winter: server = UTC+2, so server 04:00 is 02:00 UTC.
    winter_start = datetime(2026, 1, 14, 2, 0, tzinfo=UTC)
    out_w = resample_bars(
        m5(48, winter_start), Timeframe.M5, Timeframe.H4, clock=CLOCK, calendar=FTMO_CAL
    )
    assert out_w.frame["timestamp"].to_list() == [winter_start]


def test_missing_sub_bar_inside_open_market_marks_bucket_incomplete() -> None:
    src = m5(12)
    gappy = pl.concat([src.slice(0, 4), src.slice(5)])  # drop one bar of the second M15
    out = resample_bars(gappy, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert out.frame.height == 3
    assert out.incomplete == (datetime(2026, 7, 1, 1, 15, tzinfo=UTC),)


def test_session_start_bucket_is_complete_when_the_break_covers_missing_sub_bars() -> None:
    # Server 01:05 first bar after the break (NY 18:05). H1 bucket 01:00 holds 11 M5 bars.
    utc_start = CLOCK.server_to_utc(
        pl.Series([datetime(2026, 7, 1, 1, 5)], dtype=pl.Datetime("us"))  # noqa: DTZ001
    )[0]
    out = resample_bars(
        m5(11, utc_start), Timeframe.M5, Timeframe.H1, clock=CLOCK, calendar=FTMO_CAL
    )
    assert out.frame.height == 1
    assert out.incomplete == ()
    server_label = CLOCK.utc_to_server(out.frame["timestamp"])[0]
    assert server_label == datetime(2026, 7, 1, 1, 0)  # noqa: DTZ001


def test_a_stray_bar_in_a_closed_slot_cannot_complete_a_bucket() -> None:
    """ECC review F-17: bar counts must come from OPEN slots only."""
    # Server 01:00-01:15 (summer): 01:00 is inside the break, 01:05 and 01:10 are open.
    start = datetime(2026, 6, 30, 22, 0, tzinfo=UTC)  # server 01:00
    three = m5(3, start)  # bars at 01:00 (stray, closed), 01:05, 01:10
    without_0105 = pl.concat([three.slice(0, 1), three.slice(2)])
    out = resample_bars(without_0105, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert out.frame.height == 0
    assert out.incomplete == (start,)
    # Control: with the open slot present the bucket is complete.
    ok = resample_bars(three, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert ok.frame.height == 1


def test_unknown_spread_policy_is_a_clear_error() -> None:
    with pytest.raises(ValueError, match="spread_policy"):
        resample_bars(
            m5(3),
            Timeframe.M5,
            Timeframe.M15,
            clock=CLOCK,
            calendar=FTMO_CAL,
            spread_policy="median",  # type: ignore[arg-type]
        )


def test_full_synthetic_sessions_resample_without_incomplete_buckets() -> None:
    utc_bars = ftmo_like_m5(datetime(2026, 3, 2, tzinfo=UTC), weeks=2)  # spans the US DST change
    for tf in (Timeframe.M15, Timeframe.H1, Timeframe.H4):
        out = resample_bars(utc_bars, Timeframe.M5, tf, clock=CLOCK, calendar=FTMO_CAL)
        assert out.incomplete == (), tf
        assert out.frame.height > 0


def test_rejects_invalid_timeframe_pairs_and_unsorted_input() -> None:
    with pytest.raises(ValueError, match="coarser"):
        resample_bars(m5(3), Timeframe.M15, Timeframe.M5, clock=CLOCK, calendar=FTMO_CAL)
    with pytest.raises(ValueError, match="multiple"):
        resample_bars(m5(3), Timeframe.M5, Timeframe.M5, clock=CLOCK, calendar=FTMO_CAL)
    src = m5(6)
    shuffled = pl.concat([src.slice(3), src.slice(0, 3)])
    with pytest.raises(ValueError, match="sorted"):
        resample_bars(shuffled, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    with pytest.raises(ValueError, match="sorted"):
        resample_bars(
            pl.concat([src, src.slice(0, 1)]),
            Timeframe.M5,
            Timeframe.M15,
            clock=CLOCK,
            calendar=FTMO_CAL,
        )


def test_does_not_mutate_input() -> None:
    src = m5(6)
    before = src.clone()
    resample_bars(src, Timeframe.M5, Timeframe.M15, clock=CLOCK, calendar=FTMO_CAL)
    assert src.equals(before)
