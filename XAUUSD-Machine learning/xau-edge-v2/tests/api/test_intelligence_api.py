"""``/api/v2/intelligence``: described, scenario-based, authority NONE, and the decision untouched."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import write_live, write_store
from xau_edge_v2.api.paper import engine_tick

Make = Callable[..., TestClient]


def client(make_client: Make, tmp_path: Path) -> TestClient:
    root = write_store(tmp_path / "deep", minutes=500)
    write_live(root)
    return make_client(data_root=root)


def test_the_document_is_descriptive_and_has_no_authority(
    make_client: Make, tmp_path: Path
) -> None:
    body = client(make_client, tmp_path).get("/api/v2/intelligence").json()
    assert body["authority"] == "NONE" and body["descriptive_only"] is True
    assert body["evidence"] == "UNVALIDATED"
    auth = body["authorization"]
    assert auth["candidate_active"] is False and auth["strategy_version"] == "1.1.0"
    assert auth["evidence"] == "UNVALIDATED"
    assert {s["key"] for s in body["scenarios"]} >= {"NO_TRADE", "CONTINUATION", "REVERSAL"}
    assert [t["timeframe"] for t in body["timeframes"]] == ["H4", "H1", "M15", "M5", "M1"]


def test_the_funnel_and_the_three_reasons_are_always_present(
    make_client: Make, tmp_path: Path
) -> None:
    auth = client(make_client, tmp_path).get("/api/v2/intelligence").json()["authorization"]
    keys = [s["key"] for s in auth["funnel"]]
    assert keys[:2] == ["H1_DIRECTION", "HTF_CONFLICT"] and "GATE_GOVERNOR" in keys
    assert {"chain_verdict", "gates", "system_hold", "explanation"} <= set(auth)
    if auth["action"] == "WAIT":
        assert auth["explanation"]


def test_the_intelligence_never_changes_the_strategy_decision(
    make_client: Make, tmp_path: Path
) -> None:
    c = client(make_client, tmp_path)
    before = c.get("/api/v2/state").json()
    c.get("/api/v2/intelligence")
    c.get("/api/v2/intelligence")
    after = c.get("/api/v2/state").json()
    for key in ("action", "reason_codes", "blocker", "strategy_version", "readiness_level"):
        assert before[key] == after[key]
    assert after["mode"] == "PAPER"


def test_the_engine_records_state_transitions_without_a_viewer(
    make_client: Make, tmp_path: Path
) -> None:
    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    engine_tick(ctx)
    rows = ctx.desk.store.events()
    assert rows and rows[-1]["kind"] == "INIT"
    assert rows[-1]["strategy_version"] == "1.1.0" and rows[-1]["action"] in ("WAIT", "BUY", "SELL")


def test_an_unreachable_store_answers_with_the_error_shape(
    make_client: Make, tmp_path: Path
) -> None:
    r = make_client(data_root=tmp_path / "nope").get("/api/v2/intelligence")
    assert r.status_code == 503 and r.json()["error_code"] == "STORE_UNAVAILABLE"
