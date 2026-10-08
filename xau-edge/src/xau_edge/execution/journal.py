"""Execution journal: an append-only audit trail of every order-related event (ADR-0019).

One JSON line per event (intent accepted, order requested, broker answered, position closed,
reconciliation result, kill switch change). Only decisions, ids, prices and broker result codes are
written; the secret redaction of the logging layer applies as well. If a line cannot be written the
caller must NOT proceed with the action the event describes: ``record`` raises ``JournalError``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xau_edge.execution.runner import JournalError
from xau_edge.observability import REDACTED, log_event

_LOG = logging.getLogger(__name__)
_SECRET_WORDS = ("password", "passwd", "secret", "token", "login", "credential")


def _clean(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return REDACTED
    if isinstance(value, dict):
        return {
            str(k): REDACTED
            if any(w in str(k).lower() for w in _SECRET_WORDS)
            else _clean(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        return [_clean(v, depth + 1) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(type(value).__name__)


class ExecutionJournal:
    """Append-only event log."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"cannot create the journal directory: {exc}"
            raise JournalError(msg) from exc

    def record(self, event: str, **fields: Any) -> None:
        """Append one event; raises ``JournalError`` if it cannot be written."""
        line = {"at": datetime.now(UTC).isoformat(), "event": event, **_clean(fields)}
        try:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line, sort_keys=True) + "\n")
        except (OSError, TypeError, ValueError) as exc:
            msg = f"cannot write the execution journal: {exc}"
            raise JournalError(msg) from exc
        log_event(_LOG, "journal.event", journal_event=event)

    def read(self, limit: int = 200) -> list[dict[str, Any]]:
        """The latest ``limit`` events, oldest first; a malformed line raises ``JournalError``."""
        if not self.path.exists():
            return []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()[-limit:]
            return [json.loads(line) for line in lines]
        except (OSError, json.JSONDecodeError) as exc:
            msg = f"cannot read the execution journal: {exc}"
            raise JournalError(msg) from exc
