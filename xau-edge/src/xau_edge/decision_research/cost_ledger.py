# ruff: noqa: E501 - these modules carry their selection/audit record as prose
"""Cost ledger: where every component of the all-in cost comes from, and whether it is verified.

``rr.CostModel`` carries four numbers and one flag. This module is the evidence behind the flag. Each
component (spread, slippage, commission, swap) records its value in price units for one round trip,
its source, the instant it was measured or read, the window it is relevant to, how it was converted,
and a status. UNKNOWN IS NOT ZERO: a component without a verified value has ``value=None`` (or an
explicit, labelled assumption), and :func:`gate_cost_model` then returns ``None`` so the gate stays
closed. A verified model needs all four components verified *and* fresh.

Nothing here reads an outcome and nothing here talks to a broker: values come from measurements that
already exist in the repository (tick/bar spread description of the cost model v2, a read-only MT5
``symbol_info`` reading) or are declared BLOCKED_EXTERNALLY with the exact evidence that would
unblock them.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from xau_edge.decision_research.rr import CostModel

POINT_SIZE = 0.01
"""XAUUSD: one MT5 point is 0.01 in price (the unit of every spread/swap figure below)."""

COST_MODEL_V2 = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "edge-program-v3"
    / "foundation"
    / "cost_model_v2.json"
)

ComponentName = Literal["spread", "slippage", "commission", "swap"]
COMPONENTS: tuple[ComponentName, ...] = ("spread", "slippage", "commission", "swap")


class CostStatus(StrEnum):
    VERIFIED_MEASURED = "VERIFIED_MEASURED"  # a measurement over recorded data
    VERIFIED_BROKER_SPEC = "VERIFIED_BROKER_SPEC"  # read from the broker terminal / contract
    UNVERIFIED_ASSUMPTION = "UNVERIFIED_ASSUMPTION"  # a declared number nobody has checked
    BLOCKED_EXTERNALLY = "BLOCKED_EXTERNALLY"  # needs evidence only the owner/broker can supply


VERIFIED = frozenset({CostStatus.VERIFIED_MEASURED, CostStatus.VERIFIED_BROKER_SPEC})


class CostComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: ComponentName
    value: float | None = Field(default=None, ge=0.0, allow_inf_nan=False)
    """Round-trip cost in PRICE units, or ``None`` when it is not known. ``None`` is never read as 0."""
    unit: str = "price units per round trip"
    source: str = Field(min_length=1)
    measured_at: datetime | None = None
    relevance: str = Field(min_length=1)
    """The window/condition the number is valid for (a year and session, a swap read date, ...)."""
    conversion: str = Field(min_length=1)
    status: CostStatus
    evidence_needed: str | None = None
    max_age_days: int | None = Field(default=None, ge=1)
    """A reading that changes over time (swap) expires; ``None`` means it does not."""

    @model_validator(mode="after")
    def _verified_means_evidenced(self) -> CostComponent:
        if self.status in VERIFIED:
            if self.value is None or self.measured_at is None:
                raise ValueError(f"{self.name}: a verified component needs a value and a timestamp")
            if self.measured_at.tzinfo is None:
                raise ValueError(f"{self.name}: measured_at must be timezone-aware")
        elif self.status is CostStatus.BLOCKED_EXTERNALLY and not self.evidence_needed:
            raise ValueError(f"{self.name}: a blocked component must say what evidence unblocks it")
        return self

    def usable(self, now: datetime) -> bool:
        """Verified, has a value, and not past its shelf life."""
        if self.status not in VERIFIED or self.value is None or self.measured_at is None:
            return False
        if self.max_age_days is None:
            return True
        return now - self.measured_at <= timedelta(days=self.max_age_days)


class CostLedger(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    components: tuple[CostComponent, ...]

    @model_validator(mode="after")
    def _one_of_each(self) -> CostLedger:
        names = sorted(c.name for c in self.components)
        if names != sorted(COMPONENTS):
            raise ValueError("a ledger needs exactly one of spread, slippage, commission, swap")
        return self

    def component(self, name: ComponentName) -> CostComponent:
        return next(c for c in self.components if c.name == name)

    def blockers(self, now: datetime) -> list[tuple[str, str, str]]:
        """(component, status, what is missing) for everything that keeps the model unverified."""
        out: list[tuple[str, str, str]] = []
        for c in self.components:
            if c.usable(now):
                continue
            if c.status in VERIFIED:  # verified once, but stale
                missing = f"re-read: the {c.name} reading is older than {c.max_age_days} days"
                out.append((c.name, "STALE", missing))
            else:
                missing = c.evidence_needed or "a verified source for this component"
                out.append((c.name, c.status.value, missing))
        return out

    def gate_cost_model(self, now: datetime) -> CostModel | None:
        """A verified ``CostModel`` iff every component is verified and fresh; otherwise ``None``.

        There is deliberately no way to obtain a "verified" model with an unknown component set to
        zero: the caller gets ``None`` and the authorization gate answers COST_MODEL_UNVERIFIED.
        """
        if self.blockers(now):
            return None
        values = {c.name: float(c.value or 0.0) for c in self.components}
        return CostModel(
            spread=values["spread"],
            slippage=values["slippage"],
            commission=values["commission"],
            swap=values["swap"],
            source="cost-ledger: " + "; ".join(f"{c.name}={c.source}" for c in self.components),
            verified=True,
        )


def measured_spread_price(
    year: int, session: str, quantile: Literal["median", "p90"] = "p90", path: Path = COST_MODEL_V2
) -> tuple[float, str]:
    """Tick spread (points) of ``year`` and ``session`` from the cost model v2, converted to price.

    Returns the one-way spread in price units and the measured sample size note. Raises ``KeyError``
    when that (year, session) was not measured: a missing measurement is an error, never 0.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["tick_spread_by_year_session"]:
        if row["y"] == year and row["session"] == session:
            return float(row[quantile]) * POINT_SIZE, f"n={row['n']} {quantile}"
    raise KeyError(f"no tick spread measured for {year} {session}")


