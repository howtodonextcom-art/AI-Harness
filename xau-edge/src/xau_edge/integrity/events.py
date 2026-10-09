"""Causal event state machine for level breaches (roadmap sections 17 and 40).

Input is a stream of CLOSED bars, one at a time. A breach of a level that was complete before the
bar opened starts as BREACH, waits as PENDING for ``m`` bars, and resolves to ACCEPTED, REJECTED or
(at the end of data) UNRESOLVED. An event can only be classified from bars up to and including the
bar that resolves it, so

    information_available_at <= decision_time < earliest_entry_time

holds by construction. ``step`` never looks ahead: feeding a prefix of a series gives exactly the
prefix of the events (tested with truncation and future-garbage properties).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum


class EventState(StrEnum):
    """Lifecycle of a breach."""

    BREACH = "BREACH"
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True)
class Bar:
    """A closed bar. ``close_time`` is when the bar's information became available."""

    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float

    def __post_init__(self) -> None:
        if self.close_time <= self.open_time or self.high < self.low:
            msg = "malformed bar"
            raise ValueError(msg)
        if not (self.low <= min(self.open, self.close) and max(self.open, self.close) <= self.high):
            msg = "bar open/close outside its high/low"
            raise ValueError(msg)


@dataclass(frozen=True)
class LevelEvent:
    """A resolved (or unresolved) breach with the three timestamps that keep it causal."""

    level_name: str
    level: float
    side: str  # "UP" breaches a high, "DOWN" breaches a low
    state: EventState
    breach_time: datetime
    detected_at: datetime
    confirmation_available_at: datetime
    decision_time: datetime
    earliest_entry_time: datetime
    bars_waited: int

    def is_causal(self) -> bool:
        """The ordering invariant of roadmap section 17."""
        return (
            self.detected_at <= self.confirmation_available_at <= self.decision_time
            and self.decision_time < self.earliest_entry_time
        )


@dataclass
class _Window:
    """High/low of the window being built."""

    key: object = None
    high: float = float("-inf")
    low: float = float("inf")


@dataclass
class _Pending:
    name: str
    level: float
    side: str
    breach_time: datetime
    detected_at: datetime
    waited: int = 0


ENTRY_DELAY = timedelta(seconds=1)


