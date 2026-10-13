"""V2's own durable state: paper positions, the append-only journal and the account row.

SQLite (stdlib), one file under V2's data directory. This is the ONLY place V2 writes (the shared
market store stays read-only). Every change is one transaction; the journal is append-only (the
store exposes no update or delete for it); a position can be opened once per ``setup_id`` (UNIQUE),
so a repeated poll or a restart can never open the same setup twice.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    setup_id TEXT NOT NULL UNIQUE,
    decision_id TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    lots REAL NOT NULL,
    entry REAL NOT NULL,
    quote_entry REAL NOT NULL,
    stop_loss REAL NOT NULL,
    take_profit REAL NOT NULL,
    take_profit_2 REAL,
    net_rr REAL NOT NULL,
    risk_amount REAL NOT NULL,
    risk_pct REAL NOT NULL,
    tick_size REAL NOT NULL,
    tick_value REAL NOT NULL,
    point REAL NOT NULL,
    contract_size REAL NOT NULL,
    session TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('AUTO', 'MANUAL')),
    opened_at TEXT NOT NULL,
    last_bar_us INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
    closed_at TEXT,
    exit_price REAL,
    exit_reason TEXT,
    ambiguous INTEGER NOT NULL DEFAULT 0,
    pnl_usd REAL,
    swap_usd REAL,
    mae_points REAL NOT NULL DEFAULT 0,
    mfe_points REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS journal (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    position_id TEXT,
    detail TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decision_log (
    bar_open_us INTEGER PRIMARY KEY,
    logged_at TEXT NOT NULL,
    action TEXT NOT NULL,
    readiness_level INTEGER NOT NULL,
    bias TEXT NOT NULL,
    refusals TEXT NOT NULL,
    price REAL,
    spread_points REAL,
    atr_m15 REAL,
    market_status TEXT NOT NULL,
    data_quality TEXT,
    decision_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    setup_id TEXT
);
CREATE TABLE IF NOT EXISTS decision_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    action TEXT NOT NULL,
    chain_verdict TEXT NOT NULL,
    strategy_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_decisions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    timestamp TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    setup_id TEXT NOT NULL,
    system_action TEXT NOT NULL,
    system_recommendation TEXT NOT NULL,
    system_bias TEXT NOT NULL,
    setup_state TEXT NOT NULL,
    trigger_state TEXT NOT NULL,
    m1_execution_state TEXT,
    m1_quality TEXT,
    entry REAL,
    sl REAL,
    tp REAL,
    rr REAL,
    risk_pct REAL,
    risk_amount REAL,
    price REAL,
    expiry TEXT,
    human_choice TEXT NOT NULL CHECK (human_choice IN ('ACCEPT', 'WAIT', 'REJECT')),
    human_reason TEXT NOT NULL,
    paper_mode TEXT NOT NULL CHECK (paper_mode = 'PAPER'),
    strategy_version TEXT NOT NULL,
    evidence_label TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS human_by_setup ON human_decisions (setup_id, seq);
CREATE TRIGGER IF NOT EXISTS human_decisions_no_update BEFORE UPDATE ON human_decisions
BEGIN SELECT RAISE(ABORT, 'human decisions are append-only'); END;
CREATE TRIGGER IF NOT EXISTS human_decisions_no_delete BEFORE DELETE ON human_decisions
BEGIN SELECT RAISE(ABORT, 'human decisions are append-only'); END;
CREATE TABLE IF NOT EXISTS account (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

POSITION_COLUMNS = [
    "id",
    "setup_id",
    "decision_id",
    "side",
    "lots",
    "entry",
    "quote_entry",
    "stop_loss",
    "take_profit",
    "take_profit_2",
    "net_rr",
    "risk_amount",
    "risk_pct",
    "tick_size",
    "tick_value",
    "point",
    "contract_size",
    "session",
    "source",
    "opened_at",
    "last_bar_us",
    "status",
    "closed_at",
    "exit_price",
    "exit_reason",
    "ambiguous",
    "pnl_usd",
    "swap_usd",
    "mae_points",
    "mfe_points",
]


@dataclass(frozen=True)
class JournalRow:
    seq: int
    ts: datetime
    kind: str
    position_id: str | None
    detail: dict[str, Any]


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


class PaperStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(SCHEMA)

    # ---- reliability --------------------------------------------------------------------------
    def integrity(self) -> list[str]:
        """Problems found by SQLite's own checks (an empty list means the file is sound)."""
        with self._lock:
            quick = [str(r[0]) for r in self._db.execute("PRAGMA integrity_check").fetchall()]
            fk = [
                f"foreign key violation: {tuple(r)}"
                for r in self._db.execute("PRAGMA foreign_key_check")
            ]
        return [p for p in quick if p != "ok"] + fk

    def backup_to(self, target: Path) -> Path:
        """A consistent online copy (SQLite backup API; safe while the engine writes)."""
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            copy = sqlite3.connect(target)
            try:
                self._db.backup(copy)
            finally:
                copy.close()
        return target

    # ---- the decision log (forward evidence) --------------------------------------------------
    def log_decision(self, row: dict[str, Any]) -> bool:
        """Record the decision seen at one closed M5 bar; False when that bar was already logged."""
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with self._tx() as db:
            cur = db.execute(
                f"INSERT OR IGNORE INTO decision_log ({cols}) VALUES ({marks})",
                tuple(row.values()),
            )
            return cur.rowcount == 1

    def log_event(self, row: dict[str, Any]) -> None:
        """Append one state transition (regime, scenario, authorization, gate): event-driven, so a
        transition between two M5 closes is never lost."""
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with self._tx() as db:
            db.execute(
                f"INSERT INTO decision_events ({cols}) VALUES ({marks})", tuple(row.values())
            )

    def events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM decision_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def last_logged_bar(self) -> int | None:
        with self._lock:
            row = self._db.execute("SELECT MAX(bar_open_us) AS m FROM decision_log").fetchone()
        return None if row["m"] is None else int(row["m"])

    def decision_rows(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM decision_log ORDER BY bar_open_us").fetchall()
        return [dict(r) for r in rows]

    # ---- the human's decisions (append-only: no update, no delete) -----------------------------
    def append_human(self, row: dict[str, Any]) -> None:
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        with self._tx() as db:
            db.execute(
                f"INSERT INTO human_decisions ({cols}) VALUES ({marks})",
                tuple(row.values()),
            )

    def human_decisions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM human_decisions ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_human(self, setup_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM human_decisions WHERE setup_id = ? ORDER BY seq DESC LIMIT 1",
                (setup_id,),
            ).fetchone()
        return None if row is None else dict(row)

    def human_revision(self) -> int:
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(MAX(seq), 0) AS r FROM human_decisions"
            ).fetchone()
        return int(row["r"])

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---- transactions -------------------------------------------------------------------------
    def _tx(self) -> _Tx:
        return _Tx(self._db, self._lock)

    # ---- account ------------------------------------------------------------------------------
    def account(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute("SELECT value FROM account WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_account_once(self, key: str, value: str) -> str:
        """Set ``key`` only when absent (a changed config never rewrites history)."""
        with self._tx() as db:
            db.execute("INSERT OR IGNORE INTO account (key, value) VALUES (?, ?)", (key, value))
            row = db.execute("SELECT value FROM account WHERE key = ?", (key,)).fetchone()
        return str(row["value"])

    # ---- positions ----------------------------------------------------------------------------
    def insert_position(self, row: dict[str, Any], journal_detail: dict[str, Any]) -> bool:
        """Open a position and journal it atomically; False when ``setup_id`` was already used."""
        cols = ", ".join(row)
        marks = ", ".join("?" for _ in row)
        try:
            with self._tx() as db:
                db.execute(f"INSERT INTO positions ({cols}) VALUES ({marks})", tuple(row.values()))
                self._journal(db, row["opened_at"], "OPENED", row["id"], journal_detail)
        except sqlite3.IntegrityError:
            return False
        return True

    def close_position(
        self, position_id: str, fields: dict[str, Any], journal_detail: dict[str, Any]
    ) -> bool:
        """Close an OPEN position and journal it atomically; False when it was not open."""
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._tx() as db:
            cur = db.execute(
                f"UPDATE positions SET {sets}, status = 'CLOSED' WHERE id = ? AND status = 'OPEN'",
                (*fields.values(), position_id),
            )
            if cur.rowcount != 1:
                return False
            self._journal(db, fields["closed_at"], "CLOSED", position_id, journal_detail)
        return True

    def touch_position(self, position_id: str, last_bar_us: int, mae: float, mfe: float) -> None:
        with self._tx() as db:
            db.execute(
                "UPDATE positions SET last_bar_us = ?, mae_points = ?, mfe_points = ? "
                "WHERE id = ? AND status = 'OPEN'",
                (last_bar_us, mae, mfe, position_id),
            )

    def positions(self, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        where, args = ("WHERE status = ?", (status,)) if status else ("", ())
        with self._lock:
            rows = self._db.execute(
                f"SELECT * FROM positions {where} ORDER BY opened_at DESC, id DESC LIMIT ?",
                (*args, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def position(self, position_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._db.execute(
                "SELECT * FROM positions WHERE id = ?", (position_id,)
            ).fetchone()
        return None if row is None else dict(row)

    def all_positions_oldest_first(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM positions ORDER BY opened_at, id").fetchall()
        return [dict(r) for r in rows]

    # ---- journal ------------------------------------------------------------------------------
    def append_journal(
        self, ts: datetime, kind: str, position_id: str | None, detail: dict[str, Any]
    ) -> None:
        with self._tx() as db:
            self._journal(db, _iso(ts), kind, position_id, detail)

    @staticmethod
    def _journal(
        db: sqlite3.Connection, ts: str, kind: str, position_id: str | None, detail: dict[str, Any]
    ) -> None:
        db.execute(
            "INSERT INTO journal (ts, kind, position_id, detail) VALUES (?, ?, ?, ?)",
            (ts, kind, position_id, json.dumps(detail, sort_keys=True, default=str)),
        )

    def revision(self) -> int:
        """Highest journal sequence: changes whenever a position opens or closes."""
        with self._lock:
            row = self._db.execute("SELECT COALESCE(MAX(seq), 0) AS r FROM journal").fetchone()
        return int(row["r"])

    def journal(self, limit: int = 200) -> list[JournalRow]:
        with self._lock:
            rows = self._db.execute(
                "SELECT * FROM journal ORDER BY seq DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            JournalRow(
                seq=int(r["seq"]),
                ts=datetime.fromisoformat(r["ts"]),
                kind=str(r["kind"]),
                position_id=r["position_id"],
                detail=json.loads(r["detail"]),
            )
            for r in rows
        ]


class _Tx:
    """``BEGIN IMMEDIATE`` ... ``COMMIT`` (or ``ROLLBACK`` on error), holding the store lock."""

    def __init__(self, db: sqlite3.Connection, lock: threading.RLock) -> None:
        self._db, self._lock = db, lock

    def __enter__(self) -> sqlite3.Connection:
        self._lock.acquire()
        self._db.execute("BEGIN IMMEDIATE")
        return self._db

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        try:
            self._db.execute("COMMIT" if exc_type is None else "ROLLBACK")
        finally:
            self._lock.release()
