"""Read-only API: endpoints answer from data, unsupported inputs are rejected, nothing can trade."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.conftest import make_bars
from xau_edge.api.app import create_app
from xau_edge.api.service import ApiContext, jsonable
from xau_edge.domain.timeframe import Timeframe
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.risk.prop_rules import load_prop_profile
from xau_edge.signals.engine import MarketFrames

PROP = load_prop_profile(Path(__file__).parents[3] / "configs" / "prop" / "ftmo_2step.yaml")


def _walk(n: int, tf: Timeframe, seed: int) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    step = (tf.minutes / 5) ** 0.5
    close = (
        2000 + np.cumsum(rng.normal(0, step, n)) + 6 * np.sin(np.arange(n) * 5 / tf.minutes / 30)
    )
    open_ = np.concatenate([[2000.0], close[:-1]])
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.4, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.4, n))
    return make_bars(n, tf).with_columns(
        pl.Series("open", open_),
        pl.Series("high", high),
        pl.Series("low", low),
        pl.Series("close", close),
        pl.Series("tick_volume", rng.integers(50, 500, n)),
    )


@pytest.fixture(scope="module")
def frames() -> MarketFrames:
    return MarketFrames(
        m5=_walk(9_000, Timeframe.M5, 1),
        m15=_walk(3_200, Timeframe.M15, 2),
        h1=_walk(800, Timeframe.H1, 3),
        h4=_walk(220, Timeframe.H4, 4),
    )


@pytest.fixture
def client(frames: MarketFrames, tmp_path: Path) -> TestClient:
    ctx = ApiContext(
        load_frames=lambda: frames,
        registry=ExperimentRegistry(tmp_path / "runs"),
        prop=PROP,
        models_dir=tmp_path / "models",
    )
    return TestClient(create_app(ctx))


def test_health_states_that_live_trading_is_off(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["live_trading"] is False


def test_market_returns_the_requested_number_of_bars(client: TestClient) -> None:
    body = client.get("/market/XAUUSD", params={"timeframe": "H1", "limit": 25}).json()
    assert body["timeframe"] == "H1"
    assert len(body["bars"]) == 25
    assert {"timestamp", "open", "high", "low", "close", "spread"} <= set(body["bars"][0])


def test_inputs_are_validated(client: TestClient) -> None:
    assert client.get("/market/EURUSD").status_code == 404
    assert client.get("/market/XAUUSD", params={"timeframe": "M1"}).status_code == 422
    assert client.get("/market/XAUUSD", params={"limit": 0}).status_code == 422
    assert client.get("/market/XAUUSD", params={"limit": 999_999}).status_code == 422
    assert client.get("/signals/XAUUSD", params={"at": "yesterday"}).status_code == 422
    assert client.get("/signals/XAUUSD", params={"at": "2026-01-01T00:00:00"}).status_code == 422
    assert client.get("/backtests/../etc").status_code in (404, 422)
    assert client.get("/backtests/zzzz").status_code == 404


def test_features_and_regime(client: TestClient) -> None:
    rows = client.get("/features/XAUUSD", params={"timeframe": "M15", "limit": 5}).json()["rows"]
    assert len(rows) == 5
    assert "rsi_14" in rows[0]
    regime = client.get("/regime/XAUUSD").json()
    assert {"H4", "H1", "M15", "M5"} <= set(regime)
    assert regime["M15"]["regime"] is not None
    assert len(regime["recent_m15_regimes"]) == 96


def test_signal_endpoint_returns_wait_without_validated_evidence(client: TestClient) -> None:
    body = client.get("/signals/XAUUSD").json()
    assert body["direction"] == "WAIT"
    assert "NO_VALIDATED_EDGE" in body["reasons"]
    assert body["evidence_status"] == "NONE"
    json.dumps(body, allow_nan=False)


def test_patterns_endpoint_returns_normalised_paths_and_what_followed(client: TestClient) -> None:
    body = client.get("/patterns/XAUUSD", params={"k": 5}).json()
    assert body["available"] is True
    assert len(body["matches"]) == 5
    assert len(body["current_path"]) == body["window"] + 1
    m = body["matches"][0]
    assert m["pattern_path"][0] == 0.0
    assert len(m["outcome_path"]) == body["outcome_bars"] + 1
    assert body["matches"][0]["distance"] <= body["matches"][-1]["distance"]
    json.dumps(body, allow_nan=False)


def test_risk_status_exposes_limits_and_profile_provenance(client: TestClient) -> None:
    body = client.get("/risk/status").json()
    assert body["live_trading"] is False
    assert body["limits"]["max_concurrent_trades"] == 1
    assert body["prop_profile"]["verified_on"] == "2026-10-08"
    assert body["evidence_status"] == "NONE"


def test_backtests_and_models_reflect_the_registry(frames: MarketFrames, tmp_path: Path) -> None:
    registry = ExperimentRegistry(tmp_path / "runs")
    rec = registry.record(
        family="backtest",
        name="x",
        dataset_ids={},
        feature_ids={},
        params={"strategy": "a"},
        seeds={},
        period="development",
        metrics={"verdict": {"passed": False}, "metrics": {"trade_count": 7}},
        code_version="c",
        code_dirty=False,
    )
    ctx = ApiContext(lambda: frames, registry, PROP, models_dir=tmp_path / "models")
    c = TestClient(create_app(ctx))
    runs = c.get("/backtests").json()["runs"]
    assert [r["id"] for r in runs] == [rec.id]
    assert runs[0]["passed"] is False
    assert runs[0]["trades"] == 7
    assert c.get(f"/backtests/{rec.id}").json()["params"] == {"strategy": "a"}
    assert c.get("/models").json() == {"models": []}


def test_no_route_other_than_the_paper_endpoint_accepts_a_write(client: TestClient) -> None:
    writes = {
        (m, route.path)
        for route in client.app.routes  # type: ignore[attr-defined]
        for m in getattr(route, "methods", set())
        if m not in {"GET", "HEAD", "OPTIONS"}
    }
    assert writes == {("POST", "/paper/orders")}
    for path in ("/orders", "/trade", "/execute", "/mt5/order"):
        assert client.post(path, json={}).status_code in (404, 405)


def test_cors_allows_only_the_local_dashboard(client: TestClient) -> None:
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    other = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_jsonable_converts_non_finite_numbers_and_numpy_scalars() -> None:
    out = jsonable({"a": float("nan"), "b": np.float64("inf"), "c": [np.int64(3), 1.5]})
    assert out == {"a": None, "b": None, "c": [3, 1.5]}


def test_legacy_signals_endpoint_is_marked_deprecated_and_points_to_the_desk(
    client: TestClient,
) -> None:
    res = client.get("/signals/XAUUSD")
    assert res.headers["Deprecation"] == "true"
    assert "/trade/decision" in res.headers["Link"]
    body = res.json()
    assert body["deprecated"] is True and body["successor"] == "/trade/decision"
    assert "data/raw" in body["legacy_source"]
