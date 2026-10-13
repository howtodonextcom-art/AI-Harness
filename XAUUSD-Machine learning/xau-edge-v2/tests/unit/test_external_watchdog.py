"""The external watchdog: what it calls a problem, when it speaks, and that it never leaks."""

from __future__ import annotations

import importlib.util
import json
import threading
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from tests.unit.test_ops import SECRET, FakeTelegram

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "external_watchdog", ROOT / "scripts" / "external_watchdog.py"
)
assert spec and spec.loader
wd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wd)

NOW = datetime(2026, 10, 13, 10, 0, tzinfo=UTC)


def serve(status: int, body: dict[str, Any]) -> tuple[HTTPServer, int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(body).encode())

        def log_message(self, *_: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


def health(status: str = "OK", **states: str) -> dict[str, Any]:
    checks = [{"id": k, "label": k, "state": v, "detail": f"{k} is {v}"} for k, v in states.items()]
    return {"status": status, "checks": checks}


@pytest.mark.parametrize(
    ("status", "body", "healthy", "needle"),
    [
        (200, health("OK", engine_loop="OK"), True, ""),
        (
            200,
            health("DEGRADED", model="NOT_DEPLOYED", engine_loop="OK"),
            True,
            "",
        ),  # expected, not a page
        (200, health("DOWN", store="FAIL"), False, "DOWN"),
        (200, health("DEGRADED", engine_loop="FAIL"), False, "vòng nền PAPER FAIL"),
        (200, health("DEGRADED", engine_loop="WARN"), False, "vòng nền PAPER WARN"),
        (500, {"error": "x"}, False, "HTTP 500"),
    ],
)
def test_what_counts_as_a_problem(
    status: int, body: dict[str, Any], healthy: bool, needle: str
) -> None:
    server, port = serve(status, body)
    try:
        ok, problem = wd.check_health(port, timeout=3)
    finally:
        server.shutdown()
        server.server_close()
    assert ok is healthy and needle in problem


def test_an_unreachable_service_is_a_problem() -> None:
    ok, problem = wd.check_health(9, timeout=1)
    assert ok is False and "không phản hồi" in problem


class Sink:
    def __init__(self, ok: bool = True) -> None:
        self.ok, self.texts = ok, []

    def __call__(self, text: str) -> bool:
        self.texts.append(text)
        return self.ok


def test_it_waits_for_two_failures_then_alerts_once_and_reminds_hourly() -> None:
    state: dict[str, object] = {}
    sink = Sink()
    assert (
        wd.step(state, False, "dịch vụ không phản hồi", NOW, sink, "pc") == []
    )  # first failure: wait
    sent = wd.step(state, False, "dịch vụ không phản hồi", NOW + timedelta(minutes=2), sink, "pc")
    assert len(sent) == 1 and "⛔" in sent[0] and "không phản hồi" in sent[0] and "pc" in sent[0]
    assert (
        wd.step(state, False, "x", NOW + timedelta(minutes=30), sink, "pc") == []
    )  # not every pass
    assert len(wd.step(state, False, "x", NOW + timedelta(minutes=63), sink, "pc")) == 1  # hourly
    assert len(sink.texts) == 2


def test_a_single_blip_is_forgotten_and_a_recovery_is_announced_only_after_an_alert() -> None:
    state: dict[str, object] = {}
    sink = Sink()
    wd.step(state, False, "x", NOW, sink, "pc")
    assert (
        wd.step(state, True, "", NOW + timedelta(minutes=2), sink, "pc") == [] and sink.texts == []
    )
    assert state == {"failures": 0}
    wd.step(state, False, "x", NOW + timedelta(minutes=4), sink, "pc")
    wd.step(state, False, "x", NOW + timedelta(minutes=6), sink, "pc")  # alerted
    rec = wd.step(state, True, "", NOW + timedelta(minutes=20), sink, "pc")
    assert len(rec) == 1 and "✅" in rec[0] and "16 phút" in rec[0]
    assert wd.step(state, True, "", NOW + timedelta(minutes=22), sink, "pc") == []


def test_a_failed_send_is_retried_and_a_missing_channel_postpones_the_alert() -> None:
    state: dict[str, object] = {}
    nobody = Sink(ok=False)  # the channel is down or not configured
    wd.step(state, False, "x", NOW, nobody, "pc")
    wd.step(state, False, "x", NOW + timedelta(minutes=2), nobody, "pc")
    assert "alerted_at" not in state  # nothing was delivered, so it is not "alerted"
    later = Sink()
    sent = wd.step(state, False, "x", NOW + timedelta(minutes=4), later, "pc")
    assert len(sent) == 1 and state["alerted_at"]  # delivered as soon as the channel works
    stuck = Sink(ok=False)
    assert wd.step(state, True, "", NOW + timedelta(minutes=10), stuck, "pc") == []
    assert state.get("alerted_at")  # the recovery could not be sent: it will be tried again
    assert len(wd.step(state, True, "", NOW + timedelta(minutes=12), Sink(), "pc")) == 1


def test_env_parsing_state_files_and_the_telegram_call(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        f'# c\nXAU_V2_TELEGRAM_BOT_TOKEN="{SECRET}"\nXAU_V2_TELEGRAM_CHAT_ID=42\n\nbad line\n',
        encoding="utf-8",
    )
    parsed = wd.read_env(env)
    assert (
        parsed["XAU_V2_TELEGRAM_BOT_TOKEN"] == SECRET and parsed["XAU_V2_TELEGRAM_CHAT_ID"] == "42"
    )
    assert wd.read_env(tmp_path / "missing") == {}
    state_file = tmp_path / "s" / "state.json"
    wd.save_state({"failures": 3}, state_file)
    assert wd.load_state(state_file) == {"failures": 3} and wd.load_state(tmp_path / "none") == {}
    fake = FakeTelegram({"ok": True})
    try:
        assert wd.send_telegram(SECRET, "42", "xin chào", api=fake.url) is True
        assert (
            fake.requests[0][0] == f"/bot{SECRET}/sendMessage"
            and fake.requests[0][1]["chat_id"] == "42"
        )
    finally:
        fake.close()
    assert wd.send_telegram(SECRET, "42", "x", api="http://127.0.0.1:9") is False


def test_its_messages_say_nothing_about_trading() -> None:
    state: dict[str, object] = {}
    sink = Sink()
    wd.step(state, False, "dịch vụ không phản hồi (URLError)", NOW, sink, "pc")
    wd.step(
        state, False, "dịch vụ không phản hồi (URLError)", NOW + timedelta(minutes=2), sink, "pc"
    )
    wd.step(state, True, "", NOW + timedelta(minutes=9), sink, "pc")
    text = " ".join(sink.texts)
    for banned in ("BUY", "SELL", "PnL", "bid", "ask", "$"):
        assert banned not in text
