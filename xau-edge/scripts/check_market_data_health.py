"""Health gate for the market data platform (exit 0 only when GOOD; non-zero when unsafe).

    uv run python scripts/check_market_data_health.py [--allow-degraded]

Reads the collector status file (no MT5 connection needed). A missing or stale file is UNKNOWN or
STALE, never GOOD. A closed market is not a failure: the collector reports bar freshness accordingly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.market_data.collector import read_status_file  # noqa: E402

EXIT = {"GOOD": 0, "DEGRADED": 1, "STALE": 2, "DISCONNECTED": 3, "UNKNOWN": 4}
KEYS = (
    "health",
    "reasons",
    "market_status",
    "collector_running",
    "stale_timeframes",
    "last_closed",
    "stored_rows",
    "updated_at",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--max-age", type=float, default=60.0)
    parser.add_argument("--allow-degraded", action="store_true")
    args = parser.parse_args()
    status = read_status_file(args.root / "collector_status.json", max_age_seconds=args.max_age)
    print(json.dumps({k: status.get(k) for k in KEYS}, indent=2, default=str))
    code = EXIT.get(str(status.get("health")), 4)
    return 0 if code == 0 or (code == 1 and args.allow_degraded) else code


if __name__ == "__main__":
    raise SystemExit(main())
