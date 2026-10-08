"""Dataset catalog: merges raw fetches into one deterministic frame and exposes read-only SQL."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl

from xau_edge.domain.bars import coerce_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.store import RawDataset, RawStore

_READ_ONLY_SQL = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogLoad:
    """A merged view of every raw fetch for one symbol and timeframe."""

    frame: pl.DataFrame
    dataset_id: str
    """Hash of the contributing raw-file hashes: changes whenever the underlying data changes."""
    datasets: tuple[RawDataset, ...]
    duplicates_resolved: int
    """Timestamps present in more than one fetch, resolved by keeping the newest fetch."""


def view_name(symbol: str, timeframe: Timeframe) -> str:
    """SQL view name for a dataset, e.g. ``bars_xauusd_m15``."""
    return f"bars_{symbol.lower()}_{timeframe.value.lower()}"


class DatasetCatalog:
    """Reads the raw store. Never writes; the merge rule is explicit and reported."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self._store = RawStore(self.root)

    def available(self) -> list[tuple[str, Timeframe]]:
        """All (symbol, timeframe) pairs that have at least one stored dataset."""
        found: list[tuple[str, Timeframe]] = []
        if not self.root.is_dir():
            return found
        for symbol_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for tf in Timeframe:
                if self._store.datasets(symbol_dir.name, tf):
                    found.append((symbol_dir.name, tf))
        return found

    def load(self, symbol: str, timeframe: Timeframe) -> CatalogLoad:
        """Merge all fetches; where timestamps overlap, the most recent fetch wins."""
        datasets = self._store.datasets(symbol, timeframe)
        if not datasets:
            msg = f"No raw datasets for {symbol} {timeframe.value} under {self.root}"
            raise FileNotFoundError(msg)
        frames = [
            pl.read_parquet(d.path).with_columns(pl.lit(rank).alias("_rank"))
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
        return CatalogLoad(
            frame=coerce_bars(merged),
            dataset_id=digest[:16],
            datasets=tuple(datasets),
            duplicates_resolved=combined.height - merged.height,
        )

    def sql(self, query: str) -> pl.DataFrame:
        """Run a read-only SELECT over views named ``bars_<symbol>_<timeframe>``."""
        if not _READ_ONLY_SQL.match(query) or ";" in query.strip().rstrip(";"):
            msg = "only a single read-only SELECT/WITH statement is allowed"
            raise ValueError(msg)
        con = duckdb.connect(config={"enable_external_access": False})
        try:
            for symbol, tf in self.available():
                con.register(view_name(symbol, tf), self.load(symbol, tf).frame.to_arrow())
            return con.execute(query).pl()
        finally:
            con.close()
