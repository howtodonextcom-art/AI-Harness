# ruff: noqa - one-off Class D measurement script for V3_RESEARCH_FOUNDATION_AND_HUMAN_DECISION.md
"""Cost model v2: XAUUSD spread by era, session, UTC hour and volatility regime (market data only).

Measures COST, never returns: no strategy, no outcome, no hypothesis is evaluated here.

1. Tick spread (ask - bid, 2021-10..2026-10): per-minute median, then median / p90 per year and per UTC hour.
2. Tick vs bar spread on the same minutes: is the M1 bar `spread` column (the only pre-2021 source) representative?
3. M1 bar spread 2011..2026 per year x session and per ATR(H1) tercile, in points and as a share of ATR(H1).
4. Scheduled-event spread (NFP proxy: first Friday 08:30 New York, 2021-10..2026-09) vs the same clock on other Fridays.

    .venv\\Scripts\\python.exe docs\\research\\edge-program-v3\\foundation\\cost_model_v2.py
"""

import glob
import json
import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import polars as pl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
MKT = os.path.join(ROOT, "data", "market", "XAUUSD")
OUT = os.path.join(os.path.dirname(__file__), "cost_model_v2.json")
POINT = 0.01
NY = ZoneInfo("America/New_York")

SESSIONS = [  # UTC hours, fixed (not DST-adjusted): a cost description, not a trading rule
    ("ASIA", 0, 7),
    ("LONDON", 7, 12),
    ("LDN_NY_OVERLAP", 12, 16),
    ("NY_LATE", 16, 21),
    ("ROLLOVER", 21, 24),
]


def session_expr(col: str = "timestamp") -> pl.Expr:
    h = pl.col(col).dt.hour()
    e = pl.lit("ROLLOVER")
    for name, a, b in reversed(SESSIONS):
        e = pl.when((h >= a) & (h < b)).then(pl.lit(name)).otherwise(e)
    return e


def q(df: pl.DataFrame, by: list[str], col: str) -> list[dict]:
    return (
        df.group_by(by)
        .agg(
            pl.len().alias("n"),
            pl.col(col).median().round(2).alias("median"),
            pl.col(col).quantile(0.9).round(2).alias("p90"),
        )
        .sort(by)
        .to_dicts()
    )


def tick_minutes() -> pl.DataFrame:
    files = sorted(glob.glob(os.path.join(MKT, "ticks", "*", "*.parquet")))
    parts = []
    for f in files:
        t = pl.read_parquet(f, columns=["timestamp", "bid", "ask"])
        if t.height == 0:
            continue
        parts.append(
            t.with_columns(((pl.col("ask") - pl.col("bid")) / POINT).alias("sp"))
            .group_by(pl.col("timestamp").dt.truncate("1m").dt.cast_time_unit("us").alias("minute"))
            .agg(pl.col("sp").median().alias("tick_sp"), pl.len().alias("ticks"))
        )
    return pl.concat(parts).sort("minute")


def m1_bars(since: int) -> pl.DataFrame:
    files = [
        f
        for f in glob.glob(os.path.join(MKT, "M1", "*.parquet"))
        if int(os.path.basename(f)[:4]) >= since
    ]
    return (
        pl.concat(
            [pl.read_parquet(f, columns=["timestamp", "spread"]) for f in files],
            how="diagonal_relaxed",
        )
        .unique(subset=["timestamp"])
        .sort("timestamp")
    )


def h1_atr() -> pl.DataFrame:
    files = glob.glob(os.path.join(MKT, "H1", "*.parquet"))
    df = (
        pl.concat([pl.read_parquet(f) for f in files], how="diagonal_relaxed")
        .unique(subset=["timestamp"])
        .sort("timestamp")
    )
    prev = pl.col("close").shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"), (pl.col("high") - prev).abs(), (pl.col("low") - prev).abs()
    )
    df = df.with_columns(tr.rolling_mean(14).alias("atr_h1"))
    # tercile of ATR(H1) inside its own calendar year: the regime is relative to the era, not absolute dollars
    df = df.with_columns(pl.col("timestamp").dt.year().alias("y"))
    df = df.with_columns(
        (pl.col("atr_h1").rank("average").over("y") / pl.col("atr_h1").count().over("y")).alias(
            "atr_pct"
        )
    ).with_columns(
        pl.when(pl.col("atr_pct") < 1 / 3)
        .then(pl.lit("LOW"))
        .when(pl.col("atr_pct") < 2 / 3)
        .then(pl.lit("MID"))
        .otherwise(pl.lit("HIGH"))
        .alias("vol_regime")
    )
    return df.select(pl.col("timestamp").alias("hour"), "atr_h1", "vol_regime")


