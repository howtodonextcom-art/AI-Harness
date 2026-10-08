"""File logging for the 24/5 service: INFO to a rotating file, with the existing JSON redaction.

``observability.configure_logging`` is left untouched. This helper calls it (console handler at
``console_level``) and then lowers the logger to INFO and adds a rotating file handler that reuses
``JsonFormatter``, so every line in the file is redacted exactly like the console output.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from xau_edge.observability import ROOT_LOGGER, JsonFormatter, XauHandler, configure_logging


class XauFileHandler(RotatingFileHandler):
    """Marker subclass so the helper can find and replace its own handler (idempotent setup)."""


def setup_service_logging(
    log_file: Path | str,
    *,
    file_level: str = "INFO",
    console_level: str = "WARNING",
    max_bytes: int = 5_000_000,
    backup_count: int = 10,
    stream: TextIO | None = None,
) -> Path:
    """Install the console handler and a rotating JSON file handler; return the log path."""
    numeric = logging.getLevelName(file_level.upper())
    if not isinstance(numeric, int):
        msg = f"unknown log level: {file_level!r}"
        raise ValueError(msg)
    path = Path(log_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    configure_logging(console_level, stream=stream)
    logger = logging.getLogger(ROOT_LOGGER)
    console = logging.getLevelName(console_level.upper())
    for existing in [h for h in logger.handlers if isinstance(h, XauFileHandler)]:
        logger.removeHandler(existing)
        existing.close()
    for handler in logger.handlers:
        if isinstance(handler, XauHandler):
            handler.setLevel(console)
    file_handler = XauFileHandler(
        path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", delay=True
    )
    file_handler.setLevel(numeric)
    file_handler.setFormatter(JsonFormatter())
    logger.addHandler(file_handler)
    logger.setLevel(min(numeric, console))
    return path


def close_service_logging() -> None:
    """Remove and close the file handler (used by tests and on shutdown)."""
    logger = logging.getLogger(ROOT_LOGGER)
    for handler in [h for h in logger.handlers if isinstance(h, XauFileHandler)]:
        logger.removeHandler(handler)
        handler.close()
