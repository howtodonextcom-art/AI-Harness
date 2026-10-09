"""Atomic text writes that survive concurrent readers (including Windows sharing violations).

Write a temp file, then ``os.replace`` it over the target. On Windows the replace can fail with
``PermissionError`` while a reader holds the target open; that is transient, so it is retried
briefly. Readers therefore see the old or the new complete file, never a torn one.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

RETRIES = 200
RETRY_SLEEP = 0.01


def atomic_write_text(path: Path, text: str, *, retries: int = RETRIES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    for attempt in range(retries):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if attempt == retries - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(RETRY_SLEEP)
