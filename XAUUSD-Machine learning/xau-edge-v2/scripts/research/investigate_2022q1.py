"""Price/tick quality investigation of 2022-Q1 (Gate B3 item 6). Prices and ticks ONLY.

No signal, no PnL, no outcome of any strategy is computed or read. For each day it compares the stored M1
bars (bid chart) with the stored ticks aggregated to M1 and describes how they differ.

    uv run python scripts/research/investigate_2022q1.py --out docs/research/investigation_2022q1.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

for _v in ("POLARS_MAX_THREADS", "OMP_NUM_THREADS"):
    os.environ[_v] = "1"

import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))
from xau_edge_v2.config import Settings  # noqa: E402

MONTHS = ("2021-11", "2021-12", "2022-01", "2022-02", "2022-03", "2022-04", "2022-05")


def tick_minutes(t: pl.DataFrame, col: str) -> pl.DataFrame:
    return (
        t.with_columns(pl.col("timestamp").dt.truncate("1m").dt.cast_time_unit("us").alias("m"))
        .group_by("m")
        .agg(
            pl.col(col).first().alias("o"),
            pl.col(col).max().alias("h"),
            pl.col(col).min().alias("l"),
            pl.col(col).last().alias("c"),
            pl.len().alias("n"),
        )
    )


def worst_diff(j: pl.DataFrame) -> np.ndarray:
    return np.maximum.reduce(
        [
            np.abs(j[a].to_numpy() - j[b].to_numpy())
            for a, b in (("o", "open"), ("h", "high"), ("l", "low"), ("c", "close"))
        ]
    )


def day_report(day: Path, m1: pl.DataFrame) -> dict[str, Any]:
    t = (
        pl.read_parquet(day)
        .sort("timestamp")
        .with_columns(((pl.col("bid") + pl.col("ask")) / 2).alias("mid"))
    )
    out: dict[str, Any] = {"ticks": t.height}
    ts = t["timestamp"].dt.epoch("ms").to_numpy()
    gaps = np.diff(ts)
    out["max_tick_gap_s"] = round(float(gaps.max()) / 1000, 1) if gaps.size else 0
    out["crossed_quotes"] = int((t["bid"] > t["ask"]).sum())
    out["duplicate_timestamps"] = int((gaps == 0).sum())
    out["spread_points_median"] = float(((t["ask"] - t["bid"]) * 100).median() or 0)
    for col in ("bid", "mid", "ask"):
        b = tick_minutes(t, col)
        j = b.join(
            m1.select(
                pl.col("timestamp").alias("m"), "open", "high", "low", "close", "tick_volume"
            ),
            on="m",
            how="inner",
        )
        if j.height == 0:
            continue
        w = worst_diff(j)
        out[f"{col}_within_2c"] = round(float((w <= 0.02).mean()), 4)
        out[f"{col}_within_10c"] = round(float((w <= 0.10).mean()), 4)
        out[f"{col}_median_diff"] = round(float(np.median(w)), 3)
        if col == "bid":
            out["bars"] = j.height
            out["max_diff"] = round(float(w.max()), 2)
            out["tick_count_equals_tick_volume"] = round(
                float((j["n"].to_numpy() == j["tick_volume"].to_numpy()).mean()), 4
            )
            sign = np.sign(j["c"].to_numpy() - j["close"].to_numpy())
            out["close_bias_share_stored_higher"] = round(float((sign < 0).mean()), 3)
    # best minute shift (is the stored bar series shifted against the ticks?)
    best = {}
    b = tick_minutes(t, "bid")
    for s in (-2, -1, 0, 1, 2):
        bs = b.with_columns((pl.col("m") + pl.duration(minutes=s)).alias("m"))
        j = bs.join(
            m1.select(pl.col("timestamp").alias("m"), "open", "high", "low", "close"),
            on="m",
            how="inner",
        )
        if j.height:
            best[s] = round(float((worst_diff(j) <= 0.10).mean()), 3)
    out["shift_minutes_within_10c"] = best
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root = Settings().data_root / "XAUUSD"
    result: dict[str, Any] = {
        "months": {},
        "note": "prices and ticks only; no signal, PnL or outcome",
    }
    for month in MONTHS:
        m1 = pl.read_parquet(root / "M1" / f"{month}.parquet").sort("timestamp")
        days = sorted((root / "ticks" / month[:4]).glob(f"{month}-*.parquet"))
        rows = {}
        for d in days:
            rows[d.stem] = day_report(d, m1)
        good = [r["bid_within_10c"] for r in rows.values() if "bid_within_10c" in r]
        result["months"][month] = {
            "days": len(rows),
            "bid_within_10c_mean": round(float(np.mean(good)), 4) if good else None,
            "bid_within_10c_min": round(float(np.min(good)), 4) if good else None,
            "days_below_90pct": [k for k, r in rows.items() if r.get("bid_within_10c", 1) < 0.90],
            "detail": rows,
        }
        print(
            month,
            result["months"][month]["days"],
            "days; mean within 10c",
            result["months"][month]["bid_within_10c_mean"],
            "min",
            result["months"][month]["bid_within_10c_min"],
            flush=True,
        )
    Path(a.out).write_text(json.dumps(result, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
