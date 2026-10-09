"""Event COUNTS per Batch A variant on Development-2 (Class D: frequencies, no outcomes).

Never calls ``compute_outcomes``; reads prices only to detect events. Output feeds the
pre-registration (expected N, MDE).

    uv run python scripts/v2_event_counts.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

from xau_edge.evaluation.edge_program import load_research_data  # noqa: E402
from xau_edge.integrity.dependence import dependence_report  # noqa: E402
from xau_edge.research_v2.batch_a import frame_for, in_window, variants  # noqa: E402

RAW = ROOT / "data" / "research_history"
MANIFEST = ROOT / "docs" / "research" / "edge-program" / "data-manifest.json"
OUT = ROOT / "docs" / "research" / "edge-program-v2" / "event-counts-dev2.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = load_research_data(RAW, MANIFEST)
    frame, h4, first = frame_for(data.h1, data.h4, "dev2")
    rows = []
    for variant in variants():
        events = in_window(variant.build(frame, h4), first)
        years = Counter(int(frame.year[d]) for d in events.decision)
        days = frame.day[events.decision + 1] if events.n else np.array([], dtype=np.int64)
        dummy = np.zeros(events.n)
        eff = (
            dependence_report(dummy, days).unique_days if events.n else 0
        )  # unique trading days: an upper bound on independent events
        rows.append(
            {
                "variant": variant.id,
                "hypothesis": variant.hypothesis,
                "events": events.n,
                "unique_days": int(eff),
                "excluded_clock_unsafe": events.excluded_unsafe,
                "by_year": dict(sorted(years.items())),
            }
        )
        print(
            f"{variant.id:22s} events={events.n:5d} days={eff:5d} unsafe_excluded={events.excluded_unsafe}"
        )
    if args.write:
        OUT.write_text(
            json.dumps(
                {
                    "class": "D (event frequencies on Development-2; no outcomes computed)",
                    "dataset_ids": data.dataset_ids,
                    "variants": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {OUT.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
