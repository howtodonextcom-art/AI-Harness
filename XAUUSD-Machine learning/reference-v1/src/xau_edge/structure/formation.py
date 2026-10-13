"""Formation lifecycle of a double top / double bottom: where a pattern is in its structure.

States (structural recognition, never a forecast):

    POSSIBLE           peak A and valley V are confirmed and big enough            progress 25
    DEVELOPING         a later close is back within the equal-peak band of A       progress 50
    NEAR_CONFIRMATION  the second peak B is confirmed and equal to A               progress 75
    CONFIRMED          a close beyond the neckline (this is also ACTIONABLE)       progress 100
    INVALIDATED        the structure failed first (reason recorded)                progress kept

``formation_progress`` is a milestone count (0, 25, 50, 75, 100). It is NOT a win probability and
NOT a probability that the pattern completes; treating either as such is a misuse. Every transition
happens on the bar whose data proves it, using closed bars and confirmed pivots only, so a lifecycle
cut at any bar equals the lifecycle computed from the data up to that bar (prefix invariance).
CONFIRMED lifecycles coincide exactly with ``reversal.detect_reversals`` double detections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike
from pydantic import BaseModel, ConfigDict

from xau_edge.features.indicators import as_hlc, atr
from xau_edge.structure.detection import PatternPoint, PatternType, make_pattern_id
from xau_edge.structure.pivots import Pivot, alternate, confirmed_pivots
from xau_edge.structure.reversal import ATR_PERIOD, ReversalConfig, _arm_double, _initial_scan

Floats = np.ndarray  # type: ignore[type-arg,unused-ignore]


class FormationState(StrEnum):
    POSSIBLE = "POSSIBLE"
    DEVELOPING = "DEVELOPING"
    NEAR_CONFIRMATION = "NEAR_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    INVALIDATED = "INVALIDATED"


PROGRESS = {
    FormationState.POSSIBLE: 25,
    FormationState.DEVELOPING: 50,
    FormationState.NEAR_CONFIRMATION: 75,
    FormationState.CONFIRMED: 100,
}
_OPEN = (FormationState.POSSIBLE, FormationState.DEVELOPING, FormationState.NEAR_CONFIRMATION)


class FormationEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bar: int  # the bar whose data proves the transition
    state: FormationState
    formation_progress: int  # milestone count, not a probability
    reason: str = ""


class FormationTrack(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    pattern_id: str  # stable for the whole life: derived from A and V only
    detection_id: str | None = None  # the id the detector gives the finished pattern (A, V, B)
    pattern_type: PatternType
    bias: Literal["LONG", "SHORT"]
    timeframe: str | None = None
    points: tuple[PatternPoint, ...]
    started_at: int  # bar where the first point formed
    last_pattern_point_at: int  # bar where the latest point formed
    events: tuple[FormationEvent, ...]
    state: FormationState
    formation_progress: int
    confirmed_at: int | None = None
    actionable_at: int | None = None
    invalidated_at: int | None = None
    invalidation_reason: str | None = None
    evidence_sources: tuple[str, ...] = ()
    progress_note: str = "FORMATION_PROGRESS is a structural milestone, not a win probability"


@dataclass
class _Live:
    a: Pivot
    v: Pivot
    b: Pivot | None = None
    state: FormationState = FormationState.POSSIBLE
    events: list[FormationEvent] = field(default_factory=list)
    peak: float = 0.0
    geometry_known_at: int = 0
    pending_fail: bool = False  # a weak second peak was seen; a higher peak may still replace it

    def move(self, bar: int, state: FormationState, reason: str = "") -> None:
        if self.events and self.events[-1].state == state:
            return
        previous = self.events[-1].formation_progress if self.events else 0
        progress = PROGRESS.get(state, previous)
        self.events.append(
            FormationEvent(bar=bar, state=state, formation_progress=progress, reason=reason)
        )
        self.state = state


def _split(live: list[_Live]) -> tuple[list[_Live], list[_Live]]:
    keep = [t for t in live if t.state is not FormationState.INVALIDATED]
    return keep, [t for t in live if t.state is FormationState.INVALIDATED]


def _retire_superseded(live: list[_Live], replaced: Pivot, bar: int) -> None:
    """A more extreme pivot of the same kind replaced ``replaced``: what leaned on it is redone."""
    for t in live:
        if t.state is FormationState.CONFIRMED:
            continue
        if replaced == t.v:  # a deeper valley restarts the structure
            t.move(bar, FormationState.INVALIDATED, "VALLEY_SUPERSEDED")
        elif replaced == t.b:
            t.b, t.pending_fail = None, False  # re-evaluated with the new peak


def _start(
    history: list[Pivot], pv: Pivot, bar: int, atr_now: float, cfg: ReversalConfig
) -> _Live | None:
    a = history[-2]
    height = a.price - pv.price
    if (
        pv.bar - a.bar < cfg.min_bars_between
        or height <= 0
        or height < cfg.min_height_atr * atr_now
    ):
        return None
    track = _Live(a, pv, peak=a.price, geometry_known_at=bar)
    track.move(bar, FormationState.POSSIBLE)
    return track


@dataclass(frozen=True)
class _Bar:
    """What is known at the bar a pivot is confirmed."""

    bar: int
    atr: float
    high: Floats
    close: Floats


def _arm(track: _Live, pv: Pivot, armed: object, known: _Bar) -> None:
    peak = armed.peak  # type: ignore[attr-defined]
    track.b, track.pending_fail = pv, False
    track.peak, track.geometry_known_at = peak, known.bar
    track.move(known.bar, FormationState.NEAR_CONFIRMATION)
    verdict = _initial_scan(armed, known.close, pv.bar + 1, known.bar)  # type: ignore[arg-type]
    if verdict is not None and verdict < 0:
        track.move(known.bar, FormationState.INVALIDATED, "PEAK_EXCEEDED")
    elif verdict is not None:
        track.move(known.bar, FormationState.CONFIRMED, f"trigger_bar={verdict}")


def _second_peak(
    live: list[_Live], history: list[Pivot], pv: Pivot, known: _Bar, cfg: ReversalConfig
) -> None:
    """A new peak became known: arm the structures waiting for a second peak.

    A structure that was too small at its valley (judged with the ATR of that moment) but qualifies
    now starts here, at NEAR_CONFIRMATION: its earlier states were never knowable, so none is
    invented.
    """
    a, v = history[-3], history[-2]
    armed = _arm_double(history, known.bar, known.high, known.atr, cfg)
    matched = False
    for t in live:
        if (t.a, t.v) != (a, v) or t.state not in _OPEN:
            continue
        matched = True
        if armed is None:
            t.b, t.pending_fail = pv, True  # a higher peak may still replace this one
        else:
            _arm(t, pv, armed, known)
    if not matched and armed is not None:
        late = _Live(a, v, peak=a.price, geometry_known_at=known.bar)
        _arm(late, pv, armed, known)
        live.append(late)


def _advance(live: list[_Live], bar: int, close: Floats, cfg: ReversalConfig) -> None:
    """Bar ``bar`` for the structures that were already live (closes only)."""
    for t in live:
        if t.state in (FormationState.CONFIRMED, FormationState.INVALIDATED):
            continue
        neck = t.v.price
        if t.state is FormationState.NEAR_CONFIRMATION:
            if bar > t.geometry_known_at + cfg.max_break_bars:
                t.move(bar, FormationState.INVALIDATED, "BREAK_WINDOW_EXPIRED")
            elif close[bar] > t.peak:
                t.move(bar, FormationState.INVALIDATED, "PEAK_EXCEEDED")
            elif close[bar] < neck:
                t.move(bar, FormationState.CONFIRMED, f"trigger_bar={bar}")
            continue
        low_band = cfg.equal_tolerance * (t.a.price - t.v.price)
        # B may stand above A by tol/(1-tol) of the A-V height (the detector's test uses max(A, B))
        up_band = low_band / (1.0 - cfg.equal_tolerance) if cfg.equal_tolerance < 1.0 else low_band
        if bar - t.a.bar > cfg.max_pattern_bars:
            t.move(bar, FormationState.INVALIDATED, "SPAN_EXPIRED")
        elif close[bar] > t.a.price + up_band:
            t.move(bar, FormationState.INVALIDATED, "PEAK_BAND_EXCEEDED")
        elif close[bar] < neck:
            t.move(bar, FormationState.INVALIDATED, "NECKLINE_BROKEN_FIRST")
        elif t.state is FormationState.POSSIBLE and close[bar] >= t.a.price - low_band:
            t.move(bar, FormationState.DEVELOPING)


def _scan_tops(
    h: Floats, lo: Floats, c: Floats, atr_arr: Floats, cfg: ReversalConfig
) -> list[_Live]:
    pivots = confirmed_pivots(h, lo, c, left=cfg.pivot_left, right=cfg.pivot_right)
    history: list[Pivot] = []
    live: list[_Live] = []
    done: list[_Live] = []
    pi = 0
    for j in range(c.size):
        fresh: list[_Live] = []
        while pi < len(pivots) and pivots[pi].confirmed_at == j:
            pv = pivots[pi]
            pi += 1
            replaced = alternate(history, pv)
            if replaced is not None:
                _retire_superseded(live, replaced, j)
            if pv.kind == "L":  # a valley after a weak second peak makes that failure final
                for t in live:
                    if t.pending_fail and t.b is not None and pv.bar > t.b.bar:
                        t.move(j, FormationState.INVALIDATED, "SECOND_PEAK_NOT_EQUAL")
            if history[-1] is pv and not np.isnan(atr_arr[j]):
                if pv.kind == "L" and len(history) >= 2 and history[-2].kind == "H":
                    started = _start(history, pv, j, float(atr_arr[j]), cfg)
                    if started is not None:
                        fresh.append(started)
                if pv.kind == "H" and len(history) >= 3:
                    _second_peak(live, history, pv, _Bar(j, float(atr_arr[j]), h, c), cfg)
            live, retired = _split(live)
            done.extend(retired)
        _advance(live, j, c, cfg)
        live, retired = _split(live)
        done.extend(retired)
        live.extend(fresh)
    return done + live


def _to_track(t: _Live, mirrored: bool, timeframe: str | None) -> FormationTrack:
    sign = -1.0 if mirrored else 1.0
    pts = [("A", t.a), ("V", t.v)] + ([("B", t.b)] if t.b is not None else [])
    points = tuple(
        PatternPoint(label=lab, bar=p.bar, price=sign * p.price, confirmed_at=p.confirmed_at)
        for lab, p in pts
    )
    ptype: PatternType = "DOUBLE_BOTTOM" if mirrored else "DOUBLE_TOP"
    confirmed = next((e.bar for e in t.events if e.state is FormationState.CONFIRMED), None)
    invalid = next((e for e in t.events if e.state is FormationState.INVALIDATED), None)
    progress = max((e.formation_progress for e in t.events), default=0)
    return FormationTrack(
        pattern_id=make_pattern_id(ptype, points[:2]),
        detection_id=make_pattern_id(ptype, points) if t.b is not None else None,
        pattern_type=ptype,
        bias="LONG" if mirrored else "SHORT",
        timeframe=timeframe,
        points=points,
        started_at=t.a.bar,
        last_pattern_point_at=max(p.bar for _, p in pts),
        events=tuple(t.events),
        state=t.events[-1].state,
        formation_progress=progress,
        confirmed_at=confirmed,
        actionable_at=confirmed,
        invalidated_at=invalid.bar if invalid else None,
        invalidation_reason=invalid.reason if invalid else None,
    )


def track_double_formations(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    config: ReversalConfig | None = None,
    timeframe: str | None = None,
) -> list[FormationTrack]:
    """Every double top/bottom structure that reached at least POSSIBLE, with its lifecycle."""
    cfg = config or ReversalConfig()
    h, lo, c = as_hlc(high, low, close)
    atr_arr = atr(h, lo, c, ATR_PERIOD)
    tracks: list[FormationTrack] = []
    for mirrored, hh, ll, cc in ((False, h, lo, c), (True, -lo, -h, -c)):
        tracks.extend(
            _to_track(t, mirrored, timeframe) for t in _scan_tops(hh, ll, cc, atr_arr, cfg)
        )
    tracks.sort(key=lambda t: (t.events[0].bar, t.pattern_id))
    return tracks


def lifecycle_violations(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    cuts: list[int],
    config: ReversalConfig | None = None,
) -> list[str]:
    """Prefix invariance of the lifecycle: events up to bar t must not depend on bars after t."""
    h, lo, c = (np.asarray(x, dtype=np.float64) for x in (high, low, close))

    def flat(tracks: list[FormationTrack], t: int) -> set[tuple[str, str, int]]:
        return {
            (k.pattern_id, e.state.value, e.bar) for k in tracks for e in k.events if e.bar <= t
        }

    full = track_double_formations(h, lo, c, config)
    problems: list[str] = []
    for t in cuts:
        prefix = track_double_formations(h[: t + 1], lo[: t + 1], c[: t + 1], config)
        mine, theirs = flat(prefix, t), flat(full, t)
        if mine != theirs:
            problems.append(
                f"cut {t}: {len(mine ^ theirs)} events differ, e.g. {sorted(mine ^ theirs)[:2]}"
            )
    return problems
