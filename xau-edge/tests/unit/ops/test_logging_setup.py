"""Rotating file logging keeps the JSON redaction."""

from __future__ import annotations

import io
import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from xau_edge.observability import REDACTED, ROOT_LOGGER, log_event
from xau_edge.ops.logging_setup import XauFileHandler, close_service_logging, setup_service_logging

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _cleanup() -> Iterator[None]:
    yield
    close_service_logging()
    logging.getLogger(ROOT_LOGGER).handlers.clear()


def flush() -> None:
    for h in logging.getLogger(ROOT_LOGGER).handlers:
        h.flush()


def test_info_goes_to_file_but_not_console_and_secrets_are_redacted(tmp_path: Path) -> None:
    console = io.StringIO()
    path = setup_service_logging(tmp_path / "logs" / "bot.log", stream=console)
    log = logging.getLogger("xau_edge.test")
    log_event(log, "cycle.done", rows=3, bot_token="abc123")
    log_event(log, "careful", logging.WARNING, note="password=hunter2")
    flush()
    text = path.read_text(encoding="utf-8")
    lines = [json.loads(x) for x in text.splitlines()]
    assert [x["event"] for x in lines] == ["cycle.done", "careful"]
    assert lines[0]["bot_token"] == REDACTED
    assert "hunter2" not in text
    assert "cycle.done" not in console.getvalue()
    assert "careful" in console.getvalue()


def test_setup_is_idempotent_and_rotates(tmp_path: Path) -> None:
    path = setup_service_logging(
        tmp_path / "bot.log", stream=io.StringIO(), max_bytes=300, backup_count=2
    )
    setup_service_logging(path, stream=io.StringIO(), max_bytes=300, backup_count=2)
    handlers = [h for h in logging.getLogger(ROOT_LOGGER).handlers if isinstance(h, XauFileHandler)]
    assert len(handlers) == 1
    log = logging.getLogger("xau_edge.test")
    for i in range(40):
        log_event(log, "tick", n=i)
    flush()
    assert (tmp_path / "bot.log.1").exists()
    assert not (tmp_path / "bot.log.3").exists()


def test_unknown_level_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown log level"):
        setup_service_logging(tmp_path / "x.log", file_level="LOUD")
