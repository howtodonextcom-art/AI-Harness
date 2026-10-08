"""Operator commands for the persistent kill switch (no HTTP route, ADR-0019).

``status`` prints the state, ``trip`` latches it, ``reset`` clears it and needs the exact
confirmation phrase. Every change is also written to the execution journal.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from xau_edge.execution.journal import ExecutionJournal
from xau_edge.execution.runner import JournalError
from xau_edge.execution.state import ExecutionState, StateError
from xau_edge.risk.kill_switch import RESET_PHRASE


def run(argv: Sequence[str], *, state_path: Path, journal_path: Path) -> int:
    """Run one command; returns the process exit code (0 ok, 2 refused, 3 state error)."""
    parser = argparse.ArgumentParser(prog="kill_switch")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    trip = sub.add_parser("trip")
    trip.add_argument("--reason", required=True)
    reset = sub.add_parser("reset")
    reset.add_argument("--confirm", required=True, help=f"must be exactly {RESET_PHRASE!r}")
    args = parser.parse_args(list(argv))
    try:
        state = ExecutionState(state_path)
        journal = ExecutionJournal(journal_path)
        if args.command == "status":
            tripped, reason = state.kill_switch_state()
            print(
                f"kill switch: {'TRIPPED' if tripped else 'clear'}"
                + (f" ({reason})" if tripped else "")
            )
            return 0
        if args.command == "trip":
            state.trip_kill_switch(args.reason)  # safety first: latch before any bookkeeping
            print("kill switch tripped; open positions are NOT closed (handle them manually)")
            try:
                journal.record("kill_switch.trip", reason=args.reason, source="cli")
            except JournalError as exc:
                print(f"warning: the trip could not be journalled: {exc}")
            return 0
        if args.confirm != RESET_PHRASE:
            print(f"refused: --confirm must be exactly {RESET_PHRASE!r}")
            return 2
        journal.record("kill_switch.reset", source="cli")
        state.reset_kill_switch(confirm=args.confirm)
        print("kill switch cleared")
        return 0
    except (StateError, JournalError) as exc:
        print(f"error: {exc}")
        return 3
