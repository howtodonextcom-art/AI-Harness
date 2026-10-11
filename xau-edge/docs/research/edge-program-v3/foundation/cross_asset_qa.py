# ruff: noqa - one-off Class D data QA for V3_RESEARCH_FOUNDATION_AND_HUMAN_DECISION.md (no returns, no outcome)
"""Cross-asset data QA: EURUSD / USDJPY / XAGUSD vs XAUUSD on the same broker (FTMO-Demo).

Checks, per symbol, on M1 and H1 from 2011-01-01: history depth, gaps, timezone/DST (weekly first and last bar
hour in UTC per year), spread per year, bar alignment with XAUUSD minutes, and a SHA-256 manifest of the files.
Only timestamps, spreads and bar counts are read: no price return is computed.

    .venv\\Scripts\\python.exe docs\\research\\edge-program-v3\\foundation\\cross_asset_qa.py
"""

import glob
import hashlib
import json
import os
from datetime import datetime, timezone

import polars as pl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MKT = os.path.join(ROOT, "data", "market")
OUT = os.path.join(os.path.dirname(__file__), "cross_asset_qa.json")
MANIFEST = os.path.join(os.path.dirname(__file__), "cross_asset_manifest.json")
SYMBOLS = ["XAUUSD", "EURUSD", "USDJPY", "XAGUSD"]
SINCE = datetime(2011, 1, 1, tzinfo=timezone.utc)


def load(sym: str, tf: str) -> pl.DataFrame:
    files = sorted(glob.glob(os.path.join(MKT, sym, tf, "*.parquet")))
    if not files:
        return pl.DataFrame()
    df = pl.concat(
        [pl.read_parquet(f, columns=["timestamp", "spread", "tick_volume"]) for f in files],
        how="diagonal_relaxed",
    )
    return df.unique(subset=["timestamp"]).sort("timestamp").filter(pl.col("timestamp") >= SINCE)


def sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def weekly_edges(df: pl.DataFrame) -> list[dict]:
    """Hour (UTC) of the first bar of each trading week and of the last one, by year: shows a DST/timezone shift."""
    # a trading week opens on Sunday evening UTC: shift by two days so Saturday..Friday falls in one bucket
    wk = df.with_columns((pl.col("timestamp") + pl.duration(days=2)).dt.truncate("1w").alias("w"))
    edges = wk.group_by("w").agg(
        pl.col("timestamp").min().alias("first"), pl.col("timestamp").max().alias("last")
    )
    edges = edges.with_columns(
        pl.col("first").dt.year().alias("y"),
        (
            pl.col("first").dt.weekday().cast(pl.Int32) * 100
            + pl.col("first").dt.hour().cast(pl.Int32)
        ).alias("first_dow_hour"),
        (
            pl.col("last").dt.weekday().cast(pl.Int32) * 100
            + pl.col("last").dt.hour().cast(pl.Int32)
        ).alias("last_dow_hour"),
    )
    return (
        edges.group_by("y")
        .agg(
            pl.len().alias("weeks"),
            pl.col("first_dow_hour").mode().first().alias("first_mode_dowhour"),
            pl.col("first_dow_hour").n_unique().alias("first_distinct"),
            pl.col("last_dow_hour").mode().first().alias("last_mode_dowhour"),
            pl.col("last_dow_hour").n_unique().alias("last_distinct"),
        )
        .sort("y")
        .to_dicts()
    )


def gaps(df: pl.DataFrame, step_s: int) -> dict:
    d = df.with_columns(pl.col("timestamp").diff().dt.total_seconds().alias("dt"))
    inner = d.filter(
        (pl.col("dt") > step_s) & (pl.col("dt") < 36 * 3600)
    )  # exclude weekends / holidays
    return {
        "intraday_gaps_gt_step": inner.height,
        "gaps_gt_15min": inner.filter(pl.col("dt") > 900).height,
        "gaps_gt_60min": inner.filter(pl.col("dt") > 3600).height,
        "largest_intraweek_gap_min": None
        if inner.height == 0
        else round(inner["dt"].max() / 60, 1),
        "by_year_gt_15min": inner.filter(pl.col("dt") > 900)
        .group_by(pl.col("timestamp").dt.year().alias("y"))
        .len()
        .sort("y")
        .to_dicts(),
    }


def main() -> None:
    res: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "since": SINCE.isoformat(),
        "symbols": {},
    }
    manifest: dict = {"generated_at": res["generated_at"], "files": {}}
    xau_m1 = load("XAUUSD", "M1").select("timestamp")
    xau_h1 = load("XAUUSD", "H1").select("timestamp")
    for sym in SYMBOLS:
        row: dict = {}
        for tf, step in (("M1", 60), ("H1", 3600)):
            df = load(sym, tf)
            if df.height == 0:
                row[tf] = {"status": "MISSING"}
                continue
            ref = xau_m1 if tf == "M1" else xau_h1
            ref_n = ref.height
            both = ref.join(df.select("timestamp"), on="timestamp", how="inner").height
            row[tf] = {
                "first": str(df["timestamp"].min()),
                "last": str(df["timestamp"].max()),
                "bars": df.height,
                "bars_by_year": df.group_by(pl.col("timestamp").dt.year().alias("y"))
                .len()
                .sort("y")
                .to_dicts(),
                "gaps": gaps(df, step),
                "weekly_edges_utc": weekly_edges(df),
                "spread_points_by_year": df.group_by(pl.col("timestamp").dt.year().alias("y"))
                .agg(
                    pl.col("spread").median().alias("median"),
                    pl.col("spread").quantile(0.9).alias("p90"),
                    (pl.col("spread") == 0).mean().round(4).alias("zero_share"),
                )
                .sort("y")
                .to_dicts(),
                "xau_bars_with_this_bar_pct": round(100 * both / ref_n, 2) if ref_n else None,
            }
        res["symbols"][sym] = row
        for f in sorted(
            glob.glob(os.path.join(MKT, sym, "H1", "*.parquet"))
            + glob.glob(os.path.join(MKT, sym, "M1", "*.parquet"))
        ):
            if sym == "XAUUSD":
                continue  # XAUUSD has its own ledger manifest
            manifest["files"][os.path.relpath(f, ROOT).replace("\\", "/")] = {
                "bytes": os.path.getsize(f),
                "sha256": sha(f),
            }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print("wrote", OUT, "and", MANIFEST, f"({len(manifest['files'])} files)")
    for sym, row in res["symbols"].items():
        for tf in ("M1", "H1"):
            r = row.get(tf, {})
            if r.get("status") == "MISSING":
                print(sym, tf, "MISSING")
                continue
            g = r["gaps"]
            print(
                f"{sym} {tf} {r['first'][:10]}..{r['last'][:10]} bars={r['bars']} gaps>15m={g['gaps_gt_15min']} gaps>60m={g['gaps_gt_60min']} largest={g['largest_intraweek_gap_min']}m xau_aligned={r['xau_bars_with_this_bar_pct']}%"
            )
            print(
                "   weekly edges:",
                [
                    (e["y"], e["first_mode_dowhour"], e["last_mode_dowhour"])
                    for e in r["weekly_edges_utc"]
                ][:16],
            )
            print("   spread:", [(e["y"], e["median"]) for e in r["spread_points_by_year"]][:16])


if __name__ == "__main__":
    main()
