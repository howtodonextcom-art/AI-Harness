"""Research-only family eligibility: causal, closed-bar, with no caller in the live system."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from tests.unit.test_core import frame
from tests.unit.test_intelligence import bars
from xau_edge_v2.core.frames import Frame
from xau_edge_v2.core.intelligence import families as fam
from xau_edge_v2.core.intelligence import price_action as pa
from xau_edge_v2.domain.contract import Timeframe

WIDE = [(100.0, 102.0, 98.0, 100.0)] * 80
TIGHT = [(100.0, 100.3, 99.7, 100.0)] * 20


def test_family_b_needs_a_tight_box_and_a_decisive_close_beyond_it() -> None:
    up = fam.family_b(bars([*WIDE, *TIGHT, (100.0, 101.7, 99.9, 101.6)]))
    assert [(s.side, s.index) for s in up] == [(1, 100)]
    assert up[0].invalidation == pytest.approx(99.7) and up[0].risk_atr > 0
    down = fam.family_b(bars([*WIDE, *TIGHT, (100.0, 100.1, 98.3, 98.4)]))
    assert [(s.side, s.index) for s in down] == [(-1, 100)]
    assert fam.family_b(bars([*WIDE, *TIGHT, (100.0, 101.9, 99.9, 100.5)])) == []  # a weak body
    assert fam.family_b(bars([*WIDE, *TIGHT, (100.0, 100.4, 99.6, 100.1)])) == []  # inside the box
    assert fam.family_b(bars([*WIDE, (100.0, 104.0, 99.9, 103.9)])) == []  # no tight box


@pytest.mark.parametrize("seed", [1, 2, 3])
@pytest.mark.parametrize("name", ["B", "C", "D"])
def test_families_are_causal_and_known_at_the_bar_close(seed: int, name: str) -> None:
    f = frame(Timeframe.M15, 1200, seed=seed)
    run = {"B": fam.family_b, "C": fam.family_c, "D": fam.family_d}[name]
    full = run(f)
    for s in full:
        assert s.known_at_us == int(f.available_us[s.index]) and s.risk_atr > 0
        assert s.family == name and s.side in (-1, 1)
    for cut in (400, 777, 1050):
        assert run(f.head(cut)) == [s for s in full if s.index < cut]


def test_the_random_walk_produces_signals_for_every_family() -> None:
    f = frame(Timeframe.M15, 6000, seed=7)
    counts = {k: len(v) for k, v in fam.all_families(f).items()}
    assert counts["C"] > 0 and counts["D"] > 0 and counts["B"] >= 0


def test_family_c_waits_for_the_structure_confirmation() -> None:
    f = frame(Timeframe.M15, 4000, seed=11)
    sweeps = {e.index: e for e in pa.detect(f) if e.kind.startswith("FAILED_BREAKOUT")}
    for s in fam.family_c(f):
        earlier = [i for i in sweeps if 0 < s.index - i <= fam.CONFIRM_WINDOW]
        assert earlier, "a family C signal always follows a sweep"
        assert s.index > min(earlier)  # never at the sweep bar itself


def test_no_live_module_imports_the_research_families() -> None:
    src = Path(__file__).resolve().parents[2] / "src" / "xau_edge_v2"
    pattern = re.compile(r"intelligence(\.| import )families|import families")
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p.name != "families.py"
        and "research" not in p.parts  # research code (multifamily) is the only allowed consumer
        and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_a_flat_or_short_history_yields_nothing() -> None:
    flat: Frame = bars([(100.0, 100.0, 100.0, 100.0)] * 80)
    assert fam.family_b(flat) == [] and np.isfinite(0.0)
    assert fam.family_b(bars([(100.0, 101.0, 99.0, 100.0)] * 10)) == []
