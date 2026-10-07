"""Immutable, content-addressed raw bar storage (Parquet)."""

from __future__ import annotations

import hashlib
import re
import stat
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


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


class RawStore:
    """Write-once store for raw market data.

    Files are named by content hash. Re-writing identical data is a no-op; a different
    payload at an existing path raises instead of overwriting. Files are marked read-only.
    """

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write(
        self, df: pl.DataFrame, *, symbol: str, timeframe: Timeframe, source: str
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
        dataset = RawDataset(path, digest, df.height, start, end, symbol, timeframe, source)

        if path.exists():
            if self.verify(dataset):
                return dataset
            msg = f"{path} exists with different content; raw data is immutable"
            raise RawDataImmutableError(msg)

        directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        df.write_parquet(tmp)
        tmp.rename(path)
        path.chmod(stat.S_IREAD)
        return dataset

    def verify(self, dataset: RawDataset) -> bool:
        """True if the stored file still matches the recorded content hash."""
        try:
            return dataframe_sha256(pl.read_parquet(dataset.path)) == dataset.sha256
        except Exception:
            return False
