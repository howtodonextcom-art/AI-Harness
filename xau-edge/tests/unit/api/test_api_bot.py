"""Bot endpoints: read-only, fail loud on unreadable files, never a green light by omission."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests.unit.api.test_api import PROP, frames  # noqa: F401 - fixture import
from xau_edge.api.app import create_app
from xau_edge.api.bot import BotContext
from xau_edge.api.service import ApiContext
from xau_edge.execution.reconcile import (
    BrokerAccount,
    BrokerPosition,
    BrokerSnapshot,
    ReconcileResult,
)
from xau_edge.execution.runner import CycleReport
from xau_edge.execution.state import ExecutionState
from xau_edge.execution.status import (
    BotStatus,
    StatusCycle,
    StatusPosition,
    StatusPropFacts,
    build_status,
    evaluate_health,
    read_status,
    write_status,
)
from xau_edge.experiments.registry import ExperimentRegistry
from xau_edge.signals.engine import MarketFrames

NOW = datetime(2026, 3, 4, 14, 0, tzinfo=UTC)


def _status(**over: object) -> BotStatus:
    base: dict[str, object] = {
        "updated_at": NOW,
        "mode": "dry-run",
        "symbol": "XAUUSD",
        "connected": True,
        "account_demo": True,
        "balance": 100_000.0,
        "equity": 100_050.0,
        "positions": [],
        "reconcile_clean": True,
        "reconcile_codes": [],
        "last_cycle": StatusCycle(
            decision_time=NOW.isoformat(),
            direction="WAIT",
            accepted=False,
            reasons=["NO_VALIDATED_EDGE"],
            data_age_minutes=3.0,
        ),
        "news_status": "unknown",
    }
    base.update(over)
    return BotStatus(**base)


def _ctx(tmp_path: Path, frames: MarketFrames, **kw: object) -> tuple[TestClient, BotContext]:  # noqa: F811
    bot = BotContext(
        state_path=tmp_path / "state.sqlite",
        status_path=tmp_path / "status.json",
        cycles_path=tmp_path / "cycles.jsonl",
        journal_path=tmp_path / "journal.jsonl",
    )
    clock: Callable[[], datetime] = lambda: NOW + timedelta(minutes=5)  # noqa: E731
    api = ApiContext(
        lambda: frames,
        ExperimentRegistry(tmp_path / "runs"),
        PROP,
        bot=bot,
        clock=clock,
        **kw,  # type: ignore[arg-type]
    )
    return TestClient(create_app(api)), bot


def test_without_a_bot_the_routes_say_unavailable(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    api = ApiContext(lambda: frames, ExperimentRegistry(tmp_path / "runs"), PROP)
    assert TestClient(create_app(api)).get("/bot/status").status_code == 503


def test_status_before_the_bot_has_run_is_not_healthy_by_omission(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, _ = _ctx(tmp_path, frames)
    body = client.get("/bot/status").json()
    assert body["live_trading"] is False
    assert body["status"] is None
    assert [a["code"] for a in body["alerts"]] == ["NO_STATUS"]
    assert body["kill_switch"]["known"] is False


def test_status_reflects_the_snapshot_and_the_kill_switch(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    write_status(bot.status_path, _status())
    state = ExecutionState(bot.state_path)
    body = client.get("/bot/status").json()
    assert body["healthy"] is True
    assert body["status"]["mode"] == "dry-run"
    assert body["kill_switch"] == {"tripped": False, "reason": "", "known": True}
    state.trip_kill_switch("manual")
    body = client.get("/bot/status").json()
    assert body["kill_switch"]["tripped"] is True
    assert body["healthy"] is False
    assert "KILL_SWITCH_TRIPPED" in [a["code"] for a in body["alerts"]]


def test_account_positions_and_reconciliation_views(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    assert client.get("/bot/account").json() == {"available": False}
    assert client.get("/bot/reconciliation").json() == {"available": False}
    assert client.get("/bot/positions").json() == {"positions": []}
    position = StatusPosition(
        ticket="1",
        symbol="XAUUSD",
        direction=1,
        lots=0.5,
        entry_price=2000.0,
        stop_loss=1990.0,
        take_profit=2010.0,
        opened_at=NOW,
        bot_owned=True,
    )
    write_status(
        bot.status_path,
        _status(positions=[position], reconcile_clean=False, reconcile_codes=["LOT_MISMATCH"]),
    )
    assert client.get("/bot/account").json()["balance"] == 100_000.0
    assert client.get("/bot/positions").json()["positions"][0]["ticket"] == "1"
    rec = client.get("/bot/reconciliation").json()
    assert rec["clean"] is False
    assert rec["codes"] == ["LOT_MISMATCH"]
    codes = [a["code"] for a in client.get("/bot/alerts").json()["alerts"]]
    assert "RECONCILE_DIRTY" in codes


def test_cycles_and_journal_are_tailed_and_bounded(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    lines = [json.dumps({"n": i}) for i in range(10)]
    bot.cycles_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bot.journal_path.write_text(json.dumps({"at": "x", "event": "a"}) + "\n", encoding="utf-8")
    assert [c["n"] for c in client.get("/bot/cycles", params={"limit": 3}).json()["cycles"]] == [
        7,
        8,
        9,
    ]
    assert client.get("/bot/journal").json()["events"][0]["event"] == "a"
    assert client.get("/bot/cycles", params={"limit": 0}).status_code == 422
    assert client.get("/bot/cycles", params={"limit": 501}).status_code == 422


@pytest.mark.parametrize("path", ["/bot/status", "/bot/cycles", "/bot/journal", "/bot/account"])
def test_unreadable_files_give_503_not_a_healthy_looking_answer(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
    path: str,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    bot.status_path.write_text("{not json", encoding="utf-8")
    bot.cycles_path.write_text("garbage\n", encoding="utf-8")
    bot.journal_path.write_text("garbage\n", encoding="utf-8")
    assert client.get(path).status_code == 503


def test_a_corrupt_state_file_gives_503(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    bot.state_path.write_bytes(b"junk" * 100)
    assert client.get("/bot/status").status_code == 503


def test_status_exposes_funded_mode_and_prop_facts(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    prop = StatusPropFacts(
        evidence_label="UNVALIDATED",
        strategy_id="baseline_b",
        rollout_tier=1,
        rollout_tier_name="micro",
        daily_floor_distance_pct=1.5,
        max_floor_distance_pct=8.0,
        requests_today=3,
        request_budget=50,
        trading_days=2,
        kill_switch_tripped=False,
        kill_switch_reason="",
    )
    write_status(bot.status_path, _status(mode="funded", account_demo=False, prop=prop))
    body = client.get("/bot/status").json()
    assert body["status"]["mode"] == "funded"
    assert body["status"]["prop"] == prop.model_dump(mode="json")
    assert "ACCOUNT_NOT_DEMO" not in [a["code"] for a in body["alerts"]]


def test_status_without_prop_facts_gets_the_defaults(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    write_status(bot.status_path, _status(mode="demo"))
    status = client.get("/bot/status").json()["status"]
    assert status["mode"] == "demo"
    assert status["prop"]["evidence_label"] == "NONE"
    assert status["prop"]["daily_floor_distance_pct"] is None


def test_risk_status_reports_the_persistent_kill_switch(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    state = ExecutionState(bot.state_path)
    body = client.get("/risk/status").json()
    assert body["kill_switch"] == {
        "source": "execution_state",
        "tripped": False,
        "reason": "",
        "known": True,
        "error": None,
    }
    assert body["paper_kill_switch"]["configured"] is False
    state.trip_kill_switch("daily floor breach")
    switch = client.get("/risk/status").json()["kill_switch"]
    assert switch["tripped"] is True
    assert switch["reason"] == "daily floor breach"


def test_risk_status_with_no_state_file_is_unknown_not_clear(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    switch = client.get("/risk/status").json()["kill_switch"]
    assert switch["tripped"] is None
    assert switch["known"] is False
    assert switch["error"]
    assert not bot.state_path.exists()  # reading never creates the database


def test_risk_status_with_a_corrupt_state_is_unknown_without_leaking_the_path(
    frames: MarketFrames,  # noqa: F811
    tmp_path: Path,
) -> None:
    client, bot = _ctx(tmp_path, frames)
    bot.state_path.write_bytes(b"junk" * 100)
    response = client.get("/risk/status")
    assert response.status_code == 200
    switch = response.json()["kill_switch"]
    assert switch["tripped"] is None
    assert switch["error"] == "the execution state is unreadable"
    assert bot.state_path.name not in response.text


def test_no_bot_route_accepts_a_write() -> None:
    api = ApiContext(
        lambda: (_ for _ in ()).throw(RuntimeError()),
        ExperimentRegistry(Path("nowhere")),
        PROP,
    )
    for route in create_app(api).routes:
        if isinstance(route, APIRoute) and route.path.startswith("/bot"):
            assert route.methods == {"GET"}


def test_health_rules(tmp_path: Path) -> None:
    now = NOW + timedelta(minutes=5)
    assert [a.code for a in evaluate_health(_status(), None, now)] == ["NEWS_UNKNOWN"]
    stale = evaluate_health(_status(), None, NOW + timedelta(hours=2))
    assert "HEARTBEAT_STALE" in [a.code for a in stale]
    bad = _status(connected=False, account_demo=False)
    codes = [a.code for a in evaluate_health(bad, None, now)]
    assert {"TERMINAL_DISCONNECTED", "ACCOUNT_NOT_DEMO"} <= set(codes)
    cycle = StatusCycle(
        decision_time=None,
        direction="WAIT",
        accepted=False,
        reasons=["DATA_STALE"],
        data_age_minutes=99.0,
    )
    stale_data = evaluate_health(_status(last_cycle=cycle), None, now)
    assert "DATA_STALE" in [a.code for a in stale_data]


def test_status_file_round_trip_and_corruption(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    assert read_status(path) is None
    write_status(path, _status())
    assert read_status(path) == _status()
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(ValueError, match="unreadable"):
        read_status(path)


def test_build_status_from_a_cycle() -> None:
    pos = BrokerPosition("9", "XAUUSD", 1, 0.5, 2000.0, 1990.0, 2010.0, 7, "c", NOW)
    snap = BrokerSnapshot(NOW, BrokerAccount("A", True, 1000.0, 1001.0), (pos,))
    report = CycleReport(
        NOW.isoformat(), NOW.isoformat(), "WAIT", "h", False, ("NEWS_UNKNOWN",), None, True, 2.0
    )
    status = build_status(
        NOW,
        mode="dry-run",
        symbol="XAUUSD",
        snapshot=snap,
        reconcile=ReconcileResult(True, ()),
        report=report,
        bot_tickets=frozenset({"9"}),
    )
    assert status.connected
    assert status.positions[0].bot_owned
    assert status.news_status == "unknown"
    assert "account_id" not in status.model_dump_json()
    offline = build_status(
        NOW, mode="dry-run", symbol="XAUUSD", snapshot=None, reconcile=None, report=None
    )
    assert offline.connected is False
    assert offline.balance is None


def _report(reasons: tuple[str, ...], *, skipped: bool = False) -> CycleReport:
    return CycleReport(
        NOW.isoformat(), NOW.isoformat(), "WAIT", "h", False, reasons, None, True, 2.0, skipped
    )


def test_news_is_only_clear_when_it_was_actually_evaluated() -> None:
    def news(report: CycleReport | None) -> str:
        built = build_status(
            NOW,
            mode="dry-run",
            symbol="XAUUSD",
            snapshot=None,
            reconcile=None,
            report=report,
        )
        return built.news_status

    assert news(None) == "unknown"
    assert news(_report(("NEWS_UNKNOWN",))) == "unknown"
    assert news(_report(("DATA_STALE",))) == "unknown"
    assert news(_report(("RECONCILE_LOT_MISMATCH",), skipped=True)) == "unknown"
    assert news(_report(("NO_VALIDATED_EDGE",))) == "clear"
    assert news(_report(("NEWS_RISK",))) == "risk"
