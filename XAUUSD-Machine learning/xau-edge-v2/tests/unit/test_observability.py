from __future__ import annotations

import json
from pathlib import Path

from xau_edge_v2.observability import FIELDS, configure_logging


def test_json_lines_have_every_required_field(tmp_path: Path) -> None:
    log = configure_logging(tmp_path)
    log.info("hello", extra={"request_id": "r1", "latency_ms": 1.5, "status": 200})
    for handler in log.handlers:
        handler.flush()
    row = json.loads((tmp_path / "xau_edge_v2.jsonl").read_text().splitlines()[-1])
    for key in ("timestamp", "level", "message", *FIELDS):
        assert key in row
    assert row["request_id"] == "r1" and row["decision_id"] is None  # unknown stays null
