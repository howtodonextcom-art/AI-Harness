# ruff: noqa: E501 - these modules carry their selection/audit record as prose
"""First-failure waterfall: every detected pattern gets exactly ONE class, the first gate it fails.

The order is fixed here and documented in the report; it is not tuned to any result:

    DETECTED
      -> INVALID_GEOMETRY        levels on the wrong side after adverse tick rounding
      -> ROOM_FAIL               opposing confirmed structure does not leave the reward distance + 1 tick (or room unknown)
      -> GROSS_RR_FAIL           gross reward-to-risk below the floor (1.5, never lower)
      -> FILL_UNVERIFIED         no causal executable fill with an evidenced spread
      -> COST_UNVERIFIED         spread / slippage / commission / swap not all verified
      -> NET_RR_FAIL             net reward-to-risk below the floor (or not computable)
      -> PROBABILITY_UNAVAILABLE no calibrated out-of-sample probability
      -> ENTRY_ELIGIBLE          every gate passed (a future programme's candidate, never an order)

The classes partition the detections (the counts add up to the number detected). The raw, overlapping
reasons are reported separately: a pattern that fails three gates counts once in the partition and three
times in ``raw_reasons``. Nothing here reads a price after detection and nothing is an outcome.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MIN_RR_FLOOR = 1.5


class Stage(StrEnum):
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    ROOM_FAIL = "ROOM_FAIL"
    GROSS_RR_FAIL = "GROSS_RR_FAIL"
    FILL_UNVERIFIED = "FILL_UNVERIFIED"
    COST_UNVERIFIED = "COST_UNVERIFIED"
    NET_RR_FAIL = "NET_RR_FAIL"
    PROBABILITY_UNAVAILABLE = "PROBABILITY_UNAVAILABLE"
    ENTRY_ELIGIBLE = "ENTRY_ELIGIBLE"


ORDER: tuple[Stage, ...] = tuple(Stage)


class GateRecord(BaseModel):
    """What each gate says about one detection. ``None`` means unknown, which is never a pass."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    family: str
    pattern_id: str
    valid_geometry: bool
    room_ok: bool | None = None
    gross_rr: float | None = Field(default=None, allow_inf_nan=False)
    fill_verified: bool = False
    cost_verified: bool = False
    net_rr: float | None = Field(default=None, allow_inf_nan=False)
    probability_available: bool = False


def raw_reasons(rec: GateRecord, min_rr: float = MIN_RR_FLOOR) -> frozenset[Stage]:
    """Every gate the record fails, overlapping. Gates that need a failed earlier input are still listed."""
    floor = max(min_rr, MIN_RR_FLOOR)
    out: set[Stage] = set()
    if not rec.valid_geometry:
        out.add(Stage.INVALID_GEOMETRY)
    if rec.room_ok is not True:
        out.add(Stage.ROOM_FAIL)
    if rec.gross_rr is None or rec.gross_rr < floor:
        out.add(Stage.GROSS_RR_FAIL)
    if not rec.fill_verified:
        out.add(Stage.FILL_UNVERIFIED)
    if not rec.cost_verified:
        out.add(Stage.COST_UNVERIFIED)
    if rec.net_rr is None or rec.net_rr < floor:
        out.add(Stage.NET_RR_FAIL)
    if not rec.probability_available:
        out.add(Stage.PROBABILITY_UNAVAILABLE)
    return frozenset(out)


def first_failure(rec: GateRecord, min_rr: float = MIN_RR_FLOOR) -> Stage:
    failed = raw_reasons(rec, min_rr)
    for stage in ORDER:
        if stage in failed:
            return stage
    return Stage.ENTRY_ELIGIBLE


def waterfall(
    records: Iterable[GateRecord], min_rr: float = MIN_RR_FLOOR
) -> dict[str, dict[str, Any]]:
    """Per family and ``ALL``: detected, first-failure partition, overlapping raw reasons, survivors."""
    by_family: dict[str, list[GateRecord]] = {}
    for rec in records:
        by_family.setdefault(rec.family, []).append(rec)
    by_family["ALL"] = [r for rs in list(by_family.values()) for r in rs]
    out: dict[str, dict[str, Any]] = {}
    for family, recs in sorted(by_family.items()):
        first = Counter(first_failure(r, min_rr) for r in recs)
        raw: Counter[Stage] = Counter()
        for r in recs:
            raw.update(raw_reasons(r, min_rr))
        # survivors[s] = detections that pass every gate up to and including s
        survivors: dict[str, int] = {"DETECTED": len(recs)}
        alive = len(recs)
        for stage in ORDER[:-1]:
            alive -= first.get(stage, 0)
            survivors[f"PASSED_{stage.value}"] = alive
        out[family] = {
            "detected": len(recs),
            "first_failure": {s.value: first.get(s, 0) for s in ORDER},
            "raw_reasons_overlapping": {s.value: raw.get(s, 0) for s in ORDER[:-1]},
            "survivors": survivors,
        }
    return out
