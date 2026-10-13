"""Kill switch: once tripped, nothing may trade until a human resets it deliberately."""

from __future__ import annotations

import logging
from typing import Final

from xau_edge.observability import log_event

RESET_PHRASE: Final = "I understand the risk"
_LOG = logging.getLogger(__name__)


class KillSwitch:
    """Latching stop. ``trip`` keeps the FIRST reason; ``reset`` needs the exact phrase."""

    def __init__(self) -> None:
        self._reason: str | None = None

    @property
    def tripped(self) -> bool:
        """True while trading is blocked."""
        return self._reason is not None

    @property
    def reason(self) -> str:
        """Why the switch tripped (empty when it has not)."""
        return self._reason or ""

    def trip(self, reason: str) -> None:
        """Block trading. Later calls do not overwrite the original reason."""
        if self._reason is None:
            self._reason = reason
            log_event(_LOG, "kill_switch.trip", logging.CRITICAL, reason=reason)

    def reset(self, *, confirm: str) -> None:
        """Re-enable trading; ``confirm`` must equal ``RESET_PHRASE``."""
        if confirm != RESET_PHRASE:
            msg = f"confirm must be exactly {RESET_PHRASE!r} to reset the kill switch"
            raise ValueError(msg)
        log_event(_LOG, "kill_switch.reset", logging.WARNING, previous_reason=self.reason)
        self._reason = None
