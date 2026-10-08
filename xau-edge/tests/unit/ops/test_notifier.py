"""Telegram notifier, dispatcher rules and fallback, all with a fake transport."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from xau_edge.execution.status import Alert, Severity
from xau_edge.ops.notifier import (
    AlertCode,
    AlertDispatcher,
    AlertEvent,
    NullNotifier,
    TelegramNotifier,
    build_dispatcher,
    build_notifier,
    redact,
)
from xau_edge.ops.settings import OpsSettings

pytestmark = pytest.mark.unit

TOKEN = "123456789:ABCdefGhIJKlmnoPQRstuVWxyz_0123456"
T0 = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)


class FakeTransport:
    def __init__(self, status: int = 200, error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.calls: list[tuple[str, Mapping[str, Any], float]] = []

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> int:
        self.calls.append((url, payload, timeout))
        if self.error:
            raise self.error
        return self.status


class Clock:
    def __init__(self) -> None:
        self.now = T0

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: float) -> None:
        self.now += timedelta(**kw)


def event(code: str = "STALE_DATA", severity: Severity = "warning") -> AlertEvent:
    return AlertEvent(code=code, severity=severity, message="m", at=T0)


def test_telegram_posts_to_send_message() -> None:
    tr = FakeTransport()
    n = TelegramNotifier(TOKEN, "42", transport=tr, timeout=3.0)
    assert n.notify(event(AlertCode.KILL_SWITCH_TRIPPED, "critical"))
    url, payload, timeout = tr.calls[0]
    assert url.endswith(f"/bot{TOKEN}/sendMessage")
    assert payload["chat_id"] == "42"
    assert "KILL_SWITCH_TRIPPED" in payload["text"]
    assert timeout == 3.0


def test_network_error_never_raises_and_redacts_token() -> None:
    tr = FakeTransport(error=OSError(f"cannot reach https://x/bot{TOKEN}/sendMessage"))
    n = TelegramNotifier(TOKEN, "42", transport=tr)
    assert n.notify(event()) is False
    assert n.last_error is not None
    assert TOKEN not in n.last_error
    assert TOKEN not in repr(n)


def test_http_error_status_is_a_failure() -> None:
    n = TelegramNotifier(TOKEN, "42", transport=FakeTransport(status=401))
    assert n.notify(event()) is False
    assert n.last_error == "HTTP 401"


def test_redact_removes_token_shaped_text_even_if_unknown() -> None:
    assert TOKEN not in redact(f"boom {TOKEN} end")
    assert "sekret" not in redact("a sekret b", "sekret")


def test_from_health_alert() -> None:
    e = AlertEvent.from_alert(Alert("HEARTBEAT_STALE", "critical", "x"), at=T0)
    assert (e.code, e.severity) == ("HEARTBEAT_STALE", "critical")


def make(tmp_path: Path, tr: FakeTransport, clock: Clock, **kw: Any) -> AlertDispatcher:
    return AlertDispatcher(
        TelegramNotifier(TOKEN, "42", transport=tr), tmp_path / "alerts.jsonl", clock=clock, **kw
    )


def test_duplicate_within_interval_is_suppressed_then_resent(tmp_path: Path) -> None:
    tr, clock = FakeTransport(), Clock()
    d = make(tmp_path, tr, clock, min_interval=timedelta(minutes=15))
    assert d.dispatch(event()).sent
    clock.advance(minutes=5)
    r = d.dispatch(event())
    assert r.suppressed
    assert not r.sent
    clock.advance(minutes=11)
    assert d.dispatch(event()).sent
    assert len(tr.calls) == 2


def test_critical_resent_only_after_repeat_interval(tmp_path: Path) -> None:
    tr, clock = FakeTransport(), Clock()
    d = make(
        tmp_path,
        tr,
        clock,
        min_interval=timedelta(minutes=5),
        critical_repeat=timedelta(minutes=30),
    )
    crit = event("KILL_SWITCH_TRIPPED", "critical")
    assert d.dispatch(crit).sent
    clock.advance(minutes=29)
    assert d.dispatch(crit).suppressed
    clock.advance(minutes=1)
    assert d.dispatch(crit).sent


def test_escalation_is_sent_immediately(tmp_path: Path) -> None:
    tr, clock = FakeTransport(), Clock()
    d = make(tmp_path, tr, clock)
    assert d.dispatch(event("STALE_DATA", "warning")).sent
    assert d.dispatch(event("STALE_DATA", "critical")).sent


def test_resolve_allows_immediate_resend(tmp_path: Path) -> None:
    tr, clock = FakeTransport(), Clock()
    d = make(tmp_path, tr, clock)
    d.dispatch(event())
    d.resolve("STALE_DATA")
    assert d.dispatch(event()).sent


def test_hourly_cap_applies_to_non_critical_only(tmp_path: Path) -> None:
    tr, clock = FakeTransport(), Clock()
    d = make(tmp_path, tr, clock, max_per_hour=2)
    assert d.dispatch(event("A")).sent
    assert d.dispatch(event("B")).sent
    assert d.dispatch(event("C")).reason == "hourly rate limit"
    assert d.dispatch(event("D", "critical")).sent
    clock.advance(minutes=61)
    assert d.dispatch(event("C")).sent


def test_failure_writes_fallback_file_without_token(tmp_path: Path) -> None:
    tr, clock = FakeTransport(error=OSError(f"bot{TOKEN}")), Clock()
    d = make(tmp_path, tr, clock)
    r = d.dispatch(event(AlertCode.STALE_DATA, "warning"))
    assert r.fallback_written
    assert not r.sent
    text = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8")
    assert TOKEN not in text
    rec = json.loads(text.splitlines()[0])
    assert rec["alerts"][0]["code"] == "STALE_DATA"
    assert rec["delivered"] is False
    # retry is throttled: the dead network does not flood the file
    assert d.dispatch(event(AlertCode.STALE_DATA, "warning")).suppressed
    assert len((tmp_path / "alerts.jsonl").read_text(encoding="utf-8").splitlines()) == 1


def test_unwritable_fallback_does_not_raise(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    d = AlertDispatcher(NullNotifier(), blocker / "sub" / "alerts.jsonl", clock=Clock())
    r = d.dispatch(event())
    assert not r.sent
    assert not r.fallback_written


def test_notifier_raising_unexpectedly_is_contained(tmp_path: Path) -> None:
    class Bad:
        def notify(self, event: AlertEvent) -> bool:
            raise RuntimeError("boom")

    d = AlertDispatcher(Bad(), tmp_path / "a.jsonl", clock=Clock())
    assert d.dispatch(event()).reason == "dispatcher error"


def test_build_from_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAU_EDGE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("XAU_EDGE_TELEGRAM_CHAT_ID", raising=False)
    unset = OpsSettings(_env_file=None)
    assert not unset.telegram_configured
    assert isinstance(build_notifier(unset), NullNotifier)
    cfg = OpsSettings.model_validate({"telegram_bot_token": TOKEN, "telegram_chat_id": "42"})
    assert cfg.telegram_configured
    assert TOKEN not in repr(cfg)
    assert isinstance(build_notifier(cfg), TelegramNotifier)
    assert isinstance(build_dispatcher(cfg, fallback_path=tmp_path / "a.jsonl"), AlertDispatcher)
