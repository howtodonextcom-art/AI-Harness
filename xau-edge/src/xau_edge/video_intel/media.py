"""Local media handling: ffmpeg discovery, probing, adaptive frame sampling, audio extraction."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

Runner = Callable[[Sequence[str]], tuple[int, str, str]]


def _run(argv: Sequence[str]) -> tuple[int, str, str]:
    try:
        done = subprocess.run(  # noqa: S603
            list(argv), capture_output=True, text=True, timeout=600, check=False, encoding="utf-8",
            errors="replace",
        )  # fmt: skip
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return done.returncode, done.stdout, done.stderr


def find_ffmpeg() -> str | None:
    """``XAU_EDGE_FFMPEG``, then PATH, then the bundled ``imageio-ffmpeg`` binary if installed."""
    env = os.environ.get("XAU_EDGE_FFMPEG")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    if importlib.util.find_spec("imageio_ffmpeg") is not None:
        import imageio_ffmpeg  # noqa: PLC0415

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    return None


class MediaInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    duration_s: float
    width: int
    height: int
    video_codec: str
    has_audio: bool


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO = re.compile(r"Stream #\S+.*?Video:\s*(\w+).*?,\s*(\d{2,5})x(\d{2,5})")


def parse_probe(stderr: str) -> MediaInfo | None:
    dur = _DURATION.search(stderr)
    vid = _VIDEO.search(stderr)
    if not dur or not vid:
        return None
    h, m, s = dur.groups()
    return MediaInfo(
        duration_s=int(h) * 3600 + int(m) * 60 + float(s),
        width=int(vid.group(2)),
        height=int(vid.group(3)),
        video_codec=vid.group(1),
        has_audio="Audio:" in stderr,
    )


def probe(
    path: Path, ffmpeg: str | None, runner: Runner = _run
) -> tuple[SourceCheck, MediaInfo | None]:
    if not path.is_file() or path.stat().st_size == 0:
        return SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE, code=ErrorCode.FILE_NOT_FOUND,
            message=f"No media file at {path.name}.",
        ), None  # fmt: skip
    if ffmpeg is None:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.FFMPEG_MISSING,
            message="ffmpeg is not available (set XAU_EDGE_FFMPEG or install it).",
        ), None  # fmt: skip
    _code, _out, err = runner([ffmpeg, "-hide_banner", "-i", str(path)])  # exit 1 is normal here
    info = parse_probe(err)
    if info is None:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.PROBE_FAILED,
            message="ffmpeg could not read video streams from the file.", detail=err[-300:],
        ), None  # fmt: skip
    return SourceCheck(
        status=SourceStatus.MEDIA_READY, code=ErrorCode.OK, message="Media probed."
    ), info


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class KeyFrame(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_ms: int
    path: str
    change_score: float
    reason: str  # "first", "scene_change" or "last"


def thumbnail_vector(path: Path) -> np.ndarray:  # type: ignore[type-arg,unused-ignore]
    from PIL import Image  # noqa: PLC0415 - optional dependency (extra "video")

    with Image.open(path) as image:
        return np.asarray(image.convert("L").resize((32, 32)), dtype=np.float64)


def select_keyframes(
    vectors: Sequence[np.ndarray],  # type: ignore[type-arg,unused-ignore]
    *,
    threshold: float,
    always_last: bool = True,
) -> list[tuple[int, str, float]]:
    """Pick ``(index, reason, change)``: the first frame, every frame that differs from the last
    *kept* frame by at least ``threshold`` (mean absolute pixel change), and the last frame.

    Comparing with the last kept frame, not the previous one, matters for charts that are drawn
    line by line: each step is tiny, but the accumulated change still crosses the threshold.
    """
    if not vectors:
        return []
    picks: dict[int, tuple[str, float]] = {0: ("first", 0.0)}
    reference = vectors[0]
    for i in range(1, len(vectors)):
        change = float(np.abs(vectors[i] - reference).mean())
        if change >= threshold:
            picks[i] = ("scene_change", change)
            reference = vectors[i]
    last = len(vectors) - 1
    if always_last and last > 0 and last not in picks:
        picks[last] = ("last", float(np.abs(vectors[last] - reference).mean()))
    return [(i, reason, change) for i, (reason, change) in sorted(picks.items())]


def extract_keyframes(
    video: Path,
    out_dir: Path,
    ffmpeg: str,
    *,
    sample_fps: float = 2.0,
    threshold: float = 1.0,
    width: int = 720,
    runner: Runner = _run,
) -> tuple[SourceCheck, list[KeyFrame]]:
    """Sample at ``sample_fps``, then keep only frames that changed (duplicate elimination)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("cand_*.png"):
        old.unlink()
    cmd = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-i",
        str(video),
        "-vf",
        f"fps={sample_fps},scale={width}:-1",
    ]
    code, _out, err = runner([*cmd, str(out_dir / "cand_%04d.png")])
    candidates = sorted(out_dir.glob("cand_*.png"))
    if code != 0 or not candidates:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.PROBE_FAILED,
            message="Frame extraction produced no frames.", detail=err[-300:],
        ), []  # fmt: skip
    vectors = [thumbnail_vector(p) for p in candidates]
    keep = {
        i: (reason, change) for i, reason, change in select_keyframes(vectors, threshold=threshold)
    }
    kept: list[KeyFrame] = []
    for i, path in enumerate(candidates):
        if i in keep:
            kept.append(
                KeyFrame(
                    timestamp_ms=round(i * 1000 / sample_fps),
                    path=path.name,
                    change_score=round(keep[i][1], 3),
                    reason=keep[i][0],
                )
            )
        else:
            path.unlink()
    return SourceCheck(
        status=SourceStatus.MEDIA_READY, code=ErrorCode.OK,
        message=f"{len(kept)} keyframes kept of {len(candidates)} sampled.",
    ), kept  # fmt: skip


def extract_audio(video: Path, wav: Path, ffmpeg: str, runner: Runner = _run) -> SourceCheck:
    code, _out, err = runner(
        [ffmpeg, "-v", "error", "-y", "-i", str(video), "-ac", "1", "-ar", "16000", str(wav)]
    )
    if code != 0 or not wav.is_file():
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.PROBE_FAILED,
            message="Audio extraction failed (the file may have no audio stream).",
            detail=err[-300:],
        )  # fmt: skip
    return SourceCheck(
        status=SourceStatus.MEDIA_READY, code=ErrorCode.OK, message="Audio extracted."
    )
