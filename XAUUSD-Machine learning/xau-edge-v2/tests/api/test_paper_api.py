from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import write_live
from tests.unit.test_core import CTX, buy_state
from xau_edge_v2.api import paper as paper_api
from xau_edge_v2.core.decision import Decision, decide
from xau_edge_v2.paper.desk import MinuteBar

Make = Callable[..., TestClient]
BUY = decide(buy_state(), CTX)


def _ctx(client: TestClient):  # type: ignore[no-untyped-def]
    return client.app.state.ctx  # type: ignore[attr-defined]


def _force(monkeypatch: pytest.MonkeyPatch, decision: Decision | None) -> None:
    """Make the live decision a given one (the desk and the routes both read it)."""
    monkeypatch.setattr("xau_edge_v2.api.paper.live_decision", lambda _ctx: decision)
    monkeypatch.setattr("xau_edge_v2.api.state.live_decision", lambda _ctx: decision)


def test_an_empty_desk_reports_honestly(make_client: Make) -> None:
    client = make_client()
    s = client.get("/api/v2/paper/summary").json()
    assert s["mode"] == "PAPER" and s["auto_paper"] is False
    assert s["equity"] == s["start_equity"] == 10_000.0 and s["open_count"] == 0
    assert s["governor"]["refusals"] == [] and s["assumptions"]
    assert client.get("/api/v2/paper/positions").json() == {"positions": []}
    assert client.get("/api/v2/paper/journal").json() == {"events": []}
    assert client.get("/api/v2/paper/positions?status=BOGUS").status_code == 422


def test_open_current_needs_a_valid_plan_and_names_why_not(make_client: Make) -> None:
    client = make_client()
    r = client.post("/api/v2/paper/open-current")  # the fixture store has too little history
    assert r.status_code == 409 and r.json()["error_code"] == "NO_VALID_PLAN"
    assert client.get("/api/v2/paper/positions").json()["positions"] == []


