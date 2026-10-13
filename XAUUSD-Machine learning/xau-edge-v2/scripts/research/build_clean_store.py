"""Build the derived CLEAN bar store and its manifest (ADR-V2-019). The raw store is read-only.

    uv run python scripts/research/build_clean_store.py --dump data/research/terminal_dump --out data/clean_store

The raw files are hashed BEFORE and AFTER the build; any change aborts. Only the windows decided at
Gate B2 are built (DEV' 2005-06..2018-12, VALIDATION' 2019-01..2021-01, RESERVED 2021-10..12);
2021-02..09 is quarantined; Confirm-C, Test-H and Holdout are never read.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import polars as pl  # noqa: E402

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))

from xau_edge_v2.config import Settings  # noqa: E402
from xau_edge_v2.research.clean_store import (  # noqa: E402
    SCHEMA,
    SCOPE,
    TFS,
    build_month,
    entry_for,
    manifest_hash,
    months_in_scope,
    sha256_file,
    sha256_json,
    window_of,
    write_month,
)
from xau_edge_v2.research.clean_view import (  # noqa: E402
    MEDIAN_MULTIPLE,
    MIN_TICK_VOLUME,
    ROLLOVER_HOURS,
)


def load_dump(path: Path) -> pl.DataFrame:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return pl.DataFrame(
        rows,
        schema=["t", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"],
        orient="row",
    )


def raw_fingerprint(raw_root: Path, months: list[str]) -> dict[str, dict[str, str]]:
    return {
        m: {
            tf: sha256_file(raw_root / tf / f"{m}.parquet")
            for tf in TFS
            if (raw_root / tf / f"{m}.parquet").exists()
        }
        for m in months
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--months", default="", help="comma list (default: every month in scope)")
    a = ap.parse_args()
    raw_root = Settings().data_root / "XAUUSD"
    out = Path(a.out)
    dump = Path(a.dump)
    t1, t4 = load_dump(dump / "XAUUSD_H1.json"), load_dump(dump / "XAUUSD_H4.json")
    months = [m for m in a.months.split(",") if m] or months_in_scope()
    before = raw_fingerprint(raw_root, months)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "adr": "ADR-V2-019",
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rule": {
            "pseudo_bar": f"minute 0 of UTC hour in {list(ROLLOVER_HOURS)}, spread 0, tick_volume >= max({MIN_TICK_VOLUME:.0f}, {MEDIAN_MULTIPLE:.0f} x median)",
            "h4": "restored from the broker re-fetch where it swallowed a pseudo-bar",
            "pass": "no residual pseudo-bar; M1->M5->M15/M30/H1->H4 synchronised >= 0.995; H4 identical to the re-fetch (<= 2021-01); H1 identical >= 0.999 (from 2009-09); ticks agree >= 0.97 (RESERVED)",
        },
        "scope": [{"from": lo, "to": hi, "window": w} for lo, hi, w in SCOPE],
        "terminal_refetch": {n: sha256_file(dump / f"XAUUSD_{n}.json") for n in ("H1", "H4", "D1")},
        "terminal_refetch_provenance": json.loads(
            (dump / "provenance.json").read_text(encoding="utf-8")
        ),
        "known_source_defects": {
            "ftmo_pseudo_bars": "FTMO history (bars as served today) holds one pseudo-bar per day 2012-06-26..2021-01-20; the re-fetch comes from MetaQuotes-Demo, which does not",
            "ftmo_ticks_2022-01-04_to_2022-03-21": "the stored FTMO TICKS of these days deviate from the bars and from MetaQuotes-Demo by up to 12 dollars; the BARS agree with MetaQuotes-Demo. Never use ticks of that window (spread or cost modelling) without re-checking",
        },
        "months": {},
    }
    dropped_rows: list[tuple[str, str, str]] = []
    for month in months:
        window = window_of(month)
        if window == "QUARANTINE":
            manifest["months"][month] = {
                "status": "QUARANTINED",
                "window": window,
                "reasons": ["owner decision (Gate B2): no independent source for 2021-02..09"],
                "files": {},
            }
            continue
        res = build_month(raw_root, month, t1, t4)
        files = write_month(res, out) if res.status == "PASS" else {}
        entry = entry_for(res, before[month], files)
        for tf, stamps in res.dropped.items():
            dropped_rows += [
                (month, tf, datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d %H:%M"))
                for t in stamps
            ]
        manifest["months"][month] = entry
        print(month, res.window, res.status, "; ".join(res.reasons)[:120], flush=True)
    after = raw_fingerprint(raw_root, months)
    if after != before:
        sys.exit("ABORT: the raw store changed while building")
    out.mkdir(parents=True, exist_ok=True)
    with (out / "dropped_pseudo_bars.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["month", "timeframe", "timestamp_utc"])
        w.writerows(dropped_rows)
    manifest["dropped_pseudo_bars_sha256"] = sha256_file(out / "dropped_pseudo_bars.csv")
    manifest["raw_fingerprint_sha256"] = sha256_json(before)
    counts: dict[str, int] = {}
    for v in manifest["months"].values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    manifest["summary"] = {
        "months": counts,
        "dropped_m1": sum(1 for r in dropped_rows if r[1] == "M1"),
    }
    manifest["manifest_sha256"] = manifest_hash(manifest)
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(manifest["summary"]))
    print("manifest_sha256", manifest["manifest_sha256"])


if __name__ == "__main__":
    main()
