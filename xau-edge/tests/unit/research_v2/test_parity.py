"""Research-to-live parity: the streaming detector must equal the batch detector, bar for bar."""

from __future__ import annotations

import pytest

from tests.unit.research_v2.helpers import frame, random_walk
from xau_edge.research_v2.events import EventSet, sweep_events
from xau_edge.research_v2.frame import H1Frame, build_frame
from xau_edge.research_v2.stream import StreamBar, StreamEvent, StreamingSweep, replay_digest

VARIANTS = [
    (level_set, mode, eps)
    for level_set in ("PD", "ASIA")
    for mode in ("reject", "accept")
    for eps in (0.0, 0.25, 0.5)
]


def replay(f: H1Frame, level_set: str, mode: str, eps: float) -> tuple[list[StreamEvent], int]:
    detector = StreamingSweep(level_set, mode, eps)
    events: list[StreamEvent] = []
    for i in range(f.n):
        bar = StreamBar(
            t=int(f.t[i]),
            o=float(f.o[i]),
            h=float(f.h[i]),
            low=float(f.low[i]),
            c=float(f.c[i]),
            day=int(f.day[i]),
            utc_date=int(f.utc_date[i]),
            utc_hour=int(f.utc_hour[i]),
            unsafe_day=bool(f.unsafe_day[i]),
        )
        events.extend(detector.step(bar))
    return events, detector.events_unsafe


def as_pairs(events: EventSet) -> list[tuple[int, int, str]]:
    return [
        (int(d), int(s), lv)
        for d, s, lv in zip(events.decision, events.direction, events.level, strict=True)
    ]


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize(("level_set", "mode", "eps"), VARIANTS)
def test_streaming_equals_batch(seed: int, level_set: str, mode: str, eps: float) -> None:
    df = random_walk(weeks=12, seed=seed, vol=3.0)
    f = frame(df)
    batch = sweep_events(f, level_set, mode, eps)
    streamed, _unsafe = replay(f, level_set, mode, eps)
    assert [(e.index, e.direction, e.level) for e in streamed] == as_pairs(batch)


@pytest.mark.parametrize(("level_set", "mode"), [("PD", "reject"), ("ASIA", "accept")])
def test_parity_also_holds_when_unsafe_days_are_excluded(level_set: str, mode: str) -> None:
    df = random_walk(year=2016, weeks=40, seed=4, vol=4.0)
    f = build_frame(df, {2016})
    batch = sweep_events(f, level_set, mode, 0.0)
    streamed, unsafe = replay(f, level_set, mode, 0.0)
    assert [(e.index, e.direction, e.level) for e in streamed] == as_pairs(batch)
    assert unsafe == batch.excluded_unsafe
    assert unsafe > 0


def test_parity_survives_a_data_gap() -> None:
    df = random_walk(weeks=10, seed=6, vol=3.0)
    gapped = df.slice(0, 200).vstack(df.slice(230, df.height - 230))  # ~30 missing hours
    f = frame(gapped)
    for level_set, mode, eps in VARIANTS:
        batch = sweep_events(f, level_set, mode, eps)
        streamed, _ = replay(f, level_set, mode, eps)
        assert [(e.index, e.direction, e.level) for e in streamed] == as_pairs(batch)


def test_streaming_never_looks_ahead_a_prefix_gives_a_prefix() -> None:
    df = random_walk(weeks=12, seed=2, vol=3.0)
    full = frame(df)
    cut = full.n * 2 // 3
    head = frame(df.head(cut))
    for level_set, mode, eps in VARIANTS:
        a, _ = replay(full, level_set, mode, eps)
        b, _ = replay(head, level_set, mode, eps)
        assert [e for e in a if e.index < cut] == b


def test_the_parity_tests_are_not_vacuous() -> None:
    f = frame(random_walk(weeks=12, seed=1, vol=3.0))
    counts = {v: sweep_events(f, *v).n for v in VARIANTS}
    assert sum(counts.values()) > 100
    assert all(counts[("PD", "reject", 0.0)] > 0 for _ in [0])


def test_replay_is_deterministic_and_the_digest_detects_any_difference() -> None:
    f = frame(random_walk(weeks=12, seed=5, vol=3.0))
    a, _ = replay(f, "PD", "reject", 0.0)
    b, _ = replay(f, "PD", "reject", 0.0)
    assert a == b
    assert replay_digest(a) == replay_digest(b)
    assert replay_digest(a) != replay_digest(a[:-1])
    flipped = [StreamEvent(a[0].index, -a[0].direction, a[0].level), *a[1:]]
    assert replay_digest(flipped) != replay_digest(a)
