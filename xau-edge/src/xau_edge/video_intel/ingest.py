"""Authorized media ingestion through yt-dlp.

Rules enforced here, not left to the caller:

* no cookies, no browser-profile access, no credentials are ever passed to the extractor;
* no CAPTCHA/DRM/privacy bypass: a login wall or restriction is reported, not worked around;
* every failure maps to a ``SourceStatus`` + ``ErrorCode``; a download is never reported as success
  unless a non-empty media file exists afterwards.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from xau_edge.video_intel.source import SourceRef
from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

Runner = Callable[[Sequence[str]], tuple[int, str, str]]
"""Run an argv; return (exit code, stdout, stderr)."""

_FORBIDDEN_FLAGS = ("--cookies", "--cookies-from-browser", "--username", "--password", "--netrc")
_MAX_FILESIZE = "200M"


def default_runner(argv: Sequence[str]) -> tuple[int, str, str]:
    try:
        done = subprocess.run(  # noqa: S603
            list(argv), capture_output=True, text=True, timeout=300, check=False, encoding="utf-8"
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return done.returncode, done.stdout, done.stderr


def extractor_argv() -> list[str] | None:
    """The yt-dlp invocation available here, or ``None``."""
    if importlib.util.find_spec("yt_dlp") is not None:
        return [sys.executable, "-m", "yt_dlp"]
    return None


def assert_no_credentials(argv: Sequence[str]) -> None:
    for arg in argv:
        if arg.startswith(_FORBIDDEN_FLAGS):
            raise ValueError(f"credential-bearing extractor flag refused: {arg.split('=')[0]}")


_LOGIN = re.compile(r"log ?in|sign in|authentication|cookies|private|members?-only", re.I)
_RESTRICT = re.compile(r"geo|not available in your country|age.?restrict|drm|copyright", re.I)
_MISSING = re.compile(r"404|not found|removed|no longer available|does not exist|unavailable", re.I)
_NET = re.compile(r"timed out|timeout|name or service|getaddrinfo|connection|network", re.I)


def classify_failure(stderr: str, *, returncode: int = 1) -> SourceCheck:
    text = stderr.strip()
    tail = text[-400:] if text else None
    if returncode == 127:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.EXTRACTOR_MISSING,
            message="yt-dlp is not installed.", detail=tail,
        )  # fmt: skip
    if _LOGIN.search(text):
        return SourceCheck(
            status=SourceStatus.AUTH_REQUIRED, code=ErrorCode.LOGIN_REQUIRED,
            message="The platform requires a login. Supply a local file or a transcript instead.",
            detail=tail,
        )  # fmt: skip
    if _RESTRICT.search(text):
        return SourceCheck(
            status=SourceStatus.RESTRICTED, code=ErrorCode.RESTRICTED_CONTENT,
            message="The content is restricted (region, age, DRM or rights). Not bypassed.",
            detail=tail,
        )  # fmt: skip
    if _NET.search(text):
        return SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE, code=ErrorCode.NETWORK,
            message="Network failure while reaching the source.", detail=tail,
        )  # fmt: skip
    if _MISSING.search(text):
        return SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE, code=ErrorCode.NOT_FOUND,
            message="The video was removed, is private or does not exist.", detail=tail,
        )  # fmt: skip
    return SourceCheck(
        status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.EXTRACTOR_ERROR,
        message="The extractor failed for an unrecognised reason.", detail=tail,
    )  # fmt: skip


def inspect_url(
    ref: SourceRef, runner: Runner = default_runner, argv: list[str] | None = None
) -> tuple[SourceCheck, dict[str, Any] | None]:
    """Fetch metadata only (no media). ``ACCESSIBLE`` means metadata was readable."""
    base = argv if argv is not None else extractor_argv()
    if base is None:
        return classify_failure("", returncode=127), None
    cmd = [
        *base,
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        "--no-playlist",
        ref.location,
    ]
    assert_no_credentials(cmd)
    code, out, err = runner(cmd)
    if code != 0:
        return classify_failure(err, returncode=code), None
    try:
        meta = json.loads(out)
    except json.JSONDecodeError:
        return classify_failure("unparsable extractor output"), None
    return SourceCheck(
        status=SourceStatus.ACCESSIBLE,
        code=ErrorCode.OK,
        message="Metadata readable without login.",
    ), {
        "title": meta.get("title"),
        "uploader": meta.get("uploader"),
        "duration": meta.get("duration"),
        "id": meta.get("id"),
        "webpage_url": meta.get("webpage_url"),
        "extractor": meta.get("extractor_key"),
    }  # fmt: skip


def download(
    ref: SourceRef,
    out_dir: Path,
    *,
    ffmpeg: str | None,
    runner: Runner = default_runner,
    argv: list[str] | None = None,
) -> tuple[SourceCheck, Path | None]:
    """Download the media to ``out_dir/video.<ext>``; ``MEDIA_READY`` only if the file exists."""
    base = argv if argv is not None else extractor_argv()
    if base is None:
        return classify_failure("", returncode=127), None
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [*base, "--no-playlist", "--max-filesize", _MAX_FILESIZE, "--socket-timeout", "20"]
    cmd += ["-f", "bv*+ba/b", "--merge-output-format", "mp4"]
    if ffmpeg:
        cmd += ["--ffmpeg-location", ffmpeg]
    cmd += ["-o", str(out_dir / "video.%(ext)s"), ref.location]
    assert_no_credentials(cmd)
    code, _out, err = runner(cmd)
    if code != 0:
        return classify_failure(err, returncode=code), None
    produced = sorted(p for p in out_dir.glob("video.*") if p.is_file() and p.stat().st_size > 0)
    if not produced:
        return SourceCheck(
            status=SourceStatus.EXTRACTION_FAILED, code=ErrorCode.EXTRACTOR_ERROR,
            message="The extractor exited cleanly but produced no media file.", detail=None,
        ), None  # fmt: skip
    return SourceCheck(
        status=SourceStatus.MEDIA_READY,
        code=ErrorCode.OK,
        message=f"Media saved: {produced[0].name}",
    ), produced[0]
