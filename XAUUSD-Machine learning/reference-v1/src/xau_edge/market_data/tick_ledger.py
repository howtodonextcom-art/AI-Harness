"""Append-only, restart-safe store of raw ticks from the MT5 terminal (daily Parquet partitions).

Layout: ``<root>/<SYMBOL>/ticks/<YYYY>/<YYYY-MM-DD>.parquet`` (UTC days, zstd), a per-symbol
``ticks/coverage.json`` (which ``[start, end)`` windows were fetched COMPLETELY) and
``ticks/events.jsonl``. Rules:

* a fetched window is recorded as covered only when the terminal returned all of it (the caller
  splits windows that hit the per-call limit), so "no ticks" in a covered window means no ticks;
* stored ticks are never overwritten: inside an already covered window the stored ticks are
  authoritative and a different answer from the terminal is logged as ``TICKS_CHANGED`` instead of
  being merged; outside covered windows new ticks are added;
* exact duplicate rows are dropped; distinct ticks sharing a millisecond are all kept;
* files are replaced atomically (temp + rename); re-running a fetch is idempotent;
* memory is bounded by one day (a few hundred thousand rows for XAUUSD);
* nothing here stores credentials or account data. Retention is explicit (``prune``/``archive``),
  never automatic, and defaults to keeping everything.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from xau_edge.domain.market import TICK_COLUMNS, conform_ticks, empty_ticks
from xau_edge.market_data.event_log import append_event, read_events
from xau_edge.market_data.locking import file_lock

_KEY = [c for c in TICK_COLUMNS if c != "timestamp"]


class TickLedgerError(RuntimeError):
    """The tick ledger is unreadable or was given unusable input."""


@dataclass(frozen=True)
class TickAppendResult:
    """What an append did."""

    received: int
    new: int
    duplicates: int
    conflicts: int
    windows_recorded: int


def _day(ts: datetime) -> str:
    return ts.astimezone(UTC).strftime("%Y-%m-%d")


def _merge(windows: list[list[str]]) -> list[list[str]]:
    """Merge touching/overlapping ``[start, end)`` ISO windows."""
    out: list[list[str]] = []
    for start, end in sorted(windows):
        if out and start <= out[-1][1]:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


class TickLedger:
    """Daily-partitioned raw tick store for one or more symbols."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # -- paths ---------------------------------------------------------------------------------

    def _dir(self, symbol: str) -> Path:
        if not symbol.isalnum():
            msg = f"unsafe symbol {symbol!r}"
            raise TickLedgerError(msg)
        return self.root / symbol / "ticks"

    def _file(self, symbol: str, day: str) -> Path:
        return self._dir(symbol) / day[:4] / f"{day}.parquet"

    # -- coverage ------------------------------------------------------------------------------

    def coverage(self, symbol: str) -> list[tuple[datetime, datetime]]:
        """Merged windows fetched completely."""
        path = self._dir(symbol) / "coverage.json"
        if not path.exists():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return [
                (datetime.fromisoformat(a), datetime.fromisoformat(b)) for a, b in raw["windows"]
            ]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            msg = f"unreadable tick coverage: {exc}"
            raise TickLedgerError(msg) from exc

    def _save_coverage(self, symbol: str, windows: list[list[str]]) -> None:
        path = self._dir(symbol) / "coverage.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"windows": _merge(windows)}), encoding="utf-8")
        tmp.replace(path)

    def uncovered(
        self, symbol: str, start: datetime, end: datetime
    ) -> list[tuple[datetime, datetime]]:
        """The parts of ``[start, end)`` that have not been fetched completely yet."""
        gaps: list[tuple[datetime, datetime]] = []
        cursor = start
        for a, b in self.coverage(symbol):
            if b <= cursor:
                continue
            if a >= end:
                break
            if a > cursor:
                gaps.append((cursor, min(a, end)))
            cursor = max(cursor, b)
            if cursor >= end:
                break
        if cursor < end:
            gaps.append((cursor, end))
        return gaps

    # -- writing -------------------------------------------------------------------------------

    def append(
        self,
        symbol: str,
        ticks: pl.DataFrame,
        window: tuple[datetime, datetime],
        *,
        now: datetime | None = None,
        reason: str = "append",
    ) -> TickAppendResult:
        """Store ``ticks`` fetched COMPLETELY for ``[window[0], window[1])`` and record coverage."""
        with file_lock(self._dir(symbol) / ".write.lock"):
            return self._append_locked(symbol, ticks, window, now=now, reason=reason)

    def _append_locked(
        self,
        symbol: str,
        ticks: pl.DataFrame,
        window: tuple[datetime, datetime],
        *,
        now: datetime | None,
        reason: str,
    ) -> TickAppendResult:
        stamp = now or datetime.now(UTC)
        start, end = window
        if end <= start or start.tzinfo is None or end.tzinfo is None:
            msg = "window must be timezone-aware and increasing"
            raise TickLedgerError(msg)
        if end > stamp + timedelta(seconds=1):
            msg = "refusing to record coverage for a window that has not ended"
            raise TickLedgerError(msg)
        frame = conform_ticks(ticks)
        if frame.height and (
            frame["timestamp"].min() < start.astimezone(UTC)  # type: ignore[operator]
            or frame["timestamp"].max() >= end.astimezone(UTC)  # type: ignore[operator]
        ):
            msg = "ticks fall outside the declared window"
            raise TickLedgerError(msg)
        frame = frame.unique(subset=_KEY, keep="first", maintain_order=True).sort(
            "timestamp_msc", maintain_order=True
        )
        received = ticks.height
        new = conflicts = 0
        covered = self.coverage(symbol)
        day_cursor = start.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        while day_cursor < end:
            nxt = day_cursor + timedelta(days=1)
            lo, hi = max(start, day_cursor), min(end, nxt)
            part = frame.filter((pl.col("timestamp") >= lo) & (pl.col("timestamp") < hi))
            added, clashed = self._merge_day(
                symbol,
                day=_day(day_cursor),
                part=part,
                lo=lo,
                hi=hi,
                covered=covered,
                stamp=stamp,
                reason=reason,
            )
            new += added
            conflicts += clashed
            day_cursor = nxt
        windows = [[a.isoformat(), b.isoformat()] for a, b in covered] + [
            [start.isoformat(), end.isoformat()]
        ]
        self._save_coverage(symbol, windows)
        return TickAppendResult(
            received, new, frame.height - new - conflicts if frame.height else 0, conflicts, 1
        )

    def _merge_day(
        self,
        symbol: str,
        *,
        day: str,
        part: pl.DataFrame,
        lo: datetime,
        hi: datetime,
        covered: list[tuple[datetime, datetime]],
        stamp: datetime,
        reason: str,
    ) -> tuple[int, int]:
        stored = self.read_day(symbol, day)
        inside = [(max(a, lo), min(b, hi)) for a, b in covered if a < hi and b > lo]
        fresh_rows = part
        conflicts = 0
        for a, b in inside:  # the stored answer is authoritative inside already covered windows
            in_window = (pl.col("timestamp") >= a) & (pl.col("timestamp") < b)
            mine = stored.filter(in_window).select(_KEY)
            theirs = part.filter(in_window).select(_KEY)
            clash = (
                theirs.join(mine, on=_KEY, how="anti").height
                + mine.join(theirs, on=_KEY, how="anti").height
            )
            if clash:
                conflicts += theirs.join(mine, on=_KEY, how="anti").height
                detail: dict[str, Any] = {"day": day, "from": a.isoformat(), "to": b.isoformat()}
                detail |= {"differing_rows": clash, "reason": reason}
                self.log_event(symbol, "TICKS_CHANGED", detail, now=stamp)
            fresh_rows = fresh_rows.filter(~in_window)
        fresh_rows = fresh_rows.join(stored.select(_KEY), on=_KEY, how="anti")
        if fresh_rows.height:
            merged = pl.concat([stored, fresh_rows]).sort("timestamp_msc", maintain_order=True)
            self._write_day(symbol, day, merged)
        return fresh_rows.height, conflicts

    def log_event(
        self, symbol: str, kind: str, detail: dict[str, Any], *, now: datetime | None = None
    ) -> None:
        row = {"at": (now or datetime.now(UTC)).isoformat(), "kind": kind, **detail}
        append_event(self._dir(symbol) / "events.jsonl", row)

    def events(self, symbol: str) -> list[dict[str, Any]]:
        return read_events(self._dir(symbol) / "events.jsonl")

    # -- reading -------------------------------------------------------------------------------

    def read_day(self, symbol: str, day: str) -> pl.DataFrame:
        path = self._file(symbol, day)
        if not path.exists():
            return empty_ticks()
        try:
            return conform_ticks(pl.read_parquet(path))
        except (OSError, pl.exceptions.PolarsError) as exc:
            msg = f"unreadable tick file {path.name}: {exc}"
            raise TickLedgerError(msg) from exc

    def _write_day(self, symbol: str, day: str, frame: pl.DataFrame) -> None:
        target = self._file(symbol, day)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".parquet.tmp")
        frame.write_parquet(tmp, compression="zstd")
        tmp.replace(target)

    def days(self, symbol: str) -> list[str]:
        directory = self._dir(symbol)
        return sorted(p.stem for p in directory.glob("*/*.parquet")) if directory.is_dir() else []

    def load(
        self, symbol: str, start: datetime, end: datetime, *, limit: int = 1_000_000
    ) -> pl.DataFrame:
        """Ticks in ``[start, end)`` (at most ``limit`` rows: bounded for callers)."""
        wanted = [d for d in self.days(symbol) if _day(start) <= d <= _day(end)]
        parts = [self.read_day(symbol, d) for d in wanted]
        if not parts:
            return empty_ticks()
        frame = pl.concat(parts).filter(
            (pl.col("timestamp") >= start) & (pl.col("timestamp") < end)
        )
        return frame.sort("timestamp_msc", maintain_order=True).head(limit)

    def latest(self, symbol: str) -> datetime | None:
        for day in reversed(self.days(symbol)):
            frame = self.read_day(symbol, day)
            if frame.height:
                value = frame["timestamp"].max()
                return value if isinstance(value, datetime) else None
        return None

    def earliest(self, symbol: str) -> datetime | None:
        for day in self.days(symbol):
            frame = self.read_day(symbol, day)
            if frame.height:
                value = frame["timestamp"].min()
                return value if isinstance(value, datetime) else None
        return None

    # -- integrity -----------------------------------------------------------------------------

    def manifest(self, symbol: str) -> dict[str, Any]:
        """Per day: rows and SHA-256; plus totals and the coverage windows."""
        files: dict[str, Any] = {}
        total = 0
        for day in self.days(symbol):
            path = self._file(symbol, day)
            rows = self.read_day(symbol, day).height
            total += rows
            files[day] = {"rows": rows, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        digest = hashlib.sha256("|".join(v["sha256"] for v in files.values()).encode()).hexdigest()[
            :16
        ]
        return {
            "symbol": symbol, "rows": total, "days": len(files), "dataset_id": digest,
            "first": self.earliest(symbol), "last": self.latest(symbol), "files": files,
            "coverage": [(a.isoformat(), b.isoformat()) for a, b in self.coverage(symbol)],
        }  # fmt: skip

    # -- retention (explicit, never automatic) -------------------------------------------------

    def archive_before(self, symbol: str, cutoff_day: str, archive_root: Path | None) -> list[str]:
        """Move whole day files older than ``cutoff_day`` to ``archive_root`` (or delete if None).

        Hash-checked copy first, original removed only after verification. Coverage is kept so the
        gap is visible. Callers must pass the cutoff explicitly; nothing calls this on a timer.
        """
        moved: list[str] = []
        for day in self.days(symbol):
            if day >= cutoff_day:
                continue
            source = self._file(symbol, day)
            if archive_root is not None:
                target = archive_root / symbol / "ticks" / day[:4] / source.name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                if (
                    hashlib.sha256(source.read_bytes()).digest()
                    != hashlib.sha256(target.read_bytes()).digest()
                ):
                    msg = f"archive copy of {day} does not match; original kept"
                    raise TickLedgerError(msg)
            source.unlink()
            moved.append(day)
        if moved:
            self.log_event(
                symbol, "TICKS_ARCHIVED", {"days": moved, "archived": archive_root is not None}
            )
        return moved
