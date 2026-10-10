"""Stored bars versus the terminal: classify every difference, repair only the provably benign one.

The bar ledger is append-only: the first value written for a bar stays, a later different value from
the terminal is only logged (``BAR_CHANGED``). That keeps history from moving silently, but a benign
late revision then makes the feed look DEGRADED forever. This module is the deterministic policy:

* ``LATE_TICK_VOLUME``: the bar is settled and ONLY ``tick_volume`` differs (OHLC, spread and real
  volume are identical) by a small, bounded amount. Real case, 2026-10-09 13:54 UTC M1 stored 238
  against the terminal's 239 (and the same +1 in its M5/M15/M30/H1 parents). The terminal is the
  canonical source of bars, so the stored volume is reconciled to it through the AUDITED path
  (``BarLedger.replace_bars``: a ``BAR_REPAIRED`` event with old and new values, the reason and the
  detection time). Nothing is silent.
* every other difference (a price moved, spread differs, a bar exists on one side only) is NEVER
  repaired automatically. It stays visible as a data-quality problem until a human decides.

The tick ledger is NOT used as an oracle here: MT5 counts only price-changing ticks in
``tick_volume`` and assigns ticks to bars by its own rules, so the ledger's tick counts differ from
bar volumes in almost every minute (measured: 40 of 40 sampled minutes).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Any

import polars as pl

from xau_edge.domain.timeframe import Timeframe

SETTLE = timedelta(minutes=2)
"""A bar younger than this may still be receiving late ticks: it is never reconciled yet."""

LATE_TICK_VOLUME = "LATE_TICK_VOLUME"
PRICE_DIFFERENCE = "PRICE_DIFFERENCE"
SPREAD_DIFFERENCE = "SPREAD_DIFFERENCE"
MISSING_IN_STORE = "MISSING_IN_STORE"
ONLY_IN_STORE = "ONLY_IN_STORE"
UNSETTLED_VOLUME = "UNSETTLED_VOLUME"
VOLUME_OUT_OF_BOUND = "VOLUME_OUT_OF_BOUND"

PRICE_FIELDS = ("open", "high", "low", "close")


def volume_tolerance(stored_volume: int) -> int:
    """Largest tick_volume revision still treated as a late tick: 3 ticks or 0.5%, if more."""
    return max(3, ceil(abs(stored_volume) * 0.005))


@dataclass(frozen=True)
class BarDifference:
    timeframe: str
    timestamp: datetime
    kind: str
    stored: dict[str, Any] | None
    terminal: dict[str, Any] | None
    volume_delta: int | None = None

    def as_record(self) -> dict[str, Any]:
        return {
            "timeframe": self.timeframe,
            "bar_open": self.timestamp.isoformat(),
            "kind": self.kind,
            "stored": _plain(self.stored),
            "terminal": _plain(self.terminal),
            "volume_delta": self.volume_delta,
        }


def _plain(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: row[k] for k in (*PRICE_FIELDS, "tick_volume", "spread", "real_volume") if k in row}


def classify(
    stored: dict[str, Any], terminal: dict[str, Any], timeframe: Timeframe, now: datetime
) -> str | None:
    """None when identical; otherwise exactly one kind (price beats spread beats volume)."""
    if any(stored[f] != terminal[f] for f in PRICE_FIELDS):
        return PRICE_DIFFERENCE
    if stored["spread"] != terminal["spread"] or stored["real_volume"] != terminal["real_volume"]:
        return SPREAD_DIFFERENCE
    if stored["tick_volume"] == terminal["tick_volume"]:
        return None
    if stored["timestamp"] + timeframe.delta + SETTLE > now:
        return UNSETTLED_VOLUME
    delta = abs(int(terminal["tick_volume"]) - int(stored["tick_volume"]))
    if delta > volume_tolerance(int(stored["tick_volume"])):
        return VOLUME_OUT_OF_BOUND
    return LATE_TICK_VOLUME


def compare(
    stored: pl.DataFrame, terminal: pl.DataFrame, timeframe: Timeframe, now: datetime
) -> list[BarDifference]:
    """Every difference between the two frames, bar by bar (both directions)."""
    s = {r["timestamp"]: r for r in stored.iter_rows(named=True)}
    t = {r["timestamp"]: r for r in terminal.iter_rows(named=True)}
    out: list[BarDifference] = []
    for ts in sorted(set(s) | set(t)):
        if ts not in t:
            out.append(BarDifference(timeframe.value, ts, ONLY_IN_STORE, s[ts], None))
        elif ts not in s:
            out.append(BarDifference(timeframe.value, ts, MISSING_IN_STORE, None, t[ts]))
        else:
            kind = classify(s[ts], t[ts], timeframe, now)
            if kind is not None:
                delta = int(t[ts]["tick_volume"]) - int(s[ts]["tick_volume"])
                out.append(BarDifference(timeframe.value, ts, kind, s[ts], t[ts], delta))
    return out


def late_tick_volume_rows(
    stored: pl.DataFrame, terminal: pl.DataFrame, timeframe: Timeframe, now: datetime
) -> pl.DataFrame:
    """The terminal's rows for exactly the bars the policy may reconcile (possibly none)."""
    wanted = [
        d.timestamp for d in compare(stored, terminal, timeframe, now) if d.kind == LATE_TICK_VOLUME
    ]
    if not wanted:
        return terminal.head(0)
    return terminal.filter(pl.col("timestamp").is_in(wanted))
