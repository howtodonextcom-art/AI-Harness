from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from xau_edge_v2.api.model import model_detail
from xau_edge_v2.api.state import unavailable_state

Make = Callable[..., TestClient]


def test_health_is_honest_about_what_is_deployed(make_client: Make) -> None:
    body = make_client().get("/api/v2/health").json()
    assert body["mode"] == "PAPER" and body["store"]["read_only"] is True
    checks = {c["id"]: c["state"] for c in body["checks"]}
    assert checks["store"] == "OK"
    assert checks["engine"] == "OK" and checks["model"] == "NOT_DEPLOYED"
    assert body["status"] == "DEGRADED"  # an undeployed model is never reported as OK


def test_health_goes_down_when_the_store_is_missing(make_client: Make, tmp_path: Path) -> None:
    body = make_client(data_root=tmp_path / "nope").get("/api/v2/health").json()
    assert body["status"] == "DOWN" and body["store"]["reachable"] is False


def test_state_with_too_little_history_waits_and_never_fakes_a_signal(make_client: Make) -> None:
    body = make_client().get("/api/v2/state").json()  # the fixture store has 5 bars per timeframe
    assert body["action"] == "WAIT" and body["plan"] is None and body["risk"] is None
    assert body["evidence"] == "UNVALIDATED" and body["model"]["status"] == "RETIRED"
    assert body["mode"] == "PAPER" and body["blocker"] and body["reason_codes"]
    assert body["strategy_version"] == "1.1.0" and body["decision_id"]
    assert body["readiness_level"] <= 5  # READY exists only with a BUY/SELL plan


def test_state_is_unavailable_when_the_store_is_missing(make_client: Make, tmp_path: Path) -> None:
    body = make_client(data_root=tmp_path / "nope").get("/api/v2/state").json()
    assert body["action"] == "UNAVAILABLE" and body["plan"] is None
    assert body["reason_codes"] == ["STORE_UNAVAILABLE"] and body["readiness_level"] == 0


@pytest.mark.parametrize("path", ["/api/v2/health", "/api/v2/state"])
def test_api_is_read_only(make_client: Make, path: str) -> None:
    client = make_client()
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(path).status_code == 405


def test_unknown_api_path_is_json_404_not_the_page(make_client: Make) -> None:
    r = make_client().get("/api/v2/nope")
    assert r.status_code == 404 and "<html" not in r.text.lower()


def test_spa_fallback_and_page(make_client: Make) -> None:
    client = make_client()
    assert "root" in client.get("/").text
    assert "root" in client.get("/anything/deep").text  # SPA route fallback


def test_asset_cache_and_gzip(make_client: Make) -> None:
    r = make_client().get("/assets/app-abc123.js", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200
    assert r.headers["cache-control"].startswith("public, max-age=31536000")
    assert r.headers.get("content-encoding") == "gzip"
    assert make_client().get("/").headers["cache-control"] == "no-cache"


def test_missing_web_build_is_structured_not_503(make_client: Make, tmp_path: Path) -> None:
    r = make_client(web_dist=tmp_path / "no-dist").get("/")
    assert r.status_code == 404 and r.json()["error_code"] == "WEB_NOT_BUILT"


def test_request_id_header_and_json_log(make_client: Make, tmp_path: Path) -> None:
    client = make_client()
    r = client.get("/api/v2/state")
    assert len(r.headers["x-request-id"]) == 12
    line = (tmp_path / "logs" / "xau_edge_v2.jsonl").read_text().splitlines()[-1]
    row = json.loads(line)
    assert row["path"] == "/api/v2/state" and row["status"] == 200 and row["latency_ms"] >= 0


def test_ws_hello_then_sequential_heartbeats(make_client: Make) -> None:
    with make_client().websocket_connect("/ws") as ws:
        first = json.loads(ws.receive_text())
        beats = [json.loads(ws.receive_text()) for _ in range(3)]
    assert first["type"] == "hello" and first["seq"] == 0
    assert [b["type"] for b in beats] == ["heartbeat"] * 3
    assert [b["seq"] for b in beats] == [1, 2, 3]  # a client detects any gap


def test_ws_rejects_foreign_origin_accepts_local(make_client: Make) -> None:
    client = make_client()
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws", headers={"origin": "http://evil.example"}) as ws,
    ):
        ws.receive_text()
    with client.websocket_connect("/ws", headers={"origin": "http://127.0.0.1:8200"}) as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"


