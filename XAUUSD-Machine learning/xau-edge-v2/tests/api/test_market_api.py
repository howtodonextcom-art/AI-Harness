from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
from fastapi.testclient import TestClient

from tests.conftest import write_live, write_series
from xau_edge_v2.domain.contract import Timeframe

Make = Callable[..., TestClient]
START = datetime(2026, 1, 28, tzinfo=UTC)
COUNT = 1200


def _client(make: Make, tmp_path: Path) -> tuple[TestClient, list[datetime]]:
    root = tmp_path / "series"
    times = write_series(root, Timeframe.H1, START, COUNT, step_minutes=60)
    write_live(root)
    return make(data_root=root), times


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _times(body: dict[str, object]) -> list[str]:
    return [b["time"] for b in body["bars"]]  # type: ignore[index, union-attr]


def test_default_is_the_newest_bars_ascending_with_metadata(
    make_client: Make, tmp_path: Path
) -> None:
    client, times = _client(make_client, tmp_path)
    body = client.get("/api/v2/market/bars", params={"timeframe": "H1", "limit": 5}).json()
    assert len(body["bars"]) == 5
    assert body["bars"][-1]["time"].startswith(times[-1].strftime("%Y-%m-%dT%H:%M"))
    assert body["has_more_after"] is False and body["has_more_before"] is True
    assert body["oldest_available"].startswith(times[0].strftime("%Y-%m-%dT%H:%M"))
    assert body["newest_available"].startswith(times[-1].strftime("%Y-%m-%dT%H:%M"))
    assert body["data_version"].endswith("-3")  # Jan, Feb, Mar files
    assert all(b["is_closed"] for b in body["bars"])


def test_before_pages_back_without_gaps_or_duplicates(make_client: Make, tmp_path: Path) -> None:
    client, _ = _client(make_client, tmp_path)
    collected: list[str] = []
    cursor: str | None = None
    for _ in range(100):
        params: dict[str, object] = {"timeframe": "H1", "limit": 250}
        if cursor:
            params["before"] = cursor
        body = client.get("/api/v2/market/bars", params=params).json()
        page = _times(body)
        if not page:
            break
        collected = page + collected
        cursor = page[0]
        if not body["has_more_before"]:
            break
    assert len(collected) == COUNT and len(set(collected)) == COUNT
    assert collected == sorted(collected)


def test_from_to_window_is_half_open(make_client: Make, tmp_path: Path) -> None:
    client, times = _client(make_client, tmp_path)
    a, b = times[100], times[160]
    body = client.get(
        "/api/v2/market/bars",
        params={"timeframe": "H1", "from": _iso(a), "to": _iso(b), "limit": 1000},
    ).json()
    assert len(body["bars"]) == 60 and body["has_more_before"] and body["has_more_after"]
    assert _times(body)[0].startswith(a.strftime("%Y-%m-%dT%H:%M"))
    only_from = client.get(
        "/api/v2/market/bars", params={"timeframe": "H1", "from": _iso(a), "limit": 3}
    ).json()
    assert len(only_from["bars"]) == 3


def test_invalid_requests_are_structured_422s(make_client: Make, tmp_path: Path) -> None:
    client, times = _client(make_client, tmp_path)
    t = _iso(times[10])
    cases = [
        ({"before": "2026-02-01T00:00:00"}, "BARS_TZ_REQUIRED"),
        ({"before": t, "from": t}, "BARS_PARAMS_CONFLICT"),
        ({"from": _iso(times[20]), "to": _iso(times[10])}, "BARS_RANGE_INVALID"),
        ({"limit": 5001}, "REQUEST_INVALID"),
        ({"limit": 0}, "REQUEST_INVALID"),
        ({"timeframe": "H9"}, "REQUEST_INVALID"),
    ]
    for params, code in cases:
        r = client.get("/api/v2/market/bars", params={"timeframe": "H1", **params})
        assert r.status_code == 422 and r.json()["error_code"] == code, (params, r.text)


def test_unreachable_store_is_404_not_503(make_client: Make, tmp_path: Path) -> None:
    r = make_client(data_root=tmp_path / "nowhere").get(
        "/api/v2/market/bars", params={"timeframe": "M1"}
    )
    assert r.status_code == 404 and r.json()["error_code"] == "STORE_UNAVAILABLE"


def test_empty_window_has_no_bars_and_no_more(make_client: Make, tmp_path: Path) -> None:
    client, times = _client(make_client, tmp_path)
    far = _iso(times[-1] + timedelta(days=30))
    body = client.get("/api/v2/market/bars", params={"timeframe": "H1", "from": far}).json()
    assert (
        body["bars"] == [] and body["has_more_before"] is False and body["has_more_after"] is False
    )


