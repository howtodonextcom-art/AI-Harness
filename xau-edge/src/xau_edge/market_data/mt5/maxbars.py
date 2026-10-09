"""Find and (when explicitly asked, with the terminal closed) change the terminal's MaxBars setting.

``[Charts] MaxBars`` in a terminal data folder's ``config/common.ini`` is "Max bars in chart". It
caps how much history the terminal serves to Python. Only that one line is ever read or written:
the file also holds account fields, which this module never touches, prints or returns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

MAXBARS_LINE = re.compile(r"^MaxBars=(\d+)[ \t]*\r?$", flags=re.MULTILINE)
RECOMMENDED = 10_000_000


@dataclass(frozen=True)
class IniCandidate:
    """One terminal data folder."""

    data_dir: Path
    ini: Path
    install_path: str | None
    max_bars: int | None
    is_ftmo: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "data_dir": self.data_dir.name,
            "install_path": self.install_path,
            "max_bars": self.max_bars,
            "is_ftmo": self.is_ftmo,
        }


def decode_ini(raw: bytes) -> tuple[str, str]:
    """(text, encoding): MetaTrader writes UTF-16 with a BOM; fall back to UTF-8."""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16"), "utf-16"
    return raw.decode("utf-8"), "utf-8"


def read_max_bars(text: str) -> int | None:
    match = MAXBARS_LINE.search(text)
    return None if match is None else int(match.group(1))


def apply_max_bars(raw: bytes, value: int) -> bytes:
    """``raw`` with ONLY the MaxBars value replaced (encoding and every other byte preserved)."""
    text, encoding = decode_ini(raw)
    if MAXBARS_LINE.search(text) is None:
        msg = "no MaxBars line under [Charts]"
        raise ValueError(msg)
    updated = MAXBARS_LINE.sub(
        lambda m: f"MaxBars={value}" + ("\r" if m.group(0).endswith("\r") else ""), text, count=1
    )
    return (
        updated.encode(encoding)
        if encoding != "utf-16"
        else b"\xff\xfe" + updated.encode("utf-16-le")
    )


def _read_origin(data_dir: Path) -> str | None:
    origin = data_dir / "origin.txt"
    try:
        raw = origin.read_bytes()
    except OSError:
        return None
    text, _ = decode_ini(raw)
    return text.strip().strip("﻿") or None


def find_candidates(appdata: Path, terminal_path: str | None = None) -> list[IniCandidate]:
    """Every ``%APPDATA%/MetaQuotes/Terminal/<hash>/config/common.ini`` with its install origin."""
    base = appdata / "MetaQuotes" / "Terminal"
    out: list[IniCandidate] = []
    if not base.is_dir():
        return out
    for ini in sorted(base.glob("*/config/common.ini")):
        data_dir = ini.parent.parent
        origin = _read_origin(data_dir)
        try:
            text, _ = decode_ini(ini.read_bytes())
        except (OSError, UnicodeError):
            continue
        wanted = (terminal_path or "").lower().replace("/", "\\")
        looks_ftmo = origin is not None and (
            "ftmo" in origin.lower()
            or (wanted != "" and str(Path(wanted).parent).lower() in origin.lower())
        )
        out.append(IniCandidate(data_dir, ini, origin, read_max_bars(text), looks_ftmo))
    return out


def select_ftmo(candidates: list[IniCandidate]) -> IniCandidate | None:
    """The single FTMO terminal folder, or None when zero or several match (never guess)."""
    matches = [c for c in candidates if c.is_ftmo]
    return matches[0] if len(matches) == 1 else None
