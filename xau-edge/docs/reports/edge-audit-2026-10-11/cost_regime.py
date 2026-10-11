# ruff: noqa - one-off Class D measurement script for INDEPENDENT_EDGE_FAILURE_AUDIT.md
import glob
import os

import polars as pl

ROOT = r"z:\Coding\Projects\AI-Harness\xau-edge\data\market\XAUUSD"
for tf in ("H1", "M15"):
    files = glob.glob(os.path.join(ROOT, tf, "*.parquet"))
    df = (
        pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")
        .unique(subset=["timestamp"])
        .sort("timestamp")
    )
    prev = pl.col("close").shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"), (pl.col("high") - prev).abs(), (pl.col("low") - prev).abs()
    )
    df = df.with_columns(tr.alias("tr")).with_columns(pl.col("tr").rolling_mean(14).alias("atr"))
    df = df.with_columns(
        (pl.max_horizontal(pl.col("spread"), pl.lit(30)) * 0.01 / pl.col("atr")).alias(
            "floor30_over_atr"
        ),
        (pl.col("spread") * 0.01 / pl.col("atr")).alias("rec_over_atr"),
    )
    yr = (
        df.group_by(pl.col("timestamp").dt.year().alias("y"))
        .agg(
            pl.col("close").median().alias("px"),
            pl.col("atr").median().alias("atr_med"),
            pl.col("spread").median().alias("spread_pts"),
            pl.col("rec_over_atr").median().alias("rec_spread_R"),
            pl.col("floor30_over_atr").median().alias("floor30_spread_R"),
        )
        .sort("y")
    )
    print(tf)
    print(yr.filter(pl.col("y") >= 2004))
