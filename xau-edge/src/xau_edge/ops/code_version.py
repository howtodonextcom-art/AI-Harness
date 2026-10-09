"""The code version recorded with every journal line and evaluation: short git SHA (+ ``-dirty``).

Never raises: outside a git checkout (or without git) it returns ``unknown`` so a journal line is
still written, but an evaluation script refuses to certify a result without a SHA.
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            ["git", *args],  # noqa: S607 - git on PATH
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


@lru_cache(maxsize=1)
def current_code_version() -> str:
    """``XAU_EDGE_CODE_VERSION`` if set, else ``<short sha>[-dirty]``, else ``unknown``."""
    override = os.environ.get("XAU_EDGE_CODE_VERSION")
    if override:
        return override
    sha = _git("rev-parse", "--short", "HEAD")
    if not sha:
        return "unknown"
    dirty = _git("status", "--porcelain", "--untracked-files=no")
    return f"{sha}-dirty" if dirty else sha
