"""Alert delivery: Telegram push, de-duplication, rate limiting and a file fallback.

Design rules:

* Sending an alert must NEVER raise into the trading loop (``Notifier.notify`` returns a bool).
* The bot token is never logged or written: every error text is passed through ``redact``.
* When the network fails the alert is appended to ``alerts.jsonl`` so it is not lost.
* No hard-coded credentials: ``build_notifier`` reads them from ``OpsSettings`` (environment/.env).
"""

from __future__ import annotations

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from xau_edge.execution.status import Alert, Severity
from xau_edge.observability import log_event
from xau_edge.ops.settings import OpsSettings

_LOG = logging.getLogger(__name__)
REDACTED = "***"
TELEGRAM_API = "https://api.telegram.org"
MAX_TEXT = 3500
_BOT_TOKEN = re.compile(r"\d{5,}:[A-Za-z0-9_-]{10,}")
_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


class AlertCode(StrEnum):
    """Alert codes the operations layer knows about."""

    KILL_SWITCH_TRIPPED = "KILL_SWITCH_TRIPPED"
    RECONCILE_MISMATCH = "RECONCILE_MISMATCH"
    STALE_DATA = "STALE_DATA"
    HEARTBEAT_DEAD = "HEARTBEAT_DEAD"
    NEAR_DAILY_LOSS_FLOOR = "NEAR_DAILY_LOSS_FLOOR"
    ORDER_REFUSED = "ORDER_REFUSED"
    NEWS_COVERAGE_ENDING = "NEWS_COVERAGE_ENDING"
    AUTO_FLATTEN = "AUTO_FLATTEN"
    ROLLOUT_TIER_CHANGE = "ROLLOUT_TIER_CHANGE"
    CLOCK_DRIFT = "CLOCK_DRIFT"


class AlertEvent(BaseModel):
    """One alert occurrence. ``code`` is free text so health alerts can be forwarded as they are."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    severity: Severity
    message: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    details: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_alert(cls, alert: Alert, *, at: datetime | None = None) -> AlertEvent:
        """Wrap an ``execution.status.Alert`` (health check, news coverage)."""
        return cls(
            code=alert.code,
            severity=alert.severity,
            message=alert.message,
            at=at or datetime.now(UTC),
        )

    def render(self) -> str:
        """Plain-text message (no markup, so nothing needs escaping)."""
        stamp = f"{self.at:%Y-%m-%d %H:%M:%S} UTC"
        text = f"[{self.severity.upper()}] {self.code}\n{self.message}\n{stamp}"
        return text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + "...[truncated]"


def redact(text: str, *secrets: str) -> str:
    """Remove the given secrets and anything that looks like a Telegram bot token from ``text``."""
    out = _BOT_TOKEN.sub(REDACTED, text)
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    return out


class Notifier(Protocol):
    """Anything that can deliver an alert. Must not raise."""

    def notify(self, event: AlertEvent) -> bool:
        """Deliver ``event``; True when delivered."""
        ...


class HttpTransport(Protocol):
    """Minimal HTTP POST so tests can inject a fake (no real network in tests)."""

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> int:
        """POST ``payload`` as JSON and return the HTTP status code; may raise on network errors."""
        ...


class UrllibTransport:
    """Real transport on the standard library (no extra dependency)."""

    def post_json(self, url: str, payload: Mapping[str, Any], timeout: float) -> int:
        """POST JSON over HTTPS and return the status code."""
        if not url.startswith("https://"):
            msg = "refusing a non-HTTPS URL"
            raise ValueError(msg)
        request = urllib.request.Request(  # noqa: S310 - scheme checked above
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return int(response.status)
        except urllib.error.HTTPError as exc:
            return int(exc.code)


class TelegramNotifier:
    """Send alerts through the Telegram Bot API ``sendMessage``."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        *,
        transport: HttpTransport | None = None,
        timeout: float = 10.0,
        api_base: str = TELEGRAM_API,
    ) -> None:
        if not bot_token or not chat_id:
            msg = "bot_token and chat_id are required"
            raise ValueError(msg)
        self._token = bot_token
        self._chat_id = chat_id
        self._transport = transport or UrllibTransport()
        self._timeout = timeout
        self._api_base = api_base.rstrip("/")
        self.last_error: str | None = None

    def __repr__(self) -> str:
        return "TelegramNotifier(token=***, chat_id=***)"

    def notify(self, event: AlertEvent) -> bool:
        """Send; never raises. ``last_error`` holds the redacted reason after a failure."""
        url = f"{self._api_base}/bot{self._token}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": event.render(),
            "disable_web_page_preview": True,
        }
        try:
            status = self._transport.post_json(url, payload, self._timeout)
        except Exception as exc:
            self.last_error = redact(f"{type(exc).__name__}: {exc}", self._token, self._chat_id)
            log_event(_LOG, "alert.send_failed", logging.WARNING, error=self.last_error)
            return False
        if status != 200:
            self.last_error = f"HTTP {status}"
            log_event(_LOG, "alert.send_failed", logging.WARNING, error=self.last_error)
            return False
        self.last_error = None
        return True


