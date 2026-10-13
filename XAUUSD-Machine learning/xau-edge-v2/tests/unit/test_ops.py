"""Operational alerts, the Telegram notifier, verified backup mirrors and their health checks."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from xau_edge_v2.api import paper as paper_api
from xau_edge_v2.api.health import _backup_checks
from xau_edge_v2.ops.alerts import Alerter, TelegramNotifier, problems_from_checks
from xau_edge_v2.paper import backup as bk
from xau_edge_v2.paper.store import PaperStore

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=UTC)
SECRET = "123456:SECRET-TOKEN-VALUE"


class Recorder:
    """A Notifier that records messages and can be told to fail."""

    def __init__(self, ok: bool = True) -> None:
        self.ok, self.messages = ok, []
        self.last_error: str | None = None

    def send(self, text: str) -> bool:
        self.messages.append(text)
        self.last_error = None if self.ok else "boom"
        return self.ok


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


# ---- the state machine ----------------------------------------------------------------------------
def test_a_blip_that_clears_before_the_confirmation_is_never_reported() -> None:
    rec = Recorder()
    alerter = Alerter(rec, confirm_seconds=120, host="h")
    assert alerter.evaluate({"engine_loop": ("Vòng nền", "x")}, NOW) == []
    assert alerter.evaluate({"engine_loop": ("Vòng nền", "x")}, NOW + minutes(1)) == []
    assert alerter.evaluate({}, NOW + minutes(1.5)) == []  # cleared: silence, no recovery either
    assert rec.messages == [] and alerter.active == {}


def test_a_lasting_problem_is_reported_once_repeated_rarely_and_its_recovery_announced() -> None:
    rec = Recorder()
    alerter = Alerter(rec, confirm_seconds=120, renotify_seconds=3600, host="pc")
    problem = {"freshness": ("Độ mới dữ liệu", "nến M1 quá cũ")}
    assert alerter.evaluate(problem, NOW) == []
    sent = alerter.evaluate(problem, NOW + minutes(3))
    assert (
        len(sent) == 1
        and "Độ mới dữ liệu" in sent[0]
        and "nến M1 quá cũ" in sent[0]
        and "pc" in sent[0]
    )
    assert alerter.evaluate(problem, NOW + minutes(30)) == []  # not repeated every pass
    assert len(alerter.evaluate(problem, NOW + minutes(64))) == 1  # one reminder after the hour
    recovery = alerter.evaluate({}, NOW + minutes(70))
    assert len(recovery) == 1 and "ổn định lại sau 70 phút" in recovery[0]
    assert alerter.evaluate({}, NOW + minutes(80)) == []  # and only once
    assert alerter.sent == 3 and alerter.failed == 0 and alerter.last_sent_at == NOW + minutes(70)


def test_a_failed_send_is_not_counted_as_sent_and_is_retried_at_most_once_a_minute() -> None:
    rec = Recorder(ok=False)
    alerter = Alerter(rec, confirm_seconds=0)
    problem = {"paper_db": ("CSDL sổ PAPER", "hỏng")}
    assert alerter.evaluate(problem, NOW) == []
    assert alerter.evaluate(problem, NOW + timedelta(seconds=30)) == []  # too soon to retry
    assert len(rec.messages) == 1 and alerter.failed == 1 and alerter.last_error == "boom"
    rec.ok = True
    assert len(alerter.evaluate(problem, NOW + timedelta(seconds=61))) == 1  # delivered on retry
    assert alerter.sent == 1 and alerter.last_error is None
    assert alerter.evaluate({}, NOW + minutes(5))  # now it was reported, so recovery is announced


def test_without_a_channel_nothing_is_sent_and_the_gap_is_visible() -> None:
    alerter = Alerter(None, confirm_seconds=0)
    assert alerter.configured is False
    assert alerter.evaluate({"store": ("Kho dữ liệu", "mất")}, NOW + minutes(10)) == []
    assert alerter.sent == 0 and "store" in alerter.active  # still tracked for the health page
    assert alerter.startup(NOW) is False


def test_each_problem_is_tracked_separately() -> None:
    rec = Recorder()
    alerter = Alerter(rec, confirm_seconds=60)
    alerter.evaluate({"a": ("A", "1")}, NOW)
    alerter.evaluate({"a": ("A", "1"), "b": ("B", "2")}, NOW + minutes(2))  # A confirmed, B new
    assert [m for m in rec.messages if "· A:" in m] and not [m for m in rec.messages if "· B:" in m]
    alerter.evaluate({"b": ("B", "2")}, NOW + minutes(4))  # A recovered, B confirmed
    assert any("✅" in m and "· A:" in m for m in rec.messages)
    assert any("⚠" in m and "· B:" in m for m in rec.messages)


def test_messages_are_operational_only() -> None:
    rec = Recorder()
    alerter = Alerter(rec, confirm_seconds=0, host="pc")
    alerter.evaluate(
        {"engine_loop": ("Vòng nền PAPER", "engine không có lượt thành công nào trong 90s")}, NOW
    )
    alerter.startup(NOW)
    alerter.evaluate({}, NOW + minutes(2))
    text = " ".join(rec.messages)
    assert not re.search(
        r"\b(BUY|SELL|MUA|BÁN|PnL|bid|ask|lãi|lỗ)\b|\$\d|\d{4}\.\d{2}", text, re.IGNORECASE
    )


def test_only_alertable_unhealthy_checks_become_problems() -> None:
    rows = [
        ("store", "Kho", "OK", "ok"),
        ("engine_loop", "Vòng nền", "FAIL", "chết"),
        ("freshness", "Độ mới", "WARN", "cũ"),
        ("model", "Mô hình", "NOT_DEPLOYED", "đã loại"),
        ("backup_offdevice", "Ngoài thiết bị", "WARN", "chưa có"),  # a reminder, not a page
        ("alerts", "Telegram", "WARN", "chưa cấu hình"),  # the channel never pages about itself
        ("backup_mirror", "Bản sao", "WARN", "trễ"),
    ]
    assert problems_from_checks(rows) == {
        "engine_loop": ("Vòng nền", "chết"),
        "freshness": ("Độ mới", "cũ"),
        "backup_mirror": ("Bản sao", "trễ"),
    }


# ---- the Telegram notifier against a local fake server ------------------------------------------
class FakeTelegram:
    def __init__(self, reply: dict[str, Any], status: int = 200) -> None:
        self.requests: list[tuple[str, dict[str, Any]]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append((self.path, body))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(reply).encode())

            def log_message(self, *_: object) -> None:
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def test_the_notifier_posts_to_the_bot_api_and_reads_the_answer() -> None:
    fake = FakeTelegram({"ok": True, "result": {}})
    try:
        notifier = TelegramNotifier(SECRET, "42", api=fake.url)
        assert notifier.send("xin chào" + "x" * 5000) is True
        path, body = fake.requests[0]
        assert path == f"/bot{SECRET}/sendMessage" and body["chat_id"] == "42"
        assert body["disable_web_page_preview"] is True and len(body["text"]) <= 3500
        assert notifier.last_error is None
    finally:
        fake.close()


@pytest.mark.parametrize(
    ("reply", "status", "expected"),
    [
        ({"ok": False, "description": "chat not found"}, 200, "chat not found"),
        ({"ok": False}, 401, "HTTP 401"),
    ],
)
def test_the_notifier_reports_a_refusal_without_raising_or_leaking_the_token(
    reply: dict[str, Any], status: int, expected: str
) -> None:
    fake = FakeTelegram(reply, status)
    try:
        notifier = TelegramNotifier(SECRET, "42", api=fake.url)
        assert notifier.send("x") is False
        assert expected in (notifier.last_error or "") and SECRET not in (notifier.last_error or "")
    finally:
        fake.close()


def test_the_notifier_survives_an_unreachable_api() -> None:
    notifier = TelegramNotifier(SECRET, "42", api="http://127.0.0.1:9", timeout=1.0)
    assert notifier.send("x") is False
    assert notifier.last_error and SECRET not in notifier.last_error


# ---- verified mirrors ------------------------------------------------------------------------------
def make_backup(folder: Path, name: str = "paper-20261013-100000.sqlite3") -> Path:
    store = PaperStore(folder / "src.sqlite3")
    store.append_journal(NOW, "NOTE", None, {"a": 1})
    target = store.backup_to(folder / "backups" / name)
    store.close()
    return target


def test_a_mirror_copy_is_byte_identical_sound_and_rotated(tmp_path: Path) -> None:
    source = make_backup(tmp_path)
    mirror = tmp_path / "mirror"
    final = bk.copy_verified(source, mirror, keep=2)
    assert final.read_bytes() == source.read_bytes() and not list(mirror.glob("*.partial"))
    opened = PaperStore(final)
    assert opened.integrity() == []
    opened.close()
    for day in (14, 15, 16):
        newer = source.with_name(f"paper-202610{day}-100000.sqlite3")
        shutil.copyfile(source, newer)
        bk.copy_verified(newer, mirror, keep=2)
    assert [p.name for p in sorted(mirror.glob("paper-*.sqlite3"))] == [
        "paper-20261015-100000.sqlite3",
        "paper-20261016-100000.sqlite3",
    ]


def test_a_copy_that_differs_from_the_source_is_rejected_and_leaves_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_backup(tmp_path)
    real = shutil.copyfile

    def truncating(src: Path, dst: Path) -> Path:
        real(src, dst)
        Path(dst).write_bytes(Path(dst).read_bytes()[:-100])  # a half-written copy
        return Path(dst)

    monkeypatch.setattr(bk.shutil, "copyfile", truncating)
    state = bk.MirrorState(path=tmp_path / "mirror", offdevice=False)
    assert bk.sync_mirror(state, source, 3, NOW) is False
    assert "differs" in (state.last_error or "") and state.last_ok is None
    assert list((tmp_path / "mirror").glob("*")) == []  # neither a final nor a partial file


def test_an_unreachable_mirror_is_recorded_not_raised(tmp_path: Path) -> None:
    source = make_backup(tmp_path)
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    state = bk.MirrorState(
        path=blocker / "sub", offdevice=False
    )  # a directory cannot be made there
    assert bk.sync_mirror(state, source, 3, NOW) is False
    assert state.last_error and state.last_ok is None and state.last_attempt == NOW


def test_the_engine_mirrors_the_daily_backup_and_catches_up_after_an_outage(
    make_client, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    mirror = tmp_path / "mirror"
    ctx = make_client(backup_mirrors=[mirror]).app.state.ctx
    status = paper_api.engine_status(ctx)
    blocker = tmp_path / "mirror"
    blocker.write_text("not a directory")  # the mirror is unavailable at backup time
    first = paper_api.maybe_backup(ctx, NOW)
    assert first is not None and status.mirrors[0].last_ok is None and status.mirrors[0].last_error
    blocker.unlink()  # the drive is back
    paper_api.maybe_backup(ctx, NOW + timedelta(seconds=100))  # too soon after the failed attempt
    assert status.mirrors[0].last_ok is None
    paper_api.maybe_backup(
        ctx, NOW + timedelta(seconds=400)
    )  # same day: no new backup, but it catches up
    assert status.mirrors[0].last_ok is not None and status.mirrors[0].last_file == first.name
    assert (mirror / first.name).read_bytes() == first.read_bytes()


# ---- health -----------------------------------------------------------------------------------------
def checks(ctx: Any, now: datetime) -> dict[str, tuple[str, str]]:
    return {c.id: (c.state, c.detail) for c in _backup_checks(ctx, now)}


def test_health_says_plainly_when_no_off_device_copy_exists(make_client) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client().app.state.ctx
    got = checks(ctx, NOW)
    assert got["backup_mirror"][0] == "WARN" and "chưa cấu hình" in got["backup_mirror"][1]
    state, detail = got["backup_offdevice"]
    assert state == "WARN" and "CHƯA CÓ" in detail and "cùng một ổ vật lý" in detail
    assert got["alerts"][0] == "WARN" and "CHƯA cấu hình" in got["alerts"][1]


def test_health_reflects_mirrors_freshness_and_the_alert_channel(
    make_client, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client(
        backup_mirrors=[tmp_path / "m"], backup_offdevice_dir=tmp_path / "off"
    ).app.state.ctx
    status = paper_api.engine_status(ctx)
    assert [m.offdevice for m in status.mirrors] == [False, True]
    assert checks(ctx, NOW)["backup_mirror"][0] == "WARN"  # never mirrored yet
    for m in status.mirrors:
        m.last_ok = NOW - timedelta(hours=2)
    got = checks(ctx, NOW)
    assert got["backup_mirror"][0] == "OK" and got["backup_offdevice"][0] == "OK"
    assert "CHƯA CÓ" not in got["backup_offdevice"][1]
    status.mirrors[1].last_ok = NOW - timedelta(hours=30)
    status.mirrors[1].last_error = "PermissionError: denied"
    off_state, off_detail = checks(ctx, NOW)["backup_offdevice"]
    assert off_state == "WARN" and "PermissionError" in off_detail
    ctx.cache["alerter"] = Alerter(Recorder())
    assert checks(ctx, NOW)["alerts"][0] == "OK"
    ctx.cache["alerter"].last_error = "HTTP 401"
    ctx.cache["alerter"].failed = 2
    state, detail = checks(ctx, NOW)["alerts"]
    assert state == "WARN" and "HTTP 401" in detail


def test_the_startup_notice_is_rate_limited_and_survives_a_restart_loop(make_client) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client().app.state.ctx
    rec = Recorder()
    ctx.cache["alerter"] = Alerter(rec, host="pc")
    assert paper_api.startup_notice(ctx, NOW) is True
    assert paper_api.startup_notice(ctx, NOW + minutes(5)) is False  # a crash loop stays quiet
    assert paper_api.startup_notice(ctx, NOW + minutes(31)) is True
    assert len(rec.messages) == 2 and "khởi động" in rec.messages[0]
    ctx.cache["alerter"] = Alerter(None)
    assert paper_api.startup_notice(ctx, NOW + minutes(90)) is False  # no channel, nothing to send


def test_an_alerting_failure_never_counts_against_the_engine(
    make_client, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    ctx = make_client().app.state.ctx

    def boom(_c: object, _n: object = None) -> list[str]:
        msg = "alert backend down"
        raise RuntimeError(msg)

    monkeypatch.setattr(paper_api, "evaluate_alerts", boom)
    monkeypatch.setattr(paper_api, "ALERT_PASS_SECONDS", 0.0)

    async def run() -> None:
        task = asyncio.create_task(paper_api.run_engine(ctx))
        await asyncio.sleep(0.4)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    status = paper_api.engine_status(ctx)
    assert status.errors == 0 and status.ticks >= 1 and status.last_ok is not None


def test_the_token_never_appears_in_settings_repr_logs_or_health(make_client, caplog) -> None:  # type: ignore[no-untyped-def]
    from pydantic import SecretStr  # noqa: PLC0415

    from xau_edge_v2.config import Settings  # noqa: PLC0415

    settings = Settings(telegram_bot_token=SecretStr(SECRET), telegram_chat_id="42")
    assert SECRET not in repr(settings) and SECRET not in str(settings.model_dump())
    client = make_client(telegram_bot_token=SECRET, telegram_chat_id="42", alerts_enabled=True)
    ctx = client.app.state.ctx
    alerter = paper_api.get_alerter(ctx)
    assert alerter.configured is True
    body = client.get("/api/v2/health").text + client.get("/api/v2/state").text
    assert SECRET not in body and SECRET not in caplog.text
    health = {c["id"]: c for c in client.get("/api/v2/health").json()["checks"]}
    assert health["alerts"]["state"] == "OK" and "đã cấu hình" in health["alerts"]["detail"]
