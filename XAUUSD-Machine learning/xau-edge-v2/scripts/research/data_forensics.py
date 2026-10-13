"""Month-by-month forensic audit of the stored XAUUSD bars against independent evidence.

Independent evidence, in order of strength (never a strategy result, never a price outcome):
  * a fresh broker re-fetch of H1/H4/D1 (``terminal_dump.py``), exact bar identity, before 2021-02;
  * the stored ticks (a separate collection path) aggregated to M1, from 2021-10;
  * internal consistency: stored M1 aggregated to the re-fetched H1/H4 buckets.

Per month it measures
  * pseudo-bars: a bar at the daily rollover with spread 0 and a day-sized tick volume;
  * H1 / H4 identity against the re-fetch (the UTC offset is derived from the bars);
  * the stored M1 aggregated to H1 / H4 against the re-fetch;
  * ticks aggregated to M1 against the stored M1 (a few sample days per month);
  * session-only lag-1 autocorrelation, OHLC validity, duplicates, ordering, spread, tick volume.

Classes (definitions in docs/research/V2_DATA_PROVENANCE_FORENSIC_REPORT.md; ``VERIFIED_VALID`` means
verified against the evidence above, which comes from the same broker, not from a third party):
VERIFIED_VALID, SUSPECT, INVALID, INSUFFICIENT_EVIDENCE. An INVALID month may be ``recoverable``.

    uv run python scripts/research/data_forensics.py --dump data/research/terminal_dump --out docs/research/data_forensics_xauusd.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
from xau_edge_v2.config import Settings  # noqa: E402
from xau_edge_v2.research.clean_view import pseudo_bar_mask as pseudo_mask  # noqa: E402

TOL = 0.0051
CLOSE = 0.15
H1_FIRST = datetime(2009, 9, 1, tzinfo=UTC)
TICKS_FROM = datetime(2021, 10, 1, tzinfo=UTC)
REFETCH_UNTIL = datetime(2021, 2, 1, tzinfo=UTC)
SAMPLE_DAYS = 3
"""Tick days sampled per month: evenly spaced among the days that have ticks."""


def load_dump(path: Path) -> pl.DataFrame:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return pl.DataFrame(
        rows,
        schema=["t", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"],
        orient="row",
    )


def match_terminal(
    store: pl.DataFrame, term: pl.DataFrame, mon_lo: int, mon_hi: int
) -> dict[str, Any]:
    """Compare the stored bars of one month with the re-fetched bars, by time (server = UTC + 2 or + 3 hours)."""
    have = {
        int(t.timestamp()): (o, h, lo, c)
        for t, o, h, lo, c in zip(
            store["timestamp"],
            store["open"],
            store["high"],
            store["low"],
            store["close"],
            strict=True,
        )
    }
    t = term.filter((pl.col("t") - 3 * 3600 >= mon_lo) & (pl.col("t") - 2 * 3600 < mon_hi))
    ident = close = far = missing = 0
    offs: dict[int, int] = {}
    used: set[int] = set()
    for tt, o, h, lo, c in zip(t["t"], t["open"], t["high"], t["low"], t["close"], strict=True):
        best: tuple[float, int] | None = None
        for off in (2, 3):
            b = have.get(int(tt - off * 3600))
            if b is not None:
                d = max(abs(b[0] - o), abs(b[1] - h), abs(b[2] - lo), abs(b[3] - c))
                if best is None or d < best[0]:
                    best = (d, off)
        if best is None:
            missing += 1
            continue
        d, off = best
        used.add(int(tt - off * 3600))
        offs[off] = offs.get(off, 0) + 1
        ident += d <= TOL
        close += TOL < d <= CLOSE
        far += d > CLOSE
    return {
        "terminal": t.height, "identical": ident, "close": close, "far": far, "missing_in_store": missing,
        "offsets": offs, "stored_unmatched": store.height - len(used),
    }  # fmt: skip


def m1_to_bucket_agreement(
    m1: pl.DataFrame, term: pl.DataFrame, hours: int, offsets: dict[int, int]
) -> float | None:
    """Share of re-fetched bars whose OHLC is within 15 cents of the stored M1 aggregated over the same window.

    Pseudo-bars are excluded from the aggregation. ``offsets`` are the server-UTC offsets seen for the month.
    """
    if m1.height == 0 or not offsets:
        return None
    clean = m1.filter(pl.Series(~pseudo_mask(m1)))
    ts = clean["timestamp"].dt.epoch("s").to_numpy()
    o, h, lo, c = (clean[k].to_numpy() for k in ("open", "high", "low", "close"))
    off = max(offsets, key=lambda k: offsets[k])
    n = ok = 0
    for tt, to, th, tl, tc in zip(
        term["t"], term["open"], term["high"], term["low"], term["close"], strict=True
    ):
        best = None
        for sh in {off, 5 - off}:
            u = int(tt - sh * 3600)
            i, j = int(np.searchsorted(ts, u)), int(np.searchsorted(ts, u + hours * 3600))
            if j - i == 0:
                continue
            d = max(
                abs(o[i] - to), abs(h[i:j].max() - th), abs(lo[i:j].min() - tl), abs(c[j - 1] - tc)
            )
            best = d if best is None else min(best, d)
        if best is None:
            continue
        n += 1
        ok += best <= CLOSE
    return round(ok / n, 4) if n else None


def tick_check(
    root: Path, m1: pl.DataFrame, year: int, month: int
) -> dict[str, float | int] | None:
    """Ticks (a separate collection path) aggregated to M1 against the stored M1, a few sample days."""
    rows = []
    days = sorted((root / "ticks" / f"{year}").glob(f"{year}-{month:02d}-*.parquet"))
    pick = [
        days[int(i * (len(days) - 1) / max(SAMPLE_DAYS - 1, 1))]
        for i in range(min(SAMPLE_DAYS, len(days)))
    ]
    for f in dict.fromkeys(pick):
        t = pl.read_parquet(f).sort("timestamp")
        b = (
            t.with_columns(pl.col("timestamp").dt.truncate("1m").dt.cast_time_unit("us").alias("m"))
            .group_by("m")
            .agg(
                pl.col("bid").first().alias("o"),
                pl.col("bid").max().alias("h"),
                pl.col("bid").min().alias("l"),
                pl.col("bid").last().alias("c"),
            )
        )
        rows.append(
            b.join(
                m1.select(pl.col("timestamp").alias("m"), "open", "high", "low", "close"),
                on="m",
                how="inner",
            )
        )
    if not rows:
        return None
    j = pl.concat(rows)
    worst = np.maximum.reduce(
        [
            np.abs(j[a].to_numpy() - j[b].to_numpy())
            for a, b in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))
        ]
    )
    return {
        "bars": j.height,
        "within_10c": round(float((worst <= 0.10).mean()), 4),
        "max_diff": round(float(worst.max()), 2),
    }


def hygiene(m5: pl.DataFrame) -> dict[str, float | int]:
    ts = m5["timestamp"].dt.epoch("s").to_numpy()
    o, h, lo, c = (m5[k].to_numpy() for k in ("open", "high", "low", "close"))
    step = np.diff(ts)
    r = np.diff(np.log(c))
    sess = step == 300
    pair = sess[:-1] & sess[1:]
    ac = float(np.corrcoef(r[:-1][pair], r[1:][pair])[0, 1]) if pair.sum() > 50 else float("nan")  # noqa: PLR2004
    sd = float(r[sess].std()) if sess.any() else 0.0
    return {
        "bars": m5.height,
        "ohlc_invalid": int(
            ((h < np.maximum(o, c) - 1e-9) | (lo > np.minimum(o, c) + 1e-9) | (h < lo)).sum()
        ),
        "duplicates": int((step == 0).sum()),
        "not_increasing": int((step < 0).sum()),
        "ac1_session": round(ac, 3),
        "ret_gt_8sigma": int((np.abs(r) > 8 * sd).sum()) if sd else 0,
        "spread_median": float(m5["spread"].median() or 0.0),
        "zero_spread_share": round(float((m5["spread"] == 0).mean()), 3),
        "tick_volume_median": float(m5["tick_volume"].median() or 0.0),
    }


def classify(mon: str, m: dict[str, Any]) -> tuple[str, bool, list[str]]:  # noqa: PLR0911, PLR0912
    """(class, recoverable, reasons). See the report for the definitions."""
    y, mo = int(mon[:4]), int(mon[5:])
    first = datetime(y, mo, 1, tzinfo=UTC)
    why: list[str] = []
    pseudo = int(m["pseudo_bars_m1"])
    ac = float(m["ac1_session"])
    if pseudo >= 5:  # noqa: PLR2004
        recoverable = bool(m.get("h1_exact") == 1.0 and (m.get("m1_to_h1_agreement") or 0) >= 0.995)  # noqa: PLR2004
        return (
            "INVALID",
            recoverable,
            [
                f"{pseudo} daily pseudo-bars (next-day OHLC at the rollover, spread 0, day-sized volume)"
            ],
        )
    if pseudo > 0:
        why.append(f"{pseudo} isolated pseudo-bar(s)")
    if m["ohlc_invalid"] or m["duplicates"] or m["not_increasing"]:
        why.append("OHLC invalid / duplicate / non-monotonic bars")
    if abs(ac) > 0.15:  # noqa: PLR2004
        why.append(
            f"session-only lag-1 autocorrelation {ac:+.2f}: mean reversion of unknown origin"
        )
    if first >= TICKS_FROM:
        t = m.get("tick_check")
        if not t:
            return "INSUFFICIENT_EVIDENCE", False, [*why, "no tick sample for this month"]
        if t["within_10c"] < 0.97:  # noqa: PLR2004
            why.append(f"ticks agree with stored M1 in only {t['within_10c']:.1%} of bars")
        return (
            ("SUSPECT", False, why)
            if why
            else (
                "VERIFIED_VALID",
                False,
                ["stored M1 agrees with the independently collected ticks; hygiene clean"],
            )
        )
    if first >= REFETCH_UNTIL:
        return (
            "INSUFFICIENT_EVIDENCE",
            False,
            [*why, "after the re-fetch era and before the tick era: no independent source"],
        )
    ref = m.get("h1_exact") if first >= H1_FIRST else m.get("h4_exact")
    agg = m.get("m1_to_h1_agreement") if first >= H1_FIRST else m.get("m1_to_h4_agreement")
    if ref is None:
        return "INSUFFICIENT_EVIDENCE", False, [*why, "no independent re-fetch for this month"]
    if ref < 0.995:  # noqa: PLR2004
        why.append(f"only {ref:.1%} of the re-fetched bars are identical")
    if agg is not None and agg < 0.97:  # noqa: PLR2004
        why.append(f"stored M1 agrees with the re-fetched bars in only {agg:.1%} of buckets")
    if why:
        return "SUSPECT", False, why
    level = "H1" if first >= H1_FIRST else "H4"
    return (
        "VERIFIED_VALID",
        False,
        [f"identical to a fresh broker re-fetch ({level}); stored M1 consistent; hygiene clean"],
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Settings().data_root / "XAUUSD"
    dump = Path(a.dump)
    t1, t4 = load_dump(dump / "XAUUSD_H1.json"), load_dump(dump / "XAUUSD_H4.json")
    out: dict[str, dict[str, Any]] = {}
    for f in sorted((root / "M5").glob("*.parquet")):
        mon = f.stem
        y, mo = int(mon[:4]), int(mon[5:])
        lo = int(datetime(y, mo, 1, tzinfo=UTC).timestamp())
        hi = int(datetime(y + (mo == 12), mo % 12 + 1, 1, tzinfo=UTC).timestamp())
        m5 = pl.read_parquet(f).sort("timestamp")
        m1 = pl.read_parquet(root / "M1" / f.name).sort("timestamp")
        row: dict[str, Any] = {**hygiene(m5)}
        row["pseudo_bars_m1"] = int(pseudo_mask(m1).sum())
        row["pseudo_bars_m5"] = int(pseudo_mask(m5).sum())
        h1 = pl.read_parquet(root / "H1" / f.name).sort("timestamp")
        h4 = pl.read_parquet(root / "H4" / f.name).sort("timestamp")
        row["pseudo_bars_h1"] = int(pseudo_mask(h1).sum())
        t1m = t1.filter((pl.col("t") - 3 * 3600 >= lo) & (pl.col("t") - 2 * 3600 < hi))
        t4m = t4.filter((pl.col("t") - 3 * 3600 >= lo) & (pl.col("t") - 2 * 3600 < hi))
        if datetime(y, mo, 1, tzinfo=UTC) >= H1_FIRST:
            r = match_terminal(h1, t1, lo, hi)
            n = r["terminal"]
            row["h1_terminal"] = n
            row["h1_exact"] = round(r["identical"] / n, 4) if n else None
            row["h1_close_or_exact"] = round((r["identical"] + r["close"]) / n, 4) if n else None
            row["h1_far"] = r["far"]
            row["h1_missing_in_store"] = r["missing_in_store"]
            row["h1_store_unmatched"] = r["stored_unmatched"]
            row["utc_offsets_seen"] = r["offsets"]
            row["m1_to_h1_agreement"] = m1_to_bucket_agreement(m1, t1m, 1, r["offsets"])
        r4 = match_terminal(h4, t4, lo, hi)
        n4 = r4["terminal"]
        row["h4_terminal"] = n4
        row["h4_exact"] = round(r4["identical"] / n4, 4) if n4 else None
        row["h4_store_unmatched"] = r4["stored_unmatched"]
        row["m1_to_h4_agreement"] = m1_to_bucket_agreement(m1, t4m, 4, r4["offsets"])
        if datetime(y, mo, 1, tzinfo=UTC) >= TICKS_FROM:
            row["tick_check"] = tick_check(root, m1, y, mo)
        cls, rec, why = classify(mon, row)
        row["class"], row["recoverable"], row["why"] = cls, rec, why
        out[mon] = row
    counts: dict[str, int] = {}
    for r in out.values():
        key = str(r["class"]) + (" (recoverable)" if r["recoverable"] else "")
        counts[key] = counts.get(key, 0) + 1
    Path(a.out).write_text(
        json.dumps({"counts": counts, "months": out}, indent=1), encoding="utf-8"
    )
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
