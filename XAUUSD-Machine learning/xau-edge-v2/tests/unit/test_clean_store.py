"""The derived clean store: cleaning, restoration, synchronisation checks, manifest and the guarded reader."""
# ruff: noqa: PLW2901  (test builders rebuild rows in place)

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.research.clean_store import (
    TFS,
    CleanBarStore,
    CleanStoreError,
    MonthResult,
    aggregate,
    build_month,
    entry_for,
    manifest_hash,
    sha256_file,
    write_month,
)

MONTH = "2014-07"
SERVER = 3  # summer: server = UTC + 3
H = 3600


def utc(d: int, h: int, m: int = 0) -> datetime:
    return datetime(2014, 7, d, h, m, tzinfo=UTC)


def m1_day(
    day: int,
    rng: np.random.Generator,
    price: float,
    *,
    start: datetime | None = None,
    minutes: int = 1315,
) -> tuple[list[dict[str, Any]], float]:
    """Real M1 bars of one trading session: from the previous day 22:05 UTC for ``minutes`` minutes."""
    t0 = start or utc(day - 1, 22, 5)
    rows = []
    for i in range(minutes):
        o = price
        c = o + float(rng.normal(0, 0.15))
        rows.append(
            {
                "timestamp": t0 + timedelta(minutes=i),
                "open": o,
                "high": max(o, c) + 0.05,
                "low": min(o, c) - 0.05,
                "close": c,
                "tick_volume": int(rng.integers(20, 200)),
                "spread": 20,
                "real_volume": 0,
            }
        )
        price = c
    return rows, price


def frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    return (
        pl.DataFrame(rows)
        .with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))
        .sort("timestamp")
    )


def coarse(m1: pl.DataFrame, every: str, spread: int = 20) -> pl.DataFrame:
    a = aggregate(m1, every)
    return (
        a.rename({"tick_volume_sum": "tick_volume"})
        .with_columns(
            pl.lit(spread).cast(pl.Int64).alias("spread"),
            pl.lit(0).cast(pl.Int64).alias("real_volume"),
        )
        .select("timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")
    )


