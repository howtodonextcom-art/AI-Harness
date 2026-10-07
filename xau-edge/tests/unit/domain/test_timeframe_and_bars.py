from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest
from pydantic import ValidationError

from xau_edge.domain.bars import (
    BAR_COLUMNS,
    Bar,
    BarRequest,
    MissingColumnsError,
    coerce_bars,
    empty_bars,
)
from xau_edge.domain.instrument import XAUUSD
from xau_edge.domain.timeframe import Timeframe

pytestmark = pytest.mark.unit

T0 = datetime(2025, 3, 3, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("tf", "minutes"),
    [(Timeframe.M5, 5), (Timeframe.M15, 15), (Timeframe.H1, 60), (Timeframe.H4, 240)],
)
def test_timeframe_minutes_and_delta(tf: Timeframe, minutes: int) -> None:
    assert tf.minutes == minutes
    assert tf.delta == timedelta(minutes=minutes)


def test_timeframe_from_string_is_case_insensitive_and_rejects_unknown() -> None:
    assert Timeframe.parse("h1") is Timeframe.H1
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        Timeframe.parse("M1")


def test_xauusd_instrument_defaults() -> None:
    assert XAUUSD.symbol == "XAUUSD"
    assert XAUUSD.point == pytest.approx(10**-XAUUSD.digits)


def test_bar_accepts_consistent_ohlc() -> None:
    bar = Bar(
        symbol="XAUUSD",
        timeframe=Timeframe.M5,
        timestamp=T0,
        open=2000.0,
        high=2001.0,
        low=1999.0,
        close=2000.5,
        tick_volume=10,
        spread=20,
    )
    assert bar.real_volume is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"high": 1998.0},  # high below open/close
        {"low": 2002.0},  # low above open/close
        {"open": 0.0},  # non-positive price
        {"tick_volume": -1},
        {"spread": -1},
    ],
)
def test_bar_rejects_invalid_values(overrides: dict[str, float]) -> None:
    values: dict[str, object] = {
        "symbol": "XAUUSD",
        "timeframe": Timeframe.M5,
        "timestamp": T0,
        "open": 2000.0,
        "high": 2001.0,
        "low": 1999.0,
        "close": 2000.5,
        "tick_volume": 10,
        "spread": 20,
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        Bar(**values)


def test_bar_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        Bar(
            symbol="XAUUSD",
            timeframe=Timeframe.M5,
            timestamp=datetime(2025, 3, 3, 10, 0),  # noqa: DTZ001 - deliberate naive value
            open=1.0,
            high=1.0,
            low=1.0,
            close=1.0,
            tick_volume=0,
            spread=0,
        )


def test_bar_request_requires_ordered_aware_range() -> None:
    BarRequest(symbol="XAUUSD", timeframe=Timeframe.H1, start=T0, end=T0 + timedelta(hours=2))
    with pytest.raises(ValidationError):
        BarRequest(symbol="XAUUSD", timeframe=Timeframe.H1, start=T0, end=T0)
    with pytest.raises(ValidationError):
        BarRequest(
            symbol="XAUUSD",
            timeframe=Timeframe.H1,
            start=datetime(2025, 1, 1),  # noqa: DTZ001
            end=T0,
        )


def test_empty_bars_has_contract_schema() -> None:
    df = empty_bars()
    assert df.columns == list(BAR_COLUMNS)
    assert df.height == 0


def test_coerce_bars_casts_types_and_fills_optional_columns() -> None:
    raw = pl.DataFrame(
        {
            "timestamp": [T0],
            "open": [2000],
            "high": [2001],
            "low": [1999],
            "close": [2000],
            "tick_volume": [5],
            "spread": [20],
        }
    )
    out = coerce_bars(raw)
    assert out.columns == list(BAR_COLUMNS)
    assert out["open"].dtype == pl.Float64
    assert out["real_volume"].null_count() == 1


def test_coerce_bars_reports_all_missing_columns() -> None:
    with pytest.raises(MissingColumnsError) as exc:
        coerce_bars(pl.DataFrame({"timestamp": [T0], "open": [1.0]}))
    assert {"high", "low", "close", "tick_volume", "spread"} <= set(exc.value.missing)
