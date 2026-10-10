"""Rebuild and verify the paper desk's state from its append-only journal.

The journal is the commit log: a paper trade EXISTS if and only if ``paper.open`` is in it, and the
state file (``paper_desk.json``) is a snapshot that must agree with it. Write order in the desk:

    paper.pending (intent, fsync) -> broker fill (memory) -> paper.open (fsync, commit)
        -> atomic state snapshot

so a crash leaves one of three recognisable situations:

* intent only (crash before the fill was committed): no position exists anywhere; the intent is an
  ORPHAN and is closed with a ``paper.abort`` line (the setup stays consumed: never a duplicate);
* journal ahead of the snapshot (crash between the commit and the snapshot, or an older snapshot
  restored): the journal is right and the snapshot is stale: the desk FAILS CLOSED until the owner
  runs ``scripts/paper_recover.py`` (dry-run, then ``--apply``);
* snapshot ahead of the journal: impossible without tampering: FAILS CLOSED.

Nothing here invents a trade. A state rebuilt from the journal contains only what the journal
committed; the in-flight excursions (MFE / MAE) of an open trade and ``last_bar`` are the only
things lost, and they are reported.
"""

from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xau_edge.market_data.atomic import atomic_write_text

STATE_FILE = "paper_desk.json"
JOURNAL_FILE = "paper_journal.jsonl"


@dataclass
class Replay:
    """What the journal says happened."""

    trades: dict[str, dict[str, Any]] = field(default_factory=dict)
    positions: dict[str, dict[str, Any]] = field(default_factory=dict)  # broker position json
    closed: list[dict[str, Any]] = field(default_factory=list)  # broker ClosedTrade json
    orphans: list[str] = field(default_factory=list)  # intents that never committed
    problems: list[str] = field(default_factory=list)
    events: int = 0


def read_journal(path: Path) -> tuple[list[dict[str, Any]], int]:
    """Journal events in order and the number of unreadable lines (a torn last line is skipped)."""
    if not path.exists():
        return [], 0
    out: list[dict[str, Any]] = []
    bad = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if isinstance(value, dict) and "event" in value:
            out.append(value)
        else:
            bad += 1
    return out, bad


def replay_journal(path: Path) -> Replay:  # noqa: PLR0912 - one branch per journal event
    events, bad = read_journal(path)
    rep = Replay(events=len(events))
    if bad > 1:
        rep.problems.append(f"{bad} unreadable journal lines (only a torn LAST line is tolerated)")
    pending: dict[str, str] = {}
    for ev in events:
        kind = str(ev["event"])
        tid = ev.get("trade_id")
        if kind == "paper.pending" and tid:
            rep.trades[tid] = {k: v for k, v in ev.items() if k not in ("event", "at")}
            pending[tid] = ev.get("setup_id", "?")
        elif kind == "paper.open" and tid:
            rec = {k: v for k, v in ev.items() if k not in ("event", "at")}
            rep.trades[tid] = rec
            pending.pop(tid, None)
            position = rec.get("broker_position")
            if not isinstance(position, dict):
                rep.problems.append(f"{tid}: paper.open carries no broker position (old journal)")
            else:
                rep.positions[str(position["position_id"])] = position
        elif kind == "paper.cancel" and tid:
            rep.trades[tid] = {k: v for k, v in ev.items() if k not in ("event", "at")}
            pending.pop(tid, None)
        elif kind == "paper.abort" and tid:
            rec = rep.trades.get(tid, {"trade_id": tid, "setup_id": ev.get("setup_id")})
            rec.update(status="CANCELLED", cancel_reason=ev.get("why", "ABORTED"))
            rep.trades[tid] = rec
            pending.pop(tid, None)
        elif kind == "paper.modify" and tid and tid in rep.trades:
            rec = rep.trades[tid]
            rec["sl"] = ev.get("sl", rec.get("sl"))
            rec["stage"] = ev.get("stage", rec.get("stage"))
            pid = rec.get("position_id")
            if pid in rep.positions and ev.get("sl") is not None:
                rep.positions[pid]["stop_loss"] = ev["sl"]
        elif kind == "paper.close" and tid:
            rec = {k: v for k, v in ev.items() if k not in ("event", "at")}
            rep.trades[tid] = rec
            closed = rec.get("broker_closed")
            if not isinstance(closed, dict):
                rep.problems.append(f"{tid}: paper.close carries no broker trade (old journal)")
            else:
                rep.closed.append(closed)
            rep.positions.pop(str(rec.get("position_id")), None)
    rep.orphans = sorted(pending)
    return rep


def state_from_replay(rep: Replay, *, initial_capital: float, saved_at: datetime) -> dict[str, Any]:
    """The state snapshot the journal implies (JSON-safe, same shape as the desk's own)."""
    counter = 0
    for pid in [*rep.positions, *(str(c.get("position_id")) for c in rep.closed)]:
        if pid.startswith("p") and pid[1:].isdigit():
            counter = max(counter, int(pid[1:]))
    order_ids = sorted(
        f"paper-{t['setup_id']}"
        for t in rep.trades.values()
        if t.get("position_id") and t.get("setup_id")
    )
    balance = initial_capital + sum(float(c["net_pnl"]) for c in rep.closed)
    return {
        "version": 1,
        "saved_at": saved_at.astimezone(UTC).isoformat(),
        "last_bar": None,
        "broker": {
            "balance": balance,
            "counter": counter,
            "order_ids": order_ids,
            "positions": list(rep.positions.values()),
            "closed": rep.closed,
            "quote": None,
        },
        "trades": rep.trades,
    }


