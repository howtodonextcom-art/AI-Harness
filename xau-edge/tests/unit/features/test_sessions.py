"""Trading-session labels from bar-open timestamps (DST-aware, local exchange hours)."""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl
import pytest

from xau_edge.features.sessions import TradingSession, session_features


def _label(ts: datetime) -> str:
    out = session_features(pl.Series("timestamp", [ts], dtype=pl.Datetime("us", "UTC")))
    return str(out["trading_session"][0])


@pytest.mark.parametrize(
    ("ts", "expected"),
    [
        # Northern winter: London = UTC, New York = UTC-5, Tokyo = UTC+9
        (datetime(2025, 1, 15, 3, 0, tzinfo=UTC), "ASIA"),
        (datetime(2025, 1, 15, 10, 0, tzinfo=UTC), "LONDON"),
        (datetime(2025, 1, 15, 14, 0, tzinfo=UTC), "LONDON_NY_OVERLAP"),
        (datetime(2025, 1, 15, 18, 0, tzinfo=UTC), "NEW_YORK"),
        (datetime(2025, 1, 15, 22, 0, tzinfo=UTC), "OFF_HOURS"),
        # Northern summer: London = UTC+1, New York = UTC-4
        (datetime(2025, 7, 15, 3, 0, tzinfo=UTC), "ASIA"),
        (datetime(2025, 7, 15, 11, 30, tzinfo=UTC), "LONDON"),
        (datetime(2025, 7, 15, 12, 30, tzinfo=UTC), "LONDON_NY_OVERLAP"),
        (datetime(2025, 7, 15, 19, 0, tzinfo=UTC), "NEW_YORK"),
    ],
)
def test_session_labels(ts: datetime, expected: str) -> None:
    assert _label(ts) == expected


def test_session_boundaries_use_local_open_close_with_bar_open_times() -> None:
    # London opens 08:00 local (07:00 UTC in summer): the 07:55 bar is before, 08:00 local is in.
    assert _label(datetime(2025, 7, 15, 6, 55, tzinfo=UTC)) != "LONDON"
    assert _label(datetime(2025, 7, 15, 7, 0, tzinfo=UTC)) == "LONDON"
    # New York closes 17:00 local: 16:55 ET bar is in, 17:00 ET bar is out.
    assert _label(datetime(2025, 1, 15, 21, 55, tzinfo=UTC)) == "NEW_YORK"
    assert _label(datetime(2025, 1, 15, 22, 0, tzinfo=UTC)) == "OFF_HOURS"


def test_dst_transition_week_differs_from_fixed_utc_hours() -> None:
    # 2025-03-12: US already on summer time, UK not yet: overlap shifts by one hour.
    assert _label(datetime(2025, 3, 12, 12, 30, tzinfo=UTC)) == "LONDON_NY_OVERLAP"
    assert _label(datetime(2025, 1, 15, 12, 30, tzinfo=UTC)) == "LONDON"


def test_hour_and_day_of_week_are_utc_and_monday_is_one() -> None:
    ts = pl.Series(
        "timestamp", [datetime(2025, 3, 3, 13, 5, tzinfo=UTC)], dtype=pl.Datetime("us", "UTC")
    )
    out = session_features(ts)
    assert out["hour"][0] == 13
    assert out["day_of_week"][0] == 1
    assert out.columns == ["hour", "day_of_week", "trading_session"]


def test_enum_values_match_the_brief() -> None:
    assert {s.value for s in TradingSession} >= {"ASIA", "LONDON", "NEW_YORK", "LONDON_NY_OVERLAP"}


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValueError, match="UTC"):
        session_features(pl.Series("timestamp", [datetime(2025, 1, 1)]))  # noqa: DTZ001 - naive on purpose


def test_null_timestamps_are_rejected_not_labelled_off_hours() -> None:
    series = pl.Series(
        "timestamp",
        [datetime(2025, 1, 15, 10, 0, tzinfo=UTC), None],
        dtype=pl.Datetime("us", "UTC"),
    )
    with pytest.raises(ValueError, match="null"):
        session_features(series)
