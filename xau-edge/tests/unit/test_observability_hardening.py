"""Hardening found by the independent reviews: redaction precision, fail-safe formatting."""

from __future__ import annotations

import io
import json
import logging
import threading
from typing import Any

import numpy as np
import pytest

from xau_edge.observability import REDACTED, JsonFormatter, XauHandler, configure_logging

LOGGER = "xau_edge.test"


def _record(message: str = "evt", **fields: Any) -> logging.LogRecord:
    record = logging.LogRecord(LOGGER, logging.INFO, __file__, 1, message, None, None)
    record.fields = fields
    return record


def _format(**fields: Any) -> dict[str, object]:
    out = json.loads(JsonFormatter().format(_record(**fields)))
    assert isinstance(out, dict)
    return out


@pytest.fixture(autouse=True)
def _reset_logger() -> object:
    yield
    logger = logging.getLogger("xau_edge")
    for handler in [h for h in logger.handlers if isinstance(h, XauHandler)]:
        logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True


@pytest.mark.parametrize("key", ["passed", "bypass", "compass", "rows", "timeframe", "duplicate"])
def test_ordinary_keys_survive_redaction(key: str) -> None:
    assert _format(**{key: 7})[key] == 7


@pytest.mark.parametrize(
    "key",
    [
        "pwd",
        "passwd",
        "auth",
        "Authorization",
        "bearer",
        "cookie",
        "private_key",
        "apikey",
        "MT5_SERVER_PASSWORD",
        "sessionId",
        "dsn",
        "accounts",
        "tokens",
    ],
)
def test_more_credential_key_shapes_are_redacted(key: str) -> None:
    assert _format(**{key: "s3cr3t"})[key] == REDACTED


def test_secrets_embedded_in_strings_and_messages_are_scrubbed() -> None:
    text = json.dumps(_format(conn="login=123456;password=hunter2 token: abc"))
    assert "hunter2" not in text
    assert "123456" not in text
    assert "abc" not in text
    line = JsonFormatter().format(_record("failed password=hunter2"))
    assert "hunter2" not in line


def test_unknown_objects_are_not_stringified() -> None:
    class Leaky:
        def __str__(self) -> str:
            return "pw=hunter2"

        __repr__ = __str__

    out = _format(obj=Leaky())
    assert "hunter2" not in json.dumps(out)
    assert out["obj"] == "<Leaky>"


def _reject(token: str) -> None:
    msg = f"non-standard JSON constant {token}"
    raise AssertionError(msg)


def test_non_finite_floats_produce_valid_json() -> None:
    line = JsonFormatter().format(_record(x=float("nan"), y=float("inf")))
    out = json.loads(line, parse_constant=_reject)
    assert out["event"] == "evt"
    assert out["x"] == "nan"
    assert out["y"] == "inf"


def test_cyclic_structures_do_not_crash_the_caller() -> None:
    cyc: list[object] = []
    cyc.append(cyc)
    assert json.loads(JsonFormatter().format(_record(cyc=cyc)))["event"] == "evt"


def test_oversized_values_are_truncated() -> None:
    line = JsonFormatter().format(_record(big="x" * 1_000_000, many=list(range(10_000))))
    out = json.loads(line)
    assert len(out["big"]) < 5_000
    assert len(out["many"]) <= 101


def test_formatter_never_raises_on_bad_fields_or_args() -> None:
    bad_args = logging.LogRecord(LOGGER, logging.INFO, __file__, 1, "%s %s", ("a",), None)
    assert json.loads(JsonFormatter().format(bad_args))["event"] == "log_format_error"
    bad_fields = _record()
    bad_fields.fields = 5
    assert json.loads(JsonFormatter().format(bad_fields))["event"] == "evt"


def test_configure_logging_stops_propagation_and_is_thread_safe() -> None:
    stream = io.StringIO()
    threads = [
        threading.Thread(target=configure_logging, args=("INFO",), kwargs={"stream": stream})
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    logger = logging.getLogger("xau_edge")
    assert logger.propagate is False
    assert len([h for h in logger.handlers if isinstance(h, XauHandler)]) == 1


def test_numpy_scalars_keep_their_values() -> None:
    out = _format(n=np.int64(5), f=np.float32(1.5), b=np.bool_(True), nan=np.float64("nan"))
    assert out["n"] == 5
    assert out["f"] == 1.5
    assert out["b"] is True
    assert out["nan"] == "nan"


@pytest.mark.parametrize(
    "text",
    [
        "access_token=abc123",
        "client_secret: abc123",
        "db_password=abc123",
        "Authorization: Bearer abc123",
        "refresh_token=abc123",
    ],
)
def test_compound_secret_assignments_are_scrubbed(text: str) -> None:
    assert "abc123" not in json.dumps(_format(msg=text))


def test_huge_integers_are_bounded() -> None:
    out = _format(big=10**5000)
    assert len(str(out["big"])) < 100