def h4_server(h1: pl.DataFrame) -> pl.DataFrame:
    """H4 bars aligned to the SERVER clock (hour multiple of 4): UTC bucket start = floor((t + 3 h) / 4 h) * 4 h - 3 h."""
    t = h1["timestamp"].dt.epoch("s").to_numpy()
    bucket = ((t + SERVER * H) // (4 * H)) * (4 * H) - SERVER * H
    d = h1.with_columns(pl.Series("b", bucket))
    out = d.group_by("b", maintain_order=True).agg(
        pl.col("open").first(),
        pl.col("high").max(),
        pl.col("low").min(),
        pl.col("close").last(),
        pl.col("tick_volume").sum(),
        pl.lit(20).cast(pl.Int64).alias("spread"),
        pl.lit(0).cast(pl.Int64).alias("real_volume"),
    )
    return out.with_columns(
        pl.from_epoch("b", time_unit="s")
        .dt.replace_time_zone("UTC")
        .dt.cast_time_unit("us")
        .alias("timestamp")
    ).select("timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")


class World:
    """A synthetic raw month with pseudo-bars, the clean truth and the broker re-fetch."""

    def __init__(
        self, tmp: Path, *, days: tuple[int, ...] = (8, 9, 10, 11), break_overlap: bool = False
    ) -> None:
        rng = np.random.default_rng(3)
        price = 1300.0
        real: list[dict[str, Any]] = []
        sessions: dict[int, list[dict[str, Any]]] = {}
        for d in days:
            rows, price = m1_day(d, rng, price)
            sessions[d] = rows
            real += rows
        self.real_m1 = frame(real)
        pseudo_rows = []
        for d in days:
            s = frame(sessions[d])
            pseudo_rows.append(
                {
                    "timestamp": utc(d - 1, 21, 0),
                    "open": float(s["open"][0]),
                    "high": float(s["high"].max()),
                    "low": float(s["low"].min()),
                    "close": float(s["close"][-1]),
                    "tick_volume": 120_000,
                    "spread": 0,
                    "real_volume": 0,
                }
            )
        # the pseudo-bar of day d sits at (d-1) 21:00, i.e. before that session; it carries the session's OHLC
        self.pseudo = frame(pseudo_rows)
        self.raw: dict[str, pl.DataFrame] = {
            "M1": pl.concat([self.real_m1, self.pseudo]).sort("timestamp")
        }
        for tf, every in (("M5", "5m"), ("M15", "15m"), ("M30", "30m"), ("H1", "1h")):
            self.raw[tf] = pl.concat([coarse(self.real_m1, every), self.pseudo]).sort("timestamp")
        self.clean_h1 = coarse(self.real_m1, "1h")
        self.clean_h4 = h4_server(self.clean_h1)
        merged = []
        for row in self.clean_h4.iter_rows(named=True):
            t = row["timestamp"]
            hit = self.pseudo.filter(
                (pl.col("timestamp") >= t) & (pl.col("timestamp") < t + timedelta(hours=4))
            )
            if hit.height:
                p = hit.row(0, named=True)
                row = {
                    **row,
                    "open": p["open"],
                    "high": max(row["high"], p["high"]),
                    "low": min(row["low"], p["low"]),
                    "tick_volume": row["tick_volume"] + p["tick_volume"],
                }
            merged.append(row)
        self.raw["H4"] = frame(merged)
        self.root = tmp / "store" / "XAUUSD"
        for tf, df in self.raw.items():
            path = self.root / tf / f"{MONTH}.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            df.write_parquet(path)
        self.term_h1 = self.refetch(self.clean_h1)
        self.term_h4 = self.refetch(self.clean_h4)

    @staticmethod
    def refetch(df: pl.DataFrame) -> pl.DataFrame:
        return df.with_columns((pl.col("timestamp").dt.epoch("s") + SERVER * H).alias("t")).select(
            "t", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
        )

    def rewrite(self, tf: str, df: pl.DataFrame) -> None:
        df.write_parquet(self.root / tf / f"{MONTH}.parquet")

    def build(self) -> MonthResult:
        return build_month(self.root, MONTH, self.term_h1, self.term_h4)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_a_month_with_pseudo_bars_is_cleaned_and_passes(world: World) -> None:
    res = world.build()
    assert res.status == "PASS", res.reasons
    assert res.window == "DEV'"
    assert res.frames["M1"].height == world.real_m1.height
    for tf in ("M5", "M15", "M30", "H1"):
        assert res.dropped[tf] == res.dropped["M1"]
    assert len(res.dropped["M1"]) == 4
    assert (
        res.frames["H4"]
        .select("open", "high", "low", "close", "tick_volume")
        .equals(world.clean_h4.select("open", "high", "low", "close", "tick_volume"))
    )
    assert len(res.restored_h4) == 4
    assert res.checks["sync_H1_H4"]["share"] == 1.0
    assert res.checks["refetch_H4"]["share"] == 1.0


def test_the_raw_files_are_not_touched(world: World) -> None:
    before = {tf: sha256_file(world.root / tf / f"{MONTH}.parquet") for tf in TFS}
    world.build()
    assert {tf: sha256_file(world.root / tf / f"{MONTH}.parquet") for tf in TFS} == before


def test_the_written_store_is_reproducible_bit_for_bit(world: World, tmp_path: Path) -> None:
    a = world.build()
    fa = write_month(a, tmp_path / "a")
    fb = write_month(world.build(), tmp_path / "b")
    assert fa == fb


def test_a_month_with_nothing_to_clean_comes_out_identical(tmp_path: Path) -> None:
    w = World(tmp_path)
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        w.rewrite(tf, w.raw[tf].filter(~pl.col("tick_volume").is_in([120_000])))
    w.rewrite("H4", w.clean_h4)
    res = w.build()
    assert res.status == "PASS", res.reasons
    assert res.checks["identical_to_raw"] is True


def test_a_bucket_that_swallowed_the_pseudo_bar_is_rebuilt_from_clean_m1(tmp_path: Path) -> None:
    """DST-gap weeks: real bars exist inside the rollover hour, so the coarse bar mixes real and pseudo data."""
    w = World(tmp_path, days=(8, 9))
    extra_rows, _ = m1_day(
        9, np.random.default_rng(1), 1301.0, start=utc(8, 21, 5), minutes=40
    )  # 21:05..21:44 are real
    real = pl.concat([w.real_m1, frame(extra_rows)]).sort("timestamp")
    pseudo = w.pseudo
    raw_m1 = pl.concat([real, pseudo]).sort("timestamp")
    w.rewrite("M1", raw_m1)
    for tf, every in (("M5", "5m"), ("M15", "15m"), ("M30", "30m"), ("H1", "1h")):
        clean = coarse(real, every)
        # the broker bar of the rollover bucket absorbed the pseudo-bar
        cl = clean.to_dicts()
        out = []
        for r in cl:
            hit = pseudo.filter(
                (pl.col("timestamp") >= r["timestamp"])
                & (
                    pl.col("timestamp")
                    < r["timestamp"]
                    + timedelta(hours={"M5": 0.0833, "M15": 0.25, "M30": 0.5, "H1": 1}[tf])
                )
            )
            if hit.height:
                p = hit.row(0, named=True)
                r = {
                    **r,
                    "open": p["open"],
                    "high": max(r["high"], p["high"]),
                    "low": min(r["low"], p["low"]),
                    "close": r["close"],
                    "tick_volume": r["tick_volume"] + p["tick_volume"],
                    "spread": 0,
                }
            out.append(r)
        pure = [
            r for r in pseudo.to_dicts() if not any(r["timestamp"] == o["timestamp"] for o in out)
        ]
        w.rewrite(tf, frame(out + pure))
    w.term_h1 = w.refetch(coarse(real, "1h"))
    w.term_h4 = w.refetch(h4_server(coarse(real, "1h")))
    res = w.build()
    assert res.status == "PASS", res.reasons
    assert sum(res.checks.get(f"rebuilt_{tf}", 0) for tf in ("M5", "M15", "M30", "H1")) > 0
    h1 = res.frames["H1"].filter(pl.col("timestamp") == utc(8, 21, 0))
    expect = coarse(real, "1h").filter(pl.col("timestamp") == utc(8, 21, 0))
    assert h1.select("open", "high", "low", "close").equals(
        expect.select("open", "high", "low", "close")
    )


def test_a_pseudo_bar_alone_in_an_h4_bucket_is_dropped_not_matched(tmp_path: Path) -> None:
    """A closed day: the pseudo-bar is the only content of its bucket and the broker has no such H4 bar."""
    w = World(tmp_path, days=(8, 9))
    lonely = {
        "timestamp": utc(12, 21, 0),
        "open": 1300.0,
        "high": 1300.5,
        "low": 1299.5,
        "close": 1300.2,
        "tick_volume": 50,
        "spread": 0,
        "real_volume": 0,
    }
    for tf in TFS:
        w.rewrite(tf, frame([*w.raw[tf].to_dicts(), lonely]))
    res = w.build()
    assert res.status == "PASS", res.reasons
    assert res.checks["h4_pseudo_only_dropped"] == 1
    assert utc(12, 21, 0) not in res.frames["H4"]["timestamp"].to_list()


@pytest.mark.parametrize(
    ("tamper", "reason"),
    [
        ("m5_close", "synchronisation"),
        ("missing_h4_refetch", "no re-fetched counterpart"),
        ("h1_far_from_refetch", "H1 identical to the re-fetch"),
        ("residual", "remain in H1"),
    ],
)
def test_a_month_that_cannot_be_proven_is_quarantined_with_a_reason(
    world: World, tamper: str, reason: str
) -> None:
    if tamper == "m5_close":
        m5 = world.raw["M5"].to_dicts()
        m5[100] = {**m5[100], "close": m5[100]["close"] + 3.0, "high": m5[100]["high"] + 3.0}
        world.rewrite("M5", frame(m5))
    elif tamper == "missing_h4_refetch":
        world.term_h4 = world.term_h4.head(world.term_h4.height - 2)
    elif tamper == "h1_far_from_refetch":
        world.term_h1 = world.term_h1.with_columns(pl.col("close") + 2.0, pl.col("high") + 2.0)
    elif tamper == "residual":
        h1 = world.raw["H1"].to_dicts()
        h1.append(
            {
                "timestamp": utc(12, 22, 0),
                "open": 1300.0,
                "high": 1301.0,
                "low": 1299.0,
                "close": 1300.5,
                "tick_volume": 900_000,
                "spread": 0,
                "real_volume": 0,
            }
        )
        world.rewrite("H1", frame(h1))
    res = world.build()
    assert res.status == "QUARANTINED"
    assert any(reason in r for r in res.reasons), res.reasons


def test_an_h4_bar_that_differs_without_a_pseudo_bar_in_it_is_refused(tmp_path: Path) -> None:
    w = World(tmp_path, days=(8, 9))
    h4 = w.raw["H4"].to_dicts()
    victim = next(
        r
        for r in h4
        if not (
            w.pseudo.filter(
                (pl.col("timestamp") >= r["timestamp"])
                & (pl.col("timestamp") < r["timestamp"] + timedelta(hours=4))
            ).height
        )
    )
    victim["high"] += 4.0
    w.rewrite("H4", frame(h4))
    res = w.build()
    assert res.status == "QUARANTINED"
    assert any("without a pseudo-bar" in r for r in res.reasons)


# ---- the manifest and the guarded reader -----------------------------------------------------
def make_store(
    tmp_path: Path, months: dict[str, MonthResult], *, extra: dict[str, Any] | None = None
) -> Path:
    out = tmp_path / "clean"
    manifest: dict[str, Any] = {"schema": 1, "months": {}}
    for month, res in months.items():
        files = write_month(res, out) if res.status == "PASS" else {}
        manifest["months"][month] = entry_for(res, {}, files)
    manifest.update(extra or {})
    manifest["manifest_sha256"] = manifest_hash(manifest)
    (out).mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return out


def pass_result(world: World, month: str = MONTH) -> MonthResult:
    res = world.build()
    res.month = month
    return res


def test_the_reader_serves_pass_months_and_verifies_every_file(
    world: World, tmp_path: Path
) -> None:
    out = make_store(tmp_path, {MONTH: pass_result(world)})
    store = CleanBarStore(out)
    assert store.pass_months() == [MONTH]
    assert store.verify_all() == 6
    df = store.window(Timeframe.H1, utc(8, 0), utc(9, 0), 1000)
    assert df.height > 0


def test_a_tampered_file_is_refused(world: World, tmp_path: Path) -> None:
    out = make_store(tmp_path, {MONTH: pass_result(world)})
    path = out / "XAUUSD" / "M5" / f"{MONTH}.parquet"
    pl.read_parquet(path).with_columns(pl.col("close") + 0.01).write_parquet(path)
    with pytest.raises(CleanStoreError, match="sha256"):
        CleanBarStore(out).window(Timeframe.M5, utc(8, 0), utc(9, 0), 100)


def test_a_tampered_manifest_is_refused(world: World, tmp_path: Path) -> None:
    out = make_store(tmp_path, {MONTH: pass_result(world)})
    m = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    m["months"][MONTH]["window"] = "VALIDATION'"
    (out / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(CleanStoreError, match="manifest_sha256"):
        CleanBarStore(out)


def test_a_quarantined_month_in_the_range_is_never_skipped_silently(
    world: World, tmp_path: Path
) -> None:
    good = pass_result(world)
    bad = MonthResult(month="2014-08", window="DEV'")
    bad.fail("synthetic quarantine")
    out = make_store(tmp_path, {MONTH: good, "2014-08": bad})
    store = CleanBarStore(out)
    assert store.status("2014-08") == "QUARANTINED"
    with pytest.raises(CleanStoreError, match="QUARANTINED"):
        store.window(Timeframe.H1, utc(8, 0), datetime(2014, 8, 5, tzinfo=UTC), 100)
    with pytest.raises(CleanStoreError, match="outside"):
        store.window(Timeframe.H1, datetime(2013, 1, 1, tzinfo=UTC), utc(9, 0), 100)
    with pytest.raises(CleanStoreError, match="outside"):
        store.window(Timeframe.H1, utc(8, 0), None, 100)
    assert store.window(Timeframe.H1, utc(8, 0), utc(9, 0), 100).height > 0
