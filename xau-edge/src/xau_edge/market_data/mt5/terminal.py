"""Find MetaTrader 5 terminals on a Windows machine (no installation, no network, no secrets).

``discover_terminals`` looks for ``terminal64.exe`` in the usual install locations and in the
MetaQuotes data folder; ``select_terminal`` picks one deterministically: the explicit preference
first, then a terminal whose folder name mentions the broker, then the first by path. Nothing is
installed or launched here, and no configuration file is read (they contain account details).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

TERMINAL_NAME = "terminal64.exe"
MAX_DEPTH = 3


@dataclass(frozen=True)
class TerminalCandidate:
    """A terminal executable found on disk."""

    path: Path
    root: str
    broker_hint: str

    def as_dict(self) -> dict[str, str]:
        return {"path": str(self.path), "root": self.root, "broker_hint": self.broker_hint}


def default_roots(env: Mapping[str, str] | None = None) -> list[Path]:
    """Install and data folders worth searching on Windows."""
    env = env if env is not None else os.environ
    roots: list[Path] = []
    for key, fallback in (
        ("ProgramFiles", r"C:\Program Files"),
        ("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        ("LOCALAPPDATA", ""),
    ):
        value = env.get(key) or fallback
        if value:
            roots.append(Path(value))
    appdata = env.get("APPDATA")
    if appdata:
        roots.append(Path(appdata) / "MetaQuotes" / "Terminal")
    return roots


def _walk(root: Path, depth: int, listdir: Callable[[Path], Iterable[Path]]) -> Iterable[Path]:
    if depth < 0:
        return
    try:
        entries = list(listdir(root))
    except OSError:
        return
    for entry in entries:
        if entry.name.lower() == TERMINAL_NAME:
            yield entry
        elif depth > 0 and _is_dir(entry):
            yield from _walk(entry, depth - 1, listdir)


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def discover_terminals(
    roots: Iterable[Path] | None = None,
    *,
    listdir: Callable[[Path], Iterable[Path]] = lambda p: p.iterdir(),
    max_depth: int = MAX_DEPTH,
) -> list[TerminalCandidate]:
    """Every ``terminal64.exe`` under the roots (bounded depth), sorted by path."""
    found: dict[Path, TerminalCandidate] = {}
    for root in roots if roots is not None else default_roots():
        for exe in _walk(root, max_depth, listdir):
            hint = exe.parent.name
            found[exe] = TerminalCandidate(exe, str(root), hint)
    return sorted(found.values(), key=lambda c: str(c.path).lower())


def select_terminal(
    candidates: list[TerminalCandidate], *, preferred: Path | None = None, broker: str = "FTMO"
) -> TerminalCandidate | None:
    """The explicit preference, else a terminal whose folder mentions the broker, else the first."""
    if not candidates:
        return None
    if preferred is not None:
        for c in candidates:
            if str(c.path).lower() == str(preferred).lower():
                return c
    for c in candidates:
        if broker.lower() in str(c.path).lower():
            return c
    return candidates[0]
