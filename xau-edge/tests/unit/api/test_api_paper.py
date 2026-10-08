# ruff: noqa: F811
"""POST /paper/orders: server-side signal only, paper broker only, WAIT places nothing."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.api.test_api import PROP, frames  # noqa: F401 - fixture import
from tests.unit.signals.test_decision import _inputs
from xau_edge.api.app import create_app
from xau_edge.api.service import ApiContext
from xau_edge.backtest.costs import CostModel
from xau_edge.execution.paper import PaperExecutionBroker
from xau_edge.execution.safety import ExecutionSafety
from xau_edge.execution.trader import PaperTrader
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.risk.engine import RiskEngine, RiskLimits
from xau_edge.signals.decision import decide
from xau_edge.signals.engine import MarketFrames
from xau_edge.signals.schema import Signal


def _trader() -> PaperTrader:
    broker = PaperExecutionBroker(
        100_000.0, costs=CostModel(swap_long_points=0, swap_short_points=0)
    )
    return PaperTrader(broker, RiskEngine(RiskLimits(), PROP), ExecutionSafety())


def _provider_for(frames: MarketFrames, price: float | None = None) -> Callable[[datetime], Signal]:
    market = float(frames.m5["close"][-1])
    return lambda at: decide(_inputs(timestamp=at, price=market if price is None else price))


def _now(frames: MarketFrames) -> Callable[[], datetime]:
    last = frames.m15["timestamp"].max()
    assert isinstance(last, datetime)
    return lambda: last + timedelta(minutes=16)  # one minute after the latest decision bar


def _client(frames: MarketFrames, tmp_path: Path, **kwargs: object) -> TestClient:
    ctx = ApiContext(
        lambda: frames,
        ExperimentRegistry(tmp_path / "runs"),
        PROP,
        paper=_trader(),
        clock=_now(frames),
        **kwargs,  # type: ignore[arg-type]
    )
    return TestClient(create_app(ctx))


def test_without_paper_configuration_the_endpoint_is_unavailable(
    frames: MarketFrames, tmp_path: Path
) -> None:
    ctx = ApiContext(lambda: frames, ExperimentRegistry(tmp_path / "runs"), PROP)
    assert TestClient(create_app(ctx)).post("/paper/orders", json={}).status_code == 503


def test_a_real_signal_without_evidence_is_wait_and_places_nothing(
    frames: MarketFrames,
    tmp_path: Path,
) -> None:
    c = _client(frames, tmp_path)
    body = c.post("/paper/orders", json={}).json()
    assert body["accepted"] is False
    assert body["signal_direction"] == "WAIT"
    assert "NO_VALIDATED_EDGE" in body["reasons"]
    assert c.get("/paper/positions").json() == {"positions": []}
    assert c.get("/paper/account").json()["balance"] == 100_000.0


def test_a_validated_buy_becomes_a_paper_position_once(
    frames: MarketFrames, tmp_path: Path
) -> None:
    c = _client(frames, tmp_path, signal_provider=_provider_for(frames))
    first = c.post("/paper/orders", json={}).json()
    assert first["accepted"] is True
    assert first["signal_direction"] == "BUY"
    assert first["position_id"] == "p1"
    again = c.post("/paper/orders", json={}).json()
    assert again["accepted"] is False
    assert again["reasons"] == ["DUPLICATE_SIGNAL"]
    positions = c.get("/paper/positions").json()["positions"]
    assert len(positions) == 1
    assert positions[0]["signal_hash"] == first["signal_hash"]
    assert c.get("/paper/account").json()["open_positions"] == 1


@pytest.mark.parametrize(
    "payload",
    [{"direction": "BUY"}, {"lots": 100}, {"stop_loss": 1.0}, {"symbol": "EURUSD"}, {"at": 5}],
)
def test_the_client_cannot_choose_any_trade_parameter(
    frames: MarketFrames,
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    c = _client(frames, tmp_path, signal_provider=_provider_for(frames))
    assert c.post("/paper/orders", json=payload).status_code == 422
    assert c.get("/paper/positions").json() == {"positions": []}


def test_only_the_latest_decision_bar_can_be_traded(frames: MarketFrames, tmp_path: Path) -> None:
    c = _client(frames, tmp_path, signal_provider=_provider_for(frames))
    old = frames.m15["timestamp"][2000].isoformat().replace("+00:00", "Z")
    assert c.post("/paper/orders", json={"at": old}).status_code == 422


def test_a_signal_the_market_has_already_run_away_from_is_rejected_not_a_server_error(
    frames: MarketFrames,
    tmp_path: Path,
) -> None:
    c = _client(frames, tmp_path, signal_provider=_provider_for(frames, price=2000.0))
    r = c.post("/paper/orders", json={})
    assert r.status_code == 200
    assert r.json()["accepted"] is False
    assert r.json()["reasons"] == ["ORDER_REJECTED"]
    assert c.get("/paper/positions").json() == {"positions": []}


def test_orders_on_stale_data_are_refused(frames: MarketFrames, tmp_path: Path) -> None:
    ctx = ApiContext(
        lambda: frames,
        ExperimentRegistry(tmp_path / "runs"),
        PROP,
        paper=_trader(),
        signal_provider=_provider_for(frames),
        clock=lambda: datetime(2030, 1, 1, tzinfo=UTC),
    )
    body = TestClient(create_app(ctx)).post("/paper/orders", json={}).json()
    assert body["accepted"] is False
    assert body["reasons"] == ["DATA_STALE"]


def test_risk_status_reflects_the_paper_kill_switch(frames: MarketFrames, tmp_path: Path) -> None:
    trader = _trader()
    ctx = ApiContext(
        lambda: frames,
        ExperimentRegistry(tmp_path / "runs"),
        PROP,
        paper=trader,
        clock=_now(frames),
    )
    c = TestClient(create_app(ctx))
    assert c.get("/risk/status").json()["kill_switch"]["tripped"] is False
    trader.risk.kill_switch.trip("test breach")
    status = c.get("/risk/status").json()["kill_switch"]
    assert status["tripped"] is True
    assert status["reason"] == "test breach"
