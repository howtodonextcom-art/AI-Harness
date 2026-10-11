"""UNKNOWN market/data state must not authorize a new BUY/SELL."""

from __future__ import annotations

from datetime import UTC, datetime

from tests.unit.trading.helpers import SPEC, aligned_state
from tests.unit.trading.test_cockpit import signal
from xau_edge.domain.market import MarketStatus
from xau_edge.trading.baseline import DecisionContext, decide
from xau_edge.trading.cockpit import action_for, hero_state
from xau_edge.trading.frames import MultiTfBars
from xau_edge.trading.live_source import LiveSnapshot
from xau_edge.trading.schema import Refusal, TradeDecision


def test_unknown_status_is_not_open() -> None:
    snap = LiveSnapshot(
        now=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
        bars=MultiTfBars({}),
        quote=None,
        spec=SPEC,
        status=MarketStatus.UNKNOWN,
        stale_timeframes=(),
        freshness={},
        collector_alive=True,
        latest_m1_close=None,
    )
    assert snap.market_open is False
    assert snap.usable is False


def test_unknown_market_status_cannot_produce_buy_or_sell() -> None:
    ctx = DecisionContext(
        spec=SPEC,
        equity=100_000.0,
        market_open=True,
        market_status="UNKNOWN",
        source_mode="LIVE",
    )
    s = decide(aligned_state(), ctx)
    assert s.decision is TradeDecision.WAIT
    assert Refusal.UNKNOWN_STATE in s.refusal_reasons


def test_unknown_hero_is_not_wait_and_not_closed() -> None:
    wait = signal(wait=True)
    hero = hero_state(
        signal=wait,
        conditions=[
            {
                "code": "MARKET_UNKNOWN",
                "severity": "ERROR",
                "message": "market status is unknown",
            }
        ],
        expired=False,
        plan=None,
        position=None,
        last_exit=None,
        market_open=False,
        now=datetime(2026, 10, 11, 12, 0, tzinfo=UTC),
    )
    assert hero["state"] == "UNKNOWN"
    assert action_for(hero, wait, None)["code"] == "UNAVAILABLE"
