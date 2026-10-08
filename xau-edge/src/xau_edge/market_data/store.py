"""Immutable, content-addressed raw bar storage (Parquet plus a small JSON record)."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_META_SUFFIX = ".meta.json"


class RawDataImmutableError(RuntimeError):
    """Raised when a write would replace existing raw data with different content."""


@dataclass(frozen=True)
class RawDataset:
    """Reference to one stored raw dataset."""

    path: Path
    sha256: str
    rows: int
    start: datetime
    end: datetime
    symbol: str
    timeframe: Timeframe
    source: str
    fetched_at: datetime


def dataframe_sha256(df: pl.DataFrame) -> str:
    """Stable content hash of a frame (schema and values, row order significant)."""
    digest = hashlib.sha256()
    digest.update(str(df.schema).encode("utf-8"))
    digest.update(df.write_csv().encode("utf-8"))
    return digest.hexdigest()


def _check_name(label: str, value: str) -> None:
    if not _SAFE_NAME.match(value) or ".." in value:
        msg = f"unsafe {label} name {value!r}"
        raise ValueError(msg)


def _meta_path(path: Path) -> Path:
    return path.with_name(path.name + _META_SUFFIX)


def _write_meta(dataset: RawDataset) -> None:
    record = {
        "sha256": dataset.sha256,
        "rows": dataset.rows,
        "start": dataset.start.isoformat(),
        "end": dataset.end.isoformat(),
        "symbol": dataset.symbol,
        "timeframe": dataset.timeframe.value,
        "source": dataset.source,
        "fetched_at": dataset.fetched_at.isoformat(),
    }
    meta = _meta_path(dataset.path)
    meta.write_text(json.dumps(record, indent=2), encoding="utf-8")
    meta.chmod(stat.S_IREAD)


def _read_meta(parquet: Path) -> RawDataset | None:
    meta = _meta_path(parquet)
    if not meta.exists():
        return None
    r = json.loads(meta.read_text(encoding="utf-8"))
    return RawDataset(
        path=parquet,
        sha256=r["sha256"],
        rows=r["rows"],
        start=datetime.fromisoformat(r["start"]),
        end=datetime.fromisoformat(r["end"]),
        symbol=r["symbol"],
        timeframe=Timeframe(r["timeframe"]),
        source=r["source"],
        fetched_at=datetime.fromisoformat(r["fetched_at"]),
    )


class RawStore:
    """Write-once store for raw market data.

    Files are named by content hash. Re-writing identical data is a no-op that keeps the original
    record (including its fetch time); a different payload at an existing path raises. Files are
    marked read-only. Each Parquet file has a ``.meta.json`` sidecar with provenance.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write(
        self,
        df: pl.DataFrame,
        *,
        symbol: str,
        timeframe: Timeframe,
        source: str,
        fetched_at: datetime | None = None,
    ) -> RawDataset:
        """Store ``df`` and return its reference."""
        if df.height == 0:
            msg = "refusing to store an empty frame"
            raise ValueError(msg)
        _check_name("source", source)
        _check_name("symbol", symbol)

        digest = dataframe_sha256(df)
        start = df["timestamp"].min()
        end = df["timestamp"].max()
        assert isinstance(start, datetime)  # noqa: S101 - frame is non-empty with datetimes
        assert isinstance(end, datetime)  # noqa: S101
        name = f"{source}__{start:%Y%m%dT%H%M%S}__{end:%Y%m%dT%H%M%S}__{digest[:12]}.parquet"
        directory = self.root / symbol / timeframe.value
        path = directory / name
        stamp = (fetched_at or datetime.now(UTC)).astimezone(UTC)
        dataset = RawDataset(path, digest, df.height, start, end, symbol, timeframe, source, stamp)

        if path.exists():
            if not self.verify(dataset):
                msg = f"{path} exists with different content; raw data is immutable"
                raise RawDataImmutableError(msg)
            existing = _read_meta(path)
            if existing is not None:
                return existing
            legacy = RawDataset(
                path,
                digest,
                df.height,
                start,
                end,
                symbol,
                timeframe,
                source,
                datetime.fromtimestamp(path.stat().st_mtime, UTC),
            )
            _write_meta(legacy)
            return legacy

        directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        df.write_parquet(tmp)
        tmp.rename(path)
        path.chmod(stat.S_IREAD)
        _write_meta(dataset)
        return dataset

    def datasets(self, symbol: str, timeframe: Timeframe) -> list[RawDataset]:
        """Stored datasets for a symbol/timeframe, oldest fetch first."""
        directory = self.root / symbol / timeframe.value
        if not directory.is_dir():
            return []
        found = [d for p in directory.glob("*.parquet") if (d := _read_meta(p)) is not None]
        return sorted(found, key=lambda d: (d.fetched_at, d.path.name))

    def verify(self, dataset: RawDataset) -> bool:
        """True if the stored file still matches the recorded content hash."""
        try:
            return dataframe_sha256(pl.read_parquet(dataset.path)) == dataset.sha256
        except Exception:
            return False
