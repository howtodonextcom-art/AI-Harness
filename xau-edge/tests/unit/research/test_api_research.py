"""The research API: GET only, bounded inputs, no paths or secrets, demote is down-only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests.unit.api.test_api import PROP
from tests.unit.control.fakes import TOKEN, Rig
from tests.unit.research.helpers import make_repo, result_file, write
from xau_edge.api.app import ALLOWED_ORIGINS, create_app
from xau_edge.api.service import ApiContext
from xau_edge.control.security import TOKEN_HEADER
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.research.service import ResearchService

PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
GET_PATHS = (
    "/research/overview",
    "/research/ledger",
    "/research/power",
    "/research/hypotheses",
    "/research/candidates",
    "/research/data",
    "/research/locks",
    "/research/calibration",
    "/research/soak",
    "/research/stage1",
    "/research/stage1/x",
    "/research/lineage",
    "/research/prospective",
    "/research/rollout",
    "/research/gates",
    "/lifecycle/strategies",
    "/lifecycle/x/forward",
)


def _ctx(tmp_path: Path, *, research: bool, control: Rig | None = None) -> ApiContext:
    return ApiContext(
        load_frames=lambda: (_ for _ in ()).throw(RuntimeError("no data in this test")),
        registry=ExperimentRegistry(tmp_path / "runs"),
        prop=PROP,
        models_dir=tmp_path / "models",
        research=ResearchService(tmp_path / "repo") if research else None,
        control=control.service if control else None,
        control_port=PORT,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "repo")


@pytest.fixture
def client(tmp_path: Path, repo: Path) -> TestClient:
    return TestClient(create_app(_ctx(tmp_path, research=True)), base_url=BASE)


def test_every_research_and_lifecycle_route_is_get_only(client: TestClient) -> None:
    routes = [r for r in client.app.routes if isinstance(r, APIRoute)]  # type: ignore[attr-defined]
    mine = [r for r in routes if r.path.startswith(("/research", "/lifecycle"))]
    assert len(mine) >= 18
    for route in mine:
        assert route.methods == {"GET"}, route.path


@pytest.mark.parametrize("path", GET_PATHS)
def test_each_page_answers_and_a_write_verb_is_refused(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200
    for verb in (client.post, client.put, client.delete, client.patch):
        assert verb(path).status_code in {403, 404, 405}


def test_without_a_research_service_the_routes_say_unavailable(tmp_path: Path) -> None:
    c = TestClient(create_app(_ctx(tmp_path, research=False)), base_url=BASE)
    for path in GET_PATHS:
        assert c.get(path).status_code == 503


def test_query_parameters_are_bounded(client: TestClient) -> None:
    assert client.get("/research/power", params={"k": 0}).status_code == 422
    assert client.get("/research/power", params={"k": 1001}).status_code == 422
    assert client.get("/research/power", params={"n": 0}).status_code == 422
    assert client.get("/research/power", params={"sd": 0}).status_code == 422
    assert client.get("/research/power", params={"k": 8, "n": 1000}).json()["k"] == 8
    assert client.get("/research/ledger", params={"programme": "v3"}).status_code == 422
    assert client.get("/research/ledger", params={"hypothesis": "../x"}).status_code == 422
    assert client.get("/research/ledger", params={"hypothesis": "H01"}).json()["shown"] == 4


@pytest.mark.parametrize("bad", ["..", "..%2f..%2f.env", "a b", "x" * 80, "%00"])
def test_a_variant_or_strategy_id_cannot_be_a_path(client: TestClient, bad: str) -> None:
    for url in (f"/research/candidates/{bad}", f"/lifecycle/{bad}/forward"):
        r = client.get(url)
        assert r.status_code in {404, 422, 200}
        if r.status_code == 200:
            assert r.json()["status"] == "unknown"


def test_answers_carry_no_absolute_path_and_no_secret(client: TestClient, tmp_path: Path) -> None:
    write(tmp_path / "repo", ".env", "MT5_PASSWORD=hunter2\n")
    write(tmp_path / "repo", "data/execution/control_token", "supersecret-token")
    write(tmp_path / "repo", "configs/.env.local", "XAU_EDGE_TELEGRAM_BOT_TOKEN=abc\n")
    for path in GET_PATHS:
        text = client.get(path).text
        assert str(tmp_path) not in text, path
        assert "hunter2" not in text
        assert "supersecret" not in text
        assert "TELEGRAM" not in text


def test_the_overview_over_http_shows_the_banner_and_the_pending_decisions(
    client: TestClient,
) -> None:
    body = client.get("/research/overview").json()
    assert body["banner"] == "Không có edge được kiểm định."
    assert body["verdict"]["label"].startswith("(B)")
    assert [d["id"] for d in body["decisions"]] == ["D-1", "D-2"]


def test_the_ui_forbidden_words_do_not_appear_in_any_answer(client: TestClient) -> None:
    for path in GET_PATHS:
        text = client.get(path).text.lower()
        assert "guaranteed" not in text
        assert "will make money" not in text


# -- the one write: demote, through the control guard -----------------------------------------


def _headers(**over: str) -> dict[str, str]:
    base = {
        TOKEN_HEADER: TOKEN,
        "Origin": ALLOWED_ORIGINS[0],
        "Content-Type": "application/json",
        "Idempotency-Key": "abcdef123456",
    }
    base.update(over)
    return {k: v for k, v in base.items() if v != ""}


@pytest.fixture
def control_client(tmp_path: Path, repo: Path) -> TestClient:
    (tmp_path / "rig").mkdir()
    rig = Rig(tmp_path / "rig")
    for name in ("dev", "val"):
        body = json.dumps(result_file("H04-L40", name, passed=True))
        write(repo, f"experiments/edge_program/H04-L40_{name}_x.json", body)
    event = {
        "strategy_id": "H04-L40",
        "from_state": "RESEARCH",
        "to_state": "PAPER",
        "at": "t",
        "source": "cli",
        "reason": "r",
    }
    write(repo, "data/execution/lifecycle.jsonl", json.dumps(event) + "\n")
    return TestClient(create_app(_ctx(tmp_path, research=True, control=rig)), base_url=BASE)


def _demote(client: TestClient, body: dict[str, Any], **headers: str) -> Any:
    return client.post(
        "/control/lifecycle/demote", content=json.dumps(body), headers=_headers(**headers)
    )


def test_a_demotion_needs_the_token_the_origin_and_the_typed_word(
    control_client: TestClient,
) -> None:
    good = {
        "strategy_id": "H04-L40",
        "to": "WATCH",
        "reason": "window below bound",
        "confirm": "DEMOTE",
    }
    assert _demote(control_client, good, **{TOKEN_HEADER: ""}).status_code == 403
    assert _demote(control_client, good, Origin="http://evil.example").status_code == 403
    assert _demote(control_client, good, **{"Idempotency-Key": ""}).status_code == 400
    wrong = _demote(control_client, {**good, "confirm": "demote"})
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "CONFIRMATION_MISMATCH"
    ok = _demote(control_client, good)
    assert ok.status_code == 200
    assert ok.json()["event"]["to_state"] == "WATCH"
    rows = control_client.get("/lifecycle/strategies").json()["strategies"]
    assert {s["strategy_id"]: s["state"] for s in rows}["H04-L40"] == "WATCH"


@pytest.mark.parametrize(
    "target", ["VALIDATED", "FUNDED", "PAPER", "RESEARCH", "RETIRED", "nonsense"]
)
def test_the_web_cannot_promote_or_name_another_state(
    control_client: TestClient, target: str
) -> None:
    body = {"strategy_id": "H04-L40", "to": target, "reason": "try", "confirm": "DEMOTE"}
    assert _demote(control_client, body).status_code == 422


def test_the_web_cannot_touch_rejected_or_unknown_strategies(control_client: TestClient) -> None:
    for sid in ("baseline_c", "unknown-thing"):
        body = {"strategy_id": sid, "to": "WATCH", "reason": "x", "confirm": "DEMOTE"}
        r = _demote(control_client, body)
        assert r.status_code == 409
        assert r.json()["detail"]["code"] == "DEMOTE_REFUSED"


def test_extra_fields_are_rejected_so_no_other_parameter_can_ride_along(
    control_client: TestClient,
) -> None:
    body = {
        "strategy_id": "H04-L40",
        "to": "WATCH",
        "reason": "x",
        "confirm": "DEMOTE",
        "promote": True,
    }
    assert _demote(control_client, body).status_code == 422


def test_without_control_enabled_the_demote_route_does_not_exist(client: TestClient) -> None:
    paths = {getattr(r, "path", "") for r in client.app.routes}  # type: ignore[attr-defined]
    assert "/control/lifecycle/demote" not in paths


def test_the_same_idempotency_key_replays_the_first_demotion(control_client: TestClient) -> None:
    body = {"strategy_id": "H04-L40", "to": "WATCH", "reason": "first", "confirm": "DEMOTE"}
    first = _demote(control_client, body)
    again = _demote(control_client, {**body, "to": "DISABLED", "reason": "second"})
    assert first.status_code == again.status_code == 200
    assert again.json()["event"]["to_state"] == "WATCH"
    states = control_client.get("/lifecycle/strategies").json()["strategies"]
    assert {s["strategy_id"]: s["state"] for s in states}["H04-L40"] == "WATCH"


def test_research_reads_refuse_a_foreign_host_when_the_control_plane_is_on(
    tmp_path: Path, repo: Path
) -> None:
    (tmp_path / "rig").mkdir()
    rig = Rig(tmp_path / "rig")
    client = TestClient(
        create_app(_ctx(tmp_path, research=True, control=rig)), base_url="http://evil.example"
    )
    assert client.get("/research/overview").status_code == 403
    assert client.get("/lifecycle/strategies").status_code == 403
