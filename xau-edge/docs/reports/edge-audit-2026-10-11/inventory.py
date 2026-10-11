# ruff: noqa - one-off Class D measurement script for INDEPENDENT_EDGE_FAILURE_AUDIT.md
import glob
import json
import os

import polars as pl

root = r"z:\Coding\Projects\AI-Harness\xau-edge\data"
for base in ("market", "research_history"):
    for tf in ("M1", "M5", "M15", "M30", "H1", "H4"):
        files = glob.glob(os.path.join(root, base, "XAUUSD", tf, "*.parquet"))
        if not files:
            continue
        df = pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")
        ts = "timestamp" if "timestamp" in df.columns else df.columns[0]
        df = df.unique(subset=[ts])
        print(base, tf, df.height, df[ts].min(), df[ts].max(), sorted(df.columns))
tick_dirs = sorted(glob.glob(os.path.join(root, "market", "XAUUSD", "ticks", "*", "*")))
print("tick files", len(tick_dirs), tick_dirs[:1], tick_dirs[-1:])
t0 = pl.read_parquet(tick_dirs[0]) if tick_dirs[0].endswith(".parquet") else None
if t0 is not None:
    print("tick cols", t0.columns, t0.height)
for f in glob.glob(os.path.join(root, "news", "*")):
    print("news", f, os.path.getsize(f))
