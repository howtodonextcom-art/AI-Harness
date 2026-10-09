"""The live decision path never touches the legacy research store or the MT5 order API."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3] / "src" / "xau_edge"
LIVE_FILES = [*sorted((ROOT / "trading").glob("*.py")), ROOT / "api" / "trade.py"]
FORBIDDEN_IMPORTS = [
    r"xau_edge\.market_data\.catalog",
    r"xau_edge\.market_data\.raw_store",
    r"xau_edge\.signals\.(engine|evidence)",
    r"xau_edge\.brokers\.mt5_demo\.(orders|trade)",
    r"MetaTrader5",
]


def _code(path: Path) -> str:
    """Source without comments and docstring prose (only imports and code matter)."""
    return "\n".join(
        line
        for line in path.read_text(encoding="utf-8").splitlines()
        if re.match(r"\s*(from|import) ", line)
    )


def test_live_path_imports_nothing_legacy_and_no_order_api() -> None:
    assert LIVE_FILES
    offenders = [
        (path.name, pattern)
        for path in LIVE_FILES
        for pattern in FORBIDDEN_IMPORTS
        if re.search(pattern, _code(path))
    ]
    assert offenders == []


def test_no_live_path_file_names_the_raw_store_in_code() -> None:
    for path in LIVE_FILES:
        # docstrings may mention "data/raw" to say it is NOT read; code strings may not
        text = path.read_text(encoding="utf-8")
        code_strings = re.findall(r'(?<![`])"(?:[^"\n]*data/raw[^"\n]*)"', text)
        assert code_strings == [], path.name


def test_the_trade_api_has_no_order_call() -> None:
    text = (ROOT / "api" / "trade.py").read_text(encoding="utf-8")
    assert "order_send" not in text
