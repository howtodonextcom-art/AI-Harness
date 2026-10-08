"""Structured logging: JSON shape, redaction, idempotent setup, and pipeline log events."""

from __future__ import annotations

import io
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from tests.conftest import make_bars
from xau_edge.domain.timeframe import Timeframe
from xau_edge.market_data.catalog import DatasetCatalog
from xau_edge.market_data.store import RawStore
from xau_edge.market_data.validators.checks import validate_bars
from xau_edge.observability import (
    REDACTED,
    JsonFormatter,
    XauHandler,
    configure_logging,
    log_event,
)

LOGGER = "xau_edge.test"


def _format(**fields: object) -> dict[str, object]:
    record = logging.LogRecord(LOGGER, logging.INFO, __file__, 1, "evt", None, None)
    record.fields = fields
    out = json.loads(JsonFormatter().format(record))
    assert isinstance(out, dict)
    return out


def test_formatter_emits_one_json_object_with_core_keys() -> None:
    out = _format(rows=3)
    assert out["event"] == "evt"
    assert out["level"] == "INFO"
    assert out["logger"] == LOGGER
    assert out["rows"] == 3
    datetime.fromisoformat(str(out["ts"]))


def test_formatter_serialises_non_json_values() -> None:
    out = _format(when=datetime(2025, 1, 1, tzinfo=UTC), where=Path("a/b"), tf=Timeframe.M5)
    assert out["when"] == "2025-01-01 00:00:00+00:00"
    assert out["tf"] == "M5"


@pytest.mark.parametrize(
    "key", ["password", "MT5_PASSWORD", "api_key", "secret", "token", "mt5_login", "login"]
)
def test_sensitive_keys_are_redacted(key: str) -> None:
    out = _format(**{key: "hunter2"})
    assert out[key] == REDACTED
    assert "hunter2" not in json.dumps(out)


def test_nested_sensitive_keys_are_redacted() -> None:
    out = _format(broker={"login": 123456, "server": "Demo", "extra": [{"password": "p"}]})
    text = json.dumps(out)
    assert "123456" not in text
    assert '"p"' not in text
    assert "Demo" in text


def test_reserved_keys_cannot_be_overwritten_by_fields() -> None:
    out = _format(event="spoof", level="CRITICAL", ts="x")
    assert out["event"] == "evt"
    assert out["level"] == "INFO"
    assert out["ts"] != "x"
    assert out["field_event"] == "spoof"


def test_configure_logging_is_idempotent_and_honours_level() -> None:
    stream = io.StringIO()
    configure_logging("WARNING", stream=stream)
    configure_logging("WARNING", stream=stream)
    logger = logging.getLogger("xau_edge")
    assert len([h for h in logger.handlers if isinstance(h, XauHandler)]) == 1
    log_event(logging.getLogger("xau_edge.x"), "dropped", logging.INFO)
    log_event(logging.getLogger("xau_edge.x"), "kept", logging.ERROR, n=1)
    lines = stream.getvalue().strip().splitlines()
    assert [json.loads(line)["event"] for line in lines] == ["kept"]


def test_configure_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="log level"):
        configure_logging("LOUD")


@pytest.fixture(autouse=True)
def _reset_logger() -> object:
    yield
    logger = logging.getLogger("xau_edge")
    for handler in [h for h in logger.handlers if isinstance(h, XauHandler)]:
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


def _events(caplog: pytest.LogCaptureFixture) -> dict[str, dict[str, object]]:
    return {r.getMessage(): getattr(r, "fields", {}) for r in caplog.records}


def test_raw_write_logs_ingestion(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="xau_edge")
    df = make_bars(10, Timeframe.M5)
    ds = RawStore(tmp_path).write(df, symbol="XAUUSD", timeframe=Timeframe.M5, source="file")
    fields = _events(caplog)["raw.write"]
    assert fields["symbol"] == "XAUUSD"
    assert fields["rows"] == 10
    assert fields["sha256"] == ds.sha256
    assert fields["duplicate"] is False


def test_raw_write_of_identical_data_logs_duplicate(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store = RawStore(tmp_path)
    df = make_bars(10, Timeframe.M5)
    store.write(df, symbol="XAUUSD", timeframe=Timeframe.M5, source="file")
    caplog.set_level(logging.INFO, logger="xau_edge")
    store.write(df, symbol="XAUUSD", timeframe=Timeframe.M5, source="file")
    assert _events(caplog)["raw.write"]["duplicate"] is True


def test_validation_logs_verdict_and_issue_counts(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="xau_edge")
    bad = make_bars(10, Timeframe.M15).with_columns(pl.lit(-1).alias("tick_volume"))
    report = validate_bars(bad, Timeframe.M15)
    rec = next(r for r in caplog.records if r.getMessage() == "validation.result")
    fields = rec.fields  # type: ignore[attr-defined]
    assert fields["passed"] is report.passed is False
    assert fields["rows"] == 10
    assert fields["issues"]["NEGATIVE_VOLUME"] == 10
    assert rec.levelno == logging.WARNING


def test_passing_validation_logs_at_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="xau_edge")
    validate_bars(make_bars(10, Timeframe.M15), Timeframe.M15)
    rec = next(r for r in caplog.records if r.getMessage() == "validation.result")
    assert rec.levelno == logging.INFO


def test_catalog_load_logs_dataset_id(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    RawStore(tmp_path).write(
        make_bars(10, Timeframe.M5), symbol="XAUUSD", timeframe=Timeframe.M5, source="file"
    )
    caplog.set_level(logging.INFO, logger="xau_edge")
    loaded = DatasetCatalog(tmp_path).load("XAUUSD", Timeframe.M5)
    fields = _events(caplog)["catalog.load"]
    assert fields["dataset_id"] == loaded.dataset_id
    assert fields["rows"] == 10


def test_exception_type_is_logged_without_message() -> None:
    try:
        raise RuntimeError("password=hunter2")
    except RuntimeError:
        record = logging.LogRecord(LOGGER, logging.ERROR, __file__, 1, "boom", None, sys.exc_info())
    out = json.loads(JsonFormatter().format(record))
    assert out["exc_type"] == "RuntimeError"
    assert "hunter2" not in json.dumps(out)
