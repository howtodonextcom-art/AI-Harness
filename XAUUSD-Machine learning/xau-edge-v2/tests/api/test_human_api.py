"""G9: the human layer. The human is the final authority; the system only advises; nothing is sent."""

from __future__ import annotations

import ast
import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.test_execution import assess
from xau_edge_v2.api import paper as paper_api
from xau_edge_v2.core.decision import Decision
from xau_edge_v2.core.execution import ExecutionAssessment
from xau_edge_v2.paper.desk import PaperDesk

Make = Callable[..., TestClient]
SRC = Path(__file__).resolve().parents[2] / "src" / "xau_edge_v2"


def candidate(ask: float = 2000.4) -> tuple[Decision, ExecutionAssessment]:
    execution, decision = assess(ask=ask)
    expiry = datetime.now(UTC) + timedelta(minutes=10)
    return replace(decision, expiry=expiry), execution


def force(
    monkeypatch: pytest.MonkeyPatch,
    decision: Decision | None,
    execution: ExecutionAssessment | None,
) -> None:
    for module in ("human", "state", "paper"):
        monkeypatch.setattr(f"xau_edge_v2.api.{module}.live_decision", lambda _c, d=decision: d)
    for module in ("human", "state"):
        monkeypatch.setattr(f"xau_edge_v2.api.{module}.live_execution", lambda _c, e=execution: e)


def post(
    client: TestClient, choice: str, setup_id: str, reason: str = "", **headers: str
) -> object:
    return client.post(
        "/api/v2/human/decision",
        json={"choice": choice, "setup_id": setup_id, "reason": reason},
        headers=headers,
    )


