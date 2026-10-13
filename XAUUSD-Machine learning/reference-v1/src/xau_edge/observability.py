"""Structured (JSON-lines) logging with secret redaction.

Events are logged through the standard library under the ``xau_edge`` logger. Nothing is emitted
unless ``configure_logging`` installs a handler (library code never configures logging itself).

Redaction is defence in depth, not a licence to log secrets: call sites log only metadata (symbol,
counts, hashes). The formatter additionally (a) replaces values whose key looks like a credential,
(b) scrubs ``password=...``-style text inside strings and messages, (c) never calls ``str()`` on
unknown objects, and (d) bounds depth, container size and string length. It never raises.
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
import threading
from datetime import UTC, date, datetime
from enum import Enum
from pathlib import PurePath
from typing import Any, Final, TextIO

import numpy as np

REDACTED: Final = "***REDACTED***"
ROOT_LOGGER: Final = "xau_edge"

_STEMS: Final = (
    "password",
    "passwd",
    "secret",
    "token",
    "login",
    "credential",
    "apikey",
    "privatekey",
    "authorization",
    "bearer",
    "cookie",
    "account",
    "session",
)
_KEY_TOKENS: Final = frozenset({"pass", "pwd", "auth", "key", "dsn"})
_TOKEN_SPLIT: Final = re.compile(r"[^A-Za-z0-9]+|(?<=[a-z0-9])(?=[A-Z])")
_INLINE_SECRET: Final = re.compile(
    r"(?i)(?:[\w-]*(?:password|passwd|pwd|secret|token|login|api[_-]?key|account)[\w-]*"
    r"\s*[=:]\s*[^\s;,&]+|authorization\s*[=:]\s*\S+(?:\s+\S+)?)"
)
_RESERVED: Final = ("ts", "level", "logger", "event")
_MAX_DEPTH: Final = 6
_MAX_ITEMS: Final = 100
_MAX_STR: Final = 1000
_MAX_INT: Final = 2**63
_LOCK: Final = threading.Lock()


class XauHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker subclass so ``configure_logging`` can find and replace its own handler."""


def _sensitive_key(key: str) -> bool:
    squashed = re.sub(r"[^a-z0-9]", "", key.lower())
    if any(stem in squashed for stem in _STEMS):
        return True
    return any(t.lower() in _KEY_TOKENS for t in _TOKEN_SPLIT.split(key) if t)


def _scrub(text: str) -> str:
    """Truncate first (the pattern is quadratic on long words), then scrub inline secrets."""
    truncated = len(text) > _MAX_STR
    cleaned = _INLINE_SECRET.sub(REDACTED, text[:_MAX_STR])
    return cleaned + "...[truncated]" if truncated else cleaned


def _sanitise(value: Any, key: str | None = None, depth: int = 0) -> Any:  # noqa: PLR0911, PLR0912 - flat type dispatch
    if key is not None and _sensitive_key(key):
        return REDACTED
    if isinstance(value, np.generic):
        value = value.item()
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if abs(value) < _MAX_INT else "<bigint>"
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, str):
        return _scrub(value)
    if isinstance(value, Enum):
        return _sanitise(value.value, None, depth)
    if isinstance(value, (datetime, date)):
        return str(value)
    if isinstance(value, PurePath):
        return _scrub(str(value))
    if depth >= _MAX_DEPTH:
        return "<max-depth>"
    if isinstance(value, dict):
        items = list(value.items())[:_MAX_ITEMS]
        return {str(k): _sanitise(v, str(k), depth + 1) for k, v in items}
    if isinstance(value, (list, tuple, set, frozenset)):
        out = [_sanitise(v, None, depth + 1) for v in list(value)[:_MAX_ITEMS]]
        if len(value) > _MAX_ITEMS:
            out.append("...")
        return out
    return f"<{type(value).__name__}>"


class JsonFormatter(logging.Formatter):
    """Format a record as one JSON object; structured fields come from ``record.fields``."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            payload: dict[str, Any] = {
                "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "event": _scrub(record.getMessage()),
            }
            fields = getattr(record, "fields", {})
            if isinstance(fields, dict):
                for key, value in _sanitise(fields).items():
                    payload[f"field_{key}" if key in _RESERVED else key] = value
            if record.exc_info and record.exc_info[0] is not None:
                payload["exc_type"] = record.exc_info[0].__name__
            return json.dumps(payload, allow_nan=False)
        except Exception:
            return json.dumps(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "level": "ERROR",
                    "logger": record.name,
                    "event": "log_format_error",
                }
            )


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """Log ``event`` with structured ``fields`` (redacted by the formatter)."""
    logger.log(level, event, extra={"fields": fields})


def configure_logging(
    level: str = "INFO", *, stream: TextIO | None = None, propagate: bool = False
) -> None:
    """Install one JSON handler on the ``xau_edge`` logger (idempotent, thread-safe).

    ``propagate`` is off by default so an application-level root handler does not print every
    event a second time.
    """
    numeric = logging.getLevelName(level.upper())
    if not isinstance(numeric, int):
        msg = f"unknown log level: {level!r}"
        raise ValueError(msg)
    with _LOCK:
        logger = logging.getLogger(ROOT_LOGGER)
        logger.setLevel(numeric)
        logger.propagate = propagate
        for existing in [h for h in logger.handlers if isinstance(h, XauHandler)]:
            logger.removeHandler(existing)
        handler = XauHandler(stream or sys.stderr)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