def test_quote_and_symbol(make_client: Make, tmp_path: Path) -> None:
    client, _ = _client(make_client, tmp_path)
    quote = client.get("/api/v2/market/quote").json()
    assert quote["available"] is True and quote["bid"] == 4165.43 and quote["spread_points"] == 35.0
    assert quote["state"] in {"FRESH", "MARKET_CLOSED"}
    symbol = client.get("/api/v2/market/symbol").json()
    assert symbol["source"] == "BROKER_LIVE" and symbol["tick_value"] == 1.0
    assert symbol["contract_size"] == 100.0 and symbol["volume_step"] == 0.01


def test_symbol_and_quote_degrade_gracefully_without_the_live_file(
    make_client: Make, tmp_path: Path
) -> None:
    root = tmp_path / "nolive"
    write_series(root, Timeframe.H1, START, 10, step_minutes=60)
    client = make_client(data_root=root)
    q = client.get("/api/v2/market/quote")
    assert q.status_code == 200 and q.json()["state"] == "UNAVAILABLE"
    s = client.get("/api/v2/market/symbol")
    assert s.status_code == 404 and s.json()["error_code"] == "SYMBOL_SPEC_UNAVAILABLE"


def test_market_routes_are_read_only(make_client: Make) -> None:
    client = make_client()
    for path in ("/api/v2/market/bars", "/api/v2/market/quote", "/api/v2/market/symbol"):
        assert client.post(path).status_code == 405
        assert client.delete(path).status_code == 405


def _write_ticks(root: Path, count: int = 30) -> datetime:
    folder = root / "XAUUSD" / "ticks" / "2026"
    folder.mkdir(parents=True, exist_ok=True)
    base = datetime(2026, 10, 12, 10, 0, tzinfo=UTC)
    stamps = [base + timedelta(milliseconds=500 * i) for i in range(count)]
    pl.DataFrame(
        {
            "timestamp_msc": [int(t.timestamp() * 1000) for t in stamps],
            "timestamp": stamps,
            "bid": [4000.0 + i * 0.01 for i in range(count)],
            "ask": [4000.35 + i * 0.01 for i in range(count)],
            "last": [0.0] * count,
            "volume": [0] * count,
            "flags": [0] * count,
        }
    ).with_columns(
        pl.col("timestamp").dt.replace_time_zone("UTC").dt.cast_time_unit("ms")
    ).write_parquet(folder / "2026-10-12.parquet")
    return base


def test_ticks_half_open_ordered_and_truncation_is_explicit(
    make_client: Make, tmp_path: Path
) -> None:
    root = tmp_path / "t"
    base = _write_ticks(root)
    client = make_client(data_root=root)
    start, end = _iso(base), _iso(base + timedelta(seconds=15))
    body = client.get("/api/v2/market/ticks", params={"from": start, "to": end, "limit": 10}).json()
    assert body["count"] == 10 and body["has_more"] is True and body["limit"] == 10
    msc = [t["time_msc"] for t in body["ticks"]]
    assert msc == sorted(msc) and len(set(msc)) == 10
    assert body["ticks"][0]["ask"] > body["ticks"][0]["bid"]
    full = client.get("/api/v2/market/ticks", params={"from": start, "to": end}).json()
    assert full["count"] == 30 and full["has_more"] is False  # [from, to) over 30 ticks
    assert full["first_day"] == full["last_day"] == "2026-10-12"


def test_ticks_errors_are_json_with_codes(make_client: Make, tmp_path: Path) -> None:
    root = tmp_path / "t"
    _write_ticks(root)
    client = make_client(data_root=root)
    naive = client.get(
        "/api/v2/market/ticks", params={"from": "2026-10-12T10:00:00", "to": "2026-10-12T11:00:00"}
    )
    assert naive.status_code == 422 and naive.json()["error_code"] == "TICKS_TZ_REQUIRED"
    backwards = client.get(
        "/api/v2/market/ticks",
        params={"from": "2026-10-12T11:00:00Z", "to": "2026-10-12T10:00:00Z"},
    )
    assert backwards.status_code == 422 and backwards.json()["error_code"] == "TICKS_RANGE_INVALID"
    too_many = client.get(
        "/api/v2/market/ticks",
        params={"from": "2026-10-12T10:00:00Z", "to": "2026-10-12T11:00:00Z", "limit": 99999},
    )
    assert too_many.status_code == 422 and too_many.json()["error_code"] == "REQUEST_INVALID"
    empty = make_client(data_root=tmp_path / "none").get(
        "/api/v2/market/ticks",
        params={"from": "2026-10-12T10:00:00Z", "to": "2026-10-12T11:00:00Z"},
    )
    assert empty.status_code == 404 and empty.json()["error_code"] == "TICKS_UNAVAILABLE"
    assert client.post("/api/v2/market/ticks").status_code == 405
