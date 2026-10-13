"""Stop-loss and take-profit engines (trading core sections 14 and 15).

The stop is never a random dollar amount: it comes from market structure (beyond the last confirmed
swing), from the ATR, or from a hybrid that takes the larger of the two but refuses a stop wider
than a maximum number of ATR. Parameters here are research parameters, not magic constants: they
are fixed in configuration before results are looked at and are never tuned on profit.
Targets are an R multiple, capped by the next opposing structure level, and always judged after the
spread: a payoff that only works at zero cost is refused.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StopModel(StrEnum):
    STRUCTURE = "STRUCTURE"
    ATR = "ATR"
    HYBRID = "HYBRID"


class LevelConfig(BaseModel):
    """Stop and target parameters (fixed in advance)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stop_model: StopModel = StopModel.HYBRID
    atr_k: float = Field(default=1.25, gt=0)
    """ATR multiple for the ATR model and the minimum distance of the hybrid."""
    structure_buffer_atr: float = Field(default=0.1, ge=0)
    max_stop_atr: float = Field(default=3.0, gt=0)
    """A stop wider than this many ATR is refused (the risk would not be worth the setup)."""
    r_multiple: float = Field(default=2.0, gt=0)
    tp2_r_multiple: float | None = 3.0
    min_net_rr: float = Field(default=1.5, gt=0)
    structure_target_buffer_atr: float = Field(default=0.1, ge=0)


@dataclass(frozen=True)
class Stop:
    """A stop level and how it was derived."""

    price: float
    distance: float
    model: str


@dataclass(frozen=True)
class Targets:
    """Take-profit levels and the payoff they imply (net of the spread)."""

    tp1: float
    tp2: float | None
    gross_rr: float
    net_rr: float
    required_win_rate: float
    capped_by_structure: bool


def compute_stop(
    direction: int, entry: float, swing_level: float | None, atr: float, cfg: LevelConfig
) -> Stop | None:
    """The stop for ``direction`` (+1 buy, -1 sell), or None when no acceptable stop exists."""
    if direction not in (-1, 1) or atr <= 0 or entry <= 0:
        return None
    atr_distance = cfg.atr_k * atr
    structure_distance: float | None = None
    if swing_level is not None:
        raw = (entry - swing_level) if direction > 0 else (swing_level - entry)
        if raw > 0:
            structure_distance = raw + cfg.structure_buffer_atr * atr
    if cfg.stop_model is StopModel.ATR:
        distance, model = atr_distance, StopModel.ATR.value
    elif cfg.stop_model is StopModel.STRUCTURE:
        if structure_distance is None:
            return None
        distance, model = structure_distance, StopModel.STRUCTURE.value
    else:
        distance = max(structure_distance or 0.0, atr_distance)
        model = StopModel.HYBRID.value
    if distance <= 0 or distance > cfg.max_stop_atr * atr:
        return None
    return Stop(price=entry - direction * distance, distance=distance, model=model)


def compute_targets(
    direction: int,
    entry: float,
    stop: Stop,
    cfg: LevelConfig,
    *,
    spread: float,
    atr: float,
    opposing_level: float | None = None,
) -> Targets | None:
    """TP1 (and optionally TP2), capped by the next opposing level, with the net payoff.

    ``spread`` is in price units. ``net_rr = (reward - spread) / (risk + spread)``. Returns None
    when the net payoff is below ``min_net_rr`` (the caller turns that into RR_TOO_LOW).
    """
    risk = stop.distance
    reward = cfg.r_multiple * risk
    capped = False
    if opposing_level is not None:
        room = (opposing_level - entry) if direction > 0 else (entry - opposing_level)
        room -= cfg.structure_target_buffer_atr * atr
        if 0 < room < reward:
            reward, capped = room, True
        elif room <= 0:
            return None  # the opposing level is already at or beyond the entry
    gross = reward / risk
    net = (reward - spread) / (risk + spread)
    if net < cfg.min_net_rr:
        return None
    tp2 = None
    if cfg.tp2_r_multiple is not None and not capped:
        tp2 = entry + direction * cfg.tp2_r_multiple * risk
    return Targets(
        tp1=entry + direction * reward,
        tp2=tp2,
        gross_rr=gross,
        net_rr=net,
        required_win_rate=1.0 / (1.0 + net),
        capped_by_structure=capped,
    )
