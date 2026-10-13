"""Data-source interface shared by MetaTrader 5 and offline adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl

from xau_edge.domain.bars import BarRequest


@runtime_checkable
class BarSource(Protocol):
    """Anything that can supply OHLC bars for a request.

    Contract for implementations:

    * return a frame following ``xau_edge.domain.bars.BAR_SCHEMA`` (UTC bar-open timestamps),
    * restrict rows to ``[request.start, request.end)``,
    * never sort, de-duplicate or repair data (validators report problems; they are not hidden),
    * never trade or mutate any account state.
    """

    name: str

    def fetch_bars(self, request: BarRequest) -> pl.DataFrame:
        """Return bars for ``request``."""
        ...
