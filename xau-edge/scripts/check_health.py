"""Health check for an external watcher (Task Scheduler, cron, uptime monitor).

    uv run python scripts/check_health.py

Prints the alerts and exits 0 when there is no critical alert, 1 otherwise. A missing status, a
stale heartbeat, a tripped kill switch, a dirty reconciliation or an unreachable terminal are all
critical or warning conditions, never "all clear". Each run also appends the alerts to
``data/execution/alerts.jsonl``.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.config import Settings
from xau_edge.execution.state import ExecutionState, StateError
from xau_edge.execution.status import evaluate_health, read_status


def main() -> int:
    settings = Settings()
    now = datetime.now(UTC)
    exec_dir = Path("data/execution")
    try:
        status = read_status(exec_dir / "status.json")
    except ValueError as exc:
        print(f"CRITICAL STATUS_UNREADABLE: {exc}")
        return 1
    state: ExecutionState | None = None
    if settings.demo_state_path.exists():
        try:
            state = ExecutionState(settings.demo_state_path)
        except StateError as exc:
            print(f"CRITICAL STATE_UNAVAILABLE: {exc}")
            return 1
    alerts = evaluate_health(status, state, now)
    for alert in alerts:
        print(f"{alert.severity.upper()} {alert.code}: {alert.message}")
    if not alerts:
        print("OK")
    if alerts:
        with (exec_dir / "alerts.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"at": now.isoformat(), "alerts": [a.__dict__ for a in alerts]}) + "\n"
            )
    return 1 if any(a.severity == "critical" for a in alerts) else 0


if __name__ == "__main__":
    sys.exit(main())
