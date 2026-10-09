"""MaxBars helper: only that line changes, UTF-16 kept, no account field leaks, no guessing."""

from __future__ import annotations

from pathlib import Path

import pytest

from xau_edge.market_data.mt5.maxbars import (
    apply_max_bars,
    decode_ini,
    find_candidates,
    read_max_bars,
    select_ftmo,
)

INI = "[Common]\r\nLogin=7654321\r\nServer=FTMO-Demo\r\n[Charts]\r\nMaxBars=100000\r\nOther=1\r\n"


def make_terminal(appdata: Path, name: str, origin: str, ini_text: str = INI) -> Path:
    data = appdata / "MetaQuotes" / "Terminal" / name
    (data / "config").mkdir(parents=True)
    (data / "config" / "common.ini").write_bytes(b"\xff\xfe" + ini_text.encode("utf-16-le"))
    (data / "origin.txt").write_bytes(b"\xff\xfe" + origin.encode("utf-16-le"))
    return data


def test_apply_changes_only_the_maxbars_value_and_keeps_utf16() -> None:
    raw = b"\xff\xfe" + INI.encode("utf-16-le")
    updated = apply_max_bars(raw, 10_000_000)
    old_text, _ = decode_ini(raw)
    new_text, encoding = decode_ini(updated)
    assert encoding == "utf-16"
    assert read_max_bars(new_text) == 10_000_000
    assert new_text == old_text.replace("MaxBars=100000", "MaxBars=10000000")
    assert updated[:2] == b"\xff\xfe"


def test_missing_maxbars_line_is_an_error_not_a_guess() -> None:
    with pytest.raises(ValueError, match="no MaxBars"):
        apply_max_bars(b"[Charts]\r\nFoo=1\r\n", 5)


def test_finds_every_terminal_and_selects_exactly_one_ftmo(tmp_path: Path) -> None:
    make_terminal(tmp_path, "AAA", r"C:\Program Files\MetaTrader 5")
    make_terminal(tmp_path, "BBB", r"C:\Program Files\FTMO Global Markets MT5 Terminal")
    candidates = find_candidates(
        tmp_path, r"C:\Program Files\FTMO Global Markets MT5 Terminal\terminal64.exe"
    )
    assert {c.data_dir.name for c in candidates} == {"AAA", "BBB"}
    chosen = select_ftmo(candidates)
    assert chosen is not None
    assert chosen.data_dir.name == "BBB"
    assert chosen.max_bars == 100000


def test_ambiguous_or_missing_ftmo_selects_nothing(tmp_path: Path) -> None:
    make_terminal(tmp_path, "A1", r"C:\FTMO One")
    make_terminal(tmp_path, "A2", r"C:\FTMO Two")
    assert select_ftmo(find_candidates(tmp_path)) is None
    assert select_ftmo([]) is None
    assert find_candidates(tmp_path / "nowhere") == []


def test_candidate_report_never_contains_account_fields(tmp_path: Path) -> None:
    make_terminal(tmp_path, "BBB", r"C:\FTMO Terminal")
    (candidate,) = find_candidates(tmp_path)
    text = str(candidate.as_dict())
    assert "7654321" not in text
    assert "Login" not in text
    assert "FTMO-Demo" not in text
