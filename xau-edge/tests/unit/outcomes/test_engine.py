"""Historical outcome engine: forward returns, excursions, barriers, directions, contamination."""

from __future__ import annotations

import numpy as np
import pytest

from xau_edge.outcomes.engine import OutcomeConfig, compute_outcomes

CFG = OutcomeConfig(horizons=(2, 4), neutral_threshold_atr=0.5, stop_atr=1.0, target_atr=2.0)


def _bars() -> dict[str, np.ndarray]:
    """close/high/low around anchor 0 (close 100, ATR 2): hand-checkable."""
    close = np.array([100.0, 101.0, 103.0, 99.0, 104.0, 98.0, 100.0])
    high = close + 0.5
    low = close - 0.5
    atr = np.full(close.size, 2.0)
    return {"high": high, "low": low, "close": close, "atr": atr}


def _run(ends: list[int], cfg: OutcomeConfig = CFG, **over: np.ndarray):  # type: ignore[no-untyped-def]
    d = _bars() | over
    return compute_outcomes(d["high"], d["low"], d["close"], d["atr"], np.array(ends), cfg)


def test_forward_return_and_atr_units() -> None:
    t = _run([0])
    # h=2: close[2]=103 ; h=4: close[4]=104
    np.testing.assert_allclose(t.forward_return[0], [0.03, 0.04])
    np.testing.assert_allclose(t.forward_atr[0], [1.5, 2.0])


def test_direction_uses_the_neutral_band_in_atr_units() -> None:
    t = _run([0])
    assert t.direction[0].tolist() == [1, 1]
    flat = _run([0], close=np.array([100.0, 100.2, 100.5, 100.4, 100.6, 100, 100]))
    assert flat.direction[0].tolist() == [0, 0]  # 0.5/2 = 0.25 ATR and 0.3 ATR < 0.5
    down = _run([0], close=np.array([100.0, 99, 97, 98, 96, 100, 100]))
    assert down.direction[0].tolist() == [-1, -1]


def test_neutral_boundary_is_exclusive_of_the_band() -> None:
    exactly = _run([0], close=np.array([100.0, 100, 101.0, 100, 101.0, 100, 100]))  # +0.5 ATR
    assert exactly.direction[0].tolist() == [1, 1]
    just_inside = _run([0], close=np.array([100.0, 100, 100.99, 100, 100.99, 100, 100]))
    assert just_inside.direction[0].tolist() == [0, 0]


def test_excursions_use_highs_and_lows_after_the_anchor_only() -> None:
    t = _run([0])
    # h=2 window = bars 1..2: highs 101.5, 103.5 ; lows 100.5, 102.5
    assert t.max_up_atr[0, 0] == pytest.approx((103.5 - 100.0) / 2.0)
    assert t.max_down_atr[0, 0] == pytest.approx(0.0)  # nothing below the reference
    # h=4 adds bars 3..4: low 98.5 -> down 1.5 -> 0.75 ATR ; high 104.5 -> 2.25 ATR
    assert t.max_up_atr[0, 1] == pytest.approx(2.25)
    assert t.max_down_atr[0, 1] == pytest.approx(0.75)


def test_long_barrier_target_first_with_r_multiple() -> None:
    # target = +2 ATR = +4 -> 104 ; stop = -1 ATR = -2 -> 98
    t = _run([0])
    assert t.long_barrier[0, 0] == 0  # h=2: high 103.5 < 104, low stays above 98
    assert t.long_barrier[0, 1] == 1  # h=4: bar 4 high 104.5 >= 104
    assert t.long_barrier_bars[0, 1] == 4
    assert t.long_r[0, 1] == pytest.approx(2.0)


def test_unresolved_trade_is_marked_to_market_in_r() -> None:
    t = _run([0])
    # h=2, neither barrier: R = (103 - 100) / (1.0 * 2) = 1.5
    assert t.long_r[0, 0] == pytest.approx(1.5)
    qc = np.array([100.0, 99.5, 99.2, 99.0, 99.4, 100, 100])
    quiet = _run([0], close=qc, high=qc + 0.5, low=qc - 0.5)
    assert quiet.short_barrier[0, 0] == 0
    assert quiet.short_r[0, 0] == pytest.approx((100.0 - 99.2) / (1.0 * 2.0))
    assert quiet.long_r[0, 0] == pytest.approx(-(100.0 - 99.2) / (1.0 * 2.0))