def diff_against_state(
    rep: Replay, state: dict[str, Any] | None, *, initial_capital: float
) -> list[str]:
    """Human-readable differences between the journal and a state snapshot (empty = they agree)."""
    out: list[str] = list(rep.problems)
    if state is None:
        if any(t.get("status") in ("OPEN", "CLOSED") for t in rep.trades.values()):
            out.append("the journal has committed trades but there is no state snapshot")
        return out
    try:
        trades: dict[str, dict[str, Any]] = state["trades"]
        broker: dict[str, Any] = state["broker"]
    except (KeyError, TypeError):
        return [*out, "the state snapshot has no trades/broker section"]
    for tid in sorted(set(rep.trades) | set(trades)):
        a, b = rep.trades.get(tid), trades.get(tid)
        if b is None and tid in rep.orphans:
            continue  # an intent that never committed is not a trade (it is closed as an orphan)
        if a is None:
            out.append(f"{tid}: in the state but never journalled")
        elif b is None:
            out.append(f"{tid}: journalled ({a.get('status')}) but missing from the state")
        elif a.get("status") != b.get("status"):
            out.append(f"{tid}: journal says {a.get('status')}, state says {b.get('status')}")
    snap_positions = {str(p["position_id"]) for p in broker.get("positions", [])}
    if snap_positions != set(rep.positions):
        out.append(
            f"open broker positions differ: journal {sorted(rep.positions)} "
            f"vs state {sorted(snap_positions)}"
        )
    if len(broker.get("closed", [])) != len(rep.closed):
        out.append(
            f"closed trades differ: journal {len(rep.closed)} "
            f"vs state {len(broker.get('closed', []))}"
        )
    expected = initial_capital + sum(float(c["net_pnl"]) for c in rep.closed)
    if not math.isclose(float(broker.get("balance", math.nan)), expected, abs_tol=1e-6):
        out.append(
            f"balance differs: journal implies {expected:.6f}, state has {broker.get('balance')}"
        )
    return out


@dataclass
class RecoveryReport:
    root: str
    ok: bool
    differences: list[str]
    orphans: list[str]
    applied: bool = False
    backup: str | None = None
    notes: list[str] = field(default_factory=list)


def recover(
    root: Path | str, *, initial_capital: float, apply: bool = False, now: datetime | None = None
) -> RecoveryReport:
    """Verify the state against the journal; with ``apply`` replace it by the journal's state.

    Dry-run by default. ``apply`` keeps the old state as ``paper_desk.json.bak-<time>`` and writes
    a ``paper.recovered`` journal line. It refuses when the journal itself is not trustworthy
    (old format, unreadable lines): in that case nothing is touched.
    """
    base = Path(root)
    stamp = now or datetime.now(UTC)
    rep = replay_journal(base / JOURNAL_FILE)
    state_path = base / STATE_FILE
    state: dict[str, Any] | None = None
    notes: list[str] = []
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except ValueError:
            notes.append("the state snapshot is unreadable; the journal is the only evidence")
    differences = diff_against_state(rep, state, initial_capital=initial_capital)
    report = RecoveryReport(
        str(base), not differences and not rep.orphans, differences, rep.orphans, notes=notes
    )
    if rep.problems:
        report.notes.append(
            "the journal is not complete enough to rebuild from: nothing was changed"
        )
        return report
    if not apply:
        return report
    for (
        tid
    ) in rep.orphans:  # an intent that never committed: nothing exists, the setup stays consumed
        rep.trades[tid].update(status="CANCELLED", cancel_reason="CRASH_BEFORE_COMMIT")
    rebuilt = state_from_replay(rep, initial_capital=initial_capital, saved_at=stamp)
    if state_path.exists():
        backup = state_path.with_name(f"{state_path.name}.bak-{stamp:%Y%m%dT%H%M%S}")
        shutil.copy2(state_path, backup)
        report.backup = backup.name
    atomic_write_text(state_path, json.dumps(rebuilt, default=str))
    with (base / JOURNAL_FILE).open("a", encoding="utf-8") as handle:
        for tid in rep.orphans:
            abort: dict[str, Any] = {
                "event": "paper.abort",
                "at": stamp.astimezone(UTC).isoformat(),
                "trade_id": tid,
                "setup_id": rep.trades[tid].get("setup_id"),
                "why": "CRASH_BEFORE_COMMIT",
            }
            handle.write(json.dumps(abort, sort_keys=True) + "\n")
        handle.write(
            json.dumps(
                {
                    "event": "paper.recovered",
                    "at": stamp.astimezone(UTC).isoformat(),
                    "differences": differences,
                    "orphans": rep.orphans,
                },
                sort_keys=True,
            )
            + "\n"
        )
    report.applied = True
    report.notes.append(
        "MFE/MAE progress of an open trade and last_bar are not in the journal: they restart"
    )
    return report
