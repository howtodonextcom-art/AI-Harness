"""Edge Program signal generators on hand-built SYNTHETIC bars (rules and causality only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl
import pytest
from polars.testing import assert_frame_equal

from xau_edge.domain.bars import BAR_SCHEMA
from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.history import daily_from_h1
from xau_edge.strategies.edge_program import (
    SERVER_CLOCK,
    SPECS,
    VARIANTS,
    compression_ratio,
    daily_momentum,
    edge_context,
    generate_signals,
    get_variant,
    prior_channel,
    server_daily_bars,
    variant_signals,
    variants_of,
)

H1 = Timeframe.H1
H4 = Timeframe.H4


def _frame(
    start: datetime, opens: np.ndarray, closes: np.ndarray, tf: Timeframe = H1, pad: float = 0.1
) -> pl.DataFrame:
    n = opens.size
    return pl.DataFrame(
        {
            "timestamp": [start + i * timedelta(minutes=tf.minutes) for i in range(n)],
            "open": opens,
            "high": np.maximum(opens, closes) + pad,
            "low": np.minimum(opens, closes) - pad,
            "close": closes,
            "tick_volume": np.full(n, 100),
            "spread": np.full(n, 25),
            "real_volume": [None] * n,
        },
        schema=BAR_SCHEMA,
    )


def _flat(start: datetime, n: int, tf: Timeframe = H1, price: float = 2000.0) -> pl.DataFrame:
    return _frame(start, np.full(n, price), np.full(n, price), tf)


def _set(
    frame: pl.DataFrame,
    ts: datetime,
    open_: float,
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
) -> pl.DataFrame:
    hit = pl.col("timestamp") == ts
    assert frame.filter(hit).height == 1
    hi = max(open_, close) + 0.1 if high is None else high
    lo = min(open_, close) - 0.1 if low is None else low
    return frame.with_columns(
        pl.when(hit).then(pl.lit(open_)).otherwise(pl.col("open")).alias("open"),
        pl.when(hit).then(pl.lit(close)).otherwise(pl.col("close")).alias("close"),
        pl.when(hit).then(pl.lit(hi)).otherwise(pl.col("high")).alias("high"),
        pl.when(hit).then(pl.lit(lo)).otherwise(pl.col("low")).alias("low"),
    )


def _walk(start: datetime, n: int, tf: Timeframe, seed: int) -> pl.DataFrame:
    """Random walk with slowly cycling volatility, so compression and expansion both occur."""
    rng = np.random.default_rng(seed)
    sigma = 1.0 + 0.8 * np.sin(np.arange(n) / 40.0)
    close = 2000.0 + np.cumsum(rng.normal(0.0, sigma))
    opens = np.concatenate([[2000.0], close[:-1]])
    frame = _frame(start, opens, close, tf)
    wick = np.abs(rng.normal(0.0, 0.3 * sigma))
    return frame.with_columns(
        (pl.col("high") + pl.Series(wick)).alias("high"),
        (pl.col("low") - pl.Series(wick[::-1].copy())).alias("low"),
    )


def _times(sig: pl.DataFrame) -> list[tuple[datetime, int]]:
    return list(zip(sig["timestamp"].to_list(), sig["direction"].to_list(), strict=True))


# --- registry -------------------------------------------------------------------------------


def test_grid_has_exactly_eighteen_registered_variants() -> None:
    assert len(VARIANTS) == 18
    assert set(VARIANTS) == {
        "H01-theta0.3", "H01-theta0.6", "H01-theta0.9",
        "H02-b0.0", "H02-b0.25", "H02-b0.5",
        "H03-c0.8", "H03-c0.9", "H03-c1.0",
        "H04-L10", "H04-L20", "H04-L40",
        "H05-s1.5", "H05-s2.0", "H05-s2.5",
        "H06-N20", "H06-N40", "H06-N80",
    }  # fmt: skip
    assert all(len(variants_of(h)) == 3 for h in SPECS)


@pytest.mark.parametrize(
    ("hypothesis", "stop", "target", "hold_h1", "cooldown"),
    [
        ("H01", 1.5, 3.0, 6, 0),
        ("H02", 1.5, 3.0, 8, 0),
        ("H03", 1.5, 3.0, 24, 12),
        ("H04", 1.5, 3.0, 24, 6),
        ("H05", 1.5, 1.0, 6, 3),
        ("H06", 2.0, 4.0, 120, 6),
    ],
)
def test_registered_exits_and_holds_in_execution_bars(
    hypothesis: str, stop: float, target: float, hold_h1: int, cooldown: int
) -> None:
    spec = SPECS[hypothesis]
    assert (spec.stop_atr, spec.target_atr, spec.cooldown_bars) == (stop, target, cooldown)
    assert spec.hold_execution_bars == hold_h1


def test_unknown_variant_and_hypothesis_are_rejected() -> None:
    with pytest.raises(ValueError, match=r"H03-c0\.9"):
        get_variant("H03-c0.7")
    with pytest.raises(ValueError, match="H06"):
        variants_of("H07")


def test_params_identify_the_variant() -> None:
    p = get_variant("H06-N40").params()
    assert p["variant"] == "H06-N40"
    assert p["value"] == 40
    assert p["hold_execution_bars"] == 120
    assert p["signal_timeframe"] == "H4"


# --- H01 ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("day", "london_utc", "ny_utc"),
    [(datetime(2011, 1, 10, tzinfo=UTC), 8, 13), (datetime(2011, 7, 11, tzinfo=UTC), 7, 12)],
)
def test_h01_session_open_bars_follow_dst(day: datetime, london_utc: int, ny_utc: int) -> None:
    bars = _flat(day - timedelta(days=1), 72)
    bars = _set(bars, day.replace(hour=0), 2000.0, 1999.0)  # Tokyo 09:00 JST, down
    bars = _set(bars, day.replace(hour=london_utc), 2000.0, 2001.0)  # London 08:00, up
    bars = _set(bars, day.replace(hour=ny_utc), 2000.0, 2001.0)  # New York 08:00, up
    bars = _set(bars, day.replace(hour=10), 2000.0, 2001.0)  # not a session open
    other = london_utc + 1 if london_utc == 7 else london_utc - 1  # the other DST regime's hour
    bars = _set(bars, day.replace(hour=other), 2000.0, 2001.0)
    sig = generate_signals("H01-theta0.9", bars)
    assert _times(sig) == [
        (day.replace(hour=0), -1),
        (day.replace(hour=london_utc), 1),
        (day.replace(hour=ny_utc), 1),
    ]
    assert (sig["decision_time"] == sig["timestamp"] + timedelta(hours=1)).all()
    assert sig["max_hold_bars"].to_list() == [6, 6, 6]


def test_h01_small_bodies_below_theta_give_no_signal() -> None:
    day = datetime(2011, 1, 10, tzinfo=UTC)
    bars = _set(_flat(day - timedelta(days=1), 48), day.replace(hour=8), 2000.0, 2000.05)
    assert generate_signals("H01-theta0.3", bars).height == 0


# --- H02 ------------------------------------------------------------------------------------


def _h02_bars() -> pl.DataFrame:
    d1 = datetime(2011, 1, 11, tzinfo=UTC)
    d2 = datetime(2011, 1, 12, tzinfo=UTC)
    d3 = datetime(2011, 1, 13, tzinfo=UTC)
    bars = _flat(d1 - timedelta(days=1), 24 * 4)
    bars = _set(bars, d1.replace(hour=2), 2000.0, 2000.0, high=2001.0)
    bars = _set(bars, d1.replace(hour=4), 2000.0, 2000.0, low=1999.0)
    bars = _set(bars, d1.replace(hour=9), 2000.0, 2001.5)  # first breakout: LONG
    bars = _set(bars, d1.replace(hour=11), 2000.0, 2002.5)  # second breakout same day: ignored
    bars = _set(bars, d2.replace(hour=7), 2000.0, 1998.0)  # day 2 breakdown: SHORT
    return _set(bars, d3.replace(hour=16), 2000.0, 2003.0)  # after 15:00 UTC: ignored


@pytest.mark.parametrize("variant", ["H02-b0.0", "H02-b0.25", "H02-b0.5"])
def test_h02_first_breakout_of_the_asia_range_per_day(variant: str) -> None:
    sig = generate_signals(variant, _h02_bars())
    assert _times(sig) == [
        (datetime(2011, 1, 11, 9, tzinfo=UTC), 1),
        (datetime(2011, 1, 12, 7, tzinfo=UTC), -1),
    ]


def test_h02_day_with_a_missing_asia_bar_has_no_signal() -> None:
    bars = _h02_bars().filter(pl.col("timestamp") != datetime(2011, 1, 11, 3, tzinfo=UTC))
    sig = generate_signals("H02-b0.0", bars)
    assert _times(sig) == [(datetime(2011, 1, 12, 7, tzinfo=UTC), -1)]


# --- H03 ------------------------------------------------------------------------------------


def test_compression_ratio_uses_only_bars_before_t() -> None:
    atr = np.arange(1.0, 201.0)
    ratio = compression_ratio(atr, 120)
    assert np.isnan(ratio[:120]).all()
    for t in (120, 150, 199):
        assert ratio[t] == pytest.approx(atr[t - 1] / atr[t - 120 : t].mean())
    atr[130] = np.nan
    assert np.isnan(compression_ratio(atr, 120)[131])


def test_prior_channel_excludes_the_current_bar() -> None:
    high = np.array([1.0, 5.0, 2.0, 3.0, 9.0])
    low = -high
    hh, ll = prior_channel(high, low, 3)
    assert np.isnan(hh[:3]).all()
    assert hh[3] == 5.0
    assert hh[4] == 5.0
    assert ll[4] == -5.0


def _vol_bars(first_range: float, second_range: float) -> tuple[pl.DataFrame, datetime]:
    start = datetime(2011, 1, 3, tzinfo=UTC)
    bars = pl.concat(
        [
            _frame(start, np.full(130, 2000.0), np.full(130, 2000.0), pad=first_range / 2),
            _frame(
                start + timedelta(hours=130),
                np.full(60, 2000.0),
                np.full(60, 2000.0),
                pad=second_range / 2,
            ),
        ]
    )
    return bars, start + timedelta(hours=165)


@pytest.mark.parametrize("variant", ["H03-c0.8", "H03-c0.9", "H03-c1.0"])
def test_h03_breakout_after_compression_with_cooldown(variant: str) -> None:
    bars, t = _vol_bars(2.0, 0.2)
    bars = _set(bars, t, 2000.0, 2001.5)
    bars = _set(bars, t + timedelta(hours=1), 2000.0, 2002.5)  # inside the 12-bar cooldown
    bars = _set(bars, t + timedelta(hours=13), 2000.0, 2003.5)  # after it (fresh 24-bar high)
    sig = generate_signals(variant, bars)
    assert _times(sig) == [(t, 1), (t + timedelta(hours=13), 1)]
    assert sig["max_hold_bars"].to_list() == [24, 24]


def test_h03_breakout_during_expansion_is_ignored() -> None:
    bars, t = _vol_bars(0.2, 2.0)
    bars = _set(bars, t, 2000.0, 2002.0)
    assert generate_signals("H03-c1.0", bars).height == 0


# --- H04 ------------------------------------------------------------------------------------


def test_server_daily_bars_availability_and_dropped_short_days() -> None:
    start = datetime(2011, 1, 3, 22, tzinfo=UTC)  # server midnight in winter (NY 17:00)
    bars = _walk(start, 24 * 4, H1, 1)
    short_day = (pl.col("timestamp") >= start + timedelta(hours=30)) & (
        pl.col("timestamp") < start + timedelta(hours=45)
    )
    bars = bars.filter(~short_day)  # day 2 keeps 9 bars -> dropped
    daily = server_daily_bars(bars)
    assert daily.height == 3
    assert (daily["available_at"] == daily["last_open"] + timedelta(hours=1)).all()
    assert daily["available_at"][0] == start + timedelta(hours=24)
    reference = daily_from_h1(bars, SERVER_CLOCK)
    assert daily["close"].to_list() == reference["close"].to_list()
    assert daily["timestamp"].to_list() == reference["timestamp"].to_list()


def _trend_with_dip(dip_at: int) -> pl.DataFrame:
    n = 24 * 31
    close = 2000.0 + 0.05 * np.arange(n)
    close[dip_at - 1] -= 3.0
    opens = np.concatenate([[2000.0], close[:-1]])
    return _frame(datetime(2011, 1, 3, tzinfo=UTC), opens, close)


@pytest.mark.parametrize(("variant", "expected"), [("H04-L10", 1), ("H04-L20", 1), ("H04-L40", 0)])
def test_h04_ema_cross_in_the_daily_trend_direction(variant: str, expected: int) -> None:
    bars = _trend_with_dip(700)
    sig = generate_signals(variant, bars)
    assert sig.height == expected
    if expected:
        assert _times(sig) == [(bars["timestamp"][700], 1)]  # the cross down at 699 is no SHORT


def test_h04_uses_only_daily_bars_closed_at_the_decision() -> None:
    bars = _walk(datetime(2011, 1, 3, tzinfo=UTC), 24 * 20, H1, 3)
    ctx = edge_context(bars)
    m = daily_momentum(ctx, 1)
    daily = ctx.daily
    decision = ctx.h1["available_at"].to_list()
    avail = daily["available_at"].to_list()
    closes = daily["close"].to_list()
    for i in range(0, len(decision), 7):
        usable = [k for k, a in enumerate(avail) if a <= decision[i]]
        if len(usable) < 2:
            assert np.isnan(m[i])
            continue
        k = usable[-1]
        assert m[i] == np.sign(closes[k] - closes[k - 1])


# --- H05 ------------------------------------------------------------------------------------


def test_h05_threshold_uses_the_previous_bar_atr_and_stop_uses_the_current() -> None:
    start = datetime(2011, 1, 3, tzinfo=UTC)
    t = start + timedelta(hours=30)
    bars = _set(_flat(start, 40), t, 2000.0, 2000.32)
    sig = generate_signals("H05-s1.5", bars)
    assert _times(sig) == [(t, -1)]  # 0.32 >= 1.5 x 0.2 although < 1.5 x ATR(t)
    assert sig["atr"][0] == pytest.approx((13 * 0.2 + 0.52) / 14)
    assert (sig["stop_atr"][0], sig["target_atr"][0]) == (1.5, 1.0)
    assert generate_signals("H05-s2.0", bars).height == 0


def test_h05_cooldown_of_three_bars() -> None:
    start = datetime(2011, 1, 3, tzinfo=UTC)
    t = start + timedelta(hours=30)
    bars = _flat(start, 40)
    bars = _set(bars, t, 2000.0, 2001.0)
    bars = _set(bars, t + timedelta(hours=1), 2000.0, 1999.0)
    bars = _set(bars, t + timedelta(hours=3), 2000.0, 2001.0)
    sig = generate_signals("H05-s1.5", bars)
    assert _times(sig) == [(t, -1), (t + timedelta(hours=3), -1)]


# --- H06 ------------------------------------------------------------------------------------


def test_h06_h4_donchian_breakout_held_120_h1_bars() -> None:
    h1 = _flat(datetime(2011, 1, 3, tzinfo=UTC), 24 * 10)
    start4 = datetime(2011, 1, 3, 1, tzinfo=UTC)
    h4 = _flat(start4, 50, H4)
    t = start4 + timedelta(hours=4 * 25)
    h4 = _set(h4, t, 2000.0, 2001.0)
    sig = generate_signals("H06-N20", h1, h4)
    assert _times(sig) == [(t, 1)]
    assert sig["decision_time"][0] == t + timedelta(hours=4)
    assert sig["max_hold_bars"][0] == 120
    assert (sig["stop_atr"][0], sig["target_atr"][0]) == (2.0, 4.0)
    assert generate_signals("H06-N40", h1, h4).height == 0


def test_h06_without_h4_bars_is_refused() -> None:
    with pytest.raises(ValueError, match="H4"):
        generate_signals("H06-N20", _flat(datetime(2011, 1, 3, tzinfo=UTC), 50))


# --- causality ------------------------------------------------------------------------------


H1_START = datetime(2011, 1, 3, tzinfo=UTC)
H4_START = datetime(2011, 1, 3, 1, tzinfo=UTC)


def _data() -> tuple[pl.DataFrame, pl.DataFrame]:
    return _walk(H1_START, 24 * 50, H1, 11), _walk(H4_START, 6 * 50, H4, 12)


def _until(sig: pl.DataFrame, cut: datetime) -> pl.DataFrame:
    return sig.filter(pl.col("decision_time") <= cut)


def _mutate_after(frame: pl.DataFrame, cut: datetime, seed: int) -> pl.DataFrame:
    late = pl.col("timestamp") >= cut
    other = _walk(frame["timestamp"][0], frame.height, H1, seed)
    cols = ["open", "high", "low", "close"]
    return frame.with_columns(
        [pl.when(late).then(other[c] + 50.0).otherwise(pl.col(c)).alias(c) for c in cols]
    )


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_changing_bars_after_t_never_changes_signals_up_to_t(variant: str) -> None:
    h1, h4 = _data()
    cut = H1_START + timedelta(hours=803)
    full = variant_signals(variant, edge_context(h1, h4))
    changed = variant_signals(
        variant, edge_context(_mutate_after(h1, cut, 99), _mutate_after(h4, cut, 98))
    )
    assert_frame_equal(_until(full, cut), _until(changed, cut))


@pytest.mark.parametrize("variant", list(VARIANTS))
def test_truncating_after_a_server_day_end_never_changes_earlier_signals(variant: str) -> None:
    h1, h4 = _data()
    cut = datetime(2011, 2, 1, 22, tzinfo=UTC)  # 17:00 New York = server midnight
    assert SERVER_CLOCK.to_server_wall(cut).hour == 0
    full = variant_signals(variant, edge_context(h1, h4))
    h1_cut = h1.filter(pl.col("timestamp") < cut)
    h4_cut = h4.filter(pl.col("timestamp") + timedelta(hours=4) <= cut)
    cut_sig = variant_signals(variant, edge_context(h1_cut, h4_cut))
    assert_frame_equal(_until(full, cut), _until(cut_sig, cut))


def test_the_causality_fixture_produces_signals_for_every_hypothesis() -> None:
    h1, h4 = _data()
    ctx = edge_context(h1, h4)
    for hypothesis in SPECS:
        assert sum(variant_signals(v, ctx).height for v in variants_of(hypothesis)) > 0
