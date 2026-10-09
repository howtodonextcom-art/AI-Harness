from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.trading.helpers import m1_series, multi_tf, resample
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.profiles import BrokerProfile
from xau_edge.trading.activity import (
    VolumeType,
    activity,
    detect_volume_type,
    volume_acceleration,
    volume_percentile,
    volume_ratio,
)
from xau_edge.trading.frames import (
    FrameError,
    closed_as_of,
    compare_with_broker,
    derive_from_m1,
    forming_bar_open,
    from_frames,
    with_available_at,
)
from xau_edge.trading.patterns import (
    breakout,
    compression,
    detect_patterns,
    engulfing,
    failed_breakout,
    inside_bar,
    outside_bar,
    pin_bar,
    range_expansion,
    strong_body,
)

ROOT = Path(__file__).parents[3]
PROFILE = BrokerProfile.from_yaml(ROOT / "configs" / "brokers" / "ftmo_demo.yaml")

# -- timeframes ----------------------------------------------------------------------------


def test_the_timeframes_of_the_trading_core_exist_with_their_lengths() -> None:
    minutes = {tf.value: tf.minutes for tf in Timeframe}
    assert minutes == {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}
    assert Timeframe.parse("m30") is Timeframe.M30


# -- volume semantics ----------------------------------------------------------------------


def test_a_feed_without_real_volume_is_tick_volume_and_real_is_never_inferred() -> None:
    ticks = np.arange(100, 400)
    assert detect_volume_type(ticks, np.zeros(300)) is VolumeType.TICK_VOLUME
    assert detect_volume_type(ticks, None) is VolumeType.TICK_VOLUME
    assert detect_volume_type(ticks, np.full(300, 5.0)) is VolumeType.UNKNOWN  # never REAL
    assert detect_volume_type(ticks[:10], None) is VolumeType.UNKNOWN
    assert detect_volume_type(np.zeros(300), None) is VolumeType.UNKNOWN


def test_the_real_ftmo_research_data_has_only_tick_volume() -> None:
    files = sorted((ROOT / "data" / "raw" / "XAUUSD" / "H1").glob("*.parquet"))
    if not files:
        pytest.skip("local raw data not available (CI)")
    df = pl.read_parquet(files[0])
    found = detect_volume_type(df["tick_volume"].to_numpy(), df["real_volume"].to_numpy())
    assert found is VolumeType.TICK_VOLUME


def test_normalised_activity_ignores_the_scale_of_the_timeframe() -> None:
    rng = np.random.default_rng(0)
    base = rng.integers(80, 120, 300).astype(float)
    small = activity(base)
    large = activity(base * 40)  # an H1-sized raw volume: same shape, other scale
    for key in ("zscore", "percentile", "ratio"):
        assert np.allclose(small[key], large[key], equal_nan=True)


def test_activity_is_causal() -> None:
    v = np.random.default_rng(1).integers(50, 500, 200).astype(float)
    full = activity(v)
    head = activity(v[:150])
    for key in full:
        assert np.allclose(full[key][:150], head[key], equal_nan=True)


def test_ratio_percentile_and_acceleration_have_the_documented_meaning() -> None:
    v = np.array([10.0] * 30 + [40.0])
    assert volume_ratio(v, 20)[-1] == pytest.approx(4.0)
    assert volume_percentile(v, 31)[-1] == pytest.approx(1.0)
    z = np.array([0.0, 0.0, 0.0, 1.0, 2.0])
    assert volume_acceleration(z, 3)[3] == pytest.approx(1.0)


# -- bar closure ---------------------------------------------------------------------------


def test_an_unfinished_higher_timeframe_bar_is_never_used() -> None:
    bars = multi_tf(minutes=60 * 24 * 3)
    at = datetime(2026, 3, 3, 10, 37, tzinfo=UTC)
    h1 = bars.as_of(Timeframe.H1, at)
    assert h1 is not None
    assert h1["timestamp"][-1] == datetime(2026, 3, 3, 9, 0, tzinfo=UTC)  # 10:00 bar is forming
    assert h1["available_at"][-1] <= at
    m1 = bars.as_of(Timeframe.M1, at)
    assert m1 is not None
    assert m1["timestamp"][-1] == datetime(2026, 3, 3, 10, 36, tzinfo=UTC)
    assert forming_bar_open(Timeframe.H1, at) == datetime(2026, 3, 3, 10, 0, tzinfo=UTC)
    assert forming_bar_open(Timeframe.M30, at) == datetime(2026, 3, 3, 10, 30, tzinfo=UTC)


def test_a_bar_becomes_available_exactly_at_its_close() -> None:
    bars = multi_tf(minutes=60 * 6)
    at = datetime(2026, 3, 2, 3, 0, tzinfo=UTC)
    h1 = bars.as_of(Timeframe.H1, at)
    assert h1 is not None
    assert h1["timestamp"][-1] == datetime(2026, 3, 2, 2, 0, tzinfo=UTC)  # the 03:00 close counts
    assert closed_as_of(bars.frames[Timeframe.M5], at)["available_at"].max() == at


def test_frames_without_available_at_or_with_naive_time_are_refused() -> None:
    m1 = m1_series(30)
    with pytest.raises(FrameError, match="available_at"):
        closed_as_of(m1, datetime(2026, 3, 2, tzinfo=UTC))
    naive = m1.with_columns(m1["timestamp"].dt.replace_time_zone(None))
    with pytest.raises(FrameError, match="UTC"):
        with_available_at(naive, Timeframe.M1)
    with pytest.raises(FrameError, match="missing"):
        with_available_at(m1.drop("spread"), Timeframe.M1)


