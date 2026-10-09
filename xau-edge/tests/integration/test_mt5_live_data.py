"""Live checks against the running FTMO DEMO terminal. Local only: CI runs ``-m "not mt5"``.

uv run --extra mt5 pytest -m mt5 tests/integration/test_mt5_live_data.py
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.mt5.runtime import DEFAULT_TERMINAL, open_feed

pytestmark = pytest.mark.mt5


@pytest.fixture(scope="module")
def feed():  # type: ignore[no-untyped-def]
    try:
        with open_feed(DEFAULT_TERMINAL) as f:
            yield f
    except Exception as exc:
        pytest.skip(f"MT5 terminal not available: {exc}")


def test_demo_account_and_symbol(feed) -> None:  # type: ignore[no-untyped-def]
    assert feed.facts().demo
    mapping = feed.discover_symbol("XAUUSD")
    assert mapping.broker_symbol


def test_quote_age_matches_broker_clock(feed) -> None:  # type: ignore[no-untyped-def]
    mapping = feed.discover_symbol("XAUUSD")
    quote = feed.quote(mapping)
    if quote.market_status.value == "OPEN" and quote.timestamp is not None:
        assert abs(quote.age_seconds) < 60  # a wrong clock offset would show hours


def test_closed_bars_only_and_tick_volume(feed) -> None:  # type: ignore[no-untyped-def]
    mapping = feed.discover_symbol("XAUUSD")
    for tf in (Timeframe.M1, Timeframe.H1):
        frame = feed.latest_bars(mapping.broker_symbol, tf, 50)
        newest = frame["timestamp"].max()
        assert newest + tf.delta <= datetime.now(UTC) + timedelta(seconds=2)
        assert (frame["tick_volume"] > 0).all()
