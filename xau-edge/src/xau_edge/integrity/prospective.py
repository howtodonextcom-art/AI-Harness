"""Prospective evidence ledger (roadmap section 21): sealed BEFORE the outcome exists.

An append-only JSON-lines file where every record carries the hash of the previous one. A SIGNAL is
sealed with its decision, SL, TP and expected R at ``created_at``; the result comes later as an
OUTCOME record that refers to it. ``verify`` re-derives every hash and every ordering rule; the UI
may show "SEALED BEFORE OUTCOME" only when it returns VALID. Nothing here fabricates records.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from xau_edge.integrity.canonical import canonical_hash, canonical_json

GENESIS: Final = "0" * 64
VALID: Final = "VALID"
INVALID: Final = "INVALID"
UNKNOWN: Final = "UNKNOWN"
EMPTY: Final = "NO PROSPECTIVE EVIDENCE YET"

MAX_BYTES: Final = 16_000_000
MAX_SKEW: Final = 300.0
SIGNAL_FIELDS: Final = (
    "record_id",
    "kind",
    "created_at",
    "decision_available_at",
    "earliest_resolution_at",
    "strategy_id",
    "strategy_version",
    "config_hash",
    "dataset_hash",
    "feature_version",
    "code_commit",
    "market_regime",
    "decision",
    "direction",
    "entry_reference",
    "sl",
    "tp",
    "predicted_probabilities",
    "expected_r",
    "evidence_status",
)
_OUTCOME_MARKERS: Final = ("outcome", "realised", "realized", "pnl", "result", "exit_price")
_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


class LedgerError(RuntimeError):
    """An append was refused."""


def _when(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        msg = f"timestamp without a time zone: {value!r}"
        raise ValueError(msg)
    return parsed.astimezone(UTC)


def seal(body: dict[str, Any], previous_hash: str) -> dict[str, Any]:
    """Body plus ``previous_record_hash`` and ``record_hash`` (hash of everything else)."""
    record = {**body, "previous_record_hash": previous_hash}
    record["record_hash"] = canonical_hash(record)
    return record


def _hash_ok(record: dict[str, Any]) -> bool:
    claimed = record.get("record_hash")
    rest = {k: v for k, v in record.items() if k != "record_hash"}
    try:
        return claimed == canonical_hash(rest)
    except ValueError:
        return False


@dataclass(frozen=True)
class VerifyResult:
    """The verdict about a ledger file."""

    status: str
    records: int
    signals: int
    outcomes: int
    problems: tuple[str, ...]
    head_hash: str

    @property
    def sealed_before_outcome(self) -> bool:
        """True only when the whole chain verified and holds at least one signal."""
        return self.status == VALID and self.signals > 0


def _check_signal(record: dict[str, Any], problems: list[str], line: int) -> None:
    missing = [f for f in SIGNAL_FIELDS if f not in record]
    if missing:
        problems.append(f"line {line}: missing {', '.join(missing)}")
        return
    for key in record:
        if any(marker in key.lower() for marker in _OUTCOME_MARKERS):
            problems.append(f"line {line}: a signal carries outcome data ({key})")
    try:
        created = _when(record["created_at"])
        available = _when(record["decision_available_at"])
        earliest = _when(record["earliest_resolution_at"])
    except ValueError as exc:
        problems.append(f"line {line}: {exc}")
        return
    if created < available:
        problems.append(f"line {line}: sealed before its own decision was available")
    if created >= earliest:
        problems.append(f"line {line}: sealed at or after the earliest possible outcome")


def verify(path: Path, *, check_anchor: bool = True) -> VerifyResult:  # noqa: PLR0912, PLR0915 - one pass, one rule per branch
    """Re-derive the chain. Missing file: UNKNOWN. Empty file: VALID with zero records."""
    if not path.exists():
        return VerifyResult(UNKNOWN, 0, 0, 0, ("ledger file does not exist",), GENESIS)
    try:
        if path.stat().st_size > MAX_BYTES:
            return VerifyResult(UNKNOWN, 0, 0, 0, ("ledger file is too large to verify",), GENESIS)
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except (OSError, UnicodeDecodeError):
        return VerifyResult(UNKNOWN, 0, 0, 0, ("ledger file cannot be read",), GENESIS)
    problems: list[str] = []
    seen: dict[str, datetime] = {}
    earliest_of: dict[str, datetime] = {}
    answered: set[str] = set()
    previous = GENESIS
    last_time: datetime | None = None
    signals = outcomes = 0
    for number, text in enumerate(lines, start=1):
        try:
            record = json.loads(text)
        except json.JSONDecodeError:
            problems.append(f"line {number}: not valid JSON")
            break
        if not isinstance(record, dict):
            problems.append(f"line {number}: not an object")
            break
        if not _hash_ok(record):
            problems.append(f"line {number}: record hash does not match its content (modified)")
        if record.get("previous_record_hash") != previous:
            problems.append(f"line {number}: broken chain")
        previous = str(record.get("record_hash", ""))
        rid = str(record.get("record_id", ""))
        if not rid:
            problems.append(f"line {number}: no record_id")
        elif rid in seen:
            problems.append(f"line {number}: duplicate record_id {rid}")
        kind = record.get("kind")
        try:
            created = _when(record.get("created_at"))
        except ValueError as exc:
            problems.append(f"line {number}: {exc}")
            continue
        if last_time is not None and created < last_time:
            problems.append(f"line {number}: time inversion")
        last_time = created
        if kind == "SIGNAL":
            signals += 1
            _check_signal(record, problems, number)
            seen[rid] = created
            with contextlib.suppress(ValueError):
                earliest_of[rid] = _when(record.get("earliest_resolution_at"))
        elif kind == "OUTCOME":
            outcomes += 1
            ref = str(record.get("signal_id", ""))
            if ref not in earliest_of:
                problems.append(f"line {number}: outcome refers to an unknown signal")
            elif ref in answered:
                problems.append(f"line {number}: a second outcome for signal {ref}")
            else:
                answered.add(ref)
                try:
                    observed = _when(record.get("observed_at"))
                except ValueError as exc:
                    problems.append(f"line {number}: {exc}")
                else:
                    if observed <= seen[ref]:
                        problems.append(
                            f"line {number}: outcome observed before its signal was sealed"
                        )
                    elif observed < earliest_of[ref]:
                        problems.append(
                            f"line {number}: outcome observed before the earliest resolution"
                        )
            seen[rid] = created
        else:
            problems.append(f"line {number}: unknown kind {kind!r}")
    anchor = _read_anchor(path) if check_anchor else None
    if anchor is not None and (anchor["records"], anchor["head"]) != (len(lines), previous):
        if len(lines) < anchor["records"]:
            problems.append("ledger has fewer records than its last anchor (tail truncated)")
        else:
            problems.append("ledger head differs from its last anchor (rewritten)")
    status = INVALID if problems else VALID
    return VerifyResult(status, len(lines), signals, outcomes, tuple(problems), previous)


def anchor_path(path: Path) -> Path:
    """The head anchor beside a ledger (commit it to git to anchor the chain externally)."""
    return path.with_name(path.name + ".head")


def _read_anchor(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(anchor_path(path).read_text(encoding="utf-8"))
        return {"records": int(raw["records"]), "head": str(raw["head"])}
    except (OSError, ValueError, KeyError, TypeError):
        return None


class ProspectiveLedger:
    """Append-only writer. Refuses anything that would make the file fail ``verify``."""

    def __init__(self, path: Path, clock: Callable[[], datetime] | None = None) -> None:
        self.path = path
        self.clock = clock

    @classmethod
    def live(cls, path: Path) -> ProspectiveLedger:
        """The writer for real signals: ``created_at`` must match the system clock (5 min skew)."""
        return cls(path, clock=lambda: datetime.now(UTC))

    def _lock(self) -> threading.Lock:
        with _GUARD:
            return _LOCKS.setdefault(str(self.path.resolve()), threading.Lock())

    def append(self, body: dict[str, Any]) -> dict[str, Any]:
        """Seal and append one SIGNAL or OUTCOME body; raise ``LedgerError`` if it is not valid."""
        with self._lock():
            state = verify(self.path) if self.path.exists() else None
            if state is not None and state.status != VALID:
                msg = "the ledger does not verify; refusing to append: " + "; ".join(
                    state.problems[:3]
                )
                raise LedgerError(msg)
            head = GENESIS if state is None else state.head_hash
            if self.clock is not None:
                try:
                    skew = abs((_when(body.get("created_at")) - self.clock()).total_seconds())
                except ValueError as exc:
                    msg = f"record refused: {exc}"
                    raise LedgerError(msg) from exc
                if skew > MAX_SKEW:
                    msg = "record refused: created_at differs from the system clock (backdated)"
                    raise LedgerError(msg)
            record = seal(body, head)
            trial = canonical_json(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.open("a", encoding="utf-8").close()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(trial + "\n")
            after = verify(self.path, check_anchor=False)
            if after.status != VALID:
                self._rollback(trial)
                msg = "record refused: " + "; ".join(after.problems[:3])
                raise LedgerError(msg)
            self._write_anchor(after)
            return record

    def _write_anchor(self, state: VerifyResult) -> None:
        body = json.dumps({"records": state.records, "head": state.head_hash})
        anchor_path(self.path).write_text(body + chr(10), encoding="utf-8")

    def _rollback(self, trial: str) -> None:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if lines and lines[-1] == trial:
            lines.pop()
            self.path.write_text("".join(f"{ln}\n" for ln in lines), encoding="utf-8")