def test_short_barrier_stop_first() -> None:
    # short: target = 96, stop = 102 ; bar 2 high 103.5 >= 102 -> stop
    t = _run([0])
    assert t.short_barrier[0, 0] == -1
    assert t.short_barrier_bars[0, 0] == 2
    assert t.short_r[0, 0] == pytest.approx(-1.0)


def test_same_bar_target_and_stop_resolves_to_the_stop() -> None:
    close = np.array([100.0, 100.0, 100.0, 100.0, 100.0])
    high = np.array([100.0, 105.0, 100, 100, 100])  # bar 1 reaches +5
    low = np.array([100.0, 95.0, 100, 100, 100])  # and -5 in the same bar
    atr = np.full(5, 2.0)
    t = compute_outcomes(high, low, close, atr, np.array([0]), CFG)
    assert t.long_barrier[0, 0] == -1
    assert t.short_barrier[0, 0] == -1
    assert t.long_r[0, 0] == pytest.approx(-1.0)


def test_outcomes_ignore_every_bar_after_the_horizon() -> None:
    base = _run([0])
    d = _bars()
    d["close"][5:] = 1e6
    d["high"][5:] = 2e6
    d["low"][5:] = -1e6
    other = compute_outcomes(d["high"], d["low"], d["close"], d["atr"], np.array([0]), CFG)
    for name in base._fields:
        np.testing.assert_array_equal(getattr(base, name), getattr(other, name), err_msg=name)


def test_outcomes_ignore_bars_before_the_anchor_except_through_atr() -> None:
    d = _bars()
    a = compute_outcomes(d["high"], d["low"], d["close"], d["atr"], np.array([2]), CFG)
    d2 = _bars()
    d2["close"][:2] = -50.0
    d2["high"][:2] = 50.0
    d2["low"][:2] = -90.0
    b = compute_outcomes(d2["high"], d2["low"], d2["close"], d2["atr"], np.array([2]), CFG)
    for name in a._fields:
        np.testing.assert_array_equal(getattr(a, name), getattr(b, name), err_msg=name)


def test_anchors_without_enough_future_or_atr_are_nan_or_zero_coded() -> None:
    t = _run([5])  # only 1 bar left; both horizons incomplete
    assert np.isnan(t.forward_return[0]).all()
    assert np.isnan(t.long_r[0]).all()
    assert t.direction[0].tolist() == [0, 0]
    assert t.complete[0].tolist() == [False, False]
    nan_atr = _run([0], atr=np.full(7, np.nan))
    assert np.isnan(nan_atr.forward_atr[0]).all()
    assert nan_atr.complete[0].tolist() == [False, False]


def test_many_anchors_match_a_one_by_one_loop() -> None:
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(size=300))
    high, low = close + rng.uniform(0, 1, 300), close - rng.uniform(0, 1, 300)
    atr = np.full(300, 1.5)
    cfg = OutcomeConfig(horizons=(5, 20), neutral_threshold_atr=0.3, stop_atr=1.0, target_atr=1.5)
    ends = np.arange(10, 270, 7)
    bulk = compute_outcomes(high, low, close, atr, ends, cfg)
    for row, e in enumerate(ends):
        one = compute_outcomes(high, low, close, atr, np.array([e]), cfg)
        for name in bulk._fields:
            np.testing.assert_array_equal(
                getattr(bulk, name)[row], getattr(one, name)[0], err_msg=name
            )


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="horizons"):
        OutcomeConfig(horizons=())
    with pytest.raises(ValueError, match="horizons"):
        OutcomeConfig(horizons=(10, 5))
    with pytest.raises(ValueError, match="target_atr"):
        OutcomeConfig(stop_atr=2.0, target_atr=0.0)
    with pytest.raises(ValueError, match="length"):
        compute_outcomes(np.ones(3), np.ones(2), np.ones(3), np.ones(3), np.array([0]), CFG)
    with pytest.raises(ValueError, match="anchor"):
        _run([100])


def test_excursions_are_never_negative_when_price_only_falls() -> None:
    falling = np.array([100.0, 99.0, 98.0, 97.0, 96.0, 95.0, 94.0])
    t = _run([0], close=falling, high=falling + 0.5, low=falling - 0.5)
    assert (t.max_up_atr[0] == 0.0).all()
    rising = falling[::-1].copy()
    r = _run([0], close=rising, high=rising + 0.5, low=rising - 0.5)
    assert (r.max_down_atr[0] == 0.0).all()
