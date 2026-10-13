"""Golden tests: indicators must reproduce TA-Lib on a fixed synthetic input.

Fixture provenance is recorded inside ``tests/fixtures/talib_golden.json``. TA-Lib is not a
runtime or test dependency; only its recorded output is used, so these tests are the independent
reference required by the plan (Epic 04 acceptance).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from xau_edge.features import indicators as ind

FIXTURE = Path(__file__).parents[2] / "fixtures" / "talib_golden.json"
RTOL = 1e-9
ATOL = 1e-9


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _arr(values: list[float | None]) -> NDArray[np.float64]:
    return np.array([np.nan if v is None else v for v in values], dtype=np.float64)


def _assert_matches(actual: NDArray[np.float64], expected: list[float | None]) -> None:
    want = _arr(expected)
    assert actual.shape == want.shape
    # the warm-up (NaN) region must be identical, not merely close
    np.testing.assert_array_equal(np.isnan(actual), np.isnan(want))
    np.testing.assert_allclose(actual, want, rtol=RTOL, atol=ATOL, equal_nan=True)


def _assert_matches_trimmed(
    actual: NDArray[np.float64], expected: list[float | None], first_valid: int
) -> None:
    """TA-Lib trims MACD and STOCH outputs to a common start; ours start at the line's own warm-up.

    Check our documented first valid index, then equality wherever TA-Lib reports a value.
    """
    want = _arr(expected)
    assert actual.shape == want.shape
    assert np.isnan(actual[:first_valid]).all()
    assert not np.isnan(actual[first_valid:]).any()
    kept = ~np.isnan(want)
    np.testing.assert_allclose(actual[kept], want[kept], rtol=RTOL, atol=ATOL)


def _ohlc(
    golden: dict[str, Any],
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
    data = golden["input"]
    return _arr(data["open"]), _arr(data["high"]), _arr(data["low"]), _arr(data["close"])


@pytest.mark.parametrize("period", [9, 20, 50, 200])
def test_ema_matches_talib(golden: dict[str, Any], period: int) -> None:
    close = _ohlc(golden)[3]
    _assert_matches(ind.ema(close, period), golden["ema"][str(period)])


def test_sma_matches_talib(golden: dict[str, Any]) -> None:
    _assert_matches(ind.sma(_ohlc(golden)[3], 20), golden["sma"]["20"])


def test_rsi_matches_talib(golden: dict[str, Any]) -> None:
    _assert_matches(ind.rsi(_ohlc(golden)[3], 14), golden["rsi"]["14"])


def test_true_range_matches_talib(golden: dict[str, Any]) -> None:
    _, high, low, close = _ohlc(golden)
    _assert_matches(ind.true_range(high, low, close), golden["trange"])


def test_atr_matches_talib(golden: dict[str, Any]) -> None:
    _, high, low, close = _ohlc(golden)
    _assert_matches(ind.atr(high, low, close, 14), golden["atr"]["14"])


def test_adx_matches_talib(golden: dict[str, Any]) -> None:
    _, high, low, close = _ohlc(golden)
    result = ind.adx(high, low, close, 14)
    _assert_matches(result.adx, golden["adx"]["14"])
    _assert_matches(result.plus_di, golden["adx"]["plus_di"])
    _assert_matches(result.minus_di, golden["adx"]["minus_di"])


def test_macd_matches_talib(golden: dict[str, Any]) -> None:
    result = ind.macd(_ohlc(golden)[3], 12, 26, 9)
    _assert_matches_trimmed(result.macd, golden["macd"]["macd"], first_valid=25)
    _assert_matches(result.signal, golden["macd"]["signal"])
    _assert_matches(result.histogram, golden["macd"]["hist"])


def test_stochastic_matches_talib(golden: dict[str, Any]) -> None:
    _, high, low, close = _ohlc(golden)
    result = ind.stochastic(high, low, close, 14, 3, 3)
    _assert_matches_trimmed(result.k, golden["stoch"]["k"], first_valid=15)
    _assert_matches(result.d, golden["stoch"]["d"])


def test_bollinger_matches_talib(golden: dict[str, Any]) -> None:
    result = ind.bollinger(_ohlc(golden)[3], 20, 2.0)
    _assert_matches(result.upper, golden["bbands"]["upper"])
    _assert_matches(result.middle, golden["bbands"]["middle"])
    _assert_matches(result.lower, golden["bbands"]["lower"])
