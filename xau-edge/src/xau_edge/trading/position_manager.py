"""Deterministic position manager: break-even, trailing, time exit, invalidation, emergencies.

``evaluate`` is a pure function of the position, the context and the configuration: the same inputs
give the same actions, so paper, replay and demo behave identically and every action can be
journalled with its reason. Rules:

* The stop is only ever TIGHTENED (never loosened) and moves through three explicit stages:
  INITIAL -> BREAK_EVEN -> TRAILING. Break-even and trailing are OFF by default: they are enabled
  only by explicit configuration, after evidence, never automatically.
* A close request always wins over a stop modification, and emergencies (kill switch, daily loss
  guard, equity floor) win over everything. Every close carries an ``exit_reason``.
* A stop or target reached inside the evaluated bar is reported as a close; when both are reached in
  one bar the STOP is assumed first (pessimistic), like the research barrier labels.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SlStage(StrEnum):
    INITIAL = "INITIAL"
    BREAK_EVEN = "BREAK_EVEN"
    TRAILING = "TRAILING"


class TrailModel(StrEnum):
    NONE = "NONE"
    ATR = "ATR"
    SWING = "SWING"
    CHANDELIER = "CHANDELIER"


class ExitReason(StrEnum):
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TIME_EXPIRY = "TIME_EXPIRY"
    INVALIDATION = "INVALIDATION"
    OPPOSITE_SIGNAL = "OPPOSITE_SIGNAL"
    SPREAD_EMERGENCY = "SPREAD_EMERGENCY"
    DAILY_LOSS_GUARD = "DAILY_LOSS_GUARD"
    KILL_SWITCH = "KILL_SWITCH"
    EQUITY_FLOOR = "EQUITY_FLOOR"
    FORCED_FLAT = "FORCED_FLAT"


class ManagerConfig(BaseModel):
    """Management rules (all optional rules default to OFF)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    break_even_enabled: bool = False
    break_even_at_r: float = Field(default=1.0, gt=0)
    break_even_buffer_r: float = Field(default=0.05, ge=0)
    """Where the stop goes at break-even, in R beyond the entry (covers the round-trip cost)."""
    trail_model: TrailModel = TrailModel.NONE
    trail_start_r: float = Field(default=1.5, gt=0)
    trail_atr_k: float = Field(default=2.0, gt=0)
    max_hold_minutes: int = Field(default=120, ge=1)
    close_on_invalidation: bool = True
    close_on_opposite_signal: bool = False
    spread_emergency_points: float | None = None


@dataclass(frozen=True)
class PositionState:
    """One open position as the manager sees it."""

    ticket: str
    direction: int  # +1 long, -1 short
    lots: float
    entry: float
    initial_sl: float
    sl: float
    tp: float
    opened_at: datetime
    stage: SlStage = SlStage.INITIAL

    @property
    def risk(self) -> float:
        """Initial risk in price units (1R)."""
        return abs(self.entry - self.initial_sl)


@dataclass(frozen=True)
class ManagerContext:
    """The market and the guards at the evaluation time."""

    now: datetime
    bar_high: float
    bar_low: float
    last_price: float
    atr: float | None = None
    swing_low: float | None = None
    swing_high: float | None = None
    highest_since_entry: float | None = None
    lowest_since_entry: float | None = None
    spread_points: float | None = None
    invalidated: bool = False
    opposite_signal: bool = False
    kill_switch: bool = False
    daily_loss_guard: bool = False
    equity_floor_hit: bool = False
    must_flat_by: datetime | None = None


@dataclass(frozen=True)
class Action:
    """What to do: HOLD, MODIFY_SL (``new_sl``) or CLOSE (``reason``)."""

    kind: str
    reason: str
    new_sl: float | None = None
    stage: SlStage | None = None


HOLD = Action("HOLD", "no change")


def _close(reason: ExitReason) -> Action:
    return Action("CLOSE", reason.value)


def _tighter(direction: int, current: float, candidate: float) -> bool:
    return candidate > current if direction > 0 else candidate < current


def _r_multiple(pos: PositionState, price: float) -> float:
    return pos.direction * (price - pos.entry) / pos.risk if pos.risk > 0 else 0.0


