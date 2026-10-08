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
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Literal

from xau_edge.observability import log_event
from xau_edge.risk.kill_switch import RESET_PHRASE, KillSwitch

_LOG = logging.getLogger(__name__)
SCHEMA_VERSION: Final = 4
STATE_UNREADABLE: Final = "STATE_UNREADABLE"

_SCHEMA: Final = (
    "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS kill_switch (id INTEGER PRIMARY KEY CHECK (id = 1),"
    " tripped INTEGER NOT NULL, reason TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS seen_signals (signal_hash TEXT PRIMARY KEY,"
    " intent_id TEXT NOT NULL, decision_time TEXT NOT NULL, dry_run INTEGER NOT NULL,"
    " risk_amount REAL NOT NULL, day TEXT NOT NULL, created_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS daily_orders (day TEXT PRIMARY KEY, count INTEGER NOT NULL)",
    "CREATE TABLE IF NOT EXISTS bot_positions (intent_id TEXT PRIMARY KEY, ticket TEXT NOT NULL,"
    " symbol TEXT NOT NULL, direction INTEGER NOT NULL, lots REAL NOT NULL,"
    " stop_loss REAL NOT NULL, take_profit REAL NOT NULL, status TEXT NOT NULL,"
    " opened_at TEXT NOT NULL, max_hold_until TEXT NOT NULL, updated_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS submissions (intent_id TEXT PRIMARY KEY, signal_hash TEXT NOT NULL,"
    " status TEXT NOT NULL, retcode INTEGER, ticket TEXT, updated_at TEXT NOT NULL)",
)
_EXPECTED_TABLES: Final = frozenset(
    {"meta", "kill_switch", "seen_signals", "daily_orders", "bot_positions", "submissions"}
)


@dataclass(frozen=True)
class BotPositionRecord:
    """A position the bot opened, as recorded when the broker confirmed it."""

    intent_id: str
    ticket: str
    symbol: str
    direction: Literal[-1, 1]
    lots: float
    stop_loss: float
    take_profit: float
    opened_at: datetime
    max_hold_until: datetime


@dataclass(frozen=True)
class AccountBaseline:
    """Reference balances the prop-firm loss limits are measured from."""

    initial_capital: float
    day_start_balance: float
    highest_eod_balance: float


class StateError(RuntimeError):
    """The execution state could not be opened, read or written; execution must be refused."""


class DuplicateSignalError(StateError):
    """The signal hash was already recorded as acted on."""


