"""Integrity verification of the bar and tick ledgers (read-only; used by the verify scripts).

Each check returns a plain dict with ``ok`` plus the evidence, so a failure says what and where.
Immutability is verified against a saved manifest: a file older than the active partition whose
hash changed is a FAIL (history must not move); the active partition may legitimately grow.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.market import TICK_COLUMNS
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.ledger import BarLedger, LedgerError
from xau_edge.market_data.tick_ledger import TickLedger, TickLedgerError
from xau_edge.market_data.validators.market_calendar import MarketCalendar

BAR_SCHEMA = ("timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume")


def _manifest_diff(current: dict[str, str], saved: dict[str, str], active: str) -> dict[str, Any]:
    changed = sorted(k for k, v in current.items() if k in saved and saved[k] != v and k != active)
    removed = sorted(k for k in saved if k not in current)
    return {
        "changed_historical": changed,
        "removed": removed,
        "added": sorted(set(current) - set(saved)),
    }


def _bar_problems(frame: pl.DataFrame, tf: Timeframe) -> list[str]:
    problems: list[str] = []
    if tuple(frame.columns) != BAR_SCHEMA:
        problems.append(f"schema {frame.columns}")
    ts = frame["timestamp"]
    if ts.n_unique() != frame.height:
        problems.append(f"{frame.height - ts.n_unique()} duplicate timestamps")
    if not ts.is_sorted():
        problems.append("timestamps not sorted")
    bad = frame.filter(
        (pl.col("high") < pl.max_horizontal("open", "close"))
        | (pl.col("low") > pl.min_horizontal("open", "close"))
        | (pl.col("low") <= 0)
        | (pl.col("tick_volume") < 0)
        | (pl.col("spread") < 0)
    ).height
    if bad:
        problems.append(f"{bad} bars violate OHLC/volume/spread sanity")
    newest = ts.max()
    if isinstance(newest, datetime) and newest + tf.delta > datetime.now(UTC) + timedelta(
        seconds=5
    ):
        problems.append("a stored bar has not closed yet")
    return problems


def _coverage(
    frame: pl.DataFrame, tf: Timeframe, calendar: MarketCalendar
) -> tuple[int, float | None]:
    first, last = frame["timestamp"].min(), frame["timestamp"].max()
    if not isinstance(first, datetime) or not isinstance(last, datetime):
        return 0, None
    slots = pl.datetime_range(first, last, interval=f"{tf.minutes}m", eager=True)
    table = pl.DataFrame({"t": slots.dt.replace_time_zone("UTC")})
    closed = table.select(calendar.closed_span_expr(pl.col("t"), tf.minutes).alias("c"))["c"]
    expected = int((~closed).sum())
    return expected, (round(frame.height / expected, 5) if expected else None)


def verify_bars(
    ledger: BarLedger,
    symbol: str,
    calendar: MarketCalendar,
    *,
    saved_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Readability, schema, ordering, uniqueness, OHLC sanity, immutability and coverage per TF."""
    report: dict[str, Any] = {"symbol": symbol, "timeframes": {}, "ok": True}
    for tf in Timeframe:
        entry: dict[str, Any] = {"ok": True, "problems": []}
        problems: list[str] = entry["problems"]
        report["timeframes"][tf.value] = entry
        try:
            frame = ledger.load(symbol, tf)
        except LedgerError as exc:
            problems.append(f"unreadable: {exc}")
            entry["ok"] = report["ok"] = False
            continue
        entry["rows"] = frame.height
        if frame.height == 0:
            entry["state"] = "EMPTY"
            continue
        problems += _bar_problems(frame, tf)
        expected, coverage = _coverage(frame, tf, calendar)
        entry["expected_open_slots"] = expected
        entry["coverage"] = coverage
        files = ledger.file_hashes(symbol, tf)
        if saved_manifest is not None:
            old = saved_manifest.get("timeframes", {}).get(tf.value, {}).get("files", {})
            diff = _manifest_diff(files, old, active=max(files) if files else "")
            entry["manifest"] = diff
            moved = diff["changed_historical"] + diff["removed"]
            if moved:
                problems.append(f"historical files changed/removed: {moved}")
        entry["ok"] = not problems
        report["ok"] = report["ok"] and entry["ok"]
    return report


def _day_problems(day: str, frame: pl.DataFrame) -> tuple[list[str], int]:
    problems: list[str] = []
    if tuple(frame.columns) != TICK_COLUMNS:
        problems.append(f"{day}: schema {frame.columns}")
    if frame.height == 0:
        return problems, 0
    if not frame["timestamp_msc"].is_sorted():
        problems.append(f"{day}: ticks not ordered by time")
    key = [c for c in TICK_COLUMNS if c != "timestamp"]
    dupes = frame.height - frame.unique(subset=key).height
    if dupes:
        problems.append(f"{day}: {dupes} exact duplicate ticks")
    lo, hi = frame["timestamp"].min(), frame["timestamp"].max()
    if (
        isinstance(lo, datetime)
        and isinstance(hi, datetime)
        and (lo.strftime("%Y-%m-%d") != day or hi.strftime("%Y-%m-%d") != day)
    ):
        problems.append(f"{day}: ticks outside the partition's UTC day")
    quoted = frame.filter((pl.col("bid") > 0) & (pl.col("ask") > 0))
    crossed = quoted.filter(pl.col("ask") < pl.col("bid")).height
    if crossed:
        problems.append(f"{day}: {crossed} ticks with ask < bid")
    if frame.filter((pl.col("bid") < 0) | (pl.col("ask") < 0)).height:
        problems.append(f"{day}: negative prices")
    return problems, crossed


def verify_ticks(
    ledger: TickLedger,
    symbol: str,
    *,
    saved_manifest: dict[str, Any] | None = None,
    max_days: int | None = None,
) -> dict[str, Any]:
    """Per day: readability, order, duplicates, crossed/negative spreads, day containment."""
    problems: list[str] = []
    report: dict[str, Any] = {"symbol": symbol, "days": 0, "rows": 0, "problems": problems}
    days = ledger.days(symbol)
    if max_days:
        days = days[-max_days:]
    crossed_total = 0
    for day in days:
        try:
            frame = ledger.read_day(symbol, day)
        except TickLedgerError as exc:
            problems.append(str(exc))
            continue
        report["days"] += 1
        report["rows"] += frame.height
        found, crossed = _day_problems(day, frame)
        problems += found
        crossed_total += crossed
    if saved_manifest is not None:
        current = {d: v["sha256"] for d, v in ledger.manifest(symbol)["files"].items()}
        old = {d: v["sha256"] for d, v in saved_manifest.get("files", {}).items()}
        diff = _manifest_diff(current, old, max(current) if current else "")
        report["manifest"] = diff
        moved = diff["changed_historical"] + diff["removed"]
        if moved:
            problems.append(f"historical days changed/removed: {moved}")
    windows = ledger.coverage(symbol)
    if any(b > c for (_, b), (c, _) in pairwise(windows)):
        problems.append("coverage windows overlap (should be merged)")
    report["crossed_ticks"] = crossed_total
    report["coverage_windows"] = len(windows)
    report["ok"] = not problems
    return report


def load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None
