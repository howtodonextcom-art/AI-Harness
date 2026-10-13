"""Structured JSON logs with rotation (spec section 60).

Fields: timestamp, request_id, decision_id, model_version, data_timestamp, action, latency_ms,
error_code (+ level, message, path, status). Unknown values are null, never invented.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

FIELDS = (
    "request_id", "decision_id", "model_version", "data_timestamp", "action", "latency_ms",
    "error_code", "path", "status",
)  # fmt: skip


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key in FIELDS:
            out[key] = getattr(record, key, None)
        return json.dumps(out, default=str)


def configure_logging(
    log_dir: Path, *, max_bytes: int = 5_000_000, backups: int = 5
) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("xau_edge_v2")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    target = str((log_dir / "xau_edge_v2.jsonl").resolve())
    for existing in list(logger.handlers):
        if isinstance(existing, RotatingFileHandler):
            if existing.baseFilename == target:
                return logger  # already configured for this directory
            logger.removeHandler(existing)
            existing.close()
    handler = RotatingFileHandler(target, maxBytes=max_bytes, backupCount=backups, encoding="utf-8")
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger
