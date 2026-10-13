"""F6: the lifecycle is a deterministic, restartable replay (research/replay.py).

Decision of Gate B2: the planned stop stays where the setup formed (no sliding); a run is one continuous
replay; a restart from a checkpoint equals the continuous run; if the checkpoint cannot be restored the
engine goes COLD and C1 decisions are WAIT until the state is provably the same as a continuous run's.
"""

from __future__ import annotations

import json
import random
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from tests.unit.test_candidate import CTX, buy_state, sell_state
from xau_edge_v2.core.candidate import (
    CAND_VERSION,
    MEMORY_BARS,
    RESTORE_CODE,
    VARIANTS,
    Observation,
    config_for,
)
from xau_edge_v2.core.market_state import MarketState
from xau_edge_v2.research.replay import (
    Checkpoint,
    Replay,
    digest_of,
    load_checkpoint,
    save_checkpoint,
)

STEP = 300_000_000  # five minutes in microseconds
T0 = 1_300_000_000_000_000
SPEC = "a" * 64
STORE = "b" * 64
CFGS = {v: config_for(v) for v in VARIANTS}


def make_stream(seed: int, n: int = 900) -> list[tuple[int, MarketState | None, Observation]]:
    """Long armed runs (the planned stop depends on how far back the arming bar is), flips, shocks, gaps."""
    rng = random.Random(seed)
    out: list[tuple[int, MarketState | None, Observation]] = []
    i = 0
    swing = 1996.0
    while i < n:
        kind = rng.choice(["armed_long", "armed_short", "off", "armed_long", "mixed"])
        length = (
            rng.choice([4, 9, 30, 120, 160]) if kind.startswith("armed") else rng.choice([3, 8, 20])
        )
        for _ in range(length):
            if i >= n:
                break
            swing += rng.uniform(-0.04, 0.06)  # the M5 swing keeps moving while the setup holds
            snap = buy_state().snapshots["M5"]
            snap = replace(snap, last_swing_low=swing, last_swing_high=swing + 8.0)
            if kind == "armed_long":
                st = buy_state(
                    snapshots={"M5": snap}, m5_momentum=rng.choice(["FLAT", "FLAT", "UP"])
                )
            elif kind == "armed_short":
                st = replace(
                    sell_state(),
                    snapshots={"M5": snap},
                    m5_momentum=rng.choice(["FLAT", "FLAT", "DOWN"]),
                )
            elif kind == "off":
                st = buy_state(
                    snapshots={"M5": snap},
                    m15_structure="RANGE",
                    m15_pullback="NONE",
                    m5_momentum="UP",
                )
            else:
                st = buy_state(
                    snapshots={"M5": snap},
                    m15_pullback=rng.choice(["NONE", "PULLBACK_IN_UPTREND"]),
                    m5_momentum=rng.choice(["UP", "FLAT"]),
                    volatility_regime=rng.choice(["NORMAL", "HIGH", "LOW"]),
                    spread=rng.choice([25.0, 60.0]),
                    h1_trend=rng.choice(["BULLISH", "BULLISH", "BEARISH", "NEUTRAL"]),
                )
            obs = Observation(
                shock=rng.random() < 0.02,
                m5_close=swing + rng.uniform(-3.0, 9.0),
                h1_resistance=rng.choice([None, 2040.0]),
                h1_support=rng.choice([None, 1960.0]),
            )
            # a missing-data bar now and then: the lifecycle is cleared
            out.append((T0 + i * STEP, None if rng.random() < 0.01 else st, obs))
            i += 1
    return out


def run(stream, engine: Replay, start: int = 0, stop: int | None = None):
    rows = []
    for open_us, st, obs in stream[start:stop]:
        if st is None:
            engine.skip(open_us)
            rows.append(None)
            continue
        out = engine.step(open_us, st, CTX, obs)
        rows.append({v: (d, info) for v, (d, info) in out.items()})
    return rows


def fresh() -> Replay:
    return Replay(CFGS, spec_sha256=SPEC, store_manifest_sha256=STORE)


def opens(stream) -> np.ndarray:
    return np.array([t for t, _, _ in stream], dtype=np.int64)


