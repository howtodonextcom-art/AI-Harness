"""Compact the many small per-refresh Parquet files of a symbol/timeframe into monthly files.

Raw data stays immutable and content-addressed:

* the merged view the catalog serves (newest fetch wins on equal timestamps) is computed first;
* each month of it is written as a NEW content-hash dataset (``source="compact"``) through the
  normal ``RawStore.write`` (read-only file plus sidecar);
* only when the compacted set is proven identical to the original merge (same frame, same
  content hash) are the old files MOVED, with their sidecars, to
  ``<root>/_archive/<symbol>/<timeframe>/<compaction-id>/`` together with a manifest. Nothing is
  ever deleted. ``_archive`` is ignored by the catalog (its name is not a valid symbol).

The catalog ``dataset_id`` changes (it hashes the contributing file hashes) while the bar content
is byte-for-byte the same; the manifest records both so an old dataset can be re-verified from the
archive. Run it while the bot is idle (weekend): moving files under a reader that already listed
them would make that single load fail (it fails closed and the next cycle succeeds).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog, clear_catalog_cache
from xau_edge.market_data.store import RawDataset, RawStore, dataframe_sha256
from xau_edge.observability import log_event

_LOG = logging.getLogger(__name__)
ARCHIVE_DIR = "_archive"
COMPACT_SOURCE = "compact"


class CompactionError(RuntimeError):
    """Raised when compaction cannot prove the compacted set equals the original merge."""


@dataclass(frozen=True)
class CompactionResult:
    """What a compaction did (or would do, for a dry run)."""

    symbol: str
    timeframe: Timeframe
    files_before: int
    files_after: int
    rows: int
    archived: int
    archive_dir: Path | None
    dry_run: bool
    skipped_reason: str | None = None


def _move(path: Path, target_dir: Path) -> None:
    for source in (path, path.with_name(path.name + ".meta.json")):
        if source.exists():
            source.rename(target_dir / source.name)


def compact_timeframe(
    root: Path | str,
    symbol: str,
    timeframe: Timeframe,
    *,
    min_files: int = 2,
    dry_run: bool = False,
    now: datetime | None = None,
) -> CompactionResult:
    """Merge every dataset of ``symbol``/``timeframe`` into monthly files (see module docs)."""
    base = Path(root)
    store = RawStore(base)
    catalog = DatasetCatalog(base)
    before = catalog.load(symbol, timeframe, use_cache=False)  # full integrity verification
    sources = list(before.datasets)
    months = before.frame.with_columns(pl.col("timestamp").dt.strftime("%Y%m").alias("_month"))
    parts = months.partition_by("_month", maintain_order=True, as_dict=False)
    if len(sources) < min_files:
        reason = f"only {len(sources)} file(s), below min_files={min_files}"
        return CompactionResult(
            symbol,
            timeframe,
            len(sources),
            len(sources),
            before.frame.height,
            0,
            None,
            dry_run,
            reason,
        )
    if dry_run:
        return CompactionResult(
            symbol, timeframe, len(sources), len(parts), before.frame.height, 0, None, True
        )

    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    newest_fetch = max(d.fetched_at for d in sources)
    written: list[RawDataset] = [
        store.write(
            part.drop("_month"),
            symbol=symbol,
            timeframe=timeframe,
            source=COMPACT_SOURCE,
            fetched_at=newest_fetch,
        )
        for part in parts
    ]

    # Prove the compacted set reproduces the original merge before touching any old file.
    frames = [store.read_verified(d) for d in written]
    rebuilt = pl.concat(frames).sort("timestamp")
    if rebuilt.height != before.frame.height or dataframe_sha256(rebuilt) != dataframe_sha256(
        before.frame
    ):
        msg = f"compacted {symbol} {timeframe.value} differs from the original merge; nothing moved"
        raise CompactionError(msg)

    new_paths = {d.path for d in written}
    to_archive = [d for d in sources if d.path not in new_paths]
    if not to_archive:
        return CompactionResult(
            symbol,
            timeframe,
            len(sources),
            len(sources),
            before.frame.height,
            0,
            None,
            False,
            "already compact",
        )
    compaction_id = f"{stamp:%Y%m%dT%H%M%SZ}__{before.dataset_id}"
    archive = base / ARCHIVE_DIR / symbol / timeframe.value / compaction_id
    archive.mkdir(parents=True, exist_ok=False)
    manifest = {
        "compaction_id": compaction_id,
        "created_at": stamp.isoformat(),
        "symbol": symbol,
        "timeframe": timeframe.value,
        "merged_frame_sha256": dataframe_sha256(before.frame),
        "old_dataset_id": before.dataset_id,
        "rows": before.frame.height,
        "archived": [{"file": d.path.name, "sha256": d.sha256, "rows": d.rows} for d in to_archive],
        "compacted": [{"file": d.path.name, "sha256": d.sha256, "rows": d.rows} for d in written],
    }
    (archive / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for dataset in to_archive:
        _move(dataset.path, archive)
    clear_catalog_cache()

    after = catalog.load(symbol, timeframe, use_cache=False)
    if dataframe_sha256(after.frame) != dataframe_sha256(before.frame):
        msg = f"{symbol} {timeframe.value} changed after archiving; restore from {archive}"
        raise CompactionError(msg)
    log_event(
        _LOG,
        "compact.done",
        symbol=symbol,
        timeframe=timeframe.value,
        files_before=len(sources),
        files_after=len(after.datasets),
        archived=len(to_archive),
        old_dataset_id=before.dataset_id,
        new_dataset_id=after.dataset_id,
    )
    return CompactionResult(
        symbol,
        timeframe,
        len(sources),
        len(after.datasets),
        before.frame.height,
        len(to_archive),
        archive,
        False,
    )


def compact_all(
    root: Path | str, *, min_files: int = 2, dry_run: bool = False
) -> list[CompactionResult]:
    """Compact every (symbol, timeframe) the catalog can see."""
    return [
        compact_timeframe(root, symbol, tf, min_files=min_files, dry_run=dry_run)
        for symbol, tf in DatasetCatalog(root).available()
    ]
