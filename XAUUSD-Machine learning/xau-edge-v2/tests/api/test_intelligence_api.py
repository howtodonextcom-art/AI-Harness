"""``/api/v2/intelligence``: described, scenario-based, authority NONE, and the decision untouched."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import write_live, write_store
from xau_edge_v2.api.intelligence import record_event, record_intelligence
from xau_edge_v2.api.paper import engine_tick
from xau_edge_v2.paper.store import PaperStore

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
    engine_tick(ctx)  # no page was ever opened
    rows = ctx.desk.store.events()
    assert [r["kind"] for r in rows] == ["ENGINE_START"]
    row = rows[0]
    assert row["strategy_version"] == "1.1.0" and row["action"] in ("WAIT", "BUY", "SELL")
    assert row["event_id"] and row["event_key"] and row["dataset_version"] and row["decision_id"]


def test_a_get_never_writes_however_many_clients(make_client: Make, tmp_path: Path) -> None:
    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    engine_tick(ctx)
    before = ctx.desk.store.event_count()
    snapshots = [c.get("/api/v2/intelligence").json() for _ in range(5)]

    def hit(_: int) -> int:
        return TestClient(c.app).get("/api/v2/intelligence").status_code

    with ThreadPoolExecutor(8) as pool:
        codes = list(pool.map(hit, range(24)))
    assert set(codes) == {200}
    assert ctx.desk.store.event_count() == before  # not a single row from 29 reads
    assert all(s["authority"] == "NONE" for s in snapshots)
    assert "intel_engine_prev" in ctx.cache  # the engine's own state, untouched by the reads


def test_recording_the_same_snapshot_twice_is_one_row(make_client: Make, tmp_path: Path) -> None:
    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    first = record_intelligence(ctx)
    second = record_intelligence(ctx)  # same cached analysis: same moment, same key
    assert first == 1 and second == 0
    assert ctx.desk.store.event_count() == 1
    kwargs = {
        "kind": "REGIME",
        "text": "H1: RANGE -> TREND_UP",
        "moment": datetime(2026, 1, 1, tzinfo=UTC),
        "action": "WAIT",
        "chain_verdict": "NO_DIRECTION",
        "strategy_version": "1.1.0",
        "decision_id": "d1",
        "setup_id": None,
        "position_id": None,
    }
    assert record_event(ctx, **kwargs) is True
    assert record_event(ctx, **kwargs) is False  # a retry never duplicates
    assert ctx.desk.store.event_count() == 2


def test_a_restart_keeps_history_and_starts_a_new_observation(
    make_client: Make, tmp_path: Path
) -> None:
    first = client(make_client, tmp_path)
    ctx1 = first.app.state.ctx  # type: ignore[attr-defined]
    engine_tick(ctx1)
    old = [r["event_id"] for r in ctx1.desk.store.events()]
    ctx1.desk.store.close()
    second = client(make_client, tmp_path)  # same database file, a fresh process state
    ctx2 = second.app.state.ctx  # type: ignore[attr-defined]
    assert [r["event_id"] for r in ctx2.desk.store.events()] == old  # history survived
    engine_tick(ctx2)
    rows = ctx2.desk.store.events()
    assert [r["kind"] for r in rows].count("ENGINE_START") == 2
    assert len({r["event_id"] for r in rows}) == 2  # distinct ids, nothing overwritten


def test_events_are_linked_to_the_open_paper_position(
    make_client: Make, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    monkeypatch.setattr(ctx.desk, "open_row", lambda: {"id": "POS-1"})
    record_intelligence(ctx)
    assert ctx.desk.store.events()[0]["paper_position_id"] == "POS-1"


def test_the_view_shows_the_stored_history_with_ids(make_client: Make, tmp_path: Path) -> None:
    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    engine_tick(ctx)
    body = c.get("/api/v2/intelligence").json()
    assert body["changes"] and body["changes"][0]["event_id"]
    assert body["authorization"]["chain_basis"] == "COUNTERFACTUAL_GATES_OFF"
    assert "chain_evaluable" in body["authorization"]


def test_an_old_database_is_migrated_in_place(tmp_path: Path) -> None:
    path = tmp_path / "old.sqlite3"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE decision_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,"
        " kind TEXT NOT NULL, text TEXT NOT NULL, action TEXT NOT NULL, chain_verdict TEXT NOT NULL,"
        " strategy_version TEXT NOT NULL);"
        "INSERT INTO decision_events (at, kind, text, action, chain_verdict, strategy_version)"
        " VALUES ('2026-10-13T00:00:00+00:00', 'INIT', 'old row', 'WAIT', 'X', '1.1.0');"
    )
    conn.commit()
    conn.close()
    store = PaperStore(path)
    assert store.event_count() == 1  # the old row is kept
    assert store.log_event({
        "at": "2026-10-13T00:01:00+00:00", "kind": "K", "text": "t", "action": "WAIT",
        "chain_verdict": "-", "strategy_version": "1.1.0", "event_key": "k1",
    })  # fmt: skip
    assert store.events()[0]["event_id"]
    store.close()


def test_an_unreachable_store_answers_with_the_error_shape(
    make_client: Make, tmp_path: Path
) -> None:
    r = make_client(data_root=tmp_path / "nope").get("/api/v2/intelligence")
    assert r.status_code == 503 and r.json()["error_code"] == "STORE_UNAVAILABLE"


def test_a_paper_order_is_in_the_trail_with_its_ids(make_client: Make, tmp_path: Path) -> None:
    from tests.unit.test_core import CTX, SPEC, buy_state  # noqa: PLC0415
    from xau_edge_v2.api.paper import _paper_event  # noqa: PLC0415
    from xau_edge_v2.core.decision import decide  # noqa: PLC0415

    c = client(make_client, tmp_path)
    ctx = c.app.state.ctx  # type: ignore[attr-defined]
    decision = decide(buy_state(), CTX)
    moment = datetime(2026, 3, 3, 10, 0, 20, tzinfo=UTC)
    row = ctx.desk.open_position(moment, decision, SPEC, "AUTO")
    assert row is not None
    _paper_event(ctx, moment, "PAPER_OPEN", str(row["id"]))
    trail = ctx.desk.store.events()[0]
    assert trail["kind"] == "PAPER_OPEN" and trail["paper_position_id"] == row["id"]
    assert trail["decision_id"] == decision.decision_id and trail["setup_id"] == decision.setup_id
    assert trail["strategy_version"] and trail["dataset_version"] and trail["event_id"]
    _paper_event(ctx, moment, "PAPER_OPEN", str(row["id"]))  # a retry is the same row
    assert [e["kind"] for e in ctx.desk.store.events()].count("PAPER_OPEN") == 1
