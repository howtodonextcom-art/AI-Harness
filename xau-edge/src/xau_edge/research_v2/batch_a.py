"""Batch A (H07-H10): the 24 frozen variants and the guarded loader for Development-2.

Splits (roadmap 13.1): Development-2 2011-01-01..2018-12-31, Validation-2 2019-01-01..2021-12-31,
Test-H 2022-01-01..2025-04-30 (LOCKED). This module exposes Development-2 and Validation-2 only;
asking for Test-H or anything at or after 2025-05-01 raises, and the freeze guard is separate
(``guards.py``). Loading a window reads no bar at or after its end.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import polars as pl

from xau_edge.research_v2.events import (
    EventSet,
    sweep_events,
    transition_events,
    volatility_events,
)
from xau_edge.research_v2.frame import H1Frame, build_frame, uncertified_years

ROOT: Final = Path(__file__).resolve().parents[3]
CERTIFICATE: Final = ROOT / "docs" / "research" / "edge-program-v2" / "clock-certificate.json"
WINDOWS: Final = {
    "dev2": (datetime(2011, 1, 1, tzinfo=UTC), datetime(2019, 1, 1, tzinfo=UTC)),
    "val2": (datetime(2019, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC)),
}
LOCKED: Final = ("testH", "holdout")
K_BATCH_A: Final = 24


class LockedSplitError(PermissionError):
    """A locked split (Test-H, holdout) was requested without its freeze record."""


@dataclass(frozen=True)
class Variant:
    """One frozen variant: its id, hypothesis and the function that builds its events."""

    id: str
    hypothesis: str
    build: Callable[[H1Frame, pl.DataFrame], EventSet]


Builder = Callable[[H1Frame, pl.DataFrame], EventSet]


def _sweep(level_set: str, mode: str, eps: float) -> Builder:
    def build(f: H1Frame, _h4: pl.DataFrame) -> EventSet:
        return sweep_events(f, level_set, mode, eps)

    return build


def _transition(transition: str, tercile: float) -> Builder:
    def build(f: H1Frame, h4: pl.DataFrame) -> EventSet:
        return transition_events(f, h4, transition, tercile)

    return build


def _volatility(c_max: float, lookback: int) -> Builder:
    def build(f: H1Frame, h4: pl.DataFrame) -> EventSet:
        return volatility_events(f, h4, c_max, lookback)

    return build


def variants() -> list[Variant]:
    """The 24 Batch A variants, exactly as registered (grid trimmed to 6 per hypothesis)."""
    out: list[Variant] = []
    for mode, hyp in (("reject", "H07"), ("accept", "H08")):
        for level_set in ("PD", "ASIA"):
            for eps in (0.0, 0.25, 0.5):
                out.append(
                    Variant(
                        f"{hyp}-{level_set}-e{eps:g}",
                        hyp,
                        _sweep(level_set, mode, eps),
                    )
                )
    for transition in ("ASIA_LONDON", "LONDON_NY"):
        for tercile in (0.2, 0.3, 0.4):
            out.append(
                Variant(
                    f"H09-{transition}-t{tercile:g}",
                    "H09",
                    _transition(transition, tercile),
                )
            )
    for c_max in (0.8, 0.9):
        for lookback in (20, 50, 100):
            out.append(
                Variant(
                    f"H10-c{c_max:g}-L{lookback}",
                    "H10",
                    _volatility(c_max, lookback),
                )
            )
    return out


def window_bars(
    h1: pl.DataFrame, h4: pl.DataFrame, window: str
) -> tuple[pl.DataFrame, pl.DataFrame, datetime, datetime]:
    """Bars strictly before the window's end (warm-up included) and the window bounds."""
    if window in LOCKED or window not in WINDOWS:
        msg = f"window {window!r} is not available to Batch A (Test-H and holdout are locked)"
        raise LockedSplitError(msg)
    start, end = WINDOWS[window]
    cols = ["timestamp", "open", "high", "low", "close", "spread"]
    return (
        h1.filter(pl.col("timestamp") < end).select(cols),
        h4.filter(pl.col("timestamp") < end).select("timestamp", "close"),
        start,
        end,
    )


def frame_for(h1: pl.DataFrame, h4: pl.DataFrame, window: str) -> tuple[H1Frame, pl.DataFrame, int]:
    """Frame of everything before the window end, the H4 frame, and the first in-window index."""
    bars, h4_bars, start, _end = window_bars(h1, h4, window)
    frame = build_frame(bars, uncertified_years(CERTIFICATE))
    first = int((bars["timestamp"] < start).sum())
    return frame, h4_bars, first


def in_window(events: EventSet, first: int) -> EventSet:
    """Keep events decided inside the window (earlier ones are warm-up)."""
    keep = events.decision >= first
    return EventSet(
        events.name,
        events.decision[keep],
        events.direction[keep],
        [lv for lv, k in zip(events.level, keep, strict=True) if k],
        events.excluded_unsafe,
    )
