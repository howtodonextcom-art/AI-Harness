"""/md status components, quote states, quality, API freshness, and torn-file stress."""

from __future__ import annotations

import json
import threading
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.unit.market_data.test_collector_ledger import NOW, FakeClient, make_collector
from xau_edge.api.market_data import add_market_data_routes
from xau_edge.market_data.atomic import atomic_write_text
from xau_edge.market_data.collector import read_status_file


def build(tmp_path: Path) -> tuple[TestClient, FakeClient]:
    client = FakeClient()
    collector = make_collector(tmp_path, client)
    collector.run_once()
    app = FastAPI()
    add_market_data_routes(app, tmp_path, clock=lambda: client.now)
    return TestClient(app), client


def test_components_are_reported_separately_when_healthy(tmp_path: Path) -> None:
    http, _ = build(tmp_path)
    body = http.get("/md/status").json()
    assert body["components"]["collector"] == "RUNNING"
    assert body["components"]["terminal"] == "CONNECTED"
    assert body["components"]["quote"] == "FRESH"
    assert body["components"]["bars"] == "FRESH"
    assert body["components"]["market"] == "OPEN"
    assert body["recovery_action"] is None


def test_stopped_collector_is_stale_with_the_exact_recovery_action(tmp_path: Path) -> None:
    http, client = build(tmp_path)
    client.now = NOW + timedelta(minutes=2)  # nobody refreshed anything for two minutes
    body = http.get("/md/status").json()
    assert body["components"]["collector"] == "STALE"
    assert body["components"]["terminal"] == "UNKNOWN"
    assert body["components"]["quote"] == "STALE"
    assert "start_market_stack.ps1" in body["recovery_action"]
    quote = http.get("/md/XAUUSD/quote").json()
    assert quote["state"] == "STALE"
    assert "collector stopped" in quote["reason"]
    client.now = NOW + timedelta(minutes=45)
    assert http.get("/md/status").json()["components"]["collector"] == "STOPPED"


def test_api_notices_stale_bars_by_itself_when_the_collector_is_dead(tmp_path: Path) -> None:
    http, client = build(tmp_path)
    client.now = NOW + timedelta(minutes=12)  # the collector's own last snapshot still says FRESH
    body = http.get("/md/status").json()
    assert body["freshness"]["M1"] == "STALE"
    assert (
        body["freshness"]["H4"] == "FRESH"
    )  # a slow timeframe is not stale just because time passed
    assert body["components"]["bars"] == "STALE"
    quality = http.get("/md/XAUUSD/quality").json()
    assert {d["timeframe"]: d["freshness"] for d in quality["history_depth"]}["M1"] == "STALE"


def test_market_closed_quote_is_contextualised_not_broken(tmp_path: Path) -> None:
    http, client = build(tmp_path)
    client.now = NOW + timedelta(days=3)  # a Saturday
    quote = http.get("/md/XAUUSD/quote").json()
    assert quote["state"] == "MARKET_CLOSED"
    assert quote["stale"] is False
    assert "expected to be old" in quote["reason"]
    assert quote["last_tick_time"]


def test_quality_endpoint_reports_depth_ticks_disk(tmp_path: Path) -> None:
    http, _ = build(tmp_path)
    body = http.get("/md/XAUUSD/quality").json()
    assert {d["timeframe"] for d in body["history_depth"]} == {"M1", "M5", "M15", "M30", "H1", "H4"}
    assert all(d["earliest"] and d["rows"] for d in body["history_depth"])
    assert "level" in body["disk"]
    assert body["collector_health"] in {"GOOD", "STALE", "DEGRADED"}


def test_api_never_serves_a_cached_quote_after_the_collector_updates(tmp_path: Path) -> None:
    http, client = build(tmp_path)
    first = http.get("/md/XAUUSD/quote").json()
    client.now += timedelta(seconds=10)
    collector = make_collector(tmp_path, client)
    collector.poll_quote()
    collector.write_live()
    second = http.get("/md/XAUUSD/quote").json()
    assert second["collector_age_seconds"] < first["collector_age_seconds"] + 10
    assert second["timestamp"] != first["timestamp"]


def test_live_and_status_files_are_never_torn_under_concurrent_reads(tmp_path: Path) -> None:
    target = tmp_path / "live.json"
    atomic_write_text(target, json.dumps({"n": 0, "pad": "x" * 5000}))
    stop = threading.Event()
    torn: list[str] = []

    def writer() -> None:
        try:
            for i in range(300):
                atomic_write_text(target, json.dumps({"n": i, "pad": "x" * 5000}))
        except OSError as exc:
            torn.append(f"writer failed: {exc}")
        finally:
            stop.set()

    def reader() -> None:
        while not stop.is_set():
            try:
                json.loads(target.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                torn.append(str(exc))
            except OSError:
                continue  # a momentary sharing violation is not a torn file
            stop.wait(0.001)

    threads = [threading.Thread(target=reader) for _ in range(3)]
    threads.append(threading.Thread(target=writer))
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert torn == []


def test_corrupt_status_file_is_unknown_not_a_crash(tmp_path: Path) -> None:
    path = tmp_path / "collector_status.json"
    path.write_text("{torn", encoding="utf-8")
    assert read_status_file(path)["health"] == "UNKNOWN"
    http, _ = build(tmp_path / "other")
    path2 = tmp_path / "other" / "collector_status.json"
    path2.write_text("{torn", encoding="utf-8")
    body = http.get("/md/status").json()
    assert body["components"]["collector"] == "STOPPED"
    assert pytest.approx(1.0) == 1.0
