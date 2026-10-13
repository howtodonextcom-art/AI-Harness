"""The derived CLEAN bar store (ADR-V2-019): the raw store is never touched.

For every month in scope it
  1. reads the RAW bars (read-only) of M1, M5, M15, M30, H1, H4;
  2. drops the daily pseudo-bars (``clean_view``) from M1..H1 and checks that every dropped coarse bar is
     IDENTICAL to the M1 pseudo-bar (a bucket that mixes it with real bars is not recoverable);
  3. restores H4 from the broker re-fetch (``terminal_dump.py``): an H4 bar that differs from the re-fetch is
     replaced, and only when it is a rollover bar (the one that swallowed the pseudo-bar);
  4. verifies synchronisation M1 -> M5 -> M15/M30/H1 -> H4 and identity with the re-fetch;
  5. writes the month ONLY if every check passes, with sha256 of every file and of every raw input.
A month that fails is QUARANTINED in the manifest with its reasons and no data file.

``CleanBarStore`` is the only way research code may read it: it verifies the manifest and the sha256 of
every file it opens, and refuses any month that is not listed as PASS (no silent skipping).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from xau_edge_v2.data.bar_store import BarStore
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.research.clean_view import pseudo_bar_mask

SCHEMA = 1
TFS = ("M1", "M5", "M15", "M30", "H1", "H4")
EVERY = {"M5": "5m", "M15": "15m", "M30": "30m", "H1": "1h"}
bucket_td = {
    "M5": timedelta(minutes=5),
    "M15": timedelta(minutes=15),
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
}
TOL = 0.0051
SYNC_MIN_SHARE = 0.995
"""A hierarchy check passes when at least this share of the coarse bars equals the aggregation of the finer bars."""
H1_REFETCH_FROM = datetime(2009, 9, 1, tzinfo=UTC)
OHLC = ("open", "high", "low", "close")
SCOPE: tuple[tuple[str, str, str], ...] = (
    ("2005-06", "2018-12", "DEV'"),
    ("2019-01", "2021-01", "VALIDATION'"),
    ("2021-02", "2021-09", "QUARANTINE"),
    ("2021-10", "2021-12", "RESERVED"),
)
"""Windows of the owner decision (Gate B2). Confirm-C, Test-H and Holdout are never built."""


class CleanStoreError(RuntimeError):
    """The clean store was asked for something it does not hold, or it does not match its manifest."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def window_of(month: str) -> str | None:
    for lo, hi, name in SCOPE:
        if lo <= month <= hi:
            return name
    return None


def months_in_scope() -> list[str]:
    out: list[str] = []
    for lo, hi, _ in SCOPE:
        y, m = int(lo[:4]), int(lo[5:])
        while f"{y:04d}-{m:02d}" <= hi:
            out.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


@dataclass
class MonthResult:
    month: str
    window: str
    status: str = "PASS"
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    dropped: dict[str, list[int]] = field(default_factory=dict)
    restored_h4: list[int] = field(default_factory=list)
    frames: dict[str, pl.DataFrame] = field(default_factory=dict)

    def fail(self, reason: str) -> None:
        self.status = "QUARANTINED"
        self.reasons.append(reason)


# ---------------------------------------------------------------------------------------------
# aggregation and comparison
# ---------------------------------------------------------------------------------------------
def aggregate(fine: pl.DataFrame, every: str) -> pl.DataFrame:
    """OHLC + tick volume of ``fine`` bars grouped on UTC-aligned buckets."""
    if fine.height == 0:
        return fine.clear()
    return (
        fine.sort("timestamp")
        .group_by_dynamic("timestamp", every=every, closed="left", label="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("tick_volume").sum().alias("tick_volume_sum"),
        )
    )


def sync_share(fine: pl.DataFrame, coarse: pl.DataFrame, every: str) -> dict[str, float | int]:
    """How many coarse bars equal the aggregation of the finer bars (OHLC within half a cent)."""
    agg = aggregate(fine, every)
    if coarse.height == 0:
        return {
            "coarse": 0,
            "exact": 0,
            "share": 1.0,
            "missing_in_fine": 0,
            "extra_in_fine": agg.height,
        }
    j = coarse.join(agg, on="timestamp", how="left", suffix="_agg")
    has = j["open_agg"].is_not_null().to_numpy()
    exact = np.ones(j.height, dtype=bool)
    for c in OHLC:
        a, b = j[c].to_numpy(), j[f"{c}_agg"].to_numpy()
        exact &= np.abs(np.where(has, a - np.nan_to_num(b), 1.0)) <= TOL
    exact &= has
    extra = agg.join(coarse.select("timestamp"), on="timestamp", how="anti").height
    return {
        "coarse": coarse.height,
        "exact": int(exact.sum()),
        "share": round(float(exact.sum()) / coarse.height, 5),
        "missing_in_fine": int((~has).sum()),
        "extra_in_fine": extra,
    }


def h1_to_h4_share(h1: pl.DataFrame, h4: pl.DataFrame, month_end: int) -> dict[str, float | int]:
    """Each H4 bar against the H1 bars inside [ts, ts + 4 h) (server aligned: the H4 bar's own timestamp).

    A bucket that runs past the end of the month is skipped (its other H1 bars are in the next file).
    """
    ts = h1["timestamp"].dt.epoch("s").to_numpy()
    o, h, lo, c = (h1[k].to_numpy() for k in OHLC)
    exact = n = 0
    for t, ho, hh, hl, hc in zip(
        h4["timestamp"].dt.epoch("s").to_list(),
        h4["open"],
        h4["high"],
        h4["low"],
        h4["close"],
        strict=True,
    ):
        if t + 4 * 3600 > month_end:
            continue
        n += 1
        i, j = int(np.searchsorted(ts, t)), int(np.searchsorted(ts, t + 4 * 3600))
        if (
            j > i
            and abs(o[i] - ho) <= TOL
            and abs(h[i:j].max() - hh) <= TOL
            and abs(lo[i:j].min() - hl) <= TOL
            and abs(c[j - 1] - hc) <= TOL
        ):
            exact += 1
    return {"coarse": n, "exact": exact, "share": round(exact / n, 5) if n else 1.0}


def refetch_identity(
    bars: pl.DataFrame, term: pl.DataFrame, month_lo: int, month_hi: int
) -> dict[str, float | int]:
    """Share of re-fetched bars (server = UTC + 2 or + 3) that the stored bars equal."""
    have = {
        int(t.timestamp()): (o, h, lo, c)
        for t, o, h, lo, c in zip(
            bars["timestamp"], bars["open"], bars["high"], bars["low"], bars["close"], strict=True
        )
    }
    t = term.filter((pl.col("t") - 3 * 3600 >= month_lo) & (pl.col("t") - 2 * 3600 < month_hi))
    exact = 0
    used: set[int] = set()
    for tt, o, h, lo, c in zip(t["t"], t["open"], t["high"], t["low"], t["close"], strict=True):
        for off in (2, 3):
            b = have.get(int(tt - off * 3600))
            if (
                b is not None
                and max(abs(b[0] - o), abs(b[1] - h), abs(b[2] - lo), abs(b[3] - c)) <= TOL
            ):
                exact += 1
                used.add(int(tt - off * 3600))
                break
    n = t.height
    return {
        "refetched": n,
        "exact": exact,
        "share": round(exact / n, 5) if n else 1.0,
        "stored_without_refetch": bars.height - len(used),
    }


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------
def _h4_server_offset(ts_utc: int) -> int:
    """Server offset (2 winter, 3 summer) of the H4 bar stamped ``ts_utc``: its server hour is a multiple of 4."""
    hour = (ts_utc // 3600) % 24
    for off in (2, 3):
        if (hour + off) % 24 % 4 == 0:
            return off
    msg = f"H4 bar at UTC hour {hour} fits no server offset"
    raise CleanStoreError(msg)


def restore_h4(
    raw_h4: pl.DataFrame,
    term_h4: pl.DataFrame,
    res: MonthResult,
    pseudo_ts: set[int],
    clean_h1_ts: np.ndarray,
) -> pl.DataFrame:
    """Replace the H4 bars that differ from the re-fetch; only a rollover bar next to a pseudo-bar may differ.

    An H4 bar with no re-fetched counterpart is dropped when it is the pseudo-bar ALONE (a closed Saturday or
    a holiday: no clean H1 bar inside its bucket); anything else is a failure.
    """
    term = {
        int(r[0]): r
        for r in term_h4.select(
            "t", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"
        ).iter_rows()
    }
    rows = raw_h4.to_dicts()
    changed: list[int] = []
    dropped: list[int] = []
    missing = 0
    for row in rows:
        ts = int(row["timestamp"].timestamp())
        tb = term.get(ts + _h4_server_offset(ts) * 3600)
        if tb is None:
            alone = any(ts <= p < ts + 4 * 3600 for p in pseudo_ts) and not (
                int(np.searchsorted(clean_h1_ts, ts + 4 * 3600))
                - int(np.searchsorted(clean_h1_ts, ts))
            )
            if alone:
                dropped.append(ts)
            else:
                missing += 1
            continue
        same = max(abs(row[k] - tb[i]) for i, k in enumerate(OHLC, start=1)) <= TOL
        if same:
            continue
        # allowed only when a pseudo-bar sits inside this H4 bucket
        if not any(ts <= p < ts + 4 * 3600 for p in pseudo_ts):
            res.fail(
                f"H4 bar {row['timestamp']:%Y-%m-%d %H:%M} differs from the re-fetch without a pseudo-bar in it"
            )
            continue
        for i, k in enumerate(
            ("open", "high", "low", "close", "tick_volume", "spread", "real_volume"), start=1
        ):
            row[k] = tb[i]
        changed.append(ts)
    if missing:
        res.fail(f"{missing} H4 bar(s) have no re-fetched counterpart")
    res.restored_h4 = changed
    res.checks["h4_restored"] = len(changed)
    res.checks["h4_pseudo_only_dropped"] = len(dropped)
    res.dropped["H4"] = dropped
    rows = [r for r in rows if int(r["timestamp"].timestamp()) not in set(dropped)]
    return pl.DataFrame(rows, schema=raw_h4.schema) if rows else raw_h4.clear()


TICKS_FROM = "2021-10"
REFETCH_UNTIL = "2021-01"
"""After this month the broker re-fetch no longer equals the stored bars (history was revised), so it cannot verify them."""
TICK_MIN_SHARE = 0.97
TICK_SAMPLE_DAYS = 3


def tick_check(raw_root: Path, m1: pl.DataFrame, month: str) -> dict[str, float | int] | None:
    """Ticks (a separate collection path) aggregated to M1 against the stored M1, a few sample days."""
    folder = raw_root / "ticks" / month[:4]
    days = sorted(folder.glob(f"{month}-*.parquet"))
    if not days:
        return None
    pick = [
        days[int(i * (len(days) - 1) / max(TICK_SAMPLE_DAYS - 1, 1))]
        for i in range(min(TICK_SAMPLE_DAYS, len(days)))
    ]
    parts = []
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
        parts.append(
            b.join(
                m1.select(pl.col("timestamp").alias("m"), "open", "high", "low", "close"),
                on="m",
                how="inner",
            )
        )
    j = pl.concat(parts)
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


def build_month(  # noqa: PLR0912, PLR0915 - one pass, one check per line
    raw_root: Path, month: str, term_h1: pl.DataFrame, term_h4: pl.DataFrame
) -> MonthResult:
    """Clean one month. ``raw_root`` is ``<store>/XAUUSD`` (read only)."""
    res = MonthResult(month=month, window=window_of(month) or "OUT_OF_SCOPE")
    y, mo = int(month[:4]), int(month[5:])
    lo = int(datetime(y, mo, 1, tzinfo=UTC).timestamp())
    hi = int(datetime(y + (mo == 12), mo % 12 + 1, 1, tzinfo=UTC).timestamp())
    raw: dict[str, pl.DataFrame] = {}
    for tf in TFS:
        path = raw_root / tf / f"{month}.parquet"
        if not path.exists():
            res.fail(f"raw {tf} file missing")
            return res
        raw[tf] = pl.read_parquet(path).sort("timestamp")
    # 2. pseudo-bars
    m1_mask = pseudo_bar_mask(raw["M1"])
    pseudo = raw["M1"].filter(pl.Series(m1_mask))
    pseudo_by_ts = {int(r["timestamp"].timestamp()): r for r in pseudo.iter_rows(named=True)}
    clean: dict[str, pl.DataFrame] = {"M1": raw["M1"].filter(pl.Series(~m1_mask))}
    res.dropped["M1"] = sorted(pseudo_by_ts)
    m1_agg = {
        tf: {
            int(r["timestamp"].timestamp()): r
            for r in aggregate(clean["M1"], EVERY[tf]).iter_rows(named=True)
        }
        for tf in ("M5", "M15", "M30", "H1")
    }
    m1_spread = clean["M1"].select("timestamp", "spread")
    rebuilt_ts: dict[str, set[int]] = {}
    for tf in ("M5", "M15", "M30", "H1"):
        df = raw[tf]
        ts = df["timestamp"].dt.epoch("s").to_numpy()
        hit = (
            np.isin(ts, np.fromiter(pseudo_by_ts, dtype=np.int64, count=len(pseudo_by_ts)))
            if pseudo_by_ts
            else np.zeros(len(ts), dtype=bool)
        )
        rows = df.to_dicts()
        keep: list[dict[str, Any]] = []
        rebuilt = 0
        rebuilt_ts[tf] = set()
        for i, r in enumerate(rows):
            if not hit[i]:
                keep.append(r)
                continue
            p = pseudo_by_ts[int(ts[i])]
            if all(abs(r[k] - p[k]) <= TOL for k in OHLC) and r["tick_volume"] == p["tick_volume"]:
                continue  # the bar IS the pseudo-bar: drop it
            agg = m1_agg[tf].get(int(ts[i]))
            if agg is None:
                continue  # nothing real in the bucket
            # the bucket swallowed the pseudo-bar: rebuild it from the clean M1 bars (verified below)
            last = m1_spread.filter(pl.col("timestamp") < r["timestamp"] + (bucket_td[tf])).filter(
                pl.col("timestamp") >= r["timestamp"]
            )
            rebuilt_row = {
                **r, "open": agg["open"], "high": agg["high"], "low": agg["low"], "close": agg["close"],
                "tick_volume": agg["tick_volume_sum"], "spread": int(last["spread"][-1]) if last.height else r["spread"],
            }  # fmt: skip
            keep.append(rebuilt_row)
            rebuilt += 1
            rebuilt_ts[tf].add(int(ts[i]))
        clean[tf] = pl.DataFrame(keep, schema=df.schema) if keep else df.clear()
        res.dropped[tf] = sorted(int(t) for t in ts[hit])
        res.checks[f"rebuilt_{tf}"] = rebuilt
    # residual pseudo-bars of any timeframe (e.g. an H1 pseudo-bar with no M1 twin)
    for tf in ("M1", "M5", "M15", "M30", "H1"):
        mask = pseudo_bar_mask(clean[tf], era_rule=tf == "M1")
        if rebuilt_ts.get(
            tf
        ):  # a bucket rebuilt from clean M1 is checked by sync and identity, not by its spread field
            mask &= ~np.isin(
                clean[tf]["timestamp"].dt.epoch("s").to_numpy(),
                np.fromiter(rebuilt_ts[tf], dtype=np.int64, count=len(rebuilt_ts[tf])),
            )
        left = int(mask.sum())
        res.checks[f"residual_pseudo_{tf}"] = left
        if left:
            res.fail(f"{left} pseudo-bar(s) remain in {tf} after cleaning")
    refetch_era = month <= REFETCH_UNTIL
    # 3. H4 from the re-fetch (only while the re-fetch still equals the stored history)
    if refetch_era:
        clean["H4"] = (
            restore_h4(
                raw["H4"],
                term_h4,
                res,
                set(pseudo_by_ts),
                clean["H1"]["timestamp"].dt.epoch("s").to_numpy(),
            )
            if res.status == "PASS"
            else raw["H4"]
        )
    else:
        clean["H4"] = raw["H4"]
    # 4. synchronisation and identity
    for fine, coarse in (("M1", "M5"), ("M5", "M15"), ("M5", "M30"), ("M5", "H1")):
        s = sync_share(clean[fine], clean[coarse], EVERY[coarse])
        res.checks[f"sync_{fine}_{coarse}"] = s
        if s["share"] < SYNC_MIN_SHARE:
            res.fail(f"{fine}->{coarse} synchronisation {s['share']:.4f} < {SYNC_MIN_SHARE}")
    s4 = h1_to_h4_share(clean["H1"], clean["H4"], hi)
    res.checks["sync_H1_H4"] = s4
    if s4["share"] < SYNC_MIN_SHARE:
        res.fail(f"H1->H4 synchronisation {s4['share']:.4f} < {SYNC_MIN_SHARE}")
    if refetch_era:
        r4 = refetch_identity(clean["H4"], term_h4, lo, hi)
        res.checks["refetch_H4"] = r4
        if r4["share"] < 1.0:
            res.fail(f"H4 identical to the re-fetch in only {r4['share']:.4f}")
    elif month >= TICKS_FROM:
        tk = tick_check(raw_root, clean["M1"], month)
        res.checks["tick_check"] = tk
        if tk is None or tk["within_10c"] < TICK_MIN_SHARE:
            res.fail(
                f"ticks agree with the stored M1 in only {None if tk is None else tk['within_10c']}"
            )
    else:
        res.fail("no independent source for this month")
    if refetch_era and datetime(y, mo, 1, tzinfo=UTC) >= H1_REFETCH_FROM:
        r1 = refetch_identity(clean["H1"], term_h1, lo, hi)
        res.checks["refetch_H1"] = r1
        if r1["share"] < 0.999:
            res.fail(f"H1 identical to the re-fetch in only {r1['share']:.4f}")
        if r1["stored_without_refetch"] > 6:
            res.fail(
                f"{r1['stored_without_refetch']} stored H1 bars have no re-fetched counterpart"
            )
    # hygiene
    for tf in ("M1", "M5", "H1"):
        d = clean[tf]
        step = np.diff(d["timestamp"].dt.epoch("s").to_numpy())
        o, h, low, c = (d[k].to_numpy() for k in OHLC)
        bad = int(((h < np.maximum(o, c) - 1e-9) | (low > np.minimum(o, c) + 1e-9)).sum()) + int(
            (step <= 0).sum()
        )
        res.checks[f"hygiene_{tf}"] = bad
        if bad:
            res.fail(f"{bad} OHLC/ordering defect(s) in {tf}")
    untouched = (
        not any(res.dropped.values())
        and not res.restored_h4
        and not any(res.checks.get(f"rebuilt_{t}") for t in ("M5", "M15", "M30", "H1"))
    )
    if untouched:  # a month with nothing to clean must come out EXACTLY as it went in
        same = all(clean[tf].equals(raw[tf]) for tf in TFS)
        res.checks["identical_to_raw"] = same
        if not same:
            res.fail("a month with nothing to clean differs from the raw month")
    res.frames = clean
    return res


def entry_for(
    res: MonthResult, raw_sha: dict[str, str], files: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """The manifest entry of one month."""
    return {
        "status": res.status,
        "window": res.window,
        "reasons": res.reasons,
        "checks": res.checks,
        "dropped_pseudo_bars": {tf: len(v) for tf, v in res.dropped.items()},
        "restored_h4": len(res.restored_h4),
        "raw_sha256": raw_sha,
        "files": files,
    }


def write_month(res: MonthResult, out_root: Path) -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for tf in TFS:
        path = out_root / "XAUUSD" / tf / f"{res.month}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        res.frames[tf].write_parquet(path, compression="zstd", statistics=False)
        files[tf] = {"sha256": sha256_file(path), "rows": res.frames[tf].height}
    return files


def manifest_hash(manifest: dict[str, Any]) -> str:
    body = {
        k: v for k, v in manifest.items() if k not in ("manifest_sha256", "built_at")
    }  # the build time is not content
    return sha256_json(body)


# ---------------------------------------------------------------------------------------------
# the only reader research code may use
# ---------------------------------------------------------------------------------------------
class CleanBarStore(BarStore):
    """``BarStore`` over the clean store: manifest checked, every file hash checked, only PASS months."""

    def __init__(self, root: Path, *, verify_manifest: bool = True) -> None:
        super().__init__(root, cache_seconds=0.0)
        path = root / "manifest.json"
        if not path.exists():
            msg = f"no manifest in {root}: not a clean store"
            raise CleanStoreError(msg)
        self.manifest: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        if verify_manifest and manifest_hash(self.manifest) != self.manifest.get("manifest_sha256"):
            msg = "manifest_sha256 does not match the manifest: tampered or corrupted"
            raise CleanStoreError(msg)
        self._verified: set[str] = set()

    def status(self, month: str) -> str:
        m = self.manifest["months"].get(month)
        return "NOT_LISTED" if m is None else str(m["status"])

    def pass_months(self) -> list[str]:
        return sorted(k for k, v in self.manifest["months"].items() if v["status"] == "PASS")

    def _require_range(self, start: datetime, end: datetime | None) -> None:
        lo = f"{start.year:04d}-{start.month:02d}"
        hi = lo if end is None else f"{end.year:04d}-{end.month:02d}"
        listed = sorted(self.manifest["months"])
        for month in listed:
            if lo <= month <= hi and self.status(month) != "PASS":
                msg = (
                    f"month {month} is {self.status(month)} in the clean store: no silent skipping"
                )
                raise CleanStoreError(msg)
        if lo < listed[0] or (end is not None and hi > listed[-1]) or end is None:
            msg = f"range {lo}..{hi} reaches outside the clean store ({listed[0]}..{listed[-1]})"
            raise CleanStoreError(msg)

    def _read_month(self, tf: Timeframe, month: str) -> pl.DataFrame:
        info = self.manifest["months"].get(month)
        if info is None or info["status"] != "PASS":
            msg = f"month {month} is not a PASS month of the clean store"
            raise CleanStoreError(msg)
        key = f"{tf.value}/{month}"
        if key not in self._verified:
            path = self._dir(tf) / f"{month}.parquet"
            if not path.exists() or sha256_file(path) != info["files"][tf.value]["sha256"]:
                msg = f"{key}: file missing or sha256 differs from the manifest"
                raise CleanStoreError(msg)
            self._verified.add(key)
        return super()._read_month(tf, month)

    def window(
        self, tf: Timeframe, start: datetime, end: datetime | None, limit: int
    ) -> pl.DataFrame:
        self._require_range(start, end)
        return super().window(tf, start, end, limit)

    def verify_all(self) -> int:
        """Re-hash every file of every PASS month; returns the number of files checked."""
        n = 0
        for month in self.pass_months():
            for tf in TFS:
                self._read_month(Timeframe(tf), month)
                n += 1
        return n
