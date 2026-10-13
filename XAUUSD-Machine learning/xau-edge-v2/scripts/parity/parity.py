"""G3 parity: does V2 read and interpret the shared data exactly like V1?

Run with the V1 interpreter (it has V1's code) and V2's sources on the path:

    <V1>/.venv/Scripts/python.exe scripts/parity/parity.py [--out results.json] [--quick]

This is TOOLING: it imports V1 only to compare outputs. The V2 package itself never imports V1
(enforced by tests/unit/test_isolation.py). Nothing here writes to the shared store.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
import urllib.request
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "src"))

import polars as pl  # noqa: E402
from xau_edge.domain.timeframe import Timeframe as V1Tf  # noqa: E402
from xau_edge.market_data.broker_clock import BrokerClock as V1Clock  # noqa: E402
from xau_edge.market_data.calendars import ftmo_calendar  # noqa: E402
from xau_edge.market_data.ledger import BarLedger  # noqa: E402
from xau_edge.market_data.session import market_status as v1_status  # noqa: E402
from xau_edge.market_data.tick_ledger import TickLedger  # noqa: E402
from xau_edge.trading.live_source import spec_from_broker  # noqa: E402

from xau_edge_v2.data.bar_store import BarStore  # noqa: E402
from xau_edge_v2.data.broker_profile import default_calendar, load_profile  # noqa: E402
from xau_edge_v2.data.live_feed import LiveFeed  # noqa: E402
from xau_edge_v2.data.tick_store import TickStore  # noqa: E402
from xau_edge_v2.domain.contract import Timeframe  # noqa: E402
from xau_edge_v2.domain.market import BrokerClock  # noqa: E402

DATA = Path("Z:/Coding/Projects/AI-Harness/xau-edge/data/market")
SYMBOL = "XAUUSD"
V1_API = "http://127.0.0.1:8000"
V2_API = "http://127.0.0.1:8200"
SEED = 20261012
COLS = ["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]


def digest(frame: pl.DataFrame) -> str:
    h = hashlib.sha256()
    for c in COLS:
        if c in frame.columns:
            col = frame[c]
            if col.dtype.is_temporal():
                col = col.dt.epoch("us")
            h.update(col.to_numpy().tobytes())
    return h.hexdigest()


def get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def section(name: str) -> dict[str, Any]:
    return {"name": name, "checks": 0, "mismatches": 0, "examples": [], "notes": []}


def record(sec: dict[str, Any], ok: bool, detail: str) -> None:
    sec["checks"] += 1
    if not ok:
        sec["mismatches"] += 1
        if len(sec["examples"]) < 5:
            sec["examples"].append(detail)


def sample_instants(rng: random.Random, n: int) -> list[datetime]:
    lo = datetime(2004, 6, 1, tzinfo=UTC)
    span = int((datetime(2026, 12, 31, tzinfo=UTC) - lo).total_seconds())
    return [lo + timedelta(seconds=rng.randrange(span)) for _ in range(n)]


def dst_boundaries() -> list[datetime]:
    """Every US and EU DST transition 2004..2026, +/- 3 hours in 5-minute steps, plus weekends."""
    out: list[datetime] = []
    for year in range(2004, 2027):
        for zone in ("America/New_York", "Europe/Athens"):
            tz = ZoneInfo(zone)
            prev = datetime(year, 1, 1, tzinfo=UTC)
            cur = prev
            while cur.year == year:
                nxt = cur + timedelta(days=1)
                if cur.astimezone(tz).utcoffset() != nxt.astimezone(tz).utcoffset():
                    probe = cur
                    while probe.astimezone(tz).utcoffset() == cur.astimezone(tz).utcoffset():
                        probe += timedelta(minutes=1)
                    out.extend(probe + timedelta(minutes=5 * k) for k in range(-36, 37))
                cur = nxt
    return out


# --------------------------------------------------------------------------------------------
def check_bars(quick: bool) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    v1, v2 = BarLedger(DATA), BarStore(DATA, cache_seconds=0.0)
    sec_files = section("bars: every monthly file, full content digest (public read paths)")
    sec_tail = section("bars: random tail(limit, before) windows")
    sec_win = section("bars: random [start,end) windows")
    total_rows: dict[str, int] = {}
    for tf in Timeframe:
        t1 = V1Tf(tf.value)
        months = v2.months(tf)
        sample_months = months if not quick else rng.sample(months, min(12, len(months)))
        total = 0
        for month in sample_months:
            y, m = int(month[:4]), int(month[5:])
            start = datetime(y, m, 1, tzinfo=UTC)
            end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=UTC)
            a = v1.load(SYMBOL, t1, start, end)
            pages: list[pl.DataFrame] = []
            cursor = start
            while True:
                page = v2.window(tf, cursor, end, 5000)
                if page.height == 0:
                    break
                pages.append(page)
                cursor = page["timestamp"][-1] + timedelta(microseconds=1)
                if page.height < 5000:
                    break
            b = pl.concat(pages) if pages else a.head(0)
            total += a.height
            record(
                sec_files,
                a.height == b.height and digest(a) == digest(b),
                f"{tf.value} {month}: v1 {a.height} v2 {b.height}",
            )
        total_rows[tf.value] = total
        for _ in range(8 if quick else 40):
            month = rng.choice(months)
            full = v1.load(
                SYMBOL, t1, datetime(int(month[:4]), int(month[5:]), 1, tzinfo=UTC), None
            )
            if full.height == 0:
                continue
            before = full["timestamp"][rng.randrange(full.height)]
            limit = rng.choice([1, 2, 10, 97, 300, 1000, 5000])
            ta = v1.tail(SYMBOL, t1, limit, end=before)
            tb = v2.tail(tf, limit, before=before)
            record(
                sec_tail,
                ta.height == tb.height and digest(ta) == digest(tb),
                f"{tf.value} before {before} limit {limit}: {ta.height} vs {tb.height}",
            )
            start = before
            end = start + timedelta(minutes=rng.choice([30, 600, 4000, 90000]))
            wa = v1.load(SYMBOL, t1, start, end).head(limit)
            wb = v2.window(tf, start, end, limit)
            record(
                sec_win,
                wa.height == wb.height and digest(wa) == digest(wb),
                f"{tf.value} [{start}, {end}) limit {limit}: {wa.height} vs {wb.height}",
            )
    sec_files["notes"].append(f"rows compared per timeframe: {total_rows}")
    return [sec_files, sec_tail, sec_win]


def check_bars_api(quick: bool) -> dict[str, Any]:
    sec = section("bars: HTTP parity, V2 /api/v2/market/bars vs V1 /md/XAUUSD/bars")
    rng = random.Random(SEED + 1)
    try:
        get_json(f"{V2_API}/api/v2/health")
        get_json(f"{V1_API}/md/status")
    except OSError as exc:
        sec["notes"].append(f"SKIPPED: a service is not reachable ({exc})")
        return sec
    v2 = BarStore(DATA)
    for tf in Timeframe:
        for _ in range(4 if quick else 12):
            cov = v2.coverage(tf)
            assert cov.oldest and cov.newest
            span = (cov.newest - cov.oldest).total_seconds()
            before = cov.oldest + timedelta(seconds=rng.uniform(0.02, 0.98) * span)
            limit = rng.choice([50, 300, 1000])
            iso = before.strftime("%Y-%m-%dT%H:%M:%SZ")
            a = get_json(
                f"{V1_API}/md/XAUUSD/bars?timeframe={tf.value}&limit={limit}&before={iso}"
            )["bars"]
            b = get_json(
                f"{V2_API}/api/v2/market/bars?timeframe={tf.value}&limit={limit}&before={iso}"
            )["bars"]
            key = lambda r: (  # noqa: E731
                datetime.fromisoformat(r["time"].replace("Z", "+00:00")),
                r["open"], r["high"], r["low"], r["close"], r["tick_volume"], r["spread"],
            )  # fmt: skip
            record(
                sec,
                [key(r) for r in a] == [key(r) for r in b],
                f"{tf.value} before {iso} limit {limit}: {len(a)} vs {len(b)}",
            )
    return sec


def check_ticks(quick: bool) -> dict[str, Any]:
    sec = section("ticks: random [start,end) windows, V2 TickStore vs V1 TickLedger")
    rng = random.Random(SEED + 2)
    v1, v2 = TickLedger(DATA), TickStore(DATA)
    days_a, days_b = v1.days(SYMBOL), v2.days()
    record(sec, days_a == days_b, f"day lists differ: {len(days_a)} vs {len(days_b)}")
    sec["notes"].append(f"stored tick days: {len(days_b)} ({days_b[0]} .. {days_b[-1]})")
    rows = 0
    for _ in range(20 if quick else 150):
        day = rng.choice(days_b)
        start = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(
            seconds=rng.randrange(86_400)
        )
        end = start + timedelta(minutes=rng.choice([1, 5, 30, 120]))
        limit = rng.choice([10, 1000, 100_000])
        a = v1.load(SYMBOL, start, end, limit=limit)
        b = v2.load(start, end, limit=limit)
        rows += a.height
        same = a.height == b.height and (
            a.height == 0
            or (
                a["timestamp_msc"].equals(b["timestamp_msc"])
                and a["bid"].equals(b["bid"])
                and a["ask"].equals(b["ask"])
            )
        )
        record(sec, same, f"[{start}, {end}) limit {limit}: {a.height} vs {b.height}")
    sec["notes"].append(f"tick rows compared: {rows}")
    return sec


def check_calendar_clock(quick: bool) -> list[dict[str, Any]]:
    rng = random.Random(SEED + 3)
    sec_status = section(
        "calendar: market status (OPEN/CLOSED/ROLLOVER) at random instants + every DST boundary"
    )
    sec_clock = section("broker clock NY+7: UTC -> server wall at the same instants")
    sec_back = section(
        "broker clock NY+7: server wall -> UTC (strict=False, DST gaps/folds -> null)"
    )
    n = 3000 if quick else 60_000
    instants = sample_instants(rng, n) + dst_boundaries()
    cal1, cal2 = ftmo_calendar(), default_calendar()
    c1, c2 = V1Clock.parse("NY+7"), BrokerClock.parse("NY+7")
    for t in instants:
        s1, s2 = v1_status(t, cal1).value, cal2.status(t).value
        record(sec_status, s1 == s2, f"{t.isoformat()}: v1 {s1} v2 {s2}")
    sec_status["notes"].append(
        f"instants: {len(instants)} (incl. {len(dst_boundaries())} around DST changes)"
    )
    for t in instants:
        a = c1.to_server_wall(t)
        b = c2.to_server_wall(t)
        record(sec_clock, a == b, f"{t.isoformat()}: v1 {a} v2 {b}")
    naives = [t.replace(tzinfo=None) + timedelta(hours=7) for t in instants]
    series = pl.Series("t", naives, dtype=pl.Datetime("us"))
    back1 = c1.server_to_utc(series, strict=False).to_list()
    nulls = 0
    for naive, v1_value in zip(naives, back1, strict=True):
        v2_value = c2.server_to_utc(naive, strict=False)
        nulls += v2_value is None
        record(sec_back, v1_value == v2_value, f"{naive}: v1 {v1_value} v2 {v2_value}")
    sec_back["notes"].append(f"null (gap/fold) results: {nulls} (identical in both)")
    return [sec_status, sec_clock, sec_back]


def check_spec_and_config() -> list[dict[str, Any]]:
    sec_spec = section(
        "symbol spec: V2 LiveFeed.symbol_info vs V1 spec_from_broker (same live.json)"
    )
    sec_cfg = section("config: V2 JSON copy vs V1 YAML profile + session exceptions")
    raw = json.loads((DATA / "live.json").read_text(encoding="utf-8")).get("symbol_spec")
    s1 = spec_from_broker(raw)
    s2 = LiveFeed(DATA, cache_seconds=0.0).symbol_info()
    assert s1 is not None and s2 is not None
    a = (
        {k: v for k, v in asdict(s1).items()}
        if hasattr(s1, "__dataclass_fields__")
        else s1.model_dump()
    )
    b = s2.model_dump()
    for key, v1_value in a.items():
        if key == "symbol":
            continue
        record(sec_spec, key in b and b[key] == v1_value, f"{key}: v1 {v1_value} v2 {b.get(key)}")
    sec_spec["notes"].append(f"fields compared: {sorted(k for k in a if k != 'symbol')}")
    v1_cal = ftmo_calendar()
    v2_cfg = load_profile().calendar
    for field in (
        "timezone",
        "weekend_close_minute",
        "weekend_open_minute",
        "daily_break_start_minute",
        "daily_break_end_minute",
    ):
        record(
            sec_cfg,
            getattr(v1_cal, field) == getattr(v2_cfg, field),
            f"{field}: v1 {getattr(v1_cal, field)} v2 {getattr(v2_cfg, field)}",
        )
    w1 = sorted((w.start, w.end, w.reason) for w in v1_cal.closures)
    w2 = sorted((w.start, w.end, w.reason) for w in v2_cfg.closures)
    record(sec_cfg, w1 == w2, f"closure windows: v1 {len(w1)} v2 {len(w2)}")
    record(sec_cfg, load_profile().clock.token == "NY+7", "clock token")
    return [sec_spec, sec_cfg]


def check_quote_api() -> dict[str, Any]:
    sec = section("quote: V2 /api/v2/market/quote vs V1 /md/XAUUSD/quote (same live file)")
    try:
        for _ in range(30):
            a = get_json(f"{V1_API}/md/XAUUSD/quote")
            b = get_json(f"{V2_API}/api/v2/market/quote")
            if (
                a.get("timestamp", "").replace("Z", "")[:23]
                == (b.get("timestamp") or "").replace("Z", "").replace("+00:00", "")[:23]
            ):
                same = all(a.get(k) == b.get(k) for k in ("bid", "ask", "spread_points"))
                record(sec, same, f"v1 {a} v2 {b}")
                state_ok = (a.get("state") == b.get("state")) or {
                    a.get("state"),
                    b.get("state"),
                } <= {"FRESH", "STALE"}
                record(sec, state_ok, f"state v1 {a.get('state')} v2 {b.get('state')}")
            time.sleep(0.3)
    except OSError as exc:
        sec["notes"].append(f"SKIPPED: a service is not reachable ({exc})")
    if sec["checks"] == 0:
        sec["notes"].append("no pair of reads with the same quote timestamp was captured")
    return sec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(HERE.parent / "parity_results.json"))
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    t0 = time.time()
    sections: list[dict[str, Any]] = []
    sections += check_bars(args.quick)
    sections.append(check_bars_api(args.quick))
    sections.append(check_ticks(args.quick))
    sections += check_calendar_clock(args.quick)
    sections += check_spec_and_config()
    sections.append(check_quote_api())
    result = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "quick": args.quick,
        "seconds": round(time.time() - t0, 1),
        "sections": sections,
        "total_checks": sum(s["checks"] for s in sections),
        "total_mismatches": sum(s["mismatches"] for s in sections),
    }
    Path(args.out).write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    for s in sections:
        flag = (
            "OK "
            if s["mismatches"] == 0 and s["checks"] > 0
            else "FAIL"
            if s["mismatches"]
            else "SKIP"
        )
        print(f"[{flag}] {s['checks']:>7} checks {s['mismatches']:>4} mismatches  {s['name']}")
        for note in s["notes"]:
            print(f"        note: {note}")
        for ex in s["examples"]:
            print(f"        MISMATCH: {ex}")
    total, bad, secs = result["total_checks"], result["total_mismatches"], result["seconds"]
    print(f"total {total} checks, {bad} mismatches, {secs} s")
    return 1 if result["total_mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
