"""Red-team regressions: each attack from the sprint's list that is not already covered elsewhere.

Covered in other files (see docs/reports/TRADING_CORE_ACCEPTANCE.md for the map): M1 never reverses
H1, SL/TP sides, lot rounding, RR net of spread, paper duplicate and double close, journal
provenance. Here: stale data, forming bars, volume semantics, missing spread, expiry, timezone.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from tests.unit.market_data.test_collector_ledger import FakeClient, make_collector
from tests.unit.trading.helpers import SPEC
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource
from xau_edge.trading.paper_desk import PaperDesk
from xau_edge.trading.schema import Refusal, TradeDecision


@pytest.fixture
def world(tmp_path: Path) -> tuple[TradeEngine, FakeClient, Path]:
    client = FakeClient()
    root = tmp_path / "market"
    make_collector(root, client).run_once()
    engine = TradeEngine(
        LiveTradingMarketSource(root, MarketCalendar()),
        PaperDesk(tmp_path / "trade", clock=lambda: client.now),
        EngineConfig(root=tmp_path / "trade", baseline=BaselineConfig(allow_unknown_news=True)),
        broker_clock=SERVER_CLOCK,
        clock=lambda: client.now,
    )
    return engine, client, root


def test_stale_data_can_only_produce_a_wait_with_a_stale_reason(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    engine, client, _ = world
    later = client.now + timedelta(minutes=30)  # the collector stopped: nothing new arrives
    engine.step(later)
    view = engine.view(later)
    assert view["decision"]["decision"] == "WAIT"
    assert not view["actionable"]
    reasons = set(view["decision"]["refusal_reasons"])
    assert reasons & {Refusal.STALE_DATA.value, Refusal.MARKET_CLOSED.value}
    assert view["decision"]["seconds_to_expiry"] in (None, 0.0)


def test_a_forming_bar_never_reaches_the_decision(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    engine, client, root = world
    live = json.loads((root / "live.json").read_text(encoding="utf-8"))
    forming_opens = [bar["timestamp"] for bar in live["forming"].values()]
    snap = engine.source.load(client.now)
    for tf, frame in snap.bars.frames.items():
        newest_close = frame["available_at"].to_list()[-1]
        assert newest_close <= client.now, tf
        assert all(t.isoformat() not in forming_opens for t in frame["timestamp"].tail(3)), tf
    assert snap.bars.frames[Timeframe.M1].height > 0


def test_volume_is_always_labelled_tick_volume(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    engine, _, _ = world
    engine.step()
    view = engine.view()
    assert view["volume"]["type"] == "TICK_VOLUME"
    assert view["decision"]["volume_type"] == "TICK_VOLUME"
    assert "not exchange volume" in view["volume"]["note"]


def test_a_missing_spread_or_quote_can_never_produce_a_trade(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    from xau_edge.trading.decision_core import SnapshotInputs, evaluate  # noqa: PLC0415

    engine, client, _ = world
    snap = engine.source.load(client.now)
    for spread, bid, ask in ((None, None, None), (None, 2000.0, 2000.2)):
        inputs = SnapshotInputs(
            snap.bars, client.now, bid, ask, spread, SPEC, 10_000.0, "UNKNOWN", True, True
        )
        _, signal = evaluate(inputs, BaselineConfig(allow_unknown_news=True), SERVER_CLOCK)
        assert signal.decision is TradeDecision.WAIT
        assert signal.refusal_reasons


def test_an_expired_setup_is_not_actionable_and_cannot_be_opened(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    from tests.unit.trading.test_engine_alerts_lock import _buy  # noqa: PLC0415
    from xau_edge.trading.paper_desk import DeskRefusal  # noqa: PLC0415

    engine, client, _ = world
    engine.step()
    signal = _buy(engine)
    engine._signal = signal.model_copy(update={"signal_expiry": client.now - timedelta(seconds=1)})
    view = engine.view()
    assert view["decision"]["expired"] is True
    assert view["actionable"] is False
    with pytest.raises(DeskRefusal) as info:
        engine.desk.open_from_decision(
            engine._signal,
            risk_pct=0.25,
            quote=engine.current_quote(client.now),
            spec=SPEC,
            now=client.now,
        )
    assert info.value.code == "EXPIRED"


def test_every_timestamp_the_api_serves_is_timezone_aware_utc(
    world: tuple[TradeEngine, FakeClient, Path],
) -> None:
    engine, _, _ = world
    engine.step()
    view = engine.view()
    stamps = [
        view["generated_at"],
        view["served_at"],
        view["data_as_of"],
        *(r["last_closed"] for r in view["timeframes"]),
    ]
    for stamp in stamps:
        assert stamp is not None
        assert stamp.endswith("+00:00") or stamp.endswith("Z"), stamp
    expiry = view["decision"]["signal_expiry"]
    if expiry is not None:
        assert expiry.endswith("+00:00") or expiry.endswith("Z")
        assert int(expiry[14:16]) % 5 == 0  # anchored to an M5 bar close, not to "now"
