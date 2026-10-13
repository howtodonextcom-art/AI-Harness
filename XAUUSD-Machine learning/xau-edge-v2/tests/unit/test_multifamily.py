"""MULTIFAMILY_RESEARCH_0.1.0 contract: geometry, gates, expiry, episodes, overlap, causality."""

from __future__ import annotations

import re
from itertools import pairwise
from pathlib import Path

import pytest

from tests.unit.test_core import frame
from tests.unit.test_intelligence import bars
from xau_edge_v2.core.risk import SymbolSpec, compute_stop, compute_targets
from xau_edge_v2.domain.contract import Timeframe
from xau_edge_v2.research import multifamily as mf

WIDE = [(100.0, 102.0, 98.0, 100.0)] * 80
TIGHT = [(100.0, 100.3, 99.7, 100.0)] * 20


def only(records: list[mf.MfRecord], family: str) -> list[mf.MfRecord]:
    return [r for r in records if r.family == family]


def test_a_family_b_order_uses_the_controls_geometry_and_the_cost_screen() -> None:
    f = bars([*WIDE, *TIGHT, (100.0, 101.7, 99.9, 101.6)])
    rec = only(mf.evaluate_frame(f), "B")
    assert len(rec) == 1
    r = rec[0]
    spread_price = float(f.spread[r.index]) * mf.POINT
    assert r.side == 1 and r.entry == pytest.approx(101.6 + spread_price)  # buys at the ask
    atr = r.risk_atr
    assert atr is not None and r.stop is not None
    stop = compute_stop(1, r.entry, 99.7, abs(r.entry - r.stop) / atr)
    assert stop is not None and stop.price == pytest.approx(r.stop)
    assert r.expiry_us == r.known_at_us + 3 * f.timeframe.seconds * 1_000_000
    if r.first_refusal is None:
        assert r.target is not None and r.net_rr is not None and r.net_rr >= 1.5
        assert r.cost_r == pytest.approx(
            (spread_price + 2 * mf.SLIPPAGE_POINTS * mf.POINT) / abs(r.entry - r.stop)
        )


def test_a_sell_enters_at_the_bid() -> None:
    f = bars([*WIDE, *TIGHT, (100.0, 100.1, 98.3, 98.4)])
    r = only(mf.evaluate_frame(f), "B")[0]
    assert r.side == -1 and r.entry == pytest.approx(98.4)


def test_the_gate_names_the_first_refusal_in_a_fixed_order() -> None:
    assert mf.GATES == ("EPISODE", "CLEARANCE", "STOP", "TARGET", "COST")
    f = frame(Timeframe.M15, 6000, seed=5)
    recs = mf.evaluate_frame(f)
    assert recs
    for r in recs:
        assert (r.first_refusal is None) or r.first_refusal in mf.GATES
        if not r.episode_head:
            assert r.first_refusal == "EPISODE"
        if r.first_refusal is None:
            assert r.stop is not None and r.target is not None and r.cost_r is not None
            assert r.cost_r <= mf.COST_R_MAX and (r.net_rr or 0) >= 1.5
            assert (r.risk_atr or 0) <= 3.0 + 1e-9
        if r.first_refusal == "STOP":
            assert r.target is None


def test_a_stop_beyond_three_atr_is_refused() -> None:
    f = frame(Timeframe.M15, 6000, seed=9)
    refused = [r for r in mf.evaluate_frame(f) if r.first_refusal == "STOP"]
    for r in refused:
        assert r.stop is None  # the control's rule: no acceptable stop, no order


def test_episodes_keep_only_the_first_signal_of_a_cluster() -> None:
    f = frame(Timeframe.M15, 6000, seed=2)
    by: dict[tuple[str, int], list[mf.MfRecord]] = {}
    for r in mf.evaluate_frame(f):
        by.setdefault((r.family, r.side), []).append(r)
    for rs in by.values():
        heads = [r for r in rs if r.episode_head]
        for a, b in pairwise(heads):
            assert b.index - a.index > mf.EPISODE_BARS


def test_overlap_is_flagged_not_hidden() -> None:
    f = frame(Timeframe.M15, 8000, seed=3)
    acc = [r for r in mf.evaluate_frame(f) if r.accepted]
    for fam_name in "BCD":
        rs = [r for r in acc if r.family == fam_name]
        free = [r for r in rs if not r.overlap]
        for a, b in pairwise(free):
            assert b.index - a.index > mf.MAX_HOLD_BARS
        assert all(r.overlap for r in rs if r not in free)


@pytest.mark.parametrize("seed", [1, 4])
def test_the_contract_is_causal(seed: int) -> None:
    f = frame(Timeframe.M15, 3000, seed=seed)
    full = mf.evaluate_frame(f)
    for cut in (800, 1500, 2400):
        part = mf.evaluate_frame(f.head(cut))
        assert part == [r for r in full if r.index < cut]


def test_the_geometry_is_the_controls_not_a_new_one() -> None:
    spec = SymbolSpec()
    assert spec == mf.SPEC
    stop = compute_stop(1, 100.0, 99.0, 1.0)
    assert stop is not None
    assert compute_targets(1, 100.0, stop, spread=0.2, atr=1.0) is not None


def test_nothing_live_imports_the_research_contract() -> None:
    src = Path(__file__).resolve().parents[2] / "src" / "xau_edge_v2"
    pattern = re.compile(r"research(\.| import )multifamily|import multifamily")
    offenders = [
        str(p.relative_to(src))
        for p in src.rglob("*.py")
        if p.name != "multifamily.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []
