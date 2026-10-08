"""The soft-stop request shared by the control plane (writer) and the bot (reader).

The bot checks it between cycles and while it waits for the next bar. A request written BEFORE the
bot process started is ignored, so a sentinel left behind by a crash never stops a later start.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


def request_stop(path: Path, now: datetime) -> None:
    """Write the stop request (atomically)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps({"requested_at": now.isoformat(), "source": "web"}), "utf-8")
    tmp.replace(path)


def clear_stop(path: Path) -> None:
    """Remove the stop request (missing is fine)."""
    path.unlink(missing_ok=True)


def _requested_at(path: Path) -> datetime | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return datetime.fromisoformat(str(raw["requested_at"]))
    except (OSError, ValueError, KeyError, TypeError):
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, UTC)
        except OSError:
            return None


class StopSentinel:
    """Callable for ``BotApp(stop_requested=...)``: True once a fresh stop request exists."""

    def __init__(self, path: Path, started_at: datetime) -> None:
        self.path = path
        self.started_at = started_at

    def __call__(self) -> bool:
        if not self.path.exists():
            return False
        when = _requested_at(self.path)
        return when is not None and when >= self.started_at
