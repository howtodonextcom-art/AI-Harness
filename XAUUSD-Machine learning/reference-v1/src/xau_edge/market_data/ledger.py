"""Persistent, restart-safe store of CLOSED bars collected from the MT5 terminal.

Layout: ``<root>/<SYMBOL>/<TF>/<YYYY-MM>.parquet`` (one file per month, sorted, unique by open
time) plus an append-only ``<root>/<SYMBOL>/events.jsonl``. Rules:

* only CLOSED bars are written (forming bars never reach the store);
* a bar that is already stored is never overwritten: an identical bar is a duplicate (counted), a
  DIFFERENT bar with the same open time is a CHANGE (kept as stored, recorded as an event) so
  history is never silently mutated;
* files are replaced atomically (temp + rename), so a crash leaves the old or the new month, never a
  torn file; re-running the same collection is idempotent;
* ``manifest`` hashes every month file so a change on disk is detectable.

This is the current/incremental layer; the research raw store (``RawStore``) stays untouched.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.bars import coerce_bars, empty_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.event_log import append_event, read_events
from xau_edge.market_data.locking import file_lock

MAX_AUDITED_BARS = 1000
PRICE_COLUMNS = ("open", "high", "low", "close", "tick_volume", "real_volume")
_FILE_COLUMNS = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
)


class LedgerError(RuntimeError):
    """The bar ledger is unreadable or was given unusable input."""


@dataclass(frozen=True)
class AppendResult:
    """What an append did."""

    received: int
    new: int
    duplicates: int
    changed: int
    changed_timestamps: tuple[datetime, ...]


def _as_dt(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _month_key(ts: datetime) -> str:
    return f"{ts.year:04d}-{ts.month:02d}"


class BarLedger:
    """Closed-bar store for one or more symbols and timeframes."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._reported: set[tuple[str, str, datetime]] = set()

    # -- paths ---------------------------------------------------------------------------------

    def _dir(self, symbol: str, timeframe: Timeframe) -> Path:
        if not symbol.isalnum():
            msg = f"unsafe symbol {symbol!r}"
            raise LedgerError(msg)
        return self.root / symbol / timeframe.value

    def _events(self, symbol: str) -> Path:
        return self.root / symbol / "events.jsonl"

    # -- writing -------------------------------------------------------------------------------

    def append_closed(
        self,
        symbol: str,
        timeframe: Timeframe,
        bars: pl.DataFrame,
        *,
        now: datetime | None = None,
        reason: str = "append",
    ) -> AppendResult:
        """Merge ``bars`` (closed only) into the monthly files; never overwrite a stored bar."""
        self._dir(symbol, timeframe)  # validates the symbol before anything touches the disk
        with file_lock(self.root / symbol / ".write.lock"):
            return self._append_locked(symbol, timeframe, bars, now=now, reason=reason)

    def _append_locked(
        self,
        symbol: str,
        timeframe: Timeframe,
        bars: pl.DataFrame,
        *,
        now: datetime | None,
        reason: str,
    ) -> AppendResult:
        stamp = now or datetime.now(UTC)
        if bars.height == 0:
            return AppendResult(0, 0, 0, 0, ())
        frame = (
            coerce_bars(bars)
            .select(_FILE_COLUMNS)
            .unique("timestamp", keep="last")
            .sort("timestamp")
        )
        newest = _as_dt(frame["timestamp"].max())
        if newest is not None and newest + timeframe.delta > stamp:
            msg = "refusing to store a bar that has not closed yet"
            raise LedgerError(msg)
        new = duplicates = changed = 0
        changed_at: list[datetime] = []
        months = frame.with_columns(
            pl.col("timestamp").dt.strftime("%Y-%m").alias("_m")
        ).partition_by("_m", as_dict=True, maintain_order=True)
        for key, part in months.items():
            month = str(key[0] if isinstance(key, tuple) else key)
            incoming = part.drop("_m")
            stored = self._read_month(symbol, timeframe, month)
            joined = incoming.join(stored, on="timestamp", how="left", suffix="_old")
            is_new = joined["open_old"].is_null()
            same = pl.all_horizontal(*[pl.col(c) == pl.col(f"{c}_old") for c in PRICE_COLUMNS])
            known = joined.filter(~is_new)
            n_same = int(known.select(same.sum()).item()) if known.height else 0
            diff = known.filter(~same) if known.height else known
            changed_ts = diff["timestamp"].to_list() if diff.height else []
            fresh = incoming.join(stored.select("timestamp"), on="timestamp", how="anti")
            new += fresh.height
            duplicates += n_same
            changed += len(changed_ts)
            changed_at += changed_ts
            if fresh.height:
                merged = pl.concat([stored, fresh]).sort("timestamp")
                self._write_month(symbol, timeframe, month, merged)
        result = AppendResult(frame.height, new, duplicates, changed, tuple(changed_at))
        fresh_changes = [
            t for t in changed_at if (symbol, timeframe.value, t) not in self._reported
        ]
        self._reported.update((symbol, timeframe.value, t) for t in changed_at)
        if fresh_changes:  # one event per differing bar, not one per poll
            detail = {
                "timeframe": timeframe.value,
                "timestamps": [t.isoformat() for t in fresh_changes[:50]],
                "count": len(fresh_changes),
                "reason": reason,
            }
            self.log_event(symbol, "BAR_CHANGED", detail, now=stamp)
        return result

    def replace_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        bars: pl.DataFrame,
        *,
        now: datetime | None = None,
        reason: str = "repair",
    ) -> list[dict[str, Any]]:
        """AUDITED replacement of already stored bars (never an insertion, never silent).

        Only bars whose open time is stored AND whose values differ are replaced. Every replacement
        is recorded in a ``BAR_REPAIRED`` event with the old and the new values. Callers must decide
        explicitly (``scripts/repair_changed_bars.py --apply``); normal collection never uses it.
        """
        self._dir(symbol, timeframe)
        stamp = now or datetime.now(UTC)
        changes: list[dict[str, Any]] = []
        with file_lock(self.root / symbol / ".write.lock"):
            incoming = coerce_bars(bars).select(_FILE_COLUMNS).unique("timestamp", keep="last")
            months = incoming.with_columns(
                pl.col("timestamp").dt.strftime("%Y-%m").alias("_m")
            ).partition_by("_m", as_dict=True, maintain_order=True)
            for key, part in months.items():
                month = str(key[0] if isinstance(key, tuple) else key)
                stored = self._read_month(symbol, timeframe, month)
                new = part.drop("_m")
                joined = new.join(stored, on="timestamp", how="inner", suffix="_old")
                differs = pl.any_horizontal(
                    *[pl.col(c) != pl.col(f"{c}_old") for c in PRICE_COLUMNS]
                )
                diff = joined.filter(differs)
                if diff.height == 0:
                    continue
                for row in diff.iter_rows(named=True):
                    changes.append(
                        {
                            "timestamp": row["timestamp"].isoformat(),
                            "old": [row[f"{c}_old"] for c in PRICE_COLUMNS],
                            "new": [row[c] for c in PRICE_COLUMNS],
                        }
                    )
                keep = stored.join(diff.select("timestamp"), on="timestamp", how="anti")
                replacement = diff.select(_FILE_COLUMNS)
                self._write_month(
                    symbol, timeframe, month, pl.concat([keep, replacement]).sort("timestamp")
                )
        if changes:
            self.log_event(
                symbol,
                "BAR_REPAIRED",
                {
                    "timeframe": timeframe.value,
                    "reason": reason,
                    "count": len(changes),
                    "bars": changes[
                        :MAX_AUDITED_BARS
                    ],  # every repaired bar is named (health matches on them)
                },
                now=stamp,
            )
        return changes

    def log_event(
        self, symbol: str, kind: str, detail: dict[str, Any], *, now: datetime | None = None
    ) -> None:
        """Append one JSON line to the symbol's event log (reconciliation, gaps, reconnects)."""
        row = {"at": (now or datetime.now(UTC)).isoformat(), "kind": kind, **detail}
        append_event(self._events(symbol), row)

    def events(self, symbol: str) -> list[dict[str, Any]]:
        """All logged events across segments (bad lines are skipped, not trusted)."""
        return read_events(self._events(symbol))

    # -- reading -------------------------------------------------------------------------------

    def _read_month(self, symbol: str, timeframe: Timeframe, month: str) -> pl.DataFrame:
        path = self._dir(symbol, timeframe) / f"{month}.parquet"
        if not path.exists():
            return empty_bars().select(_FILE_COLUMNS)
        try:
            return pl.read_parquet(path).select(_FILE_COLUMNS)
        except (OSError, pl.exceptions.PolarsError, pl.exceptions.ColumnNotFoundError) as exc:
            msg = f"unreadable ledger file {path.name}: {exc}"
            raise LedgerError(msg) from exc

    def _write_month(
        self, symbol: str, timeframe: Timeframe, month: str, frame: pl.DataFrame
    ) -> None:
        directory = self._dir(symbol, timeframe)
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{month}.parquet"
        tmp = directory / f"{month}.parquet.tmp"
        frame.sort("timestamp").write_parquet(tmp)
        tmp.replace(target)

    def months(self, symbol: str, timeframe: Timeframe) -> list[str]:
        directory = self._dir(symbol, timeframe)
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.parquet"))

    def load(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pl.DataFrame:
        """Stored closed bars in ``[start, end)`` (all when unbounded), sorted and unique."""
        wanted = self.months(symbol, timeframe)
        if start is not None:
            wanted = [m for m in wanted if m >= _month_key(start)]
        if end is not None:
            wanted = [m for m in wanted if m <= _month_key(end)]
        parts = [self._read_month(symbol, timeframe, m) for m in wanted]
        if not parts:
            return empty_bars().select(_FILE_COLUMNS)
        frame = pl.concat(parts).unique("timestamp", keep="first").sort("timestamp")
        if start is not None:
            frame = frame.filter(pl.col("timestamp") >= start)
        if end is not None:
            frame = frame.filter(pl.col("timestamp") < end)
        return frame

    def tail(
        self, symbol: str, timeframe: Timeframe, limit: int, end: datetime | None = None
    ) -> pl.DataFrame:
        """Newest ``limit`` stored bars before ``end``; reads only as many month files as needed."""
        months = self.months(symbol, timeframe)
        if end is not None:
            months = [m for m in months if m <= _month_key(end)]
        parts: list[pl.DataFrame] = []
        rows = 0
        for month in reversed(months):
            frame = self._read_month(symbol, timeframe, month)
            if end is not None:
                frame = frame.filter(pl.col("timestamp") < end)
            parts.append(frame)
            rows += frame.height
            if rows >= limit:
                break
        if not parts:
            return empty_bars().select(_FILE_COLUMNS)
        return pl.concat(parts).unique("timestamp", keep="first").sort("timestamp").tail(limit)

    def latest(self, symbol: str, timeframe: Timeframe) -> datetime | None:
        """Open time of the newest stored bar."""
        months = self.months(symbol, timeframe)
        for month in reversed(months):
            frame = self._read_month(symbol, timeframe, month)
            if frame.height:
                return _as_dt(frame["timestamp"].max())
        return None

    def earliest(self, symbol: str, timeframe: Timeframe) -> datetime | None:
        for month in self.months(symbol, timeframe):
            frame = self._read_month(symbol, timeframe, month)
            if frame.height:
                return _as_dt(frame["timestamp"].min())
        return None

    # -- integrity -----------------------------------------------------------------------------

    def file_hashes(self, symbol: str, timeframe: Timeframe) -> dict[str, str]:
        """SHA-256 of every month file (bytes only: works even when a file is unreadable)."""
        return {
            m: hashlib.sha256(
                (self._dir(symbol, timeframe) / f"{m}.parquet").read_bytes()
            ).hexdigest()
            for m in self.months(symbol, timeframe)
        }

    def file_rows(self, symbol: str, timeframe: Timeframe) -> dict[str, int]:
        """Row count of every month file (from the parquet footer, no full read)."""
        out: dict[str, int] = {}
        for month in self.months(symbol, timeframe):
            path = self._dir(symbol, timeframe) / f"{month}.parquet"
            try:
                out[month] = int(pl.scan_parquet(path).select(pl.len()).collect().item())
            except (OSError, pl.exceptions.PolarsError):
                out[month] = -1
        return out

    def manifest(self, symbol: str) -> dict[str, Any]:
        """Per timeframe: rows, first/last bar and the SHA-256 of every month file."""
        out: dict[str, Any] = {"symbol": symbol, "timeframes": {}}
        for tf in Timeframe:
            files = {}
            rows = 0
            for month in self.months(symbol, tf):
                path = self._dir(symbol, tf) / f"{month}.parquet"
                files[month] = hashlib.sha256(path.read_bytes()).hexdigest()
                rows += self._read_month(symbol, tf, month).height
            if files:
                out["timeframes"][tf.value] = {
                    "rows": rows,
                    "first": self.earliest(symbol, tf),
                    "last": self.latest(symbol, tf),
                    "files": files,
                    "rows_by_file": self.file_rows(symbol, tf),
                    "dataset_id": hashlib.sha256("|".join(files.values()).encode()).hexdigest()[
                        :16
                    ],
                }
        return out