def restored(path: Path, stream) -> Replay:
    return Replay.restore(
        path, CFGS, spec_sha256=SPEC, store_manifest_sha256=STORE, run_opens=opens(stream)
    )


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_restart_from_a_checkpoint_equals_the_continuous_run(seed: int, tmp_path: Path) -> None:
    stream = make_stream(seed)
    continuous = run(stream, fresh())
    signals = sum(1 for r in continuous if r and any(d.action != "WAIT" for d, _ in r.values()))
    assert signals > 20  # the comparison is not vacuous
    for k in (1, 7, 37, 150, 333, 600, len(stream) - 1):
        first = fresh()
        run(stream, first, 0, k)
        path = tmp_path / f"cp{k}.json"
        save_checkpoint(path, first.checkpoint())
        second = restored(path, stream)
        assert second.status == "RESTORED"
        assert second.resume_index(opens(stream)) == k
        rest = run(stream, second, k)
        assert rest == continuous[k:], f"restart at bar {k} differs from the continuous run"


def test_the_planned_stop_stays_where_the_setup_formed(tmp_path: Path) -> None:
    stream = [
        (
            T0 + i * STEP,
            buy_state(
                snapshots={
                    "M5": replace(buy_state().snapshots["M5"], last_swing_low=1996.0 + 0.05 * i)
                },
                m5_momentum="FLAT",
            ),
            Observation(m5_close=2000.0),
        )
        for i in range(150)
    ]
    eng = fresh()
    stops = set()
    for open_us, st, obs in stream:
        eng.step(open_us, st, CTX, obs)
        stops.add(eng.memories["A_C1"].planned_stop)
    assert len(stops) == 1  # no sliding with the M5 swing
    path = tmp_path / "cp.json"
    first = fresh()
    run(stream, first, 0, 100)
    save_checkpoint(path, first.checkpoint())
    second = restored(path, stream)
    run(stream, second, 100)
    assert second.memories["A_C1"].planned_stop == next(
        iter(stops)
    )  # and a restart keeps the SAME stop


def test_cold_start_waits_and_then_equals_the_continuous_run() -> None:
    stream = make_stream(5)
    continuous = run(stream, fresh())
    k = 40
    cold = Replay.restore(
        Path("does/not/exist.json"),
        CFGS,
        spec_sha256=SPEC,
        store_manifest_sha256=STORE,
        run_opens=opens(stream),
    )
    assert cold.status.startswith("COLD")
    c1 = [v for v in CFGS if CFGS[v].c1]
    vetoed = 0
    equal_after_cold = 0
    for i in range(k, len(stream)):
        was_cold = any(cold.memories[v].cold for v in c1)
        open_us, st, obs = stream[i]
        if st is None:
            cold.skip(open_us)
            continue
        out = cold.step(open_us, st, CTX, obs)
        ref = continuous[i]
        assert ref is not None
        for v, cfg in CFGS.items():
            d, info = out[v]
            if cfg.c1 and was_cold:
                if info.guard == RESTORE_CODE:
                    vetoed += 1
                assert (
                    d.action == "WAIT" or ref[v][0].action == "WAIT"
                )  # never acts on an unproven state
            else:
                assert d == ref[v][0], (
                    f"bar {i} {v}: not cold but different from the continuous run"
                )
                equal_after_cold += 1
    assert vetoed > 0  # the stream does exercise the cold path
    assert equal_after_cold > 1000


def test_a_cold_engine_equals_a_continuous_one_after_a_quiet_stretch() -> None:
    quiet = [
        (
            T0 + i * STEP,
            buy_state(m15_structure="RANGE", m15_pullback="NONE"),
            Observation(m5_close=2000.0),
        )
        for i in range(MEMORY_BARS + 3)
    ]
    tail = make_stream(9)[:200]
    tail = [(T0 + (len(quiet) + i) * STEP, st, obs) for i, (_, st, obs) in enumerate(tail)]
    stream = quiet + tail
    continuous = run(stream, fresh())
    cold = Replay.restore(
        Path("nope.json"),
        CFGS,
        spec_sha256=SPEC,
        store_manifest_sha256=STORE,
        run_opens=opens(stream),
    )
    rest = run(stream, cold)
    for i in range(MEMORY_BARS + 2, len(stream)):
        a, b = rest[i], continuous[i]
        assert (a is None) == (b is None)
        if a is not None and b is not None:
            assert {v: x[0] for v, x in a.items()} == {v: x[0] for v, x in b.items()}


