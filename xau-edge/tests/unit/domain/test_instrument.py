from __future__ import annotations

import polars as pl
import pytest
from pydantic import ValidationError

from xau_edge.domain.bars import TimestampTypeError, coerce_bars
from xau_edge.domain.instrument import Instrument

pytestmark = pytest.mark.unit


def test_instrument_rejects_point_inconsistent_with_digits() -> None:
    with pytest.raises(ValidationError, match="inconsistent"):
        Instrument(symbol="XAUUSD", digits=2, point=0.1, contract_size=100.0, quote_currency="USD")


def test_coerce_bars_rejects_non_datetime_timestamp() -> None:
    df = pl.DataFrame(
        {
            "timestamp": ["2025-03-03 00:00:00"],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "tick_volume": [1],
            "spread": [1],
        }
    )
    with pytest.raises(TimestampTypeError):
        coerce_bars(df)