@dataclass
class BreachDetector:
    """Streaming detector.

    ``window_key(bar)`` returns the window a bar belongs to (its trading day, the Asia session of
    that day, or None when the bar is outside every window). A window's high/low only become a level
    once the window has ENDED, i.e. from the first later bar that is not in it. ``entry_delay`` is
    the earliest executable instant after a decision (decision at bar close, order after the delay).
    """

    window_key: Callable[[Bar], object]
    level_name: str
    accept_bars: int
    entry_delay: timedelta = ENTRY_DELAY
    _window: _Window = field(default_factory=_Window)
    _prev_high: float | None = None
    _prev_low: float | None = None
    _pending: list[_Pending] = field(default_factory=list)
    _fired: set[str] = field(default_factory=set)
    _last: Bar | None = None

    def __post_init__(self) -> None:
        if self.accept_bars < 1 or self.entry_delay <= timedelta(0):
            msg = "accept_bars must be >= 1 and entry_delay positive"
            raise ValueError(msg)

    def _event(self, p: _Pending, state: EventState, at: Bar) -> LevelEvent:
        return LevelEvent(
            level_name=p.name,
            level=p.level,
            side=p.side,
            state=state,
            breach_time=p.breach_time,
            detected_at=p.detected_at,
            confirmation_available_at=at.close_time,
            decision_time=at.close_time,
            earliest_entry_time=at.close_time + self.entry_delay,
            bars_waited=p.waited,
        )

    def step(self, bar: Bar) -> list[LevelEvent]:
        """Consume one closed bar and return the events that resolve on it."""
        if self._last is not None and bar.close_time <= self._last.close_time:
            msg = "bars must arrive in strictly increasing close time"
            raise ValueError(msg)
        self._last = bar
        out: list[LevelEvent] = []
        # 1. pending events are resolved by this bar's close alone
        still: list[_Pending] = []
        for p in self._pending:
            p.waited += 1
            beyond = bar.close > p.level if p.side == "UP" else bar.close < p.level
            if not beyond:
                out.append(self._event(p, EventState.REJECTED, bar))
            elif p.waited >= self.accept_bars:
                out.append(self._event(p, EventState.ACCEPTED, bar))
            else:
                still.append(p)
        self._pending = still
        # 2. a window that has ended becomes a level; the current window never is one
        key = self.window_key(bar)
        win = self._window
        if win.key is not None and key != win.key:
            self._prev_high, self._prev_low = win.high, win.low
            self._window = win = _Window()
            self._fired = set()  # a new level set: each side may fire once
        # 3. does this bar breach a completed level? A bar that pokes through and closes back
        #    inside is already rejected at its own close; one that closes beyond has to hold.
        for level, side, name in (
            (self._prev_high, "UP", "_high"),
            (self._prev_low, "DOWN", "_low"),
        ):
            if level is None or side in self._fired:
                continue
            poked = bar.high > level if side == "UP" else bar.low < level
            if not poked:
                continue
            self._fired.add(side)
            pend = _Pending(self.level_name + name, level, side, bar.close_time, bar.close_time)
            closed_beyond = bar.close > level if side == "UP" else bar.close < level
            if closed_beyond:
                self._pending.append(pend)
            else:
                out.append(self._event(pend, EventState.REJECTED, bar))
        # 4. only now fold this bar into the window statistics
        if key is not None:
            win.key = key
            win.high = max(win.high, bar.high)
            win.low = min(win.low, bar.low)
        return out

    def finish(self) -> list[LevelEvent]:
        """End of data: whatever is still waiting is UNRESOLVED (never guessed)."""
        if self._last is None:
            return []
        out = [self._event(p, EventState.UNRESOLVED, self._last) for p in self._pending]
        self._pending = []
        return out


def detect(
    bars: Iterable[Bar],
    *,
    window_key: Callable[[Bar], object],
    level_name: str,
    accept_bars: int,
) -> list[LevelEvent]:
    """Run a detector over a whole series (events in resolution order, UNRESOLVED last)."""
    detector = BreachDetector(window_key, level_name, accept_bars)
    events: list[LevelEvent] = []
    for bar in bars:
        events.extend(detector.step(bar))
    events.extend(detector.finish())
    return events


def day_key(bar: Bar) -> object:
    """Calendar-day window keyed by the bar's UTC open date."""
    return bar.open_time.date()


def hour_window_key(start_hour: int, end_hour: int) -> Callable[[Bar], object]:
    """Window of the hours [start, end) of each UTC day (e.g. an Asia range); else no window."""

    def key(bar: Bar) -> object:
        hour = bar.open_time.hour
        return bar.open_time.date() if start_hour <= hour < end_hour else None

    return key


def volatility_compressed(bars: list[Bar], short: int, long: int, threshold: float) -> bool | None:
    """True when mean range of the last ``short`` bars is below ``threshold`` x the last ``long``.

    Uses only the bars passed in (the caller passes bars up to the decision time). None when there
    are not enough bars.
    """
    if short < 1 or long <= short or len(bars) < long:
        return None
    ranges = [b.high - b.low for b in bars[-long:]]
    long_mean = sum(ranges) / long
    if long_mean == 0:
        return None
    return (sum(ranges[-short:]) / short) < threshold * long_mean


def trend_context(closes: list[float], n: int) -> str:
    """UP, DOWN or FLAT from the last close against the mean of the last ``n`` closes."""
    if n < 2 or len(closes) < n:
        return "UNKNOWN"
    mean = sum(closes[-n:]) / n
    if closes[-1] > mean:
        return "UP"
    return "DOWN" if closes[-1] < mean else "FLAT"
