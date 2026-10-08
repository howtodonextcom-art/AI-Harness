"""Immutable, content-addressed raw bar storage (Parquet plus a small JSON record)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\.|$)", re.IGNORECASE)
_META_SUFFIX = ".meta.json"


class RawDataImmutableError(RuntimeError):
    """Raised when a write would replace existing raw data with different content."""


class RawDataIntegrityError(RawDataImmutableError):
    """Raised when stored data no longer matches the hash recorded when it was written."""


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


def is_safe_name(value: str) -> bool:
    """True if ``value`` is acceptable as a symbol/source directory or file component."""
    return not (
        not _SAFE_NAME.fullmatch(value)
        or ".." in value
        or value.endswith(".")
        or _WINDOWS_RESERVED.match(value)
    )


def _check_name(label: str, value: str) -> None:
    if not is_safe_name(value):
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


def _log_write(dataset: RawDataset, *, duplicate: bool) -> None:
    log_event(
        _LOG,
        "raw.write",
        symbol=dataset.symbol,
        timeframe=dataset.timeframe.value,
        source=dataset.source,
        rows=dataset.rows,
        sha256=dataset.sha256,
        start=dataset.start,
        end=dataset.end,
        duplicate=duplicate,
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
            try:
                stored = pl.read_parquet(path)
            except (OSError, pl.exceptions.PolarsError) as exc:
                msg = f"{path} exists but is unreadable ({exc}); raw data is immutable"
                raise RawDataImmutableError(msg) from exc
            if dataframe_sha256(stored) != digest:
                msg = f"{path} exists with different content; raw data is immutable"
                raise RawDataImmutableError(msg)
            existing = _read_meta(path)
            if existing is not None:
                _log_write(existing, duplicate=True)
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
            _log_write(legacy, duplicate=True)
            return legacy

        directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        df.write_parquet(tmp)
        tmp.rename(path)
        path.chmod(stat.S_IREAD)
        _write_meta(dataset)
        _log_write(dataset, duplicate=False)
        return dataset

    def datasets(self, symbol: str, timeframe: Timeframe) -> list[RawDataset]:
        """Stored datasets for a symbol/timeframe, oldest fetch first."""
        _check_name("symbol", symbol)
        directory = self.root / symbol / timeframe.value
        if not directory.is_dir():
            return []
        found = [d for p in directory.glob("*.parquet") if (d := _read_meta(p)) is not None]
        return sorted(found, key=lambda d: (d.fetched_at, d.path.name))

    def read_verified(self, dataset: RawDataset) -> pl.DataFrame:
        """Read a stored file and prove it matches both its hash and its sidecar record.

        Checks, in order: the file name carries the recorded hash prefix, the content re-hashes to
        the recorded hash, and the sidecar's row count, time range, symbol and timeframe agree with
        the file and its location. ``fetched_at`` cannot be verified from the data itself, so a
        sidecar can still be backdated by someone with write access; the store defends against
        accidents and silent corruption, not against an attacker who can rewrite both files.

        Raises :class:`RawDataIntegrityError` on any mismatch or if the file is unreadable.
        """
        path = dataset.path
        if f"__{dataset.sha256[:12]}." not in path.name:
            msg = f"{path} file name does not carry the sidecar hash; the pair was altered"
            raise RawDataIntegrityError(msg)
        try:
            frame = pl.read_parquet(path)
        except (OSError, pl.exceptions.PolarsError) as exc:
            msg = f"{path} is unreadable ({exc})"
            raise RawDataIntegrityError(msg) from exc
        if dataframe_sha256(frame) != dataset.sha256:
            msg = f"{path} content does not match the hash recorded when it was written"
            raise RawDataIntegrityError(msg)
        problems = []
        if frame.height != dataset.rows:
            problems.append(f"rows {dataset.rows} != {frame.height}")
        if (dataset.start, dataset.end) != (frame["timestamp"].min(), frame["timestamp"].max()):
            problems.append("start/end differ from the data")
        if (path.parent.parent.name, path.parent.name) != (dataset.symbol, dataset.timeframe.value):
            problems.append("symbol/timeframe differ from the file location")
        if problems:
            msg = f"{path} sidecar record disagrees with the file: {'; '.join(problems)}"
            raise RawDataIntegrityError(msg)
        return frame

    def verify(self, dataset: RawDataset) -> bool:
        """True if the stored file still matches the recorded content hash."""
        try:
            self.read_verified(dataset)
        except RawDataIntegrityError:
            return False
        return True
