"""Live-cadence parity: the production engine stepped every M1 close vs the M5-cadence engine.

Usage: ``uv run python scripts/trade_m1_parity.py --version 1.2.1 --start 2025-12-05T12:00 --end 2025-12-05T18:00``

Burned windows only (2025-05-01..2026-04-30). At every M5 close the M1-stepped engine, the
M5-stepped engine and an independent ``evaluate`` must agree exactly; the report also lists
actionable decisions that appear only between M5 closes (M1 execution timing) and any
setup announced twice. Exit code 1 on any unexplained mismatch.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from xau_edge.ops.priority import lower_priority
from xau_edge.trading.acceptance import m1_parity


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.2.1", choices=["1.1.0", "1.2.0", "1.2.1"])
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--root", default="data/market")
    parser.add_argument("--out", default="data/trade/parity")
    args = parser.parse_args()
    lower_priority()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC)
    with tempfile.TemporaryDirectory(prefix="xau-parity-") as work:
        report = m1_parity(Path(args.root), Path(work), args.version, start, end)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    name = f"parity_{args.version}_{start:%Y%m%dT%H%M}_{end:%Y%m%dT%H%M}.json"
    (out / name).write_text(json.dumps(asdict(report), indent=1, default=str), encoding="utf-8")
    print(
        f"{'PASS' if report.passed else 'FAIL'} v{args.version} {args.start}..{args.end}: "
        f"{report.m1_steps} M1 steps, {report.m5_compared} M5 closes compared, "
        f"{len(report.mismatches)} mismatches, {report.actionable_at_m5} actionable at M5, "
        f"{len(report.m1_only_actionable)} M1-only actionable, "
        f"{len(report.duplicate_alerts)} duplicate alerts"
    )
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
