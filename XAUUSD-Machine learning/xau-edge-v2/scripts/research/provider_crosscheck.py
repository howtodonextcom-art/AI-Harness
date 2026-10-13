"""Stored FTMO H1 bars against the MetaQuotes-Demo server's H1 bars (a different provider), month by month.

Both servers keep their own clock (FTMO follows US DST, MetaQuotes follows EU DST), so each bar is matched at
UTC offset 2 or 3 hours, whichever fits better. Prices only; no strategy, signal or outcome.

    uv run python scripts/research/provider_crosscheck.py --dump data/research/terminal_dump --out docs/research/provider_crosscheck.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
from xau_edge_v2.config import Settings  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    mq = {
        r[0]: r for r in json.loads((Path(a.dump) / "XAUUSD_H1.json").read_text(encoding="utf-8"))
    }
    root = Settings().data_root / "XAUUSD" / "H1"
    out: dict[str, dict[str, float | int]] = {}
    for f in sorted(root.glob("20*.parquet")):
        if f.stem < "2009-09":
            continue
        d = pl.read_parquet(f).sort("timestamp")
        diffs = []
        for t, o, h, lo, c, sp, v in zip(
            d["timestamp"],
            d["open"],
            d["high"],
            d["low"],
            d["close"],
            d["spread"],
            d["tick_volume"],
            strict=True,
        ):
            if sp == 0 and v > 20000:  # a pseudo-bar: it has no counterpart on the other provider
                continue
            best = None
            for off in (2, 3):
                m = mq.get(int(t.timestamp()) + off * 3600)
                if m:
                    x = max(abs(m[1] - o), abs(m[2] - h), abs(m[3] - lo), abs(m[4] - c))
                    best = x if best is None else min(best, x)
            if best is not None:
                diffs.append(best)
        if diffs:
            x = np.array(diffs)
            out[f.stem] = {
                "bars": len(x),
                "median": round(float(np.median(x)), 3),
                "p95": round(float(np.quantile(x, 0.95)), 3),
                "p99": round(float(np.quantile(x, 0.99)), 3),
                "max": round(float(x.max()), 2),
                "share_within_1": round(float((x <= 1.0).mean()), 4),
            }
    Path(a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    for m in (
        "2012-05",
        "2013-05",
        "2020-12",
        "2021-01",
        "2021-02",
        "2021-05",
        "2021-09",
        "2021-10",
        "2022-01",
        "2022-02",
        "2022-03",
        "2022-05",
        "2023-05",
        "2024-05",
        "2025-05",
        "2026-05",
        "2026-09",
    ):
        if m in out:
            print(m, out[m])


if __name__ == "__main__":
    main()
