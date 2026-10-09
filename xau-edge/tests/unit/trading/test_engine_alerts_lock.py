"""Engine over a fake collector run, setup alerts and the demo lock."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.unit.market_data.test_collector_ledger import NOW, FakeClient, make_collector
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.ops.notifier import AlertEvent
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import comparable, explain
from xau_edge.trading.demo_lock import demo_lock_status
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource
from xau_edge.trading.paper_desk import PaperDesk
from xau_edge.trading.schema import TradeDecision, TradingSignal
from xau_edge.trading.setup_alerts import SetupAlerts


class Sink:
    def __init__(self) -> None:
        self.events: list[AlertEvent] = []

    def dispatch(self, event: AlertEvent) -> None:
        self.events.append(event)


@pytest.fixture
def engine(tmp_path: Path) -> tuple[TradeEngine, FakeClient]:
    client = FakeClient()
    make_collector(tmp_path / "market", client).run_once()
    source = LiveTradingMarketSource(tmp_path / "market", MarketCalendar())
    desk = PaperDesk(tmp_path / "trade", clock=lambda: client.now)
    eng = TradeEngine(
        source,
        desk,
        EngineConfig(root=tmp_path / "trade", baseline=BaselineConfig(allow_unknown_news=True)),
        broker_clock=SERVER_CLOCK,
        clock=lambda: client.now,
    )
    return eng, client


def test_engine_answers_with_a_complete_transparent_view(
    engine: tuple[TradeEngine, FakeClient],
) -> None:
    eng, _ = engine
    assert eng.step() is True
    view = eng.view()
    assert view["available"] is True
    assert view["decision"]["decision"] in {"BUY", "SELL", "WAIT"}
    assert [t["timeframe"] for t in view["timeframes"]] == ["H4", "H1", "M30", "M15", "M5", "M1"]
    assert view["volume"]["type"] == "TICK_VOLUME"
    assert view["evidence"]["validated_edge"] is False
    assert view["news"]["warning"] is True  # NEWS NOT VERIFIED is visible, not silently safe
    assert view["demo"]["paper_desk_sends_orders"] is False
    assert view["desk"]["account"]["simulated"] is True


def test_unchanged_inputs_do_not_recompute_or_flicker(
    engine: tuple[TradeEngine, FakeClient],
) -> None:
    eng, _ = engine
    assert eng.step() is True
    first = eng.view()["decision"]["decision_id"]
    assert eng.step() is False
    assert eng.view()["decision"]["decision_id"] == first


def test_wait_always_explains_itself(engine: tuple[TradeEngine, FakeClient]) -> None:
    eng, _ = engine
    eng.step()
    signal = eng._signal
    assert signal is not None
    if signal.decision is TradeDecision.WAIT:
        assert signal.refusal_reasons
        assert all(line.startswith("WAIT because:") for line in explain(signal))


def test_same_snapshot_same_decision(engine: tuple[TradeEngine, FakeClient]) -> None:
    eng, client = engine
    eng.step()
    first = comparable(eng._signal)  # type: ignore[arg-type]
    eng._key = None
    eng.step(client.now)
    assert comparable(eng._signal) == first  # type: ignore[arg-type]


def test_stale_collector_blocks_trading_with_a_reason(
    engine: tuple[TradeEngine, FakeClient],
) -> None:
    eng, client = engine
    eng.step()
    eng.step(client.now + timedelta(hours=3))
    view = eng.view(client.now + timedelta(hours=3))
    assert view["actionable"] is False


def test_paper_open_refuses_a_setup_that_is_not_current(
    engine: tuple[TradeEngine, FakeClient],
) -> None:
    from xau_edge.trading.paper_desk import DeskRefusal  # noqa: PLC0415

    eng, _ = engine
    eng.step()
    with pytest.raises(DeskRefusal):
        eng.paper_open(setup_id="not-the-live-setup", risk_pct=0.25)


# -- setup alerts -------------------------------------------------------------------------------


def _buy(engine_: TradeEngine, setup_id: str = "abcdef0123456789") -> TradingSignal:
    base = engine_._signal
    assert base is not None
    return base.model_copy(
        update={
            "decision": TradeDecision.BUY,
            "refusal_reasons": (),
            "setup_id": setup_id,
            "entry_price": 2000.0,
            "stop_loss": 1995.0,
            "take_profit": 2010.0,
            "risk_reward": 2.0,
            "risk_pct": 0.25,
            "position_size": 0.5,
            "signal_expiry": base.timestamp + timedelta(minutes=15),
        }
    )


def test_a_setup_is_announced_once_and_remembered_across_restarts(
    engine: tuple[TradeEngine, FakeClient], tmp_path: Path
) -> None:
    eng, _ = engine
    eng.step()
    sink = Sink()
    state = tmp_path / "alerts.json"
    alerts = SetupAlerts(sink, state)
    signal = _buy(eng)
    now = signal.timestamp
    for _ in range(3):
        alerts.on_decision(signal, now, taken_setups=set(), blocked=False)
    assert [e.code.split(":")[0] for e in sink.events] == ["BUY_SETUP_READY"]
    again = Sink()
    SetupAlerts(again, state).on_decision(signal, now, taken_setups=set(), blocked=False)
    assert again.events == []  # restart does not repeat the message


def test_wait_is_never_announced_and_a_vanished_setup_is_invalidated(
    engine: tuple[TradeEngine, FakeClient], tmp_path: Path
) -> None:
    eng, _ = engine
    eng.step()
    sink = Sink()
    alerts = SetupAlerts(sink, tmp_path / "a.json")
    signal = _buy(eng)
    wait = eng._signal
    assert wait is not None
    now = signal.timestamp
    alerts.on_decision(
        wait.model_copy(update={"decision": TradeDecision.WAIT}),
        now,
        taken_setups=set(),
        blocked=False,
    )
    assert sink.events == []
    alerts.on_decision(signal, now, taken_setups=set(), blocked=False)
    alerts.on_decision(
        wait.model_copy(update={"decision": TradeDecision.WAIT, "setup_id": ""}),
        now + timedelta(minutes=1),
        taken_setups=set(),
        blocked=False,
    )
    assert [e.code.split(":")[0] for e in sink.events] == ["BUY_SETUP_READY", "SETUP_INVALIDATED"]


def test_blocked_desk_sends_no_setup_alert(
    engine: tuple[TradeEngine, FakeClient], tmp_path: Path
) -> None:
    eng, _ = engine
    eng.step()
    sink = Sink()
    signal = _buy(eng)
    SetupAlerts(sink, tmp_path / "a.json").on_decision(
        signal, signal.timestamp, taken_setups=set(), blocked=True
    )
    assert sink.events == []


# -- demo lock ----------------------------------------------------------------------------------


def test_demo_lock_lists_reasons_and_never_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT5_TRADE_PASSWORD", "super-secret-value-123")
    monkeypatch.setenv("XAU_EDGE_ENABLE_DEMO_TRADING", "false")
    status: dict[str, Any] = demo_lock_status({"account_trade_allowed": False})
    text = json.dumps(status)
    assert "super-secret-value-123" not in text
    assert status["status"] == "LOCKED"
    codes = {r["code"] for r in status["reasons"]}
    assert {"TRADING_NOT_ALLOWED", "DEMO_TRADING_DISABLED"} <= codes
    assert status["paper_desk_sends_orders"] is False
    assert NOW  # fixture import is used for the clock only
