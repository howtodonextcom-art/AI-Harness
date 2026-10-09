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
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                raw = json.loads(line)
                event = LifecycleEvent(
                    strategy_id=str(raw["strategy_id"]),
                    from_state=str(raw["from_state"]),
                    to_state=str(raw["to_state"]),
                    at=str(raw["at"]),
                    source=str(raw["source"]),
                    reason=str(raw["reason"]),
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
        """Current state per strategy (seed, then the events in order)."""
        current = dict(self.seed)
        for event in self._events():
            current[event.strategy_id] = event.to_state
        return current

    def history(self, strategy_id: str) -> list[LifecycleEvent]:
        """Events of one strategy, oldest first."""
        return [e for e in self._events() if e.strategy_id == strategy_id]

    def demote(self, strategy_id: str, to_state: str, reason: str, source: str) -> LifecycleEvent:
        """Move a strategy DOWN. Refuses anything that is not a demotion allowed from the web."""
        if not _ID.match(strategy_id):
            msg = "invalid strategy id"
            raise LifecycleError(msg)
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
        clean = " ".join(reason.split())[:200]
        if not clean:
            msg = "a reason is required"
            raise LifecycleError(msg)
        event = LifecycleEvent(
            strategy_id, from_state, to_state, datetime.now(UTC).isoformat(), source, clean
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__, sort_keys=True) + "\n")
        return event
