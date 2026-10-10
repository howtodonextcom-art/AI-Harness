"""Pluggable calendar sources. No provider is bundled for any specific website.

A provider returns the text of a calendar document in the format of ``news/pit.py``. To use a real
source, either export it to that CSV and point ``LocalFileProvider`` at the file, or implement
``CalendarProvider`` (one method) for your data vendor. ``HttpsCsvProvider`` fetches such a CSV from
a URL you choose and trust; nothing is fetched unless you configure it.
"""

from __future__ import annotations

import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

MAX_BYTES = 5_000_000
USER_AGENT = "xau-edge-news/1.0 (personal decision support; a few fetches per day)"


class CalendarProviderError(RuntimeError):
    """Raised when a source cannot be read."""


class CalendarProvider(Protocol):
    """A source of calendar documents."""

    def fetch_text(self) -> str:
        """Return the calendar document text, or raise ``CalendarProviderError``."""
        ...


class LocalFileProvider:
    """Reads a calendar CSV from a local path (the manual / exported-by-hand workflow)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def fetch_text(self) -> str:
        """Read the file."""
        try:
            if self.path.stat().st_size > MAX_BYTES:
                msg = f"{self.path} is larger than {MAX_BYTES} bytes"
                raise CalendarProviderError(msg)
            return self.path.read_text(encoding="utf-8")
        except OSError as exc:
            msg = f"cannot read {self.path}: {exc}"
            raise CalendarProviderError(msg) from exc


def _urlopen_read(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "text/csv", "User-Agent": USER_AGENT})  # noqa: S310 - https only
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        data: bytes = response.read(MAX_BYTES + 1)
    return data


class HttpsCsvProvider:
    """Fetches a calendar CSV over HTTPS from a URL the operator configured."""

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 20.0,
        opener: Callable[[str, float], bytes] = _urlopen_read,
    ) -> None:
        if not url.startswith("https://"):
            msg = "only https:// sources are accepted"
            raise CalendarProviderError(msg)
        self.url = url
        self._timeout = timeout
        self._opener = opener

    def fetch_text(self) -> str:
        """Download and decode; the URL is not echoed in errors (it may carry a key)."""
        try:
            data = self._opener(self.url, self._timeout)
        except Exception as exc:
            msg = f"download failed ({type(exc).__name__})"
            raise CalendarProviderError(msg) from None
        if len(data) > MAX_BYTES:
            msg = f"download larger than {MAX_BYTES} bytes"
            raise CalendarProviderError(msg)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            msg = "download is not UTF-8 text"
            raise CalendarProviderError(msg) from None


def provider_from_source(source: str) -> CalendarProvider:
    """``forexfactory`` names the weekly feed, ``https://...`` an HttpsCsvProvider, else a path."""
    if source.strip().lower() in ("forexfactory", "ff"):
        from xau_edge.news.forexfactory import ForexFactoryProvider  # noqa: PLC0415 - no cycle

        return ForexFactoryProvider()
    if source.lower().startswith(("http://", "https://")):
        return HttpsCsvProvider(source)
    return LocalFileProvider(source)
