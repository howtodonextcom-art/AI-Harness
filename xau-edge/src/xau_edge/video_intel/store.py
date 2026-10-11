"""File-backed knowledge store (data/video_knowledge/<id>/knowledge.json); no second database.

* writes are atomic and the previous version is kept under ``history/`` (nothing is lost on re-run);
* one record per media file: a second URL that yields the same SHA-256 becomes an alias;
* version-1 records load through the schema's status migration.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from xau_edge.video_intel.knowledge import VideoKnowledge

DEFAULT_ROOT = Path("data") / "video_knowledge"


def video_id_for(location: str) -> str:
    return hashlib.sha256(location.strip().encode("utf-8")).hexdigest()[:12]


def save(knowledge: VideoKnowledge, root: Path = DEFAULT_ROOT) -> Path:
    folder = root / knowledge.video.id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "knowledge.json"
    new_text = knowledge.model_dump_json(indent=2)
    if target.is_file():
        old_text = target.read_text(encoding="utf-8")
        if old_text == new_text:
            return target
        history = folder / "history"
        history.mkdir(exist_ok=True)
        stamp = hashlib.sha256(old_text.encode("utf-8")).hexdigest()[:10]
        (history / f"knowledge.{stamp}.json").write_text(old_text, encoding="utf-8")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    tmp.replace(target)
    return target


def load(video_id: str, root: Path = DEFAULT_ROOT) -> VideoKnowledge:
    return VideoKnowledge.model_validate_json(
        (root / video_id / "knowledge.json").read_text(encoding="utf-8")
    )


def list_ids(root: Path = DEFAULT_ROOT) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir() if (p / "knowledge.json").is_file())


def find_by_hash(sha256: str, root: Path = DEFAULT_ROOT) -> str | None:
    """The id of the record built from the same media bytes, if one exists."""
    for video_id in list_ids(root):
        try:
            raw = json.loads((root / video_id / "knowledge.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if raw.get("video", {}).get("file_sha256") == sha256:
            return video_id
    return None


def history_count(video_id: str, root: Path = DEFAULT_ROOT) -> int:
    folder = root / video_id / "history"
    return len(list(folder.glob("knowledge.*.json"))) if folder.is_dir() else 0
