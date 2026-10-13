"""Golden decision streams: each baseline version's behaviour on seeded synthetic bars is pinned.

If one of these hashes changes, a baseline version's behaviour changed. That must be a NEW version
(with its own pre-registration), never an edit of an existing one: update the pin only together
with a version bump.
"""

from __future__ import annotations

import functools
import hashlib
import json

import pytest

from tests.unit.trading.helpers import SPEC, m1_series, resample
from xau_edge.domain.timeframe import Timeframe
from xau_edge.trading.baseline import BaselineConfig
from xau_edge.trading.decision_core import SnapshotInputs, comparable, evaluate
from xau_edge.trading.frames import MultiTfBars, from_frames
from xau_edge.trading.market_state import SnapshotMemo

TFS = {
    Timeframe.M1: 1,
    Timeframe.M5: 5,
    Timeframe.M15: 15,
    Timeframe.M30: 30,
    Timeframe.H1: 60,
    Timeframe.H4: 240,
}
PINS = {
    "1.1.0": "773e001992ce0835",
    "1.2.0": "f93b54755bd45eda",
    "1.2.1": "f93b54755bd45eda",
}


@functools.cache
def _bars() -> MultiTfBars:
    m1 = m1_series(24_000, seed=2026, drift=0.004, vol=0.45)
    return from_frames({tf: (m1 if n == 1 else resample(m1, n)) for tf, n in TFS.items()})


@functools.cache
def stream_hash(version: str) -> str:
    bars = _bars()
    cfg = BaselineConfig(allow_unknown_news=True, version=version)
    memo = SnapshotMemo()
    digest = hashlib.sha256()
    closes = bars.frames[Timeframe.M5]["available_at"].to_list()[-2400::120]
    for at in closes:
        m5 = bars.as_of(Timeframe.M5, at)
        assert m5 is not None
        close, spread = float(m5["close"][-1]), float(m5["spread"][-1])
        inputs = SnapshotInputs(
            bars.truncated(at), at, close, close + spread * SPEC.point, spread, SPEC, 10_000.0,
            "UNKNOWN", True, True,
        )  # fmt: skip
        _, signal = evaluate(inputs, cfg, None, memo)
        record = comparable(signal)  # floats are left out on purpose: the pin must not flake on
        # last-digit differences between numpy/polars builds; levels are pinned by other tests
        digest.update(
            json.dumps(
                {
                    "decision": record["decision"],
                    "refusals": record["refusals"],
                    "setup_id": record["setup_id"],
                    "phase": signal.metadata.get("setup_phase"),
                },
                sort_keys=True,
            ).encode()
        )
    return digest.hexdigest()[:16]


@pytest.mark.parametrize("version", ["1.1.0", "1.2.0", "1.2.1"])
def test_each_baseline_version_keeps_its_pinned_behaviour(version: str) -> None:
    assert stream_hash(version) == PINS[version]


def test_the_versions_are_genuinely_different_streams() -> None:
    hashes = {v: stream_hash(v) for v in ("1.1.0", "1.2.0")}
    assert len(set(hashes.values())) == 2
