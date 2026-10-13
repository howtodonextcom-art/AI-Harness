"""The daily pseudo-bar detector (research/clean_view.py): the forensic findings as regression tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest

from xau_edge_v2.research.clean_view import (
    DataDefectError,
    pseudo_bar_mask,
    require_clean,
    strip_pseudo_bars,
)


def frame(rows: list[tuple[datetime, float, int, int]]) -> pl.DataFrame:
    """(timestamp, close, spread, tick_volume) rows; the other OHLC columns follow the close."""
    return pl.DataFrame(
        {
            "timestamp": [r[0] for r in rows],
            "open": [r[1] for r in rows],
            "high": [r[1] + 0.2 for r in rows],
            "low": [r[1] - 0.2 for r in rows],
            "close": [r[1] for r in rows],
            "spread": [r[2] for r in rows],
            "tick_volume": [r[3] for r in rows],
        }
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))


T = datetime(2013, 5, 14, 20, 40, tzinfo=UTC)


def normal_bars(start: datetime, n: int = 20) -> list[tuple[datetime, float, int, int]]:
    return [(start + timedelta(minutes=5 * i), 1860.0, 20, 100) for i in range(n)]


def test_the_2013_05_14_bar_is_detected() -> None:
    f = frame(
        [
            (T, 1425.4, 39, 114),
            (T + timedelta(minutes=20), 1392.36, 0, 187_530),  # 21:00 UTC, spread 0, a day of ticks
            (T + timedelta(minutes=85), 1425.5, 48, 215),
        ]
    )
    assert pseudo_bar_mask(f).tolist() == [False, True, False]


def test_the_first_bar_after_the_break_is_not_a_pseudo_bar() -> None:
    """2021 reopening bars have spread 0 and a few thousand ticks: normal, kept."""
    f = frame(
        [
            (datetime(2021, 3, 1, 21, 0, tzinfo=UTC), 1724.9, 0, 2875),
            (datetime(2021, 6, 1, 22, 0, tzinfo=UTC), 1899.3, 0, 4755),
        ]
    )
    assert not pseudo_bar_mask(f).any()


@pytest.mark.parametrize(
    "row",
    [
        (datetime(2013, 5, 14, 20, 0, tzinfo=UTC), 1425.0, 0, 187_530),  # not the rollover hour
        (datetime(2013, 5, 14, 21, 5, tzinfo=UTC), 1425.0, 0, 187_530),  # not minute 0
        (datetime(2013, 5, 14, 21, 0, tzinfo=UTC), 1425.0, 40, 187_530),  # a real spread
    ],
)
def test_every_part_of_the_signature_is_required(row: tuple[datetime, float, int, int]) -> None:
    assert not pseudo_bar_mask(frame([row])).any()


def test_the_winter_rollover_hour_is_covered() -> None:
    f = frame(
        [
            *normal_bars(datetime(2021, 1, 20, 20, 0, tzinfo=UTC)),
            (datetime(2021, 1, 20, 22, 0, tzinfo=UTC), 1860.0, 0, 90_000),
        ]
    )
    assert pseudo_bar_mask(f).sum() == 1


def test_strip_returns_a_copy_and_the_count() -> None:
    f = frame([*normal_bars(T), (T + timedelta(minutes=20), 1392.36, 0, 187_530)])
    clean, n = strip_pseudo_bars(f)
    assert n == 1
    assert clean.height == 20
    assert f.height == 21  # the input is never edited


def test_require_clean_stops_a_pipeline() -> None:
    f = frame([*normal_bars(T), (T + timedelta(minutes=20), 1392.36, 0, 187_530)])
    with pytest.raises(DataDefectError, match="pseudo-bar"):
        require_clean(f, "2013-05")
    require_clean(frame(normal_bars(T)), "ok")


def test_the_pseudo_bar_creates_the_mean_reversion_and_removing_it_removes_it() -> None:
    """A random walk with one next-day-close bar per day: naive lag-1 autocorrelation about -0.3; stripped about 0."""
    rng = np.random.default_rng(1)
    rows: list[tuple[datetime, float, int, int]] = []
    price = 1400.0
    for day in range(60):
        base = datetime(2013, 1, 7, 22, 5, tzinfo=UTC) + timedelta(days=day)
        walk = price + np.cumsum(rng.normal(0, 0.15, 240))
        for i, p in enumerate(walk):
            rows.append((base + timedelta(minutes=5 * i), float(p), 30, 100))
        price = float(walk[-1])
        next_day_close = price + rng.normal(
            0, 8.0
        )  # the pseudo-bar carries the NEXT session's close
        rows.append((base + timedelta(hours=23), next_day_close, 0, 120_000))
    f = frame(rows)
    f = (
        f.with_columns(pl.col("timestamp").dt.replace(hour=21, minute=0).alias("ts2"))
        if False
        else f
    )
    # place the pseudo-bar exactly at the rollover minute of each day
    fixed = [
        (r[0].replace(hour=21, minute=0) if r[2] == 0 else r[0], r[1], r[2], r[3]) for r in rows
    ]
    f = frame(fixed).sort("timestamp")

    def naive(d: pl.DataFrame) -> float:
        r = np.diff(np.log(d["close"].to_numpy()))
        return float(np.corrcoef(r[:-1], r[1:])[0, 1])

    clean, n = strip_pseudo_bars(f)
    assert n == 60
    assert naive(f) < -0.25
    assert abs(naive(clean)) < 0.1
