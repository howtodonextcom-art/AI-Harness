"""Validate a video source reference without touching the network."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from xau_edge.video_intel.status import ErrorCode, SourceCheck, SourceStatus

_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_FACEBOOK = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch", "web.facebook.com"}
_MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
LOCAL_SUFFIXES = _MEDIA_SUFFIXES


class Platform(StrEnum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    DIRECT = "direct_media"
    LOCAL = "local_file"


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    platform: Platform
    location: str  # URL or path exactly as supplied (provenance)


def classify_source(value: str) -> tuple[SourceRef | None, SourceCheck]:
    """Return a ``SourceRef`` for a supported source, else ``None`` and the reason."""
    text = value.strip()
    if not text:
        return None, SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE, code=ErrorCode.BAD_URL, message="Empty source."
        )
    if "://" not in text:
        path = Path(text)
        if path.suffix.lower() not in LOCAL_SUFFIXES:
            return None, SourceCheck(
                status=SourceStatus.SOURCE_UNAVAILABLE,
                code=ErrorCode.UNSUPPORTED_HOST,
                message=f"Not a supported local video file ({path.suffix or 'no extension'}).",
            )
        return SourceRef(platform=Platform.LOCAL, location=text), SourceCheck(
            status=SourceStatus.ACCESSIBLE, code=ErrorCode.OK, message="Local file reference."
        )
    parsed = urlparse(text)
    if parsed.scheme != "https":
        return None, SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE,
            code=ErrorCode.UNSUPPORTED_SCHEME,
            message=f"Only https URLs are accepted, got '{parsed.scheme}'.",
        )
    host = (parsed.hostname or "").lower()
    if host in _YOUTUBE:
        platform = Platform.YOUTUBE
    elif host in _FACEBOOK:
        platform = Platform.FACEBOOK
    elif Path(parsed.path).suffix.lower() in _MEDIA_SUFFIXES and host:
        platform = Platform.DIRECT
    else:
        return None, SourceCheck(
            status=SourceStatus.SOURCE_UNAVAILABLE,
            code=ErrorCode.UNSUPPORTED_HOST,
            message=f"Host '{host}' is not YouTube, Facebook or a direct media URL.",
        )
    return SourceRef(platform=platform, location=text), SourceCheck(
        status=SourceStatus.ACCESSIBLE, code=ErrorCode.OK, message="Supported source."
    )
