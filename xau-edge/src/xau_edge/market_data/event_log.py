"""Append-only JSON-lines event log with non-destructive size-based segmentation.

When the active file passes ``max_bytes`` it is renamed to ``<name>-<stamp>.jsonl`` (never deleted
or rewritten), and a new active file starts. Readers see every segment in order, so audit history
stays complete while single files stay small. Torn lines are skipped, not trusted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_MAX_BYTES = 5_000_000


def append_event(path: Path, row: dict[str, Any], *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size >= max_bytes:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        path.replace(path.with_name(f"{path.stem}-{stamp}{path.suffix}"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def read_events(path: Path) -> list[dict[str, Any]]:
    segments = (
        sorted(path.parent.glob(f"{path.stem}-*{path.suffix}")) if path.parent.is_dir() else []
    )
    out: list[dict[str, Any]] = []
    for file in [*segments, path]:
        if not file.exists():
            continue
        for line in file.read_text(encoding="utf-8").splitlines():
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                out.append(value)
    return out