def spread_component(
    year: int, session: str, quantile: Literal["median", "p90"] = "p90"
) -> CostComponent:
    """Round-trip spread: one spread is paid crossing in and out of the market at bid/ask."""
    one_way, note = measured_spread_price(year, session, quantile)
    return CostComponent(
        name="spread",
        value=one_way,
        source=f"cost_model_v2 tick spread ({note}), class D description, no outcome",
        measured_at=datetime(2026, 10, 11, 4, 48, tzinfo=UTC),
        relevance=f"{year} {session} ticks only; tick eras start 2021-10; bar spreads understate it before 2024",
        conversion=f"points x {POINT_SIZE} = price; one spread per round trip (entry at ask, exit at bid)",
        status=CostStatus.VERIFIED_MEASURED,
    )


def swap_component(
    direction: Literal["BUY", "SELL"], nights: int, read_at: datetime
) -> CostComponent:
    """Swap for ``nights`` rollovers, from the MT5 symbol_info reading (mode 1: points per lot per night).

    The reading changes (-76.05 on 2026-10-08, -69.25 on 2026-10-11 for longs), so it expires after
    seven days. The Wednesday triple is not modelled here: a caller that holds across a Wednesday
    must pass ``nights`` that already counts it.
    """
    points = 69.25 if direction == "BUY" else 4.2  # magnitudes: a swap COST in points per night
    return CostComponent(
        name="swap",
        value=points * POINT_SIZE * nights,
        source="MT5 symbol_info XAUUSD read-only reading (FTMO-Demo), swap_mode 1 = points",
        measured_at=read_at,
        relevance=f"{direction}, {nights} rollover night(s); valid for the week of the reading",
        conversion=f"{points} points x {POINT_SIZE} x {nights} nights; price units per 1.0 unit of gold",
        status=CostStatus.VERIFIED_BROKER_SPEC,
        max_age_days=7,
    )


def blocked_slippage() -> CostComponent:
    return CostComponent(
        name="slippage",
        value=None,
        source="no executed fills exist: PAPER fills at the quote, orders are forbidden",
        relevance="XAUUSD market orders",
        conversion="requested minus filled price, per fill, in price units",
        status=CostStatus.BLOCKED_EXTERNALLY,
        evidence_needed=(
            "N >= 30 broker-executed demo fills with requested and filled prices and times "
            "(owner authorization for demo execution is required to produce them)"
        ),
    )


def blocked_commission() -> CostComponent:
    return CostComponent(
        name="commission",
        value=None,
        source="not exposed by MT5 symbol_info; the project documents 0 as UNVERIFIED",
        relevance="the FTMO account type actually used",
        conversion="USD per lot per side divided by (contract size x lot) = price units per round trip",
        status=CostStatus.BLOCKED_EXTERNALLY,
        evidence_needed="the account's commission schedule (FTMO account-type terms or a closed demo deal's commission field)",
    )


def default_ledger(
    year: int, session: str, direction: Literal["BUY", "SELL"], nights: int, swap_read_at: datetime
) -> CostLedger:
    """The current honest ledger: spread and swap evidenced, slippage and commission blocked."""
    return CostLedger(
        components=(
            spread_component(year, session),
            blocked_slippage(),
            blocked_commission(),
            swap_component(direction, nights, swap_read_at),
        )
    )