def _live_with_forming(root: Path, updated: datetime) -> None:
    now = updated
    payload = {
        "updated_at": now.isoformat(),
        "quote": {
            "bid": 4165.4, "ask": 4165.8, "mid": 4165.6, "spread_points": 40.0,
            "spread_price": 0.4, "timestamp": now.isoformat(),
        },
        "forming": {
            "M1": {"timestamp": now.replace(second=0).isoformat(), "open": 4165.0, "high": 4166.0,
                   "low": 4164.5, "close": 4165.6, "tick_volume": 12, "spread": 40},
            "M5": {"timestamp": now.isoformat(), "open": 1.0, "high": 0.5, "low": 2.0, "close": 1.0,
                   "tick_volume": 1},  # invalid OHLC: skipped, never served
            "H1": "garbage",
        },
        "symbol_spec": None,
    }  # fmt: skip
    (root / "live.json").write_text(json.dumps(payload), encoding="utf-8")


def test_forming_bars_are_served_open_and_invalid_rows_are_skipped(
    make_client: Make, store: Path
) -> None:
    _live_with_forming(store, datetime.now(UTC))
    body = make_client(data_root=store).get("/api/v2/market/forming").json()
    assert [b["timeframe"] for b in body["bars"]] == ["M1"]
    assert body["bars"][0]["bar"]["is_closed"] is False and body["updated_at"]


def test_forming_is_empty_not_an_error_without_a_live_file(
    make_client: Make, tmp_path: Path
) -> None:
    body = make_client(data_root=tmp_path / "none").get("/api/v2/market/forming").json()
    assert body == {"bars": [], "updated_at": None}


def test_ws_pushes_a_live_event_when_the_collector_writes(make_client: Make, store: Path) -> None:
    client = make_client(data_root=store, live_poll_seconds=0.02, heartbeat_seconds=0.05)
    with client.websocket_connect("/ws") as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"
        _live_with_forming(store, datetime.now(UTC) + timedelta(seconds=1))
        events = [json.loads(ws.receive_text()) for _ in range(6)]
    live = [e for e in events if e["type"] == "live"]
    assert live, "a new live file must produce a live event"
    assert live[0]["quote"]["bid"] == 4165.4 and live[0]["forming"][0]["timeframe"] == "M1"
    seqs = [e["seq"] for e in events]
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))  # no gaps across event kinds


def test_ws_announces_a_state_change_without_carrying_the_decision(
    make_client: Make, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = {"n": 0}

    def changing(_ctx: object) -> object:
        calls["n"] += 1  # same answer first, then a different one
        code = "SAME" if calls["n"] <= 2 else f"CHANGED{calls['n']}"
        return unavailable_state(datetime.now(UTC), "v", code, "test")

    monkeypatch.setattr("xau_edge_v2.api.live_socket.build_state", changing)
    client = make_client(
        data_root=store, live_poll_seconds=0.02, heartbeat_seconds=0.05, state_poll_seconds=0.05
    )
    with client.websocket_connect("/ws") as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"
        events = [json.loads(ws.receive_text()) for _ in range(12)]
    states = [e for e in events if e["type"] == "state"]
    assert states and "plan" not in states[0] and "action" not in states[0]


def test_model_endpoint_reports_research_status_and_locks_without_any_forecast(
    make_client: Make,
) -> None:
    body = make_client().get("/api/v2/model").json()
    assert body["available"] is True and body["status"] == "RETIRED" and body["authority"] == "NONE"
    assert body["model_id"] == "har_ridge" and body["k_family"] == "K_V2_VOL_V0" and body["k"] == 2
    assert body["candidates"] == ["har_ridge", "lightgbm_regressor"]
    assert (
        body["test_h"] == "LOCKED"
        and body["holdout"] == "LOCKED"
        and body["lightgbm_promoted"] is False
    )
    assert [s["name"][:8] for s in body["stages"]] == ["Phát tri", "Kiểm địn"]
    val = body["stages"][1]
    assert (
        val["skill_vs_atr14"] > 0.05 and val["ci95"][0] > 0 and 0.75 <= val["coverage_80"] <= 0.85
    )
    assert {c["id"] for c in val["criteria"]} == {
        "skill",
        "ci95",
        "ci_adjusted",
        "coverage",
        "years",
    }
    forbidden = {"forecast", "prediction", "expected_range", "confidence", "probability"}
    assert not forbidden & set(body) and "KHÔNG được hiển thị" in body["display"]
    state = make_client().get("/api/v2/state").json()
    assert state["model"]["task"] == "future_log_range" and "thẩm quyền" in state["model"]["note"]


def test_model_endpoint_is_honest_when_the_registry_is_missing(tmp_path: Path) -> None:
    detail = model_detail(tmp_path)
    assert (
        detail.available is False
        and detail.status.value == "NOT_DEPLOYED"
        and detail.authority == "NONE"
    )
