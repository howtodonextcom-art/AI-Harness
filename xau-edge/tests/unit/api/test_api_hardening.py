# ruff: noqa: F811
"""API hardening from the independent review: bounds, caching, traversal, CORS, news status."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.api.test_api import PROP, frames  # noqa: F401 - fixture import
from xau_edge.api.app import create_app
from xau_edge.api.service import ApiContext
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.signals.engine import MarketFrames, generate_signal
from xau_edge.signals.schema import Signal


@pytest.fixture
def client(frames: MarketFrames, tmp_path: Path) -> TestClient:
    ctx = ApiContext(
        load_frames=lambda: frames,
        registry=ExperimentRegistry(tmp_path / "runs"),
        prop=PROP,
        models_dir=tmp_path / "models",
    )
    return TestClient(create_app(ctx))


def test_dates_outside_the_data_range_are_rejected_and_never_crash(client: TestClient) -> None:
    for path in ("/patterns/XAUUSD", "/signals/XAUUSD"):
        assert client.get(path, params={"at": "1990-01-01T00:00:00Z"}).status_code == 422
        assert client.get(path, params={"at": "2999-01-01T00:00:00Z"}).status_code == 422


def test_encoded_traversal_in_run_ids_is_rejected(client: TestClient) -> None:
    for bad in ("..%2f..%2fpyproject", "%2e%2e%5c%2e%2e%5csecret", "abc%00def", "A" * 300):
        assert client.get(f"/backtests/{bad}").status_code in (404, 422)


def test_repeated_signal_requests_for_the_same_bar_are_computed_once(
    frames: MarketFrames,
    tmp_path: Path,
) -> None:
    calls = {"n": 0}
    registry = ExperimentRegistry(tmp_path / "runs")

    def provider(at: datetime) -> Signal:
        calls["n"] += 1
        return generate_signal(frames, at, registry)

    ctx = ApiContext(lambda: frames, registry, PROP, signal_provider=provider)
    c = TestClient(create_app(ctx))
    first = c.get("/signals/XAUUSD").json()
    second = c.get("/signals/XAUUSD").json()
    assert first == second
    assert calls["n"] == 1


def test_the_cache_is_bounded(frames: MarketFrames, tmp_path: Path) -> None:
    ctx = ApiContext(lambda: frames, ExperimentRegistry(tmp_path / "runs"), PROP, max_cache=2)
    c = TestClient(create_app(ctx))
    for k in (3, 4, 5, 6):
        assert c.get("/patterns/XAUUSD", params={"k": k}).status_code == 200
    assert len(ctx._cache) <= 2


def test_signal_response_states_news_status_and_data_age(client: TestClient) -> None:
    body = client.get("/signals/XAUUSD").json()
    assert body["news_status"] == "unknown"  # no calendar is configured
    assert body["data_as_of"]
    status = client.get("/risk/status").json()
    assert status["kill_switch"]["tripped"] is False
    assert "read-only" in status["kill_switch"]["note"]


def test_cors_preflight_refuses_other_methods_and_headers(client: TestClient) -> None:
    r = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "x-evil",
        },
    )
    assert r.status_code == 400
