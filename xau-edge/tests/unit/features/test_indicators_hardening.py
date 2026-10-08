"""Hardening found by the independent reviews: input shapes, period rules, magnitude guard."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
from numpy.typing import NDArray

from tests.unit.features.test_indicators_behaviour import INDICATORS, _series
from xau_edge.features import indicators as ind

F = NDArray[np.float64]


@pytest.mark.parametrize("fn", [ind.rsi, ind.ema, ind.sma])
def test_integer_and_list_input_is_accepted(fn: Callable[..., F]) -> None:
    ints = list(range(1, 60))
    np.testing.assert_allclose(fn(ints, 5), fn(np.array(ints, dtype=float), 5), equal_nan=True)


@pytest.mark.parametrize("name", sorted(INDICATORS))
def test_empty_input_gives_empty_output(name: str) -> None:
    empty = np.array([], dtype=np.float64)
    for out in INDICATORS[name](empty, empty, empty):
        assert out.shape == (0,)


@pytest.mark.parametrize("period", [1, 0])
def test_rsi_and_adx_need_period_of_at_least_two(period: int) -> None:
    h, lo, c = _series(60)
    with pytest.raises(ValueError, match="period"):
        ind.rsi(c, period)
    with pytest.raises(ValueError, match="period"):
        ind.adx(h, lo, c, period)


@pytest.mark.parametrize("bad", [2.5, True, "3"])
def test_period_must_be_an_integer(bad: object) -> None:
    with pytest.raises(ValueError, match="integer"):
        ind.sma(np.arange(10.0), bad)  # type: ignore[arg-type]


def test_huge_magnitudes_are_rejected_instead_of_overflowing() -> None:
    with pytest.raises(ValueError, match="1e150"):
        ind.bollinger(np.array([1e200, 1e200, 3e200]), 2)


def test_flat_market_stochastic_is_zero_like_talib() -> None:
    flat = np.full(40, 2000.0)
    assert ind.stochastic(flat, flat, flat).k[-1] == pytest.approx(0.0)
