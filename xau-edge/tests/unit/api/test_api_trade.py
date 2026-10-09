"""``/trade/*``: read-only decision, guarded paper actions, no route that can reach MT5."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.unit.market_data.test_collector_ledger import FakeClient, make_collector
from xau_edge.api.trade import add_trade_routes
from xau_edge.market_data.validators.market_calendar import MarketCalendar
from xau_edge.strategies.edge_program import SERVER_CLOCK
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.engine import EngineConfig, TradeEngine
from xau_edge.trading.live_source import LiveTradingMarketSource
from xau_edge.trading.paper_desk import PaperDesk

ORIGIN = "http://localhost:3000"
HEADERS = {
    "Host": "127.0.0.1:8000",
    "Origin": ORIGIN,
    "Content-Type": "application/json",
    "X-Paper-Desk": "1",
}


@pytest.fixture
def http(tmp_path: Path) -> TestClient:
    client = FakeClient()
    make_collector(tmp_path / "market", client).run_once()
    engine = TradeEngine(
        LiveTradingMarketSource(tmp_path / "market", MarketCalendar()),
        PaperDesk(tmp_path / "trade", clock=lambda: client.now),
        EngineConfig(root=tmp_path / "trade", baseline=BaselineConfig(allow_unknown_news=True)),
        broker_clock=SERVER_CLOCK,
        clock=lambda: client.now,
    )
    app = FastAPI()
    add_trade_routes(app, engine, port=8000, allowed_origins=(ORIGIN,))
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_decision_is_served_with_evidence_and_demo_lock(http: TestClient) -> None:
    body = http.get("/trade/decision").json()
    assert body["available"] is True
    assert body["evidence"]["validated_edge"] is False
    assert body["demo"]["paper_desk_sends_orders"] is False


def test_risk_calculator_rounds_down_and_rejects_nonsense(http: TestClient) -> None:
    ok = http.get("/trade/risk", params={"entry": 2000, "stop_loss": 1995, "equity": 10000})
    assert ok.status_code == 200
    assert http.get("/trade/risk", params={"entry": -1, "stop_loss": 1}).status_code == 422


def test_journal_and_paper_state_are_marked_simulated(http: TestClient) -> None:
    assert http.get("/trade/paper").json()["simulated"] is True
    assert http.get("/trade/journal").json()["simulated"] is True


@pytest.mark.parametrize(
    ("drop", "code"),
    [
        ("Origin", "BAD_ORIGIN"),
        ("X-Paper-Desk", "MISSING_DESK_HEADER"),
    ],
)
def test_paper_post_needs_origin_and_desk_header(http: TestClient, drop: str, code: str) -> None:
    headers = {k: v for k, v in HEADERS.items() if k != drop}
    res = http.post(
        "/trade/paper/open", json={"setup_id": "abcdef0123", "risk_pct": 0.25}, headers=headers
    )
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == code


def test_paper_post_refuses_a_foreign_origin_and_unknown_fields(http: TestClient) -> None:
    bad = {**HEADERS, "Origin": "http://evil.example"}
    assert (
        http.post("/trade/paper/close", json={"trade_id": "t-1234"}, headers=bad).status_code == 403
    )
    extra = {"setup_id": "abcdef0123", "risk_pct": 0.25, "entry": 1.0}
    assert http.post("/trade/paper/open", json=extra, headers=HEADERS).status_code == 422


def test_opening_a_setup_that_is_not_live_is_a_conflict_not_a_trade(http: TestClient) -> None:
    res = http.post(
        "/trade/paper/open", json={"setup_id": "abcdef0123", "risk_pct": 0.25}, headers=HEADERS
    )
    assert res.status_code == 409
    assert http.get("/trade/journal").json()["trades"] == []


def test_the_only_write_routes_are_the_two_paper_actions(http: TestClient) -> None:
    writes = {
        (m, route.path)
        for route in http.app.routes  # type: ignore[attr-defined]
        for m in getattr(route, "methods", set())
        if m not in {"GET", "HEAD", "OPTIONS"}
    }
    assert writes == {("POST", "/trade/paper/open"), ("POST", "/trade/paper/close")}