def first_fridays(start: date, end: date) -> list[datetime]:
    out = []
    d = date(start.year, start.month, 1)
    while d <= end:
        f = d + timedelta(days=(4 - d.weekday()) % 7)
        out.append(datetime.combine(f, time(8, 30), NY).astimezone(timezone.utc))
        d = date(d.year + (d.month // 12), d.month % 12 + 1, 1)
    return [x for x in out if start <= x.date() <= end]


def main() -> None:
    res: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "class": "D (cost description, no outcome)",
    }

    tm = tick_minutes()
    tm = tm.with_columns(
        pl.col("minute").dt.year().alias("y"),
        pl.col("minute").dt.hour().alias("hour_utc"),
        session_expr("minute").alias("session"),
    )
    res["tick_coverage"] = {
        "first": str(tm["minute"].min()),
        "last": str(tm["minute"].max()),
        "minutes": tm.height,
    }
    res["tick_spread_by_year"] = q(tm, ["y"], "tick_sp")
    res["tick_spread_by_session"] = q(tm, ["session"], "tick_sp")
    res["tick_spread_by_hour_utc"] = q(tm, ["hour_utc"], "tick_sp")
    res["tick_spread_by_year_session"] = q(tm, ["y", "session"], "tick_sp")

    bars = m1_bars(2011).with_columns(
        pl.col("timestamp").dt.year().alias("y"),
        session_expr().alias("session"),
        pl.col("timestamp").dt.truncate("1h").alias("hour"),
    )
    joined = tm.join(
        bars.select(
            pl.col("timestamp").alias("minute"), pl.col("spread").cast(pl.Float64).alias("bar_sp")
        ),
        on="minute",
        how="inner",
    )
    joined = joined.with_columns((pl.col("tick_sp") / pl.col("bar_sp")).alias("ratio"))
    res["tick_vs_bar_same_minute"] = {
        "minutes": joined.height,
        "by_year": joined.group_by("y")
        .agg(
            pl.len().alias("n"),
            pl.col("tick_sp").median().round(2).alias("tick_median"),
            pl.col("bar_sp").median().round(2).alias("bar_median"),
            pl.col("ratio").median().round(3).alias("ratio_median"),
            pl.col("ratio").quantile(0.9).round(3).alias("ratio_p90"),
        )
        .sort("y")
        .to_dicts(),
    }

    atr = h1_atr()
    b = (
        bars.join(atr, on="hour", how="left")
        .drop_nulls("atr_h1")
        .with_columns((pl.col("spread") * POINT / pl.col("atr_h1")).alias("sp_atr_h1"))
    )
    res["bar_spread_points_by_year"] = q(b, ["y"], "spread")
    res["bar_spread_points_by_year_session"] = q(b, ["y", "session"], "spread")
    res["bar_spread_over_atr_h1_by_year"] = (
        b.group_by("y")
        .agg(
            pl.len().alias("n"),
            pl.col("sp_atr_h1").median().round(4).alias("median"),
            pl.col("sp_atr_h1").quantile(0.9).round(4).alias("p90"),
        )
        .sort("y")
        .to_dicts()
    )
    res["bar_spread_over_atr_h1_by_era_regime"] = (
        b.with_columns(
            pl.when(pl.col("y") <= 2018)
            .then(pl.lit("DEV2_2011_2018"))
            .when(pl.col("y") <= 2021)
            .then(pl.lit("VAL2_2019_2021"))
            .otherwise(pl.lit("RECENT_2022_2026"))
            .alias("era")
        )
        .group_by(["era", "vol_regime"])
        .agg(
            pl.len().alias("n"),
            pl.col("spread").median().alias("spread_pts_median"),
            pl.col("sp_atr_h1").median().round(4).alias("median"),
            pl.col("sp_atr_h1").quantile(0.9).round(4).alias("p90"),
        )
        .sort(["era", "vol_regime"])
        .to_dicts()
    )

    events = first_fridays(date(2021, 10, 1), date(2026, 9, 30))
    ev_rows = []
    for e in events:
        for k in range(-5, 16):
            ev_rows.append({"minute": e + timedelta(minutes=k), "offset": k, "kind": "NFP_PROXY"})
        # control: the same NY clock on the following Friday (no NFP)
        c = (e.astimezone(NY) + timedelta(days=7)).astimezone(timezone.utc)
        for k in range(-5, 16):
            ev_rows.append(
                {"minute": c + timedelta(minutes=k), "offset": k, "kind": "CONTROL_FRIDAY"}
            )
    ev = pl.DataFrame(ev_rows).with_columns(
        pl.col("minute").dt.convert_time_zone("UTC").dt.cast_time_unit("us")
    )
    ej = ev.join(tm.select("minute", "tick_sp"), on="minute", how="inner")
    res["event_spread_nfp_proxy"] = {
        "note": "NFP proxy = first Friday 08:30 America/New_York; known shifted releases are not excluded (proxy, not a PIT calendar)",
        "events": len(events),
        "by_kind_offset_bucket": ej.with_columns(
            pl.when(pl.col("offset") < 0)
            .then(pl.lit("pre_-5_-1"))
            .when(pl.col("offset") <= 2)
            .then(pl.lit("release_0_2"))
            .when(pl.col("offset") <= 5)
            .then(pl.lit("post_3_5"))
            .otherwise(pl.lit("post_6_15"))
            .alias("bucket")
        )
        .group_by(["kind", "bucket"])
        .agg(
            pl.len().alias("n"),
            pl.col("tick_sp").median().round(1).alias("median"),
            pl.col("tick_sp").quantile(0.9).round(1).alias("p90"),
        )
        .sort(["kind", "bucket"])
        .to_dicts(),
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print("wrote", OUT)
    for k in (
        "tick_coverage",
        "tick_spread_by_year",
        "tick_spread_by_session",
        "tick_vs_bar_same_minute",
        "bar_spread_over_atr_h1_by_year",
        "bar_spread_over_atr_h1_by_era_regime",
        "event_spread_nfp_proxy",
    ):
        print(k, json.dumps(res[k], default=str)[:2500])


if __name__ == "__main__":
    main()
