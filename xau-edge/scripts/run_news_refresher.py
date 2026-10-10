"""Keep the news calendar fresh: run ``news_update.py`` every few minutes, which itself skips unless due.

    uv run python scripts/run_news_refresher.py [--every-minutes 15] [--refresh-hours 4]

A child of ``run_market_stack.py`` (the supervisor restarts it). The update script owns the safety
rules (atomic write, never shrink coverage, rate-limit guard); a failed run leaves the old file and
the API shows the calendar as STALE once it is too old. Nothing here talks to MT5.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--every-minutes", type=float, default=15.0)
    parser.add_argument("--refresh-hours", type=float, default=4.0)
    args = parser.parse_args()
    command = [
        sys.executable,
        str(ROOT / "scripts" / "news_update.py"),
        "--min-interval-minutes",
        str(args.refresh_hours * 60),
    ]
    while True:
        result = subprocess.run(command, cwd=ROOT, check=False)  # noqa: S603
        print(f"news refresher: update exited {result.returncode}", flush=True)
        time.sleep(args.every_minutes * 60)


if __name__ == "__main__":
    raise SystemExit(main())
