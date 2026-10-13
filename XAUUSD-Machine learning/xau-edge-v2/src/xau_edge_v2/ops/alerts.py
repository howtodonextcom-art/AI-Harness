"""Operational alerts (service health only) with confirmation, cool-down and recovery notices.

This module knows nothing about trading: its messages carry check labels and details such as
"the engine has not completed a pass for 90 s". It never mentions a signal, a price or a PnL.

Rules (so a person is told what matters and not more):

* a problem must persist for ``confirm_seconds`` before it is reported (no alert on a blip);
* an active problem is repeated at most every ``renotify_seconds``;
* a reported problem that clears produces ONE recovery notice with its duration;
* a problem that cleared before it was ever reported produces nothing;
* a failed send is not counted as sent: it is retried (at most once a minute) and shown in /health.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

TELEGRAM_API = "https://api.telegram.org"
RETRY_SECONDS = 60.0
MAX_TEXT = 3500
ALERTABLE = frozenset(
    {"store", "freshness", "live", "disk", "engine_loop", "paper_db", "paper", "backup_mirror"}
)
"""Health checks that may raise an alert. Expected conditions (model not deployed, no off-device
copy yet, the alert channel itself) are shown on the page but never paged."""


class Notifier(Protocol):
    def send(self, text: str) -> bool: ...


@dataclass
class TelegramNotifier:
    """Plain HTTPS to the Bot API (stdlib). Never raises; never puts the token in an error."""

    token: str
    chat_id: str
    api: str = TELEGRAM_API
    timeout: float = 10.0
    last_error: str | None = None

    def send(self, text: str) -> bool:
        body = json.dumps(
            {"chat_id": self.chat_id, "text": text[:MAX_TEXT], "disable_web_page_preview": True}
        ).encode()
        request = urllib.request.Request(
            f"{self.api}/bot{self.token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                reply = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            self.last_error = f"HTTP {exc.code}"
            return False
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self.last_error = type(exc).__name__
            return False
        if reply.get("ok") is True:
            self.last_error = None
            return True
        self.last_error = f"telegram: {str(reply.get('description', 'not ok'))[:80]}"
        return False


@dataclass
class _Active:
    label: str
    detail: str
    since: datetime
    alerted_at: datetime | None = None
    last_attempt: datetime | None = None


@dataclass
class Alerter:
    notifier: Notifier | None
    confirm_seconds: float = 120.0
    renotify_seconds: float = 3600.0
    host: str = field(default_factory=socket.gethostname)
    active: dict[str, _Active] = field(default_factory=dict)
    sent: int = 0
    failed: int = 0
    last_sent_at: datetime | None = None
    last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self.notifier is not None

    def _send(self, text: str, now: datetime) -> bool:
        if self.notifier is None:
            return False
        ok = self.notifier.send(text)
        if ok:
            self.sent += 1
            self.last_sent_at = now
            self.last_error = None
        else:
            self.failed += 1
            self.last_error = getattr(self.notifier, "last_error", None) or "send failed"
        return ok

    def startup(self, now: datetime) -> bool:
        return self._send(
            f"XAU EDGE V2 đã khởi động trên {self.host} ({now:%Y-%m-%d %H:%M} UTC).", now
        )

    def evaluate(
        self, problems: dict[str, tuple[str, str]], now: datetime | None = None
    ) -> list[str]:
        """Feed the CURRENT problems (key -> (label, detail)); returns the messages sent now."""
        moment = now or datetime.now(UTC)
        out: list[str] = []
        for key, (label, detail) in problems.items():
            item = self.active.get(key)
            if item is None:
                item = self.active[key] = _Active(label, detail, moment)
            item.label, item.detail = label, detail
            if (moment - item.since).total_seconds() < self.confirm_seconds:
                continue
            due = item.alerted_at is None or (
                (moment - item.alerted_at).total_seconds() >= self.renotify_seconds
            )
            retry_ok = item.last_attempt is None or (
                (moment - item.last_attempt).total_seconds() >= RETRY_SECONDS
            )
            if due and retry_ok and self.notifier is not None:
                since = f"{item.since:%H:%M} UTC"
                text = f"⚠ XAU EDGE V2 · {label}: {detail} (từ {since}, máy {self.host})"
                item.last_attempt = moment
                if self._send(text, moment):
                    item.alerted_at = moment
                    out.append(text)
        for key in [k for k in self.active if k not in problems]:
            item = self.active.pop(key)
            if item.alerted_at is not None:
                minutes = (moment - item.since).total_seconds() / 60
                text = f"✅ XAU EDGE V2 · {item.label}: ổn định lại sau {minutes:.0f} phút"
                if self._send(text, moment):
                    out.append(text)
        return out


def problems_from_checks(checks: Sequence[tuple[str, str, str, str]]) -> dict[str, tuple[str, str]]:
    """``(id, label, state, detail)`` rows -> the alertable problems (WARN/FAIL of alertable ids)."""
    return {
        cid: (label, detail)
        for cid, label, state, detail in checks
        if cid in ALERTABLE and state in ("WARN", "FAIL")
    }
