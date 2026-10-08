"""Trip, inspect or reset the persistent kill switch.

    uv run python scripts/kill_switch.py status
    uv run python scripts/kill_switch.py trip --reason "manual stop"
    uv run python scripts/kill_switch.py reset --confirm "I understand the risk"

A tripped switch blocks NEW orders only; it never closes positions (ADR-0019).
"""

from __future__ import annotations

import sys

from xau_edge.config import Settings
from xau_edge.execution.cli import run


def main() -> int:
    settings = Settings()
    return run(
        sys.argv[1:],
        state_path=settings.demo_state_path,
        journal_path=settings.demo_journal_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
