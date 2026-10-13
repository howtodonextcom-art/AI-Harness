"""Pre-registered evaluation periods (docs/evals/edge-criteria.md). Chronological, end-exclusive."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Final

PERIODS: Final[Mapping[str, tuple[datetime, datetime]]] = MappingProxyType(
    {
        "development": (datetime(2025, 5, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
        "validation": (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 5, 1, tzinfo=UTC)),
        "test": (datetime(2026, 5, 1, tzinfo=UTC), datetime(2026, 10, 8, tzinfo=UTC)),
    }
)


def period_bounds(name: str, *, allow_test: bool = False) -> tuple[datetime, datetime]:
    """Return ``(start, end)`` of a named period; the test period needs explicit permission.

    The test period is touched once per finished candidate, so asking for it by accident is an
    error rather than a default.
    """
    if name not in PERIODS:
        msg = f"unknown period {name!r}; choose from {sorted(PERIODS)}"
        raise ValueError(msg)
    if name == "test" and not allow_test:
        msg = "the test period is single-use: pass allow_test=True for a finished candidate only"
        raise PermissionError(msg)
    return PERIODS[name]
