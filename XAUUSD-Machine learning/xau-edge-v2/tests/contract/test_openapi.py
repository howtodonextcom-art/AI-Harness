"""The OpenAPI document is the contract the web build generates its types from."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_only_known_endpoints_are_published_and_only_two_write(
    make_client: Callable[..., TestClient],
) -> None:
    spec = make_client().get("/api/v2/openapi.json").json()
    assert set(spec["paths"]) == {
        "/api/v2/health",
        "/api/v2/intelligence",
        "/api/v2/forward/summary",
        "/api/v2/human/decision",
        "/api/v2/human/decisions",
        "/api/v2/model",
        "/api/v2/state",
        "/api/v2/market/bars",
        "/api/v2/market/forming",
        "/api/v2/market/quote",
        "/api/v2/market/symbol",
        "/api/v2/market/ticks",
        "/api/v2/paper/summary",
        "/api/v2/paper/positions",
        "/api/v2/paper/journal",
        "/api/v2/paper/open-current",
        "/api/v2/paper/positions/{position_id}/close",
    }
    writes = {p for p, ops in spec["paths"].items() if set(ops) - {"get"}}
    assert writes == {
        "/api/v2/paper/open-current",
        "/api/v2/paper/positions/{position_id}/close",
        "/api/v2/human/decision",
    }
    assert all(
        set(spec["paths"][p]) == {"post"} for p in writes
    )  # PAPER writes only; no put/delete


def test_contract_cannot_express_a_live_mode(make_client: Callable[..., TestClient]) -> None:
    schemas = make_client().get("/api/v2/openapi.json").json()["components"]["schemas"]
    for name in ("StateSnapshot", "HealthResponse"):
        assert schemas[name]["properties"]["mode"]["const"] == "PAPER"
    assert "evidence" in schemas["StateSnapshot"]["required"]  # the label is never optional


def test_openapi_does_not_depend_on_whether_the_web_build_exists(
    make_client: Callable[..., TestClient], tmp_path: object
) -> None:
    with_dist = make_client().get("/api/v2/openapi.json").json()
    without = make_client(web_dist=tmp_path / "missing").get("/api/v2/openapi.json").json()  # type: ignore[operator]
    assert with_dist == without
