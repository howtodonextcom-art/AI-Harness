"""Window locks and the K ledger for ML V0 (ADR-V2-007).

* The development/validation code can only see bars whose label completes before ``2022-01-01``;
  asking for more raises ``WindowLockError``.
* Test-H and Holdout open **once each**, and only with (a) an owner approval file that names the
  frozen spec hash and the K family, and (b) a K-ledger with no earlier look at that window. The
  look is written to the ledger BEFORE any data is read, so a crash still counts as the one run.
* The ledger is append-only JSON; it records every look at a confirmatory window.

Nothing in this module reads market data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
ML_DIR = ROOT / "docs" / "ml"
SPEC = ML_DIR / "ml_v0_spec.json"
LEDGER = ML_DIR / "k_ledger.json"
APPROVALS = ML_DIR / "approvals"

DEV_UNTIL = datetime(2022, 1, 1, tzinfo=UTC)
WINDOWS: dict[str, tuple[datetime, datetime]] = {
    "TEST_H": (datetime(2022, 1, 1, tzinfo=UTC), datetime(2025, 5, 1, tzinfo=UTC)),
    "HOLDOUT": (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)),
}
FAMILY = "K_V2_VOL_V0"


class WindowLockError(RuntimeError):
    """A locked window (or an unapproved confirmatory run) was requested."""


def spec_hash(path: Path = SPEC) -> str:
    """Canonical (EOL-independent) sha256 of the frozen spec, same as ``scripts/freeze_hash.py``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    text = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_development_window(until: datetime) -> None:
    """Development and validation code may not see bars past the Test-H start."""
    if until > DEV_UNTIL:
        msg = (
            f"requested data until {until.isoformat()} but only < {DEV_UNTIL.date()} is open: "
            "Test-H and Holdout are locked (one run each, owner approval + K ledger)"
        )
        raise WindowLockError(msg)


# ---- ledger -------------------------------------------------------------------------------------
def load_ledger(path: Path = LEDGER) -> dict[str, Any]:
    if not path.exists():
        return {"families": {}, "events": []}
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomic on the same volume


def append_event(
    kind: str, detail: dict[str, Any], *, path: Path = LEDGER, now: datetime | None = None
) -> None:
    """Append one event (the ledger has no edit or delete)."""
    data = load_ledger(path)
    data["events"].append(
        {"ts": (now or datetime.now(UTC)).isoformat(), "kind": kind, "detail": detail}
    )
    _write(path, data)


def close_family(
    family: str, reason: str, *, path: Path = LEDGER, now: datetime | None = None
) -> None:
    """Mark a K family closed (no confirmatory window may be opened for it) and record why."""
    data = load_ledger(path)
    if family not in data["families"]:
        msg = f"unknown family {family!r}"
        raise WindowLockError(msg)
    data["families"][family]["status"] = "CLOSED"
    data["families"][family]["closed_reason"] = reason
    data["events"].append(
        {
            "ts": (now or datetime.now(UTC)).isoformat(),
            "kind": "FAMILY_CLOSED",
            "detail": {"family": family, "reason": reason, "confirmatory_looks": 0},
        }
    )
    _write(path, data)


def looks_at(window: str, *, path: Path = LEDGER) -> int:
    """How many times the ledger says ``window`` was opened (started, even if it crashed)."""
    return sum(
        1
        for e in load_ledger(path)["events"]
        if e["kind"] == "CONFIRMATORY_LOOK" and e["detail"].get("window") == window
    )


@dataclass(frozen=True)
class Unlock:
    """Proof that a confirmatory window may be read exactly once (issued by ``issue_unlock``)."""

    window: str
    run_id: str
    spec_hash: str


def issue_unlock(
    window: str,
    *,
    approvals: Path = APPROVALS,
    ledger: Path = LEDGER,
    spec: Path = SPEC,
    now: datetime | None = None,
) -> Unlock:
    """Check the approval and the ledger, then record the look and return the unlock token."""
    if window not in WINDOWS:
        msg = f"unknown confirmatory window {window!r}"
        raise WindowLockError(msg)
    approval_file = approvals / f"{window.lower()}_approval.json"
    if not approval_file.exists():
        msg = f"{window} is locked: no owner approval file at {approval_file.name}"
        raise WindowLockError(msg)
    approval = json.loads(approval_file.read_text(encoding="utf-8"))
    current = spec_hash(spec)
    if approval.get("spec_hash") != current or approval.get("family") != FAMILY:
        msg = f"{window} approval does not match the frozen spec hash / K family"
        raise WindowLockError(msg)
    if not approval.get("approved_by") or not approval.get("approved_at"):
        msg = f"{window} approval lacks approved_by / approved_at"
        raise WindowLockError(msg)
    family = load_ledger(ledger)["families"].get(FAMILY)
    if family is not None and family.get("status") == "CLOSED":
        msg = f"the K family {FAMILY} is CLOSED: {family.get('closed_reason')}"
        raise WindowLockError(msg)
    if family is None or family.get("spec_hash") != current:
        msg = "the K family is not recorded in the ledger for this spec hash"
        raise WindowLockError(msg)
    if looks_at(window, path=ledger) >= 1:
        msg = f"{window} was already opened once: no second run is allowed"
        raise WindowLockError(msg)
    run_id = hashlib.sha256(
        f"{window}|{current}|{(now or datetime.now(UTC)).isoformat()}".encode()
    ).hexdigest()[:16]
    append_event(
        "CONFIRMATORY_LOOK",
        {
            "window": window,
            "run_id": run_id,
            "spec_hash": current,
            "approved_by": approval["approved_by"],
        },
        path=ledger,
        now=now,
    )  # written BEFORE any data is read
    return Unlock(window=window, run_id=run_id, spec_hash=current)
