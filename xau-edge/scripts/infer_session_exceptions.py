"""Infer holiday / early-close closures from the broker's missing native bars (FTMO XAUUSD).

    uv run python scripts/infer_session_exceptions.py [--write]

Reads the stored bars of every timeframe, finds stretches the weekly template calls OPEN where the
broker has no bars, and classifies them (HOLIDAY, EARLY_CLOSE, UNCLASSIFIED). Only explained
stretches are written to ``configs/brokers/ftmo_session_exceptions.yaml``; UNCLASSIFIED absences are
listed in the report and remain data gaps. Idempotent: rerun after each backfill.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.domain.timeframe import Timeframe  # noqa: E402
from xau_edge.market_data.calendars import DEFAULT_EXCEPTIONS, ftmo_profile  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.session_exceptions import (  # noqa: E402
    Absence,
    closures_from,
    dump_closures,
    find_absences,
)

HEADER = (
    "# Holiday / early-close closures inferred from FTMO's own absent native bars by\n"
    "# scripts/infer_session_exceptions.py (reasons from date rules, never from a fixed year list).\n"
    "# UNCLASSIFIED absences are deliberately NOT here: they stay data gaps."
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data" / "market")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    calendar = ftmo_profile().validation.calendar  # the template alone, without closures
    ledger = BarLedger(args.root)
    absences: list[Absence] = []
    per_tf: dict[str, Any] = {}
    for tf in Timeframe:
        found = find_absences(ledger.load("XAUUSD", tf), tf, calendar)
        absences += found
        counts: dict[str, int] = {}
        for a in found:
            counts[a.reason] = counts.get(a.reason, 0) + 1
        per_tf[tf.value] = counts
    windows = closures_from(absences)
    unexplained = [a for a in absences if a.reason == "UNCLASSIFIED"]
    report = {
        "per_timeframe": per_tf,
        "closures_written": len(windows),
        "unclassified": len(unexplained),
        "unclassified_examples": [
            {"start": a.start.isoformat(), "end": a.end.isoformat(), "open_slots": a.open_slots}
            for a in sorted(unexplained, key=lambda a: -a.open_slots)[:15]
        ],
    }
    print(json.dumps(report, indent=2))
    if args.write:
        dump_closures(DEFAULT_EXCEPTIONS, windows, HEADER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
