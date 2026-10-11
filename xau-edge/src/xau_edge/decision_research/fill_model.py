# ruff: noqa: E501 - these modules carry their selection/audit record as prose
"""Executable fill model (frozen): the next bar's open, crossed at the correct side of the spread.

Selection record (criteria fixed BEFORE any measurement; profitability, hit rates and returns were not
looked at and cannot be: this module receives no future price except the fill bar's own open):

    criteria (equal weight, each pass/fail): causality, broker realism, data availability over the
    development history, auditability, determinism, complexity.

    A. next executable bid/ask TICK after the actionable time
       causality PASS, realism PASS (best), availability FAIL (ticks exist only from 2021-10; the
       development history is 2011-2018), audit PASS, determinism PASS, complexity FAIL (tick store).
    B. next BAR OPEN, BUY at ask = open + spread, SELL at bid = open        <- CHOSEN
       causality PASS (the fill bar is strictly after ``actionable_at``), realism PASS (bid-based bar
       open plus a stated spread), availability PASS (bars exist for the whole history), audit PASS,
       determinism PASS, complexity PASS.
    C. a preregistered limit/retest fill
       causality PASS, realism FAIL (needs a fill-probability model and a miss rule), availability
       PASS, audit FAIL (extra free parameters), determinism FAIL (depends on later price), complexity FAIL.

B is chosen because it is the only option that is causal, deterministic and available across the
history. A stays the verification instrument wherever ticks exist (it is how the bar spread is
checked below). C is rejected for reintroducing parameters and a dependence on later prices.

What stays UNVERIFIED, and is reported as such rather than hidden: the bar's recorded spread is not the
tick spread (cost model v2, same-minute comparison: the bar median understates the tick median by
a ratio of 1.43-1.63 in 2021-2023 and about 1.04-1.10 in 2024-2025), and no tick history exists before
2021-10-01, so for the development years the multiplier that converts a bar spread to an executable
spread is an assumption. A fill whose spread multiplier is not evidenced is returned with
``verified=False`` and the authorization gate treats it as FILL_UNVERIFIED.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from math import isfinite
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from xau_edge.decision_research.cost_ledger import COST_MODEL_V2, POINT_SIZE


class Fill(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    side: Literal["BUY", "SELL"]
    bar_index: int
    price: float
    spread_price: float
    basis: Literal["NEXT_BAR_OPEN_PLUS_ASK_SPREAD", "NEXT_BAR_OPEN_BID"]
    verified: bool
    unverified_reason: str | None = None


def tick_adverse(price: float, side: Literal["BUY", "SELL"], tick_size: float) -> float:
    """Round against the trader: a BUY fill up, a SELL fill down."""
    tick = Decimal(str(tick_size))
    mode = ROUND_CEILING if side == "BUY" else ROUND_FLOOR
    return float((Decimal(str(price)) / tick).to_integral_value(rounding=mode) * tick)


def next_bar_fill(
    side: Literal["BUY", "SELL"],
    opens: Sequence[float],
    spread_points: Sequence[float],
    actionable_at: int,
    *,
    spread_multiplier: float | None,
    tick_size: float = POINT_SIZE,
) -> Fill | None:
    """The fill at bar ``actionable_at + 1``; ``None`` when no such bar exists or its data is unusable.

    ``spread_multiplier`` converts the bar's recorded spread into an executable spread. ``None`` means
    "no evidence for that conversion": the fill is still computed from the recorded spread (so the
    geometry can be reported) but is flagged unverified and cannot authorize anything.
    """
    i = actionable_at + 1
    if actionable_at < 0 or i >= len(opens) or i >= len(spread_points):
        return None
    open_px, spread_pts = float(opens[i]), float(spread_points[i])
    if not (isfinite(open_px) and isfinite(spread_pts)) or spread_pts <= 0 or tick_size <= 0:
        return None
    if spread_multiplier is not None and (
        not isfinite(spread_multiplier) or spread_multiplier < 1.0
    ):
        raise ValueError("an executable spread is never narrower than the recorded bar spread")
    mult = 1.0 if spread_multiplier is None else spread_multiplier
    spread_price = spread_pts * POINT_SIZE * mult
    if side == "BUY":
        price, basis = open_px + spread_price, "NEXT_BAR_OPEN_PLUS_ASK_SPREAD"
    else:
        price, basis = open_px, "NEXT_BAR_OPEN_BID"
    reason = (
        None
        if spread_multiplier is not None
        else "bar spread to executable spread is not evidenced"
    )
    return Fill(
        side=side,
        bar_index=i,
        price=tick_adverse(price, side, tick_size),
        spread_price=spread_price,
        basis=basis,
        verified=spread_multiplier is not None,
        unverified_reason=reason,
    )


def evidenced_spread_multiplier(year: int, path: Path = COST_MODEL_V2) -> float | None:
    """Bar-to-tick spread ratio (p90, conservative) measured for ``year``; ``None`` when never measured.

    Only years with a same-minute tick comparison are evidenced. The development years have no tick
    history, so they return ``None`` and every fill there stays unverified.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data["tick_vs_bar_same_minute"]["by_year"]:
        if row["y"] == year:
            return max(1.0, float(row["ratio_p90"]))
    return None
