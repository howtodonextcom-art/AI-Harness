"""Supported bar timeframes."""

from __future__ import annotations

from datetime import timedelta
from enum import StrEnum

_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240}


class Timeframe(StrEnum):
    """Bar timeframes supported by the platform (M1 and M30 added for the trading core)."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"

    @property
    def minutes(self) -> int:
        """Bar length in minutes."""
        return _MINUTES[self.value]

    @property
    def delta(self) -> timedelta:
        """Bar length as a ``timedelta``."""
        return timedelta(minutes=self.minutes)

    @classmethod
    def parse(cls, value: str) -> Timeframe:
        """Parse a case-insensitive timeframe label such as ``"h1"``."""
        try:
            return cls(value.strip().upper())
        except ValueError:
            supported = ", ".join(t.value for t in cls)
            msg = f"Unsupported timeframe {value!r}; supported: {supported}"
            raise ValueError(msg) from None
