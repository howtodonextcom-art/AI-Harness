"""Reliability of the paper book: integrity, backups, a killed process, the engine and its watchdog."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.unit.test_core import CTX, buy_state
from xau_edge_v2.api import paper as paper_api
from xau_edge_v2.api.health import _paper_checks
from xau_edge_v2.core.decision import decide
from xau_edge_v2.domain.contract import StoreStatus, Timeframe, TimeframeFreshness
from xau_edge_v2.domain.market import MarketStatus
from xau_edge_v2.paper.store import PaperStore

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 3, 3, 10, 0, 20, tzinfo=UTC)


def position_row(setup: str = "s1") -> dict[str, object]:
    return {
        "id": f"id-{setup}", "setup_id": setup, "decision_id": "d1", "side": "BUY", "lots": 0.1,
        "entry": 2000.0, "quote_entry": 1999.97, "stop_loss": 1995.0, "take_profit": 2010.0,
        "take_profit_2": None, "net_rr": 1.9, "risk_amount": 50.0, "risk_pct": 0.25,
        "tick_size": 0.01, "tick_value": 1.0, "point": 0.01, "contract_size": 100.0,
        "session": "LONDON", "source": "AUTO", "opened_at": NOW.isoformat(),
        "last_bar_us": 0, "status": "OPEN",
    }  # fmt: skip


# ---- integrity and backups ------------------------------------------------------------------------
def test_a_healthy_database_reports_no_problem(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "p.sqlite3")
    assert store.insert_position(position_row(), {"x": 1})
    assert store.integrity() == []


def test_a_backup_is_a_consistent_copy_that_can_be_restored(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "p.sqlite3")
    assert store.insert_position(position_row("a"), {"x": 1})
    assert store.insert_position(position_row("b"), {"x": 2})
    copy = store.backup_to(tmp_path / "backups" / "p-copy.sqlite3")
    store.append_journal(NOW, "NOTE", None, {"after": "the backup"})  # the live file moves on
    restored = PaperStore(copy)
    assert restored.integrity() == []
    assert {p["setup_id"] for p in restored.positions()} == {"a", "b"}
    assert [j.kind for j in restored.journal()] == ["OPENED", "OPENED"]  # not the later note
    assert len(store.journal()) == 3


def test_a_corrupted_file_is_detected_not_trusted(tmp_path: Path) -> None:
    path = tmp_path / "p.sqlite3"
    store = PaperStore(path)
    for i in range(30):
        assert store.insert_position(position_row(f"s{i}"), {"i": i})
    store.close()
    data = bytearray(path.read_bytes())
    for offset in range(4096 * 2, 4096 * 2 + 200):  # damage a data page
        data[offset] ^= 0xFF
    broken = tmp_path / "broken.sqlite3"
    broken.write_bytes(bytes(data))
    try:
        problems = PaperStore(broken).integrity()
    except Exception as exc:  # SQLite may refuse to open it at all: that is detection too
        problems = [str(exc)]
    assert problems, "a damaged database must never look healthy"


# ---- a killed process -----------------------------------------------------------------------------
def run_child(code: str) -> int:
    """Run a script in a fresh interpreter; the exit code is what the test reads."""
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode not in (0, 9):
        raise AssertionError(result.stderr[-800:])  # a crash for another reason is a test failure
    return result.returncode


CHILD = """
import os, sys
sys.path.insert(0, {root!r})
from datetime import datetime, UTC
import json
from pathlib import Path
ROW = json.loads({row!r})
position_row = lambda: dict(ROW)
from xau_edge_v2.paper.store import PaperStore
store = PaperStore(Path({path!r}))
{body}
"""


def test_a_process_killed_inside_a_transaction_leaves_nothing_behind(tmp_path: Path) -> None:
    path = tmp_path / "p.sqlite3"
    PaperStore(path).close()  # the schema exists
    body = """