# ---- system and human are separate layers -------------------------------------------------------
def test_state_carries_a_system_advice_block_and_no_human_choice_yet(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    state = make_client().get("/api/v2/state").json()
    system = state["system"]
    assert system["recommendation"] == "BUY_CANDIDATE" and system["strategy_action"] == "BUY"
    assert (
        system["bias"] == "BUY"
        and system["setup_state"] == "ARMED"
        and system["trigger_state"] == "CONFIRMED"
    )
    assert (
        system["m1"]["state"] == "EXECUTION_WINDOW"
        and system["m1"]["quality"] == "GOOD"
        and system["m1"]["direction"] == "BUY"
    )
    assert system["primary_blocker"] is None and "CON NGƯỜI" in system["reasons"][0]
    assert (
        state["action"] == "BUY" and state["human"] is None
    )  # the strategy's own word, and no human choice
    assert state["evidence"] == "UNVALIDATED" and state["mode"] == "PAPER"


def test_a_late_candidate_is_a_wait_for_the_system_while_the_strategy_still_says_buy(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate(ask=2001.5)
    force(monkeypatch, decision, execution)
    system = make_client().get("/api/v2/state").json()["system"]
    assert system["recommendation"] == "WAIT" and system["strategy_action"] == "BUY"
    assert system["primary_blocker"] == "M1_TOO_LATE" and system["m1"]["state"] == "TOO_LATE"
    assert system["bias"] == "BUY"


# ---- ACCEPT / WAIT / REJECT ------------------------------------------------------------------------
@pytest.mark.parametrize("choice", ["ACCEPT", "WAIT", "REJECT"])
def test_each_choice_is_recorded_with_the_system_state_it_answered(
    make_client: Make, monkeypatch: pytest.MonkeyPatch, choice: str
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    r = post(client, choice, decision.setup_id, "tôi thấy hợp lý")
    assert r.status_code == 200  # type: ignore[attr-defined]
    body = r.json()  # type: ignore[attr-defined]
    rec = body["record"]
    assert (
        body["ok"] is True
        and rec["human_choice"] == choice
        and rec["human_reason"] == "tôi thấy hợp lý"
    )
    assert (
        rec["system_action"] == "BUY"
        and rec["system_recommendation"] == "BUY_CANDIDATE"
        and rec["system_bias"] == "BUY"
    )
    assert rec["setup_state"] == "ARMED" and rec["trigger_state"] == "CONFIRMED"
    assert rec["m1_execution_state"] == "EXECUTION_WINDOW" and rec["m1_quality"] == "GOOD"
    assert (
        rec["entry"] == decision.entry_price
        and rec["sl"] == decision.stop_loss
        and rec["tp"] == decision.take_profit
    )
    assert (
        rec["rr"] == decision.net_rr
        and rec["risk_pct"] == decision.risk_pct
        and rec["risk_amount"] == decision.risk_amount
    )
    assert rec["decision_id"] == decision.decision_id and rec["setup_id"] == decision.setup_id
    assert (
        rec["paper_mode"] == "PAPER"
        and rec["evidence_label"] == "UNVALIDATED"
        and rec["strategy_version"] == "1.1.0"
    )
    assert rec["timestamp"] and rec["expiry"] and rec["price"] == 2000.0
    if choice == "ACCEPT":
        assert "Không có lệnh nào được gửi đi" in body["message"]


def test_accept_changes_neither_the_system_signal_nor_the_paper_book(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    before = client.get("/api/v2/state").json()
    assert post(client, "ACCEPT", decision.setup_id).status_code == 200  # type: ignore[attr-defined]
    after = client.get("/api/v2/state").json()
    assert after["system"] == before["system"]  # the system layer is untouched
    for key in ("action", "readiness_level", "plan", "risk", "reason_codes", "strategy_version"):
        assert after[key] == before[key], key
    assert after["human"]["human_choice"] == "ACCEPT" and before["human"] is None
    assert client.get("/api/v2/paper/positions").json()["positions"] == []  # ACCEPT opens nothing
    assert client.get("/api/v2/paper/journal").json()["events"] == []


def test_accept_works_even_if_the_paper_desk_could_not_open_anything(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)

    def boom(*_a: object, **_k: object) -> None:
        msg = "the human layer must not touch the paper desk"
        raise AssertionError(msg)

    monkeypatch.setattr(PaperDesk, "open_position", boom)
    assert post(make_client(), "ACCEPT", decision.setup_id).status_code == 200  # type: ignore[attr-defined]


def test_a_change_of_mind_is_a_new_row_and_history_is_never_rewritten(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    first = post(client, "WAIT", decision.setup_id, "chờ thêm").json()["record"]  # type: ignore[attr-defined]
    second = post(client, "ACCEPT", decision.setup_id, "đã đủ").json()["record"]  # type: ignore[attr-defined]
    rows = client.get("/api/v2/human/decisions").json()["decisions"]
    assert [r["human_choice"] for r in rows] == ["ACCEPT", "WAIT"] and first["id"] != second["id"]
    assert rows[1] == first  # the earlier row is byte for byte what it was
    assert (
        client.get("/api/v2/state").json()["human"]["human_choice"] == "ACCEPT"
    )  # the latest wins in the view only


def test_the_history_cannot_be_edited_or_deleted_even_with_raw_sql(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    post(client, "REJECT", decision.setup_id)
    store = client.app.state.ctx.desk.store  # type: ignore[attr-defined]
    db = store._db
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("UPDATE human_decisions SET human_choice = 'ACCEPT'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        db.execute("DELETE FROM human_decisions")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute(
            "INSERT INTO human_decisions (id, timestamp, decision_id, setup_id, system_action, system_recommendation, system_bias, setup_state, trigger_state, human_choice, human_reason, paper_mode, strategy_version, evidence_label) VALUES ('x','t','d','s','BUY','WAIT','BUY','a','b','MAYBE','', 'PAPER','1','U')"
        )
    with pytest.raises(sqlite3.DatabaseError):
        db.execute(
            "INSERT INTO human_decisions (id, timestamp, decision_id, setup_id, system_action, system_recommendation, system_bias, setup_state, trigger_state, human_choice, human_reason, paper_mode, strategy_version, evidence_label) VALUES ('y','t','d','s','BUY','WAIT','BUY','a','b','ACCEPT','', 'LIVE','1','U')"
        )
    assert [r["human_choice"] for r in store.human_decisions()] == ["REJECT"]


# ---- the server decides every number; the page cannot -------------------------------------------------
def test_the_request_cannot_carry_a_price_a_size_or_an_unknown_choice(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    base = {"choice": "ACCEPT", "setup_id": decision.setup_id}
    for extra in ({"entry": 1.0}, {"lots": 5}, {"sl": 1.0}, {"tp": 9999}, {"paper_mode": "LIVE"}):
        assert client.post("/api/v2/human/decision", json={**base, **extra}).status_code == 422
    assert client.post("/api/v2/human/decision", json={**base, "choice": "BUY"}).status_code == 422
    assert (
        client.post("/api/v2/human/decision", json={**base, "reason": "x" * 501}).status_code == 422
    )
    assert client.post("/api/v2/human/decision", json={"choice": "ACCEPT"}).status_code == 422
    assert client.get("/api/v2/human/decisions").json()["decisions"] == []


def test_the_reason_is_plain_one_line_text(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    rec = post(client, "WAIT", decision.setup_id, "  dòng 1\n\x00dòng 2\t<b>x</b>  ").json()[
        "record"
    ]  # type: ignore[attr-defined]
    assert (
        rec["human_reason"] == "dòng 1 dòng 2 <b>x</b>"
    )  # stored as text; the page renders it as text


def test_only_the_current_candidate_can_be_answered(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    stale = post(client, "ACCEPT", "an-older-setup")
    assert stale.status_code == 409 and stale.json()["error_code"] == "STALE_CANDIDATE"  # type: ignore[attr-defined]
    expired = replace(decision, expiry=datetime.now(UTC) - timedelta(seconds=1))
    force(monkeypatch, expired, execution)
    r = post(client, "ACCEPT", decision.setup_id)
    assert r.status_code == 409 and r.json()["error_code"] == "EXPIRED"  # type: ignore[attr-defined]
    force(monkeypatch, None, None)
    assert post(client, "ACCEPT", decision.setup_id).json()["error_code"] == "NO_DATA"  # type: ignore[attr-defined]
    assert client.get("/api/v2/human/decisions").json()["decisions"] == []


def test_there_is_nothing_to_decide_when_the_system_says_wait_or_hold(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()
    late, late_exec = candidate(ask=2001.5)
    force(monkeypatch, late, late_exec)
    r = post(client, "ACCEPT", late.setup_id)
    assert (
        r.status_code == 409
        and r.json()["error_code"] == "NO_CANDIDATE"
        and "WAIT" in r.json()["message"]
    )  # type: ignore[attr-defined]
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    assert post(client, "ACCEPT", decision.setup_id).status_code == 200  # type: ignore[attr-defined]
    assert client.app.state.ctx.desk.open_position(
        datetime.now(UTC), decision, paper_api._spec(client.app.state.ctx)[0], "MANUAL"
    )  # type: ignore[attr-defined]
    held = post(client, "REJECT", decision.setup_id)
    assert held.status_code == 409 and held.json()["error_code"] == "NO_CANDIDATE"  # type: ignore[attr-defined]
    state = client.get("/api/v2/state").json()
    assert state["action"] == "HOLD" and state["system"]["recommendation"] == "HOLD"


def test_a_foreign_origin_cannot_write_a_human_decision(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client()
    r = post(client, "ACCEPT", decision.setup_id, origin="http://evil.example")
    assert r.status_code == 403 and r.json()["error_code"] == "FOREIGN_ORIGIN"  # type: ignore[attr-defined]
    assert client.get("/api/v2/human/decisions").json()["decisions"] == []
    ok = post(client, "ACCEPT", decision.setup_id, origin="http://127.0.0.1:8200")
    assert ok.status_code == 200  # type: ignore[attr-defined]


# ---- persistence and independence -------------------------------------------------------------------
def test_the_human_choice_survives_a_restart(
    make_client: Make, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    first = make_client()
    rec = post(first, "ACCEPT", decision.setup_id, "ok").json()["record"]  # type: ignore[attr-defined]
    first.app.state.ctx.desk.store.close()  # type: ignore[attr-defined]
    second = make_client()  # a new application on the same database file
    rows = second.get("/api/v2/human/decisions").json()["decisions"]
    assert [r["id"] for r in rows] == [rec["id"]] and rows[0] == rec
    state = second.get("/api/v2/state").json()
    assert state["human"] == rec and state["system"]["recommendation"] == "BUY_CANDIDATE"


def test_auto_paper_is_independent_of_the_human_layer(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client(auto_paper=True)
    ctx = client.app.state.ctx  # type: ignore[attr-defined]
    # the human REJECTS the candidate ...
    assert post(client, "REJECT", decision.setup_id).status_code == 200  # type: ignore[attr-defined]
    # ... and the research-only AUTO PAPER engine still does what it always did with the strategy's BUY
    opened = paper_api.engine_tick(ctx, datetime.now(UTC))
    assert len(opened) == 1
    position = ctx.desk.open_row()
    assert position is not None and position["source"] == "AUTO"
    # the human record is unchanged by the paper position
    rows = client.get("/api/v2/human/decisions").json()["decisions"]
    assert len(rows) == 1 and rows[0]["human_choice"] == "REJECT"


def test_the_socket_announces_a_human_decision(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    decision, execution = candidate()
    force(monkeypatch, decision, execution)
    client = make_client(live_poll_seconds=0.02, heartbeat_seconds=0.05)
    with client.websocket_connect("/ws") as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"
        post(client, "WAIT", decision.setup_id)
        types: list[str] = []
        for _ in range(60):
            types.append(json.loads(ws.receive_text())["type"])
            if types[-1] == "human":
                break
    assert "human" in types


# ---- no broker path ------------------------------------------------------------------------------------
def test_the_human_module_has_no_way_to_open_a_position_or_reach_a_broker() -> None:
    tree = ast.parse((SRC / "api" / "human.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert "xau_edge_v2.paper.desk" not in imported
    called = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not {"open_position", "close_manual", "order_send", "send_order", "manage"} & called
    text = (SRC / "api" / "human.py").read_text(encoding="utf-8")
    for banned in ("MetaTrader5", "order_send", "mt5", "requests.", "httpx", "urllib"):
        assert banned not in text, banned
