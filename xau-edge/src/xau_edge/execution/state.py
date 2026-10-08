"""Persistent execution state: kill switch, idempotency, decision bar, daily counter (ADR-0019).

A restart must not forget that the kill switch is tripped, nor which signals were already acted on.
The store is a small SQLite file (standard library, no new dependency). Every failure to open, read
or write it raises ``StateError``; nothing here swallows an error, so callers fail closed.

A missing file is a fresh, safe state (nothing seen, kill switch not tripped). A file that is not a
SQLite database, has the wrong schema, or fails its integrity check is NEVER repaired or recreated:
it raises, because silently starting over would forget a tripped kill switch.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from xau_edge.observability import log_event
from xau_edge.risk.kill_switch import RESET_PHRASE, KillSwitch

_LOG = logging.getLogger(__name__)
SCHEMA_VERSION: Final = 1
STATE_UNREADABLE: Final = "STATE_UNREADABLE"

_SCHEMA: Final = (
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS kill_switch (id INTEGER PRIMARY KEY CHECK (id = 1),"
    " tripped INTEGER NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS seen_signals (signal_hash TEXT PRIMARY KEY,"
    " intent_id TEXT NOT NULL, decision_time TEXT NOT NULL, dry_run INTEGER NOT NULL,"
    " created_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS daily_orders (day TEXT PRIMARY KEY, count INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS tickets (intent_id TEXT PRIMARY KEY, ticket TEXT,"
    " updated_at TEXT NOT NULL)",
)
_EXPECTED_TABLES: Final = frozenset(
    {"meta", "kill_switch", "seen_signals", "daily_orders", "tickets"}
)


class StateError(RuntimeError):
    """The execution state could not be opened, read or written; execution must be refused."""


class DuplicateSignalError(StateError):
    """The signal hash was already recorded as acted on."""


class DailyLimitError(StateError):
    """Recording the order would exceed the maximum orders per day."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ExecutionState:
    """SQLite-backed state shared by the bridge and (later) the demo runner."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            msg = f"cannot create the state directory {self.path.parent}: {exc}"
            raise StateError(msg) from exc
        self._initialise()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        try:
            conn = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        except sqlite3.Error as exc:
            msg = f"cannot open the state database {self.path}: {exc}"
            raise StateError(msg) from exc
        try:
            yield conn
        except sqlite3.Error as exc:
            msg = f"state database error: {exc}"
            raise StateError(msg) from exc
        finally:
            conn.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def _initialise(self) -> None:
        existed = self.path.exists()
        with self._connect() as conn:
            if existed:
                self._verify(conn)
                return
            conn.execute("BEGIN IMMEDIATE")
            for statement in _SCHEMA:
                conn.execute(statement)
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),)
            )
            conn.execute(
                "INSERT INTO kill_switch (id, tripped, reason, updated_at) VALUES (1, 0, '', ?)",
                (_now(),),
            )
            conn.execute("COMMIT")
        log_event(_LOG, "execution_state.created", path=str(self.path))

    def _verify(self, conn: sqlite3.Connection) -> None:
        check = conn.execute("PRAGMA quick_check").fetchone()
        if check is None or check[0] != "ok":
            msg = f"state database {self.path} failed its integrity check"
            raise StateError(msg)
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if not tables >= _EXPECTED_TABLES:
            msg = f"state database {self.path} has an unexpected schema (missing tables)"
            raise StateError(msg)
        version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        if version is None or version[0] != str(SCHEMA_VERSION):
            msg = f"state database {self.path} has an unsupported schema version"
            raise StateError(msg)
        if conn.execute("SELECT COUNT(*) FROM kill_switch WHERE id = 1").fetchone()[0] != 1:
            msg = f"state database {self.path} has no kill switch row"
            raise StateError(msg)

    # -- kill switch ---------------------------------------------------------------------------

    def kill_switch_state(self) -> tuple[bool, str]:
        """Return ``(tripped, reason)``."""
        with self._connect() as conn:
            row = conn.execute("SELECT tripped, reason FROM kill_switch WHERE id = 1").fetchone()
        if row is None:
            msg = "kill switch row is missing"
            raise StateError(msg)
        return bool(row[0]), str(row[1])

    def trip_kill_switch(self, reason: str) -> None:
        """Latch the kill switch; the FIRST reason is kept."""
        with self._transaction() as conn:
            row = conn.execute("SELECT tripped FROM kill_switch WHERE id = 1").fetchone()
            if row is not None and row[0]:
                return
            conn.execute(
                "UPDATE kill_switch SET tripped = 1, reason = ?, updated_at = ? WHERE id = 1",
                (reason or "unspecified", _now()),
            )
        log_event(_LOG, "kill_switch.trip", logging.CRITICAL, reason=reason, persistent=True)

    def reset_kill_switch(self, *, confirm: str) -> None:
        """Clear the kill switch; ``confirm`` must equal the existing reset phrase."""
        if confirm != RESET_PHRASE:
            msg = f"confirm must be exactly {RESET_PHRASE!r} to reset the kill switch"
            raise ValueError(msg)
        previous = self.kill_switch_state()[1]
        with self._transaction() as conn:
            conn.execute(
                "UPDATE kill_switch SET tripped = 0, reason = '', updated_at = ? WHERE id = 1",
                (_now(),),
            )
        log_event(_LOG, "kill_switch.reset", logging.WARNING, previous_reason=previous)

    # -- idempotency, decision bar, daily counter ---------------------------------------------

    def is_seen(self, signal_hash: str) -> bool:
        """True if a signal with this hash was already recorded."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_signals WHERE signal_hash = ?", (signal_hash,)
            ).fetchone()
        return row is not None

    def last_decision_bar(self) -> datetime | None:
        """Timestamp of the latest decision bar that produced an accepted intent."""
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'last_decision_bar'").fetchone()
        if row is None:
            return None
        try:
            return datetime.fromisoformat(row[0])
        except ValueError as exc:
            msg = "the stored decision bar is not a valid timestamp"
            raise StateError(msg) from exc

    def daily_order_count(self, day: str) -> int:
        """Orders recorded for a calendar-day key."""
        with self._connect() as conn:
            row = conn.execute("SELECT count FROM daily_orders WHERE day = ?", (day,)).fetchone()
        return int(row[0]) if row else 0

    def record_accepted(
        self,
        *,
        signal_hash: str,
        intent_id: str,
        decision_time: datetime,
        day: str,
        dry_run: bool,
        max_orders_per_day: int,
    ) -> None:
        """Atomically mark a signal as acted on, advance the decision bar and count the order.

        Dry-run intents are remembered (so the same signal is not offered twice) but do not use
        up the daily order budget. Raises ``DuplicateSignalError`` or ``DailyLimitError`` and
        changes nothing in that case.
        """
        with self._transaction() as conn:
            if conn.execute(
                "SELECT 1 FROM seen_signals WHERE signal_hash = ?", (signal_hash,)
            ).fetchone():
                msg = f"signal {signal_hash[:12]} was already acted on"
                raise DuplicateSignalError(msg)
            row = conn.execute("SELECT count FROM daily_orders WHERE day = ?", (day,)).fetchone()
            count = int(row[0]) if row else 0
            if not dry_run and count >= max_orders_per_day:
                msg = f"daily order limit {max_orders_per_day} reached for {day}"
                raise DailyLimitError(msg)
            conn.execute(
                "INSERT INTO seen_signals (signal_hash, intent_id, decision_time, dry_run,"
                " created_at) VALUES (?, ?, ?, ?, ?)",
                (signal_hash, intent_id, decision_time.isoformat(), int(dry_run), _now()),
            )
            if not dry_run:
                conn.execute(
                    "INSERT INTO daily_orders (day, count) VALUES (?, 1)"
                    " ON CONFLICT(day) DO UPDATE SET count = count + 1",
                    (day,),
                )
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('last_decision_bar', ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (decision_time.isoformat(),),
            )

    # -- broker tickets (placeholder for the demo adapter) -------------------------------------

    def set_ticket(self, intent_id: str, ticket: str | None) -> None:
        """Remember the broker ticket for an intent (``None`` until a broker assigns one)."""
        with self._transaction() as conn:
            conn.execute(
                "INSERT INTO tickets (intent_id, ticket, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(intent_id) DO UPDATE SET ticket = excluded.ticket,"
                " updated_at = excluded.updated_at",
                (intent_id, ticket, _now()),
            )

    def get_ticket(self, intent_id: str) -> str | None:
        """The stored ticket for an intent, if any."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT ticket FROM tickets WHERE intent_id = ?", (intent_id,)
            ).fetchone()
        return None if row is None or row[0] is None else str(row[0])


class PersistentKillSwitch(KillSwitch):
    """A ``KillSwitch`` whose latch lives in the state file, so a restart cannot clear it.

    It can be handed to ``RiskEngine``. If the state cannot be read, the switch reports itself
    tripped (fail closed) with the reason ``STATE_UNREADABLE``.
    """

    def __init__(self, state: ExecutionState) -> None:
        super().__init__()
        self._state = state

    @property
    def tripped(self) -> bool:
        """True while trading is blocked, or when the state cannot be read."""
        try:
            return self._state.kill_switch_state()[0]
        except StateError:
            return True

    @property
    def reason(self) -> str:
        """Why the switch tripped."""
        try:
            tripped, reason = self._state.kill_switch_state()
        except StateError:
            return STATE_UNREADABLE
        return reason if tripped else ""

    def trip(self, reason: str) -> None:
        """Block trading; if even the write fails the error is raised, never swallowed."""
        self._state.trip_kill_switch(reason)

    def reset(self, *, confirm: str) -> None:
        """Re-enable trading; needs the exact confirmation phrase."""
        self._state.reset_kill_switch(confirm=confirm)