def _seal_and_write(path: Path, payload: dict) -> None:
    import hashlib  # noqa: PLC0415

    body = {k: v for k, v in payload.items() if k != "payload_sha256"}
    body["payload_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    path.write_text(json.dumps(body), encoding="utf-8")


def test_a_checkpoint_that_cannot_be_trusted_means_cold_never_a_guess(tmp_path: Path) -> None:
    stream = make_stream(4, 200)
    good = fresh()
    run(stream, good, 0, 100)
    path = tmp_path / "cp.json"
    save_checkpoint(path, good.checkpoint())
    ok = restored(path, stream)
    assert ok.status == "RESTORED"
    payload = json.loads(path.read_text(encoding="utf-8"))

    cases: dict[str, tuple[dict, str]] = {
        "spec": ({"spec_sha256": "c" * 64}, "another spec"),
        "store": ({"store_manifest_sha256": "d" * 64}, "another data store"),
        "code": ({"code_version": CAND_VERSION + "-x"}, "another code version"),
        "variants": ({"variants": ["CTRL"]}, "other variants"),
        "bar": ({"last_bar_open_us": T0 + 7}, "not in this run"),
        "digest": ({"bars_digest": digest_of([1, 2, 3])}, "history differs"),
    }
    for name, (change, why) in cases.items():
        p = tmp_path / f"{name}.json"
        _seal_and_write(p, {**payload, **change})
        eng = restored(p, stream)
        assert eng.status.startswith("COLD"), name
        assert why in eng.status, name
        assert all(m.cold for m in eng.memories.values()), name
    (tmp_path / "corrupt.json").write_text(
        path.read_text(encoding="utf-8").replace('"bar_index": 100', '"bar_index": 99'),
        encoding="utf-8",
    )
    assert "corrupted" in restored(tmp_path / "corrupt.json", stream).status
    (tmp_path / "garbage.json").write_text("{not json", encoding="utf-8")
    assert restored(tmp_path / "garbage.json", stream).status.startswith("COLD")
    assert restored(tmp_path / "missing.json", stream).status == "COLD: no checkpoint"
    # a different run history (one bar shifted) is rejected
    shifted = [(t + STEP if i > 50 else t, s, o) for i, (t, s, o) in enumerate(stream)]
    assert (
        "history" in restored(path, shifted).status
        or "not in this run" in restored(path, shifted).status
    )


def test_save_is_atomic_and_keeps_the_previous_checkpoint(tmp_path: Path) -> None:
    stream = make_stream(6, 120)
    eng = fresh()
    path = tmp_path / "cp.json"
    run(stream, eng, 0, 50)
    save_checkpoint(path, eng.checkpoint())
    first_hash = path.read_text(encoding="utf-8")
    run(stream, eng, 50, 100)
    save_checkpoint(path, eng.checkpoint())
    assert path.with_suffix(".json.prev").read_text(encoding="utf-8") == first_hash
    assert not path.with_suffix(".json.tmp").exists()
    cp, why = load_checkpoint(path)
    assert why == "ok"
    assert isinstance(cp, Checkpoint)
    assert cp.bar_index == 100


def test_a_bar_without_data_clears_the_lifecycle_like_a_continuous_run(tmp_path: Path) -> None:
    stream = make_stream(8, 200)
    stream[60] = (stream[60][0], None, stream[60][2])
    a = fresh()
    ra = run(stream, a)
    b = fresh()
    run(stream, b, 0, 100)
    save_checkpoint(tmp_path / "cp.json", b.checkpoint())
    c = restored(tmp_path / "cp.json", stream)
    assert run(stream, c, 100) == ra[100:]


def test_every_flag_off_is_the_control_even_when_cold() -> None:
    stream = make_stream(10, 300)
    cold = Replay.restore(
        Path("nope.json"),
        {"CTRL": CFGS["CTRL"]},
        spec_sha256=SPEC,
        store_manifest_sha256=STORE,
        run_opens=opens(stream),
    )
    warm = Replay({"CTRL": CFGS["CTRL"]}, spec_sha256=SPEC, store_manifest_sha256=STORE)
    a, b = run(stream, cold), run(stream, warm)
    assert [r["CTRL"][0] for r in a if r] == [
        r["CTRL"][0] for r in b if r
    ]  # the decisions; only the bookkeeping label differs