db = store._db
db.execute("BEGIN IMMEDIATE")
cols = ", ".join(position_row())
db.execute(f"INSERT INTO positions ({cols}) VALUES ({', '.join('?' for _ in position_row())})", tuple(position_row().values()))
db.execute("INSERT INTO journal (ts, kind, position_id, detail) VALUES (?, ?, ?, ?)", ("t", "OPENED", "id-s1", "{}"))
os._exit(9)  # the machine loses power in the middle of the write
"""
    code = run_child(
        CHILD.format(root=str(ROOT), path=str(path), body=body, row=json.dumps(position_row()))
    )
    assert code == 9
    reopened = PaperStore(path)
    assert reopened.integrity() == []
    assert reopened.positions() == [] and reopened.journal() == []  # neither half survived


def test_a_process_killed_right_after_a_commit_keeps_both_halves(tmp_path: Path) -> None:
    path = tmp_path / "p.sqlite3"
    body = """
assert store.insert_position(position_row(), {"x": 1})
os._exit(9)  # killed immediately after the commit returned
"""
    assert (
        run_child(
            CHILD.format(root=str(ROOT), path=str(path), body=body, row=json.dumps(position_row()))
        )
        == 9
    )
    reopened = PaperStore(path)
    assert reopened.integrity() == []
    assert len(reopened.positions()) == 1 and [j.kind for j in reopened.journal()] == ["OPENED"]


# ---- decision log and the engine ------------------------------------------------------------------
def test_the_decision_log_takes_one_row_per_bar(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "p.sqlite3")
    base = {
        "logged_at": "t", "action": "WAIT", "readiness_level": 1, "bias": "NEUTRAL", "refusals": "[]",
        "price": 1.0, "spread_points": 2.0, "atr_m15": 1.0, "market_status": "OPEN",
        "data_quality": "OK", "decision_id": "d", "strategy_version": "1.1.0", "setup_id": None,
    }  # fmt: skip
    assert store.log_decision({"bar_open_us": 100, **base}) is True
    assert (
        store.log_decision({"bar_open_us": 100, **base, "action": "BUY"}) is False
    )  # first one wins
    assert store.log_decision({"bar_open_us": 400, **base}) is True
    assert store.last_logged_bar() == 400 and [r["action"] for r in store.decision_rows()] == [
        "WAIT",
        "WAIT",
    ]


def test_the_engine_logs_each_new_closed_m5_bar_once(
    make_client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    client = make_client()
    ctx = client.app.state.ctx
    decision = decide(buy_state(m5_momentum="FLAT"), CTX)
    monkeypatch.setattr("xau_edge_v2.api.paper.live_decision", lambda _c: decision)
    assert paper_api.log_forward(ctx, NOW) is True
    assert paper_api.log_forward(ctx, NOW + timedelta(seconds=3)) is False  # same bar: nothing new
    rows = ctx.desk.store.decision_rows()
    assert (
        len(rows) == 1
        and rows[0]["action"] == "WAIT"
        and json.loads(rows[0]["refusals"]) == ["NO_TRIGGER"]
    )
    assert rows[0]["strategy_version"] == "1.1.0" and rows[0]["readiness_level"] == 3
    monkeypatch.setattr("xau_edge_v2.api.paper.live_decision", lambda _c: None)
    assert paper_api.log_forward(ctx, NOW) is False  # no decision, no row (never invented)


def test_engine_tick_records_status_and_survives_an_error(
    make_client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client().app.state.ctx

    def boom(_c: object, _n: object = None) -> list[str]:
        msg = "synthetic failure"
        raise RuntimeError(msg)

    status = paper_api.engine_status(ctx)
    assert status.ticks == 0 and status.errors == 0 and status.last_ok is None
    monkeypatch.setattr(paper_api, "engine_tick", boom)
    import asyncio  # noqa: PLC0415

    async def one_pass() -> None:
        task = asyncio.create_task(paper_api.run_engine(ctx))
        await asyncio.sleep(0.3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(one_pass())
    assert (
        status.errors >= 1
        and status.last_error is not None
        and "synthetic failure" in status.last_error
    )
    assert status.last_ok is None  # a failed pass is never reported as a success


def test_a_daily_backup_is_taken_once_per_day_and_old_ones_are_rotated(
    make_client, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client(backup_keep=2).app.state.ctx
    first = paper_api.maybe_backup(ctx, NOW)
    assert first is not None and first.exists()
    assert paper_api.maybe_backup(ctx, NOW + timedelta(hours=3)) is None  # same UTC day
    for day in (1, 2, 3):
        assert paper_api.maybe_backup(ctx, NOW + timedelta(days=day)) is not None
    kept = sorted((ctx.settings.paper_db.parent / "backups").glob("paper-*.sqlite3"))
    assert len(kept) == 2 and kept[-1].name.startswith("paper-20260306")
    assert PaperStore(kept[-1]).integrity() == []


# ---- the watchdog ---------------------------------------------------------------------------------
def fake_store(m1_state: str) -> StoreStatus:
    rows = tuple(
        TimeframeFreshness(
            timeframe=tf,
            latest_bar_open=NOW,
            age_seconds=1.0,
            state=m1_state if tf is Timeframe.M1 else "FRESH",
            files=1,
        )  # type: ignore[arg-type]
        for tf in Timeframe
    )
    return StoreStatus(
        root="x",
        reachable=True,
        market_status=MarketStatus.OPEN,
        timeframes=rows,
        disk_free_gb=50.0,
    )


def checks(ctx: object, store: StoreStatus, now: datetime) -> dict[str, tuple[str, str]]:
    return {c.id: (c.state, c.detail) for c in _paper_checks(ctx, store, now)}  # type: ignore[arg-type]


def test_the_watchdog_distinguishes_ok_stale_failing_and_disabled(make_client) -> None:  # type: ignore[no-untyped-def]
    live = make_client(engine_enabled=True, paper_poll_seconds=3.0).app.state.ctx
    status = paper_api.engine_status(live)
    status.started = NOW - timedelta(seconds=10)
    assert checks(live, fake_store("FRESH"), NOW)["engine_loop"][0] == "OK"  # just started
    status.started = NOW - timedelta(minutes=5)
    assert (
        checks(live, fake_store("FRESH"), NOW)["engine_loop"][0] == "FAIL"
    )  # never completed a pass
    status.last_ok = NOW - timedelta(seconds=4)
    status.ticks = 10
    assert checks(live, fake_store("FRESH"), NOW)["engine_loop"][0] == "OK"
    status.last_ok = NOW - timedelta(minutes=2)
    state, detail = checks(live, fake_store("FRESH"), NOW)["engine_loop"]
    assert state == "WARN" and "không có lượt thành công" in detail
    status.last_ok = NOW - timedelta(seconds=2)
    status.last_error, status.last_error_at = "RuntimeError: x", NOW - timedelta(seconds=5)
    assert checks(live, fake_store("FRESH"), NOW)["engine_loop"][0] == "WARN"
    off = make_client(engine_enabled=False).app.state.ctx
    assert checks(off, fake_store("FRESH"), NOW)["engine_loop"][0] == "WARN"


def test_integrity_problems_and_unmanaged_positions_are_visible(make_client) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client().app.state.ctx
    assert checks(ctx, fake_store("FRESH"), NOW)["paper_db"][0] == "OK"
    paper_api.engine_status(ctx).integrity = ["row 7 missing from index"]
    assert checks(ctx, fake_store("FRESH"), NOW)["paper_db"] == ("FAIL", "row 7 missing from index")
    assert ctx.desk.store.insert_position(position_row(), {"x": 1})
    state, detail = checks(ctx, fake_store("STALE"), NOW)["paper"]
    assert state == "WARN" and "1 lệnh đang mở" in detail and "M1 cũ" in detail
    assert checks(ctx, fake_store("FRESH"), NOW)["paper"][0] == "OK"
