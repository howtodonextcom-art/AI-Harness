"""``/control`` over HTTP: Host, token, Origin and Content-Type checks, route table, secret scan."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.unit.api.test_api import PROP
from tests.unit.control.fakes import FAKE_TRADE_PASSWORD, TOKEN, Rig, demo_terminal
from xau_edge.api.app import ALLOWED_ORIGINS, create_app
from xau_edge.api.service import ApiContext
from xau_edge.control.runtime_mode import read_runtime_mode
from xau_edge.control.security import TOKEN_HEADER, check_token, write_token
from xau_edge.experiments.registry import ExperimentRegistry

PORT = 8000
BASE = f"http://127.0.0.1:{PORT}"
ORIGIN = ALLOWED_ORIGINS[0]
FULL_LOGIN = "12345678"


def _app(tmp_path: Path, rig: Rig | None) -> TestClient:
    ctx = ApiContext(
        load_frames=lambda: (_ for _ in ()).throw(RuntimeError("no data in this test")),
        registry=ExperimentRegistry(tmp_path / "runs"),
        prop=PROP,
        models_dir=tmp_path / "models",
        control=rig.service if rig else None,
        control_port=PORT,
    )
    return TestClient(create_app(ctx), base_url=BASE)


def _headers(**over: str) -> dict[str, str]:
    base = {
        TOKEN_HEADER: TOKEN,
        "Origin": ORIGIN,
        "Content-Type": "application/json",
        "Idempotency-Key": "abcdef123456",
    }
    base.update(over)
    return {k: v for k, v in base.items() if v != ""}


@pytest.fixture
def rig(tmp_path: Path) -> Rig:
    return Rig(tmp_path)


@pytest.fixture
def client(tmp_path: Path, rig: Rig) -> TestClient:
    return _app(tmp_path, rig)


def _post(client: TestClient, path: str, body: Any, **headers: str) -> Any:
    import json  # noqa: PLC0415

    return client.post(path, content=json.dumps(body), headers=_headers(**headers))


def test_the_control_plane_is_absent_unless_enabled(tmp_path: Path) -> None:
    c = _app(tmp_path, None)
    paths = {getattr(r, "path", "") for r in c.app.routes}  # type: ignore[attr-defined]
    assert not any(p.startswith("/control") for p in paths)
    assert c.get("/control/status", headers=_headers()).status_code == 404


def test_every_control_request_needs_the_token(client: TestClient) -> None:
    for path in ("/control/status", "/control/preflight", "/control/jobs", "/control/journal"):
        assert client.get(path).status_code == 403
        assert client.get(path, headers={TOKEN_HEADER: "wrong"}).status_code == 403
    r = _post(client, "/control/flatten", {"confirm": "FLATTEN"}, **{TOKEN_HEADER: ""})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "BAD_TOKEN"
    assert client.get("/control/status", headers={TOKEN_HEADER: TOKEN}).status_code == 200


def test_a_foreign_host_is_refused_even_with_the_token(tmp_path: Path, rig: Rig) -> None:
    for base in ("http://evil.example:8000", "http://127.0.0.1:9999", "http://localhost"):
        c = TestClient(_app(tmp_path, rig).app, base_url=base)
        r = c.get("/control/status", headers={TOKEN_HEADER: TOKEN})
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "BAD_HOST"
    ok = TestClient(_app(tmp_path, rig).app, base_url=f"http://localhost:{PORT}")
    assert ok.get("/control/status", headers={TOKEN_HEADER: TOKEN}).status_code == 200


def test_posts_need_an_allowed_origin(client: TestClient, rig: Rig) -> None:
    for origin in ("", "http://evil.example", "null", "http://localhost:3001"):
        r = _post(client, "/control/bot/start", {}, Origin=origin)
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "BAD_ORIGIN"
    assert rig.process.calls == []


def test_posts_need_a_json_content_type(client: TestClient, rig: Rig) -> None:
    for ctype in ("", "text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        r = _post(client, "/control/bot/start", {}, **{"Content-Type": ctype})
        assert r.status_code == 403
    assert rig.process.calls == []


def test_posts_need_an_idempotency_key(client: TestClient, rig: Rig) -> None:
    r = _post(client, "/control/bot/start", {}, **{"Idempotency-Key": ""})
    assert r.status_code == 400
    assert rig.process.calls == []


def test_a_good_start_request_returns_a_job(client: TestClient, rig: Rig) -> None:
    r = _post(client, "/control/bot/start", {})
    assert r.status_code == 202
    job = r.json()["job"]
    assert job["kind"] == "bot.start"
    assert client.get(f"/control/jobs/{job['id']}", headers=_headers()).json()["status"] in (
        "SUCCEEDED",
        "RUNNING",
    )
    again = _post(client, "/control/bot/start", {})
    assert again.json()["replayed"] is True
    assert rig.process.calls == ["start:DRY_RUN"]


@pytest.mark.parametrize("mode", ["FUNDED", "LIVE", "funded", "demo", "DRY-RUN", 1, None])
def test_no_route_accepts_a_mode_other_than_dry_run_or_demo(
    client: TestClient, rig: Rig, mode: Any
) -> None:
    r = _post(client, "/control/mode", {"mode": mode, "confirm": "DEMO"})
    assert r.status_code == 422
    assert read_runtime_mode(rig.paths.runtime_mode) is None


def test_bodies_never_accept_order_parameters(client: TestClient, rig: Rig) -> None:
    for body in (
        {"confirm": "SMOKE", "lots": 5},
        {"confirm": "SMOKE", "symbol": "EURUSD"},
        {"confirm": "SMOKE", "direction": -1},
    ):
        assert _post(client, "/control/smoke", body).status_code == 422
    assert _post(client, "/control/bot/start", {"mode": "DEMO"}).status_code == 422
    assert rig.term.sent == []


def test_wrong_confirmation_words_are_refused(client: TestClient, rig: Rig) -> None:
    assert _post(client, "/control/flatten", {"confirm": "yes"}).status_code == 400
    assert _post(client, "/control/smoke", {"confirm": "smoke"}).status_code == 400
    r = _post(client, "/control/mode", {"mode": "DEMO", "confirm": "ok"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "CONFIRMATION_MISMATCH"


def test_blocked_actions_answer_409_with_reasons(client: TestClient) -> None:
    r = _post(client, "/control/bot/stop", {})
    assert r.status_code == 409
    assert "BOT_NOT_RUNNING" in {b["code"] for b in r.json()["detail"]["blockers"]}


def test_rate_limited_smoke_answers_429(client: TestClient, rig: Rig) -> None:
    rig.limiter.record("smoke")
    from tests.unit.brokers.test_executor import T  # noqa: PLC0415
    from xau_edge.control.runtime_mode import RuntimeMode, write_runtime_mode  # noqa: PLC0415

    write_runtime_mode(rig.paths.runtime_mode, RuntimeMode.DEMO, T)
    r = _post(client, "/control/smoke", {"confirm": "SMOKE"})
    assert r.status_code == 429


def test_control_posts_are_rate_limited_overall(client: TestClient) -> None:
    codes = [
        _post(client, "/control/bot/stop", {}, **{"Idempotency-Key": f"key-{i:08d}"}).status_code
        for i in range(25)
    ]
    assert 429 in codes


def test_the_route_table_has_no_funded_or_live_route(client: TestClient) -> None:
    writes = {
        (m, route.path)
        for route in client.app.routes  # type: ignore[attr-defined]
        for m in getattr(route, "methods", set())
        if m not in {"GET", "HEAD", "OPTIONS"}
    }
    assert writes == {
        ("POST", "/paper/orders"),
        ("POST", "/control/bot/start"),
        ("POST", "/control/bot/stop"),
        ("POST", "/control/bot/restart"),
        ("POST", "/control/mode"),
        ("POST", "/control/smoke"),
        ("POST", "/control/flatten"),
    }
    paths = " ".join(getattr(r, "path", "") for r in client.app.routes)  # type: ignore[attr-defined]
    for word in ("funded", "live", "reset", "kill_switch", "env"):
        assert word not in paths.lower().replace("/journal", "")


def test_responses_hold_no_secret_full_account_or_path(tmp_path: Path) -> None:
    rig = Rig(
        tmp_path,
        terminal=demo_terminal(login=FULL_LOGIN),
        env={"XAU_EDGE_DEMO_ALLOWED_ACCOUNTS": FULL_LOGIN, "MT5_LOGIN": FULL_LOGIN},
    )
    client = _app(tmp_path, rig)
    bodies = [
        client.get("/control/preflight", headers=_headers()).text,
        client.get("/control/status", headers=_headers()).text,
        _post(client, "/control/bot/start", {}).text,
        client.get("/control/journal", headers=_headers()).text,
        client.get("/control/jobs", headers=_headers()).text,
    ]
    text = "\n".join(bodies)
    assert "***678" in text
    for secret in (FAKE_TRADE_PASSWORD, FULL_LOGIN, str(tmp_path), TOKEN, "Traceback"):
        assert secret not in text


def test_an_invalid_env_is_described_without_its_values(tmp_path: Path) -> None:
    rig = Rig(tmp_path, env={"XAU_EDGE_DEMO_MAGIC": "not-a-number-" + FAKE_TRADE_PASSWORD})
    body = _app(tmp_path, rig).get("/control/preflight", headers=_headers()).text
    assert FAKE_TRADE_PASSWORD not in body
    assert "env.settings" in body


def test_the_token_file_is_written_and_compared_in_constant_time(tmp_path: Path) -> None:
    path = tmp_path / "control_token"
    write_token(path, "abc" * 10)
    assert path.read_text("utf-8") == "abc" * 10
    assert check_token("abc" * 10, "abc" * 10)
    assert not check_token("abc" * 10, "abc" * 9)
    assert not check_token("", "")
    assert not check_token("abc", None)
