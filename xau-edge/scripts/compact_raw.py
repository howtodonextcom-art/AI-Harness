"""Compact the raw store into monthly Parquet files (run while the bot is idle, e.g. weekend).

    uv run python scripts/compact_raw.py --dry-run
    uv run python scripts/compact_raw.py --root data/raw

Old files are verified, then MOVED (never deleted) to data/raw/_archive/... with a manifest.
"""

from __future__ import annotations

import argparse
import sys

from xau_edge.market_data.compact import CompactionError, compact_all


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/raw")
    parser.add_argument("--min-files", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        results = compact_all(args.root, min_files=args.min_files, dry_run=args.dry_run)
    except CompactionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for r in results:
        note = f" ({r.skipped_reason})" if r.skipped_reason else ""
        tag = "DRY-RUN " if r.dry_run else ""
        print(
            f"{tag}{r.symbol} {r.timeframe.value}: {r.files_before} -> {r.files_after} files, "
            f"{r.rows} rows, archived {r.archived}{note}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
