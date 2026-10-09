"""Research console security: hostile hosts, traversal, secrets, oversize and malformed input."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.unit.control.fakes import Rig
from tests.unit.research.helpers import make_repo, write
from tests.unit.research.test_api_research import (
    BASE,
    GET_PATHS,
    _ctx,
    _headers,
)
from xau_edge.api.app import create_app
from xau_edge.research.paths import ResearchRoot, SourceUnavailableError


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path / "repo")


@pytest.fixture
def guarded(tmp_path: Path, repo: Path) -> TestClient:
    (tmp_path / "rig").mkdir()
    rig = Rig(tmp_path / "rig")
    return TestClient(create_app(_ctx(tmp_path, research=True, control=rig)), base_url=BASE)


@pytest.mark.parametrize("path", GET_PATHS)
@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1:9999", "localhost.evil.example:8000"])
def test_every_research_read_refuses_a_hostile_host_when_control_is_on(
    tmp_path: Path, repo: Path, path: str, host: str
) -> None:
    (tmp_path / "rig2").mkdir()
    rig = Rig(tmp_path / "rig2")
    client = TestClient(create_app(_ctx(tmp_path, research=True, control=rig)), base_url=BASE)
    assert client.get(path, headers={"host": host}).status_code == 403


@pytest.mark.parametrize("path", GET_PATHS)
def test_the_normal_host_still_works_with_control_on(guarded: TestClient, path: str) -> None:
    assert guarded.get(path).status_code == 200


@pytest.mark.parametrize("verb", ["put", "delete", "patch", "options", "post"])
def test_unexpected_verbs_never_succeed_on_research_paths(guarded: TestClient, verb: str) -> None:
    for path in GET_PATHS:
        response = getattr(guarded, verb)(path)
        assert response.status_code in {403, 404, 405}


@pytest.mark.parametrize(
    "bad",
    ["%2e%2e%2f%2e%2e%2f.env", "..%5c..%5c.env", "%2e%2e", "....//....//x", "a%00b", "%252e%252e"],
)
def test_encoded_traversal_in_an_id_is_refused_or_unknown(guarded: TestClient, bad: str) -> None:
    for url in (
        f"/research/candidates/{bad}",
        f"/research/stage1/{bad}",
        f"/lifecycle/{bad}/forward",
    ):
        r = guarded.get(url)
        assert r.status_code in {404, 422, 200}
        assert "MT5_" not in r.text
        if r.status_code == 200:
            assert r.json()["status"] == "unknown"


@pytest.mark.parametrize(
    "rel",
    [
        ".env",
        "docs/research/../../.env",
        "configs/.env.production",
        "data/execution/lifecycle.sqlite",
        "data/execution/funded_state.sqlite",
        "data/execution/control_token",
        "experiments/secrets.json",
        "docs/research/credentials.json",
        "/etc/passwd",
        "C:/Windows/win.ini",
        "docs\\research\\x",
        "docs/research/x.pem",
    ],
)
def test_the_research_root_refuses_secrets_databases_and_escapes(repo: Path, rel: str) -> None:
    root = ResearchRoot(repo)
    for reader in (root.read_text, root.read_json, root.resolve):
        with pytest.raises(SourceUnavailableError):
            reader(rel)


def test_oversized_and_malformed_query_values_are_refused(guarded: TestClient) -> None:
    assert guarded.get("/research/power", params={"k": 10**9}).status_code == 422
    assert guarded.get("/research/power", params={"n": 10**12}).status_code == 422
    assert guarded.get("/research/power", params={"sd": "nan"}).status_code == 422
    assert guarded.get("/research/power", params={"sd": "inf"}).status_code == 422
    assert guarded.get("/research/ledger", params={"period": "x" * 10_000}).status_code == 422
    assert guarded.get("/research/ledger", params={"scenario": "x" * 21}).status_code == 422


def test_malformed_demote_bodies_are_refused_without_a_write(
    guarded: TestClient, repo: Path
) -> None:
    lifecycle = repo / "data" / "execution" / "lifecycle.jsonl"
    cases = [
        "{not json",
        "[]",
        "null",
        json.dumps({"strategy_id": "x", "to": "WATCH", "reason": "r", "confirm": "DEMOTE", "z": 1}),
        json.dumps({"strategy_id": "../../x", "to": "WATCH", "reason": "r", "confirm": "DEMOTE"}),
        json.dumps({"strategy_id": "x", "to": "FUNDED", "reason": "r", "confirm": "DEMOTE"}),
        json.dumps(
            {"strategy_id": "x", "to": "WATCH", "reason": "r" * 10_000, "confirm": "DEMOTE"}
        ),
    ]
    for body in cases:
        response = guarded.post("/control/lifecycle/demote", content=body, headers=_headers())
        assert response.status_code in {400, 409, 422}, body[:40]
    assert not lifecycle.exists()


def test_a_demote_with_a_foreign_origin_or_wrong_content_type_never_writes(
    guarded: TestClient, repo: Path
) -> None:
    body = json.dumps({"strategy_id": "x", "to": "WATCH", "reason": "r", "confirm": "DEMOTE"})
    bad_origin = guarded.post(
        "/control/lifecycle/demote", content=body, headers=_headers(Origin="http://evil.example")
    )
    assert bad_origin.status_code == 403
    bad_type = guarded.post(
        "/control/lifecycle/demote",
        content=body,
        headers=_headers(**{"Content-Type": "text/plain"}),
    )
    assert bad_type.status_code in {400, 403, 415}
    assert not (repo / "data" / "execution" / "lifecycle.jsonl").exists()


def test_no_route_under_research_or_lifecycle_accepts_a_body_or_writes(
    guarded: TestClient, repo: Path
) -> None:
    before = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    for path in GET_PATHS:
        guarded.get(path)
    after = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert before == after  # reads never create, change or delete a file


def test_secrets_dropped_in_every_allowed_folder_never_appear_in_any_answer(
    guarded: TestClient, repo: Path
) -> None:
    for rel in ("docs/research/.env", "experiments/.env", "configs/.env", "data/forward/.env"):
        write(repo, rel, "MT5_PASSWORD=hunter2\nTOKEN=zzz-secret\n")
    write(repo, "docs/research/key.pem", "-----BEGIN PRIVATE KEY-----")
    for path in GET_PATHS:
        text = guarded.get(path).text
        assert "hunter2" not in text
        assert "zzz-secret" not in text
        assert "PRIVATE KEY" not in text


@pytest.mark.parametrize("path", GET_PATHS)
def test_hostile_hosts_are_refused_even_without_the_control_plane(
    tmp_path: Path, repo: Path, path: str
) -> None:
    client = TestClient(create_app(_ctx(tmp_path, research=True)), base_url=BASE)
    assert client.get(path, headers={"host": "evil.example"}).status_code == 403
    assert client.get(path).status_code == 200