class DuplicateSubmissionError(StateError):
    """The intent was already submitted (or a submission is unresolved)."""


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
        risk_amount: float = 0.0,
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
                " risk_amount, day, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    signal_hash,
                    intent_id,
                    decision_time.isoformat(),
                    int(dry_run),
                    risk_amount,
                    day,
                    _now(),
                ),
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

    def is_approved(self, intent_id: str) -> bool:
        """True if the bridge accepted this intent for real submission (not a dry run)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_signals WHERE intent_id = ? AND dry_run = 0", (intent_id,)
            ).fetchone()
        return row is not None

    def risk_taken(self, day: str) -> float:
        """Total risk the bridge approved for real orders on a calendar-day key."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(risk_amount), 0) FROM seen_signals"
                " WHERE day = ? AND dry_run = 0",
                (day,),
            ).fetchone()
        return float(row[0])

    def account_baseline(
        self, day: str, balance: float, *, initial_capital: float | None = None
    ) -> AccountBaseline:
        """Persisted account reference points, so a restart cannot reset the loss limits.

        The first call fixes the initial capital (or uses the one given). The first call of each
        calendar-day key fixes that day's starting balance and raises the end-of-day high-water
        mark with the previous day's last balance.
        """
        with self._transaction() as conn:

            def get(key: str) -> str | None:
                row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
                return None if row is None else str(row[0])

            def put(key: str, value: str) -> None:
                conn.execute(
                    "INSERT INTO meta (key, value) VALUES (?, ?)"
                    " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, value),
                )

            initial = get("initial_capital")
            if initial is None:
                initial = repr(initial_capital if initial_capital is not None else balance)
                put("initial_capital", initial)
            highest = float(get("highest_eod") or initial)
            if get("baseline_day") != day:
                previous = get("last_balance")
                if previous is not None:
                    highest = max(highest, float(previous))
                put("highest_eod", repr(highest))
                put("baseline_day", day)
                put("day_start_balance", repr(balance))
            put("last_balance", repr(balance))
            day_start = float(get("day_start_balance") or balance)
            return AccountBaseline(float(initial), day_start, highest)

    # -- positions the bot opened (for reconciliation) ----------------------------------------

    def register_position(self, record: BotPositionRecord) -> None:
        """Remember a position the bot opened; re-registering the same intent is refused."""
        with self._transaction() as conn:
            if conn.execute(
                "SELECT 1 FROM bot_positions WHERE intent_id = ?", (record.intent_id,)
            ).fetchone():
                msg = f"intent {record.intent_id[:12]} already has a registered position"
                raise StateError(msg)
            conn.execute(
                "INSERT INTO bot_positions (intent_id, ticket, symbol, direction, lots,"
                " stop_loss, take_profit, status, opened_at, max_hold_until, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?)",
                (
                    record.intent_id,
                    record.ticket,
                    record.symbol,
                    record.direction,
                    record.lots,
                    record.stop_loss,
                    record.take_profit,
                    record.opened_at.isoformat(),
                    record.max_hold_until.isoformat(),
                    _now(),
                ),
            )

    def mark_position_closed(self, ticket: str) -> None:
        """Record that a bot position is no longer open; an unknown ticket is an error."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE bot_positions SET status = 'CLOSED', updated_at = ? WHERE ticket = ?"
                " AND status = 'OPEN'",
                (_now(), ticket),
            )
            if cursor.rowcount != 1:
                msg = f"no open bot position with ticket {ticket}"
                raise StateError(msg)

    def all_bot_tickets(self) -> set[str]:
        """Tickets of every position the bot ever opened (open or closed)."""
        with self._connect() as conn:
            rows = conn.execute("SELECT ticket FROM bot_positions").fetchall()
        return {str(r[0]) for r in rows}

    def open_positions(self) -> list[BotPositionRecord]:
        """Positions the bot believes are open."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT intent_id, ticket, symbol, direction, lots, stop_loss, take_profit,"
                " opened_at, max_hold_until FROM bot_positions WHERE status = 'OPEN'"
                " ORDER BY opened_at"
            ).fetchall()
        try:
            return [
                BotPositionRecord(
                    intent_id=str(r[0]),
                    ticket=str(r[1]),
                    symbol=str(r[2]),
                    direction=1 if r[3] == 1 else -1,
                    lots=float(r[4]),
                    stop_loss=float(r[5]),
                    take_profit=float(r[6]),
                    opened_at=datetime.fromisoformat(r[7]),
                    max_hold_until=datetime.fromisoformat(r[8]),
                )
                for r in rows
            ]
        except (ValueError, TypeError) as exc:
            msg = "a stored bot position is malformed"
            raise StateError(msg) from exc

    # -- submissions: exactly-once guard for order sending -------------------------------------

    def begin_submission(self, intent_id: str, signal_hash: str) -> None:
        """Mark an intent as being sent; a second attempt for the same intent is refused."""
        with self._transaction() as conn:
            if conn.execute(
                "SELECT 1 FROM submissions WHERE intent_id = ?", (intent_id,)
            ).fetchone():
                msg = f"intent {intent_id[:12]} was already submitted or is being submitted"
                raise DuplicateSubmissionError(msg)
            conn.execute(
                "INSERT INTO submissions (intent_id, signal_hash, status, updated_at)"
                " VALUES (?, ?, 'PENDING', ?)",
                (intent_id, signal_hash, _now()),
            )

    def finish_submission(
        self, intent_id: str, status: str, *, retcode: int | None = None, ticket: str | None = None
    ) -> None:
        """Record the outcome (FILLED, REJECTED or UNKNOWN) of a started submission."""
        with self._transaction() as conn:
            cursor = conn.execute(
                "UPDATE submissions SET status = ?, retcode = ?, ticket = ?, updated_at = ?"
                " WHERE intent_id = ?",
                (status, retcode, ticket, _now(), intent_id),
            )
            if cursor.rowcount != 1:
                msg = f"no submission recorded for intent {intent_id[:12]}"
                raise StateError(msg)

    def unresolved_submissions(self) -> list[str]:
        """Intent ids whose submission never reached a final outcome (PENDING or UNKNOWN)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT intent_id FROM submissions WHERE status IN ('PENDING', 'UNKNOWN')"
            ).fetchall()
        return [str(r[0]) for r in rows]


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
