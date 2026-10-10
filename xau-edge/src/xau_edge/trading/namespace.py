"""Keep live paper, acceptance replay, fixtures and tests in separate namespaces.

A trade root is claimed once by one source mode (``LIVE`` or ``ACCEPTANCE_REPLAY``) in a
``SOURCE_MODE`` file. Opening it with a different mode is refused, so a replay can never write into
the live journal and live code can never read replay trades as its own.
"""

from __future__ import annotations

from pathlib import Path

MODES = ("LIVE", "ACCEPTANCE_REPLAY", "FIXTURE")
MARKER = "SOURCE_MODE"


class NamespaceError(RuntimeError):
    """The root belongs to another source mode."""


def claim_root(root: Path | str, mode: str) -> None:
    """Bind ``root`` to ``mode`` (idempotent) or raise ``NamespaceError`` if it has another one."""
    if mode not in MODES:
        msg = f"unknown source mode {mode!r}"
        raise NamespaceError(msg)
    base = Path(root)
    base.mkdir(parents=True, exist_ok=True)
    marker = base / MARKER
    if marker.exists():
        existing = marker.read_text(encoding="utf-8").strip()
        if existing != mode:
            msg = (
                f"{base} belongs to source mode {existing}, not {mode}: refusing to mix namespaces"
            )
            raise NamespaceError(msg)
        return
    marker.write_text(mode + "\n", encoding="utf-8")
