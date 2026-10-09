"""Where the research console may read from, and nothing else.

Every read goes through ``ResearchRoot``: a relative POSIX path under an allowed prefix, never an
absolute path, never ``..``, never a secret or a mutable database. A missing, oversized, blocked or
unreadable source raises ``SourceUnavailableError``; callers turn that into the status "KHÔNG RÕ"
and never into "OK" (fail closed). Error messages carry no absolute path.
"""

from __future__ import annotations

import fnmatch
import json
import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

ALLOWED_PREFIXES = (
    "docs/research",
    "docs/evals",
    "docs/reports",
    "docs/operations",
    "docs/PROFITABILITY_ROADMAP.md",
    "experiments",
    "data/execution",
    "data/forward",
    "configs",
)
BLOCKED_PATTERNS = (
    ".env*",
    "*.env",
    "*.sqlite",
    "*.sqlite-*",
    "*.db",
    "*.key",
    "*.pem",
    "*.pfx",
    "control_token*",
    "secrets.*",
    "credentials*",
)
MAX_BYTES = 4_000_000
_SAFE = re.compile(r"^[A-Za-z0-9_./ \-+=]+$")


class SourceUnavailableError(RuntimeError):
    """A source is missing, blocked, too large or unreadable (the message has no absolute path)."""


class ResearchRoot:
    """A read-only view of the repository limited to the allowed prefixes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def resolve(self, rel: str) -> Path:
        """The real path of ``rel`` if it is allowed, else ``SourceUnavailableError``."""
        if not rel or "\\" in rel or not _SAFE.match(rel):
            msg = "unsafe path"
            raise SourceUnavailableError(msg)
        pure = PurePosixPath(rel)
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or any(part.startswith("~") for part in pure.parts)
        ):
            msg = "unsafe path"
            raise SourceUnavailableError(msg)
        text = pure.as_posix()
        if not any(text == p or text.startswith(p + "/") for p in ALLOWED_PREFIXES):
            msg = f"path outside the allowed folders: {text}"
            raise SourceUnavailableError(msg)
        if any(
            fnmatch.fnmatch(part.lower(), pat) for part in pure.parts for pat in BLOCKED_PATTERNS
        ):
            msg = f"blocked file type: {text}"
            raise SourceUnavailableError(msg)
        real = (self.root / pure).resolve()
        try:
            real.relative_to(self.root)
        except ValueError as exc:
            msg = "path escapes the repository"
            raise SourceUnavailableError(msg) from exc
        return real

    def exists(self, rel: str) -> bool:
        """True if the allowed path exists (False for blocked or unsafe ones)."""
        try:
            return self.resolve(rel).exists()
        except SourceUnavailableError:
            return False

    def read_text(self, rel: str) -> str:
        """The UTF-8 text of an allowed file, size-capped."""
        real = self.resolve(rel)
        try:
            if not real.is_file():
                msg = f"missing source: {rel}"
                raise SourceUnavailableError(msg)
            if real.stat().st_size > MAX_BYTES:
                msg = f"source too large: {rel}"
                raise SourceUnavailableError(msg)
            return real.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            msg = f"unreadable source: {rel}"
            raise SourceUnavailableError(msg) from exc

    def read_json(self, rel: str) -> Any:
        """Parsed JSON of an allowed file."""
        try:
            return json.loads(self.read_text(rel))
        except json.JSONDecodeError as exc:
            msg = f"invalid JSON: {rel}"
            raise SourceUnavailableError(msg) from exc

    def list(self, rel_dir: str, pattern: str = "*") -> list[str]:
        """Relative paths of the allowed files in a folder, sorted."""
        real = self.resolve(rel_dir)
        if not real.is_dir():
            return []
        out: list[str] = []
        for item in sorted(real.glob(pattern)):
            if item.is_file():
                rel = f"{rel_dir.rstrip('/')}/{item.name}"
                try:
                    self.resolve(rel)
                except SourceUnavailableError:
                    continue
                out.append(rel)
        return out

    def age_hours(self, rel: str, now: datetime | None = None) -> float | None:
        """Hours since the file was last written (None if unknown)."""
        try:
            mtime = datetime.fromtimestamp(self.resolve(rel).stat().st_mtime, UTC)
        except (OSError, SourceUnavailableError):
            return None
        return ((now or datetime.now(UTC)) - mtime).total_seconds() / 3600.0


def unknown(source: str, reason: str) -> dict[str, Any]:
    """The standard answer for a source that cannot be read: never an implicit OK."""
    return {"status": "unknown", "source": source, "reason": reason}
