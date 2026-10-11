"""File-backed knowledge store (data/video_knowledge/<id>/knowledge.json); no second database."""

from __future__ import annotations

import hashlib
from pathlib import Path

from xau_edge.video_intel.knowledge import VideoKnowledge

DEFAULT_ROOT = Path("data") / "video_knowledge"


def video_id_for(location: str) -> str:
    return hashlib.sha256(location.strip().encode("utf-8")).hexdigest()[:12]


def save(knowledge: VideoKnowledge, root: Path = DEFAULT_ROOT) -> Path:
    folder = root / knowledge.video.id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "knowledge.json"
    tmp = target.with_suffix(".tmp")
    tmp.write_text(knowledge.model_dump_json(indent=2), encoding="utf-8")
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
