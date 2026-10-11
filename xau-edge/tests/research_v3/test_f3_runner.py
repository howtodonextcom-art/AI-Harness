"""F3 runner: New York anchors, exclusions, catastrophic stop and the reference oracle."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

import numpy as np
import polars as pl

from xau_edge.research_v2.frame import _mismatch_days
from xau_edge.research_v3 import f3

DAY = date(2015, 7, 8)  # a Wednesday, New York on EDT (09:30 NY = 13:30 UTC)


def _m1(
    day: date, path: dict[str, float], *, drop: frozenset[str] = frozenset(), spread: float = 20.0
) -> pl.DataFrame:
    rows = []
    t = datetime.combine(day, time(9, 0), tzinfo=f3.NEW_YORK)
    price = 1000.0
    while t.time() < time(17, 0):
        hm = t.strftime("%H:%M")
        price = path.get(hm, price)
        if hm not in drop:
            rows.append((t.astimezone(UTC), price, price + 0.1, price - 0.1, price, spread))
        t += timedelta(minutes=1)
    return pl.DataFrame(
        rows, schema=["timestamp", "open", "high", "low", "close", "spread"], orient="row"
    ).with_columns(pl.col("timestamp").dt.cast_time_unit("us"))


def _h1(day: date) -> pl.DataFrame:
    start = datetime.combine(day - timedelta(days=3), time(0), tzinfo=UTC)
    ts = [start + timedelta(hours=i) for i in range(24 * 4)]
    return pl.DataFrame(
        {
            "timestamp": ts,
            "open": [1000.0] * len(ts),
            "high": [1002.0] * len(ts),
            "low": [998.0] * len(ts),
            "close": [1000.0] * len(ts),
            "spread": [20] * len(ts),
        }
    ).with_columns(pl.col("timestamp").dt.cast_time_unit("us"))


NO_CLOSURES = f3.Closures(np.array([], dtype=np.int64), np.array([], dtype=np.int64))


def _run(
    m1: pl.DataFrame, closures: f3.Closures = NO_CLOSURES, bad: frozenset[int] = frozenset()
) -> dict[str, Any]:
    return f3.run(_h1(DAY), m1, DAY, DAY + timedelta(days=1), closures, set(bad))


def _bars(m1: pl.DataFrame) -> dict[str, tuple[float, float, float, float]]:
    ny = m1.with_columns(
        pl.col("timestamp")
        .dt.convert_time_zone("America/New_York")
        .dt.strftime("%H:%M")
        .alias("hm")
    )
    return {
        r["hm"]: (r["open"], r["high"], r["low"], float(r["spread"]))
        for r in ny.iter_rows(named=True)
    }


def test_up_morning_goes_long_and_exits_at_1645_matching_the_oracle() -> None:
    m1 = _m1(DAY, {"14:00": 1003.0, "16:00": 1005.0})
    res = _run(m1)
    (t,) = res["trades"]
    assert (t["direction"], t["reason"]) == (1, "TIME_EXIT")
    assert (
        datetime.fromtimestamp(t["entry_us"] / 1e6, tz=UTC)
        .astimezone(f3.NEW_YORK)
        .strftime("%H:%M")
        == "15:00"
    )
    ref = f3.reference_day(_bars(m1), t["atr"], 1.6, 3.0)
    assert ref is not None
    assert ref[:3] == (1, "16:45", "TIME_EXIT")
    assert abs(ref[3] - t["base_r"]) < 1e-12


def test_short_stop_is_checked_on_the_ask_and_matches_the_oracle() -> None:
    m1 = _m1(DAY, {"14:00": 990.0, "15:30": 1020.0}, spread=50.0)
    (t,) = _run(m1)["trades"]
    assert (t["direction"], t["reason"]) == (-1, "STOP_LOSS")
    ref = f3.reference_day(_bars(m1), t["atr"], 1.6, 3.0)
    assert ref is not None
    assert ref[1:3] == ("15:30", "STOP_LOSS")
    assert abs(ref[3] - t["base_r"]) < 1e-12


def test_exclusions_are_counted_not_traded() -> None:
    flat = _run(_m1(DAY, {}))
    assert flat["counts"]["no_signal_zero_move"] == 1
    assert flat["trades"] == []
    gap = _run(_m1(DAY, {"14:00": 1001.0}, drop=frozenset({"16:45"})))
    assert gap["counts"]["excluded_missing_anchor"] == 1
    thin = frozenset(f"10:{m:02d}" for m in range(22))
    assert _run(_m1(DAY, {"14:00": 1001.0}, drop=thin))["counts"]["excluded_low_coverage"] == 1
    ok = frozenset(f"10:{m:02d}" for m in range(21))
    assert len(_run(_m1(DAY, {"14:00": 1001.0}, drop=ok))["trades"]) == 1
    noon = int(datetime.combine(DAY, time(12), tzinfo=f3.NEW_YORK).timestamp() * 1e6)
    closed = f3.Closures(np.array([noon]), np.array([noon + 3_600_000_000]))
    assert (
        _run(_m1(DAY, {"14:00": 1001.0}), closed)["counts"]["excluded_holiday_or_early_close"] == 1
    )


def test_clock_mask_is_the_v2_rule_and_only_for_uncertified_years() -> None:
    days = [date(2015, 3, 1) + timedelta(days=i) for i in range(60)]
    v2 = _mismatch_days(days)
    assert v2
    assert all(f3.clock_unsafe(d, {2015}) == (d in v2) for d in days)
    assert not any(f3.clock_unsafe(d, set()) for d in days)


def test_anchors_follow_new_york_daylight_saving() -> None:
    hours = [
        datetime.fromtimestamp(f3.ny_us(d, f3.OPEN_NY) / 1e6, tz=UTC).hour
        for d in (date(2015, 1, 7), date(2015, 7, 8))
    ]
    assert hours == [14, 13]
