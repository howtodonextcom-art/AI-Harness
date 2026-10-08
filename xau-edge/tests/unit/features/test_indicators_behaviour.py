"""Behavioural tests: hand-computed values, no look-ahead (repainting), input validation."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from xau_edge.features import indicators as ind

F = NDArray[np.float64]


def _series(n: int = 120, seed: int = 7) -> tuple[F, F, F]:
    rng = np.random.default_rng(seed)
    close = 2000 + np.cumsum(rng.normal(0, 2, n))
    high = close + np.abs(rng.normal(0, 1, n))
    low = close - np.abs(rng.normal(0, 1, n))
    return high, low, close


# ---- hand-computed values -------------------------------------------------------------------


def test_sma_hand_values() -> None:
    out = ind.sma(np.array([1.0, 2.0, 3.0, 4.0, 5.0]), 3)
    assert np.isnan(out[:2]).all()
    np.testing.assert_allclose(out[2:], [2.0, 3.0, 4.0])


def test_ema_is_seeded_with_sma_then_recursive() -> None:
    out = ind.ema(np.array([1.0, 2.0, 3.0, 4.0]), 3)
    k = 2 / (3 + 1)
    assert math.isclose(out[2], 2.0)
    assert math.isclose(out[3], 4.0 * k + 2.0 * (1 - k))


def test_rsi_extremes() -> None:
    rising = np.arange(1.0, 40.0)
    falling = rising[::-1].copy()
    assert ind.rsi(rising, 14)[-1] == pytest.approx(100.0)
    assert ind.rsi(falling, 14)[-1] == pytest.approx(0.0)
    assert ind.rsi(np.full(40, 5.0), 14)[-1] == pytest.approx(0.0)  # TA-Lib: no gains -> 0


def test_true_range_uses_previous_close() -> None:
    high = np.array([10.0, 12.0])
    low = np.array([9.0, 11.5])
    close = np.array([9.5, 12.0])
    out = ind.true_range(high, low, close)
    assert np.isnan(out[0])
    assert out[1] == pytest.approx(2.5)  # |high - prev close| beats high - low


def test_returns_hand_values() -> None:
    close = np.array([100.0, 110.0, 99.0])
    s = ind.simple_returns(close)
    lg = ind.log_returns(close)
    assert np.isnan(s[0])
    assert np.isnan(lg[0])
    np.testing.assert_allclose(s[1:], [0.1, -0.1])
    np.testing.assert_allclose(lg[1:], [math.log(1.1), math.log(0.9)])
    np.testing.assert_allclose(ind.rolling_returns(close, 2)[2], 99.0 / 100.0 - 1)


def test_rolling_volatility_is_sample_std_of_log_returns() -> None:
    _, _, close = _series(60)
    window = 10
    out = ind.rolling_volatility(close, window)
    lr = np.diff(np.log(close))
    assert np.isnan(out[:window]).all()
    assert out[window] == pytest.approx(np.std(lr[:window], ddof=1))
    assert out[-1] == pytest.approx(np.std(lr[-window:], ddof=1))


def test_bollinger_bands_are_symmetric_around_the_mean() -> None:
    _, _, close = _series(60)
    b = ind.bollinger(close, 20, 2.0)
    np.testing.assert_allclose((b.upper + b.lower) / 2, b.middle, equal_nan=True)


def test_stochastic_is_bounded() -> None:
    high, low, close = _series(200)
    s = ind.stochastic(high, low, close)
    for line in (s.k, s.d):
        valid = line[~np.isnan(line)]
        assert valid.min() >= 0
        assert valid.max() <= 100


def test_flat_market_has_defined_indicators() -> None:
    flat = np.full(80, 2000.0)
    assert ind.atr(flat, flat, flat, 14)[-1] == pytest.approx(0.0)
    assert ind.adx(flat, flat, flat, 14).adx[-1] == pytest.approx(0.0)
    assert np.isfinite(ind.stochastic(flat, flat, flat).k[-1])


# ---- no look-ahead: appending future bars never changes past values -------------------------

Indicator = Callable[[F, F, F], list[F]]


def _adx(h: F, low: F, c: F) -> list[F]:
    r = ind.adx(h, low, c, 14)
    return [r.adx, r.plus_di, r.minus_di]


def _macd(_h: F, _low: F, c: F) -> list[F]:
    r = ind.macd(c)
    return [r.macd, r.signal, r.histogram]


def _stoch(h: F, low: F, c: F) -> list[F]:
    r = ind.stochastic(h, low, c)
    return [r.k, r.d]


def _boll(_h: F, _low: F, c: F) -> list[F]:
    r = ind.bollinger(c)
    return [r.upper, r.middle, r.lower]


INDICATORS: dict[str, Indicator] = {
    "ema": lambda h, low, c: [ind.ema(c, 20)],
    "sma": lambda h, low, c: [ind.sma(c, 20)],
    "rsi": lambda h, low, c: [ind.rsi(c, 14)],
    "atr": lambda h, low, c: [ind.atr(h, low, c, 14)],
    "adx": _adx,
    "macd": _macd,
    "stoch": _stoch,
    "bollinger": _boll,
    "simple_returns": lambda h, low, c: [ind.simple_returns(c)],
    "log_returns": lambda h, low, c: [ind.log_returns(c)],
    "rolling_returns": lambda h, low, c: [ind.rolling_returns(c, 5)],
    "rolling_vol": lambda h, low, c: [ind.rolling_volatility(c, 10)],
}


@pytest.mark.parametrize("name", sorted(INDICATORS))
@pytest.mark.parametrize("cut", [60, 90, 119])
def test_indicator_does_not_repaint(name: str, cut: int) -> None:
    high, low, close = _series(120)
    full = INDICATORS[name](high, low, close)
    part = INDICATORS[name](high[:cut], low[:cut], close[:cut])
    for f, p in zip(full, part, strict=True):
        np.testing.assert_allclose(f[:cut], p, equal_nan=True, rtol=0, atol=0)


@pytest.mark.parametrize("name", sorted(INDICATORS))
def test_indicator_does_not_mutate_inputs(name: str) -> None:
    high, low, close = _series(80)
    before = (high.copy(), low.copy(), close.copy())
    INDICATORS[name](high, low, close)
    for a, b in zip((high, low, close), before, strict=True):
        np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("name", sorted(INDICATORS))
def test_series_shorter_than_warmup_is_all_nan(name: str) -> None:
    high, low, close = _series(1)
    for out in INDICATORS[name](high, low, close):
        assert out.shape == (1,)
        assert np.isnan(out).all()


@pytest.mark.parametrize("name", ["ema", "sma", "rsi", "atr", "adx", "macd", "stoch", "bollinger"])
def test_series_just_below_warmup_is_all_nan(name: str) -> None:
    high, low, close = _series(10)
    for out in INDICATORS[name](high, low, close):
        assert np.isnan(out).all()


# ---- validation -----------------------------------------------------------------------------


@pytest.mark.parametrize("period", [0, -3])
def test_period_must_be_positive(period: int) -> None:
    with pytest.raises(ValueError, match="period"):
        ind.ema(np.arange(10.0), period)


def test_non_finite_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="finite"):
        ind.sma(np.array([1.0, np.nan, 3.0]), 2)
    with pytest.raises(ValueError, match="finite"):
        ind.log_returns(np.array([1.0, np.inf]))


def test_log_returns_reject_non_positive_prices() -> None:
    with pytest.raises(ValueError, match="positive"):
        ind.log_returns(np.array([1.0, 0.0, 2.0]))


def test_mismatched_lengths_are_rejected() -> None:
    with pytest.raises(ValueError, match="length"):
        ind.atr(np.ones(5), np.ones(4), np.ones(5), 2)


def test_macd_requires_fast_below_slow() -> None:
    with pytest.raises(ValueError, match="fast"):
        ind.macd(np.arange(50.0), fast=26, slow=12)


def test_two_dimensional_input_is_rejected() -> None:
    with pytest.raises(ValueError, match="1-D"):
        ind.sma(np.ones((3, 3)), 2)


def test_high_below_low_is_rejected() -> None:
    with pytest.raises(ValueError, match="high"):
        ind.true_range(np.array([1.0, 1.0]), np.array([2.0, 2.0]), np.array([1.5, 1.5]))


# ---- properties -----------------------------------------------------------------------------

prices = st.lists(
    st.floats(min_value=1.0, max_value=5000.0, allow_nan=False, allow_infinity=False),
    min_size=30,
    max_size=120,
)


@settings(max_examples=60, deadline=None)
@given(prices)
def test_rsi_within_bounds_and_ema_within_range(values: list[float]) -> None:
    arr = np.array(values)
    r = ind.rsi(arr, 14)
    valid = r[~np.isnan(r)]
    assert ((valid >= 0) & (valid <= 100)).all()
    e = ind.ema(arr, 10)
    ev = e[~np.isnan(e)]
    assert ev.min() >= arr.min() - 1e-9
    assert ev.max() <= arr.max() + 1e-9