@given(minute=st.integers(min_value=61, max_value=60 * 24 * 2))
@settings(max_examples=30, deadline=None)
def test_closed_bars_never_include_the_future(minute: int) -> None:
    bars = multi_tf(minutes=60 * 24 * 3 + 7)
    at = datetime(2026, 3, 2, tzinfo=UTC) + timedelta(minutes=minute)
    for tf in bars.available():
        frame = bars.as_of(tf, at)
        assert frame is not None
        assert frame.filter(pl.col("available_at") > at).height == 0


# -- deterministic resampling against an independent aggregation ---------------------------


def test_derived_frames_equal_an_independent_aggregation_inside_open_hours() -> None:
    m1 = m1_series(60 * 4)  # Monday 00:00-04:00 UTC, an open market
    derived = derive_from_m1(m1, clock=PROFILE.clock, calendar=PROFILE.validation.calendar)
    for tf in (Timeframe.M5, Timeframe.M15, Timeframe.M30, Timeframe.H1):
        expected = resample(m1, tf.minutes)
        cmp = compare_with_broker(derived[tf], expected, tf)
        assert cmp.common_bars > 0
        assert cmp.exact, (tf, cmp)
        assert cmp.volume_mismatches == 0


def test_compare_with_broker_reports_a_difference() -> None:
    base = resample(m1_series(60), 15)
    bent = base.with_columns((base["high"] + 1.0).alias("high"))
    cmp = compare_with_broker(bent, base, Timeframe.M15)
    assert cmp.ohlc_mismatches == base.height
    assert not cmp.exact
    assert cmp.max_abs_price_diff == pytest.approx(1.0)


def test_from_frames_marks_availability_per_timeframe() -> None:
    m1 = m1_series(60)
    bars = from_frames({Timeframe.M5: resample(m1, 5), Timeframe.M15: resample(m1, 15)})
    assert bars.available() == (Timeframe.M5, Timeframe.M15)
    m5 = bars.frames[Timeframe.M5]
    assert (m5["available_at"] - m5["timestamp"]).dt.total_minutes().unique().to_list() == [5]


# -- patterns ------------------------------------------------------------------------------


def test_strong_body_pin_bar_and_engulfing_on_hand_made_candles() -> None:
    o = [10.0, 10.0, 10.0, 12.0]
    h = [11.0, 10.5, 10.2, 12.2]
    lo = [9.9, 8.0, 8.0, 9.8]
    c = [10.9, 10.4, 9.9, 10.1]
    assert strong_body(o, h, lo, c).tolist() == [1, 0, 0, -1]
    assert pin_bar(o, h, lo, c).tolist()[1] == 1  # long lower wick rejects lower prices
    o2, h2, l2, c2 = [10.0, 9.8], [10.1, 10.4], [9.7, 9.7], [9.8, 10.3]
    assert engulfing(o2, h2, l2, c2).tolist() == [0, 1]


def test_inside_outside_expansion_compression_breakout_and_failed_breakout() -> None:
    h = [10.0, 9.5, 11.0, 11.5]
    lo = [8.0, 8.5, 7.0, 7.5]
    assert inside_bar(h, lo).tolist() == [0, 1, 0, 0]
    assert outside_bar(h, lo).tolist() == [0, 0, 1, 0]
    atr = [1.0] * 4
    assert range_expansion(h, lo, atr, k=1.5).tolist() == [1, 0, 1, 1]
    flat_h, flat_l = [10.0] * 6, [9.9] * 6
    assert compression(flat_h, flat_l, [1.0] * 6, bars=3, ratio=0.6)[-1] == 1
    hh = [10, 10, 10, 10, 10, 12.0]
    ll = [9, 9, 9, 9, 9, 10.5]
    cc = [9.5, 9.5, 9.5, 9.5, 9.5, 11.5]
    assert breakout(hh, ll, cc, lookback=5)[-1] == 1
    hh2 = [10, 10, 10, 10, 10, 11.0]
    cc2 = [9.5, 9.5, 9.5, 9.5, 9.5, 9.8]
    assert failed_breakout(hh2, ll, cc2, lookback=5)[-1] == -1


@given(st.integers(min_value=0, max_value=10_000), st.integers(min_value=40, max_value=150))
@settings(max_examples=50, deadline=None)
def test_patterns_are_causal_truncation_and_future_garbage(seed: int, cut: int) -> None:
    rng = np.random.default_rng(seed)
    n = 200
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.5, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.5, n))
    atr = np.full(n, 1.0)
    full = detect_patterns(open_, high, low, close, atr)
    head = detect_patterns(open_[:cut], high[:cut], low[:cut], close[:cut], atr[:cut])
    junk_c, junk_h, junk_l = close.copy(), high.copy(), low.copy()
    junk_c[cut:] += rng.normal(0, 50, n - cut)
    junk_h[cut:] += 100
    junk_l[cut:] -= 100
    junk = detect_patterns(open_, junk_h, junk_l, junk_c, atr)
    for name in full:
        assert np.array_equal(full[name][:cut], head[name]), name
        assert np.array_equal(full[name][:cut], junk[name][:cut]), name
