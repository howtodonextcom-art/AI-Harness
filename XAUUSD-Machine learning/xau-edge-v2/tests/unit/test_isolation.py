"""ADR-V2-006 and ADR-V2-008: no import from V1, and no way to send an order."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "xau_edge_v2"
FILES = sorted(SRC.rglob("*.py"))


def test_sources_found() -> None:
    assert len(FILES) >= 8


def test_no_import_from_v1_or_reference() -> None:
    bad = re.compile(r"^\s*(from|import)\s+xau_edge(\.|\s|$)", re.M)
    for f in FILES:
        text = f.read_text(encoding="utf-8")
        assert not bad.search(text), f"{f} imports the V1 package"
        assert "reference-v1" not in text, f"{f} mentions reference-v1"


def test_no_order_path_exists() -> None:
    forbidden = ("order_send", "order_check", "MetaTrader5", "import mt5")
    for f in FILES:
        text = f.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{f} contains {token}"
