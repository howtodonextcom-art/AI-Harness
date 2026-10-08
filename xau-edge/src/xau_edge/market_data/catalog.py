"""Dataset catalog: merges raw fetches into one deterministic frame and exposes read-only SQL."""

from __future__ import annotations

import contextlib
import hashlib
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl

from xau_edge.domain.bars import coerce_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.store import RawDataset, RawStore, is_safe_name
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)

_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
SQL_MEMORY_LIMIT = "512MB"
SQL_THREADS = 2
SQL_TIMEOUT_SECONDS = 30.0
SQL_MAX_ROWS = 1_000_000


@dataclass(frozen=True)
class CatalogLoad:
    """A merged view of every raw fetch for one symbol and timeframe."""

    frame: pl.DataFrame
    dataset_id: str
    """Hash of the contributing raw-file hashes. Every file is re-hashed on load, so the id
    changes whenever the underlying data changes and loading fails if a file was altered."""
    datasets: tuple[RawDataset, ...]
    duplicates_resolved: int
    """Duplicate rows removed when merging fetches (newest fetch wins on equal timestamps)."""


def view_name(symbol: str, timeframe: Timeframe) -> str:
    """SQL view name for a dataset, e.g. ``bars_xauusd_m15``."""
    return f"bars_{symbol.lower()}_{timeframe.value.lower()}"


class DatasetCatalog:
    """Reads the raw store. Never writes; the merge rule is explicit and reported."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._store = RawStore(self.root)

    def available(self) -> list[tuple[str, Timeframe]]:
        """All (symbol, timeframe) pairs that have at least one stored dataset.

        Directories whose names are not valid symbols (``.cache``, ``_staging``, ...) are ignored
        rather than treated as errors, so a stray folder cannot take the catalog down.
        """
        found: list[tuple[str, Timeframe]] = []
        if not self.root.is_dir():
            return found
        for symbol_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            if not is_safe_name(symbol_dir.name):
                continue
            for tf in Timeframe:
                if self._store.datasets(symbol_dir.name, tf):
                    found.append((symbol_dir.name, tf))
        return found

    def load(self, symbol: str, timeframe: Timeframe) -> CatalogLoad:
        """Merge all fetches; where timestamps overlap, the most recent fetch wins.

        Raises ``RawDataIntegrityError`` if any stored file or its sidecar record no longer
        agrees with the hash and metadata written with it.
        """
        datasets = self._store.datasets(symbol, timeframe)
        if not datasets:
            msg = f"No raw datasets for {symbol} {timeframe.value} under {self.root}"
            raise FileNotFoundError(msg)
        frames = [
            self._store.read_verified(d).with_columns(pl.lit(rank).alias("_rank"))
            for rank, d in enumerate(datasets)
        ]
        combined = pl.concat(frames)
        merged = (
            combined.sort("_rank", maintain_order=True)
            .unique(subset="timestamp", keep="last", maintain_order=True)
            .sort("timestamp")
            .drop("_rank")
        )
        digest = hashlib.sha256("|".join(sorted(d.sha256 for d in datasets)).encode()).hexdigest()
        result = CatalogLoad(
            frame=coerce_bars(merged),
            dataset_id=digest[:16],
            datasets=tuple(datasets),
            duplicates_resolved=combined.height - merged.height,
        )
        log_event(
            _LOG,
            "catalog.load",
            symbol=symbol,
            timeframe=timeframe.value,
            dataset_id=result.dataset_id,
            rows=result.frame.height,
            files=len(datasets),
            duplicates_resolved=result.duplicates_resolved,
        )
        return result

    def sql(
        self,
        query: str,
        *,
        timeout_s: float = SQL_TIMEOUT_SECONDS,
        max_rows: int = SQL_MAX_ROWS,
    ) -> pl.DataFrame:
        """Run a read-only SELECT over views named ``bars_<symbol>_<timeframe>``.

        The engine runs with file-system access disabled, a memory cap, a small thread pool, a
        wall-clock timeout and a cap on the number of result rows, so a careless or hostile query
        can neither read files, hang the process nor materialise an enormous result.
        """
        if not _READ_ONLY_SQL.match(query) or ";" in query.strip().rstrip(";"):
            msg = "only a single read-only SELECT/WITH statement is allowed"
            raise ValueError(msg)
        con = duckdb.connect(
            config={
                "enable_external_access": False,
                "memory_limit": SQL_MEMORY_LIMIT,
                "threads": SQL_THREADS,
            }
        )
        timed_out = threading.Event()

        def interrupt() -> None:
            timed_out.set()
            with contextlib.suppress(duckdb.Error):  # the connection may already be closed
                con.interrupt()

        timer = threading.Timer(timeout_s, interrupt)
        timer.daemon = True
        try:
            for symbol, tf in self.available():
                con.register(view_name(symbol, tf), self.load(symbol, tf).frame.to_arrow())
            timer.start()
            body = query.strip().rstrip(";")
            # The query is user-supplied by design; it is constrained by the SELECT/WITH check
            # above and by the engine sandbox (no file access, limits, timeout).
            # Newlines around it defuse a trailing -- comment.
            capped = f"SELECT * FROM (\n{body}\n) LIMIT {max_rows + 1}"  # noqa: S608
            result = con.execute(capped).pl()
        except duckdb.InterruptException as exc:
            if not timed_out.is_set():
                raise
            msg = f"SQL query exceeded the {timeout_s:g}s time limit"
            raise TimeoutError(msg) from exc
        finally:
            timer.cancel()
            con.close()
        if result.height > max_rows:
            msg = f"SQL result has more than {max_rows} rows; add a LIMIT or aggregate"
            raise ValueError(msg)
        return result
