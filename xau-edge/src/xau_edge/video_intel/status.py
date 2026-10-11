"""Source status model: each access attempt ends in one explicit, machine-readable outcome."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SourceStatus(StrEnum):
    """Where a source stands. ``MEDIA_READY`` is the only state that means pixels were read."""

    ACCESSIBLE = "ACCESSIBLE"  # metadata reachable without credentials; media not yet fetched
    AUTH_REQUIRED = "AUTH_REQUIRED"  # the platform wants a login; we never extract cookies
    RESTRICTED = "RESTRICTED"  # geo, age, DRM or platform restriction; we never bypass it
    EXTRACTION_FAILED = "EXTRACTION_FAILED"  # reachable but the extractor failed
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"  # removed, private, bad URL or no network
    MEDIA_READY = "MEDIA_READY"  # a media file exists locally and was probed
    PARTIAL_INPUT_ONLY = "PARTIAL_INPUT_ONLY"  # only a transcript, audio or screenshots were given


class ErrorCode(StrEnum):
    OK = "OK"
    BAD_URL = "BAD_URL"
    UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
    UNSUPPORTED_HOST = "UNSUPPORTED_HOST"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    RESTRICTED_CONTENT = "RESTRICTED_CONTENT"
    NOT_FOUND = "NOT_FOUND"
    NETWORK = "NETWORK"
    EXTRACTOR_MISSING = "EXTRACTOR_MISSING"
    EXTRACTOR_ERROR = "EXTRACTOR_ERROR"
    FFMPEG_MISSING = "FFMPEG_MISSING"
    PROBE_FAILED = "PROBE_FAILED"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    COOKIES_FORBIDDEN = "COOKIES_FORBIDDEN"
    ASR_UNAVAILABLE = "ASR_UNAVAILABLE"
    TOO_LONG = "TOO_LONG"
    DUPLICATE_SOURCE = "DUPLICATE_SOURCE"


class SourceCheck(BaseModel):
    """Result of one access step: a status, a code for programs and words for a person."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: SourceStatus
    code: ErrorCode
    message: str
    detail: str | None = None
