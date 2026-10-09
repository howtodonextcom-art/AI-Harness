"""``/md/*`` endpoints over a collector run on a fake MT5 client (no live terminal)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.unit.market_data.test_collector_ledger import NOW, FakeClient, make_collector
from xau_edge.api.market_data import add_market_data_routes


@pytest.fixture
def served(tmp_path: Path) -> tuple[TestClient, FakeClient, Path]:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.run_once()
    app = FastAPI()
    add_market_data_routes(app, tmp_path, clock=lambda: client.now)
    return TestClient(app), client, tmp_path


def test_bars_default_to_closed_only(served: tuple[TestClient, FakeClient, Path]) -> None:
    http, _, _ = served
    body = http.get("/md/XAUUSD/bars", params={"timeframe": "M5", "limit": 50}).json()
    assert body["closed_only"] is True and body["volume_type"] == "TICK_VOLUME"
    assert len(body["bars"]) == 50 and all(b["is_closed"] for b in body["bars"])


def test_forming_bar_only_on_request_and_marked(
    served: tuple[TestClient, FakeClient, Path],
) -> None:
    http, _, _ = served
    body = http.get("/md/XAUUSD/bars", params={"timeframe": "M1", "include_forming": True}).json()
    assert body["bars"][-1]["is_closed"] is False
    assert sum(not b["is_closed"] for b in body["bars"]) == 1


def test_quote_fresh_then_stale(served: tuple[TestClient, FakeClient, Path]) -> None:
    http, client, _ = served
    fresh = http.get("/md/XAUUSD/quote").json()
    assert fresh["available"] and not fresh["stale"] and fresh["spread_points"] == pytest.approx(20)
    client.now = NOW.replace(minute=30)  # nothing refreshed for 30 minutes during an open market
    assert http.get("/md/XAUUSD/quote").json()["stale"] is True


def test_matrix_status_ticks_and_validation(served: tuple[TestClient, FakeClient, Path]) -> None:
    http, _, _ = served
    matrix = http.get("/md/XAUUSD/matrix").json()
    assert {r["timeframe"] for r in matrix["timeframes"]} == {"M1", "M5", "M15", "M30", "H1", "H4"}
    assert all(r["last_closed_bar_open"] for r in matrix["timeframes"])
    assert http.get("/md/status").json()["source"] == "FTMO MT5"
    assert len(http.get("/md/XAUUSD/ticks", params={"limit": 5}).json()["ticks"]) <= 5
    assert http.get("/md/XAUUSD/ticks", params={"limit": 100000}).status_code == 422
    assert http.get("/md/EURUSD/quote").status_code == 404
    assert http.get("/md/XAUUSD/bars", params={"timeframe": "M2"}).status_code == 422
    assert http.get("/md/XAUUSD/bars", params={"limit": 999999}).status_code == 422
    assert http.get("/md/XAUUSD/bars", params={"before": "2026-01-01T00:00:00"}).status_code == 422


def test_no_collector_files_is_unavailable_not_an_error(tmp_path: Path) -> None:
    app = FastAPI()
    add_market_data_routes(app, tmp_path, clock=lambda: NOW)
    http = TestClient(app)
    assert http.get("/md/XAUUSD/quote").json()["available"] is False
    assert http.get("/md/status").json()["health"] == "UNKNOWN"
    assert http.get("/md/XAUUSD/bars").json()["bars"] == []


def test_torn_live_file_is_survivable(served: tuple[TestClient, FakeClient, Path]) -> None:
    http, _, root = served
    (root / "live.json").write_text("{torn", encoding="utf-8")
    assert http.get("/md/XAUUSD/quote").json()["available"] is False
    live = json.dumps({"updated_at": NOW.isoformat(), "quote": 5})
    (root / "live.json").write_text(live, encoding="utf-8")
    assert http.get("/md/XAUUSD/quote").json()["available"] is False