def test_open_current_opens_once_and_state_becomes_hold(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()
    _force(monkeypatch, BUY)
    opened = client.post("/api/v2/paper/open-current")
    assert opened.status_code == 200
    pos = opened.json()["position"]
    assert pos["status"] == "OPEN" and pos["side"] == "BUY" and pos["source"] == "MANUAL"
    assert pos["entry"] > pos["quote_entry"]  # adverse slippage
    again = client.post("/api/v2/paper/open-current")
    assert again.status_code == 409 and again.json()["error_code"] == "POSITION_ALREADY_OPEN"
    state = client.get("/api/v2/state").json()
    assert state["action"] == "HOLD" and state["reason_codes"] == ["POSITION_OPEN"]
    assert state["plan"]["entry"] == pos["entry"] and state["risk"]["lots"] == pos["lots"]
    assert state["mode"] == "PAPER" and state["evidence"] == "UNVALIDATED"
    assert [e["kind"] for e in client.get("/api/v2/paper/journal").json()["events"]] == ["OPENED"]


def test_manual_close_needs_a_fresh_quote_and_uses_the_closing_side(
    make_client: Make, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(data_root=store)
    _force(monkeypatch, BUY)
    pid = client.post("/api/v2/paper/open-current").json()["position"]["id"]
    write_live(store, quote_age_s=300.0, file_age_s=300.0)  # a stale collector
    time.sleep(0.3)  # the live file is cached for 0.25 s
    stale = client.post(f"/api/v2/paper/positions/{pid}/close")
    assert stale.status_code == 409 and stale.json()["error_code"] == "QUOTE_UNAVAILABLE"
    write_live(store)  # fresh again: bid 4165.43, ask 4165.78
    time.sleep(0.3)
    closed = client.post(f"/api/v2/paper/positions/{pid}/close")
    assert closed.status_code == 200
    pos = closed.json()["position"]
    assert (
        pos["status"] == "CLOSED"
        and pos["exit_reason"] == "MANUAL"
        and pos["exit_price"] == 4165.43
    )
    assert (
        client.post(f"/api/v2/paper/positions/{pid}/close").json()["error_code"]
        == "POSITION_NOT_OPEN"
    )
    assert client.post("/api/v2/paper/positions/missing/close").status_code == 404
    summary = client.get("/api/v2/paper/summary").json()
    assert summary["closed_count"] == 1 and summary["open_count"] == 0


def test_writes_refuse_a_foreign_origin_and_reads_do_not_care(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()
    _force(monkeypatch, BUY)
    evil = {"origin": "http://evil.example"}
    r = client.post("/api/v2/paper/open-current", headers=evil)
    assert r.status_code == 403 and r.json()["error_code"] == "FOREIGN_ORIGIN"
    assert client.get("/api/v2/paper/positions").json()["positions"] == []  # nothing was opened
    assert client.post("/api/v2/paper/positions/x/close", headers=evil).status_code == 403
    assert client.get("/api/v2/paper/summary", headers=evil).status_code == 200
    ok = client.post("/api/v2/paper/open-current", headers={"origin": "http://127.0.0.1:8200"})
    assert ok.status_code == 200


def test_the_only_post_routes_are_the_paper_writes_and_the_human_decision(
    make_client: Make,
) -> None:
    spec = make_client().get("/api/v2/openapi.json").json()
    posts = {path for path, ops in spec["paths"].items() if "post" in ops}
    assert posts == {
        "/api/v2/paper/open-current",
        "/api/v2/paper/positions/{position_id}/close",
        "/api/v2/human/decision",
    }
    assert not any(set(ops) & {"put", "patch", "delete"} for ops in spec["paths"].values())


def test_the_auto_engine_opens_a_valid_plan_once_and_manages_it_on_bars(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(auto_paper=True)
    ctx = _ctx(client)
    now = datetime.now(UTC)
    fresh = decide(buy_state(), CTX)
    assert fresh.expiry is not None
    fresh = replace(fresh, expiry=now + timedelta(minutes=10))
    _force(monkeypatch, fresh)
    opened = paper_api.engine_tick(ctx, now)
    assert len(opened) == 1
    assert paper_api.engine_tick(ctx, now + timedelta(seconds=3)) == []  # no second position
    row = ctx.desk.open_row()
    assert row is not None and row["source"] == "AUTO"
    # a new closed M1 bar reaches the target: the next pass books it
    start = int(now.replace(second=0, microsecond=0).timestamp() * 1_000_000) + 60_000_000
    bar = MinuteBar(start, row["take_profit"] + 1, row["entry"], 20.0)
    monkeypatch.setattr(paper_api, "minute_bars", lambda _c, _after: [bar])
    closed = paper_api.engine_tick(ctx, now + timedelta(minutes=2))
    assert closed == [row["id"]] or row["id"] in closed
    done = ctx.desk.store.position(row["id"])
    assert done is not None and done["exit_reason"] == "TAKE_PROFIT"


def test_the_engine_ignores_an_expired_or_waiting_decision(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(auto_paper=True)
    ctx = _ctx(client)
    now = datetime.now(UTC)
    expired = replace(decide(buy_state(), CTX), expiry=now - timedelta(minutes=1))
    _force(monkeypatch, expired)
    assert paper_api.engine_tick(ctx, now) == []
    _force(monkeypatch, decide(buy_state(m5_momentum="FLAT"), CTX))
    assert paper_api.engine_tick(ctx, now) == []
    _force(monkeypatch, None)
    assert paper_api.engine_tick(ctx, now) == []
    assert ctx.desk.store.positions() == []


def test_auto_off_never_opens_by_itself(make_client: Make, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make_client(auto_paper=False)
    _force(monkeypatch, decide(buy_state(), CTX))
    assert paper_api.engine_tick(_ctx(client), datetime.now(UTC)) == []


def test_the_socket_announces_a_paper_change(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client(live_poll_seconds=0.02, heartbeat_seconds=0.05)
    _force(monkeypatch, BUY)
    with client.websocket_connect("/ws") as ws:
        assert json.loads(ws.receive_text())["type"] == "hello"
        client.post("/api/v2/paper/open-current")
        types: list[str] = []
        for _ in range(60):  # heartbeats may come first; the paper event must arrive soon
            types.append(json.loads(ws.receive_text())["type"])
            if types[-1] == "paper":
                break
    assert "paper" in types


def test_forward_summary_is_empty_then_describes_what_the_engine_saw(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()
    empty = client.get("/api/v2/forward/summary").json()
    assert empty["evidence"] == "NO_OBSERVATIONS" and empty["funnel"] is None
    assert empty["progress"]["claim_allowed"] is False and empty["mode"] == "PAPER"
    ctx = _ctx(client)
    _force(monkeypatch, decide(buy_state(m5_momentum="FLAT"), CTX))
    assert paper_api.log_forward(ctx, datetime.now(UTC)) is True
    body = client.get("/api/v2/forward/summary").json()
    assert body["evidence"] == "FORWARD_ACCUMULATING" and body["logged_bars"] == 1
    assert body["funnel"]["by_action"] == {"WAIT": 1} and body["funnel"]["first_refusal"] == {
        "NO_TRIGGER": 1
    }
    assert body["funnel"]["signals"] == 0 and body["trades"] == []
    assert (
        body["progress"]["claim_allowed"] is False and body["progress"]["min_closed_trades"] == 100
    )
    assert any("UNVALIDATED" in n for n in body["notes"])
    assert body["paper_return_pct"] == 0.0 and body["protocol"].endswith(
        "FORWARD_EVIDENCE_PROTOCOL.md"
    )


def test_the_forward_summary_counts_a_real_paper_trade_and_never_claims(
    make_client: Make, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = make_client()
    ctx = _ctx(client)
    _force(monkeypatch, BUY)
    assert paper_api.log_forward(ctx, datetime.now(UTC)) is True
    client.post("/api/v2/paper/open-current")
    body = client.get("/api/v2/forward/summary").json()
    assert body["funnel"]["by_action"] == {"BUY": 1} and body["funnel"]["signals"] == 1
    assert body["funnel"]["distinct_setups"] == 1
    assert (
        body["trades"] == [] and body["progress"]["closed_trades"] == 0
    )  # open trades are not results
