"""P0 forensics on the research H1 history: clock and data quality per year (Class D).

Reads the ``timestamp`` column ONLY (never a price), so the output cannot be outcome evidence.
Writes ``docs/research/edge-program-v2/clock-certificate.json`` and prints a table.

    uv run python scripts/forensics_p0.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_edge.forensics.clock import certificate, clock_by_year, year_quality  # noqa: E402
from xau_edge.market_data.profiles import BrokerProfile  # noqa: E402

HISTORY = ROOT / "data" / "research_history" / "XAUUSD" / "H1"
CERT = ROOT / "docs" / "research" / "edge-program-v2" / "clock-certificate.json"
QUALITY = ROOT / "docs" / "research" / "edge-program-v2" / "data-quality-by-year.json"


def _held(value: float | None) -> str:
    return "  -" if value is None else f"{value:4.2f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="write the JSON artefacts")
    args = parser.parse_args()
    files = sorted(HISTORY.glob("*.parquet"))
    if not files:
        print("no research history H1 file found")
        return 1
    ts = pl.read_parquet(files[-1], columns=["timestamp"])["timestamp"].sort()
    calendar = BrokerProfile.from_yaml(ROOT / "configs" / "brokers" / "ftmo_demo.yaml")
    cal = calendar.validation.calendar

    def closed(series: pl.Series) -> pl.Series:
        return pl.DataFrame({"t": series}).select(cal.closed_expr(pl.col("t")).alias("c"))["c"]

    clocks = clock_by_year(ts)
    years = ts.dt.year()
    quality = [year_quality(c.year, ts.filter(years == c.year), closed) for c in clocks]
    print("year weeks close frac open frac dst-wk ny-held certified missing in-closure gaps")
    for c, q in zip(clocks, quality, strict=True):
        cm = (
            "-"
            if c.close_mode_minute is None
            else f"{c.close_mode_minute // 60}:{c.close_mode_minute % 60:02d}"
        )
        om = (
            "-"
            if c.open_mode_minute is None
            else f"{c.open_mode_minute // 60}:{c.open_mode_minute % 60:02d}"
        )
        print(
            f"{c.year}  {c.weeks:5d}  {cm:>8}  {c.close_fraction:4.2f}  {om:>7}  "
            f"{c.open_fraction:4.2f}  {c.mismatch_weeks:3d}  {_held(c.ny_anchored_mismatch_fraction)}  "
            f"{c.certified!s:9}  {q.missing_fraction:6.3f}  "
            f"{q.bars_inside_closure:9d}  {q.gaps_over_limit:4d}"
        )
    if args.write:
        CERT.parent.mkdir(parents=True, exist_ok=True)
        CERT.write_text(json.dumps(certificate(clocks), indent=2) + "\n", encoding="utf-8")
        QUALITY.write_text(
            json.dumps([q.__dict__ for q in quality], indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {CERT.name} and {QUALITY.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
