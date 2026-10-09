"""Strategy lifecycle states and the demote-only store (roadmap section 23.4 and 23.5).

States: RESEARCH, REJECTED, PAPER, DEMO, VALIDATED, FUNDED, WATCH, DEGRADED, DISABLED, RETIRED.

The store is an append-only JSON-lines file of events. The console can read it, and the web can ONLY
move a strategy DOWN to WATCH, DEGRADED or DISABLED; it can never promote, never touch a REJECTED,
RESEARCH or RETIRED strategy, and never create a strategy. Promotion happens through the ledger, an
ADR and the CLI, not from a browser. A corrupt store raises ``LifecycleError`` (fail closed).
"""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

STATES: Final = (
    "RESEARCH",
    "REJECTED",
    "PAPER",
    "DEMO",
    "VALIDATED",
    "FUNDED",
    "WATCH",
    "DEGRADED",
    "DISABLED",
    "RETIRED",
)
_RANK: Final = {
    "RESEARCH": 0,
    "REJECTED": 0,
    "RETIRED": 0,
    "DISABLED": 1,
    "DEGRADED": 2,
    "WATCH": 3,
    "PAPER": 4,
    "DEMO": 5,
    "VALIDATED": 6,
    "FUNDED": 7,
}
WEB_TARGETS: Final = ("WATCH", "DEGRADED", "DISABLED")
WEB_DEMOTABLE_FROM: Final = ("PAPER", "DEMO", "VALIDATED", "FUNDED", "WATCH", "DEGRADED")
_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,60}$")


class LifecycleError(RuntimeError):
    """The lifecycle store is unreadable or the requested change is not allowed."""


@dataclass(frozen=True)
class LifecycleEvent:
    """One change of state."""

    strategy_id: str
    from_state: str
    to_state: str
    at: str
    source: str
    reason: str
    key: str = ""


_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")


def _lock_for(path: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(str(path.resolve()), threading.Lock())


class LifecycleStore:
    """Append-only events over a seed of known strategies and their derived initial states."""

    def __init__(self, path: Path, seed: dict[str, str] | None = None) -> None:
        self.path = path
        self.seed = dict(seed or {})

    def _events(self) -> list[LifecycleEvent]:
        if not self.path.exists():
            return []
        events: list[LifecycleEvent] = []
        try:
            text = self.path.read_text(encoding="utf-8")
            lines = text.splitlines()
            # a torn FINAL line (crash mid-write, no trailing newline) is ignored; any other bad
            # line still makes the store unreadable (fail closed)
            torn_last = bool(lines) and not text.endswith("\n")
            for number, line in enumerate(lines):
                if not line.strip():
                    continue
                if torn_last and number == len(lines) - 1:
                    try:
                        json.loads(line)
                    except json.JSONDecodeError:
                        break
                raw = json.loads(line)
                event = LifecycleEvent(
                    strategy_id=str(raw["strategy_id"]),
                    from_state=str(raw["from_state"]),
                    to_state=str(raw["to_state"]),
                    at=str(raw["at"]),
                    source=str(raw["source"]),
                    reason=str(raw["reason"]),
                    key=str(raw.get("key", "")),
                )
                if event.to_state not in STATES or event.from_state not in STATES:
                    msg = "unknown state in the lifecycle store"
                    raise LifecycleError(msg)
                events.append(event)
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            msg = "the lifecycle store is unreadable"
            raise LifecycleError(msg) from exc
        return events

    def states(self) -> dict[str, str]:
        """Current state per strategy (seed, then the events in order).

        Events about a strategy that is not in the seed are ignored, and so is any event that the
        web wrote which is not a legal demotion: a hand-edited or hostile file cannot promote.
        """
        current = dict(self.seed)
        for event in self._events():
            if event.strategy_id not in current:
                continue
            if event.source == "web" and not (
                event.to_state in WEB_TARGETS
                and current[event.strategy_id] in WEB_DEMOTABLE_FROM
                and _RANK[event.to_state] < _RANK[current[event.strategy_id]]
            ):
                continue
            current[event.strategy_id] = event.to_state
        return current

    def history(self, strategy_id: str) -> list[LifecycleEvent]:
        """Events of one strategy, oldest first."""
        return [e for e in self._events() if e.strategy_id == strategy_id]

    def demote(
        self, strategy_id: str, to_state: str, reason: str, source: str, key: str = ""
    ) -> LifecycleEvent:
        """Move a strategy DOWN. Refuses anything that is not a demotion allowed from the web.

        Serialised by a lock and re-checked inside it, so two concurrent demotions cannot undo each
        other. The same ``key`` replays the first event instead of appending a second one.
        """
        with _lock_for(self.path):
            return self._demote_locked(strategy_id, to_state, reason, source, key)

    def _demote_locked(
        self, strategy_id: str, to_state: str, reason: str, source: str, key: str
    ) -> LifecycleEvent:
        if not _ID.match(strategy_id):
            msg = "invalid strategy id"
            raise LifecycleError(msg)
        clean_reason = " ".join(_CONTROL.sub(" ", reason).split())[:200]
        if key:
            for earlier in self._events():
                if earlier.key == key:
                    same = (
                        earlier.strategy_id == strategy_id
                        and earlier.to_state == to_state
                        and earlier.reason == clean_reason
                    )
                    if not same:
                        msg = "IDEMPOTENCY_CONFLICT: this key was used for a different request"
                        raise LifecycleError(msg)
                    return earlier
        current = self.states()
        if strategy_id not in current:
            msg = "unknown strategy"
            raise LifecycleError(msg)
        if to_state not in WEB_TARGETS:
            msg = f"the web may only set {', '.join(WEB_TARGETS)}"
            raise LifecycleError(msg)
        from_state = current[strategy_id]
        if from_state not in WEB_DEMOTABLE_FROM:
            msg = f"a strategy in state {from_state} cannot be changed from the web"
            raise LifecycleError(msg)
        if _RANK[to_state] >= _RANK[from_state]:
            msg = "only a lower state is allowed (no promotion, no sideways move)"
            raise LifecycleError(msg)
        clean = " ".join(_CONTROL.sub(" ", reason).split())[:200]
        if not clean:
            msg = "a reason is required"
            raise LifecycleError(msg)
        event = LifecycleEvent(
            strategy_id,
            from_state,
            to_state,
            datetime.now(UTC).isoformat(),
            source,
            clean,
            key,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.path.read_text(encoding="utf-8") if self.path.exists() else ""
        if existing and not existing.endswith("\n"):
            last = existing.rsplit("\n", 1)[-1]
            try:
                json.loads(last)
                kept = existing + "\n"  # a complete event that only lost its newline: keep it
            except json.JSONDecodeError:
                # a torn (incomplete) last line: drop it so the journal stays well formed
                kept = existing.rsplit("\n", 1)[0] + "\n" if "\n" in existing else ""
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(kept, encoding="utf-8")
            tmp.replace(self.path)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")
        return event
