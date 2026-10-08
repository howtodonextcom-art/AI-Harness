"""Lightweight experiment registry (brief section 39).

Each run is one JSON file named by the hash of its content. A record holds what is needed to
reproduce and to count variants: dataset and feature-set ids, parameters, random seeds, code
version (git commit and whether the tree was dirty), evaluation period and result metrics. Files are
write-once: re-recording identical content is a no-op, a file whose content no longer matches its
id is reported as modified. ``variant_count`` feeds the multiple-testing adjustment in
``docs/evals/edge-criteria.md``.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

_ID = re.compile(r"^[0-9a-f]{16}$")


class ExperimentRecord(BaseModel):
    """One recorded experiment run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    created_at: str
    family: str
    name: str
    dataset_ids: dict[str, str]
    feature_ids: dict[str, str]
    params: dict[str, Any]
    seeds: dict[str, int]
    period: str
    metrics: dict[str, Any]
    code_version: str
    code_dirty: bool
    notes: str = ""


def current_code_version(cwd: Path | None = None) -> tuple[str, bool]:
    """Return ``(git commit hash or "unknown", working tree has uncommitted changes)``."""
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown", False
    return head, bool(status)


def _content_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class ExperimentRegistry:
    """Directory of write-once experiment records."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def record(
        self,
        *,
        family: str,
        name: str,
        dataset_ids: dict[str, str],
        feature_ids: dict[str, str],
        params: dict[str, Any],
        seeds: dict[str, int],
        period: str,
        metrics: dict[str, Any],
        code_version: str | None = None,
        code_dirty: bool | None = None,
        notes: str = "",
    ) -> ExperimentRecord:
        """Store a run (idempotent for identical content) and return it."""
        if code_version is None:
            code_version, detected_dirty = current_code_version()
            code_dirty = detected_dirty if code_dirty is None else code_dirty
        content: dict[str, Any] = {
            "family": family,
            "name": name,
            "dataset_ids": dataset_ids,
            "feature_ids": feature_ids,
            "params": params,
            "seeds": seeds,
            "period": period,
            "metrics": metrics,
            "code_version": code_version,
            "code_dirty": bool(code_dirty),
            "notes": notes,
        }
        json.dumps(content, allow_nan=False)  # rejects values that cannot be stored faithfully
        rid = _content_id(content)
        path = self.root / f"{rid}.json"
        if path.exists():
            return self.get(rid)
        record = ExperimentRecord(id=rid, created_at=datetime.now(UTC).isoformat(), **content)
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        return record

    def get(self, record_id: str) -> ExperimentRecord:
        """Load a record, verifying that its content still matches its id."""
        if not _ID.fullmatch(record_id):
            msg = f"invalid experiment id {record_id!r}"
            raise ValueError(msg)
        data = json.loads((self.root / f"{record_id}.json").read_text(encoding="utf-8"))
        record = ExperimentRecord(**data)
        content = record.model_dump(exclude={"id", "created_at"})
        if _content_id(content) != record_id:
            msg = f"record {record_id} was modified after it was written"
            raise ValueError(msg)
        return record

    def list(self, family: str | None = None) -> list[ExperimentRecord]:
        """All records (optionally one family), oldest first."""
        if not self.root.exists():
            return []
        records = [self.get(p.stem) for p in self.root.glob("*.json") if _ID.fullmatch(p.stem)]
        if family is not None:
            records = [r for r in records if r.family == family]
        return sorted(records, key=lambda r: (r.created_at, r.id))

    def variant_count(self, family: str) -> int:
        """Number of distinct parameter sets tried in ``family`` (periods do not add variants)."""
        seen = {
            json.dumps(r.params, sort_keys=True, separators=(",", ":")) for r in self.list(family)
        }
        return len(seen)
