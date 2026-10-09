"""Streaming (live-style) implementation of the H07/H08 sweep events, for research-to-live parity.

Bars arrive ONE AT A TIME and the detector only ever sees the past. The batch detector in
``events.py`` and this one must produce IDENTICAL decisions on the same closed bars; any mismatch
is a blocker (``tests/unit/research_v2/test_parity.py``). The rules are the pre-registered ones:
first breach per level per scope, reject = a close back inside by eps x ATR within 3 bars
(breach bar included), accept = bar b+1 closes beyond by eps x ATR and bars b+2..b+4 close
outside, no data gap over 90 minutes, clock-unsafe days excluded.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

M_BARS = 3
MIN_DAY_BARS = 12
ASIA_END_HOUR = 7
MIN_ASIA_BARS = 5
ATR_PERIOD = 14
MAX_GAP_US = 90 * 60 * 1_000_000


@dataclass(frozen=True)
class StreamBar:
    """One closed bar with the keys the detector needs (all derived from the bar's own time)."""

    t: int
    o: float
    h: float
    low: float
    c: float
    day: int
    utc_date: int
    utc_hour: int
    unsafe_day: bool


@dataclass(frozen=True)
class StreamEvent:
    """A decision: the bar index at which it is made and the direction."""

    index: int
    direction: int
    level: str


@dataclass
class _Pending:
    name: str
    level: float
    side: int
    breach: int
    breach_t: int
    last_t: int


@dataclass
class StreamingSweep:
    """Incremental detector for one (level set, mode, eps) variant."""

    level_set: str
    mode: str
    eps: float
    events_unsafe: int = 0
    _n: int = 0
    _prev: StreamBar | None = None
    _tr: list[float] = field(default_factory=list)
    _atr: float = math.nan
    _day_key: int | None = None
    _day_hi: float = -math.inf
    _day_lo: float = math.inf
    _day_n: int = 0
    _day_unsafe: bool = False
    _pd: tuple[float, float, bool] | None = None
    _utc_date: int | None = None
    _asia_hi: float = -math.inf
    _asia_lo: float = math.inf
    _asia_n: int = 0
    _asia_unsafe: bool = False
    _done: set[tuple[str, int]] = field(default_factory=set)
    _pending: list[_Pending] = field(default_factory=list)
    _history: list[tuple[float, float]] = field(default_factory=list)

    def _update_atr(self, bar: StreamBar) -> None:
        if self._prev is None:
            self._tr.append(0.0)
            self._atr = math.nan
            return
        prev_c = self._prev.c
        tr = max(bar.h - bar.low, abs(bar.h - prev_c), abs(bar.low - prev_c))
        self._tr.append(tr)
        n = len(self._tr)
        if n - 1 == ATR_PERIOD:
            self._atr = sum(self._tr[1 : ATR_PERIOD + 1]) / ATR_PERIOD
        elif n - 1 > ATR_PERIOD:
            self._atr = (self._atr * (ATR_PERIOD - 1) + tr) / ATR_PERIOD
        else:
            self._atr = math.nan

    def _roll_scopes(self, bar: StreamBar) -> None:
        if self._day_key is not None and bar.day != self._day_key:
            if self._day_n >= MIN_DAY_BARS:
                self._pd = (self._day_hi, self._day_lo, self._day_unsafe)
            self._day_hi, self._day_lo, self._day_n, self._day_unsafe = (
                -math.inf,
                math.inf,
                0,
                False,
            )
        self._day_key = bar.day
        if self._utc_date is not None and bar.utc_date != self._utc_date:
            self._asia_hi, self._asia_lo = -math.inf, math.inf
            self._asia_n, self._asia_unsafe = 0, False
        self._utc_date = bar.utc_date

    def _levels(self, bar: StreamBar) -> tuple[tuple[str, float, bool, int], ...]:
        """The two levels (high, low) known BEFORE this bar's data is folded in."""
        if self.level_set == "PD":
            if self._pd is None:
                return ()
            hi, lo, un = self._pd
            return (("PDH", hi, un, bar.day), ("PDL", lo, un, bar.day))
        if bar.utc_hour < ASIA_END_HOUR or self._asia_n < MIN_ASIA_BARS:
            return ()
        hi, lo, un = self._asia_hi, self._asia_lo, self._asia_unsafe
        return (("ASIAH", hi, un, bar.utc_date), ("ASIAL", lo, un, bar.utc_date))

    def _fold(self, bar: StreamBar) -> None:
        self._day_hi, self._day_lo = max(self._day_hi, bar.h), min(self._day_lo, bar.low)
        self._day_n += 1
        self._day_unsafe = self._day_unsafe or bar.unsafe_day
        if bar.utc_hour < ASIA_END_HOUR:
            self._asia_hi, self._asia_lo = max(self._asia_hi, bar.h), min(self._asia_lo, bar.low)
            self._asia_n += 1
            self._asia_unsafe = self._asia_unsafe or bar.unsafe_day

    def step(self, bar: StreamBar) -> list[StreamEvent]:  # noqa: PLR0912
        """Consume one closed bar; return the decisions it completes (up-side first)."""
        index = self._n
        self._n += 1
        gap = self._prev is not None and bar.t - self._prev.t > MAX_GAP_US
        self._update_atr(bar)
        self._roll_scopes(bar)
        out: list[StreamEvent] = []
        # 1. resolve pending events with this bar
        still: list[_Pending] = []
        up: list[_Pending] = []
        down: list[_Pending] = []
        for p in self._pending:
            if gap:
                continue
            k = index - p.breach
            hit = self._resolve(p, bar, k)
            if hit == "emit":
                (up if p.side > 0 else down).append(p)
            elif hit == "wait":
                still.append(p)
        self._pending = still
        for p in up + down:
            if bar.unsafe_day:
                self.events_unsafe += 1
                continue
            direction = -p.side if self.mode == "reject" else p.side
            out.append(StreamEvent(index, direction, p.name))
        # 2. new breaches against the levels known before this bar
        for name, level, lvl_unsafe, scope in self._levels(bar):
            side = 1 if name.endswith("H") else -1
            if not math.isfinite(level) or (name, scope) in self._done:
                continue
            poked = bar.h > level if side > 0 else bar.low < level
            if not poked:
                continue
            self._done.add((name, scope))
            if bar.unsafe_day or lvl_unsafe:
                self.events_unsafe += 1
                continue
            pend = _Pending(name, level, side, index, bar.t, bar.t)
            if self.mode == "reject":
                verdict = self._resolve(pend, bar, 0)
                if verdict == "emit":
                    direction = -side
                    out.append(StreamEvent(index, direction, name))
                elif verdict == "wait":
                    self._pending.append(pend)
            else:
                self._pending.append(pend)
        # keep the stream ordered like the batch detector: up-side before down-side per bar
        out.sort(key=lambda e: (e.index, 0 if e.level.endswith("H") else 1))
        self._fold(bar)
        self._prev = bar
        self._history.append((bar.h, bar.low))
        return out

    def _resolve(self, p: _Pending, bar: StreamBar, k: int) -> str:  # noqa: PLR0911
        """emit, wait or drop for pending ``p`` at ``k`` bars after the breach bar."""
        atr = self._atr
        if self.mode == "reject":
            if not math.isfinite(atr):
                return "drop"
            inside = (
                bar.c < p.level - self.eps * atr if p.side > 0 else bar.c > p.level + self.eps * atr
            )
            if inside:
                return "emit"
            return "wait" if k < M_BARS - 1 else "drop"
        if k == 0:
            return "wait"
        if k == 1:
            if not math.isfinite(atr):
                return "drop"
            ok = (
                bar.c > p.level + self.eps * atr if p.side > 0 else bar.c < p.level - self.eps * atr
            )
            return "wait" if ok else "drop"
        outside = bar.c > p.level if p.side > 0 else bar.c < p.level
        if not outside:
            return "drop"
        return "emit" if k == M_BARS + 1 else "wait"


def replay_digest(events: list[StreamEvent]) -> str:
    """Deterministic fingerprint of a decision sequence (canonical JSON, SHA-256).

    Two replays of the same closed bars must give the same digest; a recorded digest next to a
    prospective signal journal lets a later replay prove it reproduced the same decisions.
    """
    from xau_edge.integrity.canonical import canonical_hash  # noqa: PLC0415 - keep import light

    return canonical_hash([[e.index, e.direction, e.level] for e in events])