def evaluate(  # noqa: PLR0911, PLR0912 - one rule per exit or management reason
    pos: PositionState, ctx: ManagerContext, cfg: ManagerConfig
) -> Action:
    """The single next action for ``pos`` (emergencies first, then exits, then stop management)."""
    if ctx.kill_switch:
        return _close(ExitReason.KILL_SWITCH)
    if ctx.daily_loss_guard:
        return _close(ExitReason.DAILY_LOSS_GUARD)
    if ctx.equity_floor_hit:
        return _close(ExitReason.EQUITY_FLOOR)
    # price levels first: the stop is assumed hit before the target inside one bar
    if pos.direction > 0:
        stop_hit, target_hit = ctx.bar_low <= pos.sl, ctx.bar_high >= pos.tp
    else:
        stop_hit, target_hit = ctx.bar_high >= pos.sl, ctx.bar_low <= pos.tp
    if stop_hit:
        return _close(ExitReason.STOP_LOSS)
    if target_hit:
        return _close(ExitReason.TAKE_PROFIT)
    if ctx.must_flat_by is not None and ctx.now >= ctx.must_flat_by:
        return _close(ExitReason.FORCED_FLAT)
    if ctx.now - pos.opened_at >= timedelta(minutes=cfg.max_hold_minutes):
        return _close(ExitReason.TIME_EXPIRY)
    if cfg.close_on_invalidation and ctx.invalidated:
        return _close(ExitReason.INVALIDATION)
    if cfg.close_on_opposite_signal and ctx.opposite_signal:
        return _close(ExitReason.OPPOSITE_SIGNAL)
    if (
        cfg.spread_emergency_points is not None
        and ctx.spread_points is not None
        and ctx.spread_points >= cfg.spread_emergency_points
    ):
        return _close(ExitReason.SPREAD_EMERGENCY)
    favourable = ctx.bar_high if pos.direction > 0 else ctx.bar_low
    reached_r = _r_multiple(pos, favourable)
    candidate: float | None = None
    stage = pos.stage
    reason = ""
    if cfg.break_even_enabled and stage is SlStage.INITIAL and reached_r >= cfg.break_even_at_r:
        candidate = pos.entry + pos.direction * cfg.break_even_buffer_r * pos.risk
        stage, reason = SlStage.BREAK_EVEN, "break-even"
    if cfg.trail_model is not TrailModel.NONE and reached_r >= cfg.trail_start_r:
        trail = _trail_level(pos, ctx, cfg)
        if trail is not None and (candidate is None or _tighter(pos.direction, candidate, trail)):
            candidate, stage, reason = trail, SlStage.TRAILING, f"trail {cfg.trail_model.value}"
    if candidate is not None and _tighter(pos.direction, pos.sl, candidate):
        return Action("MODIFY_SL", reason, new_sl=candidate, stage=stage)
    return HOLD


def _trail_level(  # noqa: PLR0911
    pos: PositionState, ctx: ManagerContext, cfg: ManagerConfig
) -> float | None:
    if cfg.trail_model is TrailModel.ATR:
        if ctx.atr is None or ctx.atr <= 0:
            return None
        return ctx.last_price - pos.direction * cfg.trail_atr_k * ctx.atr
    if cfg.trail_model is TrailModel.SWING:
        level = ctx.swing_low if pos.direction > 0 else ctx.swing_high
        return level
    if cfg.trail_model is TrailModel.CHANDELIER:
        if ctx.atr is None or ctx.atr <= 0:
            return None
        if pos.direction > 0 and ctx.highest_since_entry is not None:
            return ctx.highest_since_entry - cfg.trail_atr_k * ctx.atr
        if pos.direction < 0 and ctx.lowest_since_entry is not None:
            return ctx.lowest_since_entry + cfg.trail_atr_k * ctx.atr
    return None


def apply(pos: PositionState, action: Action) -> PositionState:
    """The position after a MODIFY_SL action (other actions leave it unchanged)."""
    if action.kind != "MODIFY_SL" or action.new_sl is None:
        return pos
    if not _tighter(pos.direction, pos.sl, action.new_sl):
        return pos  # the stop never moves the wrong way, whatever the caller asks
    return replace(pos, sl=action.new_sl, stage=action.stage or pos.stage)