class NullNotifier:
    """Used when Telegram is not configured: delivery always fails, so the file fallback records."""

    last_error: str | None = "telegram not configured"

    def notify(self, event: AlertEvent) -> bool:
        """Never delivers."""
        return False


@dataclass(frozen=True)
class DispatchResult:
    """What ``AlertDispatcher.dispatch`` did."""

    sent: bool
    suppressed: bool
    fallback_written: bool
    reason: str


class AlertDispatcher:
    """De-duplicates and rate-limits alerts, falls back to a file when delivery fails.

    * The same ``code`` is not sent again within ``min_interval``; a CRITICAL alert still active
      (the caller keeps dispatching it each cycle) is re-sent every ``critical_repeat``.
    * A severity escalation for a code (for example warning to critical) is sent immediately.
    * Non-critical messages are capped at ``max_per_hour`` overall; critical ones are not capped.
    * Throttling is based on delivery ATTEMPTS, so a dead network does not spam the fallback file.
    * State is in memory: after a restart the first occurrence of each active alert is sent again.
    """

    def __init__(
        self,
        notifier: Notifier,
        fallback_path: Path | str,
        *,
        min_interval: timedelta = timedelta(minutes=15),
        critical_repeat: timedelta = timedelta(minutes=30),
        max_per_hour: int = 30,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._notifier = notifier
        self._fallback = Path(fallback_path)
        self._min_interval = min_interval
        self._critical_repeat = critical_repeat
        self._max_per_hour = max_per_hour
        self._clock = clock
        self._last: dict[str, tuple[datetime, str]] = {}
        self._recent: deque[datetime] = deque()
        self._lock = threading.Lock()

    def resolve(self, code: str) -> None:
        """Forget a code (condition cleared) so its next occurrence is sent at once."""
        with self._lock:
            self._last.pop(code, None)

    def dispatch(self, event: AlertEvent) -> DispatchResult:
        """Deliver ``event`` subject to the rules above. Never raises."""
        try:
            return self._dispatch(event)
        except Exception as exc:
            _LOG.warning("alert.dispatch_error %s", redact(f"{type(exc).__name__}: {exc}"))
            return DispatchResult(False, False, False, "dispatcher error")

    def _dispatch(self, event: AlertEvent) -> DispatchResult:
        now = self._clock()
        critical = event.severity == "critical"
        with self._lock:
            previous = self._last.get(event.code)
            if previous is not None:
                sent_at, prior_severity = previous
                escalated = _SEVERITY_RANK[event.severity] > _SEVERITY_RANK[prior_severity]
                interval = self._critical_repeat if critical else self._min_interval
                if not escalated and now - sent_at < interval:
                    return DispatchResult(False, True, False, "duplicate within interval")
            if not critical:
                while self._recent and now - self._recent[0] >= timedelta(hours=1):
                    self._recent.popleft()
                if len(self._recent) >= self._max_per_hour:
                    return DispatchResult(False, True, False, "hourly rate limit")
                self._recent.append(now)
            self._last[event.code] = (now, event.severity)
        delivered = self._notifier.notify(event)
        if delivered:
            return DispatchResult(True, False, False, "sent")
        error = getattr(self._notifier, "last_error", None)
        written = self._write_fallback(event, str(error) if error else "delivery failed")
        return DispatchResult(False, False, written, "delivery failed")

    def _write_fallback(self, event: AlertEvent, error: str) -> bool:
        record = {
            "at": event.at.isoformat(),
            "alerts": [{"code": event.code, "severity": event.severity, "message": event.message}],
            "details": event.details,
            "delivered": False,
            "error": redact(error),
        }
        try:
            self._fallback.parent.mkdir(parents=True, exist_ok=True)
            with self._fallback.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str) + "\n")
        except OSError as exc:
            _LOG.warning("alert.fallback_failed %s", redact(str(exc)))
            return False
        return True


def build_notifier(settings: OpsSettings | None = None) -> Notifier:
    """TelegramNotifier when both variables are set, otherwise a NullNotifier (file only)."""
    cfg = settings or OpsSettings()
    if cfg.telegram_configured and cfg.telegram_bot_token and cfg.telegram_chat_id:
        return TelegramNotifier(cfg.telegram_bot_token.get_secret_value(), cfg.telegram_chat_id)
    return NullNotifier()


def build_dispatcher(
    settings: OpsSettings | None = None,
    *,
    notifier: Notifier | None = None,
    fallback_path: Path | str = "data/execution/alerts.jsonl",
) -> AlertDispatcher:
    """The dispatcher the bot should use, configured from ``OpsSettings``."""
    cfg = settings or OpsSettings()
    return AlertDispatcher(
        notifier or build_notifier(cfg),
        fallback_path,
        min_interval=timedelta(minutes=cfg.alert_min_interval_minutes),
        critical_repeat=timedelta(minutes=cfg.alert_critical_repeat_minutes),
        max_per_hour=cfg.alert_max_per_hour,
    )
