from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from tests.synthetic import ftmo_like_m5, to_server_labels
from xau_edge.market_data.broker_clock import BrokerClock, infer_broker_clock

pytestmark = pytest.mark.unit


def naive(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """Server wall-clock values are naive by definition."""
    return datetime(year, month, day, hour, minute)  # noqa: DTZ001


def convert(clock: BrokerClock, *values: datetime, strict: bool = True) -> list[datetime | None]:
    series = pl.Series("t", list(values), dtype=pl.Datetime("us"))
    return clock.server_to_utc(series, strict=strict).to_list()


def test_parse_accepts_ny_offset_and_iana_tokens() -> None:
    assert BrokerClock.parse("NY+7").ny_offset_hours == 7
    assert BrokerClock.parse("ny+7").ny_offset_hours == 7
    assert BrokerClock.parse("NY-2").ny_offset_hours == -2
    assert BrokerClock.parse("Europe/Athens").iana == "Europe/Athens"
    assert BrokerClock.parse("UTC").iana == "UTC"


@pytest.mark.parametrize("token", ["", "Mars/Olympus", "NY+", "NY+x", "NY+30"])
def test_parse_rejects_invalid_tokens(token: str) -> None:
    with pytest.raises(ValueError, match="broker clock"):
        BrokerClock.parse(token)


def test_exactly_one_clock_kind_must_be_set() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        BrokerClock()
    with pytest.raises(ValueError, match="exactly one"):
        BrokerClock(iana="UTC", ny_offset_hours=1)


def test_token_round_trips_through_parse() -> None:
    for token in ("NY+7", "NY-2", "Europe/Athens", "UTC"):
        assert BrokerClock.parse(BrokerClock.parse(token).token).token == token


def test_python_helpers_for_iana_clocks() -> None:
    clock = BrokerClock.parse("Europe/Athens")
    utc = datetime(2025, 3, 3, 0, 0, tzinfo=UTC)
    assert clock.to_server_wall(utc) == naive(2025, 3, 3, 2, 0)
    assert clock.label_as_utc(utc) == datetime(2025, 3, 3, 2, 0, tzinfo=UTC)
    assert clock.utc_to_server(pl.Series([utc]).dt.convert_time_zone("UTC")).to_list() == [
        naive(2025, 3, 3, 2, 0)
    ]


def test_infer_clock_skips_candidates_without_weekly_boundaries() -> None:
    one_day = ftmo_like_m5(datetime(2026, 6, 15, tzinfo=UTC), weeks=1).head(50)
    labelled = to_server_labels(one_day, BrokerClock.parse("NY+7"))
    assert infer_broker_clock(labelled, [BrokerClock.parse("NY+7")]) == []


def test_ny_offset_follows_us_daylight_saving() -> None:
    clock = BrokerClock.parse("NY+7")
    summer, winter = convert(clock, naive(2026, 7, 1, 12, 0), naive(2026, 1, 15, 12, 0))
    assert summer == datetime(2026, 7, 1, 9, 0, tzinfo=UTC)  # server = UTC+3
    assert winter == datetime(2026, 1, 15, 10, 0, tzinfo=UTC)  # server = UTC+2


def test_ny_offset_differs_from_athens_in_the_us_eu_mismatch_weeks() -> None:
    # 2026-03-13: US already on summer time, EU not yet.
    label = naive(2026, 3, 13, 23, 45)
    (ny,) = convert(BrokerClock.parse("NY+7"), label)
    (athens,) = convert(BrokerClock.parse("Europe/Athens"), label)
    assert ny == datetime(2026, 3, 13, 20, 45, tzinfo=UTC)
    assert athens == datetime(2026, 3, 13, 21, 45, tzinfo=UTC)


def test_iana_clock_matches_previous_behaviour() -> None:
    (out,) = convert(BrokerClock.parse("Europe/Athens"), naive(2025, 3, 3, 2, 0))
    assert out == datetime(2025, 3, 3, 0, 0, tzinfo=UTC)


def test_roundtrip_utc_to_server_to_utc() -> None:
    clock = BrokerClock.parse("NY+7")
    utc = pl.Series(
        "t", [datetime(2026, 7, 1, 9, 0, tzinfo=UTC), datetime(2026, 1, 15, 10, 0, tzinfo=UTC)]
    )
    utc = utc.dt.convert_time_zone("UTC")
    server = clock.utc_to_server(utc)
    assert server.to_list() == [naive(2026, 7, 1, 12, 0), naive(2026, 1, 15, 12, 0)]
    assert clock.server_to_utc(server).to_list() == utc.to_list()


def test_ambiguous_server_time_raises_when_strict_and_nulls_otherwise() -> None:
    clock = BrokerClock.parse("NY+7")
    ambiguous = naive(2025, 11, 2, 8, 30)  # NY 01:30 on the fall-back Sunday
    with pytest.raises(pl.exceptions.ComputeError):
        convert(clock, ambiguous)
    assert convert(clock, ambiguous, strict=False) == [None]


def test_python_helpers_shift_request_bounds() -> None:
    clock = BrokerClock.parse("NY+7")
    utc = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
    assert clock.to_server_wall(utc) == naive(2026, 7, 1, 12, 0)
    assert clock.label_as_utc(utc) == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


def test_infer_clock_picks_ny_offset_over_athens() -> None:
    utc_bars = ftmo_like_m5(
        weeks_from=datetime(2026, 2, 23, tzinfo=UTC), weeks=8
    )  # spans US/EU DST gap
    labelled = to_server_labels(utc_bars, BrokerClock.parse("NY+7"))
    scores = infer_broker_clock(
        labelled, [BrokerClock.parse(t) for t in ("NY+7", "NY+6", "Europe/Athens", "UTC")]
    )
    assert scores[0].clock == BrokerClock.parse("NY+7")
    assert scores[0].consistency == pytest.approx(1.0)
    athens = next(s for s in scores if s.clock.iana == "Europe/Athens")
    assert athens.consistency < scores[0].consistency
